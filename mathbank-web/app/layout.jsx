import "katex/dist/katex.min.css";
import "./globals.css";

export const metadata = {
  title: "MathBank Tutor",
  description: "Chat with the MathBank competition-math tutor agent.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body style={{ margin: 0 }}>{children}</body>
    </html>
  );
}
