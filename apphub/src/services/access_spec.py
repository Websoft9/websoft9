import json
import re
from pathlib import Path
from urllib.parse import unquote

URL_SCHEMES = {"http", "https", "ws", "wss"}
PORT_EXPRESSION = re.compile(r"\$\{([A-Za-z_][A-Za-z_0-9]*)(?::-([0-9]+))?\}")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
SENSITIVE_QUERY_KEYS = {"token", "access_token", "password", "secret", "api_key", "authorization"}


def classify_access(variables: dict) -> str:
    if not isinstance(variables, dict):
        raise ValueError("Invalid access metadata: variables.json must be an object.")
    if "access" not in variables or isinstance(variables["access"], dict):
        return "legacy"
    if isinstance(variables["access"], list):
        return "v2"
    raise ValueError("Invalid access declaration: expected an array or a legacy object.")


def _port(value, env: dict) -> int:
    reference = PORT_EXPRESSION.fullmatch(value) if isinstance(value, str) else None
    if reference:
        value = env.get(reference[1]) or reference[2]
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        value = int(value)
    if type(value) is not int or not 1 <= value <= 65535:
        raise ValueError("invalid or unresolved port")
    return value


def _published_ports(service: dict, env: dict) -> dict:
    ports = {}
    for item in service.get("ports") or []:
        if isinstance(item, dict):
            target, published, protocol = item.get("target"), item.get("published"), item.get("protocol", "tcp")
        else:
            binding, _, protocol = str(item).partition("/")
            binding = PORT_EXPRESSION.sub(lambda reference: str(_port(reference[0], env)), binding)
            parts = binding.rsplit(":", 2)
            target, published = parts[-1], parts[-2] if len(parts) > 1 else None
            protocol = protocol or "tcp"
        key = (_port(target, env), protocol)
        if key in ports:
            raise ValueError("ambiguous published port for access target")
        ports[key] = _port(published, env) if published is not None else None
    return ports


def _endpoint(value, roles: dict, schemes: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("endpoint must be an object")
    scheme, names = value.get("scheme"), value.get("roles")
    if not isinstance(scheme, str) or scheme not in schemes or not isinstance(names, list) or not names:
        raise ValueError("invalid endpoint scheme or roles")
    if any(not isinstance(name, str) or name not in roles or scheme not in roles[name]["schemes"] for name in names):
        raise ValueError("endpoint scheme conflicts with role")
    if len(set(names)) != len(names):
        raise ValueError("duplicate endpoint role")
    result = {"scheme": scheme, "roles": names, "kind": roles[names[0]]["kind"], "address": schemes[scheme]["address"]}
    if scheme not in URL_SCHEMES:
        if "path" in value or "query" in value:
            raise ValueError("non-URL endpoint cannot set path or query")
        return result
    path, query = value.get("path", "/"), value.get("query", {})
    if not isinstance(path, str) or not path.startswith("/") or re.search(r"[?#]|%(?![\da-fA-F]{2})", path):
        raise ValueError("invalid endpoint path")
    decoded = unquote(path, errors="strict")
    if (
        not decoded.startswith("/")
        or decoded.startswith("//")
        or "\\" in decoded
        or CONTROL.search(decoded)
        or any(part in {".", ".."} for part in decoded.split("/"))
    ):
        raise ValueError("unsafe endpoint path")
    if not isinstance(query, dict) or any(
        not isinstance(item, str)
        or key.casefold() in SENSITIVE_QUERY_KEYS
        or any(CONTROL.search(part) or "${" in part or "{{" in part for part in (key, item))
        for key, item in query.items()
    ):
        raise ValueError("invalid endpoint query")
    return {**result, "path": path, "query": query}


def access_preview_fields(app_dir: Path, variables: dict, env: dict) -> dict:
    if classify_access(variables) == "legacy":
        return {}
    import yaml

    try:
        compose = yaml.safe_load((app_dir / "docker-compose.yml").read_text(encoding="utf-8"))
        services = compose["services"]
        if not isinstance(services, dict):
            raise ValueError("Compose services must be an object")
        roles, schemes = {}, {}
        if variables["access"]:
            dictionary = json.loads((app_dir.parents[1] / "metadata" / "access-types.json").read_text(encoding="utf-8"))
            roles, schemes = dictionary["roles"], dictionary["schemes"]
        groups, unmanaged = [], []
        seen_ids, seen_targets, seen_env = set(), set(), set()
        for service_name, service in services.items():
            for binding in service.get("x-websoft9-unmanaged-ports", {}):
                target, protocol = binding.split("/")
                port = _published_ports(service, env).get((_port(target, env), protocol))
                if port is None:
                    raise ValueError("unmanaged port is not published")
                unmanaged.append(
                    {"service": service_name, "container_port": int(target), "protocol": protocol, "mapped_port": port}
                )
        for group in variables["access"]:
            group_id, service_name, port_expr = group["id"], group["service"], group["port"]
            if not isinstance(group_id, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", group_id) or group_id in seen_ids:
                raise ValueError("invalid or duplicate access group id")
            service = services[service_name]
            if str(service.get("restart", "")).lower() == "no":
                raise ValueError("access target is a one-shot service")
            port, protocol = _port(port_expr, env), group.get("protocol", "tcp")
            if protocol not in {"tcp", "udp"} or (service_name, port, protocol) in seen_targets:
                raise ValueError("invalid or duplicate access target")
            seen_ids.add(group_id)
            seen_targets.add((service_name, port, protocol))
            public = group["public"]
            require_domain, require_https = group.get("requireDomain", False), group.get("requireHttps", False)
            if any(type(flag) is not bool for flag in (public, require_domain, require_https)):
                raise ValueError("access flags must be booleans")
            mapped_port = _published_ports(service, env).get((port, protocol))
            if public != (mapped_port is not None):
                raise ValueError("access public flag disagrees with Compose publication")
            if not isinstance(group["endpoints"], list):
                raise ValueError("access endpoints must be an array")
            endpoints = [_endpoint(item, roles, schemes) for item in group["endpoints"]]
            url_schemes = {item["scheme"] for item in endpoints} & URL_SCHEMES
            if (require_domain or require_https or "rootUrl" in group or "host" in group) and not url_schemes:
                raise ValueError("access group requires a URL-capable endpoint")
            if require_https and public and url_schemes & {"http", "ws"}:
                raise ValueError("a plaintext listener requiring HTTPS cannot be published")
            address_fields = set()
            for field in ("rootUrl", "host", "mappedPort"):
                names = group.get(field, [])
                if not isinstance(names, list):
                    raise ValueError("access variable targets must be an array")
                for name in names:
                    if not isinstance(name, str) or name.startswith("W9_") or name not in env or name in seen_env:
                        raise ValueError("invalid or duplicate access variable target")
                    seen_env.add(name)
                    if field != "mappedPort":
                        address_fields.add(name)
            kind = next((name for name in ("ui", "api", "infra") if any(item["kind"] == name for item in endpoints)), "infra")
            groups.append(
                {
                    "id": group_id,
                    "service": service_name,
                    "container_port": port,
                    "port_expr": str(port_expr),
                    "protocol": protocol,
                    "public": public,
                    "default_mapped_port": mapped_port,
                    "purpose": group.get("purpose", ""),
                    "can_bind_domain": bool(url_schemes),
                    "require_domain": require_domain,
                    "require_https": require_https,
                    "supports_primary_domain": bool(address_fields),
                    "first_startup_locked": bool(
                        address_fields.intersection((variables.get("env") or {}).get("first_startup_only", []))
                    ),
                    "forward_scheme": "https" if url_schemes & {"https", "wss"} else "http",
                    "main_kind": kind,
                    "endpoints": endpoints,
                }
            )
    except (AttributeError, KeyError, TypeError, ValueError, OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Invalid access metadata for {app_dir.name}: {exc}") from exc
    first_url_group = next((group for group in groups if group["can_bind_domain"]), None)
    return {
        "access": groups,
        "unmanaged_ports": unmanaged,
        "is_web_app": first_url_group is not None,
        "default_scheme": "https"
        if first_url_group and (first_url_group["require_https"] or first_url_group["forward_scheme"] == "https")
        else "http",
        "settings": {
            key: value
            for key, value in env.items()
            if key.startswith("W9_") and key.endswith("_SET") and not key.endswith("_PORT_SET")
        },
    }
