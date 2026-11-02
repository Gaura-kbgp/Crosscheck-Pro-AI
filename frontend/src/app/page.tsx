"use client";

import { useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store/auth-store";
import { buttonVariants } from "@/components/ui/button";
import { SeverityBadge, CrossCheckStatusBadge } from "@/components/badges/status-badge";
import {
  FileCheck,
  CheckCircle2,
  GitCompare,
  FileSpreadsheet,
  ArrowRight,
} from "lucide-react";

// Real discrepancies from the Chesapeake Bay Marsh Display R3 sample job (see
// TESTING_REVIEW_FIXLIST.md P1-1/P1-2) — the same data every new signup gets
// as an auto-seeded sample project, so this preview matches what's in-app.
const SAMPLE_ROWS = [
  {
    display: "5 · Double Oven (Jamestown)",
    item: "Construction",
    design: "Furniture Board",
    ack: "PLY (plywood upgrade)",
    status: "CHANGED" as const,
    severity: "WARNING" as const,
  },
  {
    display: "5 · Salt section",
    item: "Crown moulding MCV96",
    design: "Qty 1",
    ack: "Qty 2",
    status: "CHANGED" as const,
    severity: "WARNING" as const,
  },
  {
    display: "2 · Built-in (Hampton)",
    item: "Filler F330",
    design: "Shown on elevation",
    ack: "Not in acknowledgement",
    status: "MISSING" as const,
    severity: "CRITICAL" as const,
  },
];

export default function RootPage() {
  const router = useRouter();
  const { session, isInitialized } = useAuthStore();

  // Signed-in visitors skip the landing page and go straight to their
  // dashboard; everyone else sees the explanation + demo instead of a blank
  // login wall (TESTING_REVIEW_FIXLIST.md, "No home page" finding).
  useEffect(() => {
    if (isInitialized && session) {
      router.replace("/dashboard");
    }
  }, [isInitialized, session, router]);

  return (
    <div className="min-h-screen w-full bg-[#F7F9FC] text-[#0F2747]">
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 py-5 sm:px-10">
        <div className="flex items-center gap-2.5">
          <div className="relative flex h-9 w-9 items-center justify-center rounded-lg bg-slate-900 p-1.5">
            <Image src="/logo.png" alt="CrossCheckPro" width={28} height={28} className="h-full w-full object-contain" priority />
          </div>
          <span className="text-lg font-bold tracking-tight">
            CrossCheck<span className="text-[#0EA5E9]">Pro</span>
          </span>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/login" className="text-sm font-semibold text-[#0F2747] hover:text-[#0EA5E9] transition-colors">
            Sign In
          </Link>
          <Link href="/signup" className={buttonVariants({ size: "sm" })}>
            Start Free
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="px-6 pt-10 pb-16 sm:px-10 text-center">
        <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-3.5 py-1 text-xs font-semibold text-sky-700">
          <FileCheck className="h-3.5 w-3.5" />
          Deterministic Three-Way Verification
        </div>
        <h1 className="mx-auto mt-5 max-w-2xl text-3xl font-extrabold tracking-tight sm:text-4xl">
          Check every cabinet order against the drawing and the factory acknowledgement
        </h1>
        <p className="mx-auto mt-4 max-w-xl text-base text-[#58708F]">
          CrossCheckPro catches SKU, quantity, finish and construction mismatches between a
          designer&apos;s drawing, the dealer&apos;s order and the manufacturer&apos;s
          acknowledgement — before anything goes into production.
        </p>
        <div className="mt-7 flex items-center justify-center gap-3">
          <Link href="/signup" className={buttonVariants({ size: "lg" })}>
            Create Free Account <ArrowRight className="h-4 w-4 ml-1.5" />
          </Link>
          <Link href="#sample" className={buttonVariants({ size: "lg", variant: "outline" })}>
            See a Sample Check
          </Link>
        </div>
      </section>

      {/* 30-second sample check */}
      <section id="sample" className="px-6 pb-20 sm:px-10">
        <div className="mx-auto max-w-3xl rounded-2xl border border-[#DCE6F0] bg-white shadow-sm overflow-hidden">
          <div className="border-b border-[#DCE6F0] bg-[#0B1528] px-6 py-4 text-white">
            <p className="text-xs font-semibold uppercase tracking-wider text-sky-400">Sample job</p>
            <h2 className="text-lg font-bold">Chesapeake Bay · Marsh Display R3</h2>
            <p className="text-xs text-slate-300">
              Drawing vs. real Marsh acknowledgement — every new account gets this project
              pre-loaded so you can see results before uploading your own files.
            </p>
          </div>
          <div className="divide-y divide-[#EDF2F7]">
            {SAMPLE_ROWS.map((row) => (
              <div key={row.item} className="flex flex-col gap-2 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-xs font-semibold text-[#58708F]">{row.display}</p>
                  <p className="text-sm font-semibold text-[#0F2747]">{row.item}</p>
                  <p className="text-xs text-[#58708F]">
                    Drawing: {row.design} · Acknowledgement: {row.ack}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <CrossCheckStatusBadge status={row.status} />
                  <SeverityBadge severity={row.severity} />
                </div>
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between bg-[#F7F9FC] px-6 py-4">
            <p className="text-xs text-[#58708F]">Full comparison runs line-by-line across every display.</p>
            <Link href="/signup" className="text-xs font-semibold text-[#0284C7] hover:text-[#0EA5E9]">
              Sign up to see the full report →
            </Link>
          </div>
        </div>

        <div className="mx-auto mt-8 grid max-w-3xl gap-4 sm:grid-cols-3">
          <div className="flex items-start gap-2.5 rounded-xl border border-[#DCE6F0] bg-white p-4">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-sky-500 mt-0.5" />
            <span className="text-sm text-[#0F2747]">Automated SKU, quantity and dimension cross-checking</span>
          </div>
          <div className="flex items-start gap-2.5 rounded-xl border border-[#DCE6F0] bg-white p-4">
            <GitCompare className="h-4 w-4 shrink-0 text-sky-500 mt-0.5" />
            <span className="text-sm text-[#0F2747]">Severity-ranked discrepancies with who needs to act</span>
          </div>
          <div className="flex items-start gap-2.5 rounded-xl border border-[#DCE6F0] bg-white p-4">
            <FileSpreadsheet className="h-4 w-4 shrink-0 text-sky-500 mt-0.5" />
            <span className="text-sm text-[#0F2747]">Shareable PDF/CSV reports for the manufacturer</span>
          </div>
        </div>
      </section>
    </div>
  );
}
