import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { authenticate } from '@google-cloud/local-auth';
import { google } from 'googleapis';

const DRIVE_SCOPE = ['https://www.googleapis.com/auth/drive'];

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (!key.startsWith('--')) {
      continue;
    }
    args[key.slice(2)] = value;
    i += 1;
  }
  return args;
}

function requireArg(args, name, whenTask) {
  if (!args[name]) {
    throw new Error(`Missing --${name}${whenTask ? ` for task ${whenTask}` : ''}`);
  }
}

async function getOAuthClient(credentialsPath, tokenPath) {
  if (fs.existsSync(tokenPath)) {
    const token = JSON.parse(fs.readFileSync(tokenPath, 'utf8'));
    const credentials = JSON.parse(fs.readFileSync(credentialsPath, 'utf8'));
    const installed = credentials.installed || credentials.web;
    const client = new google.auth.OAuth2(
      installed.client_id,
      installed.client_secret,
      installed.redirect_uris?.[0]
    );
    client.setCredentials(token);
    return client;
  }

  const client = await authenticate({
    keyfilePath: credentialsPath,
    scopes: DRIVE_SCOPE,
  });

  fs.writeFileSync(tokenPath, JSON.stringify(client.credentials, null, 2), 'utf8');
  return client;
}

async function getServiceAccountClient(credentialsPath) {
  const auth = new google.auth.GoogleAuth({
    keyFile: credentialsPath,
    scopes: DRIVE_SCOPE,
  });
  return auth.getClient();
}

async function listFiles(drive) {
  const res = await drive.files.list({
    pageSize: 20,
    fields: 'files(id, name, mimeType, modifiedTime)',
    orderBy: 'modifiedTime desc',
  });

  const files = res.data.files || [];
  if (files.length === 0) {
    console.log('No files found.');
    return;
  }

  for (const f of files) {
    console.log(`${f.id}\t${f.name}\t${f.mimeType}\t${f.modifiedTime}`);
  }
}

async function searchFiles(drive, query) {
  const res = await drive.files.list({
    q: query,
    pageSize: 20,
    fields: 'files(id, name, mimeType)',
  });

  const files = res.data.files || [];
  for (const f of files) {
    console.log(`${f.id}\t${f.name}\t${f.mimeType}`);
  }
}

async function uploadFile(drive, localPath, targetName) {
  const mimeType = 'application/octet-stream';
  const response = await drive.files.create({
    requestBody: {
      name: targetName,
    },
    media: {
      mimeType,
      body: fs.createReadStream(localPath),
    },
    fields: 'id, name',
  });

  console.log(`Uploaded: ${response.data.name} (${response.data.id})`);
}

async function downloadFile(drive, fileId, outPath) {
  const dest = fs.createWriteStream(outPath);
  const res = await drive.files.get(
    {
      fileId,
      alt: 'media',
    },
    {
      responseType: 'stream',
    }
  );

  await new Promise((resolve, reject) => {
    res.data
      .on('end', resolve)
      .on('error', reject)
      .pipe(dest);
  });

  console.log(`Downloaded to: ${outPath}`);
}

async function main() {
  const args = parseArgs(process.argv);
  const mode = args.mode || 'oauth2';
  const task = args.task || 'list';
  const credentialsPath = path.resolve(args.credentials || './credentials.json');
  const tokenPath = path.resolve(args.token || './token.json');

  if (!fs.existsSync(credentialsPath)) {
    throw new Error(`Credentials file not found: ${credentialsPath}`);
  }

  let authClient;
  if (mode === 'oauth2') {
    authClient = await getOAuthClient(credentialsPath, tokenPath);
  } else if (mode === 'service-account') {
    authClient = await getServiceAccountClient(credentialsPath);
  } else {
    throw new Error('Invalid --mode. Use oauth2 or service-account.');
  }

  const drive = google.drive({ version: 'v3', auth: authClient });

  if (task === 'list') {
    await listFiles(drive);
    return;
  }

  if (task === 'search') {
    requireArg(args, 'query', task);
    await searchFiles(drive, args.query);
    return;
  }

  if (task === 'upload') {
    requireArg(args, 'file', task);
    const localPath = path.resolve(args.file);
    if (!fs.existsSync(localPath)) {
      throw new Error(`Upload file not found: ${localPath}`);
    }
    const targetName = args.name || path.basename(localPath);
    await uploadFile(drive, localPath, targetName);
    return;
  }

  if (task === 'download') {
    requireArg(args, 'id', task);
    requireArg(args, 'out', task);
    await downloadFile(drive, args.id, path.resolve(args.out));
    return;
  }

  throw new Error('Invalid --task. Use list, search, upload, or download.');
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
