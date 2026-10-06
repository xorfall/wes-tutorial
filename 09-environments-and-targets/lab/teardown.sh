#!/bin/sh
# Stops the tutorial lab and removes its containers, image and generated keys.
set -eu
LAB=$(cd "$(dirname "$0")" && pwd)
docker compose -f "$LAB/compose.yaml" down --rmi local --volumes
rm -rf "$LAB/.state"
