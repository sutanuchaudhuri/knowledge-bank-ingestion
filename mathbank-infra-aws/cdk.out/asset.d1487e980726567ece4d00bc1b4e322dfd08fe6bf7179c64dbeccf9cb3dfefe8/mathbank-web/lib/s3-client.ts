import "server-only";
import { S3Client } from "@aws-sdk/client-s3";

export function createS3Client() {
  const { AWS_ENDPOINT_URL_S3: endpoint, AWS_REGION: region,
    AWS_ACCESS_KEY_ID: accessKeyId, AWS_SECRET_ACCESS_KEY: secretAccessKey } = process.env;
  if (!endpoint || !region || !accessKeyId || !secretAccessKey) {
    throw new Error("Neon S3 settings are missing. Run make sync-neon-env.");
  }
  const url = new URL(endpoint);
  if (url.protocol !== "https:" || url.username || url.password) throw new Error("Neon S3 endpoint must be credential-free HTTPS.");
  return new S3Client({ endpoint, region, credentials: { accessKeyId, secretAccessKey }, forcePathStyle: true });
}
