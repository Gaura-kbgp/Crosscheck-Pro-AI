import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import { AlertCircle, CheckCircle2, Info, AlertTriangle } from "lucide-react";

const alertVariants = cva(
  "relative w-full rounded-xl border p-4 [&>svg~*]:pl-7 [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg]:text-foreground text-sm",
  {
    variants: {
      variant: {
        default: "bg-white text-slate-900 border-slate-200",
        info: "bg-sky-50 text-sky-900 border-sky-200 [&>svg]:text-sky-600",
        success: "bg-emerald-50 text-emerald-900 border-emerald-200 [&>svg]:text-emerald-600",
        warning: "bg-amber-50 text-amber-900 border-amber-200 [&>svg]:text-amber-600",
        destructive:
          "bg-rose-50 text-rose-900 border-rose-200 [&>svg]:text-rose-600",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

const iconMap = {
  default: Info,
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  destructive: AlertCircle,
};

export interface AlertProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof alertVariants> {
  title?: string;
  hideIcon?: boolean;
}

const Alert = React.forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant = "default", title, hideIcon, children, ...props }, ref) => {
    const IconComponent = iconMap[variant || "default"];

    return (
      <div
        ref={ref}
        role="alert"
        className={cn(alertVariants({ variant }), className)}
        {...props}
      >
        {!hideIcon && <IconComponent className="h-4 w-4" />}
        {title && <h5 className="mb-1 font-semibold leading-none tracking-tight">{title}</h5>}
        <div className="text-sm [&_p]:leading-relaxed">{children}</div>
      </div>
    );
  }
);
Alert.displayName = "Alert";

export { Alert, alertVariants };
