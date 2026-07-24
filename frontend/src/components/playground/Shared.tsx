// AI Playground 公共 UI 小部件（评分条 / 参数滑块 / 代码输入框）。
"use client";

import { cn } from "@/lib/utils";
import { Textarea } from "@/components/ui";

// 0-100 彩色评分条
export function ScoreBar({ value, max = 100 }: { value: number | null; max?: number }) {
  const v = value ?? 0;
  const pct = Math.max(0, Math.min(100, (v / max) * 100));
  const tone =
    pct >= 80 ? "bg-green-500" : pct >= 60 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100 dark:bg-white/10">
        <div className={cn("h-full rounded-full", tone)} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right text-xs tabular-nums text-gray-500">
        {value == null ? "—" : v.toFixed(1)}
      </span>
    </div>
  );
}

// 参数滑块（Temperature / Top P / Max Token）
export function ParamSlider({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <label className="block">
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-medium text-gray-600 dark:text-gray-300">{label}</span>
        <span className="tabular-nums text-gray-400">{value}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-brand-500"
      />
    </label>
  );
}

// 代码编辑风格输入框（等宽）
export function CodeTextarea({
  className,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <Textarea
      className={cn("font-mono text-[13px] leading-relaxed", className)}
      {...props}
    />
  );
}

// 指标小标签
export function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-100 bg-gray-50 px-3 py-2 dark:border-white/10 dark:bg-white/5">
      <div className="text-xs text-gray-400">{label}</div>
      <div className="mt-0.5 text-sm font-medium tabular-nums">{value}</div>
    </div>
  );
}
