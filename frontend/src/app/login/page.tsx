"use client";

import React, { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useAuthStore } from "@/lib/store/auth-store";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import {
  ShieldCheck,
  CheckCircle2,
  FileSpreadsheet,
  GitCompare,
  FileCheck,
  Lock,
  Mail,
  KeyRound,
  ArrowRight,
} from "lucide-react";

const loginSchema = z.object({
  email: z.string().min(1, "Email is required").email("Please enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormData = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const { session, isInitialized, login, loginWithGoogle, isLoading, error, clearError } =
    useAuthStore();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  useEffect(() => {
    if (isInitialized && session) {
      router.replace("/dashboard");
    }
  }, [isInitialized, session, router]);

  const onSubmit = async (data: LoginFormData) => {
    setFormError(null);
    clearError();
    try {
      await login({ email: data.email, password: data.password });
      router.replace("/dashboard");
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Failed to sign in");
    }
  };

  const handleGoogleLogin = async () => {
    setFormError(null);
    clearError();
    try {
      await loginWithGoogle();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Google login failed");
    }
  };

  return (
    <div className="flex min-h-screen w-full bg-slate-50">
      {/* Left Column — Branding & Highlights */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between bg-gradient-to-br from-slate-900 via-slate-800 to-sky-950 p-12 text-white relative overflow-hidden">
        {/* Background Subtle Gradient Blobs */}
        <div className="absolute -top-32 -left-32 h-96 w-96 rounded-full bg-sky-500/10 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-32 -right-32 h-96 w-96 rounded-full bg-blue-600/10 blur-3xl pointer-events-none" />

        {/* Top Branding */}
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

        {/* Hero Narrative */}
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

        {/* Footer info */}
        <div className="relative z-10 flex items-center justify-between text-xs text-slate-400 border-t border-slate-800 pt-6">
          <span>Enterprise Tenant Isolation</span>
          <span className="flex items-center gap-1.5 font-medium">
            <Lock className="h-3.5 w-3.5 text-sky-400" />
            256-bit Encrypted
          </span>
        </div>
      </div>

      {/* Right Column — Authentication Form */}
      <div className="flex w-full lg:w-1/2 flex-col justify-center items-center p-6 sm:p-12 lg:p-16 bg-[#F7F9FC]">
        <div className="w-full max-w-md space-y-6">
          {/* Mobile branding header */}
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
            <span className="text-2xl font-bold tracking-tight text-[#0F2747]">
              CrossCheck<span className="text-[#0EA5E9]">Pro</span>
            </span>
            <p className="text-xs text-[#58708F] font-medium">
              Document Intelligence for Construction Projects
            </p>
          </div>

          <div className="space-y-1.5 text-center lg:text-left">
            <h2 className="text-2xl font-bold tracking-tight text-[#0F2747]">
              Welcome Back
            </h2>
            <p className="text-sm text-[#58708F]">
              Sign in to access your projects, cross-checks, and review queue.
            </p>
          </div>

          {(formError || error) && (
            <Alert variant="destructive" title="Authentication Error">
              {formError || error}
            </Alert>
          )}

          {/* Google OAuth Button */}
          <div>
            <Button
              type="button"
              variant="outline"
              size="lg"
              className="w-full relative h-11 bg-white hover:bg-[#F7F9FC] border-[#DCE6F0] text-[#0F2747] font-semibold shadow-2xs transition-all hover:border-[#0EA5E9]/30"
              isLoading={isLoading}
              onClick={handleGoogleLogin}
            >
              <svg
                className="h-5 w-5 mr-3 shrink-0"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  fill="#4285F4"
                />
                <path
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  fill="#34A853"
                />
                <path
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                  fill="#FBBC05"
                />
                <path
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                  fill="#EA4335"
                />
              </svg>
              <span>Continue with Google</span>
            </Button>
          </div>

          <div className="relative flex items-center justify-center">
            <div className="w-full border-t border-[#DCE6F0]" />
            <span className="absolute bg-[#F7F9FC] px-3 text-xs font-medium uppercase tracking-wider text-[#58708F]">
              Or
            </span>
          </div>

          {/* Email / Password Form */}
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label
                htmlFor="email"
                className="block text-xs font-semibold text-[#0F2747] mb-1.5"
              >
                Email Address
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-[#58708F]">
                  <Mail className="h-4 w-4" />
                </div>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="name@company.com"
                  className={`w-full rounded-lg border bg-white py-2.5 pl-9 pr-3 text-sm text-[#0F2747] placeholder:text-[#58708F] focus:outline-none focus:ring-2 focus:ring-[#0EA5E9]/20 focus:border-[#0EA5E9] transition-colors ${
                    errors.email ? "border-[#DC2626]" : "border-[#DCE6F0]"
                  }`}
                  {...register("email")}
                />
              </div>
              {errors.email && (
                <p className="mt-1 text-xs text-[#DC2626]">{errors.email.message}</p>
              )}
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label
                  htmlFor="password"
                  className="block text-xs font-semibold text-[#0F2747]"
                >
                  Password
                </label>
                <Link
                  href="/forgot-password"
                  className="text-xs font-medium text-[#0284C7] hover:text-[#0EA5E9] transition-colors"
                >
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-[#58708F]">
                  <KeyRound className="h-4 w-4" />
                </div>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  placeholder="••••••••"
                  className={`w-full rounded-lg border bg-white py-2.5 pl-9 pr-3 text-sm text-[#0F2747] placeholder:text-[#58708F] focus:outline-none focus:ring-2 focus:ring-[#0EA5E9]/20 focus:border-[#0EA5E9] transition-colors ${
                    errors.password ? "border-[#DC2626]" : "border-[#DCE6F0]"
                  }`}
                  {...register("password")}
                />
              </div>
              {errors.password && (
                <p className="mt-1 text-xs text-[#DC2626]">{errors.password.message}</p>
              )}
            </div>

            <Button
              type="submit"
              size="lg"
              className="w-full h-11 text-white font-semibold shadow-2xs"
              isLoading={isSubmitting || isLoading}
            >
              <span>Sign In</span>
              <ArrowRight className="h-4 w-4 ml-1.5" />
            </Button>
          </form>

          <div className="text-center text-sm text-[#58708F] pt-2">
            Don&apos;t have an account?{" "}
            <Link
              href="/signup"
              className="font-semibold text-[#0284C7] hover:text-[#0EA5E9] transition-colors"
            >
              Sign Up
            </Link>
          </div>

          <div className="rounded-xl border border-[#DCE6F0] bg-white p-3.5 shadow-2xs space-y-1.5">
            <div className="flex items-center gap-2 text-xs font-semibold text-[#0F2747]">
              <Lock className="h-3.5 w-3.5 text-[#0EA5E9]" />
              <span>Multi-Tenant Enterprise Security</span>
            </div>
            <p className="text-xs text-[#58708F] leading-relaxed">
              Your organization data is isolated and verified using strict
              role-based permissions.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
