// 案件中心 - 列表页（Case Center）
// SaaS 风格：卡片网格 + 搜索 + 状态/标签筛选 + 分页 + 星标/收藏 + 新建/编辑/删除。
// 数据来自 /api/cases（case_center 表），与 Phase1 /api/v1/cases 相互独立。
"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Search,
  Plus,
  Star,
  Trash2,
  Pencil,
  Loader2,
  FolderOpen,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import api, {
  type CaseCenterOut,
  type CaseCenterStatus,
  type CaseType,
  type Priority,
} from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { Badge, Button, Card, Input, Spinner, Textarea } from "@/components/ui";
import {
  caseCenterStatusLabels,
  caseCenterStatusTone,
  caseTypeLabels,
  priorityLabels,
} from "@/lib/constants";

type Tab = "all" | "starred" | "favorite";

const STATUS_OPTIONS: CaseCenterStatus[] = [
  "pending",
  "in_progress",
  "waiting_reply",
  "waiting_material",
  "complained",
  "sued",
  "completed",
  "closed",
];

const COLOR_OPTIONS = [
  "#4F46E5",
  "#0EA5E9",
  "#10B981",
  "#F59E0B",
  "#EF4444",
  "#8B5CF6",
  "#EC4899",
  "#64748B",
];

export default function CaseCenterPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [items, setItems] = useState<CaseCenterOut[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(true);

  const [q, setQ] = useState("");
  const [status, setStatus] = useState<CaseCenterStatus | "">("");
  const [tag, setTag] = useState("");
  const [tab, setTab] = useState<Tab>("all");

  const [editing, setEditing] = useState<CaseCenterOut | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formBusy, setFormBusy] = useState(false);

  const pageSize = 12;

  async function load() {
    setBusy(true);
    try {
      const p = await api.caseCenter.list({
        q: q || undefined,
        status: status || undefined,
        tag: tag || undefined,
        starred: tab === "starred" ? true : undefined,
        favorite: tab === "favorite" ? true : undefined,
        page,
        page_size: pageSize,
      });
      setItems(p.items);
      setTotal(p.total);
    } catch {
      setItems([]);
      setTotal(0);
    } finally {
      setBusy(false);
    }
  }

  // 搜索/筛选变化时回到第一页
  useEffect(() => {
    setPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, status, tag, tab]);

  useEffect(() => {
    if (loading) return;
    if (!user) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, loading, page, q, status, tag, tab]);

  async function toggleStar(c: CaseCenterOut) {
    const updated = await api.caseCenter.update(c.id, { starred: !c.starred });
    setItems((prev) => prev.map((x) => (x.id === c.id ? updated : x)));
  }
  async function toggleFavorite(c: CaseCenterOut) {
    const updated = await api.caseCenter.update(c.id, { favorite: !c.favorite });
    setItems((prev) => prev.map((x) => (x.id === c.id ? updated : x)));
  }
  async function remove(c: CaseCenterOut) {
    if (!confirm(`确定删除「${c.title}」？该操作不可恢复。`)) return;
    await api.caseCenter.remove(c.id);
    load();
  }

  const allTags = useMemo(() => {
    const s = new Set<string>();
    items.forEach((c) => c.tags?.forEach((t) => s.add(t)));
    return Array.from(s);
  }, [items]);

  if (!loading && !user) {
    return (
      <AppShell>
        <div className="py-20 text-center text-gray-500 dark:text-gray-400">
          请先
          <Link href="/login" className="mx-1 text-brand-600 hover:underline">
            登录
          </Link>
          查看你的案件中心。
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">📁 我的案件</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            共 {total} 个案件 · 拖拽排序、星标与标签帮你聚焦重要事项
          </p>
        </div>
        <Button onClick={() => { setEditing(null); setShowForm(true); }}>
          <Plus className="h-4 w-4" /> 新建案件
        </Button>
      </div>

      {/* 搜索 + 筛选 */}
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="搜索案件名称…"
            className="pl-9"
          />
        </div>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as CaseCenterStatus | "")}
          className="rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm outline-none dark:border-white/10 dark:bg-white/5"
        >
          <option value="">全部状态</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {caseCenterStatusLabels[s]}
            </option>
          ))}
        </select>
        <select
          value={tag}
          onChange={(e) => setTag(e.target.value)}
          className="rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm outline-none dark:border-white/10 dark:bg-white/5"
        >
          <option value="">全部标签</option>
          {allTags.map((t) => (
            <option key={t} value={t}>
              #{t}
            </option>
          ))}
        </select>
      </div>

      {/* 快捷标签栏 */}
      <div className="mb-5 flex gap-2">
        {(["all", "starred", "favorite"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={
              "rounded-full px-3 py-1.5 text-sm transition " +
              (tab === t
                ? "bg-brand-500 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-white/10 dark:text-gray-300")
            }
          >
            {t === "all" ? "全部" : t === "starred" ? "⭐ 星标" : "❤️ 收藏"}
          </button>
        ))}
      </div>

      {busy ? (
        <div className="flex justify-center py-20">
          <Spinner />
        </div>
      ) : items.length === 0 ? (
        <Card className="py-16 text-center text-gray-500 dark:text-gray-400">
          <FolderOpen className="mx-auto mb-3 h-10 w-10 opacity-40" />
          还没有案件，点击右上角「新建案件」开始整理你的维权事项。
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((c) => (
            <Card
              key={c.id}
              className="group relative flex flex-col transition hover:-translate-y-0.5 hover:shadow-md"
            >
              {c.color && (
                <div
                  className="absolute inset-x-0 top-0 h-1 rounded-t-2xl"
                  style={{ background: c.color }}
                />
              )}
              <div className="flex items-start justify-between">
                <Link href={`/case-center/${c.id}`} className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 pr-2">
                    <span className="truncate font-semibold">{c.title}</span>
                  </div>
                </Link>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    onClick={() => toggleStar(c)}
                    title="星标"
                    className={c.starred ? "text-amber-400" : "text-gray-300 hover:text-amber-400"}
                  >
                    <Star className="h-4 w-4" fill={c.starred ? "currentColor" : "none"} />
                  </button>
                  <button
                    onClick={() => toggleFavorite(c)}
                    title="收藏"
                    className={c.favorite ? "text-red-400" : "text-gray-300 hover:text-red-400"}
                  >
                    <span className="text-base leading-none">{c.favorite ? "❤️" : "🤍"}</span>
                  </button>
                </div>
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Badge tone="brand">{caseTypeLabels[c.case_type]}</Badge>
                <Badge tone={caseCenterStatusTone[c.status]}>
                  {caseCenterStatusLabels[c.status]}
                </Badge>
                <Badge tone="gray">优先级·{priorityLabels[c.priority]}</Badge>
              </div>

              {c.tags && c.tags.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1">
                  {c.tags.map((t) => (
                    <span
                      key={t}
                      className="rounded-md bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500 dark:bg-white/10 dark:text-gray-400"
                    >
                      #{t}
                    </span>
                  ))}
                </div>
              )}

              <p className="mt-3 line-clamp-2 flex-1 text-sm text-gray-500 dark:text-gray-400">
                {c.description || "（暂无描述）"}
              </p>

              <div className="mt-4 flex items-center justify-between border-t border-gray-100 pt-3 text-xs text-gray-400 dark:border-white/10">
                <span>{c.owner || "我"}</span>
                <div className="flex items-center gap-2 opacity-0 transition group-hover:opacity-100">
                  <button
                    onClick={() => { setEditing(c); setShowForm(true); }}
                    className="flex items-center gap-1 hover:text-brand-600"
                  >
                    <Pencil className="h-3.5 w-3.5" /> 编辑
                  </button>
                  <button
                    onClick={() => remove(c)}
                    className="flex items-center gap-1 text-red-500 hover:text-red-600"
                  >
                    <Trash2 className="h-3.5 w-3.5" /> 删除
                  </button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* 分页 */}
      {total > pageSize && (
        <div className="mt-6 flex items-center justify-center gap-3">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            上一页
          </Button>
          <span className="text-sm text-gray-500">
            第 {page} / {Math.ceil(total / pageSize)} 页
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= Math.ceil(total / pageSize)}
            onClick={() => setPage((p) => p + 1)}
          >
            下一页
          </Button>
        </div>
      )}

      {showForm && (
        <CaseFormModal
          initial={editing}
          busy={formBusy}
          onClose={() => setShowForm(false)}
          onSubmit={async (body) => {
            setFormBusy(true);
            try {
              if (editing) {
                await api.caseCenter.update(editing.id, body);
              } else {
                await api.caseCenter.create(body);
              }
              setShowForm(false);
              await load();
            } finally {
              setFormBusy(false);
            }
          }}
        />
      )}
    </AppShell>
  );
}

// ---------------------------
// 新建 / 编辑 弹窗
// ---------------------------
function CaseFormModal({
  initial,
  busy,
  onClose,
  onSubmit,
}: {
  initial: CaseCenterOut | null;
  busy: boolean;
  onClose: () => void;
  onSubmit: (body: {
    title: string;
    case_type: CaseType;
    description?: string;
    status?: CaseCenterStatus;
    priority?: Priority;
    tags?: string[];
    color?: string;
  }) => void;
}) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [case_type, setCaseType] = useState<CaseType>(initial?.case_type ?? "rent");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [status, setStatus] = useState<CaseCenterStatus | "">(
    initial?.status ?? "pending"
  );
  const [priority, setPriority] = useState<Priority>(initial?.priority ?? "medium");
  const [tags, setTags] = useState((initial?.tags ?? []).join(", "));
  const [color, setColor] = useState(initial?.color ?? COLOR_OPTIONS[0]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-2xl border border-gray-100 bg-white p-6 shadow-xl dark:border-white/10 dark:bg-[#11141b]">
        <h2 className="mb-4 text-lg font-semibold">
          {initial ? "编辑案件" : "新建案件"}
        </h2>
        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium">案件名称</label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="如：房屋租赁押金纠纷" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-sm font-medium">类型</label>
              <select
                value={case_type}
                onChange={(e) => setCaseType(e.target.value as CaseType)}
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm outline-none dark:border-white/10 dark:bg-white/5"
              >
                {(Object.keys(caseTypeLabels) as CaseType[]).map((t) => (
                  <option key={t} value={t}>
                    {caseTypeLabels[t]}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">状态</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as CaseCenterStatus)}
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm outline-none dark:border-white/10 dark:bg-white/5"
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {caseCenterStatusLabels[s]}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">优先级</label>
            <div className="flex gap-2">
              {(["low", "medium", "high"] as Priority[]).map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPriority(p)}
                  className={
                    "rounded-xl px-3 py-1.5 text-sm " +
                    (priority === p
                      ? "bg-brand-500 text-white"
                      : "bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-gray-300")
                  }
                >
                  {priorityLabels[p]}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">描述</label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="简要描述遭遇…"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">标签（逗号分隔）</label>
            <Input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="租赁, 押金" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">颜色</label>
            <div className="flex gap-2">
              {COLOR_OPTIONS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setColor(c)}
                  style={{ background: c }}
                  className={
                    "h-7 w-7 rounded-full transition " +
                    (color === c ? "ring-2 ring-offset-2 ring-gray-400" : "")
                  }
                />
              ))}
            </div>
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            取消
          </Button>
          <Button
            onClick={() =>
              onSubmit({
                title,
                case_type,
                description: description || undefined,
                status: status || undefined,
                priority,
                tags: tags
                  ? tags.split(",").map((t) => t.trim()).filter(Boolean)
                  : undefined,
                color,
              })
            }
            disabled={busy || !title.trim()}
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            {initial ? "保存" : "创建"}
          </Button>
        </div>
      </div>
    </div>
  );
}
