#!/usr/bin/env bash
set -euo pipefail

container_name="${1:-websoft9-product-current}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
console_dir="$repo_root/console"
apphub_dir="$repo_root/apphub"
supervisor_src="$repo_root/docker/product/supervisord.conf"
service_control_src="$repo_root/docker/product/scripts/platform-service-control.sh"
legacy_files_agent_sidecar="${WEBSOFT9_FILES_AGENT_SIDECAR_NAME:-websoft9-files-agent-current}"

ensure_single_container_files_runtime() {
    if docker inspect "$container_name" --format '{{range .Mounts}}{{if and (eq .Type "bind") (eq .Destination "/var/lib/docker/volumes")}}present{{end}}{{end}}' | grep -q 'present'; then
        return 0
    fi

    echo "Single-container files runtime missing /var/lib/docker/volumes bind; recreating $container_name"

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
        [[ "$mount_destination" == "/var/lib/docker/volumes" ]] && continue
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
        "${publish_args[@]}" \
        "${mount_args[@]}" \
        --mount type=bind,src=/var/lib/docker/volumes,dst=/var/lib/docker/volumes \
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
    docker cp "$supervisor_src" "$container_name:/etc/supervisor/conf.d/websoft9-platform.conf"
    docker cp "$service_control_src" "$container_name:/websoft9/script/platform-service-control.sh"
    docker exec "$container_name" chmod +x /websoft9/script/platform-service-control.sh
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

echo "[5/6] Reloading supervisor and restarting files services"
docker exec "$container_name" sh -lc 'supervisorctl -c /etc/supervisor/conf.d/websoft9-platform.conf reread && supervisorctl -c /etc/supervisor/conf.d/websoft9-platform.conf update && supervisorctl -c /etc/supervisor/conf.d/websoft9-platform.conf restart files-agent apphub-api'

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