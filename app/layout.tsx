import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import FloatingThemeToggle from "@/components/FloatingThemeToggle";

export const metadata: Metadata = {
  title: "GST Scanner — Turn GST invoices into structured data instantly",
  description:
    "Zero manual entry. Upload invoices → Extract GST data → Auto-sync to Google Sheets. Built for Indian GST workflows.",
  openGraph: {
    title: "GST Scanner — Turn GST invoices into structured data instantly",
    description:
      "Zero manual entry. Upload invoices → Extract GST data → Auto-sync to Google Sheets.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-[var(--background)] font-sans text-[var(--foreground)] antialiased" style={{ fontFamily: "'Plus Jakarta Sans', system-ui, sans-serif" }}>
        <ThemeProvider>
          <AuthProvider>
            {children}
            <FloatingThemeToggle />
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
