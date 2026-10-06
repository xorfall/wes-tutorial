#!/bin/sh
# Stops the chapter 14 lab: removes the containers, network and Prometheus data volume
# of Compose project wes-tutorial-14 only. Pulled images are kept.
# Refuses when the project's containers were created from another directory.
set -eu
LAB=$(cd "$(dirname "$0")" && pwd)
SCRIPT=teardown
. "$LAB/lab.sh"

require_docker
refuse_foreign
compose down --volumes --remove-orphans --timeout 5
