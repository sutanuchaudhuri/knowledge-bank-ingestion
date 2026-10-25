import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MathText } from "../src/ui";
import { normalizeMathText } from "../../mathbank-exam-web/src/components/mathText.js";

describe("shared MathText renderer (not a fork)", () => {
  it("repairs control-character damaged TeX using the shared normalizer", () => {
    expect(normalizeMathText("\f" + "rac{1}{2}")).toBe("\\frac{1}{2}");
    expect(normalizeMathText("\t" + "ext{count}")).toBe("\\text{count}");
    const { container } = render(<MathText text={"Compare \\(" + "\f" + "rac{1}{2}\\) and \\[x^2\\]."} />);
    expect(container.querySelector(".mb-math-inline .katex")).not.toBeNull();
    expect(container.querySelector(".mb-math-display .katex")).not.toBeNull();
  });
  it("degrades malformed math without crashing", () => {
    const { container } = render(<MathText text={"\\(\\unknowncommand{x}\\)"} />);
    expect(container.textContent).not.toBe("");
  });
});
