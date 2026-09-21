"use client";

import React, { useState, Suspense } from "react";
import Image from "next/image";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
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
  KeyRound,
  CheckCircle,
  Loader2,
  ArrowRight,
} from "lucide-react";

const resetPasswordSchema = z
  .object({
    newPassword: z.string().min(8, "Password must be at least 8 characters"),
    confirmPassword: z.string().min(1, "Please confirm your password"),
  })
  .refine((data) => data.newPassword === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

type ResetPasswordFormData = z.infer<typeof resetPasswordSchema>;

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";

  const [formError, setFormError] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordFormData>({
    resolver: zodResolver(resetPasswordSchema),
  });

  const onSubmit = async (data: ResetPasswordFormData) => {
    if (!token) {
      setFormError("Reset token is missing or invalid. Please request a new link.");
      return;
    }
    setFormError(null);
    try {
      await authApi.resetPassword({
        token,
        new_password: data.newPassword,
        confirm_password: data.confirmPassword,
      });
      setIsSuccess(true);
    } catch (err: unknown) {
      setFormError(
        err instanceof Error
          ? err.message
          : "Failed to reset password. The link may be expired or already used."
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

      {isSuccess ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-xs text-center space-y-5">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
            <CheckCircle className="h-7 w-7" />
          </div>
          <div className="space-y-2">
            <h3 className="text-xl font-bold text-slate-900">
              Password Updated Successfully
            </h3>
            <p className="text-sm text-slate-500 leading-relaxed">
              Your password has been changed securely. You can now log in to CrossCheckPro with your new credentials.
            </p>
          </div>
          <div className="pt-2">
            <Link href="/login" className="block w-full">
              <Button
                type="button"
                size="lg"
                className="w-full h-11 bg-sky-600 hover:bg-sky-700 text-white font-semibold"
              >
                Continue to Sign In
              </Button>
            </Link>
          </div>
        </div>
      ) : !token ? (
        <div className="rounded-2xl border border-rose-200 bg-white p-8 shadow-xs text-center space-y-5">
          <div className="space-y-2">
            <h3 className="text-xl font-bold text-slate-900">
              Invalid or Missing Token
            </h3>
            <p className="text-sm text-slate-500 leading-relaxed">
              This password reset link is invalid or missing a security token. Please request a new password reset link.
            </p>
          </div>
          <div className="pt-2">
            <Link href="/forgot-password" className="block w-full">
              <Button
                type="button"
                size="lg"
                className="w-full h-11 bg-sky-600 hover:bg-sky-700 text-white font-semibold"
              >
                Request New Link
              </Button>
            </Link>
          </div>
        </div>
      ) : (
        <>
          <div className="space-y-1.5 text-center lg:text-left">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">
              Set New Password
            </h2>
            <p className="text-sm text-slate-500">
              Choose a secure password with at least 8 characters.
            </p>
          </div>

          {formError && (
            <Alert variant="destructive" title="Update Failed">
              {formError}
            </Alert>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label
                htmlFor="newPassword"
                className="block text-xs font-semibold text-slate-700 mb-1.5"
              >
                New Password
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <KeyRound className="h-4 w-4" />
                </div>
                <input
                  id="newPassword"
                  type="password"
                  autoComplete="new-password"
                  placeholder="••••••••"
                  className={`w-full rounded-lg border bg-white py-2.5 pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-600 transition-colors ${
                    errors.newPassword ? "border-rose-500" : "border-slate-200"
                  }`}
                  {...register("newPassword")}
                />
              </div>
              {errors.newPassword && (
                <p className="mt-1 text-xs text-rose-600">
                  {errors.newPassword.message}
                </p>
              )}
            </div>

            <div>
              <label
                htmlFor="confirmPassword"
                className="block text-xs font-semibold text-slate-700 mb-1.5"
              >
                Confirm Password
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
                  <KeyRound className="h-4 w-4" />
                </div>
                <input
                  id="confirmPassword"
                  type="password"
                  autoComplete="new-password"
                  placeholder="••••••••"
                  className={`w-full rounded-lg border bg-white py-2.5 pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500/20 focus:border-sky-600 transition-colors ${
                    errors.confirmPassword ? "border-rose-500" : "border-slate-200"
                  }`}
                  {...register("confirmPassword")}
                />
              </div>
              {errors.confirmPassword && (
                <p className="mt-1 text-xs text-rose-600">
                  {errors.confirmPassword.message}
                </p>
              )}
            </div>

            <Button
              type="submit"
              size="lg"
              className="w-full h-11 bg-sky-600 hover:bg-sky-700 text-white font-semibold shadow-xs"
              isLoading={isSubmitting}
            >
              <span>Update Password</span>
              <ArrowRight className="h-4 w-4 ml-1.5" />
            </Button>
          </form>
        </>
      )}
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="flex min-h-screen w-full bg-slate-50">
      {/* Left Column — Branding & Highlights */}
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

      {/* Right Column — Reset Password Form */}
      <div className="flex w-full lg:w-1/2 flex-col justify-center items-center p-6 sm:p-12 lg:p-16">
        <Suspense
          fallback={
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-sky-600" />
            </div>
          }
        >
          <ResetPasswordForm />
        </Suspense>
      </div>
    </div>
  );
}
