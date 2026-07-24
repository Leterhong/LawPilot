// 模式五：AI 路由测试（查看当前路由 + 多模型比较 + 一键应用到生产）。
"use client";

import { useEffect, useMemo, useState } from "react";
import {
  api,
  type PlaygroundModelOut,
  type RoutingRuleSimpleOut,
  type CompareRowOut,
} from "@/lib/api";
import { aiFeatureLabels } from "@/lib/constants";
import { Card, Badge, Button, Spinner } from "@/components/ui";
import { ScoreBar } from "./Shared";

export function RoutingTestPanel({
  models,
  routing,
  isSuperuser,
  onRoutingChange,
}: {
  models: PlaygroundModelOut[];
  routing: RoutingRuleSimpleOut[];
  isSuperuser: boolean;
  onRoutingChange?: () => void;
}) {
  const enabled = models.filter((m) => m.is_enabled);
  const [feature, setFeature] = useState(routing[0]?.feature ?? "legal_analysis");
  const [input, setInput] = useState("请分析：用人单位未签劳动合同，员工如何维权？");
  const [candidates, setCandidates] = useState<string[]>([]);
  const [target, setTarget] = useState("");
  const [running, setRunning] = useState(false);
  const [rows, setRows] = useState<CompareRowOut[] | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 当前 feature 对应路由
  const current = useMemo(
    () => routing.find((r) => r.feature === feature),
    [routing, feature]
  );

  // 候选模型：默认包含当前路由模型 + 其他模型
  useEffect(() => {
    if (enabled.length === 0) return;
    const base = current?.model_id ? [current.model_id] : [];
    const others = enabled.filter((m) => m.id !== current?.model_id).slice(0, 2).map((m) => m.id);
    setCandidates(Array.from(new Set([...base, ...others])));
  }, [feature, current, enabled]);

  function toggle(mid: string) {
    setCandidates((s) => (s.includes(mid) ? s.filter((x) => x !== mid) : [...s, mid]));
  }

  async function run() {
    setError(null);
    if (candidates.length < 1) return setError("请至少选择 1 个候选模型");
    if (!input.trim()) return setError("请输入测试案例");
    setRunning(true);
    setRows(null);
    try {
      const r = await api.playground.compare({
        model_ids: candidates,
        user_prompt: input,
        judge_model_id: candidates[0] || null,
      });
      setRows(r.rows);
      if (!target) setTarget(r.rows[0]?.model_id ?? "");
    } catch (e: any) {
      setError(e.message || "对比失败");
    } finally {
      setRunning(false);
    }
  }

  async function publish() {
    setError(null);
    setMsg(null);
    if (!isSuperuser) return setError("仅超级管理员可应用到生产");
    if (!target) return setError("请选择要设为默认的模型");
    setPublishing(true);
    try {
      const res = await api.playground.publish({ feature, model_id: target });
      setMsg(`已发布：${aiFeatureLabels[feature] ?? feature} → ${res.to_model_id}`);
      onRoutingChange?.();
    } catch (e: any) {
      setError(e.message || "发布失败");
    } finally {
      setPublishing(false);
    }
  }

  const modelName = (id: string) => enabled.find((m) => m.id === id)?.name ?? id;

  return (
    <div className="space-y-5">
      <Card>
        <h2 className="text-lg font-semibold">AI 路由测试</h2>
        <p className="mt-1 text-sm text-gray-500">查看当前路由规则，比较候选模型并一键应用到生产。</p>

        <div className="mt-4 grid gap-5 lg:grid-cols-2">
          <div className="space-y-3">
            <Field label="当前路由规则">
              <div className="space-y-1.5 rounded-xl border border-gray-100 p-3 dark:border-white/10">
                {routing.length === 0 && <div className="text-sm text-gray-400">暂无路由规则</div>}
                {routing.map((r) => (
                  <div key={r.feature} className="flex items-center justify-between text-sm">
                    <span>{aiFeatureLabels[r.feature] ?? r.feature}</span>
                    <span className="flex items-center gap-2">
                      <span className="text-gray-500">{r.model_name ?? r.model_id}</span>
                      <Badge tone={r.enabled ? "green" : "gray"}>{r.enabled ? "启用" : "禁用"}</Badge>
                    </span>
                  </div>
                ))}
              </div>
            </Field>
            <Field label="选择任务（feature）">
              <select className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5" value={feature} onChange={(e) => setFeature(e.target.value)}>
                {routing.length === 0
                  ? Object.entries(aiFeatureLabels).map(([k, v]) => <option key={k} value={k}>{v}</option>)
                  : routing.map((r) => <option key={r.feature} value={r.feature}>{aiFeatureLabels[r.feature] ?? r.feature}</option>)}
              </select>
            </Field>
            <Field label="候选模型（比较）">
              <div className="space-y-1.5 rounded-xl border border-gray-100 p-3 dark:border-white/10">
                {enabled.map((m) => (
                  <label key={m.id} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={candidates.includes(m.id)} onChange={() => toggle(m.id)} />
                    {m.name}
                  </label>
                ))}
              </div>
            </Field>
          </div>

          <div className="space-y-3">
            <Field label="测试输入（案例 / 问题）">
              <textarea className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm outline-none dark:border-white/10 dark:bg-white/5" rows={6} value={input} onChange={(e) => setInput(e.target.value)} />
            </Field>
            {error && <div className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/15 dark:text-red-300">{error}</div>}
            {msg && <div className="rounded-xl bg-green-50 px-3 py-2 text-sm text-green-700 dark:bg-green-500/15 dark:text-green-300">{msg}</div>}
            <Button onClick={run} disabled={running}>
              {running ? <><Spinner className="mr-1" /> 比较中…</> : "▶ 运行比较"}
            </Button>
            <div className="border-t border-gray-100 pt-3 dark:border-white/10">
              <div className="mb-1 flex items-center gap-2">
                <select className="flex-1 rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5" value={target} onChange={(e) => setTarget(e.target.value)}>
                  <option value="">选择要设为默认的模型…</option>
                  {enabled.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                </select>
                <Button variant="outline" onClick={publish} disabled={publishing || !isSuperuser}>
                  {publishing ? <><Spinner className="mr-1" /> 发布中…</> : "🚀 应用到生产"}
                </Button>
              </div>
              {!isSuperuser && <div className="text-xs text-gray-400">「应用到生产」仅超级管理员可用。</div>}
            </div>
          </div>
        </div>
      </Card>

      {rows && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {rows.map((r) => (
            <Card key={r.model_id}>
              <div className="mb-2 flex items-center justify-between">
                <span className="font-medium">{r.model_name ?? r.model_id}</span>
                <Badge tone={r.status === "success" ? "green" : "red"}>{r.status}</Badge>
              </div>
              <div className="mb-3 min-h-[6rem] whitespace-pre-wrap rounded-xl bg-gray-50 p-3 text-sm dark:bg-white/5">
                {r.content ?? <span className="text-gray-400">{r.error ?? "无输出"}</span>}
              </div>
              <div className="grid grid-cols-[80px_1fr] items-center gap-2">
                <span className="text-xs text-gray-500">总分</span>
                <ScoreBar value={r.score} />
              </div>
              <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-gray-500">
                <span>⏱ {r.latency_ms}ms</span>
                <span>🔤 {r.tokens_in + r.tokens_out}</span>
                <span>💲 {r.cost != null ? `$${r.cost.toFixed(5)}` : "—"}</span>
              </div>
            </Card>
          ))}
        </div>
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
