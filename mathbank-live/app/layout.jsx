import "bootstrap/dist/css/bootstrap.min.css";
import "katex/dist/katex.min.css";
import "./globals.css";
import Link from "next/link";

export const metadata = { title: "MathBank Live", description: "Realtime live geometry classroom" };

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <nav className="navbar navbar-expand bg-dark navbar-dark px-3 py-2">
          <Link className="navbar-brand fw-semibold" href="/">MathBank <span className="badge text-bg-danger align-middle">LIVE</span></Link>
          <div className="navbar-nav ms-auto small">
            <Link className="nav-link" href="/login">Sign in</Link>
          </div>
        </nav>
        <main className="container-fluid py-3 px-3 px-lg-4">{children}</main>
      </body>
    </html>
  );
}
