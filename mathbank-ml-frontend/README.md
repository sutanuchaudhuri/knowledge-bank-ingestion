# mathbank-ml-frontend

The **separate** ML-ops/admin-analyst dashboard requested alongside `mathbank-ml-training`
and `mathbank-ml-inference` — see
[documentation/requirements/54_ML_RL_PLATFORM_ARCHITECTURE_AND_SCAFFOLDING.md](../documentation/requirements/54_ML_RL_PLATFORM_ARCHITECTURE_AND_SCAFFOLDING.md) §1
for why this is a *different* audience from `mathbank-web`'s students/course-admins:
this app is for whoever monitors models, training runs, cohort clusters, and the
tutor-policy, not for students or day-to-day course content admins.

**Status: scaffolded, not implemented, not tested.** Every page renders a shell
(heading, short description, a fetch call to `mathbank-ml-inference` through the same-
origin proxy) with `// TODO` placeholder content where a real table/chart will go.

## Pages

| Route | Backs | Status |
|---|---|---|
| `/` | Landing — links to the pages below | ✅ built (static links only) |
| `/model-registry` | `GET /v1/admin/ml/model-registry` | 🟡 fetch wiring only |
| `/training-runs` | `GET /v1/admin/ml/training-runs` | 🟡 fetch wiring only |
| `/cohorts` | `GET /v1/admin/ml/cohorts/clusters` | 🟡 fetch wiring only |
| `/tutor-policy` | `GET /v1/admin/ml/tutor-policy` | 🟡 fetch wiring only |
| `/data-readiness` | `GET /v1/admin/ml/data-readiness` | 🟡 fetch wiring only |

Every page currently renders the service's structured `501 MLUnavailable` body (todo_ref +
design_doc_ref) as its "content," proving the fetch wiring reaches `mathbank-ml-inference`
end to end — once that service's endpoints are implemented, these pages start rendering
real data with **no page-level code change**, only the eventual table/chart markup swap.

## What this app intentionally does NOT do

- It does not copy `mathbank-web`'s full design-system (`ui.jsx`, tokens, `AppShell`) —
  `_components/ui.jsx` here is a tiny, independent, unstyled-by-design subset. This is a
  deliberately different, simpler, internal tool, not a second storefront for the same
  design language.
- It has no auth wired up yet (`# TODO` in `api/ml/[...path]/route.js`) — do not deploy
  this publicly before that exists.
- It does not render the **student-facing** ML wireframes (learning profile, exam
  strategy) — those integrate into the existing `mathbank-web` app instead (doc 54 §5).

## Getting started

```bash
npm install
cp .env.example .env.local   # set ML_INFERENCE_BASE_URL
npm run dev                   # http://localhost:5175
```
