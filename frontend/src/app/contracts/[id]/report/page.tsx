"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api, type ContractReportOut } from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { Badge, Button, Card, Spinner } from "@/components/ui";
import { Markdown } from "@/components/Markdown";
import { cn } from "@/lib/utils";

const REPORT_TABS: { type: string; label: string }[] = [
  { type: "review", label: "审查报告" },
  { type: "summary", label: "摘要报告" },
  { type: "full", label: "完整报告" },
  { type: "checklist", label: "检查清单" },
];

export default function ContractReportPage() {
  const params = useParams();
  const router = useRouter();
  const { token } = useAuth();
  const id = typeof params.id === "string" ? params.id : Array.isArray(params.id) ? params.id[0] : "";

  const [reportType, setReportType] = useState("review");
  const [report, setReport] = useState<ContractReportOut | null>(null);
  const [existing, setExisting] = useState<ContractReportOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // 全局 AI 是否已配置真实模型（决定报告页是否提示去配置）
  const [aiConfigured, setAiConfigured] = useState<boolean | null>(null);

  const loadAiStatus = useCallback(async () => {
    try {
      const s = await api.aiCenter.status();
      setAiConfigured(s.ai_configured);
    } catch {
      setAiConfigured(null);
    }
  }, []);

  const loadExisting = useCallback(async () => {
    if (!token || !id) return;
    try {
      const list = await api.contracts.reports(id);
      setExisting(list);
    } catch {
      /* 忽略：不影响主流程 */
    }
  }, [token, id]);

  const loadReport = useCallback(
    async (type: string, regenerate = false) => {
      if (!token || !id) return;
      setLoading(true);
      setErr(null);
      try {
        const r = await api.contracts.report(id, type, regenerate);
        setReport(r);
      } catch (e) {
        setErr(e instanceof Error ? e.message : "报告生成失败");
        setReport(null);
      } finally {
        setLoading(false);
      }
    },
    [token, id]
  );

  useEffect(() => {
    if (!token) {
      router.replace("/login");
      return;
    }
    loadExisting();
    loadReport(reportType);
    loadAiStatus();
  }, [token, router, loadExisting, loadReport, reportType, loadAiStatus]);

  const onRegenerate = async () => {
    if (!token || !id) return;
    setGenerating(true);
    setErr(null);
    try {
      const r = await api.contracts.report(id, reportType, true);
      setReport(r);
      await loadExisting();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "重新生成失败");
    } finally {
      setGenerating(false);
    }
  };

  const aiAssisted =
    report?.content_json && (report.content_json as Record<string, unknown>).ai_assisted === true;

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl px-4 py-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <Link
              href={`/contracts/${id}`}
              className="text-sm text-blue-600 hover:underline dark:text-blue-400"
            >
              ← 返回合同详情
            </Link>
            <h1 className="mt-1 text-xl font-bold">合同审查报告</h1>
          </div>
          <div className="flex items-center gap-2">
            {aiAssisted ? (
              <Badge tone="green">AI 辅助生成</Badge>
            ) : aiConfigured === false ? (
              <Badge tone="gray">未配置模型</Badge>
            ) : (
              <Badge tone="amber">规则生成</Badge>
            )}
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
              当前未配置大模型，报告仅为规则模板。在「AI 能力中心」配置并启用模型后，可生成 AI 辅助的深度审查报告。
            </span>
            <Link href="/settings/ai-center">
              <Button variant="outline" className="shrink-0">前往配置大模型</Button>
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
                onClick={() => setReportType(t.type)}
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
            {report.content ? (
              <Markdown content={report.content} />
            ) : (
              <p className="text-gray-500">报告内容为空，请先执行 AI 分析后重新生成。</p>
            )}
            <div className="mt-6 border-t border-gray-100 pt-3 text-xs text-gray-400 dark:border-white/10">
              生成时间：{new Date(report.created_at).toLocaleString("zh-CN")}
            </div>
          </Card>
        ) : (
          <Card className="p-8 text-center text-gray-500">
            暂无报告。请先回到合同详情执行「AI 分析」，再生成报告。
          </Card>
        )}
      </div>
    </AppShell>
  );
}
