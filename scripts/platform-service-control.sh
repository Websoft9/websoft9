#!/usr/bin/env bash

set -euo pipefail

supervisor_config="${WEBSOFT9_SUPERVISOR_CONFIG:-/etc/supervisor/conf.d/websoft9-platform.conf}"

usage() {
  echo "usage: $0 <start|stop|restart|status> <all|apphub-api|apphub-media|files-agent|gitea|portainer|nginx-proxy-manager>" >&2
}

npm_start() {
  s6-rc -u change backend nginx
}

npm_stop() {
  s6-rc -d change nginx backend || true
}

npm_status() {
  if curl --silent --show-error --max-time 2 --output /dev/null http://127.0.0.1:81/; then
    echo "nginx-proxy-manager RUNNING"
  else
    echo "nginx-proxy-manager STOPPED"
    return 1
  fi
}

supervisor_action() {
  local action="$1"
  local service="$2"

  supervisorctl -c "$supervisor_config" "$action" "$service"
}

action="${1:-}"
service="${2:-}"

if [[ -z "$action" || -z "$service" ]]; then
  usage
  exit 1
fi

case "$service" in
  all)
    case "$action" in
      start)
        npm_start
        supervisorctl -c "$supervisor_config" start all
        ;;
      stop)
        supervisorctl -c "$supervisor_config" stop all || true
        npm_stop
        ;;
      restart)
        supervisorctl -c "$supervisor_config" restart all
        npm_stop
        npm_start
        ;;
      status)
        /websoft9/script/platform-healthcheck.sh --readiness
        supervisorctl -c "$supervisor_config" status
        npm_status || true
        ;;
      *)
        usage
        exit 1
        ;;
    esac
    ;;
  nginx-proxy-manager)
    case "$action" in
      start)
        npm_start
        ;;
      stop)
        npm_stop
        ;;
      restart)
        npm_stop
        npm_start
        ;;
      status)
        npm_status
        ;;
      *)
        usage
        exit 1
        ;;
    esac
    ;;
  apphub-api|apphub-media|files-agent|gitea|portainer)
    supervisor_action "$action" "$service"
    ;;
  *)
    usage
    exit 1
    ;;
esac