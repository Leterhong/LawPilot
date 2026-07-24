// 模式四：模型评测（Evaluation Center）。
"use client";

import { useState } from "react";
import {
  api,
  type PlaygroundModelOut,
  type EvaluationDatasetOut,
  type EvaluationTaskOut,
  type EvaluationResultOut,
} from "@/lib/api";
import { aiFeatureLabels } from "@/lib/constants";
import { Card, Badge, Button, Input, Spinner } from "@/components/ui";
import { ScoreBar, Metric } from "./Shared";

export function EvalPanel({
  models,
  datasets,
}: {
  models: PlaygroundModelOut[];
  datasets: EvaluationDatasetOut[];
}) {
  const enabled = models.filter((m) => m.is_enabled);
  const [name, setName] = useState("法律分析评测");
  const [selected, setSelected] = useState<string[]>(enabled.slice(0, 1).map((m) => m.id));
  const [judgeId, setJudgeId] = useState(enabled[0]?.id ?? "");
  const [datasetId, setDatasetId] = useState(datasets[0]?.id ?? "");
  const [feature, setFeature] = useState("legal_analysis");
  const [itemsText, setItemsText] = useState("请说明劳动合同解除的合法情形。\n借贷纠纷中利息上限如何认定？");
  const [running, setRunning] = useState(false);
  const [task, setTask] = useState<EvaluationTaskOut | null>(null);
  const [results, setResults] = useState<EvaluationResultOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  function toggle(mid: string) {
    setSelected((s) => (s.includes(mid) ? s.filter((x) => x !== mid) : [...s, mid]));
  }

  async function run() {
    setError(null);
    if (selected.length === 0) return setError("请至少选择 1 个被测模型");
    if (!datasetId && !itemsText.trim()) return setError("请选择测试集或填写题目");
    setRunning(true);
    setTask(null);
    setResults([]);
    try {
      const items = datasetId
        ? undefined
        : itemsText
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean)
            .map((line) => {
              const [input, expected] = line.split("||").map((x) => x.trim());
              return { input, expected: expected || null };
            });
      const t = await api.playground.evaluate({
        name: name || "未命名评测",
        model_ids: selected,
        judge_model_id: judgeId || null,
        dataset_id: datasetId || null,
        feature,
        items,
      });
      setTask(t);
    } catch (e: any) {
      setError(e.message || "评测失败");
    } finally {
      setRunning(false);
    }
  }

  async function viewReport() {
    if (!task) return;
    try {
      const r = await api.playground.getEvaluationResults(task.id);
      setResults(r);
    } catch (e: any) {
      setError(e.message || "加载报告失败");
    }
  }

  const summary = (task?.score_summary as any) ?? null;
  const modelSum = summary?.models ?? {};
  const modelName = (id: string) => enabled.find((m) => m.id === id)?.name ?? id;

  return (
    <div className="space-y-5">
      <Card>
        <h2 className="text-lg font-semibold">模型评测 · Evaluation Center</h2>
        <p className="mt-1 text-sm text-gray-500">基于测试集批量评测多个模型，自动生成报告。</p>

        <div className="mt-4 grid gap-5 lg:grid-cols-2">
          <div className="space-y-3">
            <Field label="评测名称">
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="被测模型">
              <div className="space-y-1.5 rounded-xl border border-gray-100 p-3 dark:border-white/10">
                {enabled.map((m) => (
                  <label key={m.id} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={selected.includes(m.id)} onChange={() => toggle(m.id)} />
                    {m.name}
                  </label>
                ))}
              </div>
            </Field>
            <Field label="AI 评分器（Judge）">
              <select className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5" value={judgeId} onChange={(e) => setJudgeId(e.target.value)}>
                <option value="">（不评分）</option>
                {enabled.map((m) => (<option key={m.id} value={m.id}>{m.name}</option>))}
              </select>
            </Field>
            <Field label="评测任务（feature）">
              <select className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5" value={feature} onChange={(e) => setFeature(e.target.value)}>
                {Object.entries(aiFeatureLabels).map(([k, v]) => (<option key={k} value={k}>{v}（{k}）</option>))}
              </select>
            </Field>
          </div>

          <div className="space-y-3">
            <Field label="测试集" hint="或下方直接填写题目">
              <select className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5" value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
                <option value="">（自定义题目）</option>
                {datasets.map((d) => (<option key={d.id} value={d.id}>{d.name}（{d.item_count} 题）</option>))}
              </select>
            </Field>
            <Field label="自定义题目" hint="每行一题，可选 || 期望答案">
              <textarea
                className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 font-mono text-[13px] outline-none dark:border-white/10 dark:bg-white/5"
                rows={6}
                value={itemsText}
                onChange={(e) => setItemsText(e.target.value)}
                disabled={!!datasetId}
              />
            </Field>
            {error && <div className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/15 dark:text-red-300">{error}</div>}
            <Button onClick={run} disabled={running}>
              {running ? <><Spinner className="mr-1" /> 评测中…</> : "▶ 运行评测"}
            </Button>
          </div>
        </div>
      </Card>

      {/* 报告 */}
      {task && (
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h3 className="font-semibold">{task.name}</h3>
              <div className="mt-1 text-xs text-gray-500">
                状态 <Badge tone={task.status === "done" ? "green" : "amber"}>{task.status}</Badge> · {task.processed_items}/{task.total_items} 题
              </div>
            </div>
            <Button variant="outline" size="sm" onClick={viewReport}>查看逐题报告</Button>
          </div>

          {/* 各模型聚合指标 */}
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {task.model_ids.map((mid) => {
              const ms = modelSum[mid];
              return (
                <div key={mid} className="rounded-xl border border-gray-100 p-3 dark:border-white/10">
                  <div className="mb-2 font-medium">{modelName(mid)}</div>
                  {ms ? (
                    <div className="space-y-2">
                      <div className="grid grid-cols-[80px_1fr] items-center gap-2">
                        <span className="text-xs text-gray-500">均分</span>
                        <ScoreBar value={ms.avg_score ?? null} />
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-xs text-gray-500">
                        <span>⏱ {ms.avg_latency_ms ?? 0}ms</span>
                        <span>💲 {ms.avg_cost != null ? `$${ms.avg_cost.toFixed(5)}` : "—"}</span>
                        <span>✓ {(ms.success_rate ?? 0) * 100}%</span>
                      </div>
                    </div>
                  ) : (
                    <div className="text-xs text-gray-400">暂无聚合数据</div>
                  )}
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* 逐题明细 */}
      {results.length > 0 && (
        <Card>
          <h3 className="mb-3 font-semibold">逐题明细</h3>
          <div className="space-y-3">
            {results.map((r) => (
              <div key={r.id} className="rounded-xl border border-gray-100 p-3 dark:border-white/10">
                <div className="mb-1 flex flex-wrap items-center gap-2 text-xs">
                  <Badge tone="gray">{modelName(r.model_id ?? "")}</Badge>
                  {r.score != null && <Badge tone="brand">评分 {r.score.toFixed(1)}</Badge>}
                  <span className="text-gray-400">⏱ {r.latency_ms}ms · 🔤 {r.tokens_in + r.tokens_out}</span>
                </div>
                <div className="grid gap-2 md:grid-cols-2 text-sm">
                  <div>
                    <div className="text-xs text-gray-400">输入</div>
                    <div className="whitespace-pre-wrap">{r.input}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">输出</div>
                    <div className="whitespace-pre-wrap">{r.output ?? <span className="text-gray-400">{r.error_text ?? "无"}</span>}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
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
