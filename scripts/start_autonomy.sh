#!/bin/bash
# Start the full autonomy stack: localization → initial pose → Nav2
# Usage: ./scripts/start_autonomy.sh [map_name]

BASE_URL="http://augs-rpi-5.local:8080"
MAP_NAME="${1:-bigger_map}"

set -e

echo "=== Starting autonomy stack ==="
echo "Map: $MAP_NAME"
echo ""

echo "1) Starting localization..."
curl -sf -X POST "$BASE_URL/localization/start" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"$MAP_NAME\"}" | python3 -m json.tool
echo ""

sleep 2

echo "2) Setting initial pose (0, 0, 0)..."
curl -sf -X POST "$BASE_URL/localization/set_initial_pose" \
  -H "Content-Type: application/json" \
  -d '{"x": 0.0, "y": 0.0, "yaw": 0.0}' | python3 -m json.tool
echo ""

sleep 2

echo "3) Starting autonomy (Nav2)..."
curl -sf -X POST "$BASE_URL/autonomy/start" \
  -H "Content-Type: application/json" | python3 -m json.tool
echo ""

echo "4) Checking status..."
sleep 3
curl -sf "$BASE_URL/status" | python3 -m json.tool
