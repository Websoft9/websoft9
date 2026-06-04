#!/usr/bin/env bash

set -euo pipefail

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') [platform-start-portainer] $*"
}

kill_stale_portainer_processes() {
  local found=0

  for cmdline_file in /proc/[0-9]*/cmdline; do
    [[ -r "$cmdline_file" ]] || continue

    local pid="${cmdline_file#/proc/}"
    pid="${pid%/cmdline}"

    local cmdline
    cmdline="$(tr '\0' ' ' < "$cmdline_file" 2>/dev/null || true)"
    [[ -n "$cmdline" ]] || continue

    if [[ "$cmdline" == /portainer* ]]; then
      found=1
      log "killing stale portainer pid=$pid cmd=$cmdline"
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done

  if [[ "$found" == "1" ]]; then
    sleep 1
  fi
}

main() {
  kill_stale_portainer_processes
  exec /usr/local/bin/init_portainer "$@"
}

main "$@"