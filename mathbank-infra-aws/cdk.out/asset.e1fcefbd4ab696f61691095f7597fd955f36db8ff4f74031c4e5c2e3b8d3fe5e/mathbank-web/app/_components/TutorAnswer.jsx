import { splitTutorProblem } from "../../lib/tutorProblem.mjs";
import MathText from "./MathText.jsx";
import { Icon } from "./ui.jsx";

export default function TutorAnswer({ children }) {
  const problem = splitTutorProblem(children);
  if (!problem) return <div className="mb-tutor-answer"><MathText>{children}</MathText></div>;
  return (
    <div className="mb-tutor-answer">
      {problem.intro && <MathText>{problem.intro}</MathText>}
      <section className="mb-tutor-problem" aria-label="Practice problem">
        <div className="mb-tutor-problem-title"><Icon name="file-earmark-text" />{problem.title}</div>
        <MathText>{problem.statement}</MathText>
      </section>
      <section className="mb-tutor-source" aria-label="Problem source">
        <span className="fw-semibold"><Icon name="book" />Source</span>
        <MathText>{problem.source}</MathText>
      </section>
      {problem.outro && <MathText>{problem.outro}</MathText>}
    </div>
  );
}
