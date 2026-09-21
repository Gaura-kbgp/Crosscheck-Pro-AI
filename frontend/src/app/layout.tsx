import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { QueryProvider } from "@/components/providers/query-provider";
import { AuthProvider } from "@/components/providers/auth-provider";
import { Toaster } from "sonner";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "CrossCheckPro — Document Intelligence for Construction Projects",
  description:
    "Automated three-way matching, discrepancy detection, and audit reconciliation for construction project documents.",
  icons: {
    icon: [
      { url: "/logo.png" },
      { url: "/favicon.ico" },
    ],
    shortcut: "/logo.png",
    apple: "/logo.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body
        className={`${inter.className} min-h-screen bg-slate-50 font-sans antialiased text-slate-900 selection:bg-sky-100 selection:text-sky-900`}
        suppressHydrationWarning
      >
        <QueryProvider>
          <AuthProvider>
            {children}
            <Toaster
              position="top-right"
              toastOptions={{
                className: "border border-slate-200 shadow-md font-sans text-sm",
                duration: 4000,
              }}
            />
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
