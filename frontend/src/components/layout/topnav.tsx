"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { Menu, Building2, Bell } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useAuthStore } from "@/lib/store/auth-store";
import { useOrganization } from "@/lib/hooks/use-organization";

const routeTitleMap: Record<string, string> = {
  "/dashboard": "Overview",
  "/projects": "Projects",
  "/documents": "Document Repository",
  "/crosscheck": "Three-Way CrossCheck",
  "/reviews": "Human Review Queue",
  "/reports": "Reports & Exports",
  "/organization": "Organization Settings",
  "/settings": "Settings & Preferences",
};

interface TopNavProps {
  onOpenMobileMenu?: () => void;
}

export function TopNav({ onOpenMobileMenu }: TopNavProps) {
  const pathname = usePathname();
  const { profile } = useAuthStore();
  const { data: organization } = useOrganization();

  const currentTitle =
    routeTitleMap[pathname] ||
    (pathname.startsWith("/projects/") ? "Project Details" : "Platform");

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-[#DCE6F0] bg-white px-4 sm:px-6">
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenMobileMenu}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#DCE6F0] text-[#58708F] hover:bg-[#F7F9FC] hover:text-[#0F2747] lg:hidden cursor-pointer"
          aria-label="Open mobile menu"
        >
          <Menu className="h-5 w-5" />
        </button>

        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-[#0F2747]">
            {currentTitle}
          </span>
          {pathname.startsWith("/projects") && (
            <>
              <span className="hidden sm:inline-block text-[#DCE6F0]">•</span>
              <span className="hidden sm:inline-block text-xs text-[#58708F] font-medium">
                Workspace
              </span>
            </>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        {organization?.name && (
          <div className="hidden sm:flex items-center gap-2 rounded-lg border border-[#DCE6F0] bg-[#F7F9FC] px-3 py-1.5 text-xs font-semibold text-[#0F2747]">
            <Building2 className="h-3.5 w-3.5 text-[#0EA5E9]" />
            <span className="max-w-[160px] truncate">{organization.name}</span>
          </div>
        )}

        <Badge variant="success" dot dotColor="bg-[#16A34A]" className="hidden md:inline-flex text-xs">
          Live System
        </Badge>
      </div>
    </header>
  );
}

