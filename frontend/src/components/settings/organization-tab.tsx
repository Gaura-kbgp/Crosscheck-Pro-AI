"use client";

import React, { useState } from "react";
import { UserProfile } from "@/lib/api/types";
import { useOrganization, useUpdateOrganization } from "@/lib/hooks/use-organization";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import {
  Building2,
  Users,
  FolderKanban,
  Calendar,
  ShieldCheck,
  Check,
  Loader2,
  Sparkles,
} from "lucide-react";

interface OrganizationTabProps {
  profile: UserProfile | null;
}

export function OrganizationTab({ profile }: OrganizationTabProps) {
  const { data: organization, isLoading } = useOrganization();
  const updateOrgMutation = useUpdateOrganization();

  const [orgName, setOrgName] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isAdmin = profile?.role === "ADMIN";
  const displayOrgName = orgName !== null ? orgName : (organization?.name || "");

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAdmin || !displayOrgName.trim()) return;

    setErrorMessage(null);
    setSaveSuccess(false);

    try {
      await updateOrgMutation.mutateAsync({ name: displayOrgName.trim() });
      setSaveSuccess(true);
      setOrgName(null);
      setTimeout(() => setSaveSuccess(false), 4000);
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to update organization"
      );
    }
  };

  const formattedDate = organization?.created_at
    ? new Date(organization.created_at).toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "Active";

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-[#0EA5E9]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Organization Header Card */}
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-sky-50 text-[#0EA5E9] border border-sky-200 shadow-xs shrink-0">
                <Building2 className="h-8 w-8" />
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-xl font-bold text-[#0F2747]">
                    {organization?.name || "Workspace Organization"}
                  </h3>
                  <Badge variant="success" dot dotColor="bg-emerald-500">
                    Active Workspace
                  </Badge>
                  {!isAdmin && (
                    <Badge variant="secondary">
                      Member View
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-[#58708F]">
                  Enterprise CrossCheckPro workspace
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 text-xs text-[#58708F] bg-[#F7F9FC] px-3.5 py-2 rounded-lg border border-[#DCE6F0]">
              <Calendar className="h-4 w-4 text-[#58708F]" />
              <span>Created {formattedDate}</span>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Workspace Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">
                  Team Members
                </p>
                <h4 className="text-2xl font-bold text-[#0F2747] mt-1">
                  {organization?.user_count || 1}
                </h4>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-50 text-purple-600">
                <Users className="h-5 w-5" />
              </div>
            </div>
            <p className="text-[11px] text-[#58708F] mt-2">
              Active workspace seats
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">
                  Active Projects
                </p>
                <h4 className="text-2xl font-bold text-[#0F2747] mt-1">
                  {organization?.project_count || 0}
                </h4>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-sky-600">
                <FolderKanban className="h-5 w-5" />
              </div>
            </div>
            <p className="text-[11px] text-[#58708F] mt-2">
              Cross-checked construction packages
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">
                  Workspace Plan
                </p>
                <h4 className="text-sm font-bold text-[#0F2747] mt-1">
                  Enterprise Tier
                </h4>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
                <Sparkles className="h-5 w-5" />
              </div>
            </div>
            <p className="text-[11px] text-[#58708F] mt-2">
              Unlimited document cross-checking
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Organization Settings Form Card */}
      <Card>
        <CardHeader>
          <CardTitle>Organization Details</CardTitle>
          <CardDescription>
            {isAdmin
              ? "Modify your organization name and workspace branding."
              : "Organization details are managed by Workspace Administrators."}
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSave}>
          <CardContent className="space-y-5">
            {!isAdmin && (
              <Alert variant="info" title="Administrator Permission Required">
                You are logged in with the <strong>{profile?.role || "REVIEWER"}</strong> role. Only workspace <strong>ADMIN</strong> users can edit organization information.
              </Alert>
            )}

            {saveSuccess && (
              <Alert variant="success" title="Organization Updated">
                Organization details have been saved successfully.
              </Alert>
            )}

            {errorMessage && (
              <Alert variant="destructive" title="Update Error">
                {errorMessage}
              </Alert>
            )}

            <div className="space-y-2 max-w-xl">
              <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F] flex items-center gap-1.5">
                <Building2 className="h-3.5 w-3.5 text-[#0EA5E9]" />
                Organization Name
              </label>
              <Input
                type="text"
                value={displayOrgName}
                onChange={(e) => setOrgName(e.target.value)}
                disabled={!isAdmin}
                placeholder="e.g. Apex Millwork & Construction"
                className={isAdmin ? "bg-white" : "bg-[#F7F9FC] cursor-not-allowed"}
              />
              <p className="text-[11px] text-[#58708F]">
                This name appears on executive summary reports, exported discrepancy sheets, and review logs.
              </p>
            </div>

            <div className="pt-2 border-t border-[#DCE6F0]">
              <div className="p-4 bg-[#F7F9FC] border border-[#DCE6F0] rounded-xl flex items-start gap-3">
                <ShieldCheck className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
                <div className="text-xs text-[#58708F] space-y-1">
                  <span className="font-semibold text-[#0F2747] block">
                    Workspace Security & Access Controls
                  </span>
                  <p>
                    All projects, design documents, purchase orders, and manufacturer acknowledgements within this workspace are encrypted and isolated to authorized team members.
                  </p>
                </div>
              </div>
            </div>
          </CardContent>

          {isAdmin && (
            <CardFooter className="flex justify-between items-center border-t border-[#DCE6F0] bg-[#FAFCFF] py-3.5">
              <span className="text-xs text-[#58708F]">
                Changes apply across all workspace members.
              </span>
              <Button
                type="submit"
                disabled={
                  updateOrgMutation.isPending ||
                  !displayOrgName.trim() ||
                  displayOrgName.trim() === (organization?.name || "")
                }
                className="min-w-[120px]"
              >
                {updateOrgMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : saveSuccess ? (
                  <>
                    <Check className="mr-2 h-4 w-4" />
                    Saved
                  </>
                ) : (
                  "Save Changes"
                )}
              </Button>
            </CardFooter>
          )}
        </form>
      </Card>
    </div>
  );
}
