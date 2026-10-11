\ir _session.sql

-- Q196 Daily evaluated/unassessed answer outcomes.
-- Purpose/output: UTC-day counts, accuracy among assessed answers only; NULL is_correct is not failure (021).
-- Inputs: days, cohort (minimum 10 enforced). Risk: READ ONLY; sensitive aggregate, small cohorts suppressed.
SELECT date_trunc('day',attempted_at) AS day,count(*) AS submissions,count(DISTINCT student_id) AS learners,
 count(*) FILTER(WHERE is_correct IS NULL) AS unassessed,
 avg(is_correct::int) FILTER(WHERE is_correct IS NOT NULL) AS assessed_accuracy
FROM learner.attempt WHERE attempted_at>=now()-make_interval(days => :'days'::int)
GROUP BY 1 HAVING count(DISTINCT student_id)>=greatest(10,:'cohort'::int) ORDER BY day;
-- END Q196

-- Q197 Competition practice breadth and outcomes.
-- Purpose/output: contest aggregates with participant count, distinct problems and assessed accuracy.
-- Inputs: days, cohort. Risk: READ ONLY; suppressed below 10 learners; no identities or submitted answers.
SELECT c.external_code,count(DISTINCT a.student_id) AS learners,count(DISTINCT a.problem_id) AS practiced_problems,
 count(*) AS submissions,avg(a.is_correct::int) AS assessed_accuracy
FROM learner.attempt a JOIN core.problem q USING(problem_id) JOIN core.paper p USING(paper_id)
JOIN core.competition_edition e USING(edition_id) JOIN core.competition c USING(competition_id)
WHERE a.attempted_at>=now()-make_interval(days => :'days'::int)
GROUP BY c.external_code HAVING count(DISTINCT a.student_id)>=greatest(10,:'cohort'::int) ORDER BY c.external_code;
-- END Q197

-- Q198 Solve-session lifecycle funnel.
-- Purpose/output: recent started-session counts by status, median completed duration.
-- Inputs: days, cohort. Risk: READ ONLY; group suppression; no session/student IDs.
SELECT status,count(*) AS sessions,count(DISTINCT student_id) AS learners,
 percentile_cont(0.5) WITHIN GROUP(ORDER BY extract(epoch FROM completed_at-started_at))
 FILTER(WHERE completed_at>=started_at) AS median_completed_seconds
FROM learner.solve_attempt WHERE started_at>=now()-make_interval(days => :'days'::int)
GROUP BY status HAVING count(DISTINCT student_id)>=greatest(10,:'cohort'::int) ORDER BY status;
-- END Q198

-- Q199 Independent versus assisted step outcomes.
-- Purpose/output: step-state/help buckets, independent success counts and population sizes.
-- Inputs: days, cohort. Risk: READ ONLY; suppressed aggregate; private responses/evidence excluded.
SELECT s.state,s.help_level_used,count(*) AS step_states,count(DISTINCT a.student_id) AS learners,
 count(*) FILTER(WHERE s.independent_success) AS independent_successes
FROM learner.attempt_step_state s JOIN learner.solve_attempt a USING(solve_attempt_id)
WHERE s.last_updated_at>=now()-make_interval(days => :'days'::int)
GROUP BY s.state,s.help_level_used HAVING count(DISTINCT a.student_id)>=greatest(10,:'cohort'::int)
ORDER BY s.state,s.help_level_used;
-- END Q199

-- Q200 Concept mastery population bands.
-- Purpose/output: concept-level mean mastery and attempted populations; not individual recommendations.
-- Inputs: cohort. Risk: READ ONLY; sensitive cache aggregate with minimum 10 participants.
SELECT c.slug,count(DISTINCT m.student_id) AS learners,avg(m.mastery_score) AS mean_mastery,
 sum(m.attempts_count) AS cached_attempts,sum(m.correct_count) AS cached_correct
FROM learner.concept_mastery m JOIN knowledge.concept c USING(concept_id)
GROUP BY c.slug HAVING count(DISTINCT m.student_id)>=greatest(10,:'cohort'::int) ORDER BY c.slug;
-- END Q200

-- Q201 Daily analytics rollup completeness.
-- Purpose/output: day totals for starts/completions/steps/gaps/recovery, one row per qualifying day.
-- Inputs: days, cohort. Risk: READ ONLY; minimum cohort, no per-student rows.
SELECT activity_date,count(*) AS learners,sum(attempts_started) AS starts,sum(attempts_completed) AS completions,
 sum(steps_evaluated) AS steps,sum(gaps_diagnosed) AS diagnoses,sum(recovery_plans_completed) AS recovery_completions
FROM analytics.learner_daily_activity WHERE activity_date>=current_date-:'days'::int
GROUP BY activity_date HAVING count(DISTINCT student_id)>=greatest(10,:'cohort'::int) ORDER BY activity_date;
-- END Q201

-- Q202 Gap diagnosis intervention mix.
-- Purpose/output: trigger/action counts; evidence, probes and learner target labels excluded.
-- Inputs: days, cohort. Risk: READ ONLY; sensitive aggregate suppressed below cohort minimum.
SELECT trigger,recommended_action,count(*) AS diagnoses,count(DISTINCT student_id) AS learners
FROM pedagogy.gap_diagnosis WHERE created_at>=now()-make_interval(days => :'days'::int)
GROUP BY trigger,recommended_action HAVING count(DISTINCT student_id)>=greatest(10,:'cohort'::int)
ORDER BY trigger,recommended_action;
-- END Q202

-- Q203 Knowledge-gap confirmation rates by failure location.
-- Purpose/output: location/status counts and mean confidence; no target IDs, labels or evidence.
-- Inputs: days, cohort. Risk: READ ONLY; sensitive aggregate with minimum cohort.
SELECT failure_location,status,count(*) AS hypotheses,count(DISTINCT student_id) AS learners,avg(confidence) AS mean_confidence
FROM pedagogy.knowledge_gap WHERE created_at>=now()-make_interval(days => :'days'::int)
GROUP BY failure_location,status HAVING count(DISTINCT student_id)>=greatest(10,:'cohort'::int)
ORDER BY failure_location,status;
-- END Q203

-- Q204 Recovery plan outcomes and branching.
-- Purpose/output: state/trigger counts and fraction that are child plans; no outcome JSON.
-- Inputs: days, cohort. Risk: READ ONLY; sensitive aggregate, small groups suppressed.
SELECT status,trigger,count(*) AS plans,count(DISTINCT student_id) AS learners,
 count(*) FILTER(WHERE parent_recovery_plan_id IS NOT NULL) AS branch_plans
FROM pedagogy.recovery_plan WHERE created_at>=now()-make_interval(days => :'days'::int)
GROUP BY status,trigger HAVING count(DISTINCT student_id)>=greatest(10,:'cohort'::int) ORDER BY status,trigger;
-- END Q204

-- Q205 Feedback triage/error evidence distribution.
-- Purpose/output: status/verdict/error-kind counts, mean review delay and distinct reporters.
-- Inputs: days, cohort. Risk: READ ONLY; reason, review_note, topic, audit_snapshot and IDs excluded.
SELECT status,retrieval_verdict,error_kind,count(*) AS reports,count(DISTINCT student_id) AS reporters,
 avg(reviewed_at-created_at) AS mean_review_delay
FROM learner.pedagogy_feedback WHERE created_at>=now()-make_interval(days => :'days'::int)
GROUP BY status,retrieval_verdict,error_kind HAVING count(DISTINCT student_id)>=greatest(10,:'cohort'::int)
ORDER BY status,retrieval_verdict,error_kind;
-- END Q205

-- Q206 Pending feedback age bands.
-- Purpose/output: pending report backlog in <1 day / 1–7 days / older buckets.
-- Inputs: cohort. Risk: READ ONLY; aggregate with minimum 10 distinct reporters, no text/IDs.
SELECT CASE WHEN created_at>=now()-interval '1 day' THEN 'under_1_day'
 WHEN created_at>=now()-interval '7 days' THEN '1_to_7_days' ELSE 'over_7_days' END AS age_band,
 count(*) AS reports,count(DISTINCT student_id) AS reporters
FROM learner.pedagogy_feedback WHERE status='PENDING' GROUP BY 1
HAVING count(DISTINCT student_id)>=greatest(10,:'cohort'::int) ORDER BY age_band;
-- END Q206

-- Q207 Multimodal submission processing funnel.
-- Purpose/output: state counts and median current submission age, not raw media/transcripts.
-- Inputs: days, cohort. Risk: READ ONLY; suppressed sensitive aggregate.
SELECT status,count(*) AS submissions,count(DISTINCT student_id) AS learners,
 percentile_cont(0.5) WITHIN GROUP(ORDER BY extract(epoch FROM now()-created_at)) AS median_age_seconds
FROM attempt_media.submission WHERE created_at>=now()-make_interval(days => :'days'::int)
GROUP BY status HAVING count(DISTINCT student_id)>=greatest(10,:'cohort'::int) ORDER BY status;
-- END Q207

-- Q208 Private media retention/storage budget.
-- Purpose/output: role/type/retention totals, bytes and purged asset count; excludes keys, hashes and IDs.
-- Inputs: cohort. Risk: READ ONLY; metadata aggregates, minimum 10 owners per group; no object-store calls.
SELECT a.role,a.asset_type,a.retention_class,count(*) AS assets,count(DISTINCT s.student_id) AS owners,
 sum(a.size_bytes) AS recorded_bytes,count(*) FILTER(WHERE a.purged_at IS NOT NULL) AS purged
FROM attempt_media.media_asset a JOIN attempt_media.submission s USING(submission_id)
GROUP BY a.role,a.asset_type,a.retention_class
HAVING count(DISTINCT s.student_id)>=greatest(10,:'cohort'::int) ORDER BY a.role,a.asset_type,a.retention_class;
-- END Q208

-- Q209 Assessed approved media-step alignment quality.
-- Purpose/output: latest assessment per step, grouped by correctness/alignment and assessor class.
-- Inputs: days, cohort. Risk: READ ONLY; suppressed aggregate; no actor IDs, why, evidence or response text.
WITH latest AS (
 SELECT DISTINCT ON(a.submission_id,a.transcription_version,a.step_id)
 a.submission_id,a.correctness,a.alignment_type,a.source,a.confidence
 FROM attempt_media.step_assessment a
 WHERE a.created_at>=now()-make_interval(days => :'days'::int)
 ORDER BY a.submission_id,a.transcription_version,a.step_id,a.assessment_version DESC
)
SELECT a.correctness,a.alignment_type,a.source,count(*) AS steps,count(DISTINCT s.student_id) AS learners,
 avg(a.confidence) AS mean_confidence FROM latest a JOIN attempt_media.submission s USING(submission_id)
GROUP BY a.correctness,a.alignment_type,a.source
HAVING count(DISTINCT s.student_id)>=greatest(10,:'cohort'::int) ORDER BY a.correctness,a.alignment_type,a.source;
-- END Q209

-- Q210 Learner event ingestion by actor/event type.
-- Purpose/output: recent event counts and population size, avoiding payload/idempotency/agent-session data.
-- Inputs: days, cohort. Risk: READ ONLY; sensitive aggregate, minimum cohort enforced.
SELECT event_type,actor_type,count(*) AS events,count(DISTINCT student_id) AS learners
FROM learner.event WHERE event_time>=now()-make_interval(days => :'days'::int)
GROUP BY event_type,actor_type HAVING count(DISTINCT student_id)>=greatest(10,:'cohort'::int)
ORDER BY event_type,actor_type;
-- END Q210

ROLLBACK;
