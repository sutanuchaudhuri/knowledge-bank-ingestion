import type { Workflow } from "../src/contracts";

// Public prompts only: fixture grading stays in intercepted test responses, not in the application.
export const prototypeWorkflow: Workflow = {
  workflow_id: "reference-workflow", title: "Stars and Bars · Discovery journey", domain: "Combinatorics",
  content_hash: "reference-test-hash", revision: 1, prototype_only: true,
  program: {
    schema_version: "socratic.prototype.v1", strategy_code: "COMB_STARS_BARS_BASIC",
    source: { problem_code: null, solution_id: null, route_release_id: null },
    entry: "begin", fallback_key: "lesson", max_transitions: 20,
    nodes: [
      { key: "begin", label: "Begin discovery", type: "START", topic: "Stars and Bars", prompt: "Explore the representation before generalizing." },
      { key: "start", label: "Discover the representation", type: "DISCOVERY", topic: "Stars and Bars", prompt: "Five identical objects are distributed among three labeled boxes. Why might two separators describe every distribution?" },
      { key: "quiz", label: "Stars and Bars · Assertion–Reason", type: "QUIZ", topic: "Stars and Bars", activity_ref: "approved-ar", prompt: "Assertion: The number of nonnegative solutions of \\(x+y+z=5\\) is 21. Reason: Each solution corresponds uniquely to an arrangement of five stars and two separators." },
      { key: "lesson", label: "Bijections mini-lesson", type: "LESSON", topic: "Bijections", prompt: "Write each distribution as a string of five stars and two bars. Why can no two different distributions produce the same string?" },
      { key: "easy", label: "Small counting checkpoint", type: "QUIZ", topic: "Counting", prompt: "How many pairs of nonnegative integers \\((x,y)\\) satisfy \\(x+y=3\\)?" },
      { key: "topic", label: "Counting Foundations", type: "TOPIC", topic: "Counting", prompt: "Explore the solutions to \\(a+b=2\\). Try listing all possibilities in an orderly way." },
      { key: "finish", label: "Generalize the principle", type: "TRANSFER", topic: "Stars and Bars", prompt: "Write a formula for the number of nonnegative integer solutions to \\(x_1+\\cdots+x_k=n\\). Explain why it works." },
      { key: "pie", label: "Introduction to Inclusion–Exclusion", type: "LESSON", topic: "Inclusion–Exclusion", prompt: "When upper bounds are placed on the boxes, which cases must be excluded from the unrestricted count?" },
      { key: "geometry", label: "Loci and geometric constraints", type: "TOPIC", topic: "Geometry / Loci", prompt: "Where are all points equidistant from two fixed points?" },
      { key: "done", label: "Preview complete", type: "COMPLETE", topic: "Stars and Bars", prompt: "Reflect on the representation and its limits." },
    ],
    edges: [
      { from_key: "begin", outcome: "ALWAYS", to_key: "start", priority: 10, annotation: "Begin with the concrete representation." },
      { from_key: "start", outcome: "ALWAYS", to_key: "quiz", priority: 10, annotation: "After exploring the representation, move to the Assertion–Reason quiz." },
      { from_key: "quiz", outcome: "SUCCESS", to_key: "finish", priority: 10, annotation: "A valid assertion, reason and connection lead to generalization." },
      { from_key: "quiz", outcome: "RETRY", to_key: "lesson", priority: 10, annotation: "An unjustified counting relationship calls for a short bijection lesson." },
      { from_key: "lesson", outcome: "ALWAYS", to_key: "easy", priority: 10, annotation: "Check the explanation with a simpler counting question." },
      { from_key: "easy", outcome: "SUCCESS", to_key: "finish", priority: 10, annotation: "Return to generalization after the simpler checkpoint." },
      { from_key: "easy", outcome: "RETRY", to_key: "topic", priority: 10, annotation: "Revisit Counting Foundations before retrying." },
      { from_key: "topic", outcome: "ALWAYS", to_key: "easy", priority: 10, annotation: "Retry the checkpoint after foundational review." },
      { from_key: "finish", outcome: "SUCCESS", to_key: "done", priority: 10 },
    ],
  },
};
