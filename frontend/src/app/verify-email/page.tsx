"use client";

import React, { useEffect, useState, Suspense } from "react";
import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { authApi } from "@/lib/api/endpoints";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import {
  ShieldCheck,
  CheckCircle2,
  FileSpreadsheet,
  GitCompare,
  FileCheck,
  Lock,
  Loader2,
  CheckCircle,
  XCircle,
  Mail,
  ArrowRight,
} from "lucide-react";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";

  const [verifyStatus, setVerifyStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [resendEmail, setResendEmail] = useState("");
  const [resendStatus, setResendStatus] = useState<"idle" | "loading" | "sent" | "error">("idle");
  const [resendError, setResendError] = useState("");

  const isNoToken = !token;

  useEffect(() => {
    if (!token) {
      return;
    }

    let isMounted = true;

    async function verify() {
      try {
        await authApi.verifyEmail({ token });
        if (isMounted) {
          setVerifyStatus("success");
        }
      } catch (err: unknown) {
        if (isMounted) {
          setVerifyStatus("error");
          setErrorMessage(
            err instanceof Error
              ? err.message
              : "Verification token is invalid, expired, or has already been used."
          );
        }
      }
    }

    verify();

    return () => {
      isMounted = false;
    };
  }, [token]);

  const handleResend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resendEmail) return;
    setResendStatus("loading");
    setResendError("");
    try {
      await authApi.resendVerification({ email: resendEmail });
      setResendStatus("sent");
    } catch (err: unknown) {
      setResendStatus("error");
      setResendError(
        err instanceof Error ? err.message : "Failed to resend verification link."
      );
    }
  };

  return (
    <div className="w-full max-w-md space-y-6">
      {/* Mobile branding */}
      <div className="flex flex-col items-center text-center lg:hidden space-y-2 mb-2">
        <div className="relative flex h-14 w-14 items-center justify-center rounded-2xl bg-white border border-[#DCE6F0] p-2 shadow-md">
          <Image
            src="/logo.png"
            alt="CrossCheckPro"
            width={48}
            height={48}
            className="h-full w-full object-contain"
            priority
          />
        </div>
        <span className="text-2xl font-bold tracking-tight text-slate-900">
          CrossCheck<span className="text-sky-600">Pro</span>
        </span>
      </div>

      {!isNoToken && verifyStatus === "loading" && (
        <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-xs text-center space-y-4">
          <Loader2 className="mx-auto h-10 w-10 animate-spin text-sky-600" />
          <div className="space-y-1">
            <h3 className="text-lg font-bold text-slate-900">
              Verifying Email Address
            </h3>
            <p className="text-xs text-slate-500">
              Please wait while we validate your security token...
            </p>
          </div>
        </div>
      )}

      {!isNoToken && verifyStatus === "success" && (
        <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-xs text-center space-y-5">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
            <CheckCircle className="h-7 w-7" />
          </div>
          <div className="space-y-2">
            <h3 className="text-xl font-bold text-slate-900">
              Email Verified Successfully
            </h3>
            <p className="text-sm text-slate-500 leading-relaxed">
              Your CrossCheckPro account has been verified and is ready for use.
            </p>
          </div>
          <div className="pt-2">
            <Link href="/login" className="block w-full">
              <Button
                type="button"
                size="lg"
                className="w-full h-11 bg-sky-600 hover:bg-sky-700 text-white font-semibold"
              >
                <span>Continue to Sign In</span>
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </Link>
          </div>
        </div>
      )}

      {(isNoToken || verifyStatus === "error") && (
        <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-xs space-y-5">
          <div className="text-center space-y-3">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-rose-50 text-rose-600">
              <XCircle className="h-7 w-7" />
            </div>
            <div className="space-y-1">
              <h3 className="text-lg font-bold text-slate-900">
                {isNoToken
                  ? "Missing Verification Token"
                  : "Verification Failed"}
              </h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                {errorMessage ||
                  "The verification link is missing, expired, or has already been used."}
              </p>
            </div>
          </div>

          <div className="border-t border-slate-100 pt-4 space-y-3">
            <h4 className="text-xs font-semibold text-slate-700">
              Need a new verification link?
            </h4>

            {resendStatus === "sent" ? (
              <Alert variant="default" title="Verification Link Sent">
                If the email is registered, a new verification link has been sent to your inbox.
              </Alert>
            ) : (
              <form onSubmit={handleResend} className="space-y-3">
                {resendError && (
                  <Alert variant="destructive">{resendError}</Alert>
                )}
                <div>
                  <div className="relative">
                    <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                      <Mail className="h-4 w-4" />
                    </div>
                    <input
                      type="email"
                      required
                      placeholder="name@company.com"
                      value={resendEmail}
                      onChange={(e) => setResendEmail(e.target.value)}
                      className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-600"
                    />
                  </div>
                </div>
                <Button
                  type="submit"
                  variant="outline"
                  size="sm"
                  className="w-full h-9"
                  isLoading={resendStatus === "loading"}
                >
                  Resend Verification Email
                </Button>
              </form>
            )}
          </div>

          <div className="text-center pt-2">
            <Link
              href="/login"
              className="text-xs font-medium text-sky-600 hover:text-sky-700"
            >
              Return to Sign In
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="flex min-h-screen w-full bg-slate-50">
      {/* Left Column — Branding */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between bg-gradient-to-br from-slate-900 via-slate-800 to-sky-950 p-12 text-white relative overflow-hidden">
        <div className="absolute -top-32 -left-32 h-96 w-96 rounded-full bg-sky-500/10 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-32 -right-32 h-96 w-96 rounded-full bg-blue-600/10 blur-3xl pointer-events-none" />

        <div className="relative z-10 flex items-center gap-3">
          <div className="relative flex h-11 w-11 items-center justify-center rounded-xl bg-slate-900/60 border border-sky-500/30 p-1.5 shadow-lg shadow-sky-500/20 backdrop-blur-sm shrink-0">
            <Image
              src="/logo.png"
              alt="CrossCheckPro"
              width={40}
              height={40}
              className="h-full w-full object-contain"
              priority
            />
          </div>
          <span className="text-xl font-bold tracking-tight">
            CrossCheck<span className="text-sky-400">Pro</span>
          </span>
        </div>

        <div className="relative z-10 my-auto max-w-lg space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-sky-400/20 bg-sky-500/10 px-3.5 py-1 text-xs font-semibold text-sky-300">
            <FileCheck className="h-3.5 w-3.5" />
            Deterministic Three-Way Verification
          </div>

          <h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl leading-tight">
            Document Intelligence for Construction Projects
          </h1>

          <p className="text-base text-slate-300 leading-relaxed">
            Eliminate costly discrepancies between Design Documents, Purchase
            Orders, and Manufacturer Acknowledgements before fabrication begins.
          </p>

          <div className="space-y-3.5 pt-4 border-t border-slate-700/60">
            <div className="flex items-center gap-3 text-sm text-slate-200">
              <CheckCircle2 className="h-4 w-4 text-sky-400 shrink-0" />
              <span>Automated SKU, quantity, and dimension cross-checking</span>
            </div>
            <div className="flex items-center gap-3 text-sm text-slate-200">
              <GitCompare className="h-4 w-4 text-sky-400 shrink-0" />
              <span>Introduced-at root cause tracking across revisions</span>
            </div>
            <div className="flex items-center gap-3 text-sm text-slate-200">
              <FileSpreadsheet className="h-4 w-4 text-sky-400 shrink-0" />
              <span>Audit-ready PDF reports and granular CSV exports</span>
            </div>
          </div>
        </div>

        <div className="relative z-10 flex items-center justify-between text-xs text-slate-400 border-t border-slate-800 pt-6">
          <span>Enterprise Tenant Isolation</span>
          <span className="flex items-center gap-1.5 font-medium text-slate-400">
            <Lock className="h-3.5 w-3.5 text-sky-400" />
            256-bit Encrypted
          </span>
        </div>
      </div>

      {/* Right Column */}
      <div className="flex w-full lg:w-1/2 flex-col justify-center items-center p-6 sm:p-12 lg:p-16">
        <Suspense
          fallback={
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-sky-600" />
            </div>
          }
        >
          <VerifyEmailContent />
        </Suspense>
      </div>
    </div>
  );
}
