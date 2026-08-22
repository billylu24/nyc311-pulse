"use client";

/* eslint-disable @next/next/no-html-link-for-pages -- vinext's hosted client router currently throws during internal Link navigation. */

import { Menu, X } from "lucide-react";
import { usePathname } from "next/navigation";
import { useState } from "react";

const links = [{ href: "/", label: "Research queue" }, { href: "/explore", label: "Explore" }, { href: "/evaluation", label: "Evaluation" }, { href: "/methodology", label: "Methodology" }];

export function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  return <header className="topbar">
    <a className="brand" href="/" aria-label="NYC311 Pulse home"><span className="brand-mark">311</span><span>NYC311 Pulse</span></a>
    <nav className={open ? "nav-open" : ""} aria-label="Primary navigation">
      {links.map(link => <a key={link.href} className={pathname === link.href ? "active" : ""} href={link.href} onClick={() => setOpen(false)}>{link.label}</a>)}
    </nav>
    <span className="snapshot">Fixed snapshot · Jul 31, 2026</span>
    <button className="menu-button" type="button" aria-expanded={open} aria-label="Toggle navigation" onClick={() => setOpen(value => !value)}>{open ? <X size={19} /> : <Menu size={19} />}</button>
  </header>;
}
