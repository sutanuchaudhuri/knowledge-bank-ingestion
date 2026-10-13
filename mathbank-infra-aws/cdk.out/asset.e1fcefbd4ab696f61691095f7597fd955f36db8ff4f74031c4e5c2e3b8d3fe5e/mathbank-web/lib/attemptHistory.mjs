export function attemptResult(correct) {
  if (correct == null) return { label: "Awaiting assessment", tone: "warning", icon: "hourglass-split" };
  return correct === true
    ? { label: "Correct", tone: "success", icon: "check-lg" }
    : { label: "Not yet", tone: "danger", icon: "x-lg" };
}

export function assessedAccuracy(attempts) {
  const assessed = attempts.filter((a) => typeof a.is_correct === "boolean");
  return assessed.length ? Math.round(assessed.filter((a) => a.is_correct === true).length / assessed.length * 100) : null;
}
