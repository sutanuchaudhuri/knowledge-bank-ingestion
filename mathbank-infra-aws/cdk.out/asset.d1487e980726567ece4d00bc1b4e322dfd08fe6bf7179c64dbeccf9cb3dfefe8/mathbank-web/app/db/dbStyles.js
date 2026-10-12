// Shared Bootstrap classes for corpus, profile, and administration screens.
export const panel = "card shadow-sm p-3 p-lg-4";

export const masterDetail = "app-master-detail";

export const table = "table table-hover align-middle mb-0";

export const th = { fontWeight: 600 };

export const td = { verticalAlign: "middle" };

export function rowStyle(selected) {
  return { cursor: "pointer", "--bs-table-bg": selected ? "var(--bs-primary-bg-subtle)" : "transparent" };
}

export const input = "form-control";

export const button = "btn btn-outline-secondary";

export const primaryButton = "btn btn-primary";
