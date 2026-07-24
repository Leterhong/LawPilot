// 功能七：我的收藏（Prompt Library）。
"use client";

import { useEffect, useState } from "react";
import { api, type PromptLibraryOut } from "@/lib/api";
import { Card, Badge, Button, Input, Textarea, Spinner } from "@/components/ui";
import { Modal, Field } from "@/components/ai-center/Modal";

export function LibraryPanel() {
  const [items, setItems] = useState<PromptLibraryOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [name, setName] = useState("");
  const [category, setCategory] = useState("playground");
  const [prompt, setPrompt] = useState("");
  const [variables, setVariables] = useState("");

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setItems(await api.playground.listPrompts());
    } catch (e: any) {
      setError(e.message || "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function save() {
    setError(null);
    if (!name.trim()) return setError("请填写名称");
    if (!prompt.trim()) return setError("请填写 Prompt 内容");
    setSaving(true);
    try {
      const vars = variables
        .split(/[,\n]/)
        .map((v) => v.trim())
        .filter(Boolean);
      await api.playground.createPrompt({
        name: name.trim(),
        category: category || null,
        prompt: prompt,
        variables: vars.length ? vars : null,
      });
      setOpen(false);
      setName("");
      setPrompt("");
      setVariables("");
      await load();
    } catch (e: any) {
      setError(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: string) {
    if (!confirm("确认删除该收藏？")) return;
    try {
      await api.playground.deletePrompt(id);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">我的收藏</h2>
        <Button size="sm" onClick={() => setOpen(true)}>+ 新建收藏</Button>
      </div>
      {loading && <div className="flex items-center text-sm text-gray-400"><Spinner className="mr-2" /> 加载中…</div>}
      {error && <div className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/15 dark:text-red-300">{error}</div>}
      {!loading && items.length === 0 && <div className="text-sm text-gray-400">暂无收藏，点击「新建收藏」保存优秀 Prompt。</div>}

      <div className="space-y-2">
        {items.map((p) => (
          <div key={p.id} className="rounded-xl border border-gray-100 p-3 dark:border-white/10">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="font-medium">{p.name}</span>
                {p.category && <Badge tone="gray">{p.category}</Badge>}
                {p.is_public && <Badge tone="green">公开</Badge>}
                {p.score != null && <Badge tone="brand">评分 {p.score.toFixed(1)}</Badge>}
              </div>
              <Button size="sm" variant="ghost" onClick={() => remove(p.id)}>删除</Button>
            </div>
            <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap rounded-lg bg-gray-50 p-2 font-mono text-xs text-gray-600 dark:bg-white/5">
              {p.prompt}
            </pre>
            {p.variables && p.variables.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-1">
                {p.variables.map((v) => (
                  <span key={v} className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[11px] text-gray-500 dark:bg-white/10">
                    {`{{${v}}}`}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <Modal
        open={open}
        title="新建收藏"
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>取消</Button>
            <Button onClick={save} disabled={saving}>{saving ? "保存中…" : "保存"}</Button>
          </>
        }
      >
        <div className="space-y-3">
          {error && <div className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/15 dark:text-red-300">{error}</div>}
          <Field label="名称">
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="如：法律分析 v2" />
          </Field>
          <Field label="分类">
            <Input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="playground" />
          </Field>
          <Field label="Prompt 内容">
            <Textarea rows={6} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="支持 {{case}} {{law}} 等变量" />
          </Field>
          <Field label="变量" hint="逗号或换行分隔">
            <Input value={variables} onChange={(e) => setVariables(e.target.value)} placeholder="case, law, context" />
          </Field>
        </div>
      </Modal>
    </Card>
  );
}
