"use client";

import React, { useState } from "react";
import { UserProfile } from "@/lib/api/types";
import { useChangePassword } from "@/lib/hooks/use-organization";
import { useAuthStore } from "@/lib/store/auth-store";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import {
  ShieldCheck,
  KeyRound,
  LogOut,
  Loader2,
  Check,
  Eye,
  EyeOff,
  Lock,
} from "lucide-react";

interface SecurityTabProps {
  profile: UserProfile | null;
}

export function SecurityTab({ profile }: SecurityTabProps) {
  const { logout } = useAuthStore();
  const changePasswordMutation = useChangePassword();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const isGoogleAccount = !profile?.auth_id?.startsWith("usr_");

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    if (newPassword.length < 8) {
      setErrorMessage("New password must be at least 8 characters long.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setErrorMessage("New passwords do not match.");
      return;
    }

    try {
      const res = await changePasswordMutation.mutateAsync({
        current_password: currentPassword || undefined,
        new_password: newPassword,
      });

      setSuccessMessage(res.message || "Password changed successfully!");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to change password."
      );
    }
  };

  return (
    <div className="space-y-6">
      {/* Auth Overview Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <CardTitle>Authentication & Security</CardTitle>
              <CardDescription>
                Manage your login credentials, password security, and active session.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 bg-[#F7F9FC] border border-[#DCE6F0] rounded-xl space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">
                  Sign-In Method
                </span>
                <Badge variant="success" dot dotColor="bg-emerald-500">
                  Secured
                </Badge>
              </div>
              <h4 className="text-base font-bold text-[#0F2747]">
                {isGoogleAccount ? "Google Workspace SSO" : "Email & Password"}
              </h4>
              <p className="text-xs text-[#58708F]">
                {isGoogleAccount
                  ? "Authenticated via verified Google Workspace single sign-on."
                  : "Protected with encrypted password verification."}
              </p>
            </div>

            <div className="p-4 bg-[#F7F9FC] border border-[#DCE6F0] rounded-xl space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">
                  Session Status
                </span>
                <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                  Active
                </span>
              </div>
              <h4 className="text-base font-bold text-[#0F2747]">
                Encrypted Browser Session
              </h4>
              <p className="text-xs text-[#58708F]">
                Standard 7-day rolling window with automatic session renewal.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Change Password Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-50 text-[#0EA5E9]">
              <KeyRound className="h-4 w-4" />
            </div>
            <div>
              <CardTitle>Change Password</CardTitle>
              <CardDescription>
                Update your account password with at least 8 characters.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <form onSubmit={handleChangePassword}>
          <CardContent className="space-y-4">
            {successMessage && (
              <Alert variant="success" title="Password Updated">
                {successMessage}
              </Alert>
            )}

            {errorMessage && (
              <Alert variant="destructive" title="Security Error">
                {errorMessage}
              </Alert>
            )}

            <div className="space-y-4 max-w-md">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">
                  Current Password
                </label>
                <div className="relative">
                  <Input
                    type={showPassword ? "text" : "password"}
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="Enter current password"
                    className="bg-white pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">
                  New Password
                </label>
                <Input
                  type={showPassword ? "text" : "password"}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  className="bg-white"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">
                  Confirm New Password
                </label>
                <Input
                  type={showPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter new password"
                  className="bg-white"
                />
              </div>
            </div>
          </CardContent>

          <CardFooter className="flex justify-between items-center border-t border-[#DCE6F0] bg-[#FAFCFF] py-3.5">
            <span className="text-xs text-[#58708F]">
              Your password is encrypted securely upon update.
            </span>
            <Button
              type="submit"
              disabled={changePasswordMutation.isPending || !newPassword || !confirmPassword}
              className="min-w-[140px]"
            >
              {changePasswordMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Updating...
                </>
              ) : successMessage ? (
                <>
                  <Check className="mr-2 h-4 w-4" />
                  Updated
                </>
              ) : (
                "Update Password"
              )}
            </Button>
          </CardFooter>
        </form>
      </Card>

      {/* Session Termination */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <CardTitle className="text-base">Active Device Session</CardTitle>
              <CardDescription>
                Sign out of this browser session to clear your active credentials.
              </CardDescription>
            </div>
            <Button
              variant="outline"
              onClick={() => logout()}
              className="text-rose-600 border-rose-200 hover:bg-rose-50"
            >
              <LogOut className="h-4 w-4 mr-2" />
              Sign Out
            </Button>
          </div>
        </CardHeader>
      </Card>
    </div>
  );
}
