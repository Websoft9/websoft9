def should_skip_api_key_auth(path: str) -> bool:
    normalized_path = str(path or "").strip() or "/"
    if normalized_path.startswith("/api/"):
        normalized_path = normalized_path[4:]

    if normalized_path in {"/docs", "/openapi.json", "/redoc", "/healthz"}:
        return True

    if normalized_path.startswith("/static/"):
        return True

    if normalized_path.startswith("/integrations/"):
        return True

    if normalized_path.startswith("/auth/"):
        return True

    if normalized_path == "/setup-wizard" or normalized_path.startswith("/setup-wizard/"):
        return True

    if normalized_path == "/host-access/terminal/ws":
        return True

    if normalized_path.startswith("/files/"):
        return True

    if normalized_path.startswith("/logs/"):
        return True

    if normalized_path == "/overview" or normalized_path.startswith("/overview/"):
        return True

    if normalized_path == "/services" or normalized_path.startswith("/services/"):
        return True

    if normalized_path == "/proxys" or normalized_path.startswith("/proxys/"):
        return True

    if normalized_path == "/apps" or normalized_path.startswith("/apps/"):
        return True

    if normalized_path == "/settings" or normalized_path.startswith("/settings/"):
        return True

    if normalized_path.startswith("/apps/catalog/"):
        return True

    if normalized_path.startswith("/apps/available/"):
        return True

    if normalized_path == "/apps/install":
        return True

    if normalized_path == "/settings/domain":
        return True

    return False