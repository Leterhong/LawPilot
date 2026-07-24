// AI 能力中心通用模态框（轻量，无第三方依赖）。
"use client";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui";

export function Modal({
  open,
  title,
  onClose,
  children,
  footer,
  maxWidth = "max-w-2xl",
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
  maxWidth?: string;
}) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 py-10"
      onClick={onClose}
    >
      <div
        className={cn(
          "w-full rounded-2xl border border-gray-100 bg-white p-6 shadow-xl dark:border-white/10 dark:bg-[#11151c]",
          maxWidth
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-white/10"
            aria-label="关闭"
          >
            ✕
          </button>
        </div>
        {children}
        {footer && <div className="mt-6 flex justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}

// 表单字段：标签 + 控件
export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">{label}</span>
        {hint && <span className="text-xs text-gray-400">{hint}</span>}
      </div>
      {children}
    </label>
  );
}

export function Banner({
  tone = "gray",
  children,
}: {
  tone?: "gray" | "green" | "red" | "amber";
  children: React.ReactNode;
}) {
  const tones = {
    gray: "bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300",
    green: "bg-green-50 text-green-700 dark:bg-green-500/15 dark:text-green-300",
    red: "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300",
    amber: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  } as const;
  return (
    <div className={cn("rounded-xl px-3 py-2 text-sm", tones[tone])}>{children}</div>
  );
}

export { Button };
