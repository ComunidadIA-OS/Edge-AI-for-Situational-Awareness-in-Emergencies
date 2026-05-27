#!/usr/bin/env bash
# Heimdall — post-deployment smoke test.
#
# After `docker compose up`, run this script to confirm both containers are
# healthy, the API contract is honoured, and the model is loaded.
#
# Usage:   bash scripts/verify_stack.sh

set -e

API_URL="${1:-http://localhost:8000}"
GREEN="\033[1;32m"; RED="\033[1;31m"; YELLOW="\033[1;33m"; NC="\033[0m"

pass() { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; FAIL=1; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }

FAIL=0
echo "Heimdall stack verification — API at $API_URL"
echo

# 1. Containers
echo "1. Docker containers"
if docker ps --format '{{.Names}}' | grep -q "xheimdall-convergence-api"; then
    pass "convergence-api is running"
else
    fail "convergence-api is NOT running"
fi
if docker ps --format '{{.Names}}' | grep -q "xheimdall-vision-inference"; then
    pass "vision-inference is running"
else
    warn "vision-inference is NOT running (camera-less host? check 'docker compose ps')"
fi
echo

# 2. Health endpoint
echo "2. API health"
if HEALTH=$(curl -fsS "$API_URL/health" 2>&1); then
    pass "GET $API_URL/health responded"
    echo "      $HEALTH" | head -c 200; echo
else
    fail "GET $API_URL/health failed: $HEALTH"
fi
echo

# 3. Schema contract
echo "3. MeteoReport schema contract"
RESP=$(curl -fsS -X POST "$API_URL/detect" -H "Content-Type: application/json" -d '{
  "drone_telemetry": {"lat":41.6837,"lon":-0.8881,"altitud_m":120,"heading_deg":245,"speed_kmh":35,"timestamp":"2026-05-26T22:00:00Z"},
  "perimeter": {"coordinates":[[[-0.8885,41.6835],[-0.8877,41.6835],[-0.8877,41.6839],[-0.8885,41.6839],[-0.8885,41.6835]]]},
  "area_ha": 0.5, "centroid": {"lat":41.6837,"lon":-0.8881}, "confidence": 0.9,
  "fuel_type_id": 7, "hotspots": [{"lat":41.6837,"lon":-0.8881,"temperature_c":380,"confidence":0.9}],
  "detected_at": "2026-05-26T22:00:00Z"
}' 2>&1) || { fail "POST /detect failed: $RESP"; exit 1; }

python3 - <<PY
import json, sys
d = json.loads('''$RESP''')
ok = True
def check(cond, msg):
    global ok
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond: ok = False
check(d.get('fire_perimeter',{}).get('polygon',{}).get('type') == 'Polygon', "fire_perimeter.polygon.type == 'Polygon'")
check(isinstance(d.get('fire_perimeter',{}).get('centroid'), list), "fire_perimeter.centroid is a list")
check(isinstance(d.get('metadata',{}).get('location'), list), "metadata.location is a list")
check(len(d.get('prediction',{}).get('hourly',[])) == 24, "prediction.hourly has 24 entries")
check(len(d.get('risk_buffers',[])) == 3, "risk_buffers has 3 entries")
distances = sorted({b['distance_km'] for b in d.get('risk_buffers',[])})
check(distances == [1.0, 3.0, 5.0], f"risk_buffer distances == [1, 3, 5] km (got {distances})")
sys.exit(0 if ok else 1)
PY
[ $? -ne 0 ] && FAIL=1
echo

# 4. Model engine
echo "4. TensorRT engine"
if [ -f "models/best.engine" ]; then
    SIZE_MB=$(du -m models/best.engine | cut -f1)
    pass "models/best.engine present (${SIZE_MB} MB)"
else
    warn "models/best.engine NOT present (entrypoint will export it from best.pt on first boot)"
fi
echo

if [ "$FAIL" = "1" ]; then
    echo -e "${RED}One or more checks failed.${NC} Connect a screen and inspect container logs:"
    echo "  docker compose -f docker/docker-compose.yml logs --tail=50"
    exit 1
fi
echo -e "${GREEN}All checks passed — stack is ready.${NC}"
