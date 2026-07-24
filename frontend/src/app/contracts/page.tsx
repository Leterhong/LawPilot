"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  api,
  type ContractOut,
  type ContractType,
  type ContractStatus,
} from "@/lib/api";
import {
  contractTypeLabels,
  contractStatusLabels,
  contractStatusTone,
  contractRiskLevelLabels,
  contractRiskLevelTone,
  contractAllowedExtensions,
} from "@/lib/constants";
import { AppShell } from "@/components/AppShell";
import { Badge, Button, Card, Input, Spinner } from "@/components/ui";
import { cn } from "@/lib/utils";

const TYPE_OPTIONS: ("all" | ContractType)[] = [
  "all",
  "rent",
  "labor",
  "sales",
  "service",
  "nda",
  "cooperation",
  "loan",
  "purchase",
  "other",
];
const STATUS_OPTIONS: ("all" | ContractStatus)[] = [
  "all",
  "uploaded",
  "analyzed",
  "parsing",
  "error",
];

export default function ContractsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const [items, setItems] = useState<ContractOut[]>([]);
  const [total, setTotal] = useState(0);
  const [ready, setReady] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [typeFilter, setTypeFilter] = useState<"all" | ContractType>("all");
  const [statusFilter, setStatusFilter] = useState<"all" | ContractStatus>("all");
  const [q, setQ] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.contracts.list({
        contract_type: typeFilter === "all" ? undefined : typeFilter,
        status: statusFilter === "all" ? undefined : statusFilter,
        page: 1,
        page_size: 50,
      });
      setItems(data.items);
      setTotal(data.total);
      setErr(null);
    } catch (e: any) {
      setErr(e.message || "加载失败");
    } finally {
      setReady(true);
    }
  }, [typeFilter, statusFilter]);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    load();
  }, [user, loading, router, load]);

  const filtered = useMemo(() => {
    if (!q.trim()) return items;
    const kw = q.trim().toLowerCase();
    return items.filter((it) => (it.title || "").toLowerCase().includes(kw));
  }, [items, q]);

  function validateFile(file: File): string | null {
    const name = file.name.toLowerCase();
    const ok = contractAllowedExtensions.some((ext) => name.endsWith(ext));
    if (!ok) return `不支持的文件类型，允许：${contractAllowedExtensions.join("、")}`;
    return null;
  }

  async function doUpload(file: File, title?: string) {
    const v = validateFile(file);
    if (v) {
      setUploadMsg(v);
      return;
    }
    setUploading(true);
    setUploadMsg(null);
    try {
      const res = await api.contracts.upload(file, title || file.name);
      setUploadMsg(
        `已上传「${res.contract.title}」：${res.parsed ? "解析成功" : "未提取到文本"}${
          res.ocr_used ? "（已启用 OCR）" : ""
        }`
      );
      await load();
      router.push(`/contracts/${res.contract.id}`);
    } catch (e: any) {
      setUploadMsg(e.message || "上传失败");
    } finally {
      setUploading(false);
    }
  }

  function onPick(files: FileList | null) {
    if (files && files[0]) doUpload(files[0]);
  }

  async function onDelete(it: ContractOut) {
    if (!confirm(`确认删除合同「${it.title || "未命名"}」？此操作不可恢复。`)) return;
    try {
      await api.contracts.remove(it.id);
      await load();
    } catch (e: any) {
      setErr(e.message || "删除失败");
    }
  }

  if (loading || !ready) {
    return (
      <AppShell>
        <div className="flex items-center justify-center py-20 text-gray-400">
          <Spinner className="mr-2" /> 加载中…
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">合同智能中心</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            上传合同，AI 自动解析、识别风险、逐条解释条款并给出修改建议。
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <Link href="/contracts/reminders">
            <Button variant="outline" className="gap-1.5">
              🔔 提醒中心
            </Button>
          </Link>
          <Badge tone="gray">共 {total} 份</Badge>
        </div>
      </div>

      {/* 上传区 */}
      <Card className="mb-6">
        <div
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            onPick(e.dataTransfer.files);
          }}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition",
            dragOver
              ? "border-brand-400 bg-brand-50/50 dark:bg-brand-500/10"
              : "border-gray-200 hover:border-brand-300 dark:border-white/10"
          )}
        >
          <div className="text-3xl">📄</div>
          <div className="mt-2 text-sm font-medium">
            {uploading ? "上传中…" : "点击或拖拽文件到此处上传合同"}
          </div>
          <div className="mt-1 text-xs text-gray-400">
            支持 PDF / DOCX / TXT / Markdown / 图片（PNG·JPG），图片将自动 OCR
          </div>
          <input
            ref={fileRef}
            type="file"
            accept={contractAllowedExtensions.join(",")}
            className="hidden"
            onChange={(e) => onPick(e.target.files)}
          />
        </div>
        {uploading && (
          <div className="mt-3 flex items-center text-sm text-gray-500">
            <Spinner className="mr-2" /> 正在解析与分类…
          </div>
        )}
        {uploadMsg && (
          <div className="mt-3 rounded-xl bg-brand-50 px-3 py-2 text-sm text-brand-700 dark:bg-brand-500/15 dark:text-brand-300">
            {uploadMsg}
          </div>
        )}
      </Card>

      {/* 筛选 */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="按标题搜索…"
          className="max-w-xs"
        />
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as "all" | ContractType)}
          className="rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
        >
          {TYPE_OPTIONS.map((t) => (
            <option key={t} value={t}>
              {t === "all" ? "全部类型" : contractTypeLabels[t] ?? t}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as "all" | ContractStatus)}
          className="rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s === "all" ? "全部状态" : contractStatusLabels[s] ?? s}
            </option>
          ))}
        </select>
      </div>

      {err && (
        <div className="mb-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/15 dark:text-red-300">
          {err}
        </div>
      )}

      {/* 列表 */}
      {filtered.length === 0 ? (
        <Card className="text-center text-sm text-gray-400">
          还没有合同，上传一份试试吧。
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((it) => (
            <Card key={it.id} className="flex flex-col">
              <div className="flex items-start justify-between gap-2">
                <Link
                  href={`/contracts/${it.id}`}
                  className="line-clamp-2 font-medium hover:text-brand-600 dark:hover:text-brand-300"
                >
                  {it.title || "未命名合同"}
                </Link>
                <button
                  onClick={() => onDelete(it)}
                  className="shrink-0 text-xs text-gray-400 hover:text-red-500"
                  title="删除"
                >
                  删除
                </button>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge tone="brand">
                  {it.contract_type ? contractTypeLabels[it.contract_type] ?? it.contract_type : "未分类"}
                </Badge>
                <Badge tone={contractStatusTone[it.status] ?? "gray"}>
                  {contractStatusLabels[it.status] ?? it.status}
                </Badge>
                <Badge tone={contractRiskLevelTone[it.risk_level] ?? "gray"}>
                  {contractRiskLevelLabels[it.risk_level] ?? it.risk_level}
                </Badge>
              </div>
              {it.summary && (
                <p className="mt-3 line-clamp-3 text-sm text-gray-500 dark:text-gray-400">
                  {it.summary}
                </p>
              )}
              <div className="mt-auto flex items-center justify-between pt-4 text-xs text-gray-400">
                <span>风险分 {it.risk_score}</span>
                <Link
                  href={`/contracts/${it.id}`}
                  className="font-medium text-brand-600 hover:underline dark:text-brand-300"
                >
                  查看 / 分析 →
                </Link>
              </div>
            </Card>
          ))}
        </div>
      )}
    </AppShell>
  );
}
