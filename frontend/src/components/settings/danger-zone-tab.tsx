"use client";

import React, { useState } from "react";
import { UserProfile } from "@/lib/api/types";
import { useAuthStore } from "@/lib/store/auth-store";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Dialog, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { AlertTriangle, LogOut, Trash2, ShieldAlert } from "lucide-react";

interface DangerZoneTabProps {
  profile: UserProfile | null;
}

export function DangerZoneTab({ profile }: DangerZoneTabProps) {
  const { logout } = useAuthStore();
  const [isSignOutDialogOpen, setIsSignOutDialogOpen] = useState(false);

  const isAdmin = profile?.role === "ADMIN";

  const handleConfirmSignOut = () => {
    setIsSignOutDialogOpen(false);
    logout();
  };

  return (
    <div className="space-y-6">
      {/* Danger Zone Container */}
      <Card className="border-rose-200 bg-rose-50/20">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-100 text-rose-600">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div>
              <CardTitle className="text-rose-950">Danger Zone</CardTitle>
              <CardDescription className="text-rose-700">
                Irreversible account session and workspace deletion operations.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Action 1: Sign Out All Devices */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between p-4 bg-white border border-rose-200 rounded-xl gap-4">
            <div className="space-y-0.5">
              <h5 className="font-bold text-sm text-[#0F2747] flex items-center gap-2">
                <LogOut className="h-4 w-4 text-rose-600" />
                Sign Out Active Session
              </h5>
              <p className="text-xs text-[#58708F]">
                Terminates your current access token and securely clears browser credentials.
              </p>
            </div>
            <Button
              variant="outline"
              onClick={() => setIsSignOutDialogOpen(true)}
              className="text-rose-600 border-rose-200 hover:bg-rose-50 shrink-0"
            >
              Sign Out
            </Button>
          </div>

          {/* Action 2: Delete Workspace / Tenant */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between p-4 bg-white border border-rose-200 rounded-xl gap-4">
            <div className="space-y-0.5">
              <h5 className="font-bold text-sm text-[#0F2747] flex items-center gap-2">
                <Trash2 className="h-4 w-4 text-rose-600" />
                Delete Workspace & Tenant Data
              </h5>
              <p className="text-xs text-[#58708F] max-w-lg leading-relaxed">
                {isAdmin
                  ? "Permanently deletes all construction projects, CAD drawings, PO extractions, and immutable audit logs for this organization."
                  : "Workspace deletion requires Tenant Super-Administrator authorization. Contact your organization administrator."}
              </p>
            </div>
            <Button
              variant="outline"
              disabled={!isAdmin}
              className={`shrink-0 ${
                isAdmin
                  ? "text-rose-600 border-rose-300 hover:bg-rose-50"
                  : "text-slate-400 border-slate-200 cursor-not-allowed bg-slate-50"
              }`}
            >
              {isAdmin ? "Delete Organization" : "Admin Only"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Sign Out Confirmation Dialog */}
      <Dialog open={isSignOutDialogOpen} onOpenChange={setIsSignOutDialogOpen}>
        <DialogHeader>
          <div className="flex items-center gap-2 text-rose-600 mb-1">
            <LogOut className="h-5 w-5" />
            <DialogTitle>Confirm Sign Out</DialogTitle>
          </div>
          <DialogDescription>
            Are you sure you want to sign out of CrossCheckPro? You will need to log back in to access your projects and review queue.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="gap-2 sm:gap-0 mt-4">
          <Button
            variant="outline"
            onClick={() => setIsSignOutDialogOpen(false)}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirmSignOut}
          >
            Sign Out
          </Button>
        </DialogFooter>
      </Dialog>
    </div>
  );
}
