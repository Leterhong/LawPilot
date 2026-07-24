"use client";

import { useState } from "react";
import { api, type ProviderOut, type AIMeta } from "@/lib/api";
import { aiProviderTypeLabels } from "@/lib/constants";
import { Card, Badge, Input } from "@/components/ui";
import { Modal, Field, Banner, Button } from "./Modal";

type FormState = {
  id?: string;
  name: string;
  type: string;
  base_url: string;
  api_key: string;
  enabled: boolean;
  description: string;
};

function blank(): FormState {
  return { name: "", type: "openai_compatible", base_url: "", api_key: "", enabled: true, description: "" };
}

export function ProvidersPanel({
  providers,
  meta,
  reload,
}: {
  providers: ProviderOut[];
  meta: AIMeta;
  reload: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<FormState>(blank());
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function openNew() {
    setForm(blank());
    setErr(null);
    setMsg(null);
    setOpen(true);
  }
  function openEdit(p: ProviderOut) {
    setForm({
      id: p.id,
      name: p.name,
      type: p.type,
      base_url: p.base_url ?? "",
      api_key: "",
      enabled: p.enabled,
      description: p.description ?? "",
    });
    setErr(null);
    setMsg(null);
    setOpen(true);
  }

  async function save() {
    setErr(null);
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        name: form.name,
        type: form.type,
        base_url: form.base_url || null,
        enabled: form.enabled,
        description: form.description || null,
      };
      if (form.api_key) payload.api_key = form.api_key;
      if (form.id) {
        await api.aiCenter.updateProvider(form.id, payload);
      } else {
        await api.aiCenter.createProvider(payload as any);
      }
      setMsg(form.id ? "Provider 已更新" : "Provider 已添加");
      setOpen(false);
      reload();
    } catch (e: any) {
      setErr(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function toggle(p: ProviderOut) {
    try {
      await api.aiCenter.updateProvider(p.id, { enabled: !p.enabled });
      reload();
    } catch (e: any) {
      setErr(e.message);
    }
  }
  async function remove(p: ProviderOut) {
    if (!confirm(`确认删除 Provider「${p.name}」？关联模型将变为独立模型。`)) return;
    try {
      await api.aiCenter.deleteProvider(p.id);
      reload();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Provider 管理</h2>
          <p className="text-sm text-gray-500">管理多家 OpenAI Compatible 等 Provider。</p>
        </div>
        <Button onClick={openNew}>+ 新增 Provider</Button>
      </div>

      {err && <Banner tone="red">{err}</Banner>}
      {msg && <Banner tone="green">{msg}</Banner>}

      <div className="grid gap-3">
        {providers.length === 0 && (
          <Card className="text-center text-sm text-gray-400">暂无 Provider。</Card>
        )}
        {providers.map((p) => (
          <Card key={p.id} className="flex items-center justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium">{p.name}</span>
                <Badge tone="brand">{aiProviderTypeLabels[p.type] ?? p.type}</Badge>
                <Badge tone={p.enabled ? "green" : "gray"}>{p.enabled ? "已启用" : "已禁用"}</Badge>
              </div>
              <div className="mt-1 truncate text-xs text-gray-500">
                {p.base_url || "无 Base URL"}
                {p.api_key ? " · 🔑 已配置" : " · 未配置 Key"}
              </div>
            </div>
            <div className="flex shrink-0 gap-2">
              <Button size="sm" variant="outline" onClick={() => openEdit(p)}>编辑</Button>
              <Button size="sm" variant="ghost" onClick={() => toggle(p)}>
                {p.enabled ? "禁用" : "启用"}
              </Button>
              <Button size="sm" variant="danger" onClick={() => remove(p)}>删除</Button>
            </div>
          </Card>
        ))}
      </div>

      <Modal
        open={open}
        title={form.id ? "编辑 Provider" : "新增 Provider"}
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>取消</Button>
            <Button onClick={save} disabled={saving}>{saving ? "保存中…" : "保存"}</Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label="名称" hint="显示名">
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="硅基流动" />
            </Field>
            <Field label="类型">
              <select
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
                value={form.type}
                onChange={(e) => setForm({ ...form, type: e.target.value })}
              >
                {meta.provider_types.map((t) => (
                  <option key={t} value={t}>{aiProviderTypeLabels[t] ?? t}</option>
                ))}
              </select>
            </Field>
            <Field label="Base URL">
              <Input value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://api.siliconflow.cn/v1" />
            </Field>
            <Field label="API Key" hint={form.id ? "留空=不修改" : ""}>
              <Input type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} placeholder="sk-…（加密存储）" />
            </Field>
          </div>
          <Field label="备注">
            <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="可选" />
          </Field>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
            启用该 Provider
          </label>
        </div>
      </Modal>
    </div>
  );
}
