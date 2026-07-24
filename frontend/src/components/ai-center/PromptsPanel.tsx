"use client";

import { useState } from "react";
import { api, type PromptTemplateOut, type AIModelOut, type PromptVersionOut } from "@/lib/api";
import { Card, Badge, Input, Textarea } from "@/components/ui";
import { Modal, Field, Banner, Button } from "./Modal";

type FormState = {
  id?: string;
  key: string;
  name: string;
  content: string;
  variables: string;
  enabled: boolean;
  model_id: string | null;
};

function blank(): FormState {
  return { key: "", name: "", content: "", variables: "", enabled: true, model_id: null };
}

export function PromptsPanel({
  prompts,
  models,
  reload,
}: {
  prompts: PromptTemplateOut[];
  models: AIModelOut[];
  reload: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<FormState>(blank());
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [versions, setVersions] = useState<{ id: string; name: string; data: PromptVersionOut[] } | null>(null);

  function openNew() {
    setForm(blank());
    setErr(null);
    setMsg(null);
    setOpen(true);
  }
  function openEdit(p: PromptTemplateOut) {
    setForm({
      id: p.id,
      key: p.key,
      name: p.name,
      content: p.content,
      variables: p.variables ? JSON.stringify(p.variables, null, 2) : "",
      enabled: p.enabled,
      model_id: p.model_id,
    });
    setErr(null);
    setMsg(null);
    setOpen(true);
  }

  async function save() {
    setErr(null);
    setSaving(true);
    let variables: unknown = null;
    if (form.variables.trim()) {
      try {
        variables = JSON.parse(form.variables);
      } catch {
        setErr("变量必须是合法 JSON 数组，如 [{\"name\":\"case\",\"desc\":\"案件\"}]");
        setSaving(false);
        return;
      }
    }
    try {
      const payload: Record<string, unknown> = {
        key: form.key,
        name: form.name,
        content: form.content,
        variables,
        enabled: form.enabled,
        model_id: form.model_id || null,
      };
      if (form.id) {
        await api.aiCenter.updatePrompt(form.id, payload);
      } else {
        await api.aiCenter.createPrompt(payload as any);
      }
      setMsg(form.id ? "Prompt 已更新（新版本已记录）" : "Prompt 已添加");
      setOpen(false);
      reload();
    } catch (e: any) {
      setErr(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function toggle(p: PromptTemplateOut) {
    try {
      await api.aiCenter.updatePrompt(p.id, { enabled: !p.enabled });
      reload();
    } catch (e: any) {
      setErr(e.message);
    }
  }
  async function remove(p: PromptTemplateOut) {
    if (!confirm(`确认删除 Prompt「${p.name}」？`)) return;
    try {
      await api.aiCenter.deletePrompt(p.id);
      reload();
    } catch (e: any) {
      setErr(e.message);
    }
  }
  async function showVersions(p: PromptTemplateOut) {
    try {
      const data = await api.aiCenter.promptVersions(p.id);
      setVersions({ id: p.id, name: p.name, data });
    } catch (e: any) {
      setErr(e.message);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Prompt 管理</h2>
          <p className="text-sm text-gray-500">所有 Prompt 禁止硬编码在代码中，统一在此维护并带版本历史。</p>
        </div>
        <Button onClick={openNew}>+ 新增 Prompt</Button>
      </div>

      {err && <Banner tone="red">{err}</Banner>}
      {msg && <Banner tone="green">{msg}</Banner>}

      <div className="grid gap-3">
        {prompts.length === 0 && <Card className="text-center text-sm text-gray-400">暂无 Prompt 模板。</Card>}
        {prompts.map((p) => (
          <Card key={p.id} className="flex items-center justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium">{p.name}</span>
                <Badge tone="gray">{p.key}</Badge>
                <Badge tone="brand">v{p.current_version}</Badge>
                <Badge tone={p.enabled ? "green" : "gray"}>{p.enabled ? "启用" : "禁用"}</Badge>
              </div>
              <div className="mt-1 line-clamp-1 text-xs text-gray-500">{p.content}</div>
            </div>
            <div className="flex shrink-0 gap-2">
              <Button size="sm" variant="outline" onClick={() => openEdit(p)}>编辑</Button>
              <Button size="sm" variant="ghost" onClick={() => showVersions(p)}>历史</Button>
              <Button size="sm" variant="ghost" onClick={() => toggle(p)}>{p.enabled ? "禁用" : "启用"}</Button>
              <Button size="sm" variant="danger" onClick={() => remove(p)}>删除</Button>
            </div>
          </Card>
        ))}
      </div>

      <Modal
        open={open}
        title={form.id ? "编辑 Prompt" : "新增 Prompt"}
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
            <Field label="Key" hint="代码引用标识">
              <Input value={form.key} onChange={(e) => setForm({ ...form, key: e.target.value })} placeholder="legal_analysis" disabled={!!form.id} />
            </Field>
            <Field label="名称">
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="法律分析 Prompt" />
            </Field>
          </div>
          <Field label="Prompt 内容" hint="支持 {变量} 占位">
            <Textarea
              rows={8}
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
              placeholder="你是一个专业律师，请分析以下案件：{case}"
            />
          </Field>
          <Field label="变量（JSON 数组，可选）">
            <Textarea
              rows={3}
              value={form.variables}
              onChange={(e) => setForm({ ...form, variables: e.target.value })}
              placeholder='[{"name":"case","desc":"案件描述"}]'
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="绑定模型（可选）">
              <select
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
                value={form.model_id ?? ""}
                onChange={(e) => setForm({ ...form, model_id: e.target.value || null })}
              >
                <option value="">— 不绑定 —</option>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </Field>
            <label className="flex items-center gap-2 self-end pb-2.5 text-sm">
              <input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />
              启用
            </label>
          </div>
        </div>
      </Modal>

      <Modal
        open={!!versions}
        title={versions ? `「${versions.name}」版本历史` : ""}
        onClose={() => setVersions(null)}
        maxWidth="max-w-3xl"
      >
        {versions && (
          <div className="space-y-3">
            {versions.data.length === 0 && <div className="text-sm text-gray-400">暂无历史版本。</div>}
            {versions.data.map((v) => (
              <Card key={v.id}>
                <div className="mb-1 flex items-center gap-2 text-sm">
                  <Badge tone="brand">v{v.version}</Badge>
                  {v.note && <span className="text-gray-500">{v.note}</span>}
                  <span className="ml-auto text-xs text-gray-400">{v.created_at}</span>
                </div>
                <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-gray-50 p-3 text-xs dark:bg-white/5">{v.content}</pre>
              </Card>
            ))}
          </div>
        )}
      </Modal>
    </div>
  );
}
