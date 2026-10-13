// Fetches SSM SecureString secrets at container startup and writes them to
// .env.production.local, which Next.js (and mathbank-live's own
// nextEnv.loadEnvConfig() call) already load automatically with top precedence —
// no application code change needed beyond this one bootstrap step. Mirrors the
// Lambda services' cold-start `_load_secrets_from_ssm()` pattern (requirements/63),
// adapted for Fargate: a long-lived container fetches once at startup, not once per
// invocation, since there is no per-invocation cold start here.
//
// Reads MATHBANK_SSM_PREFIX/MATHBANK_SECRET_MAP (plain, non-secret env vars the CDK
// stack sets) — same two-variable convention as every Lambda service's
// lambda_handler.py, so this is the one new piece of plumbing, not a parallel scheme.
import { writeFileSync } from "node:fs";
import { SSMClient, GetParameterCommand } from "@aws-sdk/client-ssm";

async function main() {
  const prefix = process.env.MATHBANK_SSM_PREFIX;
  const secretMap = process.env.MATHBANK_SECRET_MAP;
  if (!prefix || !secretMap) {
    console.log("fetch-secrets: MATHBANK_SSM_PREFIX/MATHBANK_SECRET_MAP not set — local run, nothing to do");
    return;
  }
  const client = new SSMClient({ region: process.env.AWS_REGION || "us-east-2" });
  const lines = [];
  for (const pair of secretMap.split(",")) {
    const [suffix, targetEnvVar] = pair.split("=");
    if (!suffix || !targetEnvVar) continue;
    const name = `${prefix}/${suffix}`;
    const resp = await client.send(new GetParameterCommand({ Name: name, WithDecryption: true }));
    lines.push(`${targetEnvVar}=${resp.Parameter.Value}`);
  }
  writeFileSync(".env.production.local", lines.join("\n") + "\n", { mode: 0o600 });
  console.log(`fetch-secrets: wrote ${lines.length} secret(s) to .env.production.local`);
}

main().catch((err) => {
  console.error("fetch-secrets: FAILED —", err.message);
  process.exit(1);
});
