"use client";

import React, { useState } from "react";
import { UserProfile, Role } from "@/lib/api/types";
import { useUpdateUserProfile, useOrganization } from "@/lib/hooks/use-organization";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { User, Mail, Shield, Building2, Calendar, Loader2, Check } from "lucide-react";

interface ProfileTabProps {
  profile: UserProfile | null;
}

const roleDescriptions: Record<Role, string> = {
  ADMIN: "Administrator with full workspace management & review privileges",
  REVIEWER: "Authorized reviewer for discrepancy resolution & project finalization",
  VIEWER: "Read-only workspace member with export & inspection access",
};

export function ProfileTab({ profile }: ProfileTabProps) {
  const [fullName, setFullName] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { data: organization } = useOrganization();
  const updateProfileMutation = useUpdateUserProfile();
  const displayName = fullName !== null ? fullName : (profile?.full_name || "");

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSaveSuccess(false);

    try {
      await updateProfileMutation.mutateAsync({ full_name: displayName.trim() });
      setSaveSuccess(true);
      setFullName(null);
      setTimeout(() => setSaveSuccess(false), 4000);
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to update profile name"
      );
    }
  };

  const initials = (profile?.full_name || profile?.email || "U")
    .split(" ")
    .map((n) => n[0])
    .join("")
    .substring(0, 2)
    .toUpperCase();

  const formattedDate = profile?.created_at
    ? new Date(profile.created_at).toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "Active Member";

  return (
    <div className="space-y-6">
      {/* Overview Card */}
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 to-blue-600 text-white font-bold text-xl shadow-md shrink-0">
                {initials}
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-xl font-bold text-[#0F2747]">
                    {profile?.full_name || profile?.email?.split("@")[0] || "User Profile"}
                  </h3>
                  <Badge variant={profile?.role === "ADMIN" ? "default" : "secondary"}>
                    {profile?.role || "REVIEWER"}
                  </Badge>
                  {profile?.is_verified && (
                    <Badge variant="success" dot dotColor="bg-emerald-500">
                      Verified
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-[#58708F] flex items-center gap-1.5">
                  <Mail className="h-3.5 w-3.5" />
                  {profile?.email}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 text-xs text-[#58708F] bg-[#F7F9FC] px-3.5 py-2 rounded-lg border border-[#DCE6F0]">
              <Calendar className="h-4 w-4 text-[#58708F]" />
              <span>Joined {formattedDate}</span>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Profile Form Card */}
      <Card>
        <CardHeader>
          <CardTitle>Personal Information</CardTitle>
          <CardDescription>
            Update your display name and review account assignment details.
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSave}>
          <CardContent className="space-y-5">
            {saveSuccess && (
              <Alert variant="success" title="Profile Updated">
                Your profile details have been saved and updated across CrossCheckPro.
              </Alert>
            )}

            {errorMessage && (
              <Alert variant="destructive" title="Update Failed">
                {errorMessage}
              </Alert>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F] flex items-center gap-1.5">
                  <User className="h-3.5 w-3.5 text-[#0EA5E9]" />
                  Full Name
                </label>
                <Input
                  type="text"
                  value={displayName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="e.g. Jane Doe"
                  className="bg-white"
                />
                <p className="text-[11px] text-[#58708F]">
                  This name is displayed on project reviews and activity reports.
                </p>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F] flex items-center gap-1.5">
                  <Mail className="h-3.5 w-3.5 text-[#0EA5E9]" />
                  Email Address
                </label>
                <Input
                  type="email"
                  value={profile?.email || ""}
                  disabled
                  className="bg-[#F7F9FC] text-[#58708F] cursor-not-allowed"
                />
                <p className="text-[11px] text-[#58708F]">
                  Email address is linked to your login credentials.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pt-2">
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F] flex items-center gap-1.5">
                  <Shield className="h-3.5 w-3.5 text-[#0EA5E9]" />
                  Account Role
                </label>
                <div className="p-3 bg-[#F7F9FC] border border-[#DCE6F0] rounded-lg">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-sm text-[#0F2747]">
                      {profile?.role || "REVIEWER"}
                    </span>
                    <span className="text-[11px] font-medium text-[#0EA5E9] bg-sky-50 px-2 py-0.5 rounded border border-sky-200">
                      Managed by Admin
                    </span>
                  </div>
                  <p className="text-xs text-[#58708F] mt-1">
                    {roleDescriptions[profile?.role || "REVIEWER"]}
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F] flex items-center gap-1.5">
                  <Building2 className="h-3.5 w-3.5 text-[#0EA5E9]" />
                  Workspace
                </label>
                <div className="p-3 bg-[#F7F9FC] border border-[#DCE6F0] rounded-lg">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-xs text-[#0F2747] truncate max-w-[200px]">
                      {organization?.name || "Active Workspace"}
                    </span>
                    <span className="text-[11px] text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 font-medium">
                      Active
                    </span>
                  </div>
                  <p className="text-xs text-[#58708F] mt-1">
                    Enterprise project workspace member.
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
          <CardFooter className="flex justify-between items-center border-t border-[#DCE6F0] bg-[#FAFCFF] py-3.5">
            <span className="text-xs text-[#58708F]">
              Changes are saved directly to your account profile.
            </span>
            <Button
              type="submit"
              disabled={
                updateProfileMutation.isPending ||
                !displayName.trim() ||
                displayName.trim() === (profile?.full_name || "")
              }
              className="min-w-[120px]"
            >
              {updateProfileMutation.isPending ? (
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
        </form>
      </Card>
    </div>
  );
}
