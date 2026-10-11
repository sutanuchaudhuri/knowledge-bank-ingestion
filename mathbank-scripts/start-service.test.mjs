import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { createServer } from "node:http";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";
import test from "node:test";
import { fileURLToPath } from "node:url";

const exec = promisify(execFile);
const script = fileURLToPath(new URL("./start-service.sh", import.meta.url));
const pidFile = ".server.pid";

async function fixture(run) {
  const directory = await mkdtemp(join(tmpdir(), "mathbank-start-test-"));
  try {
    await run(directory);
  } finally {
    try {
      const pid = Number((await readFile(join(directory, pidFile), "utf8")).trim());
      process.kill(pid, "SIGTERM");
    } catch (error) {
      if (!["ENOENT", "ESRCH"].includes(error.code)) throw error;
    }
    await rm(directory, { recursive: true, force: true });
  }
}

async function freePort() {
  const server = createServer();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;
  await new Promise((resolve) => server.close(resolve));
  return port;
}

function start(directory, port, command, timeout = "5") {
  return exec("bash", [
    script, "test-service", String(port), pidFile, ".server.log",
    `http://127.0.0.1:${port}/ready`, ...command,
  ], { cwd: directory, env: { ...process.env, START_TIMEOUT: timeout }, timeout: 15000 });
}

test("missing executable fails without a success message or PID file", async () => {
  await fixture(async (directory) => {
    await assert.rejects(start(directory, await freePort(), ["./missing"]),
      (error) => error.stderr.includes("missing or not executable") && !error.stdout.includes("ready:"));
    await assert.rejects(readFile(join(directory, pidFile)), { code: "ENOENT" });
  });
});

test("early process exit reports log location and removes stale PID", async () => {
  await fixture(async (directory) => {
    await assert.rejects(start(directory, await freePort(), ["bash", "-c", "exit 7"]),
      (error) => error.stderr.includes("exited during startup") && error.stderr.includes(".server.log"));
    await assert.rejects(readFile(join(directory, pidFile)), { code: "ENOENT" });
  });
});

test("copied virtualenv entrypoint with a stale shebang cannot report success", async () => {
  await fixture(async (directory) => {
    await writeFile(join(directory, "stale-entrypoint"), "#!/nonexistent/old-machine/python\n", { mode: 0o755 });
    await assert.rejects(start(directory, await freePort(), ["./stale-entrypoint"]),
      (error) => error.stderr.includes("exited during startup"));
  });
});

test("delayed HTTP readiness succeeds and a second start reuses the owned process", async () => {
  await fixture(async (directory) => {
    const port = await freePort();
    const command = [process.execPath, "-e",
      `setTimeout(()=>require('http').createServer((q,r)=>r.end('ready')).listen(${port},'127.0.0.1'),1100)`];
    const first = await start(directory, port, command);
    assert.match(first.stdout, /test-service ready:/);
    const pid = await readFile(join(directory, pidFile), "utf8");
    const second = await start(directory, port, command);
    assert.match(second.stdout, /already ready:/);
    assert.equal(await readFile(join(directory, pidFile), "utf8"), pid);
  });
});

test("occupied port fails without killing the unrelated server", async () => {
  const server = createServer((request, response) => response.end("unrelated"));
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  try {
    await fixture(async (directory) => {
      const port = server.address().port;
      await assert.rejects(start(directory, port, ["bash", "-c", "exit 0"]),
        (error) => error.stderr.includes("already occupied") && error.stderr.includes("No process was killed"));
      assert.equal(await (await fetch(`http://127.0.0.1:${port}`)).text(), "unrelated");
    });
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test("owned child listener is reused for dev servers with worker subprocesses", async () => {
  await fixture(async (directory) => {
    const port = await freePort();
    const worker = `require('http').createServer((q,r)=>r.end('ready')).listen(${port},'127.0.0.1')`;
    const command = [process.execPath, "-e",
      `const c=require('child_process').spawn(process.execPath,['-e',${JSON.stringify(worker)}]);
       process.on('SIGTERM',()=>{c.kill('SIGTERM');process.exit(0)});`];
    assert.match((await start(directory, port, command)).stdout, /test-service ready:/);
    assert.match((await start(directory, port, command)).stdout, /already ready:/);
  });
});

test("non-200 HTTP never counts as ready and timed-out child is stopped", async () => {
  await fixture(async (directory) => {
    const port = await freePort();
    await assert.rejects(start(directory, port, [process.execPath, "-e",
      `require('http').createServer((q,r)=>{r.statusCode=503;r.end('not ready')}).listen(${port},'127.0.0.1')`], "2"),
    (error) => error.stderr.includes("did not become ready") && !error.stdout.includes("ready:"));
    await assert.rejects(readFile(join(directory, pidFile)), { code: "ENOENT" });
    await assert.rejects(fetch(`http://127.0.0.1:${port}`));
  });
});
