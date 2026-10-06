#!/bin/sh
# Keep tmpfs mounted until the API retrieves the report. Never trust this for grading.
cp -R /source/. /workspace/ || exit 1
# Dependencies are baked into the reviewed runner image, never installed here.
slug=${PC_CHALLENGE_SLUG:-}
case "$slug" in *[!a-z0-9-]*) exit 1 ;; esac
if [ -n "$slug" ] && [ -d "/opt/promptcode-deps/$slug/node_modules" ]; then
  mkdir /workspace/node_modules || exit 1
  cp -as "/opt/promptcode-deps/$slug/node_modules/." /workspace/node_modules/ || exit 1
fi
"$@"
status=$?
printf '{"exit_code":%d}' "$status" > /tmp/promptcode-exit.json
sleep 300
