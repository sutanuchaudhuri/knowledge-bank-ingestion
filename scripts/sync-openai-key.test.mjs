import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, mkdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";
import test from "node:test";
import { fileURLToPath } from "node:url";

const exec = promisify(execFile);
const script = fileURLToPath(new URL("./sync-openai-key.mjs", import.meta.url));
const fakeKey = "sk-test-fixture-not-a-real-secret";

async function fixture(run) {
  const root = await mkdtemp(join(tmpdir(), "mathbank-env-test-"));
  try {
    await run(root);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

function sync(root, key = "") {
  return exec(process.execPath, [script, root], {
    env: { ...process.env, OPENAI_API_KEY: key },
  });
}

test("root key wins; preserve settings, replace duplicate keys and secure existing env files", async () => {
  await fixture(async (root) => {
    await writeFile(join(root, ".env"), `OPENAI_API_KEY="${fakeKey}" # model\n`);
    await mkdir(join(root, "mathbank-rest"));
    await writeFile(join(root, "mathbank-rest/.env"),
      "# preserved\nPOSTGRES_HOST=example\nOPENAI_API_KEY=old\nexport OPENAI_API_KEY=duplicate\n");
    await mkdir(join(root, "mathbank-web"));
    await writeFile(join(root, "mathbank-web/.env"), "ADMIN_LOGIN_USERNAME=test\n");
    const { stdout, stderr } = await sync(root, "sk-shell-fixture");
    assert.ok(!stdout.includes(fakeKey));
    assert.ok(!stderr.includes(fakeKey));
    for (const service of ["mathbank-rest", "mathbank-agent", "mathbank_data_ingestion", "mathbank-web"]) {
      const text = await readFile(join(root, service, ".env"), "utf8");
      assert.equal(text.match(/^OPENAI_API_KEY=/gm).length, 1);
      assert.ok(text.includes(`OPENAI_API_KEY=${fakeKey}`));
      assert.equal((await stat(join(root, service, ".env"))).mode & 0o777, 0o600);
    }
    assert.ok((await readFile(join(root, "mathbank-rest/.env"), "utf8")).includes("POSTGRES_HOST=example"));
    await sync(root);
    assert.equal((await readFile(join(root, "mathbank-agent/.env"), "utf8")).match(/^OPENAI_API_KEY=/gm).length, 1);
    await assert.rejects(stat(join(root, "mathbank-db/.env")), { code: "ENOENT" });
  });
});

test("exported shell key is ignored when root key is absent", async () => {
  await fixture(async (root) => {
    await assert.rejects(sync(root, fakeKey), error => error.stderr.includes("shell keys are ignored"));
    await assert.rejects(stat(join(root, "mathbank_data_ingestion/.env")), { code: "ENOENT" });
  });
});

test("missing or invalid key fails before changing any target and never prints its value", async () => {
  for (const key of ["", "change-me", "secret invalid value"]) {
    await fixture(async (root) => {
      await writeFile(join(root, ".env"), `OPENAI_API_KEY=${key}\n`);
      await mkdir(join(root, "mathbank-rest"));
      await writeFile(join(root, "mathbank-rest/.env"), "EXISTING=keep\n");
      await assert.rejects(sync(root), (error) => error.stderr.includes("Set a valid OPENAI_API_KEY") &&
        (!key || !error.stderr.includes(key)));
      assert.equal(await readFile(join(root, "mathbank-rest/.env"), "utf8"), "EXISTING=keep\n");
    });
  }
});
