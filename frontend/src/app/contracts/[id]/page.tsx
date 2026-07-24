"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  api,
  type ContractDetailOut,
  type ContractClauseOut,
  type ContractRiskOut,
  type ContractTaskOut,
  type ContractTaskCategory,
} from "@/lib/api";
import {
  contractTypeLabels,
  contractStatusLabels,
  contractStatusTone,
  contractRiskLevelLabels,
  contractRiskLevelTone,
  contractRiskCategoryLabels,
  contractReminderCategoryLabels,
  contractReminderCategoryTone,
  contractPriorityLabels,
  contractPriorityTone,
} from "@/lib/constants";
import { AppShell } from "@/components/AppShell";
import { Badge, Button, Card, Input, Spinner } from "@/components/ui";
import { cn } from "@/lib/utils";

function RiskScoreBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, value));
  const tone = pct >= 67 ? "bg-red-500" : pct >= 34 ? "bg-amber-500" : "bg-green-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100 dark:bg-white/10">
        <div className={cn("h-full rounded-full", tone)} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-12 text-right text-sm font-medium tabular-nums">{value}</span>
    </div>
  );
}

function taskDueLabel(due: string | null): string {
  if (!due) return "无到期日";
  const today = new Date().toISOString().slice(0, 10);
  const n = Math.round(
    (new Date(due + "T00:00:00").getTime() -
      new Date(today + "T00:00:00").getTime()) /
      86400000
  );
  if (n < 0) return `逾期 ${Math.abs(n)} 天`;
  if (n === 0) return "今天到期";
  if (n === 1) return "明天到期";
  return `还有 ${n} 天`;
}


export default function ContractDetailPage() {
  const params = useParams();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const { user, loading } = useAuth();
  const router = useRouter();

  const [detail, setDetail] = useState<ContractDetailOut | null>(null);
  const [ready, setReady] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [selectedClauseId, setSelectedClauseId] = useState<string | null>(null);

  // 提醒 / 待办
  const [tasks, setTasks] = useState<ContractTaskOut[]>([]);
  const [taskBusy, setTaskBusy] = useState<string | null>(null);
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [taskForm, setTaskForm] = useState({
    title: "",
    category: "payment" as ContractTaskCategory | null,
    due_date: "",
    priority: "normal" as "low" | "normal" | "high" | "urgent",
    type: "reminder" as "reminder" | "checklist",
  });
  const [taskFormErr, setTaskFormErr] = useState<string | null>(null);

  // 全局 AI 是否已配置真实模型（决定右侧「AI 分析」面板是否展示）
  // null = 尚未拿到状态（加载中 / 旧版后端），不强制隐藏
  const [aiConfigured, setAiConfigured] = useState<boolean | null>(null);

  const loadAiStatus = useCallback(async () => {
    try {
      const s = await api.aiCenter.status();
      setAiConfigured(s.ai_configured);
    } catch {
      // 接口不可用（如旧版后端未提供 /api/ai/status）时视为未知，不强制隐藏面板
      setAiConfigured(null);
    }
  }, []);

  const loadTasks = useCallback(async () => {
    if (!id) return;
    try {
      const data = await api.contracts.tasks(id);
      setTasks(data);
    } catch {
      /* 提醒面板非阻塞 */
    }
  }, [id]);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const d = await api.contracts.get(id);
      setDetail(d);
      setErr(null);
      if (d.clauses.length > 0) setSelectedClauseId(d.clauses[0].id);
      await loadTasks();
    } catch (e: any) {
      setErr(e.message || "加载失败");
    } finally {
      setReady(true);
    }
  }, [id, loadTasks]);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    load();
    loadAiStatus();
  }, [user, loading, router, load, loadAiStatus]);

  async function onAnalyze() {
    if (!id) return;
    setAnalyzing(true);
    setErr(null);
    try {
      const d = await api.contracts.analyze(id);
      setDetail(d);
      if (d.clauses.length > 0) setSelectedClauseId(d.clauses[0].id);
    } catch (e: any) {
      setErr(e.message || "分析失败");
    } finally {
      setAnalyzing(false);
    }
  }

  async function onTaskToggle(it: ContractTaskOut) {
    if (!id) return;
    setTaskBusy(it.id);
    try {
      await api.contracts.updateTask(id, it.id, { done: !it.done });
      await loadTasks();
    } catch (e: any) {
      setErr(e.message || "更新失败");
    } finally {
      setTaskBusy(null);
    }
  }

  async function onTaskDelete(it: ContractTaskOut) {
    if (!id) return;
    if (!confirm(`确认删除「${it.title}」？`)) return;
    setTaskBusy(it.id);
    try {
      await api.contracts.deleteTask(id, it.id);
      await loadTasks();
    } catch (e: any) {
      setErr(e.message || "删除失败");
    } finally {
      setTaskBusy(null);
    }
  }

  async function onCreateTask() {
    if (!id) return;
    if (!taskForm.title.trim()) {
      setTaskFormErr("请填写标题");
      return;
    }
    setTaskBusy("__new__");
    setTaskFormErr(null);
    try {
      await api.contracts.createTask(id, {
        type: taskForm.type,
        title: taskForm.title.trim(),
        category: taskForm.type === "reminder" ? taskForm.category : null,
        due_date: taskForm.type === "reminder" ? taskForm.due_date || null : null,
        priority: taskForm.priority,
      });
      setShowTaskForm(false);
      setTaskForm({
        title: "",
        category: "payment",
        due_date: "",
        priority: "normal",
        type: "reminder",
      });
      await loadTasks();
    } catch (e: any) {
      setTaskFormErr(e.message || "创建失败");
    } finally {
      setTaskBusy(null);
    }
  }

  const meta = (detail?.analysis_meta as Record<string, unknown> | null) ?? null;
  const aiAvailable = meta ? meta.ai_available === true : null;
  const selectedClause: ContractClauseOut | null =
    detail?.clauses.find((c) => c.id === selectedClauseId) ?? null;
  const sortedRisks: ContractRiskOut[] = detail
    ? [...detail.risks].sort((a, b) => b.score - a.score)
    : [];

  if (loading || !ready) {
    return (
      <AppShell>
        <div className="flex items-center justify-center py-20 text-gray-400">
          <Spinner className="mr-2" /> 加载中…
        </div>
      </AppShell>
    );
  }

  if (err && !detail) {
    return (
      <AppShell>
        <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-500/15 dark:text-red-300">
          {err}
        </div>
        <Link href="/contracts" className="mt-4 inline-block text-sm text-brand-600">
          ← 返回合同中心
        </Link>
      </AppShell>
    );
  }

  if (!detail) return null;

  const checklist = (detail.checklist as Array<{ item?: string; checked?: boolean; category?: string }> | null) ?? null;

  return (
    <AppShell>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <Link href="/contracts" className="text-sm text-brand-600 hover:underline dark:text-brand-300">
            ← 合同中心
          </Link>
          <h1 className="mt-1 truncate text-xl font-semibold">{detail.title || "未命名合同"}</h1>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge tone="brand">
              {detail.contract_type ? contractTypeLabels[detail.contract_type] ?? detail.contract_type : "未分类"}
            </Badge>
            <Badge tone={contractStatusTone[detail.status] ?? "gray"}>
              {contractStatusLabels[detail.status] ?? detail.status}
            </Badge>
            <Badge tone={contractRiskLevelTone[detail.risk_level] ?? "gray"}>
              {contractRiskLevelLabels[detail.risk_level] ?? detail.risk_level}
            </Badge>
            {aiConfigured === false && (
              <Badge tone="gray">AI 分析未启用</Badge>
            )}
          </div>
        </div>
        <Button
          onClick={onAnalyze}
          disabled={analyzing || aiConfigured === false}
          title={
            aiConfigured === false
              ? "请先在「设置 → AI 能力中心」配置并启用一个大模型"
              : undefined
          }
        >
          {analyzing ? (
            <>
              <Spinner className="mr-1" /> 分析中…
            </>
          ) : detail.status === "analyzed" ? (
            "重新分析"
          ) : (
            "AI 分析"
          )}
        </Button>
        <Link href={`/contracts/${id}/report`}>
          <Button variant="outline">审查报告</Button>
        </Link>
      </div>

      {err && (
        <div className="mb-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/15 dark:text-red-300">
          {err}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        {/* 左列：全文 + 条款树 */}
        <div className="space-y-4">
          <Card>
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-semibold">合同全文</h2>
              <span className="text-xs text-gray-400">
                {detail.full_text ? `${detail.full_text.length} 字` : "无文本"}
              </span>
            </div>
            <div className="max-h-[42vh] overflow-auto whitespace-pre-wrap rounded-xl bg-gray-50 p-3 text-sm leading-relaxed text-gray-700 dark:bg-white/5 dark:text-gray-300">
              {detail.full_text?.trim() ||
                detail.ocr_text?.trim() ||
                "（未提取到文本，可能是扫描件或图片未能 OCR）"}
            </div>
          </Card>

          <Card>
            <h2 className="mb-2 text-sm font-semibold">
              条款导航（{detail.clauses.length}）
            </h2>
            {detail.clauses.length === 0 ? (
              <p className="text-sm text-gray-400">暂无结构化条款。</p>
            ) : (
              <ul className="max-h-[32vh] space-y-1 overflow-auto">
                {detail.clauses.map((c) => (
                  <li key={c.id}>
                    <button
                      onClick={() => setSelectedClauseId(c.id)}
                      className={cn(
                        "w-full truncate rounded-lg px-3 py-2 text-left text-sm transition",
                        c.id === selectedClauseId
                          ? "bg-brand-50 font-medium text-brand-700 dark:bg-brand-500/15 dark:text-brand-300"
                          : "hover:bg-gray-100 dark:hover:bg-white/5"
                      )}
                    >
                      <span className="mr-2 text-gray-400">{c.clause_no || "—"}</span>
                      {(c.clause_text || "").slice(0, 24) || "（空条款）"}
                      {c.risk_level && (
                        <span
                          className={cn(
                            "ml-2 inline-block h-2 w-2 rounded-full",
                            c.risk_level === "high"
                              ? "bg-red-500"
                              : c.risk_level === "medium"
                              ? "bg-amber-500"
                              : "bg-green-500"
                          )}
                        />
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>

        {/* 右列：AI 分析 */}
        <div className="space-y-4">
          {aiConfigured === false ? (
            <Card>
              <div className="flex flex-col items-start gap-3">
                <h2 className="text-sm font-semibold">AI 分析未启用</h2>
                <p className="text-sm leading-relaxed text-gray-500 dark:text-gray-400">
                  当前尚未在「AI 能力中心」配置可用的模型（大模型 Key）。配置并启用模型后，
                  即可对合同进行 AI 风险分析、条款解释与审查报告生成。
                </p>
                <Link href="/settings/ai-center">
                  <Button variant="outline">前往配置大模型</Button>
                </Link>
              </div>
            </Card>
          ) : (
            <>          {/* 摘要 + 评分 */}
          <Card>
            <h2 className="mb-3 text-sm font-semibold">AI 分析总览</h2>
            <div className="mb-3">
              <div className="mb-1 flex items-center justify-between text-xs text-gray-500">
                <span>风险评分（0-100）</span>
              </div>
              <RiskScoreBar value={detail.risk_score} />
            </div>
            {detail.summary ? (
              <p className="text-sm leading-relaxed text-gray-700 dark:text-gray-300">
                {detail.summary}
              </p>
            ) : (
              <p className="text-sm text-gray-400">
                尚未生成摘要。点击右上角「AI 分析」开始。
              </p>
            )}
            {detail.analyzed_at && (
              <p className="mt-3 text-xs text-gray-400">
                分析时间：{new Date(detail.analyzed_at).toLocaleString("zh-CN")}
              </p>
            )}
          </Card>

          {/* 风险看板 */}
          <Card>
            <h2 className="mb-3 text-sm font-semibold">
              风险看板（{sortedRisks.length}）
            </h2>
            {sortedRisks.length === 0 ? (
              <p className="text-sm text-gray-400">未发现风险条款。</p>
            ) : (
              <ul className="space-y-3">
                {sortedRisks.map((r) => (
                  <li
                    key={r.id}
                    className="rounded-xl border border-gray-100 p-3 dark:border-white/10"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone="brand">
                          {contractRiskCategoryLabels[r.category] ?? r.category}
                        </Badge>
                        <Badge tone={contractRiskLevelTone[r.risk_level] ?? "gray"}>
                          {contractRiskLevelLabels[r.risk_level] ?? r.risk_level}
                        </Badge>
                        {r.king_clause && <Badge tone="red">⚠ 疑似霸王条款</Badge>}
                        {r.clause_ref && (
                          <span className="text-xs text-gray-400">{r.clause_ref}</span>
                        )}
                      </div>
                      <span className="text-xs tabular-nums text-gray-400">
                        风险 {r.score}
                      </span>
                    </div>
                    {r.clause_text && (
                      <p className="mt-2 line-clamp-2 text-sm text-gray-500 dark:text-gray-400">
                        {r.clause_text}
                      </p>
                    )}
                    {r.reason && (
                      <p className="mt-2 text-sm text-gray-700 dark:text-gray-300">
                        <span className="font-medium">风险原因：</span>
                        {r.reason}
                      </p>
                    )}
                    {r.suggestion && (
                      <p className="mt-1 text-sm text-brand-700 dark:text-brand-300">
                        <span className="font-medium">修改建议：</span>
                        {r.suggestion}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {/* Clause Analyzer */}
          <Card>
            <h2 className="mb-3 text-sm font-semibold">条款解释（Clause Analyzer）</h2>
            {!selectedClause ? (
              <p className="text-sm text-gray-400">从左侧条款导航选择一条查看解释。</p>
            ) : (
              <div>
                <div className="mb-2 flex items-center gap-2">
                  <span className="font-medium">{selectedClause.clause_no || "条款"}</span>
                  {selectedClause.risk_level && (
                    <Badge tone={contractRiskLevelTone[selectedClause.risk_level] ?? "gray"}>
                      {contractRiskLevelLabels[selectedClause.risk_level] ?? selectedClause.risk_level}
                    </Badge>
                  )}
                </div>
                {selectedClause.clause_text && (
                  <p className="mb-3 rounded-xl bg-gray-50 p-3 text-sm text-gray-600 dark:bg-white/5 dark:text-gray-300">
                    {selectedClause.clause_text}
                  </p>
                )}
                {selectedClause.explanation ? (
                  <p className="text-sm leading-relaxed text-gray-700 dark:text-gray-300">
                    <span className="font-medium">这是什么意思：</span>
                    {selectedClause.explanation}
                  </p>
                ) : (
                  <p className="text-sm text-gray-400">该条款暂无 AI 解释。</p>
                )}
                {selectedClause.risk_note && (
                  <p className="mt-2 text-sm text-gray-700 dark:text-gray-300">
                    <span className="font-medium">风险提示：</span>
                    {selectedClause.risk_note}
                  </p>
                )}
                {selectedClause.suggested_version && (
                  <p className="mt-2 text-sm text-brand-700 dark:text-brand-300">
                    <span className="font-medium">推荐修改版本：</span>
                    {selectedClause.suggested_version}
                  </p>
                )}
              </div>
            )}
          </Card>

          {/* 检查清单 */}
          {checklist && checklist.length > 0 && (
            <Card>
              <h2 className="mb-3 text-sm font-semibold">签署前检查清单</h2>
              <ul className="space-y-2">
                {checklist.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <span
                      className={cn(
                        "mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px]",
                        item.checked
                          ? "bg-green-500 text-white"
                          : "bg-gray-200 text-gray-500 dark:bg-white/10"
                      )}
                    >
                      {item.checked ? "✓" : ""}
                    </span>
                    <span className="text-gray-700 dark:text-gray-300">
                      {item.item || "（未命名项）"}
                      {item.category && (
                        <span className="ml-2 text-xs text-gray-400">{item.category}</span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          </>
          )}
        </div>
      </div>

      {/* 提醒 / 待办面板 */}
      <div className="mt-6">
        <Card>
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">提醒 / 待办（{tasks.length}）</h2>
            <div className="flex items-center gap-2">
              <Link href="/contracts/reminders">
                <Button variant="outline" className="text-xs">
                  🔔 提醒中心
                </Button>
              </Link>
              <Button
                variant="outline"
                className="text-xs"
                onClick={() => {
                  setShowTaskForm((v) => !v);
                  setTaskFormErr(null);
                }}
              >
                ＋ 新建
              </Button>
            </div>
          </div>

          {showTaskForm && (
            <div className="mb-4 grid gap-3 rounded-xl bg-gray-50 p-3 dark:bg-white/5 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <Input
                  value={taskForm.title}
                  onChange={(e) =>
                    setTaskForm((f) => ({ ...f, title: e.target.value }))
                  }
                  placeholder="标题，例如：支付第二季度租金"
                />
              </div>
              <div>
                <select
                  value={taskForm.type}
                  onChange={(e) =>
                    setTaskForm((f) => ({
                      ...f,
                      type: e.target.value as "reminder" | "checklist",
                    }))
                  }
                  className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
                >
                  <option value="reminder">提醒</option>
                  <option value="checklist">待办</option>
                </select>
              </div>
              {taskForm.type === "reminder" ? (
                <>
                  <div>
                    <select
                      value={taskForm.category ?? "payment"}
                      onChange={(e) =>
                        setTaskForm((f) => ({
                          ...f,
                          category: e.target.value as ContractTaskCategory,
                        }))
                      }
                      className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
                    >
                      {(["expiry", "payment", "renewal", "sign_check", "other"] as const).map(
                        (c) => (
                          <option key={c} value={c}>
                            {contractReminderCategoryLabels[c] ?? c}
                          </option>
                        )
                      )}
                    </select>
                  </div>
                  <div>
                    <input
                      type="date"
                      value={taskForm.due_date}
                      onChange={(e) =>
                        setTaskForm((f) => ({ ...f, due_date: e.target.value }))
                      }
                      className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
                    />
                  </div>
                  <div>
                    <select
                      value={taskForm.priority}
                      onChange={(e) =>
                        setTaskForm((f) => ({
                          ...f,
                          priority: e.target.value as
                            | "low"
                            | "normal"
                            | "high"
                            | "urgent",
                        }))
                      }
                      className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
                    >
                      {(["low", "normal", "high", "urgent"] as const).map((p) => (
                        <option key={p} value={p}>
                          {contractPriorityLabels[p] ?? p}
                        </option>
                      ))}
                    </select>
                  </div>
                </>
              ) : (
                <div>
                  <select
                    value={taskForm.priority}
                    onChange={(e) =>
                      setTaskForm((f) => ({
                        ...f,
                        priority: e.target.value as
                          | "low"
                          | "normal"
                          | "high"
                          | "urgent",
                      }))
                    }
                    className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
                  >
                    {(["low", "normal", "high", "urgent"] as const).map((p) => (
                      <option key={p} value={p}>
                        {contractPriorityLabels[p] ?? p}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {taskFormErr && (
                <div className="sm:col-span-2 text-sm text-red-500">{taskFormErr}</div>
              )}
              <div className="sm:col-span-2 flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => setShowTaskForm(false)}
                  disabled={taskBusy === "__new__"}
                >
                  取消
                </Button>
                <Button onClick={onCreateTask} disabled={taskBusy === "__new__"}>
                  {taskBusy === "__new__" ? "创建中…" : "创建"}
                </Button>
              </div>
            </div>
          )}

          {tasks.length === 0 ? (
            <p className="text-sm text-gray-400">
              还没有提醒 / 待办。点击「新建」添加一条吧。
            </p>
          ) : (
            <ul className="space-y-2">
              {tasks.map((t) => (
                <li
                  key={t.id}
                  className="flex items-center justify-between gap-3 rounded-xl border border-gray-100 p-3 dark:border-white/10"
                >
                  <div className="flex min-w-0 items-start gap-2">
                    <input
                      type="checkbox"
                      checked={t.done}
                      disabled={taskBusy === t.id}
                      onChange={() => onTaskToggle(t)}
                      className="mt-1 h-4 w-4 shrink-0 accent-brand-500"
                    />
                    <div className="min-w-0">
                      <div
                        className={
                          "truncate text-sm font-medium " +
                          (t.done ? "text-gray-400 line-through" : "")
                        }
                      >
                        {t.title}
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        {t.type === "reminder" && t.category && (
                          <Badge tone={contractReminderCategoryTone[t.category] ?? "gray"}>
                            {contractReminderCategoryLabels[t.category] ?? t.category}
                          </Badge>
                        )}
                        <Badge tone={contractPriorityTone[t.priority] ?? "gray"}>
                          {contractPriorityLabels[t.priority] ?? t.priority}
                        </Badge>
                        {t.type === "reminder" && t.due_date && (
                          <span
                            className={
                              "text-xs " +
                              (new Date(t.due_date + "T00:00:00").getTime() <
                              new Date().getTime()
                                ? "text-red-500"
                                : "text-gray-400")
                            }
                          >
                            {taskDueLabel(t.due_date)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => onTaskDelete(t)}
                    disabled={taskBusy === t.id}
                    className="shrink-0 text-xs text-gray-400 hover:text-red-500"
                  >
                    删除
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
