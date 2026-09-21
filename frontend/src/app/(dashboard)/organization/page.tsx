"use client";

import React from "react";
import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { useAuthStore } from "@/lib/store/auth-store";
import { useUserProfile } from "@/lib/hooks/use-organization";
import { OrganizationTab } from "@/components/settings/organization-tab";
import { Button } from "@/components/ui/button";
import { Sliders } from "lucide-react";

export default function OrganizationPage() {
  const { profile: storeProfile } = useAuthStore();
  const { data: userProfile } = useUserProfile();

  const activeProfile = userProfile || storeProfile;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Organization Settings"
        description="Tenant configuration, team metrics, and multi-tenant data boundaries."
        actions={
          <Link href="/settings">
            <Button variant="outline" size="sm" className="text-xs">
              <Sliders className="h-3.5 w-3.5 mr-1.5" />
              All Workspace Settings
            </Button>
          </Link>
        }
      />

      <OrganizationTab profile={activeProfile} />
    </div>
  );
}
