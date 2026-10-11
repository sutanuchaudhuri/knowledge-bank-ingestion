(() => {
  "use strict";
  const obstacle = document.getElementById("obstacle");
  const attempt = document.getElementById("learning-attempt");
  const start = document.getElementById("start-learning");
  const next = document.getElementById("next-hint");
  const lesson = document.getElementById("micro-lesson");
  const feedback = document.getElementById("learning-feedback");
  let hint = 0;
  const prompts = {
    concept: [
      "What does it mean for two cases to be disjoint?",
      "Try classifying a few small examples. Can any example appear in two cases?",
      "State what belongs to each case, then explain why every possibility belongs to exactly one."
    ],
    strategy: [
      "Which feature could separate the possibilities into non-overlapping groups?",
      "Use a smaller instance to test your grouping before counting the full set.",
      "List the groups, check for omissions and overlaps, and only then decide how to combine their counts."
    ],
    execution: [
      "Write down the rule for one of your cases before calculating its size.",
      "Apply that rule to a small example. Does it admit exactly the objects you intended?",
      "Check each case with the same procedure; revise the rule if it includes an object twice."
    ],
    calculation: [
      "Which single intermediate count can you check independently?",
      "Compare that count with direct enumeration on a smaller instance.",
      "Recompute only the disputed count, recording each operation, before returning to the overall sum."
    ],
    connection: [
      "How does your choice of cases connect to the rule you use to combine their counts?",
      "Explain when the addition rule applies and when independent choices would use multiplication.",
      "Match each counting operation to its justification, then check that the case partition supports it."
    ]
  };
  const reset = () => {
    hint = 0;
    next.disabled = true;
    lesson.disabled = true;
    next.textContent = "Request hint 1";
    feedback.textContent = "Share an attempt or describe the obstacle first. This illustration does not grade your work.";
  };
  start.addEventListener("click", () => {
    reset();
    if (!attempt.value.trim()) {
      feedback.textContent = "Please describe what you tried or where you are stuck before requesting a hint.";
      attempt.focus();
      return;
    }
    next.disabled = false;
    lesson.disabled = false;
    feedback.textContent = `Attempt shared for the ${obstacle.value} obstacle (illustration only). Try again, request hint 1, or take a micro-lesson.`;
  });
  next.addEventListener("click", () => {
    if (hint >= 3 || next.disabled) return;
    hint += 1;
    feedback.textContent = `Generated illustration · PENDING · Hint ${hint}/3: ${prompts[obstacle.value][hint - 1]} Pause and try this on your original attempt.`;
    next.disabled = hint === 3;
    next.textContent = hint === 3 ? "Three hints used — try again" : `Request hint ${hint + 1}`;
  });
  lesson.addEventListener("click", () => {
    feedback.textContent = "Generated illustration · PENDING · Micro-lesson: A partition splits a collection into groups with no overlap and no omissions. Practise with a small collection: assign each object to exactly one group and justify your rule. Return prompt: How would you revise the cases in your original attempt to meet those two conditions? This draft is not reviewed corpus evidence.";
  });
  obstacle.addEventListener("change", reset);
  attempt.addEventListener("input", reset);
  document.getElementById("reset-learning").addEventListener("click", () => {
    attempt.value = "";
    obstacle.value = "strategy";
    reset();
  });
})();
