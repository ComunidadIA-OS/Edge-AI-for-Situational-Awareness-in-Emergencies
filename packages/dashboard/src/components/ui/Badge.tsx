import { type ReactNode } from "react";
import { cn } from "@/src/lib/utils";

type BadgeVariant = "default" | "success" | "warning" | "error" | "info";

type Props = {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
};

const variantStyles: Record<BadgeVariant, string> = {
  default: "bg-zinc-700 text-zinc-200",
  success: "bg-emerald-900/60 text-emerald-300 border border-emerald-700/50",
  warning: "bg-amber-900/60 text-amber-300 border border-amber-700/50",
  error: "bg-red-900/60 text-red-300 border border-red-700/50",
  info: "bg-sky-900/60 text-sky-300 border border-sky-700/50",
};

export function Badge({ variant = "default", children, className }: Props) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        variantStyles[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
