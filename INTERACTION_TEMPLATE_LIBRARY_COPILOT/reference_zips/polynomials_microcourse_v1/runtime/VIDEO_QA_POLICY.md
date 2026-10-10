# External Video Pause-and-Question Policy

A YouTube video may be shown as a curated resource before transcript approval,
but learner-time "Ask about this moment" MUST remain disabled.

Enable it only when:
- video resource is APPROVED;
- exact timestamped transcript is imported;
- transcript is human-reviewed and APPROVED;
- the active segment is mapped to canonical Concept / Technique / Skill / Misconception IDs;
- fixed intervention/quiz markers are authored where required.

When the learner pauses at t:
1. persist state + t;
2. resolve the unique approved transcript segment start_ms <= t < end_ms;
3. load only that segment plus approved adjacent/prerequisite context allowed by state policy;
4. answer conversationally without inventing what the speaker said;
5. if a known misconception matches, run only a pre-authored intervention;
6. return to the exact state/time.

If transcript is missing:
status=VIDEO_TRANSCRIPT_NOT_APPROVED
student_questioning_enabled=false.
