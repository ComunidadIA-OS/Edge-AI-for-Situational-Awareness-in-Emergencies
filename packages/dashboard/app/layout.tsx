import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/src/lib/providers";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Heimdall Ground Control",
  description:
    "Conciencia situacional de incendios forestales en tiempo real · NVIDIA Jetson AGX · YOLOv9 · MapLibre GL",
  keywords: ["incendios", "wildfire", "drone", "IA", "YOLO", "Jetson", "mapa 3D"],
  authors: [{ name: "Heimdall Team" }],
  manifest: "/manifest.webmanifest",
  icons: { icon: "/favicon.svg" },
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
      lang="es"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased dark`}
    >
      <body className="h-full bg-zinc-950 text-zinc-100">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
