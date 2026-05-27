import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/src/lib/providers";
import { ErrorBoundary } from "@/src/components/ui/ErrorBoundary";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Heimdall Ground Control",
  description:
    "Real-time wildfire situational awareness · NVIDIA Jetson AGX · YOLOv9 · MapLibre GL",
  keywords: ["wildfire", "drone", "AI", "YOLO", "Jetson", "3D map"],
  authors: [{ name: "Heimdall Team" }],
};

export const viewport: Viewport = {
  themeColor: "#09090b",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased dark`}
    >
      <body className="h-full bg-zinc-950 text-zinc-100">
        <ErrorBoundary>
          <Providers>{children}</Providers>
        </ErrorBoundary>
      </body>
    </html>
  );
}
