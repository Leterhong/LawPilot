// 轻量 UI 基础组件（shadcn 风格，纯 Tailwind）。
// 不依赖 Radix，保持极简与可运行。
import { cn } from "@/lib/utils";
import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, TextareaHTMLAttributes } from "react";

// ---------------------------
// Button
// ---------------------------
const buttonVariants = {
  primary: "bg-brand-500 text-white hover:bg-brand-600 shadow-soft",
  secondary:
    "bg-gray-100 text-gray-900 hover:bg-gray-200 dark:bg-white/10 dark:text-gray-100 dark:hover:bg-white/15",
  outline:
    "border border-gray-200 bg-white hover:bg-gray-50 dark:border-white/10 dark:bg-transparent dark:hover:bg-white/5",
  ghost: "hover:bg-gray-100 dark:hover:bg-white/10",
  danger: "bg-red-500 text-white hover:bg-red-600",
} as const;

const buttonSizes = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-4 py-2 text-sm",
  lg: "px-5 py-2.5 text-base",
} as const;

export function Button({
  className,
  variant = "primary",
  size = "md",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof buttonVariants;
  size?: keyof typeof buttonSizes;
}) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition focus:outline-none focus:ring-4 focus:ring-brand-100 disabled:cursor-not-allowed disabled:opacity-50 dark:focus:ring-brand-500/20",
        buttonVariants[variant],
        buttonSizes[size],
        className
      )}
      {...props}
    />
  );
}

// ---------------------------
// Card
// ---------------------------
export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-gray-100 bg-white p-5 shadow-soft dark:border-white/10 dark:bg-white/5",
        className
      )}
      {...props}
    />
  );
}

// ---------------------------
// Input
// ---------------------------
export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "w-full rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm outline-none transition placeholder:text-gray-400 focus:border-brand-400 focus:ring-4 focus:ring-brand-100 dark:border-white/10 dark:bg-white/5 dark:text-gray-100 dark:focus:ring-brand-500/20",
        className
      )}
      {...props}
    />
  );
}

// ---------------------------
// Textarea
// ---------------------------
export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm outline-none transition placeholder:text-gray-400 focus:border-brand-400 focus:ring-4 focus:ring-brand-100 dark:border-white/10 dark:bg-white/5 dark:text-gray-100 dark:focus:ring-brand-500/20",
        className
      )}
      {...props}
    />
  );
}

// ---------------------------
// Badge
// ---------------------------
const badgeTones = {
  brand: "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300",
  gray: "bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300",
  green: "bg-green-50 text-green-700 dark:bg-green-500/15 dark:text-green-300",
  red: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
  amber: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
} as const;

export function Badge({
  className,
  tone = "gray",
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: keyof typeof badgeTones }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        badgeTones[tone],
        className
      )}
      {...props}
    />
  );
}

// ---------------------------
// Spinner
// ---------------------------
export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent text-brand-500",
        className
      )}
      role="status"
      aria-label="加载中"
    />
  );
}
