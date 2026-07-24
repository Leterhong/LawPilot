"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  api,
  type ContractOut,
  type ContractTaskOut,
  type ContractTaskCreate,
  type ContractTaskCategory,
  type ContractTaskPriority,
} from "@/lib/api";
import {
  contractReminderCategoryLabels,
  contractReminderCategoryTone,
  contractPriorityLabels,
  contractPriorityTone,
} from "@/lib/constants";
import { AppShell } from "@/components/AppShell";
import { Badge, Button, Card, Input, Spinner } from "@/components/ui";

const DAY_OPTIONS = [7, 30, 90];

function todayISO(): string {
  const d = new Date();
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10);
}

function parseDue(due: string): Date {
  return new Date(due + "T00:00:00");
}

// 距今天数（负数=逾期，正数=还有 N 天）
function daysUntil(due: string): number {
  const ms = parseDue(due).getTime() - parseDue(todayISO()).getTime();
  return Math.round(ms / 86400000);
}

function dueLabel(due: string): string {
  const n = daysUntil(due);
  if (n < 0) return `逾期 ${Math.abs(n)} 天`;
  if (n === 0) return "今天到期";
  if (n === 1) return "明天到期";
  return `还有 ${n} 天`;
}

const CATEGORY_OPTIONS: ContractTaskCategory[] = [
  "expiry",
  "payment",
  "renewal",
  "sign_check",
  "other",
];
const PRIORITY_OPTIONS: ContractTaskPriority[] = [
  "low",
  "normal",
  "high",
  "urgent",
];

export default function RemindersPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  const [days, setDays] = useState(30);
  const [items, setItems] = useState<ContractTaskOut[]>([]);
  const [ready, setReady] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  // 新建提醒弹窗
  const [showModal, setShowModal] = useState(false);
  const [contracts, setContracts] = useState<ContractOut[]>([]);
  const [form, setForm] = useState<ContractTaskCreate & { contract_id: string }>({
    contract_id: "",
    title: "",
    category: "payment",
    due_date: "",
    remind_before_days: 7,
    priority: "normal",
    note: null,
  });
  const [saving, setSaving] = useState(false);
  const [formErr, setFormErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.contracts.upcoming(days);
      setItems(data);
      setErr(null);
    } catch (e: any) {
      setErr(e.message || "加载失败");
    } finally {
      setReady(true);
    }
  }, [days]);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    load();
  }, [user, loading, router, load]);

  const { overdue, upcoming } = useMemo(() => {
    const ov: ContractTaskOut[] = [];
    const up: ContractTaskOut[] = [];
    for (const it of items) {
      if (it.due_date && daysUntil(it.due_date) < 0) ov.push(it);
      else up.push(it);
    }
    return { overdue: ov, upcoming: up };
  }, [items]);

  async function toggleDone(it: ContractTaskOut) {
    setBusyId(it.id);
    try {
      await api.contracts.updateTask(it.contract_id, it.id, { done: !it.done });
      await load();
    } catch (e: any) {
      setErr(e.message || "更新失败");
    } finally {
      setBusyId(null);
    }
  }

  async function remove(it: ContractTaskOut) {
    if (!confirm(`确认删除提醒「${it.title}」？`)) return;
    setBusyId(it.id);
    try {
      await api.contracts.deleteTask(it.contract_id, it.id);
      await load();
    } catch (e: any) {
      setErr(e.message || "删除失败");
    } finally {
      setBusyId(null);
    }
  }

  async function openModal() {
    setFormErr(null);
    setSaving(false);
    try {
      const data = await api.contracts.list({ page: 1, page_size: 100 });
      setContracts(data.items);
      setForm((f) => ({ ...f, contract_id: data.items[0]?.id ?? "" }));
    } catch (e: any) {
      setFormErr(e.message || "加载合同列表失败");
    }
    setShowModal(true);
  }

  async function submitForm() {
    if (!form.contract_id) {
      setFormErr("请选择关联合同");
      return;
    }
    if (!form.title.trim()) {
      setFormErr("请填写提醒标题");
      return;
    }
    if (!form.due_date) {
      setFormErr("请选择到期日");
      return;
    }
    setSaving(true);
    setFormErr(null);
    try {
      await api.contracts.createTask(form.contract_id, {
        type: "reminder",
        title: form.title.trim(),
        category: form.category,
        due_date: form.due_date,
        remind_before_days: form.remind_before_days,
        priority: form.priority,
        note: form.note || null,
      });
      setShowModal(false);
      await load();
    } catch (e: any) {
      setFormErr(e.message || "创建失败");
    } finally {
      setSaving(false);
    }
  }

  if (loading || !ready) {
    return (
      <AppShell>
        <div className="flex items-center justify-center py-20 text-gray-400">
          <Spinner className="mr-2" /> 加载中…
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">提醒中心</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            聚合你所有合同里「未完成」且即将到期 / 已逾期的提醒。
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <Button onClick={openModal} className="gap-1.5">
            ＋ 新建提醒
          </Button>
          <Link href="/contracts">
            <Button variant="outline">← 合同中心</Button>
          </Link>
        </div>
      </div>

      {/* 统计 + 窗口切换 */}
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-3">
          <Card className="px-4 py-3">
            <div className="text-xs text-gray-400">逾期</div>
            <div className="text-xl font-semibold text-red-500">{overdue.length}</div>
          </Card>
          <Card className="px-4 py-3">
            <div className="text-xs text-gray-400">临近到期</div>
            <div className="text-xl font-semibold text-amber-500">
              {upcoming.length}
            </div>
          </Card>
          <Card className="px-4 py-3">
            <div className="text-xs text-gray-400">合计</div>
            <div className="text-xl font-semibold">{items.length}</div>
          </Card>
        </div>
        <div className="flex items-center gap-1 rounded-xl border border-gray-200 p-1 dark:border-white/10">
          {DAY_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={
                "rounded-lg px-3 py-1.5 text-sm transition " +
                (days === d
                  ? "bg-brand-500 text-white"
                  : "text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100")
              }
            >
              {d} 天内
            </button>
          ))}
        </div>
      </div>

      {err && (
        <div className="mb-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/15 dark:text-red-300">
          {err}
        </div>
      )}

      {items.length === 0 ? (
        <Card className="text-center text-sm text-gray-400">
          未来 {days} 天内没有待办提醒。点击右上角「新建提醒」添加一条吧。
        </Card>
      ) : (
        <div className="space-y-6">
          {overdue.length > 0 && (
            <section>
              <h2 className="mb-2 text-sm font-medium text-red-500">
                已逾期（{overdue.length}）
              </h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {overdue.map((it) => (
                  <TaskCard
                    key={it.id}
                    it={it}
                    busy={busyId === it.id}
                    onToggle={toggleDone}
                    onDelete={remove}
                  />
                ))}
              </div>
            </section>
          )}
          {upcoming.length > 0 && (
            <section>
              <h2 className="mb-2 text-sm font-medium text-amber-500">
                临近到期（{upcoming.length}）
              </h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {upcoming.map((it) => (
                  <TaskCard
                    key={it.id}
                    it={it}
                    busy={busyId === it.id}
                    onToggle={toggleDone}
                    onDelete={remove}
                  />
                ))}
              </div>
            </section>
          )}
        </div>
      )}

      {/* 新建提醒弹窗 */}
      {showModal && (
        <div
          className="fixed inset-0 z-30 flex items-center justify-center bg-black/40 p-4"
          onClick={() => !saving && setShowModal(false)}
        >
          <Card
            className="w-full max-w-lg p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-4 text-lg font-semibold">新建提醒</h3>
            <div className="space-y-3">
              <div>
                <label className="mb-1 block text-sm text-gray-500">关联合同</label>
                <select
                  value={form.contract_id}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, contract_id: e.target.value }))
                  }
                  className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
                >
                  {contracts.length === 0 && <option value="">（无合同）</option>}
                  {contracts.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.title || "未命名合同"}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm text-gray-500">提醒标题 *</label>
                <Input
                  value={form.title}
                  onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                  placeholder="例如：支付第二季度租金"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-sm text-gray-500">分类</label>
                  <select
                    value={form.category ?? "payment"}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        category: e.target.value as ContractTaskCategory,
                      }))
                    }
                    className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
                  >
                    {CATEGORY_OPTIONS.map((c) => (
                      <option key={c} value={c}>
                        {contractReminderCategoryLabels[c] ?? c}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm text-gray-500">优先级</label>
                  <select
                    value={form.priority ?? "normal"}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        priority: e.target.value as ContractTaskPriority,
                      }))
                    }
                    className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
                  >
                    {PRIORITY_OPTIONS.map((p) => (
                      <option key={p} value={p}>
                        {contractPriorityLabels[p] ?? p}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-sm text-gray-500">到期日 *</label>
                  <input
                    type="date"
                    value={form.due_date ?? ""}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, due_date: e.target.value }))
                    }
                    className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm text-gray-500">
                    提前提醒（天）
                  </label>
                  <Input
                    type="number"
                    min={0}
                    value={form.remind_before_days ?? 7}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        remind_before_days: Number(e.target.value),
                      }))
                    }
                  />
                </div>
              </div>
              <div>
                <label className="mb-1 block text-sm text-gray-500">备注</label>
                <Input
                  value={form.note ?? ""}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, note: e.target.value || null }))
                  }
                  placeholder="可选"
                />
              </div>
            </div>

            {formErr && (
              <div className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/15 dark:text-red-300">
                {formErr}
              </div>
            )}

            <div className="mt-5 flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setShowModal(false)}
                disabled={saving}
              >
                取消
              </Button>
              <Button onClick={submitForm} disabled={saving}>
                {saving ? "创建中…" : "创建"}
              </Button>
            </div>
          </Card>
        </div>
      )}
    </AppShell>
  );
}

function TaskCard({
  it,
  busy,
  onToggle,
  onDelete,
}: {
  it: ContractTaskOut;
  busy: boolean;
  onToggle: (it: ContractTaskOut) => void;
  onDelete: (it: ContractTaskOut) => void;
}) {
  const overdue = it.due_date ? daysUntil(it.due_date) < 0 : false;
  return (
    <Card className="flex flex-col">
      <div className="flex items-start justify-between gap-2">
        <label className="flex cursor-pointer items-start gap-2">
          <input
            type="checkbox"
            checked={it.done}
            disabled={busy}
            onChange={() => onToggle(it)}
            className="mt-1 h-4 w-4 accent-brand-500"
          />
          <span
            className={
              "font-medium " + (it.done ? "text-gray-400 line-through" : "")
            }
          >
            {it.title}
          </span>
        </label>
        <button
          onClick={() => onDelete(it)}
          disabled={busy}
          className="shrink-0 text-xs text-gray-400 hover:text-red-500"
          title="删除"
        >
          删除
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {it.category && (
          <Badge tone={contractReminderCategoryTone[it.category] ?? "gray"}>
            {contractReminderCategoryLabels[it.category] ?? it.category}
          </Badge>
        )}
        <Badge tone={contractPriorityTone[it.priority] ?? "gray"}>
          {contractPriorityLabels[it.priority] ?? it.priority}
        </Badge>
      </div>

      {it.due_date && (
        <div className="mt-3 flex items-center justify-between text-sm">
          <span className={overdue ? "font-medium text-red-500" : "text-gray-500"}>
            {dueLabel(it.due_date)}
          </span>
          <span className="text-xs text-gray-400">{it.due_date}</span>
        </div>
      )}

      {it.contract_title && (
        <Link
          href={`/contracts/${it.contract_id}`}
          className="mt-3 text-xs text-brand-600 hover:underline dark:text-brand-300"
        >
          关联合同：{it.contract_title} →
        </Link>
      )}
    </Card>
  );
}
