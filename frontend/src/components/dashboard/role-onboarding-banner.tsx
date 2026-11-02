"use client";

import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import type { BusinessRole } from "@/lib/api/types";
import { PencilRuler, Handshake, Factory, ArrowRight } from "lucide-react";

// Section 03 of the testing review ("How each role should move through the
// tool"): each role has one main first job. This only shows for an org that
// hasn't created a real (non-sample) project yet — once they have, they
// already know their way around.
const ROLE_COPY: Record<
  BusinessRole,
  { icon: typeof PencilRuler; title: string; description: string }
> = {
  DESIGNER: {
    icon: PencilRuler,
    title: "Your first job: upload a drawing",
    description:
      "Create a project and upload your design PDF. CrossCheckPro reads each room/display — style, finish, construction, SKUs and trim — so you can confirm what it found.",
  },
  DEALER: {
    icon: Handshake,
    title: "Your first job: create a job and upload the order",
    description:
      "Create a project, then upload the order you're sending to the manufacturer. CrossCheckPro checks it against the drawing before it goes to the factory.",
  },
  MANUFACTURER: {
    icon: Factory,
    title: "Your first job: load your catalog, then upload the acknowledgement",
    description:
      "Load your Spec + Price Guide once under Organization settings, then upload the order acknowledgement. CrossCheckPro checks every SKU and mod exists, and that prices match.",
  },
};

export function RoleOnboardingBanner({ businessRole }: { businessRole: BusinessRole }) {
  const copy = ROLE_COPY[businessRole];
  const Icon = copy.icon;

  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-[#DCE6F0] bg-gradient-to-br from-sky-50 to-white p-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3.5">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sky-100 text-sky-600">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-bold text-[#0F2747]">{copy.title}</p>
          <p className="mt-0.5 text-sm text-[#58708F]">{copy.description}</p>
        </div>
      </div>
      <Link href="/projects" className={buttonVariants({ size: "default", className: "shrink-0" })}>
        Create Your First Project <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}
