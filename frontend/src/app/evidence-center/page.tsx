"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  api,
  type EvidenceFileOut,
  type EvidenceFileCategory,
  type EvidenceFileStatus,
  type CaseOut,
} from "@/lib/api";
import {
  evidenceFileCategoryLabels,
  evidenceFileCategoryTone,
  evidenceFileStatusLabels,
  evidenceFileStatusTone,
  evidenceAllowedExtensions,
} from "@/lib/constants";
import { AppShell } from "@/components/AppShell";
import { Badge, Button, Card, Input, Spinner } from "@/components/ui";
import { cn } from "@/lib/utils";

const CATEGORY_OPTIONS = Object.keys(evidenceFileCategoryLabels) as EvidenceFileCategory[];
const STATUS_OPTIONS = Object.keys(evidenceFileStatusLabels) as EvidenceFileStatus[];

function formatSize(n: number | null): string {
  if (n == null) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(s: string | null): string {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return s;
  }
}

export default function EvidenceCenterPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const [items, setItems] = useState<EvidenceFileOut[]>([]);
  const [total, setTotal] = useState(0);
  const [ready, setReady] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [categoryFilter, setCategoryFilter] = useState<"all" | EvidenceFileCategory>("all");
  const [statusFilter, setStatusFilter] = useState<"all" | EvidenceFileStatus>("all");
  const [caseFilter, setCaseFilter] = useState<string>("all");
  const [q, setQ] = useState("");
  const [cases, setCases] = useState<CaseOut[]>([]);

  const [source, setSource] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.evidenceCenter.list({
        category: categoryFilter === "all" ? undefined : categoryFilter,
        status: statusFilter === "all" ? undefined : statusFilter,
        case_id: caseFilter === "all" ? undefined : caseFilter,
        q: q.trim() || undefined,
        page: 1,
        page_size: 50,
      });
      setItems(data.items);
      setTotal(data.total);
      setErr(null);
    } catch (e: any) {
      setErr(e?.message || "加载失败");
    } finally {
      setReady(true);
    }
  }, [categoryFilter, statusFilter, caseFilter, q]);

  const loadCases = useCallback(async () => {
    try {
      const data = await api.listCases({ page: 1, page_size: 200 });
      setCases(data.items);
    } catch {
      /* 案件筛选可选，失败不影响主列表 */
    }
  }, []);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    loadCases();
    load();
  }, [user, loading, router, load, loadCases]);

  const filtered = useMemo(() => {
    if (!q.trim()) return items;
    const kw = q.trim().toLowerCase();
    return items.filter((it) => (it.name || "").toLowerCase().includes(kw));
  }, [items, q]);

  function validateFile(file: File): string | null {
    const name = file.name.toLowerCase();
    const ok = evidenceAllowedExtensions.some((ext) => name.endsWith(ext));
    if (!ok)
      return `「${file.name}」类型不支持，允许：${evidenceAllowedExtensions.join("、")}`;
    return null;
  }

  async function doUpload(files: File[]) {
    if (files.length === 0) return;
    const bad = files.map(validateFile).filter(Boolean) as string[];
    if (bad.length === files.length) {
      setUploadMsg(bad[0]);
      return;
    }
    setUploading(true);
    setUploadMsg(null);
    try {
      const res = await api.evidenceCenter.upload(files, {
        case_id: caseFilter === "all" ? undefined : caseFilter,
        source: source.trim() || undefined,
      });
      const failed = res.items.filter((i) => !i.stored);
      if (failed.length === 0) {
        setUploadMsg(`成功上传 ${res.succeeded} 个证据文件。`);
      } else {
        setUploadMsg(
          `上传完成：${res.succeeded} 成功 / ${failed.length} 失败。失败项：${failed
            .map((f) => `${f.file.name}（${f.note}）`)
            .join("；")}`
        );
      }
      setSource("");
      await load();
    } catch (e: any) {
      setUploadMsg(e?.message || "上传失败");
    } finally {
      setUploading(false);
    }
  }

  function onPick(files: FileList | null) {
    if (files && files.length) doUpload(Array.from(files));
  }

  async function onDelete(it: EvidenceFileOut) {
    if (!confirm(`确认删除证据「${it.name}」？此操作不可恢复，且会一并删除本地文件。`))
      return;
    try {
      await api.evidenceCenter.remove(it.id);
      await load();
    } catch (e: any) {
      setErr(e?.message || "删除失败");
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
          <h1 className="text-2xl font-semibold tracking-tight">智能证据中心</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            上传合同 / 付款 / 聊天 / 录音 / 网页等素材，AI 自动解析、评估证明力、梳理证据链并生成报告。
          </p>
        </div>
        <Badge tone="gray">共 {total} 份</Badge>
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
          <div className="text-3xl">🗂️</div>
          <div className="mt-2 text-sm font-medium">
            {uploading ? "上传中…" : "点击或拖拽文件到此处（可批量上传）"}
          </div>
          <div className="mt-1 text-xs text-gray-400">
            支持 PDF / Word / 图片 / 音视频 / 邮件 / 网页 等常见格式
          </div>
          <input
            ref={fileRef}
            type="file"
            multiple
            accept={evidenceAllowedExtensions.join(",")}
            className="hidden"
            onChange={(e) => onPick(e.target.files)}
          />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Input
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="来源说明（可选，如：微信截图 / 银行流水）"
            className="max-w-xs"
          />
          <select
            value={caseFilter}
            onChange={(e) => setCaseFilter(e.target.value)}
            className="rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
          >
            <option value="all">不归入案件</option>
            {cases.map((c) => (
              <option key={c.id} value={c.id}>
                归入：{c.title}
              </option>
            ))}
          </select>
        </div>
        {uploading && (
          <div className="mt-3 flex items-center text-sm text-gray-500">
            <Spinner className="mr-2" /> 正在上传与落盘…
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
          placeholder="按文件名搜索…"
          className="max-w-xs"
        />
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value as "all" | EvidenceFileCategory)}
          className="rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
        >
          <option value="all">全部类型</option>
          {CATEGORY_OPTIONS.map((t) => (
            <option key={t} value={t}>
              {evidenceFileCategoryLabels[t]}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as "all" | EvidenceFileStatus)}
          className="rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
        >
          <option value="all">全部状态</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {evidenceFileStatusLabels[s]}
            </option>
          ))}
        </select>
        {cases.length > 0 && (
          <select
            value={caseFilter}
            onChange={(e) => setCaseFilter(e.target.value)}
            className="rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
          >
            <option value="all">全部归属</option>
            {cases.map((c) => (
              <option key={c.id} value={c.id}>
                案件：{c.title}
              </option>
            ))}
          </select>
        )}
      </div>

      {err && (
        <div className="mb-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/15 dark:text-red-300">
          {err}
        </div>
      )}

      {/* 列表 */}
      {filtered.length === 0 ? (
        <Card className="text-center text-sm text-gray-400">
          还没有证据文件，上传一些素材试试吧。
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((it) => (
            <Card key={it.id} className="flex flex-col">
              <div className="flex items-start justify-between gap-2">
                <Link
                  href={`/evidence-center/${it.id}`}
                  className="line-clamp-2 font-medium hover:text-brand-600 dark:hover:text-brand-300"
                >
                  {it.name}
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
                <Badge tone={evidenceFileCategoryTone[it.category] ?? "gray"}>
                  {evidenceFileCategoryLabels[it.category] ?? it.category}
                </Badge>
                <Badge tone={evidenceFileStatusTone[it.status] ?? "gray"}>
                  {evidenceFileStatusLabels[it.status] ?? it.status}
                </Badge>
              </div>
              <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-400">
                <span>{it.file_type ? it.file_type.toUpperCase() : "—"}</span>
                <span>{formatSize(it.size_bytes)}</span>
                {it.source && <span>来源：{it.source}</span>}
              </div>
              {it.tags && it.tags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {it.tags.map((t, i) => (
                    <span
                      key={i}
                      className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500 dark:bg-white/10 dark:text-gray-300"
                    >
                      #{t}
                    </span>
                  ))}
                </div>
              )}
              <div className="mt-auto flex items-center justify-between pt-4 text-xs text-gray-400">
                <span>{formatDate(it.created_at)}</span>
                <Link
                  href={`/evidence-center/${it.id}`}
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
