export const metadata = {
  title: "MathBank ML Ops",
  description: "IntelliTutor ML/RL platform operations dashboard (requirements/54, 56).",
};

const NAV_ITEMS = [
  ["/", "Overview"],
  ["/model-registry", "Model registry"],
  ["/training-runs", "Training runs"],
  ["/cohorts", "Cohorts"],
  ["/tutor-policy", "Tutor policy"],
  ["/data-readiness", "Data readiness"],
];

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: 0, display: "flex" }}>
        <nav style={{ width: "220px", padding: "1rem", borderRight: "1px solid #e5e5e5", flexShrink: 0 }}>
          <strong>MathBank ML Ops</strong>
          <ul style={{ listStyle: "none", padding: 0, marginTop: "1rem" }}>
            {NAV_ITEMS.map(([href, label]) => (
              <li key={href} style={{ marginBottom: ".5rem" }}>
                <a href={href} style={{ color: "#333", textDecoration: "none" }}>{label}</a>
              </li>
            ))}
          </ul>
        </nav>
        <main style={{ padding: "2rem", flexGrow: 1, maxWidth: "960px" }}>{children}</main>
      </body>
    </html>
  );
}
