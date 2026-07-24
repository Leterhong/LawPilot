"use client";

import { useEffect, useState } from "react";
import { api, type AIModelOut, type RoutingRuleOut, type AIMeta } from "@/lib/api";
import { aiFeatureLabels, aiStrategyLabels } from "@/lib/constants";
import { Card, Badge, Button, Input } from "@/components/ui";
import { Banner } from "./Modal";

type RuleForm = {
  id?: string;
  model_id: string;
  fallback_model_ids: string[];
  strategy: string;
  auto_route: boolean;
  prompt_template_key: string | null;
  enabled: boolean;
};

export function RoutingPanel({
  routing,
  models,
  meta,
  reload,
}: {
  routing: RoutingRuleOut[];
  models: AIModelOut[];
  meta: AIMeta;
  reload: () => void;
}) {
  const [selected, setSelected] = useState<string>(meta.features[0] ?? "");
  const [form, setForm] = useState<RuleForm>({
    model_id: "",
    fallback_model_ids: [],
    strategy: "balanced",
    auto_route: false,
    prompt_template_key: null,
    enabled: true,
  });
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const r = routing.find((x) => x.feature === selected);
    if (r) {
      setForm({
        id: r.id,
        model_id: r.model_id,
        fallback_model_ids: r.fallback_model_ids ?? [],
        strategy: r.strategy,
        auto_route: r.auto_route,
        prompt_template_key: r.prompt_template_key,
        enabled: r.enabled,
      });
    } else {
      setForm({
        model_id: "",
        fallback_model_ids: [],
        strategy: "balanced",
        auto_route: false,
        prompt_template_key: null,
        enabled: true,
      });
    }
  }, [selected, routing]);

  function addFallback(mid: string) {
    if (!mid || form.fallback_model_ids.includes(mid)) return;
    setForm((f) => ({ ...f, fallback_model_ids: [...f.fallback_model_ids, mid] }));
  }
  function moveFallback(idx: number, dir: -1 | 1) {
    const arr = [...form.fallback_model_ids];
    const j = idx + dir;
    if (j < 0 || j >= arr.length) return;
    [arr[idx], arr[j]] = [arr[j], arr[idx]];
    setForm((f) => ({ ...f, fallback_model_ids: arr }));
  }
  function removeFallback(idx: number) {
    setForm((f) => ({ ...f, fallback_model_ids: f.fallback_model_ids.filter((_, i) => i !== idx) }));
  }

  async function save() {
    setErr(null);
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        model_id: form.model_id,
        fallback_model_ids: form.fallback_model_ids,
        strategy: form.strategy,
        auto_route: form.auto_route,
        prompt_template_key: form.prompt_template_key || null,
        enabled: form.enabled,
      };
      if (form.id) {
        await api.aiCenter.updateRouting(form.id, payload);
      } else {
        await api.aiCenter.createRouting({ feature: selected, ...(payload as any) });
      }
      setMsg("路由规则已保存");
      reload();
    } catch (e: any) {
      setErr(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  }

  const enabledModels = models.filter((m) => m.is_enabled);
  const modelName = (id: string) => models.find((m) => m.id === id)?.name ?? id;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold">AI 路由规则</h2>
        <p className="text-sm text-gray-500">为每个 AI 功能指定模型、Fallback 链与策略；AIManager 按规则自动调度。</p>
      </div>
      {err && <Banner tone="red">{err}</Banner>}
      {msg && <Banner tone="green">{msg}</Banner>}

      <div className="grid gap-4 md:grid-cols-[260px_1fr]">
        {/* 左：AI 功能列表 */}
        <Card className="h-fit">
          <div className="mb-2 text-sm font-medium text-gray-500">AI 功能</div>
          <div className="space-y-1">
            {meta.features.map((f) => {
              const has = routing.find((r) => r.feature === f && r.enabled);
              const active = f === selected;
              return (
                <button
                  key={f}
                  onClick={() => setSelected(f)}
                  className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition ${
                    active
                      ? "bg-brand-50 font-medium text-brand-700 dark:bg-brand-500/15 dark:text-brand-300"
                      : "hover:bg-gray-100 dark:hover:bg-white/5"
                  }`}
                >
                  <span>{aiFeatureLabels[f] ?? f}</span>
                  {has ? <Badge tone="green">已配置</Badge> : <Badge tone="gray">未配</Badge>}
                </button>
              );
            })}
          </div>
        </Card>

        {/* 右：选中功能的规则编辑 */}
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-medium">{aiFeatureLabels[selected] ?? selected}</h3>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
              />
              启用
            </label>
          </div>

          <div className="space-y-4">
            <div>
              <div className="mb-1 text-sm font-medium text-gray-700 dark:text-gray-300">主模型</div>
              <select
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
                value={form.model_id}
                onChange={(e) => setForm({ ...form, model_id: e.target.value })}
              >
                <option value="">— 请选择模型 —</option>
                {enabledModels.map((m) => (
                  <option key={m.id} value={m.id}>{m.name}（{m.model_name}）</option>
                ))}
              </select>
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.auto_route}
                onChange={(e) => setForm({ ...form, auto_route: e.target.checked })}
              />
              自动路由（Auto Routing：系统按策略在该功能已启用模型间自动择优）
            </label>

            <div>
              <div className="mb-1 text-sm font-medium text-gray-700 dark:text-gray-300">路由策略</div>
              <div className="flex flex-wrap gap-2">
                {meta.strategies.map((s) => (
                  <button
                    key={s}
                    onClick={() => setForm({ ...form, strategy: s })}
                    className={`rounded-lg border px-3 py-1.5 text-sm transition ${
                      form.strategy === s
                        ? "border-brand-400 bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300"
                        : "border-gray-200 dark:border-white/10"
                    }`}
                  >
                    {aiStrategyLabels[s] ?? s}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div className="mb-1 text-sm font-medium text-gray-700 dark:text-gray-300">Fallback 模型链（有序，失败时依次降级）</div>
              <div className="flex gap-2">
                <select
                  className="flex-1 rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
                  value=""
                  onChange={(e) => addFallback(e.target.value)}
                >
                  <option value="">+ 添加 Fallback 模型</option>
                  {enabledModels
                    .filter((m) => m.id !== form.model_id && !form.fallback_model_ids.includes(m.id))
                    .map((m) => (
                      <option key={m.id} value={m.id}>{m.name}</option>
                    ))}
                </select>
              </div>
              <ol className="mt-2 space-y-1">
                {form.fallback_model_ids.map((mid, i) => (
                  <li key={mid} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-1.5 text-sm dark:bg-white/5">
                    <span>
                      <span className="mr-2 text-gray-400">{i + 1}.</span>
                      {modelName(mid)}
                    </span>
                    <span className="flex gap-1">
                      <button className="px-1 text-gray-400 hover:text-gray-700" onClick={() => moveFallback(i, -1)}>↑</button>
                      <button className="px-1 text-gray-400 hover:text-gray-700" onClick={() => moveFallback(i, 1)}>↓</button>
                      <button className="px-1 text-red-400 hover:text-red-600" onClick={() => removeFallback(i)}>✕</button>
                    </span>
                  </li>
                ))}
                {form.fallback_model_ids.length === 0 && (
                  <li className="text-sm text-gray-400">无 Fallback</li>
                )}
              </ol>
            </div>

            <div>
              <div className="mb-1 text-sm font-medium text-gray-700 dark:text-gray-300">绑定 Prompt 模板（可选）</div>
              <Input
                value={form.prompt_template_key ?? ""}
                onChange={(e) => setForm({ ...form, prompt_template_key: e.target.value || null })}
                placeholder="如 legal_analysis（留空则不绑定）"
              />
            </div>

            <div className="flex justify-end pt-2">
              <Button onClick={save} disabled={saving}>{saving ? "保存中…" : "保存规则"}</Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
