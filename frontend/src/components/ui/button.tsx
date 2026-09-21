import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-semibold transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 select-none cursor-pointer",
  {
    variants: {
      variant: {
        default:
          "bg-[#0EA5E9] text-white shadow-2xs hover:bg-[#0284C7] active:scale-[0.98]",
        secondary:
          "border border-[#DCE6F0] bg-white text-[#0F2747] shadow-2xs hover:bg-[#F7F9FC] active:scale-[0.98]",
        outline:
          "border border-[#DCE6F0] bg-white text-[#0F2747] shadow-2xs hover:bg-[#F7F9FC] active:scale-[0.98]",
        ghost:
          "bg-transparent text-[#0284C7] hover:bg-[#E0F2FE] hover:text-[#0284C7] active:scale-[0.98]",
        destructive:
          "bg-[#DC2626] text-white shadow-2xs hover:bg-[#B91C1C] active:scale-[0.98]",
        success:
          "bg-[#16A34A] text-white shadow-2xs hover:bg-[#15803D] active:scale-[0.98]",
        warning:
          "bg-[#F59E0B] text-white shadow-2xs hover:bg-[#D97706] active:scale-[0.98]",
        purple:
          "bg-[#7C3AED] text-white shadow-2xs hover:bg-[#6D28D9] active:scale-[0.98]",
        link: "text-[#0284C7] underline-offset-4 hover:underline hover:text-[#0EA5E9]",
        white:
          "bg-white text-[#0F2747] border border-[#DCE6F0] shadow-2xs hover:bg-[#F7F9FC] active:scale-[0.98]",
      },
      size: {
        default: "h-9.5 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-11 rounded-lg px-6 text-base",
        icon: "h-9 w-9 rounded-lg p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant,
      size,
      isLoading,
      leftIcon,
      rightIcon,
      children,
      disabled,
      ...props
    },
    ref
  ) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
        {!isLoading && leftIcon}
        {children}
        {!isLoading && rightIcon}
      </button>
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
