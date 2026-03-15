#!/usr/bin/env bash
# test_status_api.sh — End-to-end validation of enriched /status endpoint
set -euo pipefail

BASE="${1:-http://augs-rpi-5.local:8080}"

fail() { echo "FAIL: $1"; exit 1; }
pass() { echo "PASS: $1"; }

check_json() {
  # $1 = label, $2 = jq filter, $3 = expected value, $4 = json
  actual=$(echo "$4" | jq -r "$2")
  [ "$actual" = "$3" ] && pass "$1" || fail "$1 — expected '$3', got '$actual'"
}

echo "=== Step 1: Idle status ==="
R=$(curl -sf "$BASE/status")
check_json "mode is idle" '.mode' 'idle' "$R"
check_json "navigation idle" '.navigation.status' 'idle' "$R"
check_json "pose available" '.pose.available' 'true' "$R"
echo "$R" | jq -e '.nav2_lifecycle' > /dev/null 2>&1 && fail "nav2_lifecycle should be absent in idle" || pass "no nav2_lifecycle in idle"

echo ""
echo "=== Step 2: Start localization ==="
curl -sf -X POST "$BASE/localization/start" -H 'Content-Type: application/json' -d '{"name":"my_map_name"}' | jq .
sleep 3
R=$(curl -sf "$BASE/status")
check_json "mode is localizing" '.mode' 'localizing' "$R"
check_json "localization running" '.processes.localization.running' 'true' "$R"

echo ""
echo "=== Step 3: Start autonomy ==="
curl -sf -X POST "$BASE/autonomy/start" | jq .
sleep 5
R=$(curl -sf "$BASE/status")
check_json "mode is autonomous" '.mode' 'autonomous' "$R"
check_json "nav2 running" '.processes.nav2.running' 'true' "$R"
echo "Nav2 lifecycle:" && echo "$R" | jq '.nav2_lifecycle'

echo ""
echo "=== Step 4: Wait for Nav2 active (up to 30s) ==="
for i in $(seq 1 6); do
  R=$(curl -sf "$BASE/status")
  bt_state=$(echo "$R" | jq -r '.nav2_lifecycle.bt_navigator')
  [ "$bt_state" = "active" ] && break
  echo "  bt_navigator=$bt_state, waiting 5s..."
  sleep 5
done
check_json "bt_navigator active" '.nav2_lifecycle.bt_navigator' 'active' "$R"

echo ""
echo "=== Step 5: Send goto goal ==="
curl -sf -X POST "$BASE/navigation/goto" -H 'Content-Type: application/json' \
  -d '{"x":0,"y":0.01,"yaw":0}' | jq .
sleep 2
R=$(curl -sf "$BASE/status")
check_json "navigation executing" '.navigation.goal_active' 'true' "$R"
echo "Pose:" && echo "$R" | jq '.pose'

echo ""
echo "=== Step 6: Verify /navigation/status ==="
R=$(curl -sf "$BASE/navigation/status")
check_json "nav status endpoint works" '.goal_active' 'true' "$R"

echo ""
echo "=== Step 7: E-stop ==="
curl -sf -X POST "$BASE/estop" | jq .
sleep 2
R=$(curl -sf "$BASE/status")
check_json "mode is idle" '.mode' 'idle' "$R"
check_json "navigation idle" '.navigation.status' 'idle' "$R"
echo "$R" | jq -e '.nav2_lifecycle' > /dev/null 2>&1 && fail "nav2_lifecycle should be absent after estop" || pass "no nav2_lifecycle after estop"

echo ""
echo "=== All tests passed ==="
