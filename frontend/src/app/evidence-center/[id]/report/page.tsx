"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  api,
  type EvidenceReportOut,
  type EvidenceReportType,
  type EvidenceDetailOut,
} from "@/lib/api";
import {
  evidenceReportLabels,
} from "@/lib/constants";
import { AppShell } from "@/components/AppShell";
import { Badge, Button, Card, Spinner } from "@/components/ui";
import { Markdown } from "@/components/Markdown";
import { cn } from "@/lib/utils";

const REPORT_TABS: { type: EvidenceReportType; label: string }[] = [
  { type: "directory", label: "证据目录" },
  { type: "score", label: "证据评分" },
  { type: "missing", label: "缺失分析" },
  { type: "strategy", label: "证据策略" },
  { type: "full", label: "综合报告" },
];

function reportMarkdown(r: EvidenceReportOut | null): string {
  const md = (r?.content as Record<string, unknown> | null)?.markdown;
  return typeof md === "string" ? md : "";
}

export default function EvidenceReportPage() {
  const params = useParams();
  const router = useRouter();
  const { token } = useAuth();
  const id = typeof params.id === "string" ? params.id : Array.isArray(params.id) ? params.id[0] : "";

  const [reportType, setReportType] = useState<EvidenceReportType>("directory");
  const [report, setReport] = useState<EvidenceReportOut | null>(null);
  const [existing, setExisting] = useState<EvidenceReportOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [aiConfigured, setAiConfigured] = useState<boolean | null>(null);

  const loadAiStatus = useCallback(async () => {
    try {
      const s = await api.aiCenter.status();
      setAiConfigured(s.ai_configured);
    } catch {
      setAiConfigured(null);
    }
  }, []);

  const loadExisting = useCallback(
    async (caseId: string | null) => {
      if (!token) return;
      try {
        const list = await api.evidenceCenter.listReports(caseId ?? undefined);
        setExisting(list);
      } catch {
        /* 忽略：不影响主流程 */
      }
    },
    [token]
  );

  const loadReport = useCallback(
    async (type: EvidenceReportType, caseId: string | null, regenerate = false) => {
      if (!token || !id) return;
      setLoading(true);
      setErr(null);
      try {
        const r = await api.evidenceCenter.generateReport({
          evidence_ids: [id],
          case_id: caseId,
          report_type: type,
          regenerate,
        });
        setReport(r);
      } catch (e: any) {
        setErr(e?.message || "报告生成失败");
        setReport(null);
      } finally {
        setLoading(false);
      }
    },
    [token, id]
  );

  // 先取证据详情拿 case_id，再并行加载
  useEffect(() => {
    if (!token) {
      router.replace("/login");
      return;
    }
    let caseId: string | null = null;
    (async () => {
      try {
        const detail: EvidenceDetailOut = await api.evidenceCenter.get(id);
        caseId = detail.case_id;
        await loadExisting(caseId);
        await loadReport(reportType, caseId);
        await loadAiStatus();
      } catch (e: any) {
        setErr(e?.message || "加载失败");
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, router, id]);

  const onRegenerate = async () => {
    if (!token || !id) return;
    setGenerating(true);
    setErr(null);
    try {
      const r = await api.evidenceCenter.generateReport({
        evidence_ids: [id],
        report_type: reportType,
        regenerate: true,
      });
      setReport(r);
      await loadExisting(r.case_id ?? null);
    } catch (e: any) {
      setErr(e?.message || "重新生成失败");
    } finally {
      setGenerating(false);
    }
  };

  const onDownload = (fmt: "word" | "pdf" | "markdown") => {
    if (!report) return;
    const ext = fmt === "word" ? "docx" : fmt;
    api.evidenceCenter.downloadReport(report.id, fmt, `${report.title}.${ext}`);
  };

  const md = reportMarkdown(report);

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl px-4 py-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <Link
              href={`/evidence-center/${id}`}
              className="text-sm text-blue-600 hover:underline dark:text-blue-400"
            >
              ← 返回证据详情
            </Link>
            <h1 className="mt-1 text-xl font-bold">证据报告</h1>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => onDownload("word")} disabled={!report}>
              下载 Word
            </Button>
            <Button variant="outline" size="sm" onClick={() => onDownload("pdf")} disabled={!report}>
              下载 PDF
            </Button>
            <Button variant="outline" size="sm" onClick={() => onDownload("markdown")} disabled={!report}>
              下载 MD
            </Button>
            <Button onClick={onRegenerate} disabled={generating || loading}>
              {generating ? (
                <>
                  <Spinner className="mr-1" /> 生成中…
                </>
              ) : (
                "重新生成"
              )}
            </Button>
          </div>
        </div>

        {aiConfigured === false && (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
            <span>
              当前未配置大模型，报告为规则模板。在「AI 能力中心」配置并启用模型后，可生成 AI 辅助的深度报告。
            </span>
            <Link href="/settings/ai-center">
              <Button variant="outline" className="shrink-0">
                前往配置大模型
              </Button>
            </Link>
          </div>
        )}

        {/* 报告类型 Tab */}
        <div className="mb-4 flex flex-wrap gap-2">
          {REPORT_TABS.map((t) => {
            const has = existing.some((e) => e.report_type === t.type);
            const active = t.type === reportType;
            return (
              <button
                key={t.type}
                onClick={() => {
                  setReportType(t.type);
                  // 切换类型时立即生成 / 取回
                  loadReport(t.type, report?.case_id ?? null);
                }}
                className={cn(
                  "rounded-full border px-3 py-1 text-sm transition",
                  active
                    ? "border-blue-500 bg-blue-500 text-white"
                    : "border-gray-200 bg-white text-gray-600 hover:border-blue-300 dark:border-white/10 dark:bg-white/5 dark:text-gray-300"
                )}
              >
                {t.label}
                {has && !active && (
                  <span className="ml-1 text-[10px] text-green-500">●</span>
                )}
              </button>
            );
          })}
        </div>

        {err && (
          <div className="mb-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/15 dark:text-red-300">
            {err}
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-16 text-gray-400">
            <Spinner className="mr-2" /> 正在生成报告…
          </div>
        ) : report ? (
          <Card className="p-5">
            <div className="mb-3 flex items-center gap-2">
              <Badge tone="brand">{evidenceReportLabels[report.report_type] ?? report.report_type}</Badge>
              <span className="text-sm text-gray-500">{report.title}</span>
            </div>
            {md ? (
              <Markdown content={md} />
            ) : (
              <p className="text-gray-500">报告内容为空，请尝试重新生成。</p>
            )}
            <div className="mt-6 border-t border-gray-100 pt-3 text-xs text-gray-400 dark:border-white/10">
              生成时间：{report.created_at ? new Date(report.created_at).toLocaleString("zh-CN") : "—"}
            </div>
          </Card>
        ) : (
          <Card className="p-8 text-center text-gray-500">
            暂无报告。请先在证据详情执行「AI 分析」，再生成报告。
          </Card>
        )}
      </div>
    </AppShell>
  );
}
