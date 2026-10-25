# MathBank Socratic Studio v3 — Admin rules + live student simulation

Open `index.html` in a modern browser (no server or installation required).

## Workflow demo
1. Open **Rules by topic** to see the plain-language explanations next to their actual source/outcome/destination rule fields.
2. Type "If the student gets the Assertion–Reason quiz wrong, send them to the Bijections mini-lesson". Select **Interpret rule**, verify the parsed fields, then **Accept into draft**. This prototype uses an offline phrase parser; it is **not** a real Bedrock integration.
3. Open **Designer + Simulator**. Click a node on the workflow map: the corresponding student screen appears on the right.
4. At the Assertion–Reason quiz, submit an incorrect answer to highlight the branch into Bijections; complete that activity, take the simpler quiz, then observe success/failure branching.
5. Modify a rule in the left editor, restart the student session and test the changed path.

## Intended production integration
- Source resource IDs come from reviewed MathBank quiz, lesson and topic releases, not the demo catalog.
- The human-readable rule is a maintained annotation; the typed transition is the executable authority.
- Bedrock generates JSON patches, not direct database writes. Display diff, check resource existence, policy and mathematical review, then require explicit admin acceptance.
- Step Functions executes bounded routing transitions. MathBank REST owns evaluation, learner identity and state. AI cannot override hard eligibility policy.
- Use student impersonation only as a synthetic preview. Real student logins are separate and authorization-scoped.
- Add priority, mutually exclusive guards, explicit fallback, cycle limits, version conflicts, immutable releases and audit log before production.

This is a front-end demonstration only; the offline quiz checks are not a secure grading system. Changes are stored in localStorage on this browser.
