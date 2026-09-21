"use client";

import React, { useState, useRef, useEffect } from "react";
import { MoreVertical, Edit3, Trash2 } from "lucide-react";
import { Project, Role } from "@/lib/api/types";

interface ProjectActionMenuProps {
  project: Project;
  userRole?: Role;
  onEdit?: (project: Project) => void;
  onDelete?: (project: Project) => void;
}

export function ProjectActionMenu({
  project,
  userRole = "ADMIN",
  onEdit,
  onDelete,
}: ProjectActionMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const canMutate = userRole === "ADMIN";

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  if (!canMutate || (!onEdit && !onDelete)) {
    return null;
  }

  return (
    <div className="relative inline-block text-left" ref={menuRef}>
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setIsOpen(!isOpen);
        }}
        className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#DCE6F0] bg-white text-[#58708F] hover:text-[#0F2747] hover:bg-[#F7F9FC] hover:border-slate-300 transition-colors cursor-pointer shadow-2xs"
        aria-label="More project actions"
      >
        <MoreVertical className="h-4 w-4" />
      </button>

      {isOpen && (
        <div className="absolute right-0 z-50 mt-1 w-44 origin-top-right rounded-xl border border-[#DCE6F0] bg-white py-1 shadow-xl animate-in fade-in zoom-in-95 duration-100 focus:outline-none">
          {onEdit && (
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                setIsOpen(false);
                onEdit(project);
              }}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-xs font-semibold text-[#0F2747] hover:bg-[#F7F9FC] hover:text-[#0EA5E9] transition-colors text-left cursor-pointer"
            >
              <Edit3 className="h-3.5 w-3.5 text-[#58708F]" />
              <span>Edit Details</span>
            </button>
          )}

          {onDelete && (
            <>
              {onEdit && <div className="my-1 border-t border-[#DCE6F0]" />}
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setIsOpen(false);
                  onDelete(project);
                }}
                className="flex w-full items-center gap-2.5 px-3.5 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 transition-colors text-left cursor-pointer"
              >
                <Trash2 className="h-3.5 w-3.5 text-rose-500" />
                <span>Delete Project</span>
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}

