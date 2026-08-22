import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { headers } from "next/headers";
import { QueryProvider } from "@/components/query-provider";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const forwardedHost = requestHeaders.get("x-forwarded-host");
  const host = forwardedHost ?? requestHeaders.get("host") ?? "nyc311-pulse.vercel.app";
  const protocol = requestHeaders.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  const metadataBase = new URL(process.env.NEXT_PUBLIC_SITE_URL ?? `${protocol}://${host}`);
  const title = "NYC311 Pulse";
  const description = "Evidence-first anomaly triage for New York City service requests.";
  return {
    metadataBase,
    title,
    description,
    icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
    openGraph: { title, description, type: "website", images: [{ url: "/og.png", width: 1731, height: 909, alt: "NYC311 Pulse — Evidence-first anomaly triage" }] },
    twitter: { card: "summary_large_image", title, description, images: ["/og.png"] },
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <QueryProvider>
          <SiteHeader />
          {children}
          <footer className="site-footer"><strong>NYC311 Pulse</strong><p>Official NYC Open Data · deterministic metrics · reproducible snapshot</p><div><a href="/methodology">Methods</a><a href="https://data.cityofnewyork.us/resource/erm2-nwe9" rel="noreferrer" target="_blank">Source data ↗</a></div></footer>
        </QueryProvider>
      </body>
    </html>
  );
}
