"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { useAuthStore } from "@/lib/store/auth-store";
import { useUserProfile } from "@/lib/hooks/use-organization";
import { ProfileTab } from "@/components/settings/profile-tab";
import { OrganizationTab } from "@/components/settings/organization-tab";
import { PreferencesTab } from "@/components/settings/preferences-tab";
import { NotificationsTab } from "@/components/settings/notifications-tab";
import { SecurityTab } from "@/components/settings/security-tab";
import { CrossCheckTab } from "@/components/settings/crosscheck-tab";
import { ManufacturerIntelligenceTab } from "@/components/settings/manufacturer-intelligence-tab";
import { DangerZoneTab } from "@/components/settings/danger-zone-tab";
import {
  User,
  Building2,
  Sliders,
  Bell,
  ShieldCheck,
  GitCompare,
  Factory,
  AlertTriangle,
  ChevronRight,
  Loader2,
} from "lucide-react";

type SettingsTabId =
  | "profile"
  | "organization"
  | "preferences"
  | "notifications"
  | "security"
  | "crosscheck"
  | "manufacturers"
  | "danger";

interface TabItem {
  id: SettingsTabId;
  label: string;
  description: string;
  icon: React.ElementType;
  isDanger?: boolean;
}

const SETTINGS_TABS: TabItem[] = [
  {
    id: "profile",
    label: "Profile",
    description: "Account details & display name",
    icon: User,
  },
  {
    id: "organization",
    label: "Organization",
    description: "Workspace details & members",
    icon: Building2,
  },
  {
    id: "preferences",
    label: "Preferences",
    description: "Workflow & display density",
    icon: Sliders,
  },
  {
    id: "notifications",
    label: "Notifications",
    description: "Alerts & event triggers",
    icon: Bell,
  },
  {
    id: "security",
    label: "Security",
    description: "Password & credentials",
    icon: ShieldCheck,
  },
  {
    id: "crosscheck",
    label: "CrossCheck Preferences",
    description: "Review defaults & verification",
    icon: GitCompare,
  },
  {
    id: "manufacturers",
    label: "Manufacturer & Cabinet Intelligence",
    description: "Manufacturer dictionaries & SKU aliases",
    icon: Factory,
  },
  {
    id: "danger",
    label: "Danger Zone",
    description: "Session revocation & deletion",
    icon: AlertTriangle,
    isDanger: true,
  },
];

function SettingsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { profile: storeProfile } = useAuthStore();
  const { data: userProfile } = useUserProfile();

  const activeProfile = userProfile || storeProfile;

  const tabParam = searchParams.get("tab") as SettingsTabId | null;
  const initialTab =
    tabParam && SETTINGS_TABS.some((t) => t.id === tabParam)
      ? tabParam
      : "profile";

  const [activeTab, setActiveTab] = useState<SettingsTabId>(initialTab);

  useEffect(() => {
    if (tabParam && SETTINGS_TABS.some((t) => t.id === tabParam)) {
      setActiveTab(tabParam);
    }
  }, [tabParam]);

  const handleTabChange = (tabId: SettingsTabId) => {
    setActiveTab(tabId);
    router.replace(`/settings?tab=${tabId}`, { scroll: false });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Manage your account, organization, preferences, and CrossCheckPro experience."
      />

      {/* Mobile Selector / Dropdown */}
      <div className="block lg:hidden">
        <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F] block mb-2">
          Settings Section
        </label>
        <div className="relative">
          <select
            value={activeTab}
            onChange={(e) => handleTabChange(e.target.value as SettingsTabId)}
            className="w-full h-11 px-4 rounded-xl border border-[#DCE6F0] bg-white text-sm font-semibold text-[#0F2747] shadow-xs focus:outline-none focus:ring-2 focus:ring-[#0EA5E9]"
          >
            {SETTINGS_TABS.map((tab) => (
              <option key={tab.id} value={tab.id}>
                {tab.label} — {tab.description}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Desktop 2-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Settings Navigation Bar */}
        <aside className="hidden lg:block lg:col-span-4 xl:col-span-3">
          <nav className="rounded-2xl border border-[#DCE6F0] bg-white p-2 shadow-xs space-y-1 sticky top-20">
            <div className="px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-[#58708F]">
              Account & Workspace
            </div>

            {SETTINGS_TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;

              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => handleTabChange(tab.id)}
                  className={`w-full flex items-center justify-between p-3 rounded-xl text-left transition-all group ${
                    isActive
                      ? tab.isDanger
                        ? "bg-rose-50 text-rose-700 font-semibold border border-rose-200 shadow-2xs"
                        : "bg-sky-50/80 text-[#0EA5E9] font-semibold border border-sky-200/80 shadow-2xs"
                      : tab.isDanger
                      ? "text-rose-600 hover:bg-rose-50/50 hover:text-rose-700"
                      : "text-[#58708F] hover:bg-[#F7F9FC] hover:text-[#0F2747]"
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className={`flex h-8 w-8 items-center justify-center rounded-lg shrink-0 transition-colors ${
                        isActive
                          ? tab.isDanger
                            ? "bg-rose-100 text-rose-600"
                            : "bg-[#0EA5E9] text-white shadow-2xs"
                          : "bg-slate-100/70 text-slate-500 group-hover:text-slate-700 group-hover:bg-slate-100"
                      }`}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <span className="text-sm block truncate">
                        {tab.label}
                      </span>
                      <span className="text-[11px] font-normal text-[#58708F] block truncate">
                        {tab.description}
                      </span>
                    </div>
                  </div>

                  <ChevronRight
                    className={`h-4 w-4 shrink-0 transition-transform ${
                      isActive
                        ? tab.isDanger
                          ? "text-rose-500"
                          : "text-[#0EA5E9] translate-x-0.5"
                        : "text-slate-300 opacity-0 group-hover:opacity-100"
                    }`}
                  />
                </button>
              );
            })}
          </nav>
        </aside>

        {/* Right Content Panel */}
        <main className="lg:col-span-8 xl:col-span-9 min-w-0">
          {activeTab === "profile" && <ProfileTab profile={activeProfile} />}
          {activeTab === "organization" && <OrganizationTab profile={activeProfile} />}
          {activeTab === "preferences" && <PreferencesTab />}
          {activeTab === "notifications" && <NotificationsTab />}
          {activeTab === "security" && <SecurityTab profile={activeProfile} />}
          {activeTab === "crosscheck" && <CrossCheckTab />}
          {activeTab === "manufacturers" && <ManufacturerIntelligenceTab />}
          {activeTab === "danger" && <DangerZoneTab profile={activeProfile} />}
        </main>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-[#0EA5E9]" />
        </div>
      }
    >
      <SettingsContent />
    </Suspense>
  );
}
