import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 select-none",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-[#0F2747] text-white",
        secondary:
          "border-[#E2E8F0] bg-[#F1F5F9] text-[#475569] border",
        outline:
          "text-[#58708F] border border-[#DCE6F0] bg-white",
        success:
          "border-[#BBF7D0] bg-[#DCFCE7] text-[#15803D] border",
        warning:
          "border-[#FDE68A] bg-[#FEF3C7] text-[#B45309] border",
        destructive:
          "border-[#FECACA] bg-[#FEE2E2] text-[#B91C1C] border",
        info:
          "border-[#BAE6FD] bg-[#E0F2FE] text-[#0284C7] border",
        purple:
          "border-[#E9D5FF] bg-[#F3E8FF] text-[#6D28D9] border",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {
  dot?: boolean;
  dotColor?: string;
}

function Badge({
  className,
  variant,
  dot,
  dotColor,
  children,
  ...props
}: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props}>
      {dot && (
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            dotColor || "bg-current"
          )}
        />
      )}
      {children}
    </div>
  );
}

export { Badge, badgeVariants };
