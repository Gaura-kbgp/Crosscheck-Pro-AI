"use client";

import React, { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import { NotificationSettings } from "@/lib/api/types";
import {
  Bell,
  CheckCircle2,
  AlertCircle,
  FileCheck,
  FileSpreadsheet,
  Mail,
  ShieldCheck,
  Check,
} from "lucide-react";

const DEFAULT_NOTIFICATIONS: NotificationSettings = {
  processingCompleted: true,
  processingFailed: true,
  reviewRequired: true,
  criticalDiscrepancyDetected: true,
  reportGenerated: true,
  projectFinalized: true,
  emailDigest: "instant",
};

const NOTIFICATIONS_STORAGE_KEY = "crosscheck_notification_settings";

export function NotificationsTab() {
  const [settings, setSettings] = useState<NotificationSettings>(DEFAULT_NOTIFICATIONS);
  const [isSaved, setIsSaved] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      try {
        const raw = localStorage.getItem(NOTIFICATIONS_STORAGE_KEY);
        if (raw) setSettings({ ...DEFAULT_NOTIFICATIONS, ...JSON.parse(raw) });
      } catch {
        // Fallback to defaults
      }
    }
  }, []);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (typeof window !== "undefined") {
      localStorage.setItem(NOTIFICATIONS_STORAGE_KEY, JSON.stringify(settings));
      setIsSaved(true);
      setTimeout(() => setIsSaved(false), 3000);
    }
  };

  const toggleEvent = (key: keyof Omit<NotificationSettings, "emailDigest">) => {
    setSettings((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const eventList: {
    key: keyof Omit<NotificationSettings, "emailDigest">;
    title: string;
    description: string;
    icon: React.ElementType;
    badge?: string;
  }[] = [
    {
      key: "processingCompleted",
      title: "Processing Completed",
      description: "Trigger alert when document OCR extraction, line item canonicalization, and matching finish.",
      icon: CheckCircle2,
    },
    {
      key: "processingFailed",
      title: "Processing Failed",
      description: "Trigger urgent alert if document OCR parsing fails or unreadable PDFs are encountered.",
      icon: AlertCircle,
      badge: "High Priority",
    },
    {
      key: "reviewRequired",
      title: "Human Review Queue Required",
      description: "Notify authorized reviewers when match groups contain uncertain SKUs or ambiguous descriptions.",
      icon: ShieldCheck,
    },
    {
      key: "criticalDiscrepancyDetected",
      title: "Critical Discrepancy Detected",
      description: "Immediate alert when missing items or quantity mismatches exceed tolerance thresholds.",
      icon: AlertCircle,
      badge: "Critical",
    },
    {
      key: "reportGenerated",
      title: "Audit Report Generated",
      description: "Notification when executive PDF report or CSV line item exports are ready to download.",
      icon: FileSpreadsheet,
    },
    {
      key: "projectFinalized",
      title: "Project State Finalized",
      description: "Alert all workspace members when a reviewer seals the project and locks the audit trail.",
      icon: FileCheck,
    },
  ];

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-50 text-purple-600">
              <Bell className="h-5 w-5" />
            </div>
            <div>
              <CardTitle>Notification Preferences</CardTitle>
              <CardDescription>
                Configure event alerts for automated processing pipelines and review resolutions.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <form onSubmit={handleSave}>
          <CardContent className="space-y-6">
            {isSaved && (
              <Alert variant="success" title="Notifications Configured">
                Notification event subscription preferences have been updated.
              </Alert>
            )}

            {/* Delivery Channel Status */}
            <div className="p-4 bg-[#F7F9FC] border border-[#DCE6F0] rounded-xl flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 shrink-0">
                  <Mail className="h-4 w-4" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-[#0F2747] flex items-center gap-2">
                    Email Delivery Channel
                    <Badge variant="success" dot dotColor="bg-emerald-500">
                      Active
                    </Badge>
                  </h4>
                  <p className="text-xs text-[#58708F]">
                    Connected to backend SMTP system (noreply@crosscheckpro.com)
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 text-xs text-[#58708F]">
                <span>In-App Toasts:</span>
                <span className="font-semibold text-emerald-600">Enabled</span>
              </div>
            </div>

            {/* Event Toggles */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">
                Trigger Events
              </h4>
              <div className="divide-y divide-[#DCE6F0] border border-[#DCE6F0] rounded-xl bg-white overflow-hidden">
                {eventList.map((item) => {
                  const Icon = item.icon;
                  const isChecked = settings[item.key];
                  return (
                    <div
                      key={item.key}
                      onClick={() => toggleEvent(item.key)}
                      className="flex items-start justify-between p-4 hover:bg-[#F7F9FC]/60 transition-colors cursor-pointer"
                    >
                      <div className="flex items-start gap-3 pr-4">
                        <div
                          className={`flex h-8 w-8 items-center justify-center rounded-lg mt-0.5 shrink-0 ${
                            isChecked
                              ? "bg-sky-50 text-[#0EA5E9]"
                              : "bg-slate-100 text-slate-400"
                          }`}
                        >
                          <Icon className="h-4 w-4" />
                        </div>
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold text-[#0F2747]">
                              {item.title}
                            </span>
                            {item.badge && (
                              <span
                                className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                                  item.badge === "Critical"
                                    ? "bg-rose-50 text-rose-700 border border-rose-200"
                                    : "bg-amber-50 text-amber-700 border border-amber-200"
                                }`}
                              >
                                {item.badge}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-[#58708F]">
                            {item.description}
                          </p>
                        </div>
                      </div>

                      <div className="pt-1">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => {}} // Handled by container click
                          className="h-4 w-4 rounded text-[#0EA5E9] focus:ring-[#0EA5E9] border-slate-300 pointer-events-none"
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Email Frequency */}
            <div className="space-y-2 pt-2 border-t border-[#DCE6F0]">
              <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">
                Email Notification Frequency
              </label>
              <select
                value={settings.emailDigest}
                onChange={(e) =>
                  setSettings((prev) => ({
                    ...prev,
                    emailDigest: e.target.value as NotificationSettings["emailDigest"],
                  }))
                }
                className="w-full sm:w-80 h-10 px-3 rounded-lg border border-[#DCE6F0] bg-white text-sm text-[#0F2747] focus:outline-none focus:ring-2 focus:ring-[#0EA5E9]"
              >
                <option value="instant">Instant Dispatch (Per Completed Job)</option>
                <option value="daily">Daily Summary Digest</option>
                <option value="weekly">Weekly Team Overview</option>
                <option value="disabled">Do Not Send Email Notifications</option>
              </select>
            </div>
          </CardContent>

          <CardFooter className="flex justify-between items-center border-t border-[#DCE6F0] bg-[#FAFCFF] py-3.5">
            <span className="text-xs text-[#58708F]">
              Preferences apply across automated worker and review alerts.
            </span>
            <Button type="submit" className="min-w-[130px]">
              {isSaved ? (
                <>
                  <Check className="mr-2 h-4 w-4" />
                  Saved
                </>
              ) : (
                "Save Preferences"
              )}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
