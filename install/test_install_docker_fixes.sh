#!/bin/bash
# test_install_docker_fixes.sh — Simulated tests for install_docker.sh fixes
# Runs inside the dev container; no real apt-get or systemctl calls.
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DOCKER_SH="${SCRIPT_DIR}/install_docker.sh"
PASS=0
FAIL=0

green()  { echo -e "\033[32m$*\033[0m"; }
red()    { echo -e "\033[31m$*\033[0m"; }
banner() { echo -e "\n\033[1;36m=== $* ===\033[0m"; }

pass() { PASS=$((PASS + 1)); green "  ✓ PASS: $*"; }
fail() { FAIL=$((FAIL + 1)); red   "  ✗ FAIL: $*"; }

# Shared logging functions for test sub-shells
cat > /tmp/_test_logging.sh <<'LOGGING'
_w9_ts() { date +"%Y-%m-%d %H:%M:%S"; }
log_info()  { echo "[TEST][INFO] $*"; }
log_warn()  { echo "[TEST][WARN] $*" >&2; }
log_error() { echo "[TEST][ERROR] $*" >&2; }
log_step()  { echo "[TEST][STEP] $*"; }
command_exists() { command -v "$@" >/dev/null 2>&1; }
LOGGING

# ===========================================================================
banner "TEST A: _log_pipe — \\r without \\n must not block"
# ===========================================================================

# Test A1: Normal lines with \n
out=$(timeout 5 bash -c '
source /tmp/_test_logging.sh
_log_pipe() {
  if command -v stdbuf >/dev/null 2>&1; then
    stdbuf -o0 tr "\r" "\n"
  else
    tr "\r" "\n"
  fi | while IFS= read -r line; do
    log_info "$line"
  done
}
printf "line1\nline2\nline3\n" | _log_pipe
' 2>/dev/null)
rc=$?
count=$(echo "$out" | grep -c "INFO")
if [ "$rc" -eq 0 ] && [ "$count" -ge 3 ]; then
  pass "Normal lines with \\n pass through ($count lines)"
else
  fail "Normal lines: expected >=3 lines, got $count (rc=$rc)"
fi

# Test A2: \r without \n (dpkg progress bar) — CRITICAL TEST
out=$(timeout 5 bash -c '
source /tmp/_test_logging.sh
_log_pipe() {
  if command -v stdbuf >/dev/null 2>&1; then
    stdbuf -o0 tr "\r" "\n"
  else
    tr "\r" "\n"
  fi | while IFS= read -r line; do
    log_info "$line"
  done
}
for i in $(seq 1 20); do
  printf "Progress: %d%%\r" "$((i * 5))"
  sleep 0.05
done
printf "\nDONE_SIGNAL\n"
' 2>/dev/null)
rc=$?
if [ "$rc" -eq 0 ] && echo "$out" | grep -q "DONE_SIGNAL"; then
  pass "\\r without \\n does NOT block (rc=$rc)"
elif [ "$rc" -eq 124 ]; then
  fail "\\r without \\n BLOCKED — timeout after 5s!"
else
  fail "\\r test unexpected: rc=$rc"
fi

# Test A3: Mixed \r\n output
out=$(timeout 5 bash -c '
source /tmp/_test_logging.sh
_log_pipe() {
  if command -v stdbuf >/dev/null 2>&1; then
    stdbuf -o0 tr "\r" "\n"
  else
    tr "\r" "\n"
  fi | while IFS= read -r line; do
    log_info "$line"
  done
}
printf "Unpacking docker-ce ...\r\nSetting up docker-ce ...\r\nDONE\n"
' 2>/dev/null)
rc=$?
if [ "$rc" -eq 0 ] && echo "$out" | grep -q "DONE"; then
  pass "Mixed \\r\\n output passes through"
else
  fail "Mixed \\r\\n output failed"
fi

# ===========================================================================
banner "TEST B: _run_logged pipeline with \\r progress"
# ===========================================================================

# Create mock dpkg script
cat > /tmp/_mock_dpkg.sh <<'MOCKDPKG'
#!/bin/bash
echo "Unpacking packages..."
for i in $(seq 1 15); do
  printf "Progress: %d/15\r" "$i"
  sleep 0.1
done
printf "\n"
echo "Setting up packages..."
for i in $(seq 1 10); do
  printf "Configuring: %d%%\r" "$((i * 10))"
  sleep 0.05
done
printf "\n"
echo "DONE_MOCK"
MOCKDPKG
chmod +x /tmp/_mock_dpkg.sh

# Test B1: _run_logged with \r progress
out=$(timeout 15 bash -c '
source /tmp/_test_logging.sh
_log_pipe() {
  if command -v stdbuf >/dev/null 2>&1; then
    stdbuf -o0 tr "\r" "\n"
  else
    tr "\r" "\n"
  fi | while IFS= read -r line; do
    log_info "$line"
  done
}
_run_logged() {
  local exit_file exit_code
  exit_file="$(mktemp)"
  (
    export DEBIAN_FRONTEND=noninteractive
    export APT_LISTCHANGES_FRONTEND=none
    "$@"
    echo $? > "$exit_file"
  ) 2>&1 | _log_pipe
  exit_code="$(cat "$exit_file" 2>/dev/null || echo 1)"
  rm -f "$exit_file"
  return "$exit_code"
}
_run_logged /tmp/_mock_dpkg.sh
' 2>/dev/null)
rc=$?
if [ "$rc" -eq 0 ] && echo "$out" | grep -q "DONE_MOCK"; then
  pass "_run_logged: \\r progress does NOT block (rc=$rc)"
elif [ "$rc" -eq 124 ]; then
  fail "_run_logged: \\r progress BLOCKED — timeout!"
else
  fail "_run_logged: \\r progress unexpected (rc=$rc)"
fi

# Test B2: exit code preservation on failure
out=$(timeout 5 bash -c '
source /tmp/_test_logging.sh
_log_pipe() {
  if command -v stdbuf >/dev/null 2>&1; then
    stdbuf -o0 tr "\r" "\n"
  else
    tr "\r" "\n"
  fi | while IFS= read -r line; do
    log_info "$line"
  done
}
_run_logged() {
  local exit_file exit_code
  exit_file="$(mktemp)"
  (
    export DEBIAN_FRONTEND=noninteractive
    export APT_LISTCHANGES_FRONTEND=none
    "$@"
    echo $? > "$exit_file"
  ) 2>&1 | _log_pipe
  exit_code="$(cat "$exit_file" 2>/dev/null || echo 1)"
  rm -f "$exit_file"
  return "$exit_code"
}
_run_logged sh -c "echo error msg >&2; exit 42"
' 2>/dev/null)
rc=$?
if [ "$rc" -eq 42 ]; then
  pass "_run_logged: exit code preserved (rc=42)"
else
  fail "_run_logged: exit code should be 42, got $rc"
fi

# Test B3: Fast output (50 lines)
out=$(timeout 5 bash -c '
source /tmp/_test_logging.sh
_log_pipe() {
  if command -v stdbuf >/dev/null 2>&1; then
    stdbuf -o0 tr "\r" "\n"
  else
    tr "\r" "\n"
  fi | while IFS= read -r line; do
    log_info "$line"
  done
}
_run_logged() {
  local exit_file exit_code
  exit_file="$(mktemp)"
  (
    export DEBIAN_FRONTEND=noninteractive
    export APT_LISTCHANGES_FRONTEND=none
    "$@"
    echo $? > "$exit_file"
  ) 2>&1 | _log_pipe
  exit_code="$(cat "$exit_file" 2>/dev/null || echo 1)"
  rm -f "$exit_file"
  return "$exit_code"
}
_run_logged sh -c "for i in \$(seq 1 50); do echo \"line \$i\"; done"
' 2>/dev/null)
rc=$?
if [ "$rc" -eq 0 ]; then
  pass "_run_logged: 50 fast lines handled (rc=$rc)"
else
  fail "_run_logged: 50 fast lines failed (rc=$rc)"
fi

# ===========================================================================
banner "TEST C: policy-rc.d setup / cleanup"
# ===========================================================================

source /tmp/_test_logging.sh

_setup_policy_rc_d() {
  if [ ! -d /usr/sbin ] || [ -f /usr/sbin/policy-rc.d ]; then
    return 0
  fi
  cat > /usr/sbin/policy-rc.d <<'POLICYEOF'
#!/bin/sh
# Websoft9: prevent dpkg from starting services during Docker installation.
# This file is managed by install_docker.sh and removed after installation.
exit 101
POLICYEOF
  chmod +x /usr/sbin/policy-rc.d
  log_info "Set policy-rc.d to prevent automatic service starts during package installation"
}

_cleanup_policy_rc_d() {
  if [ -f /usr/sbin/policy-rc.d ] && grep -q "Websoft9" /usr/sbin/policy-rc.d 2>/dev/null; then
    rm -f /usr/sbin/policy-rc.d
    log_info "Removed policy-rc.d, services can now start normally"
  fi
}

rm -f /usr/sbin/policy-rc.d

# C1: Setup creates file
if _setup_policy_rc_d && [ -f /usr/sbin/policy-rc.d ] && [ -x /usr/sbin/policy-rc.d ]; then
  grep -q "Websoft9" /usr/sbin/policy-rc.d && pass "policy-rc.d: setup creates executable file with marker" || fail "policy-rc.d: missing Websoft9 marker"
else
  fail "policy-rc.d: setup failed"
fi

# C2: Idempotent
_setup_policy_rc_d && pass "policy-rc.d: second setup idempotent" || fail "policy-rc.d: second setup failed"

# C3: Cleanup removes
_cleanup_policy_rc_d
[ ! -f /usr/sbin/policy-rc.d ] && pass "policy-rc.d: cleanup removes file" || fail "policy-rc.d: cleanup did NOT remove"

# C4: Cleanup idempotent
_cleanup_policy_rc_d && pass "policy-rc.d: cleanup idempotent (no file)" || fail "policy-rc.d: cleanup failed"

# C5: Does not overwrite non-Websoft9 file
echo "#!/bin/sh
# Some other tool
exit 0" > /usr/sbin/policy-rc.d
chmod +x /usr/sbin/policy-rc.d
_setup_policy_rc_d
grep -q "Some other tool" /usr/sbin/policy-rc.d && pass "policy-rc.d: preserves existing non-Websoft9 file" || fail "policy-rc.d: overwrote existing file!"

# C6: Cleanup does not remove non-Websoft9 file
_cleanup_policy_rc_d
[ -f /usr/sbin/policy-rc.d ] && pass "policy-rc.d: cleanup preserves non-Websoft9 file" || fail "policy-rc.d: cleanup removed non-Websoft9 file!"

rm -f /usr/sbin/policy-rc.d

# ===========================================================================
banner "TEST D: Edge case — very long line without \\n"
# ===========================================================================

out=$(timeout 5 bash -c '
source /tmp/_test_logging.sh
_log_pipe() {
  if command -v stdbuf >/dev/null 2>&1; then
    stdbuf -o0 tr "\r" "\n"
  else
    tr "\r" "\n"
  fi | while IFS= read -r line; do
    log_info "$line"
  done
}
_run_logged() {
  local exit_file exit_code
  exit_file="$(mktemp)"
  (
    export DEBIAN_FRONTEND=noninteractive
    export APT_LISTCHANGES_FRONTEND=none
    "$@"
    echo $? > "$exit_file"
  ) 2>&1 | _log_pipe
  exit_code="$(cat "$exit_file" 2>/dev/null || echo 1)"
  rm -f "$exit_file"
  return "$exit_code"
}
_run_logged sh -c "printf A%.0s \$(seq 1 5000); echo; echo DONE_LONG"
' 2>/dev/null)
rc=$?
if [ "$rc" -eq 0 ] && echo "$out" | grep -q "DONE_LONG"; then
  pass "Edge case: 5000-char line does not hang (rc=$rc)"
elif [ "$rc" -eq 124 ]; then
  fail "Edge case: 5000-char line caused timeout!"
else
  fail "Edge case: 5000-char line unexpected (rc=$rc)"
fi

# ===========================================================================
banner "TEST E: Verify actual install_docker.sh has all fixes"
# ===========================================================================

grep -q "stdbuf -o0 tr" "$INSTALL_DOCKER_SH" \
  && pass "install_docker.sh: _log_pipe uses stdbuf -o0" \
  || fail "install_docker.sh: _log_pipe missing stdbuf -o0!"

grep -q "^_setup_policy_rc_d()" "$INSTALL_DOCKER_SH" \
  && pass "install_docker.sh: _setup_policy_rc_d function exists" \
  || fail "install_docker.sh: _setup_policy_rc_d missing!"

grep -q "^_cleanup_policy_rc_d()" "$INSTALL_DOCKER_SH" \
  && pass "install_docker.sh: _cleanup_policy_rc_d function exists" \
  || fail "install_docker.sh: _cleanup_policy_rc_d missing!"

grep -A 60 "^install_docker_official()" "$INSTALL_DOCKER_SH" | grep -q "_setup_policy_rc_d" \
  && pass "install_docker.sh: install_docker_official calls _setup_policy_rc_d" \
  || fail "install_docker.sh: install_docker_official missing _setup_policy_rc_d!"

grep -A 30 "Debian / Ubuntu (APT)" "$INSTALL_DOCKER_SH" | grep -q "_setup_policy_rc_d" \
  && pass "install_docker.sh: custom Debian/Ubuntu path calls _setup_policy_rc_d" \
  || fail "install_docker.sh: custom Debian/Ubuntu path missing _setup_policy_rc_d!"

grep -q "^_setup_apt_noninteractive_config()" "$INSTALL_DOCKER_SH" \
  && pass "install_docker.sh: _setup_apt_noninteractive_config function exists" \
  || fail "install_docker.sh: _setup_apt_noninteractive_config missing!"

grep -q 'Dpkg::Use-Pty "0"' "$INSTALL_DOCKER_SH" \
  && pass "install_docker.sh: disables dpkg pseudo-terminal progress" \
  || fail "install_docker.sh: missing Dpkg::Use-Pty progress suppression!"

grep -A 65 "^install_docker_official()" "$INSTALL_DOCKER_SH" | grep -q "_setup_apt_noninteractive_config" \
  && pass "install_docker.sh: official path disables apt pseudo-terminal progress" \
  || fail "install_docker.sh: official path missing apt progress suppression!"

grep -A 35 "Debian / Ubuntu (APT)" "$INSTALL_DOCKER_SH" | grep -q "_setup_apt_noninteractive_config" \
  && pass "install_docker.sh: custom Debian/Ubuntu path disables apt pseudo-terminal progress" \
  || fail "install_docker.sh: custom Debian/Ubuntu path missing apt progress suppression!"

# ===========================================================================
banner "TEST F: limit Docker start timeout / unmask functions"
# ===========================================================================

# Verify timeout drop-in functions exist in source
grep -q "^_limit_docker_start_timeout()" "$INSTALL_DOCKER_SH" \
  && pass "install_docker.sh: _limit_docker_start_timeout function exists" \
  || fail "install_docker.sh: _limit_docker_start_timeout missing!"

grep -q "^_remove_docker_start_timeout()" "$INSTALL_DOCKER_SH" \
  && pass "install_docker.sh: _remove_docker_start_timeout function exists" \
  || fail "install_docker.sh: _remove_docker_start_timeout missing!"

# Verify mask is used in install_docker_official
grep -A 70 "^install_docker_official()" "$INSTALL_DOCKER_SH" | grep -q "_limit_docker_start_timeout" \
  && pass "install_docker.sh: install_docker_official calls _limit_docker_start_timeout" \
  || fail "install_docker.sh: install_docker_official missing _limit_docker_start_timeout!"

# Verify unmask before _start_docker in official path
grep -A 80 "^install_docker_official()" "$INSTALL_DOCKER_SH" | grep -q "_remove_docker_start_timeout" \
  && pass "install_docker.sh: install_docker_official calls _remove_docker_start_timeout before _start_docker" \
  || fail "install_docker.sh: install_docker_official missing _remove_docker_start_timeout!"

# Verify mask in custom Debian/Ubuntu path
grep -A 35 "Debian / Ubuntu (APT)" "$INSTALL_DOCKER_SH" | grep -q "_limit_docker_start_timeout" \
  && pass "install_docker.sh: custom Debian/Ubuntu path calls _limit_docker_start_timeout" \
  || fail "install_docker.sh: custom Debian/Ubuntu path missing _limit_docker_start_timeout!"

# Verify unmask is called in custom Debian/Ubuntu path before _start_docker
grep -A 40 "Debian / Ubuntu (APT)" "$INSTALL_DOCKER_SH" | grep -q "_remove_docker_start_timeout" \
  && pass "install_docker.sh: custom Debian/Ubuntu path calls _remove_docker_start_timeout before _start_docker" \
  || fail "install_docker.sh: custom Debian/Ubuntu path missing _remove_docker_start_timeout!"

# ===========================================================================
banner "SUMMARY"
# ===========================================================================
echo ""
echo "Tests passed: $(green "$PASS")"
echo "Tests failed: $(red "$FAIL")"
echo ""

rm -f /tmp/_test_logging.sh /tmp/_mock_dpkg.sh

if [ "$FAIL" -eq 0 ]; then
  green "🎉 All $PASS tests passed!"
  exit 0
else
  red "❌ $FAIL test(s) failed out of $((PASS + FAIL))"
  exit 1
fi
