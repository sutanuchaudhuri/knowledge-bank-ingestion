# 08 — Cohort Clustering and Admin Analytics

## 1. Goal

Help admins/instructors identify:
- common weakness patterns
- pacing profiles
- misconception clusters
- course/drop-off patterns
- subgroups needing different interventions

This is a decision-support tool, not permanent student labeling.

## 2. Feature groups for clustering

Use normalized features such as:
- mastery by broad domain
- transfer gap
- hint dependency
- speed by difficulty band
- skip/revisit style
- careless-error proxies
- persistence after failure
- misconception-family prevalence
- course completion behavior
- uncertainty / data sparsity

Avoid:
- raw personally identifying fields
- protected/sensitive demographic attributes
- arbitrary embedding clusters without interpretability

## 3. Candidate methods

Start:
- PCA for visualization only
- KMeans with stability checks
- HDBSCAN for irregular clusters / noise

Consider later:
- mixture models
- sequence clustering
- representation learning

## 4. Cluster validation

Do not accept clusters because they look interesting.

Require:
- stability across bootstrap samples
- interpretable feature differences
- sufficient cluster size
- consistency across adjacent time windows
- actionability

## 5. Example cluster profiles

### Cluster A — knowledge-strong, pacing-poor

```text
high mastery
high transfer
slow Q15–22
few skips
high late-section unanswered rate
```

Recommended admin action:
- pacing mini-course
- timed section practice
- first-pass cap strategy

### Cluster B — fast but brittle

```text
high speed
medium accuracy
low review
high answer-change regret
```

Action:
- verification/checking strategy
- slower high-value items

### Cluster C — scaffold-dependent

```text
ordinary practice accuracy high
no-hint transfer low
high hints per success
```

Action:
- fade scaffolds
- transfer sets
- delayed retest

## 6. Cohort trend

Clusters may change over time.

Store assignments as:

```text
student_id
cluster_model_version
as_of_time
cluster_id
membership_probability
```

Do not store a permanent human-readable identity label on the student profile.

## 7. Admin questions

Dashboard should answer:

```text
Which techniques produce most time loss?
Which misconceptions are growing?
Which course states have high abandonment?
Which routes reduce errors?
Which interventions improve transfer?
Which group needs matrix prerequisites?
Which students are under-challenged?
Which students are over-challenged?
```

## 8. Intervention effectiveness

For each intervention/course/route:
- pre/post matched performance
- transfer performance
- time efficiency
- effect persistence
- confidence interval
- sample size

Avoid causal language unless design supports it.
Use:
"associated with a 12-point improvement"
not
"caused a 12-point improvement"
for observational data.
