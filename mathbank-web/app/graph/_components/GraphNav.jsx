"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "../graph.module.css";

export default function GraphNav({ items }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Graph views">
      <ul className={`nav nav-pills ${styles.nav}`}>
        {items.map(({ href, title }) => {
          const active = pathname === href;
          return (
            <li key={href} className="nav-item">
              <Link
                href={href}
                className={`nav-link ${styles.navLink} ${active ? `active ${styles.navLinkActive}` : ""}`}
                aria-current={active ? "page" : undefined}
              >
                {title}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
