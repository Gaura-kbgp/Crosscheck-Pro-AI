"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "./sidebar";
import { TopNav } from "./topnav";
import { MobileNav } from "./mobile-nav";
import { useAuthStore } from "@/lib/store/auth-store";
import { useMounted } from "@/lib/hooks/use-mounted";
import Image from "next/image";
import { Loader2 } from "lucide-react";

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { session, isInitialized, isLoading } = useAuthStore();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const mounted = useMounted();

  // Route protection
  useEffect(() => {
    if (isInitialized && mounted && !session) {
      router.replace("/login");
    }
  }, [isInitialized, mounted, session, router]);

  if (!mounted) {
    return null;
  }

  if (!isInitialized || (isLoading && !session)) {
    return (
      <div className="flex h-screen w-screen flex-col items-center justify-center bg-[#0B1528] text-white">
        <div className="flex flex-col items-center gap-4">
          <div className="relative h-16 w-16 overflow-hidden rounded-2xl shadow-xl shadow-sky-500/20 ring-1 ring-sky-500/30 p-2 bg-slate-900/90 backdrop-blur-sm flex items-center justify-center">
            <Image
              src="/logo.png"
              alt="CrossCheckPro Logo"
              width={56}
              height={56}
              className="h-full w-full object-contain"
              priority
            />
          </div>
          <div className="flex items-center gap-2.5 text-sky-400">
            <Loader2 className="h-4 w-4 animate-spin text-sky-400" />
            <p className="text-sm font-semibold tracking-wide text-slate-200">
              Initializing CrossCheckPro...
            </p>
          </div>
        </div>
      </div>
    );
  }

  // If unauthenticated, let useEffect redirect to /login
  if (!session) {
    return null;
  }

  return (
    <div
      className="flex min-h-screen bg-[#F7F9FC] text-[#0F2747]"
      suppressHydrationWarning
    >
      {/* Desktop Persistent Sidebar */}
      <Sidebar className="hidden lg:flex shrink-0 sticky top-0" />

      {/* Mobile Drawer */}
      <MobileNav
        isOpen={mobileMenuOpen}
        onClose={() => setMobileMenuOpen(false)}
      />

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-x-hidden">
        <TopNav onOpenMobileMenu={() => setMobileMenuOpen(true)} />
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
