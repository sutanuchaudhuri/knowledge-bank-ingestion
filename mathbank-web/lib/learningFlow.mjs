export const DIAGNOSES = [
  { id: "concept", label: "Recognizing the concept", question: "What quantities or relationships do you recognize in the problem?" },
  { id: "strategy", label: "Choosing a strategy", question: "Which approach have you tried, and where did it stop helping?" },
  { id: "execution", label: "Carrying out a method", question: "Which operation or step are you unable to carry out?" },
  { id: "calculation", label: "Checking a calculation", question: "What calculation did you make, and what result seems inconsistent?" },
  { id: "connection", label: "Connecting the steps", question: "What have you established so far, and what do you need to establish next?" },
];

export function hintRequestState(attempt, previousAttempt, hintLevel) {
  if (!attempt.trim()) return { allowed: false, reason: "Describe what you have tried before requesting a hint." };
  if (attempt.trim().length > 4000) return { allowed: false, reason: "Keep each step under 4,000 characters before requesting coaching." };
  if (hintLevel >= 3) return { allowed: false, reason: "You have reached the final guided hint. Return to the problem and try the approach." };
  if (hintLevel > 0 && attempt.trim() === previousAttempt.trim()) {
    return { allowed: false, reason: "Update your attempt after trying the last hint before requesting more help." };
  }
  return { allowed: true, nextLevel: hintLevel + 1 };
}
