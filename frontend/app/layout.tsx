import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export const metadata: Metadata = {
  title: "Eikona - Visual Optimization Engine",
  description: "Unified RAG pipeline for photorealistic artifact generation from latent conceptual traces.",
  appleWebApp: {
    title: "Eikona",
    statusBarStyle: "black-translucent",
    capable: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark scroll-smooth">
      <body className={`${inter.variable} antialiased bg-[#050505] selection:bg-green-500/30`}>
        {children}
      </body>
    </html>
  );
}
