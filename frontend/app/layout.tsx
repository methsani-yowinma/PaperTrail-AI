import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: { default: "PaperTrail AI — Every answer should have evidence", template: "%s · PaperTrail AI" },
  description:
    "Upload research papers, check claims against them, and inspect the exact passages behind every assessment.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen">
        {children}
        <Toaster />
      </body>
    </html>
  );
}
