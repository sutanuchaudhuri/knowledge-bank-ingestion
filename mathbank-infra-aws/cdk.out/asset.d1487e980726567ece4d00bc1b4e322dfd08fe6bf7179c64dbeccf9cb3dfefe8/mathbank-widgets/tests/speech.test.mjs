import test from "node:test";
import assert from "node:assert/strict";
import { speakableText, mathToSpeech } from "../src/speech.mjs";

test("math is read naturally", () => {
  assert.equal(mathToSpeech("PA \\cdot PB = PT^2"), "P A times P B equals P T squared");
  assert.equal(mathToSpeech("\\angle ABC = 90^\\circ"), "angle A B C equals 90 degrees");
  assert.equal(mathToSpeech("\\frac{AB}{DE}"), "A B over D E");
  assert.equal(mathToSpeech("\\sqrt{2}"), "square root of 2");
});

test("markdown is stripped and long text is capped", () => {
  assert.equal(speakableText("**Hint:** use $PA \\cdot PB$."), "Hint: use P A times P B .");
  assert.equal(speakableText("![d](x.png) see [link](http://x)"), "see link");
  const long = speakableText("word ".repeat(1000));
  assert.ok(long.length <= 1202 && long.endsWith("…"));
});
