#!/usr/bin/env bash
# Called from a service directory; success requires a live process and HTTP 200.
set -euo pipefail

name="$1"
port="$2"
pid_file="$3"
log_file="$4"
url="$5"
shift 5
timeout="${START_TIMEOUT:-60}"

if ! [[ "$timeout" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: START_TIMEOUT must be a positive number of seconds." >&2
  exit 1
fi
for tool in curl lsof nohup ps; do
  command -v "$tool" >/dev/null || { echo "ERROR: $tool is required to start $name." >&2; exit 1; }
done
if ! command -v "$1" >/dev/null 2>&1; then
  echo "ERROR: $name executable is missing or not executable: $1" >&2
  echo "Install dependencies on THIS machine; do not copy .venv or node_modules from another Mac." >&2
  exit 1
fi

pid=""
if [ -f "$pid_file" ]; then
  read -r pid < "$pid_file" || true
fi
listener="$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
owns_listener() {
  local candidate="$1" parent
  [[ "$candidate" =~ ^[1-9][0-9]*$ ]] || return 1
  while [ "$candidate" -gt 1 ]; do
    [ "$candidate" = "$pid" ] && return 0
    parent="$(ps -p "$candidate" -o ppid= 2>/dev/null | tr -d ' ')" || return 1
    [[ "$parent" =~ ^[1-9][0-9]*$ ]] || return 1
    candidate="$parent"
  done
  return 1
}
if [ -n "$listener" ]; then
  if [[ "$pid" =~ ^[1-9][0-9]*$ ]] && owns_listener "$listener" && kill -0 "$pid" 2>/dev/null; then
    code="$(curl --noproxy '*' -s -o /dev/null -w '%{http_code}' --max-time 3 "$url" || true)"
    if [ "$code" = "200" ]; then
      echo "$name already ready: $url (pid $pid)"
      exit 0
    fi
    # Our own recorded process holds the port but is unhealthy: restart it.
    # Processes this script did not start are never killed (see below).
    echo "$name (pid $pid) is running but unhealthy (HTTP ${code:-none} from $url); restarting it."
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
      lsof -nP -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1 || break
      sleep 0.5
    done
    if lsof -nP -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      kill -9 "$pid" 2>/dev/null || true
      sleep 1
    fi
    rm -f "$pid_file"
    pid=""
    listener="$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  fi
fi
if [ -n "$listener" ]; then
  echo "ERROR: port $port is already occupied (PID $listener), not by a process this script started. No process was killed." >&2
  echo "Inspect it with: lsof -nP -iTCP:$port -sTCP:LISTEN" >&2
  echo "Stop the intended service explicitly before retrying." >&2
  exit 1
fi
if [[ "$pid" =~ ^[1-9][0-9]*$ ]] && kill -0 "$pid" 2>/dev/null; then
  echo "ERROR: $name recorded process $pid is alive but not ready on port $port; inspect $log_file." >&2
  exit 1
fi

nohup "$@" > "$log_file" 2>&1 < /dev/null &
pid=$!
echo "$pid" > "$pid_file"
deadline=$((SECONDS + timeout))
while [ "$SECONDS" -lt "$deadline" ]; do
  if ! kill -0 "$pid" 2>/dev/null; then
    wait "$pid" || true
    rm -f "$pid_file"
    echo "ERROR: $name exited during startup. Inspect $(pwd)/$log_file" >&2
    echo "Run its foreground command to see the error: make run (web: make dev)." >&2
    exit 1
  fi
  listener="$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if owns_listener "$listener" &&
     [ "$(curl --noproxy '*' -s -o /dev/null -w '%{http_code}' --max-time 3 "$url" || true)" = "200" ] &&
     kill -0 "$pid" 2>/dev/null; then
    echo "$name ready: $url (pid $pid), logs in $log_file"
    exit 0
  fi
  sleep 1
done
kill "$pid" 2>/dev/null || true
wait "$pid" || true
rm -f "$pid_file"
echo "ERROR: $name did not become ready at $url within ${timeout}s. Inspect $(pwd)/$log_file" >&2
exit 1
