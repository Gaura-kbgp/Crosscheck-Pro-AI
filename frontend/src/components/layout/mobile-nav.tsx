"use client";

import React from "react";
import { Sidebar } from "./sidebar";
import { X } from "lucide-react";

interface MobileNavProps {
  isOpen: boolean;
  onClose: () => void;
}

export function MobileNav({ isOpen, onClose }: MobileNavProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="fixed inset-y-0 left-0 z-50 flex w-72 flex-col bg-white shadow-2xl animate-in slide-in-from-left duration-200">
        <div className="absolute right-3 top-3.5">
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-900"
            aria-label="Close menu"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <Sidebar className="w-full border-r-0" />
      </div>
    </div>
  );
}
