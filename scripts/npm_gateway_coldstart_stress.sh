#!/usr/bin/env bash

set -euo pipefail

container_name="${1:-websoft9-dev}"
rounds="${2:-10}"
settle_seconds="${3:-1}"
report_file="${4:-/tmp/websoft9_npm_coldstart_report.txt}"
health_wait_attempts="${WEBSOFT9_STRESS_HEALTH_WAIT_ATTEMPTS:-30}"

if ! [[ "$rounds" =~ ^[0-9]+$ ]] || [[ "$rounds" -le 0 ]]; then
  echo "rounds must be a positive integer" >&2
  exit 1
fi

if ! [[ "$settle_seconds" =~ ^[0-9]+$ ]] || [[ "$settle_seconds" -lt 0 ]]; then
  echo "settle_seconds must be a non-negative integer" >&2
  exit 1
fi

api_url="http://127.0.0.1:9000/api/integrations/npm/session"
health_url="http://127.0.0.1:9000/api/healthz"
start_ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

curl_common=(--noproxy '*' --silent --show-error --connect-timeout 2 --max-time 4)

declare -a duration_ms_list=()
success_count=0
failure_count=0

: > "$report_file"
echo "websoft9 npm gateway coldstart stress report" >> "$report_file"
echo "start_time_utc=$start_ts" >> "$report_file"
echo "container=$container_name rounds=$rounds settle_seconds=$settle_seconds" >> "$report_file"
echo "health_wait_attempts=$health_wait_attempts" >> "$report_file"
echo "" >> "$report_file"

echo "Running $rounds rounds against $container_name"

for ((i=1; i<=rounds; i++)); do
  echo "[$i/$rounds] restarting npm-backend + npm-nginx"
  docker exec "$container_name" supervisorctl -c /etc/supervisor/conf.d/websoft9-platform.conf restart npm-backend npm-nginx >/tmp/w9_supervisor_restart.log 2>&1

  if [[ "$settle_seconds" -gt 0 ]]; then
    sleep "$settle_seconds"
  fi

  health_ready="false"
  health_recovery_ms=0
  health_start_ms="$(date +%s%3N)"
  for ((attempt=1; attempt<=health_wait_attempts; attempt++)); do
    health_code="$(curl "${curl_common[@]}" -o /dev/null -w '%{http_code}' "$health_url" || true)"
    if [[ "$health_code" == "200" ]]; then
      health_ready="true"
      health_end_ms="$(date +%s%3N)"
      health_recovery_ms=$((health_end_ms - health_start_ms))
      break
    fi
    sleep 1
  done

  response_file="/tmp/w9_npm_stress_resp_${i}.json"
  timing_file="/tmp/w9_npm_stress_timing_${i}.txt"
  : > "$response_file"
  : > "$timing_file"

  if [[ "$health_ready" == "true" ]]; then
    curl "${curl_common[@]}" -X POST "$api_url" -H 'Content-Type: application/json' -o "$response_file" -w '%{http_code} %{time_total}\n' > "$timing_file" || true
  else
    printf '000 0\n' > "$timing_file"
    printf '{"status":"error","details":"gateway health check did not recover in time"}' > "$response_file"
  fi

  status_code="$(awk '{print $1}' "$timing_file" | tr -d '\r' || true)"
  time_total="$(awk '{print $2}' "$timing_file" | tr -d '\r' || true)"

  if [[ -z "$status_code" ]]; then
    status_code="000"
  fi

  duration_ms="$(awk -v t="${time_total:-0}" 'BEGIN{printf "%d", t*1000}')"
  if [[ -z "$duration_ms" ]]; then
    duration_ms=0
  fi

  if [[ "$status_code" == "200" ]]; then
    result="PASS"
    success_count=$((success_count + 1))
  else
    result="FAIL"
    failure_count=$((failure_count + 1))
  fi

  duration_ms_list+=("$duration_ms")
  payload_preview="$(tr -d '\n' < "$response_file" | cut -c1-200)"

  printf 'round=%02d result=%s health_ready=%s health_recovery_ms=%s status=%s duration_ms=%s payload=%s\n' "$i" "$result" "$health_ready" "$health_recovery_ms" "$status_code" "$duration_ms" "$payload_preview" | tee -a "$report_file"
done

sorted_durations="$(printf '%s\n' "${duration_ms_list[@]}" | sort -n)"
mean_ms="$(printf '%s\n' "${duration_ms_list[@]}" | awk '{sum+=$1} END{if (NR>0) printf "%.2f", sum/NR; else print "0"}')"
min_ms="$(printf '%s\n' "$sorted_durations" | head -n 1)"
max_ms="$(printf '%s\n' "$sorted_durations" | tail -n 1)"

p95_index=$(( (rounds * 95 + 99) / 100 ))
p95_ms="$(printf '%s\n' "$sorted_durations" | sed -n "${p95_index}p")"

success_rate="$(awk -v s="$success_count" -v r="$rounds" 'BEGIN{printf "%.2f", (r>0 ? s*100/r : 0)}')"
end_ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

echo "" >> "$report_file"
echo "summary:" >> "$report_file"
echo "end_time_utc=$end_ts" >> "$report_file"
echo "success_count=$success_count failure_count=$failure_count success_rate_percent=$success_rate" >> "$report_file"
echo "latency_ms min=$min_ms mean=$mean_ms p95=$p95_ms max=$max_ms" >> "$report_file"

echo ""
echo "Completed. Summary:"
cat "$report_file" | tail -n 5

echo "Report saved to $report_file"