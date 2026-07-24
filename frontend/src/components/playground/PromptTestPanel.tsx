// 模式三：Prompt 测试（变量化 Prompt + 收藏）。
"use client";

import { useEffect, useMemo, useState } from "react";
import { api, type PlaygroundModelOut, type PlaygroundSessionOut, type PromptLibraryOut } from "@/lib/api";
import { Card, Button, Input, Spinner } from "@/components/ui";
import { CodeTextarea, Metric } from "./Shared";

const KNOWN_VARS = ["case", "law", "context", "document"];

export function PromptTestPanel({ models }: { models: PlaygroundModelOut[] }) {
  const enabled = models.filter((m) => m.is_enabled);
  const [system, setSystem] = useState("请分析以下案件：\n\n{{case}}");
  const [user, setUser] = useState("结合{{law}}，给出争议焦点与建议。");
  const [modelId, setModelId] = useState(enabled[0]?.id ?? "");
  const [vars, setVars] = useState<Record<string, string>>({});
  const [name, setName] = useState("");
  const [library, setLibrary] = useState<PromptLibraryOut[]>([]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<PlaygroundSessionOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // 自动识别 {{var}}
  const detected = useMemo(() => {
    const text = `${system}\n${user}`;
    const set = new Set<string>(KNOWN_VARS.filter((v) => text.includes(`{{${v}}}`)));
    const re = /\{\{\s*(\w+)\s*\}\}/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text))) set.add(m[1]);
    return Array.from(set);
  }, [system, user]);

  useEffect(() => {
    api.playground.listPrompts().then(setLibrary).catch(() => {});
  }, []);

  function fillVars(tpl: string): string {
    return tpl.replace(/\{\{\s*(\w+)\s*\}\}/g, (_, k) => vars[k] ?? `{{${k}}}`);
  }

  async function run() {
    setError(null);
    if (!modelId) return setError("请先选择模型");
    const u = fillVars(user);
    if (u.includes("{{")) return setError("请填写所有变量后再运行");
    setRunning(true);
    setResult(null);
    try {
      const r = await api.playground.test({
        model_id: modelId,
        system_prompt: fillVars(system) || null,
        user_prompt: u,
      });
      setResult(r);
    } catch (e: any) {
      setError(e.message || "运行失败");
    } finally {
      setRunning(false);
    }
  }

  async function saveLib() {
    setSaved(false);
    if (!name.trim()) return setError("请填写收藏名称");
    try {
      const created = await api.playground.createPrompt({
        name: name.trim(),
        category: "playground",
        prompt: `${system}\n---\n${user}`,
        variables: detected,
      });
      setLibrary((l) => [created, ...l]);
      setSaved(true);
      setName("");
    } catch (e: any) {
      setError(e.message || "收藏失败");
    }
  }

  function loadLib(p: PromptLibraryOut) {
    // 简单拆分：以 "---" 分隔 system / user
    const [s, u] = p.prompt.split("\n---\n");
    setSystem(s ?? "");
    setUser(u ?? p.prompt);
    setName(p.name);
  }

  const tu = result?.token_usage as { in?: number; out?: number; cost?: number | null } | null;
  const out = result?.output as { content?: string } | null;

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
      <Card>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Prompt 测试</h2>
          {library.length > 0 && (
            <select
              className="rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-xs dark:border-white/10 dark:bg-white/5"
              value=""
              onChange={(e) => {
                const p = library.find((x) => x.id === e.target.value);
                if (p) loadLib(p);
              }}
            >
              <option value="">载入收藏…</option>
              {library.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          )}
        </div>

        <div className="mt-4 space-y-3">
          <Field label="System Prompt" hint="可用 {{case}} {{law}} {{context}} {{document}}">
            <CodeTextarea rows={4} value={system} onChange={(e) => setSystem(e.target.value)} />
          </Field>
          <Field label="User Prompt">
            <CodeTextarea rows={4} value={user} onChange={(e) => setUser(e.target.value)} />
          </Field>

          {detected.length > 0 && (
            <div className="space-y-2 rounded-xl border border-gray-100 p-3 dark:border-white/10">
              <div className="text-xs font-medium text-gray-500">变量填充</div>
              {detected.map((v) => (
                <div key={v} className="grid grid-cols-[100px_1fr] items-center gap-2">
                  <span className="font-mono text-xs text-brand-600">{`{{${v}}}`}</span>
                  <Input
                    value={vars[v] ?? ""}
                    onChange={(e) => setVars((prev) => ({ ...prev, [v]: e.target.value }))}
                    placeholder={`输入 ${v}…`}
                  />
                </div>
              ))}
            </div>
          )}

          <Field label="测试模型">
            <select
              className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
            >
              {enabled.map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          </Field>

          {error && <div className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/15 dark:text-red-300">{error}</div>}

          <div className="flex gap-2">
            <Button onClick={run} disabled={running} className="flex-1">
              {running ? <><Spinner className="mr-1" /> 运行中…</> : "▶ 运行"}
            </Button>
          </div>

          <div className="border-t border-gray-100 pt-3 dark:border-white/10">
            <div className="mb-1 flex items-center gap-2">
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="收藏名称（如：法律分析 v2）" />
              <Button variant="outline" onClick={saveLib}>收藏</Button>
            </div>
            {saved && <div className="text-xs text-green-600">已收藏到「我的收藏」</div>}
          </div>
        </div>
      </Card>

      <Card>
        <h3 className="mb-3 font-semibold">运行结果</h3>
        {!result && !running && (
          <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-gray-200 text-sm text-gray-400 dark:border-white/10">运行后显示</div>
        )}
        {running && <div className="flex h-64 items-center justify-center text-sm text-gray-400"><Spinner className="mr-2" /> 调用中…</div>}
        {result && (
          <div className="space-y-4">
            <div className="min-h-[8rem] whitespace-pre-wrap rounded-xl bg-gray-50 p-3 text-sm dark:bg-white/5">
              {out?.content ?? <span className="text-gray-400">{result.error_text ?? "无输出"}</span>}
            </div>
            <div className="grid grid-cols-3 gap-2">
              <Metric label="响应" value={`${result.latency_ms} ms`} />
              <Metric label="Token" value={(tu?.in ?? 0) + (tu?.out ?? 0)} />
              <Metric label="成本" value={tu?.cost != null ? `$${tu.cost.toFixed(5)}` : "—"} />
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
