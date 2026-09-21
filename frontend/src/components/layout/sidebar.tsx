"use client";

import React from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/lib/store/auth-store";
import {
  LayoutDashboard,
  FolderKanban,
  FileText,
  GitCompare,
  CheckSquare,
  FileSpreadsheet,
  Building2,
  Settings,
  LogOut,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import { Separator } from "@/components/ui/separator";

const mainNavItems = [
  {
    title: "Dashboard",
    href: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    title: "Projects",
    href: "/projects",
    icon: FolderKanban,
  },
  {
    title: "Documents",
    href: "/documents",
    icon: FileText,
  },
  {
    title: "Cross-Check",
    href: "/crosscheck",
    icon: GitCompare,
  },
  {
    title: "Reviews",
    href: "/reviews",
    icon: CheckSquare,
  },
  {
    title: "Reports",
    href: "/reports",
    icon: FileSpreadsheet,
  },
];

const secondaryNavItems = [
  {
    title: "Organization",
    href: "/organization",
    icon: Building2,
  },
  {
    title: "Settings",
    href: "/settings",
    icon: Settings,
  },
];

export function Sidebar({ className }: { className?: string }) {
  const pathname = usePathname();
  const { user, profile, logout } = useAuthStore();

  const userEmail = profile?.email || user?.email || "user@crosscheckpro.com";
  const userRole = profile?.role || "REVIEWER";

  return (
    <aside
      className={cn(
        "flex h-screen w-64 flex-col border-r border-[#DCE6F0] bg-white select-none",
        className
      )}
    >
      {/* Brand Header */}
      <div className="flex h-16 items-center gap-3 px-5 border-b border-[#DCE6F0]">
        <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-white border border-[#DCE6F0] p-1 shadow-xs shrink-0 overflow-hidden">
          <Image
            src="/logo.png"
            alt="CrossCheckPro"
            width={38}
            height={38}
            className="h-full w-full object-contain"
            priority
          />
        </div>
        <div className="flex flex-col">
          <span className="font-bold text-[#0F2747] tracking-tight text-base flex items-center gap-1">
            CrossCheck<span className="text-[#0EA5E9]">Pro</span>
          </span>
          <span className="text-[10px] font-semibold text-[#58708F] uppercase tracking-wider">
            Document Intelligence
          </span>
        </div>
      </div>

      {/* Navigation List */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
        {/* Main Section */}
        <div className="space-y-1">
          <div className="px-3 mb-2 text-[11px] font-semibold text-[#58708F] uppercase tracking-wider">
            Platform
          </div>
          {mainNavItems.map((item) => {
            const isActive =
              pathname === item.href ||
              (item.href !== "/dashboard" && pathname.startsWith(item.href));
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors duration-150 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0EA5E9]/30 focus-visible:ring-offset-1",
                  isActive
                    ? "bg-transparent font-semibold text-[#0F2747]"
                    : "bg-transparent font-medium text-[#58708F] hover:bg-[#F7F9FC] hover:text-[#0F2747]"
                )}
              >
                {isActive && (
                  <span
                    className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r-[2px] bg-[#0EA5E9]"
                    aria-hidden="true"
                  />
                )}
                <Icon
                  className={cn(
                    "h-4 w-4 shrink-0 transition-colors duration-150",
                    isActive
                      ? "text-[#0EA5E9]"
                      : "text-[#58708F] group-hover:text-[#0EA5E9]"
                  )}
                />
                <span>{item.title}</span>
              </Link>
            );
          })}
        </div>

        <Separator className="mx-2 bg-[#DCE6F0]" />

        {/* Administration Section */}
        <div className="space-y-1">
          <div className="px-3 mb-2 text-[11px] font-semibold text-[#58708F] uppercase tracking-wider">
            Management
          </div>
          {secondaryNavItems.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href);
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors duration-150 group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0EA5E9]/30 focus-visible:ring-offset-1",
                  isActive
                    ? "bg-transparent font-semibold text-[#0F2747]"
                    : "bg-transparent font-medium text-[#58708F] hover:bg-[#F7F9FC] hover:text-[#0F2747]"
                )}
              >
                {isActive && (
                  <span
                    className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r-[2px] bg-[#0EA5E9]"
                    aria-hidden="true"
                  />
                )}
                <Icon
                  className={cn(
                    "h-4 w-4 shrink-0 transition-colors duration-150",
                    isActive
                      ? "text-[#0EA5E9]"
                      : "text-[#58708F] group-hover:text-[#0EA5E9]"
                  )}
                />
                <span>{item.title}</span>
              </Link>
            );
          })}
        </div>
      </div>

      {/* User & Logout Footer */}
      <div className="p-3 border-t border-[#DCE6F0] bg-[#F7F9FC]/60">
        <div className="flex items-center justify-between rounded-lg p-2 hover:bg-[#F7F9FC] transition-colors">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#E0F2FE] text-[#0284C7] font-bold text-xs">
              <UserCheck className="h-4 w-4" />
            </div>
            <div className="flex flex-col overflow-hidden text-left">
              <span className="truncate text-xs font-semibold text-[#0F2747]">
                {userEmail}
              </span>
              <span className="text-[10px] text-[#58708F] uppercase font-medium">
                {userRole}
              </span>
            </div>
          </div>
          <button
            onClick={() => logout()}
            title="Sign out"
            className="flex h-7 w-7 items-center justify-center rounded-md text-[#58708F] hover:text-[#DC2626] hover:bg-[#FEE2E2] transition-colors cursor-pointer"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
