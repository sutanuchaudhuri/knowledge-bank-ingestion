"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "./ui.jsx";

/** Pill tabs for section sub-navigation. `exact` items only match their own path. */
export default function NavTabs({ items, label, className = "" }) {
  const pathname = usePathname() || "/";
  const active = items
    .filter(({ href, exact }) => pathname === href || (!exact && pathname.startsWith(`${href}/`)))
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;
  return (
    <nav className={`mb-tabs ${className}`} aria-label={label}>
      {items.map(({ href, label: text, icon }) => (
        <Link key={href} href={href} className={`mb-tab${href === active ? " active" : ""}`} aria-current={href === active ? "page" : undefined}>
          {icon && <Icon name={icon} />}{text}
        </Link>
      ))}
    </nav>
  );
}
