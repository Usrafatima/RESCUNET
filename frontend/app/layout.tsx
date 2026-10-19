import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ShellLayout } from "@/components/layout/ShellLayout";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "RescuNet — AI Emergency Coordination",
  description: "AI-powered community emergency coordination system",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full`}>
      <body className="min-h-full bg-background text-foreground">
        <ShellLayout>{children}</ShellLayout>
      </body>
    </html>
  );
}
