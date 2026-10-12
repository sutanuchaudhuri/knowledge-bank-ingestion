import { PageHeader } from "./_components/ui.jsx";

export default function OverviewPage() {
  return (
    <>
      <PageHeader
        title="IntelliTutor ML Ops"
        subtitle="Model registry, training runs, cohorts, tutor policy and data readiness — scaffolded (requirements/54 §3)."
      />
      <p>
        This is the ML-engineering-facing dashboard — a different audience from
        mathbank-web&apos;s students and course content admins (see requirements/54 §1).
        Pick a page from the sidebar. Every page currently proxies to
        <code> mathbank-ml-inference</code> and shows that service&apos;s structured
        &quot;not implemented yet&quot; response, proving the wiring works end to end.
      </p>
      {/* TODO: once mathbank-ml-inference's endpoints have real logic, this overview page
          could grow a few top-line StatCard-equivalents (e.g. "3 models in production",
          "last training run: 2h ago") — not built in this pass. */}
    </>
  );
}
