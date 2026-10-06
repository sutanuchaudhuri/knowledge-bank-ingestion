import test from "node:test";
import assert from "node:assert/strict";
import { parseWidgetBlock, widgetSourceFromPre } from "../lib/widgetBlocks.mjs";

test("whitelisted specs render; envelope {spec} accepted", () => {
  const spec = { widget_type: "FORMULA_CARD", config: { latex: "a^2+b^2=c^2" } };
  assert.deepEqual(parseWidgetBlock(JSON.stringify(spec)), { spec });
  assert.deepEqual(parseWidgetBlock(JSON.stringify({ spec, validation: { valid: true } })), { spec });
});

test("unknown types, arrays and bad config are refused; partial JSON is pending", () => {
  assert.equal(parseWidgetBlock('{"widget_type":"IFRAME","config":{}}'), null);
  assert.equal(parseWidgetBlock("[1,2]"), null);
  assert.equal(parseWidgetBlock('{"widget_type":"TABLE","config":[]}'), null);
  assert.deepEqual(parseWidgetBlock('{"widget_type":"TAB'), { pending: true });
  assert.equal(parseWidgetBlock("x".repeat(20001)), null);
});

test("only language-widget code blocks are intercepted", () => {
  const pre = (cls) => ({ children: [{ type: "element", tagName: "code", properties: { className: [cls] }, children: [{ type: "text", value: "{}" }] }] });
  assert.equal(widgetSourceFromPre(pre("language-widget")), "{}");
  assert.equal(widgetSourceFromPre(pre("language-js")), null);
  assert.equal(widgetSourceFromPre({}), null);
});
