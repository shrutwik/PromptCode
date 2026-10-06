#!/bin/sh
# Start as root so the interview workspace bind-mount is writable, then drop
# to promptcode. When compose sets user: promptcode, skip straight to the command.
set -eu

ws="${PROMPTCODE_INTERVIEW_WORKSPACE_ROOT:-/app/data/interview_workspaces}"

if [ "$(id -u)" = "0" ]; then
  mkdir -p "$ws"
  if [ -S /var/run/docker.sock ]; then
    sock_gid="$(stat -c '%g' /var/run/docker.sock)"
    if ! getent group "$sock_gid" >/dev/null 2>&1; then
      groupadd -g "$sock_gid" dockerhost
    fi
    group_name="$(getent group "$sock_gid" | cut -d: -f1)"
    usermod -aG "$group_name" promptcode
  fi
  chown promptcode:promptcode "$ws"
  exec runuser -u promptcode -- "$@"
fi

exec "$@"
