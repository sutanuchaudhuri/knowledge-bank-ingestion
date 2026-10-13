#!/usr/bin/env bash
# Seeds SSM SecureString parameters for one service's secret env vars, read from that
# service's local .env file — never printed to stdout/logs (requirements/63). Idempotent
# (re-running updates the value and creates a new SSM parameter *version*, which is
# exactly what ssm_config.py's dynamic-reference resolution expects to pick up on the
# next `cdk deploy`).
#
# Usage: ./seed_ssm.sh mathbank-rest
set -euo pipefail

SERVICE="${1:?Usage: seed_ssm.sh <service-dir-name>, e.g. mathbank-rest}"
REGION="${AWS_REGION:-us-east-2}"
PROFILE="${AWS_PROFILE:-aws-sutanu-admin}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/$SERVICE/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found." >&2
  exit 1
fi

# Keep in sync with stacks/ssm_config.py's SECRET_ENV_KEYS, plus a few
# service-local-name variants (e.g. MATHBANK_ADMIN_API_KEY) that aren't literally the
# same key name as another service's but hold the same kind of sensitive value.
SECRET_KEYS=(
  POSTGRES_PASSWORD NEO4J_PASSWORD JWT_SECRET ADMIN_API_KEY OPENAI_API_KEY
  AWS_SECRET_ACCESS_KEY NEON_AI_GATEWAY_TOKEN ELEVEN_API_KEY ADMIN_SESSION_SECRET
  ADMIN_LOGIN_PASSWORD COGNITO_CLIENT_SECRET MATHBANK_ADMIN_API_KEY
)

echo "Seeding SSM SecureString parameters for $SERVICE in $REGION (profile: $PROFILE)..."
seeded=0
for key in "${SECRET_KEYS[@]}"; do
  # Case-insensitive: mathbank-manim-studio's own .env (unlike every other service's,
  # which sync-env.sh generates uppercase) uses lowercase keys — pydantic-settings
  # matches env vars case-insensitively, so the app is unaffected, but this grep
  # previously was not (requirements/63).
  value="$(grep -iE "^${key}=" "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
  # Strip one layer of surrounding quotes, if present, matching dotenv's own convention.
  value="${value%\"}"; value="${value#\"}"
  if [[ -z "$value" ]]; then
    continue
  fi
  aws ssm put-parameter \
    --name "/mathbank/dev/${SERVICE}/${key}" \
    --type SecureString \
    --value "$value" \
    --overwrite \
    --region "$REGION" \
    --profile "$PROFILE" \
    >/dev/null
  echo "  seeded: /mathbank/dev/${SERVICE}/${key}"
  seeded=$((seeded + 1))
done
echo "Done — $seeded parameter(s) seeded. Values were never printed."
