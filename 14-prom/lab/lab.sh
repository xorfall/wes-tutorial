# Shared by setup.sh and teardown.sh; sourced, not run. The caller sets LAB
# (this directory) and SCRIPT (its name, used in messages).
PROJECT=wes-tutorial-14

fail() {
  echo "$SCRIPT: $*" >&2
  exit 1
}
compose() {
  docker compose -f "$LAB/compose.yaml" "$@"
}
require_docker() {
  command -v docker >/dev/null 2>&1 || fail "docker is not installed"
  docker compose version >/dev/null 2>&1 \
    || fail "the docker compose plugin is not available"
  docker info >/dev/null 2>&1 || fail "the Docker daemon is not reachable"
}
# Containers of this project created from another directory run other files;
# neither take them over nor remove them.
refuse_foreign() {
  dirs=$(docker ps -a --filter "label=com.docker.compose.project=$PROJECT" \
    --format '{{.Label "com.docker.compose.project.working_dir"}}') \
    || fail "cannot list the containers of project $PROJECT"
  foreign=$(printf '%s\n' "$dirs" | sort -u | grep -Fvx "$LAB" || true)
  if [ -n "$dirs" ] && [ -n "$foreign" ]; then
    fail "project $PROJECT has containers from another directory" \
      "($(printf '%s' "$foreign" | tr '\n' ' ')); run teardown.sh there first"
  fi
}
