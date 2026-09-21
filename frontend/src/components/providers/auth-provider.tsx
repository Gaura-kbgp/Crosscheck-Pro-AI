"use client";

import { useEffect, ReactNode } from "react";
import { useAuthStore } from "@/lib/store/auth-store";

export function AuthProvider({ children }: { children: ReactNode }) {
  const initialize = useAuthStore((state) => state.initialize);

  useEffect(() => {
    initialize();
  }, [initialize]);

  return <>{children}</>;
}
