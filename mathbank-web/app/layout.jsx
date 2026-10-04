import "bootstrap/dist/css/bootstrap.min.css";
import "katex/dist/katex.min.css";
import "./globals.css";
import AppShell from "./AppShell.jsx";

export const metadata = {
  title: "MathBank Tutor",
  description: "Chat with the MathBank competition-math tutor agent.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body style={{ margin: 0 }}><AppShell>{children}</AppShell></body>
    </html>
  );
}
