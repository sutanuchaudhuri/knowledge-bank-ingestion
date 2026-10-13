import assert from "node:assert/strict";
import test from "node:test";
import { runtimeJson } from "../lib/attemptMedia.mjs";

test("private runtime requests preserve the payload and forward upload cancellation", async (context) => {
  const controller = new AbortController();
  const fetch = context.mock.method(globalThis, "fetch", async () => Response.json({ submission_id: "fixture" }));
  assert.deepEqual(await runtimeJson("/private", "POST", { problem_ref: "FIXTURE" }, controller.signal), { submission_id: "fixture" });
  const [url, options] = fetch.mock.calls[0].arguments;
  assert.equal(url, "/private");
  assert.equal(options.signal, controller.signal);
  assert.equal(options.method, "POST");
  assert.deepEqual(JSON.parse(options.body), { problem_ref: "FIXTURE" });
});

test("existing runtime GET callers do not require a signal or body", async (context) => {
  const fetch = context.mock.method(globalThis, "fetch", async () => Response.json({ status: "saved" }));
  assert.deepEqual(await runtimeJson("/private"), { status: "saved" });
  const options = fetch.mock.calls[0].arguments[1];
  assert.equal(options.method, "GET");
  assert.equal(options.body, undefined);
  assert.equal(options.signal, undefined);
});

test("private runtime authorization failures remain visible", async (context) => {
  context.mock.method(globalThis, "fetch", async () => Response.json({ detail: "Sign in required" }, { status: 401 }));
  await assert.rejects(runtimeJson("/private"), { message: "Sign in required", status: 401 });
});

test("cancelled uploads propagate abort instead of returning a success-shaped value", async (context) => {
  const controller = new AbortController();
  controller.abort();
  context.mock.method(globalThis, "fetch", async (url, options) => options.signal.throwIfAborted());
  await assert.rejects(runtimeJson("/private", "POST", {}, controller.signal), { name: "AbortError" });
});
