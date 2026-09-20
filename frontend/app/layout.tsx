import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";

export const metadata: Metadata = {
  title: "Catalyst AI | Candidate Screening",
  description: "AI-assisted talent screening workspace",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="fixed inset-x-0 top-0 z-[60] h-1 bg-[#3c172f]" aria-hidden="true" />
        <Sidebar />
        <main className="min-h-screen lg:pl-[220px]">{children}</main>
      </body>
    </html>
  );
}
