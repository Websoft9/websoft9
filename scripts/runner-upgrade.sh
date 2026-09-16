#!/bin/sh

set -eu

TASK_FILE=${1:?usage: runner-upgrade.sh /absolute/path/to/task.env}
TASK_DIR=$(dirname "$TASK_FILE")

RUN_ID=
DATA_ROOT=
STAGING_DIR=
INSTALL_PATH=
COMPOSE_FILE=
COMPOSE_PROJECT=
TARGET_IMAGE_REPO=
TARGET_IMAGE_TAG=
TARGET_IMAGE_DIGEST=
TARGET_VERSION=
CONTAINER_NAME=

fail() {
  printf '%s\n' "upgrade runner: $*" >&2
  exit 1
}

require_absolute_directory() {
  case "$1" in
    /*) [ -d "$1" ] || fail "missing directory: $1" ;;
    *) fail "path must be absolute: $1" ;;
  esac
}

require_absolute_file() {
  case "$1" in
    /*) [ -f "$1" ] || fail "missing file: $1" ;;
    *) fail "path must be absolute: $1" ;;
  esac
}

read_task() {
  seen_keys=' '
  [ -f "$TASK_FILE" ] || fail "task file does not exist"
  while IFS= read -r line || [ -n "$line" ]; do
    [ -n "$line" ] || continue
    case "$line" in
      \#*) continue ;;
      *=*) key=${line%%=*}; value=${line#*=} ;;
      *) fail "invalid task entry" ;;
    esac
    case "$key" in
      RUN_ID|DATA_ROOT|STAGING_DIR|INSTALL_PATH|COMPOSE_FILE|COMPOSE_PROJECT|TARGET_IMAGE_REPO|TARGET_IMAGE_TAG|TARGET_IMAGE_DIGEST|TARGET_VERSION|CONTAINER_NAME)
        case "$seen_keys" in *" $key "*) fail "duplicate task key: $key" ;; esac
        case "$value" in *"'"*|*'"'*|*'`'*|*'$'*|*'\'*|*' '*|*'!'*|*';'*|*'&'*|*'|'*|*'<'*|*'>'*) fail "unsafe task value: $key" ;; esac
        seen_keys="${seen_keys}${key} "
        case "$key" in
          RUN_ID) RUN_ID=$value ;;
          DATA_ROOT) DATA_ROOT=$value ;;
          STAGING_DIR) STAGING_DIR=$value ;;
          INSTALL_PATH) INSTALL_PATH=$value ;;
          COMPOSE_FILE) COMPOSE_FILE=$value ;;
          COMPOSE_PROJECT) COMPOSE_PROJECT=$value ;;
          TARGET_IMAGE_REPO) TARGET_IMAGE_REPO=$value ;;
          TARGET_IMAGE_TAG) TARGET_IMAGE_TAG=$value ;;
          TARGET_IMAGE_DIGEST) TARGET_IMAGE_DIGEST=$value ;;
          TARGET_VERSION) TARGET_VERSION=$value ;;
          CONTAINER_NAME) CONTAINER_NAME=$value ;;
        esac
        ;;
      *) fail "unknown task key: $key" ;;
    esac
  done < "$TASK_FILE"

  [ -n "$RUN_ID" ] || fail "missing task key: RUN_ID"
  [ -n "$DATA_ROOT" ] || fail "missing task key: DATA_ROOT"
  [ -n "$STAGING_DIR" ] || fail "missing task key: STAGING_DIR"
  [ -n "$INSTALL_PATH" ] || fail "missing task key: INSTALL_PATH"
  [ -n "$COMPOSE_PROJECT" ] || fail "missing task key: COMPOSE_PROJECT"
  [ -n "$TARGET_IMAGE_REPO" ] || fail "missing task key: TARGET_IMAGE_REPO"
  [ -n "$TARGET_IMAGE_TAG" ] || fail "missing task key: TARGET_IMAGE_TAG"
  [ -n "$TARGET_IMAGE_DIGEST" ] || fail "missing task key: TARGET_IMAGE_DIGEST"
  [ -n "$TARGET_VERSION" ] || fail "missing task key: TARGET_VERSION"
  [ -n "$CONTAINER_NAME" ] || fail "missing task key: CONTAINER_NAME"
}

STATE_FILE=
LOG_FILE=

write_state() {
  state=$1
  detail=$2
  timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  temporary_file="${STATE_FILE}.tmp"
  printf '{"run_id":"%s","state":"%s","target_version":"%s","detail":"%s","updated_at":"%s"}\n' \
    "$RUN_ID" "$state" "${TARGET_VERSION:-}" "$detail" "$timestamp" > "$temporary_file"
  mv "$temporary_file" "$STATE_FILE"
}

log() {
  timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  printf '%s %s\n' "$timestamp" "$*" | tee -a "$LOG_FILE"
}

compose() {
  docker compose -p "$COMPOSE_PROJECT" \
    --env-file "$INSTALL_PATH/.env" \
    -f "$COMPOSE_FILE" "$@"
}

backup_material() {
  BACKUP_DIR="$DATA_ROOT/upgrade/backups/$RUN_ID"
  mkdir -p "$BACKUP_DIR"
  cp -p "$INSTALL_PATH/.env" "$BACKUP_DIR/.env"
  # The backup keeps the conventional name; the restore step knows where it came from.
  cp -p "$COMPOSE_FILE" "$BACKUP_DIR/docker-compose.yml"
}

set_env_value() {
  key=$1
  value=$2
  input="$INSTALL_PATH/.env"
  temporary_file="${input}.upgrade-${RUN_ID}.tmp"
  awk -v key="$key" -v value="$value" '
    BEGIN { found = 0 }
    $0 ~ "^" key "=" { print key "=" value; found = 1; next }
    { print }
    END { if (!found) print key "=" value }
  ' "$input" > "$temporary_file"
  mv "$temporary_file" "$input"
}

ensure_env_default() {
  key=$1
  value=$2
  grep -q "^${key}=" "$INSTALL_PATH/.env" || set_env_value "$key" "$value"
}

restore_and_restart() {
  log "rollback started"
  cp -p "$BACKUP_DIR/.env" "$INSTALL_PATH/.env"
  cp -p "$BACKUP_DIR/docker-compose.yml" "$COMPOSE_FILE"
  set_env_value IMAGE_REPO "$OLD_IMAGE_REPO"
  set_env_value IMAGE_TAG "$ROLLBACK_TAG"
  if compose up -d --force-recreate; then
    if wait_for_healthy_container; then
      write_state rolled_back "previous deployment material restored"
      log "rollback completed"
      exit 1
    fi
  fi
  write_state rollback_failed "failed to recreate the previous deployment"
  fail "rollback failed"
}

wait_for_healthy_container() {
  elapsed=0
  while [ "$elapsed" -lt 300 ]; do
    running=$(docker inspect --format '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)
    health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$CONTAINER_NAME" 2>/dev/null || true)
    if [ "$running" = true ] && [ "$health" = healthy ]; then
      return 0
    fi
    sleep 5
    elapsed=$((elapsed + 5))
  done
  return 1
}

main() {
  read_task
  require_absolute_directory "$DATA_ROOT"
  require_absolute_directory "$STAGING_DIR"
  require_absolute_directory "$INSTALL_PATH"
  [ "$STAGING_DIR" = "$TASK_DIR" ] || fail "task must be in its staging directory"
  [ -f "$STAGING_DIR/docker-compose.yml" ] || fail "staged compose file is missing"
  [ -f "$INSTALL_PATH/.env" ] || fail "deployment .env is missing"
  # Older tasks predate COMPOSE_FILE; the conventional name stays the fallback for them.
  COMPOSE_FILE=${COMPOSE_FILE:-$INSTALL_PATH/docker-compose.yml}
  require_absolute_file "$COMPOSE_FILE"
  [ "$(dirname "$COMPOSE_FILE")" = "$INSTALL_PATH" ] || fail "the compose file must live in the install path"

  STATE_FILE="$DATA_ROOT/upgrade/state.json"
  LOG_FILE="$DATA_ROOT/upgrade/logs/${RUN_ID}.log"
  mkdir -p "$(dirname "$STATE_FILE")" "$(dirname "$LOG_FILE")"
  : > "$LOG_FILE"
  write_state applying "runner started"

  image_id=$(docker image inspect --format '{{.Id}}' "${TARGET_IMAGE_REPO}:${TARGET_IMAGE_TAG}" 2>/dev/null || true)
  [ -n "$image_id" ] || fail "target image is not available locally"
  docker image inspect --format '{{join .RepoDigests "\n"}}' "$image_id" | grep -Fq "@$TARGET_IMAGE_DIGEST" || fail "target image digest does not match task"

  old_image=$(docker inspect --format '{{.Image}}' "$CONTAINER_NAME")
  OLD_IMAGE_REPO=$(awk -F= '$1 == "IMAGE_REPO" { print substr($0, index($0, "=") + 1); exit }' "$INSTALL_PATH/.env")
  OLD_IMAGE_REPO=${OLD_IMAGE_REPO:-websoft9dev/websoft9}
  ROLLBACK_TAG="rollback-$RUN_ID"
  docker tag "$old_image" "${OLD_IMAGE_REPO}:${ROLLBACK_TAG}"
  backup_material

  cp -p "$STAGING_DIR/docker-compose.yml" "${COMPOSE_FILE}.upgrade-${RUN_ID}.tmp"
  mv "${COMPOSE_FILE}.upgrade-${RUN_ID}.tmp" "$COMPOSE_FILE"
  set_env_value IMAGE_REPO "$TARGET_IMAGE_REPO"
  set_env_value IMAGE_TAG "$TARGET_IMAGE_TAG"
  ensure_env_default CONTAINER_NAME "$CONTAINER_NAME"

  if ! compose up -d --force-recreate; then
    restore_and_restart
  fi
  if ! wait_for_healthy_container; then
    restore_and_restart
  fi

  strict_output=$(docker exec "$CONTAINER_NAME" /websoft9/script/platform-healthcheck.sh --strict 2>&1) || strict_status=$?
  strict_status=${strict_status:-0}
  case "$strict_output" in
    *"status=ready"*)
      write_state completed "upgraded to $TARGET_VERSION"
      log "upgrade completed"
      ;;
    *"status=degraded"*)
      write_state degraded "upgraded to $TARGET_VERSION with degraded services"
      log "upgrade completed with degraded services"
      ;;
    *)
      log "strict health check failed: $strict_output"
      restore_and_restart
      ;;
  esac
}

main