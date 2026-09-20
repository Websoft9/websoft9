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
  reason=${3:-}
  phase=${4:-}
  timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  temporary_file="${STATE_FILE}.tmp"
  if [ -n "$reason" ] && [ -n "$phase" ]; then
    printf '{"run_id":"%s","state":"%s","target_version":"%s","detail":"%s","reason":"%s","phase":"%s","updated_at":"%s"}\n' \
      "$RUN_ID" "$state" "${TARGET_VERSION:-}" "$detail" "$reason" "$phase" "$timestamp" > "$temporary_file"
  elif [ -n "$reason" ]; then
    printf '{"run_id":"%s","state":"%s","target_version":"%s","detail":"%s","reason":"%s","updated_at":"%s"}\n' \
      "$RUN_ID" "$state" "${TARGET_VERSION:-}" "$detail" "$reason" "$timestamp" > "$temporary_file"
  elif [ -n "$phase" ]; then
    printf '{"run_id":"%s","state":"%s","target_version":"%s","detail":"%s","phase":"%s","updated_at":"%s"}\n' \
      "$RUN_ID" "$state" "${TARGET_VERSION:-}" "$detail" "$phase" "$timestamp" > "$temporary_file"
  else
    printf '{"run_id":"%s","state":"%s","target_version":"%s","detail":"%s","updated_at":"%s"}\n' \
      "$RUN_ID" "$state" "${TARGET_VERSION:-}" "$detail" "$timestamp" > "$temporary_file"
  fi
  mv "$temporary_file" "$STATE_FILE"
}

# Log lines are read inside a console dialog, so they carry only a timestamp. Failures are spelled
# out in words instead of level tags, so the line reads like a sentence.
log_line() {
  prefix=$1
  shift
  timestamp=$(date +'%Y-%m-%d %H:%M:%S')
  printf '[%s] %s%s\n' "$timestamp" "$prefix" "$*" | tee -a "$LOG_FILE"
}

log_info()  { log_line '' "$*"; }
log_warn()  { log_line 'warning: ' "$*"; }
log_error() { log_line 'error: ' "$*"; }
log_step()  { log_line '' "$*"; }

# Backwards compatible shorthand used across the script.
log() { log_info "$*"; }

elapsed_seconds() {
  started=$1
  now=$(date +%s)
  echo $((now - started))
}

compose() {
  docker compose -p "$COMPOSE_PROJECT" \
    --env-file "$INSTALL_PATH/.env" \
    -f "$COMPOSE_FILE" "$@"
}

# Compose writes the only useful explanation of a failed recreate to its own output. It has to end
# up in the run log, otherwise the operator sees "the upgrade failed" with nothing to act on.
run_compose_logged() {
  compose_status=0
  compose_output=$(compose "$@" 2>&1) || compose_status=$?
  if [ -n "$compose_output" ]; then
    printf '%s\n' "$compose_output" | while IFS= read -r line; do log_info "[compose] $line"; done
  fi
  return "$compose_status"
}

backup_material() {
  BACKUP_DIR="$DATA_ROOT/upgrade/backups/$RUN_ID"
  mkdir -p "$BACKUP_DIR"
  cp -p "$INSTALL_PATH/.env" "$BACKUP_DIR/.env"
  # The backup keeps the conventional name; the restore step knows where it came from.
  cp -p "$COMPOSE_FILE" "$BACKUP_DIR/docker-compose.yml"
}

# Older runs kept a per-run image tag (rollback-<run_id>) in .env, which leaks a one-shot tag into
# the deployment and breaks once that tag is pruned. Only the newest rollback material is kept.
prune_old_backups() {
  keep=3
  index=0
  for directory in $(ls -1dt "$DATA_ROOT/upgrade/backups"/*/ 2>/dev/null); do
    index=$((index + 1))
    if [ "$index" -gt "$keep" ]; then
      rm -rf "$directory"
      log_info "removed stale backup: $directory"
    fi
  done
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

# The reason code is what the console turns into an explanation and a next step; the detail stays
# human readable for the operator who reads the raw state file or the log.
restore_and_restart() {
  trigger=$1
  log_step "rollback started ($trigger)"
  cp -p "$BACKUP_DIR/.env" "$INSTALL_PATH/.env"
  cp -p "$BACKUP_DIR/docker-compose.yml" "$COMPOSE_FILE"
  set_env_value IMAGE_REPO "$OLD_IMAGE_REPO"
  # Restore the deployment exactly as it was: the previous tag name goes back into .env, with the
  # rollback anchor retagged onto the previous image so the tag cannot point at the new release.
  set_env_value IMAGE_TAG "$OLD_IMAGE_TAG"
  if ! docker tag "$ROLLBACK_TAG_REF" "${OLD_IMAGE_REPO}:${OLD_IMAGE_TAG}" 2>/dev/null; then
    # The anchor is gone (pruned): keep the verified image id instead of a dangling tag.
    set_env_value IMAGE_TAG "$ROLLBACK_TAG"
    set_env_value IMAGE_REPO "$OLD_IMAGE_REPO"
    log_warn "previous image tag could not be restored; .env keeps the rollback tag $ROLLBACK_TAG"
  fi
  log_info "deployment restored: IMAGE_REPO=$OLD_IMAGE_REPO IMAGE_TAG=$OLD_IMAGE_TAG"
  if run_compose_logged up -d --force-recreate; then
    if wait_for_healthy_container; then
      write_state rolled_back "previous deployment restored after $trigger" "$trigger"
      log_step "rollback completed in $(elapsed_seconds "$RUN_STARTED_AT")s"
      exit 1
    fi
    log_error "rollback health check failed for $CONTAINER_NAME: $(container_health_summary)"
  fi
  write_state rollback_failed "failed to recreate the previous deployment after $trigger" "rollback_$trigger"
  fail "rollback failed"
}

container_health_summary() {
  docker inspect --format '{{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{end}}' "$CONTAINER_NAME" 2>/dev/null || echo unknown
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
    # Polling output is what makes a slow start diagnosable instead of a silent wait.
    log_info "waiting for $CONTAINER_NAME: status=$(container_health_summary) elapsed=${elapsed}s"
  done
  return 1
}

main() {
  read_task
  RUN_STARTED_AT=$(date +%s)
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
  # A retry runs under the same run id, so the log is appended to instead of replaced: the
  # evidence of the earlier attempt is what explains the fix that was supposed to help.
  if [ -s "$LOG_FILE" ]; then
    printf '===== attempt at %s =====\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG_FILE"
  fi
  write_state applying "preparing upgrade environment" "" prepare
  log_step "upgrade started $(date -u +%Y-%m-%dT%H:%M:%SZ): run_id=$RUN_ID target=$TARGET_VERSION image=${TARGET_IMAGE_REPO}:${TARGET_IMAGE_TAG}"
  log_info "install path: $INSTALL_PATH"
  log_info "compose project: $COMPOSE_PROJECT file: $COMPOSE_FILE"

  image_id=$(docker image inspect --format '{{.Id}}' "${TARGET_IMAGE_REPO}:${TARGET_IMAGE_TAG}" 2>/dev/null || true)
  [ -n "$image_id" ] || fail "target image is not available locally"
  docker image inspect --format '{{join .RepoDigests "\n"}}' "$image_id" | grep -Fq "@$TARGET_IMAGE_DIGEST" || fail "target image digest does not match task"
  log_info "target image verified: $image_id"

  old_image=$(docker inspect --format '{{.Image}}' "$CONTAINER_NAME")
  OLD_IMAGE_TAG=$(awk -F= '$1 == "IMAGE_TAG" { print substr($0, index($0, "=") + 1); exit }' "$INSTALL_PATH/.env")
  OLD_IMAGE_TAG=${OLD_IMAGE_TAG:-dev}
  OLD_IMAGE_REPO=$(awk -F= '$1 == "IMAGE_REPO" { print substr($0, index($0, "=") + 1); exit }' "$INSTALL_PATH/.env")
  OLD_IMAGE_REPO=${OLD_IMAGE_REPO:-websoft9dev/websoft9}
  # One fixed anchor instead of a per-run tag: it never accumulates and it is easy to prune.
  ROLLBACK_TAG="rollback"
  ROLLBACK_TAG_REF="${OLD_IMAGE_REPO}:${ROLLBACK_TAG}"
  docker tag "$old_image" "$ROLLBACK_TAG_REF"
  log_info "current deployment: ${OLD_IMAGE_REPO}:${OLD_IMAGE_TAG} ($old_image); rollback anchor $ROLLBACK_TAG_REF"

  log_step "backing up deployment material"
  backup_material
  log_info "backup directory: $BACKUP_DIR"

  log_step "staging the new release configuration"
  cp -p "$STAGING_DIR/docker-compose.yml" "${COMPOSE_FILE}.upgrade-${RUN_ID}.tmp"
  mv "${COMPOSE_FILE}.upgrade-${RUN_ID}.tmp" "$COMPOSE_FILE"
  set_env_value IMAGE_REPO "$TARGET_IMAGE_REPO"
  set_env_value IMAGE_TAG "$TARGET_IMAGE_TAG"
  ensure_env_default CONTAINER_NAME "$CONTAINER_NAME"
  log_info ".env updated: IMAGE_REPO=$TARGET_IMAGE_REPO IMAGE_TAG=$TARGET_IMAGE_TAG"

  write_state applying "recreating the platform container" "" replace
  log_step "recreating the platform container with $TARGET_VERSION"
  if ! run_compose_logged up -d --force-recreate; then
    restore_and_restart container_recreate_failed
  fi
  log_info "container recreated, waiting for a healthy state"
  if ! wait_for_healthy_container; then
    log_error "health check timed out: $(container_health_summary)"
    restore_and_restart health_check_timeout
  fi
  log_info "container is healthy after $(elapsed_seconds "$RUN_STARTED_AT")s"

  write_state applying "validating platform health" "" verify
  log_step "running the platform health check"
  strict_output=$(docker exec "$CONTAINER_NAME" /websoft9/script/platform-healthcheck.sh --strict 2>&1) || strict_status=$?
  strict_status=${strict_status:-0}
  log_info "health check output: $strict_output"
  case "$strict_output" in
    *"status=ready"*)
      write_state completed "upgraded to $TARGET_VERSION" "" verify
      log_step "upgrade completed in $(elapsed_seconds "$RUN_STARTED_AT")s"
      prune_old_backups
      ;;
    *"status=degraded"*)
      # The failing service names are the only actionable part of a degraded upgrade.
      degraded_services=$(printf '%s\n' "$strict_output" | sed -n 's/.*degraded_services=//p' | tr -cd 'A-Za-z0-9 _.-')
      write_state degraded "upgraded to $TARGET_VERSION with degraded services${degraded_services:+: $degraded_services}" health_check_degraded
      log_warn "upgrade completed with degraded services${degraded_services:+: $degraded_services}"
      prune_old_backups
      ;;
    *)
      log_error "strict health check failed, rolling back"
      restore_and_restart strict_health_check_failed
      ;;
  esac
}

main