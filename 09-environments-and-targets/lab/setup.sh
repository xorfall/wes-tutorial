#!/bin/sh
# Starts the tutorial lab: creates a key pair, starts the containers and records the host key.
# Usage: sh setup.sh        (from any directory)
set -eu
LAB=$(cd "$(dirname "$0")" && pwd)
STATE="$LAB/.state"
mkdir -p "$STATE"
if [ ! -f "$STATE/id_ed25519" ]; then
  ssh-keygen -q -t ed25519 -N '' -C wes-tutorial -f "$STATE/id_ed25519"
fi
cp "$STATE/id_ed25519.pub" "$STATE/authorized_keys"
chmod 644 "$STATE/authorized_keys"
docker compose -f "$LAB/compose.yaml" up -d --build --wait
# Record the host key of edge-host so that SSH can verify it.
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  if ssh-keyscan -p 2222 -t ed25519 127.0.0.1 > "$STATE/known_hosts" 2>/dev/null && [ -s "$STATE/known_hosts" ]; then
    break
  fi
  sleep 1
done
echo "Lab ready. Environment package: $LAB/environments.yaml"
