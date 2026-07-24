"use client";

import { useState } from "react";
import { api, type AIModelOut, type ProviderOut, type AIMeta, type TestConnectionResult } from "@/lib/api";
import { aiProviderTypeLabels, aiCapabilityLabels } from "@/lib/constants";
import { Card, Badge, Input, Textarea } from "@/components/ui";
import { Modal, Field, Banner, Button } from "./Modal";

type FormState = {
  id?: string;
  name: string;
  provider_id: string;
  model_name: string;
  api_key: string;
  base_url: string;
  embedding_model: string;
  vision_model: string;
  reranker_model: string;
  embedding_dim: string;
  temperature: string;
  top_p: string;
  timeout: string;
  max_tokens: string;
  is_default: boolean;
  is_enabled: boolean;
  capabilities: Record<string, boolean>;
  advanced: Record<string, string>;
};

const CAP_DEFAULTS: Record<string, boolean> = {
  chat: true,
  embedding: false,
  vision: false,
  streaming: true,
  json_mode: true,
  function_calling: true,
  web_search: false,
  reasoning: false,
};
const ADV_DEFAULTS: Record<string, string> = {
  auto_retry: "3",
  max_concurrency: "4",
  rate_limit_rpm: "0",
  rate_limit_tpm: "0",
};

function blankForm(): FormState {
  return {
    name: "",
    provider_id: "",
    model_name: "",
    api_key: "",
    base_url: "",
    embedding_model: "",
    vision_model: "",
    reranker_model: "",
    embedding_dim: "1024",
    temperature: "0.2",
    top_p: "1.0",
    timeout: "60",
    max_tokens: "",
    is_default: false,
    is_enabled: true,
    capabilities: { ...CAP_DEFAULTS },
    advanced: { ...ADV_DEFAULTS },
  };
}

function fromModel(m: AIModelOut): FormState {
  return {
    id: m.id,
    name: m.name,
    provider_id: m.provider_id ?? "",
    model_name: m.model_name,
    api_key: "",
    base_url: m.base_url ?? "",
    embedding_model: m.embedding_model ?? "",
    vision_model: m.vision_model ?? "",
    reranker_model: m.reranker_model ?? "",
    embedding_dim: m.embedding_dim != null ? String(m.embedding_dim) : "1024",
    temperature: String(m.temperature),
    top_p: String(m.top_p),
    timeout: String(m.timeout),
    max_tokens: m.max_tokens != null ? String(m.max_tokens) : "",
    is_default: m.is_default,
    is_enabled: m.is_enabled,
    capabilities: { ...CAP_DEFAULTS, ...(m.capabilities || {}) },
    advanced: {
      auto_retry: String((m.advanced as any)?.auto_retry ?? 3),
      max_concurrency: String((m.advanced as any)?.max_concurrency ?? 4),
      rate_limit_rpm: String((m.advanced as any)?.rate_limit_rpm ?? 0),
      rate_limit_tpm: String((m.advanced as any)?.rate_limit_tpm ?? 0),
    },
  };
}

export function ModelsPanel({
  models,
  providers,
  meta,
  reload,
}: {
  models: AIModelOut[];
  providers: ProviderOut[];
  meta: AIMeta;
  reload: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<FormState>(blankForm());
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [test, setTest] = useState<{ loading: boolean; result: TestConnectionResult | null }>({
    loading: false,
    result: null,
  });
  const [testCap, setTestCap] = useState("chat");

  function openNew() {
    setForm(blankForm());
    setErr(null);
    setMsg(null);
    setTest({ loading: false, result: null });
    setOpen(true);
  }
  function openEdit(m: AIModelOut) {
    setForm(fromModel(m));
    setErr(null);
    setMsg(null);
    setTest({ loading: false, result: null });
    setOpen(true);
  }
  function onProviderChange(pid: string) {
    const p = providers.find((x) => x.id === pid);
    setForm((f) => ({
      ...f,
      provider_id: pid,
      provider_type: p?.type ?? "",
      base_url: p?.base_url ?? f.base_url,
    }));
  }
  function setCap(k: string, v: boolean) {
    setForm((f) => ({ ...f, capabilities: { ...f.capabilities, [k]: v } }));
  }
  function setAdv(k: string, v: string) {
    setForm((f) => ({ ...f, advanced: { ...f.advanced, [k]: v } }));
  }

  async function save() {
    setErr(null);
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        name: form.name,
        model_name: form.model_name,
        provider_id: form.provider_id || null,
        base_url: form.base_url || null,
        embedding_model: form.embedding_model || null,
        vision_model: form.vision_model || null,
        reranker_model: form.reranker_model || null,
        embedding_dim: form.embedding_dim ? Number(form.embedding_dim) : null,
        temperature: Number(form.temperature),
        top_p: Number(form.top_p),
        timeout: Number(form.timeout),
        max_tokens: form.max_tokens ? Number(form.max_tokens) : null,
        is_default: form.is_default,
        is_enabled: form.is_enabled,
        capabilities: form.capabilities,
        advanced: {
          auto_retry: Number(form.advanced.auto_retry),
          max_concurrency: Number(form.advanced.max_concurrency),
          rate_limit_rpm: Number(form.advanced.rate_limit_rpm),
          rate_limit_tpm: Number(form.advanced.rate_limit_tpm),
        },
      };
      if (!form.id && form.api_key) payload.api_key = form.api_key;
      if (form.id && form.api_key) payload.api_key = form.api_key;
      if (form.id) {
        await api.aiCenter.updateModel(form.id, payload);
      } else {
        await api.aiCenter.createModel(payload as any);
      }
      setMsg(form.id ? "模型已更新" : "模型已添加");
      setOpen(false);
      reload();
    } catch (e: any) {
      setErr(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function runTest() {
    setTest({ loading: true, result: null });
    try {
      const res = await api.aiCenter.testConnection({
        model_id: form.id || undefined,
        provider_type: form.provider_id
          ? providers.find((p) => p.id === form.provider_id)?.type
          : undefined,
        base_url: form.base_url || null,
        api_key: form.api_key || null,
        model_name: form.model_name || null,
        capability: testCap,
      });
      setTest({ loading: false, result: res });
    } catch (e: any) {
      setTest({ loading: false, result: { status: "fail", capability: testCap, error: e.message } as any });
    }
  }

  async function toggleEnabled(m: AIModelOut) {
    try {
      await api.aiCenter.updateModel(m.id, { is_enabled: !m.is_enabled });
      reload();
    } catch (e: any) {
      setErr(e.message);
    }
  }
  async function setDefault(m: AIModelOut) {
    try {
      await api.aiCenter.updateModel(m.id, { is_default: true });
      reload();
    } catch (e: any) {
      setErr(e.message);
    }
  }
  async function remove(m: AIModelOut) {
    if (!confirm(`确认删除模型「${m.name}」？该操作不可恢复。`)) return;
    try {
      await api.aiCenter.deleteModel(m.id);
      reload();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">模型管理</h2>
          <p className="text-sm text-gray-500">添加 / 编辑 / 测试 / 删除模型，统一由 AIManager 调度。</p>
        </div>
        <Button onClick={openNew}>+ 添加模型</Button>
      </div>

      {err && <Banner tone="red">{err}</Banner>}
      {msg && <Banner tone="green">{msg}</Banner>}

      <div className="grid gap-3">
        {models.length === 0 && (
          <Card className="text-center text-sm text-gray-400">暂无模型，点击「添加模型」开始配置。</Card>
        )}
        {models.map((m) => (
          <Card key={m.id} className="flex items-center justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium">{m.name}</span>
                {m.is_default && <Badge tone="brand">默认</Badge>}
                <Badge tone={m.is_enabled ? "green" : "gray"}>{m.is_enabled ? "已启用" : "已禁用"}</Badge>
                {m.provider_name && <Badge tone="gray">{m.provider_name}</Badge>}
              </div>
              <div className="mt-1 truncate text-xs text-gray-500">
                {m.model_name}
                {m.base_url ? ` · ${m.base_url}` : ""} · T={m.temperature} · topP={m.top_p}
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={() => openEdit(m)}>编辑</Button>
              <Button size="sm" variant="ghost" onClick={() => toggleEnabled(m)}>
                {m.is_enabled ? "禁用" : "启用"}
              </Button>
              {!m.is_default && (
                <Button size="sm" variant="ghost" onClick={() => setDefault(m)}>设默认</Button>
              )}
              <Button size="sm" variant="danger" onClick={() => remove(m)}>删除</Button>
            </div>
          </Card>
        ))}
      </div>

      <Modal
        open={open}
        title={form.id ? "编辑模型" : "添加模型"}
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>取消</Button>
            <Button onClick={save} disabled={saving}>
              {saving ? "保存中…" : "保存"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label="模型名称" hint="显示名">
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="DeepSeek V3" />
            </Field>
            <Field label="Provider">
              <select
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
                value={form.provider_id}
                onChange={(e) => onProviderChange(e.target.value)}
              >
                <option value="">— 独立自定义（无 Provider）—</option>
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </Field>
            <Field label="Model Name" hint="API 调用的模型标识">
              <Input value={form.model_name} onChange={(e) => setForm({ ...form, model_name: e.target.value })} placeholder="deepseek-chat" />
            </Field>
            <Field label="API Key" hint="留空=不修改">
              <Input type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} placeholder="sk-…（加密存储）" />
            </Field>
            <Field label="Base URL">
              <Input value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://api.openai.com/v1" />
            </Field>
            <Field label="Embedding 模型">
              <Input value={form.embedding_model} onChange={(e) => setForm({ ...form, embedding_model: e.target.value })} placeholder="text-embedding-3-small" />
            </Field>
            <Field label="Vision 模型">
              <Input value={form.vision_model} onChange={(e) => setForm({ ...form, vision_model: e.target.value })} placeholder="gpt-4o" />
            </Field>
            <Field label="Reranker 模型">
              <Input value={form.reranker_model} onChange={(e) => setForm({ ...form, reranker_model: e.target.value })} placeholder="bge-reranker" />
            </Field>
            <Field label="Embedding 维度">
              <Input value={form.embedding_dim} onChange={(e) => setForm({ ...form, embedding_dim: e.target.value })} />
            </Field>
            <Field label="Temperature">
              <Input value={form.temperature} onChange={(e) => setForm({ ...form, temperature: e.target.value })} />
            </Field>
            <Field label="TopP">
              <Input value={form.top_p} onChange={(e) => setForm({ ...form, top_p: e.target.value })} />
            </Field>
            <Field label="Timeout(秒)">
              <Input value={form.timeout} onChange={(e) => setForm({ ...form, timeout: e.target.value })} />
            </Field>
            <Field label="Max Tokens" hint="留空=不限制">
              <Input value={form.max_tokens} onChange={(e) => setForm({ ...form, max_tokens: e.target.value })} />
            </Field>
          </div>

          <div>
            <div className="mb-2 text-sm font-medium text-gray-700 dark:text-gray-300">能力开关</div>
            <div className="flex flex-wrap gap-3">
              {meta.capability_keys.map((k) => (
                <label key={k} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={!!form.capabilities[k]}
                    onChange={(e) => setCap(k, e.target.checked)}
                  />
                  {aiCapabilityLabels[k] ?? k}
                </label>
              ))}
            </div>
          </div>

          <div>
            <div className="mb-2 text-sm font-medium text-gray-700 dark:text-gray-300">高级配置</div>
            <div className="grid grid-cols-4 gap-3">
              <Field label="自动重试">
                <Input value={form.advanced.auto_retry} onChange={(e) => setAdv("auto_retry", e.target.value)} />
              </Field>
              <Field label="并发数">
                <Input value={form.advanced.max_concurrency} onChange={(e) => setAdv("max_concurrency", e.target.value)} />
              </Field>
              <Field label="限流 RPM">
                <Input value={form.advanced.rate_limit_rpm} onChange={(e) => setAdv("rate_limit_rpm", e.target.value)} />
              </Field>
              <Field label="限流 TPM">
                <Input value={form.advanced.rate_limit_tpm} onChange={(e) => setAdv("rate_limit_tpm", e.target.value)} />
              </Field>
            </div>
          </div>

          <div className="flex items-end gap-2 border-t border-gray-100 pt-4 dark:border-white/10">
            <div className="flex-1">
              <Field label="测试连接能力">
                <select
                  className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
                  value={testCap}
                  onChange={(e) => setTestCap(e.target.value)}
                >
                  {["chat", "embedding", "vision", "streaming"].map((c) => (
                    <option key={c} value={c}>{aiCapabilityLabels[c] ?? c}</option>
                  ))}
                </select>
              </Field>
            </div>
            <Button variant="outline" onClick={runTest} disabled={test.loading}>
              {test.loading ? "测试中…" : "测试连接"}
            </Button>
          </div>
          {test.result && (
            <Banner tone={test.result.status === "ok" ? "green" : "red"}>
              {test.result.status === "ok" ? "✓ 连接成功" : "✗ 连接失败"}
              {test.result.latency_ms != null && ` · ${test.result.latency_ms}ms`}
              {test.result.model && ` · ${test.result.model}`}
              {test.result.capabilities_detected?.length
                ? ` · 探测到能力：${test.result.capabilities_detected.join(", ")}`
                : ""}
              {test.result.error && ` · ${test.result.error}`}
            </Banner>
          )}
        </div>
      </Modal>
    </div>
  );
}
