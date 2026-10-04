#!/usr/bin/env bash
# Root setup check — mirrors `make up`'s all-services scope, but for first-time
# configuration instead of runtime lifecycle. Safe to re-run any time: it only
# ever creates what's missing (.env files, venvs, node_modules) and otherwise
# just reports status. See root README.md ("make setup") and GOTCHAS.md.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MISSING=0
ok()    { printf "  \033[32m\xe2\x9c\x93\033[0m %s\n" "$1"; }
warn()  { printf "  \033[33m\xe2\x9a\xa0\033[0m %s\n" "$1"; MISSING=1; }
info()  { printf "  %s\n" "$1"; }
section(){ printf "\n\033[1m%s\033[0m\n" "$1"; }

# ── 1. .env files: create from .env.example if missing, flag leftover placeholders ──
section "Environment files"

check_env_file() {
  local dir="$1"
  local example="$dir/.env.example"
  local envfile="$dir/.env"
  [ -f "$example" ] || return 0
  if [ ! -f "$envfile" ]; then
    cp "$example" "$envfile"
    warn "$dir/.env did not exist — created from .env.example. Edit it before running this service."
    return
  fi
  local placeholders=()
  while IFS='=' read -r key rest; do
    [[ "$key" =~ ^[[:space:]]*# ]] && continue
    [ -z "$key" ] && continue
    local example_val="${rest%%#*}"
    example_val="$(echo -n "$example_val" | xargs 2>/dev/null || true)"
    case "$example_val" in
      ""|change-me*|ChangeMe*) ;;
      *) continue ;;
    esac
    local actual_val
    actual_val=$(grep -E "^${key}=" "$envfile" 2>/dev/null | tail -1 | cut -d= -f2- | xargs 2>/dev/null || true)
    if [ -z "$actual_val" ] || [ "$actual_val" = "$example_val" ]; then
      placeholders+=("$key")
    fi
  done < "$example"
  if [ "${#placeholders[@]}" -eq 0 ]; then
    ok "$dir/.env present, no placeholder values left"
  else
    warn "$dir/.env present but still has placeholder value(s): ${placeholders[*]}"
  fi
}

for d in mathbank-db mathbank-graph mathbank-rest mathbank-agent mathbank-web; do
  check_env_file "$d"
done

if [ -f mathbank-graph/remote.env.example ]; then
  if [ ! -f mathbank-graph/remote.env ]; then
    warn "mathbank-graph/remote.env missing — needed for every *-remote make target (Neon + AuraDB). Copy from remote.env.example and fill in."
  else
    ok "mathbank-graph/remote.env present"
  fi
fi

# ── 2. Shell-level secrets ──────────────────────────────────────────────────
section "Shell environment"
if [ -n "${OPENAI_API_KEY:-}" ]; then
  ok "OPENAI_API_KEY is exported in this shell"
else
  if grep -Eq '^[[:space:]]*(export[[:space:]]+)?OPENAI_API_KEY[[:space:]]*=[[:space:]]*[^[:space:]]+' .env 2>/dev/null; then
    info "OPENAI_API_KEY found in root .env; synchronizing without displaying it."
    if node scripts/sync-openai-key.mjs; then
      ok "OPENAI_API_KEY synchronized to service environment files"
    else
      warn "OPENAI_API_KEY synchronization failed; fix the root .env before startup."
    fi
  else
    warn "OPENAI_API_KEY is missing — add it to root .env and run make sync-openai-key, or export it in your shell."
  fi
fi

# ── 3. Python virtual environments ──────────────────────────────────────────
section "Python virtual environments"

setup_venv() {
  local dir="$1" target="$2"
  if [ -d "$dir/.venv" ]; then
    ok "$dir/.venv already present"
  else
    info "$dir/.venv missing — running 'make -C $dir $target'..."
    if (cd "$dir" && make "$target"); then
      ok "$dir/.venv created"
    else
      warn "$dir/.venv setup FAILED — run 'cd $dir && make $target' manually to see the error"
    fi
  fi
}

setup_venv mathbank_data_ingestion install
setup_venv mathbank-db etl-venv
setup_venv mathbank-graph etl-venv
setup_venv mathbank-rest install
setup_venv mathbank-agent install

# ── 4. Node / Next.js ────────────────────────────────────────────────────────
section "mathbank-web (Node / Next.js)"
if [ -d mathbank-web/node_modules ]; then
  ok "mathbank-web/node_modules already present"
else
  info "mathbank-web/node_modules missing — running 'make -C mathbank-web install'..."
  if (cd mathbank-web && make install); then
    ok "mathbank-web dependencies installed"
  else
    warn "mathbank-web install FAILED — run 'cd mathbank-web && make install' manually to see the error"
  fi
fi

# ── 5. Summary ───────────────────────────────────────────────────────────────
section "Summary"
if [ "$MISSING" -eq 0 ]; then
  echo "Everything is configured and installed. Start the stack with: make up"
else
  printf "Some configuration needs attention (see \033[33m\xe2\x9a\xa0\033[0m above) before running: make up\n"
fi
