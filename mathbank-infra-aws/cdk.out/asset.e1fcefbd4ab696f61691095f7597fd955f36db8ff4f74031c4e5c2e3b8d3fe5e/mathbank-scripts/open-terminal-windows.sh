#!/usr/bin/env bash
# Opens one real, visible Terminal.app window per MathBank service, each running that
# service's foreground dev command (make run / make dev) so logs stream live and
# Ctrl-C in any one window stops only that service — the alternative to `make up`'s
# background-daemon-with-PID-file model (which this script does not use at all: no PID
# files, no log files, nothing to go stale or conflict with a stray process).
#
# Usage:
#   mathbank-scripts/open-terminal-windows.sh            # core 4: rest, agent, web, live
#   mathbank-scripts/open-terminal-windows.sh --extra     # + manim-studio, ml-inference, ml-frontend
#   mathbank-scripts/open-terminal-windows.sh --all       # core 4 + every extra service
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "ERROR: this script opens macOS Terminal.app windows; not supported on $(uname -s)." >&2
  exit 1
fi
if ! osascript -e 'exists application "Terminal"' >/dev/null 2>&1; then
  echo "ERROR: Terminal.app is not available." >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# name:directory:command — matches the root Makefile's up-app (core) / up-extra (extras) sets.
CORE_SERVICES=(
  "mathbank-rest:mathbank-rest:make run"
  "mathbank-agent:mathbank-agent:make run"
  "mathbank-web:mathbank-web:make dev"
  "mathbank-live:mathbank-live:make dev"
)
EXTRA_SERVICES=(
  "mathbank-manim-studio:mathbank-manim-studio:make run"
  "mathbank-ml-inference:mathbank-ml-inference:make run"
  "mathbank-ml-frontend:mathbank-ml-frontend:make dev"
)

services=("${CORE_SERVICES[@]}")
case "${1:-}" in
  --extra) services=("${EXTRA_SERVICES[@]}") ;;
  --all) services=("${CORE_SERVICES[@]}" "${EXTRA_SERVICES[@]}") ;;
  "") ;;
  *) echo "ERROR: unknown argument '$1' (expected --extra, --all, or nothing)" >&2; exit 1 ;;
esac

echo "Opening ${#services[@]} Terminal window(s)..."
for entry in "${services[@]}"; do
  name="${entry%%:*}"
  rest="${entry#*:}"
  dir="${rest%%:*}"
  cmd="${rest#*:}"
  full_cmd="cd $(printf '%q' "$ROOT_DIR/$dir") && echo '--- $name ($dir) ---' && $cmd"
  osascript -e "tell application \"Terminal\" to do script \"$full_cmd\"" >/dev/null
  echo "  opened: $name  ($dir -> $cmd)"
done
echo "Done. Each window runs in the foreground; Ctrl-C in a window stops only that service."
