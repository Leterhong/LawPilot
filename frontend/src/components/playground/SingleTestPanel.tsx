// 模式一：单模型测试。
"use client";

import { useState } from "react";
import { api, type PlaygroundModelOut, type PlaygroundSessionOut } from "@/lib/api";
import { Card, Badge, Button, Spinner } from "@/components/ui";
import { ParamSlider, CodeTextarea, Metric } from "./Shared";

export function SingleTestPanel({ models }: { models: PlaygroundModelOut[] }) {
  const [modelId, setModelId] = useState(models[0]?.id ?? "");
  const [system, setSystem] = useState("");
  const [user, setUser] = useState("");
  const [context, setContext] = useState("");
  const [temperature, setTemperature] = useState(0.7);
  const [topP, setTopP] = useState(1);
  const [maxTokens, setMaxTokens] = useState(1024);
  const [streaming, setStreaming] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<PlaygroundSessionOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const enabledModels = models.filter((m) => m.is_enabled);

  async function run() {
    setError(null);
    if (!modelId) return setError("请先选择模型");
    if (!user.trim()) return setError("请输入 User Prompt");
    setRunning(true);
    setResult(null);
    try {
      const r = await api.playground.test({
        model_id: modelId,
        system_prompt: system || null,
        user_prompt: user,
        context: context || null,
        temperature,
        top_p: topP,
        max_tokens: maxTokens,
        streaming,
      });
      setResult(r);
    } catch (e: any) {
      setError(e.message || "测试失败");
    } finally {
      setRunning(false);
    }
  }

  const tu = result?.token_usage as { in?: number; out?: number; total?: number; cost?: number | null } | null;
  const out = result?.output as { content?: string; model_name?: string; provider_name?: string } | null;

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
      {/* 配置区 */}
      <Card>
        <h2 className="text-lg font-semibold">单模型测试</h2>
        <p className="mt-1 text-sm text-gray-500">选定单个模型跑一次对话，实时查看输出与指标。</p>

        <div className="mt-4 space-y-3">
          <Field label="模型">
            <select
              className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
            >
              {enabledModels.length === 0 && <option value="">（无可用模型）</option>}
              {enabledModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                  {m.provider_name ? ` · ${m.provider_name}` : ""}
                </option>
              ))}
            </select>
          </Field>

          <Field label="System Prompt" hint="可选">
            <CodeTextarea
              rows={3}
              value={system}
              onChange={(e) => setSystem(e.target.value)}
              placeholder="你是一位严谨的中国法律助手…"
            />
          </Field>
          <Field label="User Prompt">
            <CodeTextarea
              rows={5}
              value={user}
              onChange={(e) => setUser(e.target.value)}
              placeholder="请分析以下案件的争议焦点…"
            />
          </Field>
          <Field label="Context" hint="可选，附加上下文">
            <CodeTextarea rows={3} value={context} onChange={(e) => setContext(e.target.value)} placeholder="相关法条 / 案例原文…" />
          </Field>

          <div className="grid grid-cols-2 gap-4 pt-1">
            <ParamSlider label="Temperature" value={temperature} min={0} max={2} step={0.1} onChange={setTemperature} />
            <ParamSlider label="Top P" value={topP} min={0} max={1} step={0.05} onChange={setTopP} />
            <ParamSlider label="Max Token" value={maxTokens} min={256} max={8192} step={256} onChange={setMaxTokens} />
            <label className="flex items-end gap-2 pb-2 text-sm">
              <input type="checkbox" checked={streaming} onChange={(e) => setStreaming(e.target.checked)} />
              流式输出
            </label>
          </div>

          {error && <div className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/15 dark:text-red-300">{error}</div>}

          <Button onClick={run} disabled={running} className="w-full">
            {running ? <><Spinner className="mr-1" /> 测试中…</> : "▶ 开始测试"}
          </Button>
        </div>
      </Card>

      {/* 输出区 */}
      <Card>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-semibold">模型输出</h3>
          {result && (
            <Badge tone={result.status === "success" ? "green" : result.status === "error" ? "red" : "amber"}>
              {result.status}
            </Badge>
          )}
        </div>

        {!result && !running && (
          <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-gray-200 text-sm text-gray-400 dark:border-white/10">
            运行后在此显示输出
          </div>
        )}
        {running && (
          <div className="flex h-64 items-center justify-center text-sm text-gray-400">
            <Spinner className="mr-2" /> 模型调用中…
          </div>
        )}
        {result && (
          <div className="space-y-4">
            <div className="min-h-[8rem] whitespace-pre-wrap rounded-xl bg-gray-50 p-3 text-sm dark:bg-white/5">
              {out?.content ?? <span className="text-gray-400">{result.error_text ?? "无输出"}</span>}
            </div>

            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Metric label="响应时间" value={`${result.latency_ms} ms`} />
              <Metric label="输入 Token" value={tu?.in ?? 0} />
              <Metric label="输出 Token" value={tu?.out ?? 0} />
              <Metric label="预计成本" value={tu?.cost != null ? `$${tu.cost.toFixed(5)}` : "—"} />
            </div>

            <div className="flex flex-wrap gap-2 text-xs text-gray-500">
              <Badge tone="gray">模型：{out?.model_name ?? modelId}</Badge>
              {out?.provider_name && <Badge tone="gray">Provider：{out.provider_name}</Badge>}
            </div>
          </div>
        )}
      </Card>
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
