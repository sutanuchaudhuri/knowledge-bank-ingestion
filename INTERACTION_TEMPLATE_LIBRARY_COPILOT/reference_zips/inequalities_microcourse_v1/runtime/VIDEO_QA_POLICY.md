# Video Q&A Policy

A learner may use "Ask about this moment" only when:
- video.review_status = APPROVED
- transcript.status = APPROVED
- the active transcript segment is APPROVED
- student_questioning_enabled = true

Given release_id, state_id, video_asset_id and current_time_ms:
resolve the unique segment satisfying start_ms <= current_time_ms < end_ms.

Load only:
- exact approved transcript segment,
- its Concept / Technique / Skill / Misconception bindings,
- approved Q&A context,
- fixed interventions allowed from the current state.

The agent may explain, rephrase, clarify notation, invoke an approved prerequisite,
or start a fixed intervention.

The agent may NOT infer what the video said from companion notes.
If no approved transcript is available, return VIDEO_TRANSCRIPT_NOT_APPROVED
and keep "Ask about this moment" disabled.

If an intervention begins while video is paused, persist the exact state and timestamp.
After intervention completion, restore the exact state and timestamp and do not auto-advance.
