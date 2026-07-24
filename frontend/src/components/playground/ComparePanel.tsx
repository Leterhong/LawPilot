// 模式二：多模型对比（并行调用 + AI 自动评分）。
"use client";

import { useState } from "react";
import { api, type PlaygroundModelOut, type CompareRowOut } from "@/lib/api";
import { scoreDimLabels } from "@/lib/constants";
import { Card, Badge, Button, Spinner } from "@/components/ui";
import { ParamSlider, CodeTextarea, ScoreBar } from "./Shared";

export function ComparePanel({ models }: { models: PlaygroundModelOut[] }) {
  const enabled = models.filter((m) => m.is_enabled);
  const [selected, setSelected] = useState<string[]>(enabled.slice(0, 2).map((m) => m.id));
  const [judgeId, setJudgeId] = useState(enabled[0]?.id ?? "");
  const [system, setSystem] = useState("");
  const [user, setUser] = useState("");
  const [temperature, setTemperature] = useState(0.7);
  const [topP, setTopP] = useState(1);
  const [maxTokens, setMaxTokens] = useState(1024);
  const [running, setRunning] = useState(false);
  const [rows, setRows] = useState<CompareRowOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function toggle(mid: string) {
    setSelected((s) => (s.includes(mid) ? s.filter((x) => x !== mid) : [...s, mid]));
  }

  async function run() {
    setError(null);
    if (selected.length < 2) return setError("请至少选择 2 个模型进行对比");
    if (!user.trim()) return setError("请输入 User Prompt");
    setRunning(true);
    setRows(null);
    try {
      const r = await api.playground.compare({
        model_ids: selected,
        system_prompt: system || null,
        user_prompt: user,
        temperature,
        top_p: topP,
        max_tokens: maxTokens,
        judge_model_id: judgeId || null,
      });
      setRows(r.rows);
    } catch (e: any) {
      setError(e.message || "对比失败");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <h2 className="text-lg font-semibold">多模型对比</h2>
        <p className="mt-1 text-sm text-gray-500">一次提问并行调用多个模型，由 LLM Judge 自动横向评分。</p>

        <div className="mt-4 grid gap-5 lg:grid-cols-[320px_1fr]">
          <div className="space-y-3">
            <div>
              <div className="mb-1 text-sm font-medium text-gray-700 dark:text-gray-300">选择模型（并行）</div>
              <div className="space-y-1.5 rounded-xl border border-gray-100 p-3 dark:border-white/10">
                {enabled.length === 0 && <div className="text-sm text-gray-400">无可用模型</div>}
                {enabled.map((m) => (
                  <label key={m.id} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={selected.includes(m.id)} onChange={() => toggle(m.id)} />
                    {m.name}
                    {m.provider_name ? <span className="text-xs text-gray-400">· {m.provider_name}</span> : null}
                  </label>
                ))}
              </div>
            </div>
            <Field label="AI 评分器（Judge）">
              <select
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
                value={judgeId}
                onChange={(e) => setJudgeId(e.target.value)}
              >
                <option value="">（不评分）</option>
                {enabled.map((m) => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </Field>
            <div className="grid grid-cols-2 gap-3 pt-1">
              <ParamSlider label="Temperature" value={temperature} min={0} max={2} step={0.1} onChange={setTemperature} />
              <ParamSlider label="Top P" value={topP} min={0} max={1} step={0.05} onChange={setTopP} />
            </div>
          </div>

          <div className="space-y-3">
            <Field label="System Prompt" hint="可选">
              <CodeTextarea rows={3} value={system} onChange={(e) => setSystem(e.target.value)} />
            </Field>
            <Field label="User Prompt">
              <CodeTextarea rows={5} value={user} onChange={(e) => setUser(e.target.value)} placeholder="请输入同一个问题，多模型并排比较…" />
            </Field>
            {error && <div className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/15 dark:text-red-300">{error}</div>}
            <Button onClick={run} disabled={running}>
              {running ? <><Spinner className="mr-1" /> 并行调用中…</> : "▶ 开始对比"}
            </Button>
          </div>
        </div>
      </Card>

      {/* 结果 */}
      {rows && (
        <>
          {/* 总分排名 */}
          <Card>
            <h3 className="mb-3 font-semibold">总分排名</h3>
            <div className="space-y-2">
              {[...rows]
                .sort((a, b) => (b.score ?? -1) - (a.score ?? -1))
                .map((r) => (
                  <div key={r.model_id} className="grid grid-cols-[140px_1fr] items-center gap-3">
                    <div className="truncate text-sm font-medium">{r.model_name ?? r.model_id}</div>
                    <ScoreBar value={r.score} />
                  </div>
                ))}
            </div>
          </Card>

          {/* 逐模型并排 */}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {rows.map((r) => (
              <Card key={r.model_id}>
                <div className="mb-2 flex items-center justify-between">
                  <span className="font-medium">{r.model_name ?? r.model_id}</span>
                  <Badge tone={r.status === "success" ? "green" : "red"}>{r.status}</Badge>
                </div>
                <div className="mb-3 min-h-[7rem] whitespace-pre-wrap rounded-xl bg-gray-50 p-3 text-sm dark:bg-white/5">
                  {r.content ?? <span className="text-gray-400">{r.error ?? "无输出"}</span>}
                </div>

                {r.score_detail && (
                  <div className="mb-3 space-y-1.5">
                    {Object.entries(r.score_detail)
                      .filter(([k]) => k !== "total")
                      .map(([k, v]) => (
                        <div key={k} className="grid grid-cols-[80px_1fr] items-center gap-2">
                          <span className="text-xs text-gray-500">{scoreDimLabels[k] ?? k}</span>
                          <ScoreBar value={v} />
                        </div>
                      ))}
                  </div>
                )}

                <div className="grid grid-cols-3 gap-2 text-xs text-gray-500">
                  <span>⏱ {r.latency_ms}ms</span>
                  <span>🔤 {r.tokens_in + r.tokens_out}</span>
                  <span>💲 {r.cost != null ? `$${r.cost.toFixed(5)}` : "—"}</span>
                </div>
              </Card>
            ))}
          </div>
        </>
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
