import { execFile, spawn } from "node:child_process";
import { mkdtemp, realpath, readFile, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

export const MAX_ASYMPTOTE_CHARS = 32000;
let active = 0;

export class DiagramRenderError extends Error {
  constructor(message, status = 422) {
    super(message);
    this.status = status;
  }
}

export function validateAsymptote(source) {
  if (typeof source !== "string" || !source.trim() || source.length > MAX_ASYMPTOTE_CHARS) {
    throw new DiagramRenderError("Provide Asymptote source between 1 and 32000 characters.");
  }
  const code = source.replace(/"(?:[^"\\]|\\[\s\S])*"|'(?:[^'\\]|\\[\s\S])*'|\/\/[^\n]*|\/\*[\s\S]*?\*\//g,
    (part) => part.startsWith("/") ? " " : part);
  // OS isolation remains authoritative; reject escape/configuration primitives too.
  if (/\b(?:system|execute|eval|fork|shipout|settings|access|input|output|include|read|write|rename|delete|mkdir|chdir)\b|https?:|file:|\\(?:input|include|write|openout|catcode)\b/i.test(code)) {
    throw new DiagramRenderError("This diagram uses unsupported file, process or configuration operations.");
  }
  const imports = [...code.matchAll(/\b(?:import|from)\s+([^;\n]+)/g)].map((m) => m[1].trim());
  if (imports.some((name) => !["bsp", "three", "geometry", "graph", "math"].includes(name))) {
    throw new DiagramRenderError("This diagram imports an unsupported Asymptote module.");
  }
}

export function sandboxProfile(directory) {
  const target = JSON.stringify(directory);
  return `(version 1)
(deny default)
(allow process-fork)
(allow process-exec)
(allow sysctl-read)
(allow mach-lookup)
(allow file-read-metadata)
(allow file-map-executable (subpath "/usr/bin") (subpath "/usr/lib") (subpath "/bin")
  (subpath "/System") (subpath "/Library/TeX") (subpath "/usr/local/texlive")
  (subpath "/opt/homebrew/Cellar") (subpath "/opt/homebrew/lib") (subpath "/private/preboot"))
(allow file-read* (subpath "/usr/bin") (subpath "/usr/lib") (subpath "/usr/share")
  (subpath "/usr/libexec") (subpath "/usr/local/texlive") (subpath "/bin")
  (subpath "/System") (subpath "/Library/TeX")
  (subpath "/private/preboot") (subpath "/private/var/db/dyld")
  (subpath "/Library/Fonts") (subpath "/opt/homebrew/bin") (subpath "/opt/homebrew/lib")
  (subpath "/opt/homebrew/share") (subpath "/opt/homebrew/Cellar") (subpath ${target})
  (literal "/") (literal "/dev/null") (literal "/dev/urandom") (literal "/dev/random"))
(allow file-write* (subpath ${target}) (literal "/dev/null"))
`;
}

function compile(directory, executable) {
  return new Promise((resolve, reject) => {
    const child = spawn("/usr/bin/sandbox-exec", [
      "-f", path.join(directory, "sandbox.sb"), "/bin/sh", "-c",
      'ulimit -t 10; ulimit -f 8192; exec "$@"', "mathbank-asy", executable,
      "-safe", "-noV", "-nointeractiveView", "-render", "0", "-tex", "latex",
      "-f", "png", "-o", "diagram", "source.asy",
    ], {
      cwd: directory, detached: true, stdio: ["ignore", "ignore", "pipe"],
      env: {
        PATH: "/Library/TeX/texbin:/opt/homebrew/bin:/usr/bin:/bin",
        HOME: directory, TMPDIR: directory, ASYMPTOTE_HOME: directory,
        LANG: "en_US.UTF-8",
      },
    });
    let diagnostics = "";
    let timedOut = false;
    let memoryExceeded = false;
    let closed = false;
    let monitorFailed = false;
    const terminate = () => {
      if (child.pid) {
        try { process.kill(-child.pid, "SIGKILL"); }
        catch (error) { if (error.code !== "ESRCH") reject(error); }
      }
    };
    const timer = setTimeout(() => { timedOut = true; terminate(); }, 15000);
    const monitor = setInterval(() => {
      execFile("/bin/ps", ["-axo", "pgid=,rss="], { timeout: 1000 }, (error, stdout) => {
        if (closed) return;
        if (error) { monitorFailed = true; terminate(); return; }
        const memory = stdout.trim().split("\n").reduce((sum, line) => {
          const [group, rss] = line.trim().split(/\s+/).map(Number);
          return sum + (group === child.pid ? rss : 0);
        }, 0);
        if (memory > 512 * 1024) { memoryExceeded = true; terminate(); }
      });
    }, 250);
    child.stderr.on("data", (chunk) => {
      diagnostics += chunk.toString().slice(0, 4096 - diagnostics.length);
    });
    child.once("error", (error) => { clearTimeout(timer); clearInterval(monitor); reject(error); });
    child.once("close", (code, signal) => {
      closed = true;
      clearTimeout(timer);
      clearInterval(monitor);
      terminate();
      if (monitorFailed) reject(new DiagramRenderError("Diagram resource monitoring failed.", 503));
      else if (memoryExceeded) reject(new DiagramRenderError("Diagram rendering exceeded the memory limit."));
      else if (timedOut) reject(new DiagramRenderError("Diagram rendering exceeded the 15-second limit.", 504));
      else if (code !== 0) {
        console.error("Isolated Asymptote rendering failed:", code, signal, diagnostics.replaceAll(directory, "<temporary>"));
        reject(new DiagramRenderError("The embedded diagram could not be compiled safely."));
      } else resolve();
    });
  });
}

export async function renderAsymptote(source) {
  validateAsymptote(source);
  if (process.platform !== "darwin") {
    throw new DiagramRenderError("Isolated Asymptote rendering is not configured on this server.", 503);
  }
  if (active >= 2) throw new DiagramRenderError("Diagram renderer is busy. Please retry shortly.", 429);
  active += 1;
  let directory;
  try {
    const executable = await realpath(/* turbopackIgnore: true */ process.env.MATHBANK_ASYMPTOTE_PATH || "/Library/TeX/texbin/asy");
    directory = await realpath(await mkdtemp(path.join(tmpdir(), "mathbank-asy-")));
    await writeFile(path.join(directory, "source.asy"), source, { mode: 0o600 });
    await writeFile(path.join(directory, "sandbox.sb"), sandboxProfile(directory), { mode: 0o600 });
    await compile(directory, executable);
    const output = path.join(directory, "diagram.png");
    const metadata = await stat(output);
    if (!metadata.isFile() || metadata.size > 2 * 1024 * 1024) {
      throw new DiagramRenderError("The rendered diagram exceeds the image size limit.");
    }
    const bytes = await readFile(output);
    if (!bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) {
      throw new DiagramRenderError("The renderer did not produce a valid PNG.");
    }
    return bytes;
  } catch (error) {
    if (error instanceof DiagramRenderError) throw error;
    console.error("Asymptote renderer unavailable:", error.code || error.name);
    throw new DiagramRenderError("The isolated diagram renderer is unavailable.", 503);
  } finally {
    if (directory) await rm(directory, { recursive: true, force: true });
    active -= 1;
  }
}
