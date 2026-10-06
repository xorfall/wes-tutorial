#!/bin/sh
# Starts the chapter 14 lab (Compose project wes-tutorial-14): orders-api, its workload
# and Prometheus, then waits until Prometheus holds orders-api samples.
# Usage: sh setup.sh        (from any directory)
# Host ports, loopback only: WES14_ORDERS_API_PORT (default 18770),
# WES14_PROMETHEUS_PORT (default 19091).
# A lab that is already running keeps its orders-api mode; a new one starts healthy.
set -eu
LAB=$(cd "$(dirname "$0")" && pwd)
SCRIPT=setup
. "$LAB/lab.sh"
ORDERS_PORT=${WES14_ORDERS_API_PORT:-18770}
PROMETHEUS_PORT=${WES14_PROMETHEUS_PORT:-19091}
WAIT_SECONDS=120
SAMPLE_SECONDS=30
# Network timeout of each probe inside a container, in seconds.
PROBE_SECONDS=2

require_docker
refuse_foreign

if ! compose up -d --wait --wait-timeout "$WAIT_SECONDS"; then
  echo "setup: the lab did not become healthy within $WAIT_SECONDS s; state and recent logs:" >&2
  compose ps -a >&2 || true
  compose logs --no-color --tail 20 >&2 || true
  exit 1
fi

# A rate needs two scrapes of orders-api; wait until Prometheus can compute one.
query='rate(wes_demo_requests_total%5B10s%5D)'
deadline=$(($(date +%s) + SAMPLE_SECONDS))
while :; do
  answer=$(compose exec -T prometheus wget -q -T "$PROBE_SECONDS" -O - \
    "http://127.0.0.1:9090/api/v1/query?query=$query" 2>/dev/null || true)
  case $answer in
    *'"result":[{'*) break ;;
  esac
  if [ "$(date +%s)" -ge "$deadline" ]; then
    fail "Prometheus has no orders-api samples after $SAMPLE_SECONDS s; see http://127.0.0.1:$PROMETHEUS_PORT/targets"
  fi
  sleep 1
done

mode=$(compose exec -T orders-api python -c \
  "import urllib.request as u; print(u.build_opener(u.ProxyHandler({})).open('http://127.0.0.1:8080/profile', timeout=$PROBE_SECONDS).read().decode())" \
  2>/dev/null || echo unknown)
echo "Lab ready (Compose project $PROJECT)."
echo "  orders-api  http://127.0.0.1:$ORDERS_PORT   $mode"
echo "  Prometheus  http://127.0.0.1:$PROMETHEUS_PORT"
echo "  Contracts   14-prom/api.yaml, 14-prom/prom.yaml"
echo "  Logs        docker compose -f 14-prom/lab/compose.yaml logs -f orders-api"
