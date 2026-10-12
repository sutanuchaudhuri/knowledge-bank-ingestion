import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap-icons/font/bootstrap-icons.min.css";
import "@fontsource-variable/inter";
import "katex/dist/katex.min.css";
import "./globals.css";
import AppShell from "./AppShell.jsx";
import SourcePane from "./_components/SourcePane.jsx";

export const metadata = {
  title: "MathBank Tutor",
  description: "Chat with the MathBank competition-math tutor agent.",
};

export const viewport = { themeColor: "#4f46e5" };

export default function RootLayout({ children }) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      {/* Grammar extensions inject body attributes before React hydrates. Keep this exception local. */}
      <body suppressHydrationWarning><SourcePane><AppShell>{children}</AppShell></SourcePane></body>
    </html>
  );
}
