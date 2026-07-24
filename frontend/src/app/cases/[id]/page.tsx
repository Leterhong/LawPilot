// 案件详情页：对话 / 报告 / 证据 / 文书 / 路线图 / 任务 / 时间线。
"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import api, {
  type CaseOut,
  type DocumentOut,
  type EvidenceOut,
  type EvidenceCategory,
  type HistoryOut,
  type MessageOut,
  type RoadmapOut,
  type RoadmapStepOut,
  type TaskOut,
} from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { Badge, Button, Card, Input, Spinner, Textarea } from "@/components/ui";
import {
  caseStatusLabels,
  caseTypeLabels,
  docTypeLabels,
  evidenceCategoryLabels,
  eventTypeLabels,
  stepStatusLabels,
  taskStatusLabels,
} from "@/lib/constants";

const TABS = ["对话", "报告", "证据", "文书", "路线图", "任务", "时间线"] as const;
type Tab = (typeof TABS)[number];

export default function CaseDetailPage({ params }: { params: { id: string } }) {
  const { user, loading } = useAuth();
  const caseId = params.id;

  const [tab, setTab] = useState<Tab>("对话");
  const [caseObj, setCaseObj] = useState<CaseOut | null>(null);
  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [evidence, setEvidence] = useState<EvidenceOut[]>([]);
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [roadmap, setRoadmap] = useState<RoadmapOut | null>(null);
  const [tasks, setTasks] = useState<TaskOut[]>([]);
  const [history, setHistory] = useState<HistoryOut[]>([]);
  const [busy, setBusy] = useState(true);

  const loadAll = useCallback(async () => {
    try {
      const [c, m, ev, docs, t, h] = await Promise.all([
        api.getCase(caseId),
        api.listMessages(caseId),
        api.listEvidence(caseId),
        api.listDocuments(caseId),
        api.listTasks(caseId),
        api.listHistory(caseId),
      ]);
      setCaseObj(c);
      setMessages(m);
      setEvidence(ev);
      setDocuments(docs);
      setTasks(t);
      setHistory(h);
      try {
        setRoadmap(await api.getRoadmap(caseId));
      } catch {
        setRoadmap(null);
      }
    } catch {
      /* 忽略：由下方未登录分支处理 */
    } finally {
      setBusy(false);
    }
  }, [caseId]);

  useEffect(() => {
    if (loading) return;
    if (!user) return;
    loadAll();
  }, [user, loading, loadAll]);

  if (!loading && !user) {
    return (
      <AppShell>
        <div className="py-20 text-center text-gray-500 dark:text-gray-400">
          请先
          <Link href="/login" className="mx-1 text-brand-600 hover:underline">
            登录
          </Link>
          。
        </div>
      </AppShell>
    );
  }

  if (busy || !caseObj) {
    return (
      <AppShell>
        <div className="flex justify-center py-20">
          <Spinner />
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      {/* 头部 */}
      <div className="mb-6">
        <Link href="/cases" className="text-sm text-gray-400 hover:text-gray-600">
          ← 返回案件列表
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold">{caseObj.title}</h1>
          <Badge tone="brand">{caseTypeLabels[caseObj.case_type]}</Badge>
          <Badge tone="gray">{caseStatusLabels[caseObj.status]}</Badge>
          {!roadmap && (
            <Button
              size="sm"
              variant="outline"
              onClick={async () => {
                setRoadmap(await api.generateRoadmap(caseId));
              }}
            >
              生成办理路线图
            </Button>
          )}
        </div>
      </div>

      {/* 标签页 */}
      <div className="mb-6 flex flex-wrap gap-1 border-b border-gray-100 dark:border-white/10">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm transition ${
              tab === t
                ? "border-b-2 border-brand-500 font-medium text-brand-600"
                : "text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "对话" && (
        <ChatPane
          caseId={caseId}
          onReportReady={() => setTab("报告")}
          onCaseUpdate={(c) => setCaseObj(c)}
        />
      )}
      {tab === "报告" && <ReportPane caseObj={caseObj} />}
      {tab === "证据" && (
        <EvidencePane caseId={caseId} items={evidence} onChange={setEvidence} />
      )}
      {tab === "文书" && (
        <DocumentPane caseId={caseId} items={documents} onChange={setDocuments} />
      )}
      {tab === "路线图" && (
        <RoadmapPane
          caseId={caseId}
          roadmap={roadmap}
          onGenerate={setRoadmap}
          onChange={setRoadmap}
        />
      )}
      {tab === "任务" && <TaskPane caseId={caseId} items={tasks} onChange={setTasks} />}
      {tab === "时间线" && <HistoryPane items={history} />}
    </AppShell>
  );
}

// ---------------------------
// 对话（接入 Agent 流程引擎）
// ---------------------------
function ChatPane({
  caseId,
  onReportReady,
  onCaseUpdate,
}: {
  caseId: string;
  onReportReady?: () => void;
  onCaseUpdate?: (c: CaseOut) => void;
}) {
  const [messages, setMessages] = useState<MessageOut[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const st = await api.getAgentState(caseId);
        setMessages(st.messages);
      } catch {
        /* ignore */
      } finally {
        setLoading(false);
      }
    })();
  }, [caseId]);

  const send = async () => {
    if (!text.trim() || sending) return;
    const sent = text.trim();
    const optimistic: MessageOut = {
      id: `tmp-${Date.now()}`,
      case_id: caseId,
      role: "user",
      message_type: "text",
      content: sent,
      sequence: messages.length + 1,
      metadata_json: null,
      created_at: new Date().toISOString(),
    };
    setMessages((p) => [...p, optimistic]);
    setText("");
    setSending(true);
    try {
      const r = await api.sendChat(caseId, sent);
      setMessages((p) => [...p, r.assistant_message]);
      onCaseUpdate?.(r.case);
      if (r.report_generated) onReportReady?.();
    } catch {
      /* ignore */
    } finally {
      setSending(false);
    }
  };

  const lastMsg = messages[messages.length - 1];
  const quickOptions: string[] =
    lastMsg && lastMsg.role === "assistant"
      ? ((lastMsg.metadata_json?.options as string[] | undefined) ?? [])
      : [];
  const reportReady = lastMsg?.metadata_json?.report_ready === true;

  return (
    <div className="space-y-4">
      <Card className="min-h-[200px] space-y-3">
        {loading ? (
          <div className="flex justify-center py-10">
            <Spinner />
          </div>
        ) : messages.length === 0 ? (
          <p className="py-10 text-center text-sm text-gray-400">
            还没有对话。描述你的遭遇，AI 将持续追问、收集证据，证据齐全后生成报告。
          </p>
        ) : (
          messages.map((m) => (
            <div key={m.id} className={m.role === "user" ? "text-right" : "text-left"}>
              <span
                className={`inline-block max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm ${
                  m.role === "user"
                    ? "bg-brand-500 text-white"
                    : "bg-gray-100 text-gray-900 dark:bg-white/10 dark:text-gray-100"
                }`}
              >
                {m.content}
              </span>
            </div>
          ))
        )}
      </Card>

      {quickOptions.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {quickOptions.map((o) => (
            <Button key={o} size="sm" variant="outline" onClick={() => setText(o)}>
              {o}
            </Button>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <Textarea
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="补充你的遭遇或回答 AI 的追问…"
          className="flex-1"
        />
        <Button onClick={send} disabled={sending || !text.trim()}>
          {sending ? <Spinner /> : "发送"}
        </Button>
      </div>
      <p className="text-xs text-gray-400">
        {reportReady
          ? "✅ 报告已生成，可在「报告」标签页查看完整分析。"
          : "AI 会逐步追问以收集证据，证据齐全后将自动生成案件报告。"}
      </p>
    </div>
  );
}

// ---------------------------
// 报告（Agent 生成的 11 章节）
// ---------------------------
function ReportPane({ caseObj }: { caseObj: CaseOut }) {
  const r = caseObj.report;
  if (!r) {
    return (
      <Card className="py-12 text-center text-gray-500 dark:text-gray-400">
        报告尚未生成。请在「对话」中与 AI 充分沟通、提供关键信息后自动生成。
      </Card>
    );
  }

  const Section = ({ title, children }: { title: string; children: ReactNode }) => (
    <Card>
      <div className="mb-2 text-sm font-medium text-gray-500 dark:text-gray-400">{title}</div>
      <div className="text-sm">{children}</div>
    </Card>
  );

  return (
    <div className="space-y-4">
      <Section title="案件类型">{r.case_type}</Section>
      <Section title="一句话结论">{r.conclusion}</Section>
      <Section title="涉及法律（RAG 检索）">
        <p className="whitespace-pre-wrap">{r.legal.markdown}</p>
        {r.legal.citations.length > 0 && (
          <ul className="mt-2 space-y-1 text-xs text-gray-500 dark:text-gray-400">
            {r.legal.citations.map((c) => (
              <li key={c.id}>
                · {c.label}（{c.source}）{c.snippet ? `：${c.snippet}` : ""}
              </li>
            ))}
          </ul>
        )}
        <p className="mt-2 text-xs text-gray-400">{r.legal.note}</p>
      </Section>
      <Section title="我的权益">{r.rights}</Section>
      <Section title="对方可能存在的问题">{r.counterparty_issues}</Section>
      <Section title="建议准备证据">
        {r.evidence.uploaded.length > 0 && (
          <p className="mb-1">已上传：{r.evidence.uploaded.join("、")}</p>
        )}
        <p>建议清单：{r.evidence.checklist.join("、")}</p>
      </Section>
      <Section title="下一步怎么办">
        <ol className="list-decimal space-y-1 pl-5">
          {r.next_steps.map((s) => (
            <li key={s.order}>
              <span className="font-medium">{s.title}</span>
              {s.description ? `：${s.description}` : ""}
              {s.due_offset_days != null ? `（建议第 ${s.due_offset_days} 天）` : ""}
            </li>
          ))}
        </ol>
      </Section>
      <Section title="去哪里">
        <ul className="space-y-1">
          {r.where_to_go.map((d, i) => (
            <li key={i}>
              <span className="font-medium">{d.name}</span>：{d.reason}
            </li>
          ))}
        </ul>
      </Section>
      <Section title="可自动生成文书">
        <div className="flex flex-wrap gap-2">
          {r.documents.map((d) => (
            <Badge key={d.type} tone="brand">
              {d.label}
            </Badge>
          ))}
        </div>
      </Section>
      <Section title="风险分析">
        <p>证据完整度：{r.risk.evidence_completeness}</p>
        <p>复杂度：{r.risk.complexity}</p>
        <p>时效/举证：{r.risk.limitation}</p>
        <p>建议：{r.risk.suggestion}</p>
      </Section>
      <Card>
        <p className="text-xs text-gray-400">{r.disclaimer}</p>
      </Card>
    </div>
  );
}

// ---------------------------
// 证据
// ---------------------------
function EvidencePane({
  caseId,
  items,
  onChange,
}: {
  caseId: string;
  items: EvidenceOut[];
  onChange: (v: EvidenceOut[]) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState<EvidenceCategory>("contract");
  const [title, setTitle] = useState("");
  const [uploading, setUploading] = useState(false);

  const upload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      const ev = await api.uploadEvidence(caseId, file, category, title || undefined);
      onChange([...items, ev]);
      setFile(null);
      setTitle("");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <div className="mb-3 text-sm font-medium">上传证据</div>
        <div className="grid gap-3 sm:grid-cols-3">
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as EvidenceCategory)}
            className="rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm dark:border-white/10 dark:bg-white/5"
          >
            {Object.entries(evidenceCategoryLabels).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="证据名称（选填）" />
          <input
            type="file"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-sm"
          />
        </div>
        <Button className="mt-3" size="sm" onClick={upload} disabled={!file || uploading}>
          {uploading ? <Spinner /> : "上传"}
        </Button>
      </Card>

      {items.length === 0 ? (
        <p className="text-sm text-gray-400">暂无证据。</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {items.map((ev) => (
            <Card key={ev.id}>
              <div className="flex items-center justify-between">
                <span className="font-medium">{ev.title}</span>
                <Badge tone={ev.is_uploaded ? "green" : "amber"}>
                  {ev.is_uploaded ? "已提供" : "待补充"}
                </Badge>
              </div>
              <div className="mt-1 text-xs text-gray-400">{evidenceCategoryLabels[ev.category]}</div>
              {ev.ai_note && <p className="mt-2 text-sm text-gray-500">{ev.ai_note}</p>}
              {ev.ocr_text && (
                <p className="mt-2 max-h-24 overflow-auto text-xs text-gray-500">OCR：{ev.ocr_text}</p>
              )}
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
function DocumentPane({
  caseId,
  items,
  onChange,
}: {
  caseId: string;
  items: DocumentOut[];
  onChange: (v: DocumentOut[]) => void;
}) {
  const [selected, setSelected] = useState<DocumentOut | null>(null);
  const [gen, setGen] = useState(false);

  const generate = async (doc_type: DocumentOut["doc_type"]) => {
    setGen(true);
    try {
      const d = await api.generateDocument(caseId, doc_type);
      onChange([...items, d]);
      setSelected(d);
    } finally {
      setGen(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <div className="mb-3 text-sm font-medium">生成文书</div>
        <div className="flex flex-wrap gap-2">
          {Object.entries(docTypeLabels).map(([k, v]) => (
            <Button key={k} size="sm" variant="outline" disabled={gen} onClick={() => generate(k as DocumentOut["doc_type"])}>
              {v}
            </Button>
          ))}
        </div>
      </Card>

      {items.length === 0 ? (
        <p className="text-sm text-gray-400">尚未生成文书。</p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {items.map((d) => (
            <Card key={d.id} className="cursor-pointer transition hover:shadow-md" onClick={() => setSelected(d)}>
              <div className="flex items-center justify-between">
                <span className="font-medium">{d.title}</span>
                <Badge tone="brand">{docTypeLabels[d.doc_type]}</Badge>
              </div>
            </Card>
          ))}
        </div>
      )}

      {selected && (
        <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/40 p-4" onClick={() => setSelected(null)}>
          <div className="max-h-[80vh] w-full max-w-2xl overflow-auto rounded-2xl bg-white p-6 shadow-xl dark:bg-[#11141a]" onClick={(e) => e.stopPropagation()}>
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-lg font-semibold">{selected.title}</h3>
              <button className="text-gray-400 hover:text-gray-700" onClick={() => setSelected(null)}>
                ✕
              </button>
            </div>
            <pre className="whitespace-pre-wrap text-sm">{selected.content}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------
// 路线图
// ---------------------------
function RoadmapPane({
  caseId,
  roadmap,
  onGenerate,
  onChange,
}: {
  caseId: string;
  roadmap: RoadmapOut | null;
  onGenerate: (r: RoadmapOut) => void;
  onChange: (r: RoadmapOut | null) => void;
}) {
  const toggle = async (step: RoadmapStepOut, status: "done" | "skipped") => {
    const updated = await api.updateStep(caseId, step.id, status);
    if (!roadmap) return;
    onChange({
      ...roadmap,
      steps: roadmap.steps.map((s) => (s.id === step.id ? updated : s)),
    });
  };

  if (!roadmap) {
    return (
      <Card className="py-12 text-center">
        <p className="mb-3 text-gray-500 dark:text-gray-400">还没有办理路线图。</p>
        <Button onClick={async () => onGenerate(await api.generateRoadmap(caseId))}>生成路线图</Button>
      </Card>
    );
  }

  return (
    <div className="space-y-2">
      {roadmap.steps.map((s, i) => (
        <div key={s.id} className="flex items-start gap-3">
          <div
            className={`mt-1 flex h-7 w-7 flex-none items-center justify-center rounded-full text-xs font-medium ${
              s.status === "done"
                ? "bg-green-500 text-white"
                : s.status === "skipped"
                ? "bg-gray-200 text-gray-500 dark:bg-white/10"
                : "bg-brand-50 text-brand-600 dark:bg-brand-500/15"
            }`}
          >
            {i + 1}
          </div>
          <Card className="flex-1">
            <div className="flex items-center justify-between">
              <span className="font-medium">{s.title}</span>
              <div className="flex gap-2">
                <Button size="sm" variant="ghost" onClick={() => toggle(s, "done")}>
                  完成
                </Button>
                <Button size="sm" variant="ghost" onClick={() => toggle(s, "skipped")}>
                  跳过
                </Button>
              </div>
            </div>
            {s.description && (
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{s.description}</p>
            )}
            <div className="mt-1 text-xs text-gray-400">
              {stepStatusLabels[s.status]}
              {s.due_offset_days != null && ` · 建议第 ${s.due_offset_days} 天`}
            </div>
          </Card>
        </div>
      ))}
    </div>
  );
}

// ---------------------------
// 任务
// ---------------------------
function TaskPane({
  caseId,
  items,
  onChange,
}: {
  caseId: string;
  items: TaskOut[];
  onChange: (v: TaskOut[]) => void;
}) {
  const toggle = async (t: TaskOut) => {
    const next = t.status === "done" ? "todo" : "done";
    const updated = await api.updateTask(caseId, t.id, { status: next });
    onChange(items.map((x) => (x.id === t.id ? updated : x)));
  };

  if (items.length === 0) return <p className="text-sm text-gray-400">暂无任务。</p>;

  return (
    <div className="space-y-2">
      {items.map((t) => (
        <Card key={t.id} className="flex items-center justify-between">
          <div>
            <div className={t.status === "done" ? "line-through text-gray-400" : ""}>{t.title}</div>
            {t.description && <p className="text-sm text-gray-500">{t.description}</p>}
          </div>
          <div className="flex items-center gap-2">
            <Badge tone="gray">{taskStatusLabels[t.status]}</Badge>
            <Button size="sm" variant="outline" onClick={() => toggle(t)}>
              {t.status === "done" ? "撤销" : "完成"}
            </Button>
          </div>
        </Card>
      ))}
    </div>
  );
}

// ---------------------------
// 时间线
// ---------------------------
function HistoryPane({ items }: { items: HistoryOut[] }) {
  if (items.length === 0) return <p className="text-sm text-gray-400">暂无事件。</p>;
  return (
    <div className="space-y-3">
      {items.map((h) => (
        <div key={h.id} className="flex gap-3">
          <div className="mt-1.5 h-2 w-2 flex-none rounded-full bg-brand-400" />
          <div>
            <div className="text-sm font-medium">
              {eventTypeLabels[h.event_type]} · {h.title}
            </div>
            {h.detail && <p className="text-sm text-gray-500">{h.detail}</p>}
            <div className="text-xs text-gray-400">{new Date(h.created_at).toLocaleString()}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
