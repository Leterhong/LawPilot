// 案件中心 - 详情页（Case Center）
// 8 个 Tab：概览 / 案件分析 / 证据 / 时间线 / 任务 / 文书 / 法律依据 / 备注
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Star,
  Plus,
  Trash2,
  Check,
  Loader2,
  Scale,
  Sparkles,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import api, {
  type CaseCenterDetailOut,
  type CaseAnalysisOut,
  type CaseEvidenceOut,
  type CaseTaskOut,
  type CaseTimelineOut,
  type CaseDocumentOut,
  type CaseNoteOut,
  type CaseCenterStatus,
  type CaseType,
  type Priority,
  type TaskStatus,
  type EvidenceCategory,
  type DocType,
} from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { Badge, Button, Card, Input, Spinner, Textarea } from "@/components/ui";
import {
  caseCenterStatusLabels,
  caseCenterStatusTone,
  caseTypeLabels,
  priorityLabels,
  evidenceCategoryLabels,
  docTypeLabels,
  taskStatusLabels,
} from "@/lib/constants";

type TabKey =
  | "overview"
  | "analysis"
  | "evidence"
  | "timeline"
  | "tasks"
  | "documents"
  | "legal"
  | "notes";

const TABS: { key: TabKey; label: string }[] = [
  { key: "overview", label: "概览" },
  { key: "analysis", label: "案件分析" },
  { key: "evidence", label: "证据" },
  { key: "timeline", label: "时间线" },
  { key: "tasks", label: "任务" },
  { key: "documents", label: "文书" },
  { key: "legal", label: "法律依据" },
  { key: "notes", label: "备注" },
];

function fmt(d?: string) {
  if (!d) return "—";
  const dt = new Date(d);
  return dt.toLocaleString("zh-CN", { hour12: false });
}

export default function CaseCenterDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const caseId = params.id;

  const [data, setData] = useState<CaseCenterDetailOut | null>(null);
  const [busy, setBusy] = useState(true);
  const [tab, setTab] = useState<TabKey>("overview");
  const [err, setErr] = useState("");

  async function load() {
    setBusy(true);
    setErr("");
    try {
      const d = await api.caseCenter.get(caseId);
      setData(d);
    } catch (e: any) {
      setErr(e?.message || "加载失败");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (loading) return;
    if (!user) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, loading, caseId]);

  if (!loading && !user) {
    return (
      <AppShell>
        <div className="py-20 text-center text-gray-500 dark:text-gray-400">
          请先<Link href="/login" className="mx-1 text-brand-600 hover:underline">登录</Link>。
        </div>
      </AppShell>
    );
  }

  if (busy) {
    return (
      <AppShell>
        <div className="flex justify-center py-20">
          <Spinner />
        </div>
      </AppShell>
    );
  }

  if (err || !data) {
    return (
      <AppShell>
        <div className="py-20 text-center text-gray-500">
          {err || "案件不存在"}
          <div className="mt-4">
            <Link href="/case-center">
              <Button variant="outline">返回列表</Button>
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  const c = data.case;
  const latestAnalysis = data.analyses[0] ?? null;

  return (
    <AppShell>
      <div className="mb-4">
        <Link
          href="/case-center"
          className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-brand-600"
        >
          <ArrowLeft className="h-4 w-4" /> 返回我的案件
        </Link>
      </div>

      {/* 头部 */}
      <div className="mb-6 rounded-2xl border border-gray-100 bg-white p-5 shadow-soft dark:border-white/10 dark:bg-white/5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold">{c.title}</h1>
              <button
                onClick={async () => {
                  const u = await api.caseCenter.update(c.id, { starred: !c.starred });
                  setData({ ...data, case: u });
                }}
                className={c.starred ? "text-amber-400" : "text-gray-300 hover:text-amber-400"}
              >
                <Star className="h-5 w-5" fill={c.starred ? "currentColor" : "none"} />
              </button>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge tone="brand">{caseTypeLabels[c.case_type]}</Badge>
              <Badge tone={caseCenterStatusTone[c.status]}>
                {caseCenterStatusLabels[c.status]}
              </Badge>
              <Badge tone="gray">优先级·{priorityLabels[c.priority]}</Badge>
              {c.owner && <span className="text-sm text-gray-500">负责人：{c.owner}</span>}
            </div>
            {c.tags && c.tags.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
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
          </div>
          <Link href="/case-center">
            <Button variant="outline" size="sm">
              编辑
            </Button>
          </Link>
        </div>
      </div>

      {/* Tab 切换 */}
      <div className="mb-5 flex flex-wrap gap-1 border-b border-gray-100 dark:border-white/10">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={
              "border-b-2 px-3 py-2 text-sm transition " +
              (tab === t.key
                ? "border-brand-500 font-medium text-brand-600"
                : "border-transparent text-gray-500 hover:text-gray-900 dark:hover:text-gray-100")
            }
          >
            {t.label}
            {t.key === "evidence" && data.evidences.length > 0 && (
              <span className="ml-1 text-xs text-gray-400">{data.evidences.length}</span>
            )}
            {t.key === "tasks" && data.tasks.length > 0 && (
              <span className="ml-1 text-xs text-gray-400">{data.tasks.length}</span>
            )}
            {t.key === "notes" && data.notes.length > 0 && (
              <span className="ml-1 text-xs text-gray-400">{data.notes.length}</span>
            )}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <OverviewTab data={data} latest={latestAnalysis} onAdopt={async (st) => {
          const u = await api.caseCenter.update(c.id, { status: st });
          setData({ ...data, case: u });
        }} />
      )}
      {tab === "analysis" && (
        <AnalysisTab caseId={c.id} data={data} onChange={load} />
      )}
      {tab === "evidence" && (
        <EvidenceTab caseId={c.id} data={data} onChange={load} />
      )}
      {tab === "timeline" && (
        <TimelineTab caseId={c.id} data={data} onChange={load} />
      )}
      {tab === "tasks" && (
        <TasksTab caseId={c.id} data={data} onChange={load} />
      )}
      {tab === "documents" && (
        <DocumentsTab caseId={c.id} data={data} onChange={load} />
      )}
      {tab === "legal" && <LegalTab case={c} />}
      {tab === "notes" && (
        <NotesTab caseId={c.id} data={data} onChange={load} />
      )}
    </AppShell>
  );
}

// ---------------------------
// 概览
// ---------------------------
function OverviewTab({
  data,
  latest,
  onAdopt,
}: {
  data: CaseCenterDetailOut;
  latest: CaseAnalysisOut | null;
  onAdopt: (st: CaseCenterStatus) => void;
}) {
  const c = data.case;
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        <Card>
          <h3 className="mb-2 font-semibold">案情摘要</h3>
          <p className="whitespace-pre-wrap text-sm text-gray-600 dark:text-gray-300">
            {latest?.summary || c.description || "暂无摘要。前往「案件分析」运行一次分析。"}
          </p>
          {latest?.risk && (
            <>
              <h3 className="mb-2 mt-4 font-semibold">风险分析</h3>
              <p className="whitespace-pre-wrap text-sm text-gray-600 dark:text-gray-300">
                {latest.risk}
              </p>
            </>
          )}
        </Card>

        {latest?.next_steps && latest.next_steps.length > 0 && (
          <Card>
            <h3 className="mb-2 font-semibold">下一步行动</h3>
            <ul className="space-y-1.5">
              {latest.next_steps.map((s, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-green-500" />
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>

      <div className="space-y-4">
        <Card>
          <h3 className="mb-3 font-semibold">关键信息</h3>
          <dl className="space-y-2 text-sm">
            <Row k="状态" v={caseCenterStatusLabels[c.status]} />
            <Row k="类型" v={caseTypeLabels[c.case_type]} />
            <Row k="优先级" v={priorityLabels[c.priority]} />
            <Row k="负责人" v={c.owner || "我"} />
            <Row k="创建" v={fmt(c.created_at)} />
            <Row k="更新" v={fmt(c.updated_at)} />
            <Row k="证据" v={`${data.evidences.length} 项`} />
            <Row k="任务" v={`${data.tasks.length} 项`} />
            <Row k="文书" v={`${data.documents.length} 份`} />
          </dl>
        </Card>

        {latest?.suggested_status && latest.suggested_status !== c.status && (
          <Card>
            <p className="text-sm text-gray-500">
              AI 建议将状态调整为
              <span className="mx-1 font-medium text-brand-600">
                {caseCenterStatusLabels[latest.suggested_status]}
              </span>
            </p>
            <Button
              size="sm"
              className="mt-3"
              onClick={() => onAdopt(latest.suggested_status!)}
            >
              一键采纳
            </Button>
          </Card>
        )}
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-gray-400">{k}</dt>
      <dd className="text-right font-medium">{v}</dd>
    </div>
  );
}

// ---------------------------
// 案件分析
// ---------------------------
function AnalysisTab({
  caseId,
  data,
  onChange,
}: {
  caseId: string;
  data: CaseCenterDetailOut;
  onChange: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState("");
  const [risk, setRisk] = useState("");
  const [riskLevel, setRiskLevel] = useState("");
  const [suggested, setSuggested] = useState<CaseCenterStatus | "">("");
  const [steps, setSteps] = useState("");

  // 查找类似案例（Step 4：调用 /api/legal-cases/similar）
  const [similar, setSimilar] = useState<{
    items: any[];
    query: string;
    note?: string;
  } | null>(null);
  const [similarBusy, setSimilarBusy] = useState(false);
  const [similarErr, setSimilarErr] = useState("");

  async function findSimilar() {
    setSimilarBusy(true);
    setSimilarErr("");
    try {
      const res = await api.legalCase.similar({ case_id: caseId, limit: 10 });
      const note =
        res.parsed && res.parsed.error
          ? "无法生成案例检索（缺少案件内容）"
          : res.items.length === 0
            ? "未找到相似案例，可尝试补充案情描述。"
            : undefined;
      setSimilar({ items: res.items, query: res.query, note });
    } catch (e: any) {
      setSimilarErr(e?.message || "查找失败");
    } finally {
      setSimilarBusy(false);
    }
  }

  async function submit() {
    setBusy(true);
    try {
      await api.caseCenter.addAnalysis(caseId, {
        summary: summary || undefined,
        risk: risk || undefined,
        risk_level: riskLevel || undefined,
        suggested_status: suggested || undefined,
        next_steps: steps
          ? steps.split("\n").map((s) => s.trim()).filter(Boolean)
          : undefined,
      });
      setOpen(false);
      setSummary(""); setRisk(""); setRiskLevel(""); setSuggested(""); setSteps("");
      onChange();
    } finally {
      setBusy(false);
    }
  }

  if (open) {
    return (
      <Card>
        <h3 className="mb-3 font-semibold">新增分析</h3>
        <div className="space-y-3">
          <Textarea value={summary} onChange={(e) => setSummary(e.target.value)} rows={3} placeholder="案情摘要" />
          <Textarea value={risk} onChange={(e) => setRisk(e.target.value)} rows={2} placeholder="风险分析" />
          <div className="grid grid-cols-2 gap-3">
            <Input value={riskLevel} onChange={(e) => setRiskLevel(e.target.value)} placeholder="风险等级 low/medium/high" />
            <select
              value={suggested}
              onChange={(e) => setSuggested(e.target.value as CaseCenterStatus | "")}
              className="rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
            >
              <option value="">建议状态（可选）</option>
              {(Object.keys(caseCenterStatusLabels) as CaseCenterStatus[]).map((s) => (
                <option key={s} value={s}>{caseCenterStatusLabels[s]}</option>
              ))}
            </select>
          </div>
          <Textarea value={steps} onChange={(e) => setSteps(e.target.value)} rows={3} placeholder="下一步（每行一条）" />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setOpen(false)} disabled={busy}>取消</Button>
            <Button onClick={submit} disabled={busy}>
              {busy && <Loader2 className="h-4 w-4 animate-spin" />} 保存分析
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap justify-end gap-2">
        <Button variant="outline" onClick={findSimilar} disabled={similarBusy}>
          {similarBusy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4" />
          )}
          查找类似案例
        </Button>
        <Button onClick={() => setOpen(true)}>
          <Plus className="h-4 w-4" /> 新增分析
        </Button>
      </div>

      {similarErr && (
        <Card className="mb-4 border-red-200 py-4 text-center text-sm text-red-600 dark:border-red-500/30">
          {similarErr}
        </Card>
      )}

      {similar && (
        <div className="mb-6">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-200">
            <Sparkles className="h-4 w-4 text-brand-500" />
            相似案例
            <span className="text-xs font-normal text-gray-400">
              基于本案件自动检索（{similar.items.length} 条）
            </span>
          </div>
          {similar.note && (
            <p className="mb-2 text-xs text-gray-400">{similar.note}</p>
          )}
          {similar.items.length === 0 ? (
            <Card className="py-8 text-center text-sm text-gray-500">
              暂无相似案例。
            </Card>
          ) : (
            <div className="space-y-2">
              {similar.items.map((it: any) => (
                <Link key={it.id} href={`/case-search/${it.id}`}>
                  <Card className="transition hover:-translate-y-0.5 hover:shadow-md">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{it.title}</span>
                      {it.court_level && (
                        <Badge tone="gray">{it.court_level}</Badge>
                      )}
                      {it.winner && <Badge tone="green">胜诉方：{it.winner}</Badge>}
                      {it.compensation && (
                        <Badge tone="amber">赔偿：{it.compensation}</Badge>
                      )}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-400">
                      {it.court && <span>{it.court}</span>}
                      {it.trial_date && <span>{it.trial_date}</span>}
                    </div>
                    {it.snippet && (
                      <p
                        className="mt-2 line-clamp-2 text-sm text-gray-500 dark:text-gray-400"
                        dangerouslySetInnerHTML={{ __html: it.snippet }}
                      />
                    )}
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
      {data.analyses.length === 0 ? (
        <Card className="py-12 text-center text-gray-500">还没有分析记录。</Card>
      ) : (
        <div className="space-y-3">
          {data.analyses.map((a) => (
            <Card key={a.id}>
              <div className="mb-2 flex items-center justify-between">
                <Badge tone="brand">{a.analysis_type}</Badge>
                <span className="text-xs text-gray-400">{fmt(a.created_at)}</span>
              </div>
              {a.summary && <p className="whitespace-pre-wrap text-sm">{a.summary}</p>}
              {a.risk && (
                <p className="mt-2 whitespace-pre-wrap text-sm text-gray-600 dark:text-gray-300">
                  <span className="font-medium">风险：</span>
                  {a.risk}
                </p>
              )}
              {a.next_steps && a.next_steps.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {a.next_steps.map((s, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-green-500" />
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------
// 证据
// ---------------------------
function EvidenceTab({
  caseId,
  data,
  onChange,
}: {
  caseId: string;
  data: CaseCenterDetailOut;
  onChange: () => void;
}) {
  const [cat, setCat] = useState<EvidenceCategory>("contract");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);

  async function add() {
    if (!title.trim()) return;
    setBusy(true);
    try {
      await api.caseCenter.addEvidence(caseId, { category: cat, title: title.trim(), is_uploaded: true });
      setTitle("");
      onChange();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <Card className="mb-4">
        <div className="flex flex-wrap items-end gap-2">
          <select
            value={cat}
            onChange={(e) => setCat(e.target.value as EvidenceCategory)}
            className="rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
          >
            {(Object.keys(evidenceCategoryLabels) as EvidenceCategory[]).map((k) => (
              <option key={k} value={k}>{evidenceCategoryLabels[k]}</option>
            ))}
          </select>
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="证据名称"
            className="flex-1 min-w-[200px]"
          />
          <Button onClick={add} disabled={busy}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} 添加
          </Button>
        </div>
      </Card>
      {data.evidences.length === 0 ? (
        <Card className="py-12 text-center text-gray-500">还没有证据。</Card>
      ) : (
        <div className="space-y-2">
          {data.evidences.map((e: CaseEvidenceOut) => (
            <Card key={e.id} className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium">{e.title}</span>
                  <Badge tone="gray">{evidenceCategoryLabels[e.category]}</Badge>
                  {e.is_uploaded ? (
                    <Badge tone="green">已提供</Badge>
                  ) : (
                    <Badge tone="amber">待补充</Badge>
                  )}
                </div>
                {e.ai_note && (
                  <p className="mt-1 text-sm text-gray-500">{e.ai_note}</p>
                )}
              </div>
              <button
                onClick={async () => { await api.caseCenter.removeEvidence(caseId, e.id); onChange(); }}
                className="text-red-500 hover:text-red-600"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------
// 时间线
// ---------------------------
function TimelineTab({
  caseId,
  data,
  onChange,
}: {
  caseId: string;
  data: CaseCenterDetailOut;
  onChange: () => void;
}) {
  const [eventType, setEventType] = useState("status_changed");
  const [title, setTitle] = useState("");
  const [detail, setDetail] = useState("");
  const [busy, setBusy] = useState(false);

  async function add() {
    if (!title.trim()) return;
    setBusy(true);
    try {
      await api.caseCenter.addTimeline(caseId, {
        event_type: eventType,
        title: title.trim(),
        detail: detail || undefined,
      });
      setTitle(""); setDetail("");
      onChange();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <Card className="mb-4">
        <div className="flex flex-wrap items-end gap-2">
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="事件标题"
            className="flex-1 min-w-[200px]"
          />
          <Input
            value={detail}
            onChange={(e) => setDetail(e.target.value)}
            placeholder="详情（可选）"
            className="flex-1 min-w-[200px]"
          />
          <Input
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
            placeholder="event_type"
            className="w-40"
          />
          <Button onClick={add} disabled={busy}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} 添加
          </Button>
        </div>
      </Card>
      {data.timelines.length === 0 ? (
        <Card className="py-12 text-center text-gray-500">还没有时间线事件。</Card>
      ) : (
        <ol className="relative space-y-4 border-l border-gray-200 pl-5 dark:border-white/10">
          {data.timelines.map((t: CaseTimelineOut) => (
            <li key={t.id} className="relative">
              <span className="absolute -left-[1.45rem] top-1 h-3 w-3 rounded-full bg-brand-500" />
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-medium">{t.title}</div>
                  {t.detail && <p className="text-sm text-gray-500">{t.detail}</p>}
                  <div className="mt-0.5 text-xs text-gray-400">
                    {t.event_type} · {fmt(t.occurred_at)}
                  </div>
                </div>
                <button
                  onClick={async () => { await api.caseCenter.removeTimeline(caseId, t.id); onChange(); }}
                  className="text-red-500 hover:text-red-600"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

// ---------------------------
// 任务
// ---------------------------
function TasksTab({
  caseId,
  data,
  onChange,
}: {
  caseId: string;
  data: CaseCenterDetailOut;
  onChange: () => void;
}) {
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);

  async function add() {
    if (!title.trim()) return;
    setBusy(true);
    try {
      await api.caseCenter.addTask(caseId, { title: title.trim() });
      setTitle("");
      onChange();
    } finally {
      setBusy(false);
    }
  }

  const statusOrder: TaskStatus[] = ["todo", "in_progress", "done"];

  return (
    <div>
      <Card className="mb-4">
        <div className="flex flex-wrap items-end gap-2">
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="新任务标题"
            className="flex-1 min-w-[200px]"
            onKeyDown={(e) => { if (e.key === "Enter") add(); }}
          />
          <Button onClick={add} disabled={busy}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} 添加
          </Button>
        </div>
      </Card>
      {data.tasks.length === 0 ? (
        <Card className="py-12 text-center text-gray-500">还没有任务。</Card>
      ) : (
        <div className="space-y-2">
          {data.tasks.map((t: CaseTaskOut) => (
            <Card key={t.id} className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <select
                  value={t.status}
                  onChange={async (e) => {
                    await api.caseCenter.updateTask(caseId, t.id, {
                      status: e.target.value as TaskStatus,
                    });
                    onChange();
                  }}
                  className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs dark:border-white/10 dark:bg-white/5"
                >
                  {statusOrder.map((s) => (
                    <option key={s} value={s}>{taskStatusLabels[s]}</option>
                  ))}
                </select>
                <span className={t.status === "done" ? "line-through text-gray-400" : ""}>
                  {t.title}
                </span>
                <Badge tone="gray">优先级·{priorityLabels[t.priority]}</Badge>
              </div>
              <button
                onClick={async () => { await api.caseCenter.removeTask(caseId, t.id); onChange(); }}
                className="text-red-500 hover:text-red-600"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------
// 文书
// ---------------------------
function DocumentsTab({
  caseId,
  data,
  onChange,
}: {
  caseId: string;
  data: CaseCenterDetailOut;
  onChange: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [docType, setDocType] = useState<DocType>("complaint");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);

  async function add() {
    if (!title.trim()) return;
    setBusy(true);
    try {
      await api.caseCenter.addDocument(caseId, {
        doc_type: docType,
        title: title.trim(),
        content: content || "",
      });
      setOpen(false); setTitle(""); setContent("");
      onChange();
    } finally {
      setBusy(false);
    }
  }

  if (open) {
    return (
      <Card>
        <h3 className="mb-3 font-semibold">新增文书</h3>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value as DocType)}
              className="rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
            >
              {(Object.keys(docTypeLabels) as DocType[]).map((k) => (
                <option key={k} value={k}>{docTypeLabels[k]}</option>
              ))}
            </select>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="文书标题" />
          </div>
          <Textarea value={content} onChange={(e) => setContent(e.target.value)} rows={6} placeholder="正文（Markdown）" />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setOpen(false)} disabled={busy}>取消</Button>
            <Button onClick={add} disabled={busy}>
              {busy && <Loader2 className="h-4 w-4 animate-spin" />} 保存
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <Button onClick={() => setOpen(true)}>
          <Plus className="h-4 w-4" /> 新增文书
        </Button>
      </div>
      {data.documents.length === 0 ? (
        <Card className="py-12 text-center text-gray-500">还没有文书。</Card>
      ) : (
        <div className="space-y-3">
          {data.documents.map((d: CaseDocumentOut) => (
            <Card key={d.id}>
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{d.title}</span>
                  <Badge tone="brand">{docTypeLabels[d.doc_type]}</Badge>
                  <Badge tone="gray">{d.status}</Badge>
                </div>
                <button
                  onClick={async () => { await api.caseCenter.removeDocument(caseId, d.id); onChange(); }}
                  className="text-red-500 hover:text-red-600"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              <pre className="max-h-60 overflow-auto whitespace-pre-wrap rounded-lg bg-gray-50 p-3 text-sm text-gray-700 dark:bg-white/5 dark:text-gray-300">
                {d.content}
              </pre>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------
// 法律依据（关联 Law Search）
// ---------------------------
function LegalTab({ case: c }: { case: CaseCenterDetailOut["case"] }) {
  const [results, setResults] = useState<any[] | null>(null);
  const [busy, setBusy] = useState(false);

  async function search() {
    setBusy(true);
    try {
      const q = `${caseTypeLabels[c.case_type]} ${c.title}`;
      const r = await api.lawSearch(q, { limit: 10, offset: 0 });
      setResults(r.items);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <Card className="mb-4">
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">
            基于案件类型与名称，检索相关法律条文作为维权依据。
          </p>
          <Button onClick={search} disabled={busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Scale className="h-4 w-4" />}
            检索相关法律
          </Button>
        </div>
      </Card>
      {results === null ? (
        <Card className="py-12 text-center text-gray-500">点击上方按钮检索法律依据。</Card>
      ) : results.length === 0 ? (
        <Card className="py-12 text-center text-gray-500">未找到相关法律条文。</Card>
      ) : (
        <div className="space-y-2">
          {results.map((it) => (
            <Link key={it.id} href={`/laws/${it.id}`}>
              <Card className="transition hover:-translate-y-0.5 hover:shadow-md">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{it.law_name}</span>
                  {it.article && <Badge tone="gray">{it.article}</Badge>}
                </div>
                {it.snippet && (
                  <p className="mt-1 line-clamp-2 text-sm text-gray-500" dangerouslySetInnerHTML={{ __html: it.snippet }} />
                )}
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------
// 备注
// ---------------------------
function NotesTab({
  caseId,
  data,
  onChange,
}: {
  caseId: string;
  data: CaseCenterDetailOut;
  onChange: () => void;
}) {
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);

  async function add() {
    if (!content.trim()) return;
    setBusy(true);
    try {
      await api.caseCenter.addNote(caseId, { content: content.trim() });
      setContent("");
      onChange();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <Card className="mb-4">
        <Textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={3}
          placeholder="记录备注…"
        />
        <div className="mt-2 flex justify-end">
          <Button onClick={add} disabled={busy}>
            {busy && <Loader2 className="h-4 w-4 animate-spin" />} 添加备注
          </Button>
        </div>
      </Card>
      {data.notes.length === 0 ? (
        <Card className="py-12 text-center text-gray-500">还没有备注。</Card>
      ) : (
        <div className="space-y-2">
          {data.notes.map((n: CaseNoteOut) => (
            <Card key={n.id}>
              <div className="flex items-start justify-between">
                <div>
                  <p className="whitespace-pre-wrap text-sm">{n.content}</p>
                  <div className="mt-1 text-xs text-gray-400">{fmt(n.created_at)}</div>
                </div>
                <button
                  onClick={async () => { await api.caseCenter.removeNote(caseId, n.id); onChange(); }}
                  className="text-red-500 hover:text-red-600"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
