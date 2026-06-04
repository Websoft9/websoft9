#!/usr/bin/env bash
set -euo pipefail

container_name="${1:-websoft9-product-current}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
console_dir="$repo_root/console"
apphub_dir="$repo_root/apphub"
supervisor_src="$repo_root/docker/supervisord.conf"
logging_config_src="$repo_root/docker/apphub/logging_config.yaml"
gateway_conf_dir="$repo_root/docker/gateway"
product_proxy_init_src="$repo_root/docker/proxy/init_nginx.sh"
portainer_init_src="$repo_root/docker/deployment/init_portainer.go"
npm_base_image="${WEBSOFT9_NPM_BASE_IMAGE:-jc21/nginx-proxy-manager:2.12.6}"
platform_container_entrypoint_src="$repo_root/docker/scripts/platform-container-entrypoint.sh"
platform_entrypoint_src="$repo_root/docker/scripts/platform-entrypoint.sh"
platform_healthcheck_src="$repo_root/docker/scripts/platform-healthcheck.sh"
platform_sync_config_src="$repo_root/docker/scripts/platform-sync-config.sh"
platform_runtime_assets_src="$repo_root/docker/scripts/platform-sync-runtime-assets.py"
service_control_src="$repo_root/docker/scripts/platform-service-control.sh"
portainer_start_src="$repo_root/docker/scripts/platform-start-portainer.sh"
gateway_start_src="$repo_root/docker/scripts/platform-start-gateway.sh"
npm_backend_start_src="$repo_root/docker/scripts/platform-start-npm-backend.sh"
npm_nginx_start_src="$repo_root/docker/scripts/platform-start-npm-nginx.sh"
legacy_files_agent_sidecar="${WEBSOFT9_FILES_AGENT_SIDECAR_NAME:-websoft9-files-agent-current}"

detect_docker_volumes_root() {
    local docker_root
    docker_root="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || true)"
    docker_root="${docker_root//$'\r'/}"
    docker_root="${docker_root%%[[:space:]]*}"
    if [[ -n "$docker_root" ]]; then
        printf '%s\n' "$docker_root/volumes"
        return 0
    fi

    local mountpoint
    mountpoint="$(docker volume inspect $(docker volume ls -q) --format '{{.Mountpoint}}' 2>/dev/null | head -n1 || true)"
    mountpoint="${mountpoint//$'\r'/}"
    mountpoint="${mountpoint%%[[:space:]]*}"
    if [[ -n "$mountpoint" ]]; then
        python3 - "$mountpoint" <<'PY'
import os
import sys

print(os.path.dirname(os.path.dirname(os.path.realpath(sys.argv[1]))))
PY
        return 0
    fi

    echo "Unable to detect Docker volumes root" >&2
    exit 1
}

docker_volumes_root="${WEBSOFT9_DOCKER_VOLUMES_ROOT:-$(detect_docker_volumes_root)}"

ensure_single_container_files_runtime() {
    local has_files_bind="false"
    local needs_port_rewire="false"

    if docker inspect "$container_name" --format '{{range .Mounts}}{{if and (eq .Type "bind") (eq .Source "'"$docker_volumes_root"'") (eq .Destination "'"$docker_volumes_root"'")}}present{{end}}{{end}}' | grep -q 'present'; then
        has_files_bind="true"
    fi

    if docker inspect "$container_name" --format '{{range $containerPort, $bindings := .HostConfig.PortBindings}}{{range $bindings}}{{printf "%s|%s\n" .HostPort $containerPort}}{{end}}{{end}}' | grep -q '^9000|8889/tcp$'; then
        needs_port_rewire="true"
    fi

    if [[ "$has_files_bind" == "true" && "$needs_port_rewire" == "false" ]]; then
        return 0
    fi

    if [[ "$has_files_bind" != "true" && "$needs_port_rewire" == "true" ]]; then
        echo "Single-container files runtime missing $docker_volumes_root bind and host port 9000 still targets container port 8889; recreating $container_name"
    elif [[ "$has_files_bind" != "true" ]]; then
        echo "Single-container files runtime missing $docker_volumes_root bind; recreating $container_name"
    else
        echo "Host port 9000 still targets container port 8889; recreating $container_name to publish container port 9000 instead"
    fi

    local image_name
    image_name="$(docker inspect "$container_name" --format '{{.Config.Image}}')"

    local restart_policy
    restart_policy="$(docker inspect "$container_name" --format '{{.HostConfig.RestartPolicy.Name}}')"
    restart_policy="${restart_policy:-no}"

    local network_name
    network_name="$(docker inspect "$container_name" --format '{{range $name, $settings := .NetworkSettings.Networks}}{{println $name}}{{end}}' | head -n1 | tr -d '[:space:]')"
    network_name="${network_name:-bridge}"

    local -a mount_args
    while IFS='|' read -r mount_type mount_name mount_source mount_destination mount_rw; do
        [[ -z "$mount_type" || -z "$mount_destination" ]] && continue
        [[ "$mount_destination" == "$docker_volumes_root" ]] && continue
        if [[ "$mount_type" == "bind" ]]; then
            local bind_spec="type=bind,src=$mount_source,dst=$mount_destination"
            if [[ "$mount_rw" == "false" ]]; then
                bind_spec+=",readonly"
            fi
            mount_args+=(--mount "$bind_spec")
        elif [[ "$mount_type" == "volume" ]]; then
            local volume_spec="type=volume,src=$mount_name,dst=$mount_destination"
            if [[ "$mount_rw" == "false" ]]; then
                volume_spec+=",readonly"
            fi
            mount_args+=(--mount "$volume_spec")
        fi
    done < <(docker inspect "$container_name" --format '{{range .Mounts}}{{printf "%s|%s|%s|%s|%t\n" .Type .Name .Source .Destination .RW}}{{end}}')

    local -a publish_args
    while IFS='|' read -r host_ip host_port container_port; do
        [[ -z "$host_port" || -z "$container_port" ]] && continue
        if [[ "$host_port" == "9000" && "$container_port" == "8889" ]]; then
            container_port="9000"
        fi
        local publish_spec="${host_port}:${container_port}"
        if [[ -n "$host_ip" && "$host_ip" != "0.0.0.0" ]]; then
            publish_spec="${host_ip}:${publish_spec}"
        fi
        publish_args+=(-p "$publish_spec")
    done < <(docker inspect "$container_name" --format '{{range $containerPort, $bindings := .HostConfig.PortBindings}}{{range $bindings}}{{printf "%s|%s|%s\n" .HostIp .HostPort $containerPort}}{{end}}{{end}}' | sed 's#/tcp$##')

    docker rm -f "$legacy_files_agent_sidecar" >/dev/null 2>&1 || true
    docker rm -f "$container_name"

    docker run -d \
        --name "$container_name" \
        --restart "$restart_policy" \
        --network "$network_name" \
        -e "WEBSOFT9_FILES_AGENT_ALLOWED_ROOTS=$docker_volumes_root" \
        "${publish_args[@]}" \
        "${mount_args[@]}" \
        --mount type=bind,src="$docker_volumes_root",dst="$docker_volumes_root" \
        "$image_name" >/dev/null

    for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
        if env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u all_proxy -u ALL_PROXY \
            curl -sf http://127.0.0.1:9000/api/healthz >/dev/null; then
            return 0
        fi
        if [[ "$attempt" == "30" ]]; then
            echo "Recreated product container did not become ready" >&2
            exit 1
        fi
        echo "Waiting for recreated product container (attempt $attempt/30)"
        python3 - <<'PY'
import time
time.sleep(1)
PY
    done
}

sync_runtime_support_files() {
    echo "Syncing supervisor runtime files to $container_name"
    local init_portainer_bin
    init_portainer_bin="$(mktemp)"
    go build -o "$init_portainer_bin" "$portainer_init_src"
    docker cp "$supervisor_src" "$container_name:/etc/supervisor/conf.d/websoft9-platform.conf"
    docker cp "$logging_config_src" "$container_name:/etc/supervisor/conf.d/logging_config.yaml"
    docker exec "$container_name" rm -f /etc/websoft9/platform-gateway/portainer-ui.conf
    docker cp "$gateway_conf_dir/." "$container_name:/etc/websoft9/platform-gateway/"
    docker cp "$init_portainer_bin" "$container_name:/usr/local/bin/init_portainer"
    docker cp "$product_proxy_init_src" "$container_name:/app/init_nginx.sh"
    docker cp "$platform_container_entrypoint_src" "$container_name:/websoft9/script/platform-container-entrypoint.sh"
    docker cp "$platform_entrypoint_src" "$container_name:/websoft9/script/platform-entrypoint.sh"
    docker cp "$platform_healthcheck_src" "$container_name:/websoft9/script/platform-healthcheck.sh"
    docker cp "$platform_sync_config_src" "$container_name:/websoft9/script/platform-sync-config.sh"
    docker cp "$platform_runtime_assets_src" "$container_name:/websoft9/script/platform-sync-runtime-assets.py"
    docker cp "$service_control_src" "$container_name:/websoft9/script/platform-service-control.sh"
    docker cp "$portainer_start_src" "$container_name:/websoft9/script/platform-start-portainer.sh"
    docker cp "$gateway_start_src" "$container_name:/websoft9/script/platform-start-gateway.sh"
    docker cp "$npm_backend_start_src" "$container_name:/websoft9/script/platform-start-npm-backend.sh"
    docker cp "$npm_nginx_start_src" "$container_name:/websoft9/script/platform-start-npm-nginx.sh"
    docker exec "$container_name" rm -f /etc/websoft9/stream.conf
    docker exec "$container_name" mkdir -p /var/log/websoft9/nginx-proxy-manager /run/nginx /tmp/nginx/body /tmp/npmuserhome /var/cache/nginx /var/lib/nginx/cache/private /var/lib/nginx/cache/public /var/log/nginx
    docker exec "$container_name" chmod +x /websoft9/script/platform-entrypoint.sh
    docker exec "$container_name" chmod +x /websoft9/script/platform-container-entrypoint.sh
    docker exec "$container_name" chmod +x /websoft9/script/platform-healthcheck.sh
    docker exec "$container_name" chmod +x /websoft9/script/platform-sync-config.sh
    docker exec "$container_name" chmod +x /websoft9/script/platform-sync-runtime-assets.py
    docker exec "$container_name" chmod +x /websoft9/script/platform-service-control.sh
    docker exec "$container_name" chmod +x /websoft9/script/platform-start-npm-backend.sh
    docker exec "$container_name" chmod +x /websoft9/script/platform-start-npm-nginx.sh
    docker exec "$container_name" chmod +x /websoft9/script/platform-start-portainer.sh
    docker exec "$container_name" chmod +x /websoft9/script/platform-start-gateway.sh
    docker exec "$container_name" chmod +x /app/init_nginx.sh
    docker exec "$container_name" chmod +x /usr/local/bin/init_portainer
    rm -f "$init_portainer_bin"
}

restore_npm_frontend_if_needed() {
    if docker exec "$container_name" sh -lc 'grep -q "Nginx Proxy Manager" /app/frontend/index.html' >/dev/null 2>&1; then
        return 0
    fi

    echo "Detected contaminated NPM frontend assets; restoring /app/frontend"

    local restore_dir
    restore_dir="$(mktemp -d)"

    if docker exec "$container_name" test -d /opt/websoft9-npm-frontend; then
        docker cp "$container_name:/opt/websoft9-npm-frontend/." "$restore_dir/"
    else
        local temp_container
        temp_container="$(docker create "$npm_base_image")"
        docker cp "$temp_container:/app/frontend/." "$restore_dir/"
        docker rm "$temp_container" >/dev/null
    fi

    docker exec "$container_name" rm -rf /app/frontend/*
    docker cp "$restore_dir/." "$container_name:/app/frontend/"
    rm -rf "$restore_dir"
}

ensure_service_log_runtime_paths() {
    docker exec "$container_name" sh -lc '
        mkdir -p /var/log/websoft9/gitea /var/log/websoft9/portainer
        if [ -d /data/logs ] && [ ! -e /var/log/websoft9/nginx-proxy-manager ]; then
            ln -s /data/logs /var/log/websoft9/nginx-proxy-manager
        fi
    '
}

ensure_single_container_files_runtime

echo "[1/6] Building console"
cd "$console_dir"
npm run build

echo "[2/6] Syncing console assets to $container_name:/etc/websoft9/console"
docker cp "$console_dir/dist/." "$container_name:/etc/websoft9/console/"

echo "[3/6] Syncing apphub source to $container_name:/websoft9/apphub/src"
tar -C "$apphub_dir" -cf - src | docker exec -i "$container_name" tar -C /websoft9/apphub -xf -

echo "[4/6] Updating single-container runtime support files"
docker rm -f "$legacy_files_agent_sidecar" >/dev/null 2>&1 || true
sync_runtime_support_files
restore_npm_frontend_if_needed

echo "[5/6] Syncing runtime assets and restarting runtime services"
ensure_service_log_runtime_paths
docker exec "$container_name" sh -lc 'rm -f /data/nginx/stream/stream.conf && nginx -s reload || true && /websoft9/script/platform-sync-config.sh --mode base && /websoft9/script/platform-sync-runtime-assets.py && /websoft9/script/platform-sync-config.sh --mode credentials && supervisorctl -c /etc/supervisor/conf.d/websoft9-platform.conf reread && supervisorctl -c /etc/supervisor/conf.d/websoft9-platform.conf update && supervisorctl -c /etc/supervisor/conf.d/websoft9-platform.conf restart portainer platform-gateway files-agent apphub-api npm-backend npm-nginx'

for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if docker exec "$container_name" python3 - <<'PY' >/dev/null 2>&1
import urllib.request
urllib.request.urlopen('http://127.0.0.1:8091/healthz', timeout=2).read()
PY
    then
        break
    fi
    if [[ "$attempt" == "10" ]]; then
        echo "files-agent process inside product container did not become ready" >&2
        exit 1
    fi
done

echo "[6/6] Verifying product entry"
for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u all_proxy -u ALL_PROXY \
        curl -sf http://127.0.0.1:9000/api/auth/status >/dev/null; then
        break
    fi
    if [[ "$attempt" == "10" ]]; then
        echo "Product API did not become ready after apphub restart" >&2
        exit 1
    fi
    echo "Waiting for product API to become ready (attempt $attempt/10)"
    python3 - <<'PY'
import time
time.sleep(1)
PY
done
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u all_proxy -u ALL_PROXY \
    curl -s http://127.0.0.1:9000 | grep -E 'index-.*\.(js|css)' -o

echo "Sync complete"