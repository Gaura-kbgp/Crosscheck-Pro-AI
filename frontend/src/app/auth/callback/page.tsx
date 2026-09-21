"use client";

import React, { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuthStore } from "@/lib/store/auth-store";
import { Loader2, ShieldCheck, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";

function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const code = searchParams.get("code");
  const oauthError = searchParams.get("error");
  const handleGoogleCallback = useAuthStore((state) => state.handleGoogleCallback);
  const [asyncError, setAsyncError] = useState<string | null>(null);

  // Derive initial sync error directly from URL params if present
  const initialError = oauthError
    ? `Google authentication was cancelled or failed (${oauthError}).`
    : !code
    ? "Missing OAuth authorization code from Google."
    : null;

  const displayError = initialError || asyncError;

  useEffect(() => {
    if (!code || oauthError) {
      return;
    }

    let isMounted = true;

    async function processCode() {
      try {
        await handleGoogleCallback(code!);
        if (isMounted) {
          router.replace("/dashboard");
        }
      } catch (err: unknown) {
        if (isMounted) {
          setAsyncError(
            err instanceof Error
              ? err.message
              : "Failed to exchange Google authorization code."
          );
        }
      }
    }

    processCode();

    return () => {
      isMounted = false;
    };
  }, [code, oauthError, handleGoogleCallback, router]);

  if (displayError) {
    return (
      <div className="flex flex-col items-center max-w-sm text-center gap-4 bg-white p-8 rounded-2xl border border-rose-200 shadow-sm">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-rose-50 text-rose-600">
          <AlertCircle className="h-6 w-6" />
        </div>
        <div className="space-y-1">
          <h2 className="text-base font-semibold text-slate-800">
            Authentication Failed
          </h2>
          <p className="text-xs text-slate-500">{displayError}</p>
        </div>
        <Link href="/login" className="w-full">
          <Button variant="outline" className="w-full h-10">
            Return to Sign In
          </Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-4 bg-white p-8 rounded-2xl border border-slate-200 shadow-sm max-w-sm text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-sky-600 text-white shadow-md">
        <ShieldCheck className="h-6 w-6" />
      </div>
      <div className="flex flex-col items-center gap-2">
        <Loader2 className="h-6 w-6 animate-spin text-sky-600" />
        <h2 className="text-base font-semibold text-slate-800">
          Authenticating with CrossCheckPro
        </h2>
        <p className="text-xs text-slate-500">
          Verifying your Google identity and initializing workspace...
        </p>
      </div>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <div className="flex h-screen w-screen flex-col items-center justify-center bg-slate-50 p-4">
      <Suspense
        fallback={
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-7 w-7 animate-spin text-sky-600" />
            <p className="text-xs text-slate-500">Processing authentication...</p>
          </div>
        }
      >
        <AuthCallbackContent />
      </Suspense>
    </div>
  );
}
