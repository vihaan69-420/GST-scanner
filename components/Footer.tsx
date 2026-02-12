import Link from "next/link";

const footerLinks = [
  { href: "/", label: "Home" },
  { href: "/about", label: "About" },
  { href: "/#features", label: "Features" },
  { href: "/#pricing", label: "Pricing" },
  { href: "/pricing", label: "Compare plans" },
  { href: "/login", label: "Log in" },
  { href: "/register", label: "Register" },
];

export default function Footer() {
  return (
    <footer className="border-t border-[var(--glass-border)] bg-[var(--card)]/50">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">
          <Link
            href="/"
            className="text-lg font-semibold tracking-tight text-[var(--foreground)]"
          >
            GST Scanner
          </Link>
          <div className="flex flex-wrap items-center justify-center gap-6">
            {footerLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-sm text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
              >
                {link.label}
              </Link>
            ))}
          </div>
        </div>
        <p className="mt-8 text-center text-sm text-[var(--muted)]">
          Built for Indian GST workflows. Secure data handling. Reliable automation.
        </p>
      </div>
    </footer>
  );
}
