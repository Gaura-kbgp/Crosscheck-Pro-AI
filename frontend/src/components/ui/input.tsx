import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, error, leftIcon, rightIcon, ...props }, ref) => {
    return (
      <div className="w-full">
        <div className="relative flex items-center">
          {leftIcon && (
            <div className="absolute left-3 flex items-center pointer-events-none text-[#58708F]">
              {leftIcon}
            </div>
          )}
          <input
            type={type}
            className={cn(
              "flex h-9.5 w-full rounded-lg border border-[#DCE6F0] bg-white px-3 py-1 text-sm shadow-2xs transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-[#58708F] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#0EA5E9]/20 focus-visible:border-[#0EA5E9] disabled:cursor-not-allowed disabled:opacity-50 text-[#0F2747]",
              leftIcon && "pl-9",
              rightIcon && "pr-9",
              error && "border-[#DC2626] focus-visible:ring-[#DC2626]/20 focus-visible:border-[#DC2626]",
              className
            )}
            ref={ref}
            {...props}
          />
          {rightIcon && (
            <div className="absolute right-3 flex items-center text-[#58708F]">
              {rightIcon}
            </div>
          )}
        </div>
        {error && <p className="mt-1.5 text-xs text-[#DC2626] font-medium">{error}</p>}
      </div>
    );
  }
);
Input.displayName = "Input";

export { Input };
