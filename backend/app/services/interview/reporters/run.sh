#!/bin/sh
# Keep tmpfs mounted until the API retrieves the report. Never trust this for grading.
cp -R /source/. /workspace/ || exit 1
"$@"
status=$?
printf '{"exit_code":%d}' "$status" > /tmp/promptcode-exit.json
sleep 300
