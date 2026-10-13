import "server-only";
import { S3Client } from "@aws-sdk/client-s3";

export function createS3Client() {
  // Neon's S3-compatible credentials, read under an alias (MATHBANK_S3_*) when set —
  // never the bare AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY names on any AWS compute
  // (Fargate, Lambda), since the AWS SDK's own default credential chain checks those
  // exact names first, ahead of the task/execution role, and would silently try to
  // authenticate every *other* AWS SDK client in this app (Cognito, SSM) as this Neon
  // storage key instead of the real role — confirmed live, this exact collision broke
  // Cognito calls once this app moved off `AWS_PROFILE`-based local dev (requirements/62
  // §6a). The bare names are still read as a fallback for existing local .env files.
  const endpoint = process.env.MATHBANK_S3_ENDPOINT_URL || process.env.AWS_ENDPOINT_URL_S3;
  const region = process.env.MATHBANK_S3_REGION || process.env.AWS_REGION;
  const accessKeyId = process.env.MATHBANK_S3_ACCESS_KEY_ID || process.env.AWS_ACCESS_KEY_ID;
  const secretAccessKey = process.env.MATHBANK_S3_SECRET_ACCESS_KEY || process.env.AWS_SECRET_ACCESS_KEY;
  if (!endpoint || !region || !accessKeyId || !secretAccessKey) {
    throw new Error("Neon S3 settings are missing. Run make sync-neon-env.");
  }
  const url = new URL(endpoint);
  if (url.protocol !== "https:" || url.username || url.password) throw new Error("Neon S3 endpoint must be credential-free HTTPS.");
  return new S3Client({ endpoint, region, credentials: { accessKeyId, secretAccessKey }, forcePathStyle: true });
}
