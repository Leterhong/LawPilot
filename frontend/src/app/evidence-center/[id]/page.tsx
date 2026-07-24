"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  api,
  type EvidenceDetailOut,
  type EvidenceRelationOut,
  type EvidenceGraphOut,
  type EvidenceTimelineNodeOut,
  type EvidenceRelationType,
  type EvidenceFileCategory,
} from "@/lib/api";
import {
  evidenceFileCategoryLabels,
  evidenceFileCategoryTone,
  evidenceFileStatusLabels,
  evidenceFileStatusTone,
  evidenceRelationLabels,
  evidenceRelationTone,
} from "@/lib/constants";
import { AppShell } from "@/components/AppShell";
import { Badge, Button, Card, Input, Spinner, Textarea } from "@/components/ui";
import { cn } from "@/lib/utils";

type Tab = "overview" | "preview" | "analysis" | "graph" | "timeline";

const RELATION_TYPES = Object.keys(evidenceRelationLabels) as EvidenceRelationType[];

const DIMENSION_LABELS: Record<string, string> = {
  completeness: "完整性",
  authenticity: "真实性",
  relevance: "关联性",
  legality: "合法性",
  proof_strength: "证明力",
};

const EDGE_COLOR: Record<EvidenceRelationType, string> = {
  sequence: "#9ca3af",
  support: "#22c55e",
  contradict: "#ef4444",
  prerequisite: "#f59e0b",
  related: "#6366f1",
};

function formatDate(s: string | null): string {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleString("zh-CN");
  } catch {
    return s;
  }
}

function formatSize(n: number | null): string {
  if (n == null) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function Stars({ value }: { value: number | null }) {
  const v = Math.max(0, Math.min(5, value ?? 0));
  return (
    <span className="tracking-tight text-amber-500">
      {"★".repeat(v)}
      <span className="text-gray-300 dark:text-gray-600">{"★".repeat(5 - v)}</span>
      <span className="ml-1 text-xs text-gray-400">{v}/5</span>
    </span>
  );
}

// 证据图谱 SVG（圆形布局）
function EvidenceGraph({
  graph,
  currentId,
}: {
  graph: EvidenceGraphOut;
  currentId: string;
}) {
  const W = 680;
  const n = graph.nodes.length;
  const R = Math.min(260, 140 + n * 10);
  const H = 2 * R + 140;
  const cx = W / 2;
  const cy = H / 2;

  const pos = useMemo(() => {
    const map: Record<string, { x: number; y: number }> = {};
    graph.nodes.forEach((node, i) => {
      const ang = (2 * Math.PI * i) / Math.max(1, n) - Math.PI / 2;
      map[node.id] = { x: cx + R * Math.cos(ang), y: cy + R * Math.sin(ang) };
    });
    return map;
  }, [graph.nodes, n, R, cx, cy]);

  if (n === 0) return null;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="证据链图谱">
      <defs>
        <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">
          <path d="M0,0 L8,3 L0,6 Z" fill="#94a3b8" />
        </marker>
      </defs>
      {/* 边 */}
      {graph.edges.map((e) => {
        const s = pos[e.source_id];
        const t = pos[e.target_id];
        if (!s || !t) return null;
        const mx = (s.x + t.x) / 2;
        const my = (s.y + t.y) / 2;
        const color = EDGE_COLOR[e.relation_type] ?? "#94a3b8";
        return (
          <g key={e.id}>
            <line
              x1={s.x}
              y1={s.y}
              x2={t.x}
              y2={t.y}
              stroke={color}
              strokeWidth={1.8}
              strokeOpacity={0.7}
              markerEnd="url(#arrow)"
            />
            <rect x={mx - 30} y={my - 11} width={60} height={20} rx={6} fill="#fff" opacity={0.92} />
            <text x={mx} y={my + 4} textAnchor="middle" fontSize={11} fill={color}>
              {evidenceRelationLabels[e.relation_type] ?? e.relation_type}
            </text>
          </g>
        );
      })}
      {/* 节点 */}
      {graph.nodes.map((node) => {
        const p = pos[node.id];
        const isCurrent = node.id === currentId;
        const tone = evidenceFileCategoryTone[node.category as EvidenceFileCategory] ?? "gray";
        const toneColor =
          tone === "green"
            ? "#22c55e"
            : tone === "amber"
            ? "#f59e0b"
            : tone === "red"
            ? "#ef4444"
            : tone === "brand"
            ? "#6366f1"
            : "#9ca3af";
        const label =
          (evidenceFileCategoryLabels[node.category as EvidenceFileCategory] ?? node.category) +
          (node.proof_strength ? ` · ${node.proof_strength}★` : "");
        return (
          <g key={node.id} transform={`translate(${p.x},${p.y})`}>
            <rect
              x={-70}
              y={-26}
              width={140}
              height={52}
              rx={10}
              fill={isCurrent ? "#eef2ff" : "#fff"}
              stroke={isCurrent ? "#6366f1" : toneColor}
              strokeWidth={isCurrent ? 2.5 : 1.5}
            />
            <text
              x={0}
              y={-6}
              textAnchor="middle"
              fontSize={12}
              fontWeight={600}
              fill="#111827"
              style={{ wordBreak: "break-all" }}
            >
              {node.name.length > 14 ? node.name.slice(0, 14) + "…" : node.name}
            </text>
            <text x={0} y={14} textAnchor="middle" fontSize={10} fill={toneColor}>
              {label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function EvidenceDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { token } = useAuth();
  const id = typeof params.id === "string" ? params.id : Array.isArray(params.id) ? params.id[0] : "";

  const [detail, setDetail] = useState<EvidenceDetailOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");

  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [relations, setRelations] = useState<EvidenceRelationOut[]>([]);
  const [graph, setGraph] = useState<EvidenceGraphOut | null>(null);
  const [timeline, setTimeline] = useState<EvidenceTimelineNodeOut[]>([]);

  const [analyzing, setAnalyzing] = useState(false);
  const [building, setBuilding] = useState(false);
  const [graphMsg, setGraphMsg] = useState<string | null>(null);

  // 建立关系表单
  const [targetId, setTargetId] = useState("");
  const [relationType, setRelationType] = useState<EvidenceRelationType>("support");
  const [relationNote, setRelationNote] = useState("");

  const loadDetail = useCallback(async () => {
    if (!token || !id) return;
    setLoading(true);
    setErr(null);
    try {
      const d = await api.evidenceCenter.get(id);
      setDetail(d);
      await Promise.all([loadRelationsAndGraph(d), loadTimeline(d)]);
    } catch (e: any) {
      setErr(e?.message || "加载失败");
    } finally {
      setLoading(false);
    }
  }, [token, id]);

  const loadRelationsAndGraph = useCallback(
    async (d: EvidenceDetailOut) => {
      try {
        if (d.case_id) {
          const [rels, g] = await Promise.all([
            api.evidenceCenter.listRelations({ case_id: d.case_id }),
            api.evidenceCenter.graph({ case_id: d.case_id }),
          ]);
          setRelations(rels);
          setGraph(g);
        } else {
          const rels = await api.evidenceCenter.listRelations({ evidence_id: id });
          setRelations(rels);
          const relatedIds = Array.from(
            new Set(
              rels.flatMap((r) =>
                [r.source_id, r.target_id].filter((x) => x !== id)
              )
            )
          );
          const g = await api.evidenceCenter.graph({
            evidence_ids: [id, ...relatedIds],
          });
          setGraph(g);
        }
      } catch (e: any) {
        setGraphMsg(e?.message || "加载关系/图谱失败");
      }
    },
    [id]
  );

  const loadTimeline = useCallback(async (d: EvidenceDetailOut) => {
    if (!d.case_id) {
      setTimeline([]);
      return;
    }
    try {
      const t = await api.evidenceCenter.timeline(d.case_id);
      setTimeline(t);
    } catch {
      setTimeline([]);
    }
  }, []);

  useEffect(() => {
    if (!token) {
      router.replace("/login");
      return;
    }
    loadDetail();
  }, [token, router, loadDetail]);

  // 预览：按需取 blob
  const previewKind = useMemo(() => {
    const ft = detail?.file_type?.toLowerCase() ?? "";
    if (["png", "jpg", "jpeg", "gif", "webp", "bmp", "tif", "tiff", "heic"].includes(ft))
      return "image";
    if (ft === "pdf") return "pdf";
    if (["mp3", "wav", "m4a", "aac", "ogg"].includes(ft)) return "audio";
    if (["mp4", "mov", "avi", "webm", "mkv"].includes(ft)) return "video";
    return "text";
  }, [detail?.file_type]);

  useEffect(() => {
    let url: string | null = null;
    if (detail && previewKind !== "text") {
      api.evidenceCenter
        .fileUrl(detail.id)
        .then((u) => {
          url = u;
          setPreviewUrl(u);
        })
        .catch(() => setPreviewUrl(null));
    } else {
      setPreviewUrl(null);
    }
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [detail, previewKind]);

  async function onAnalyze(force: boolean) {
    if (!detail) return;
    setAnalyzing(true);
    setErr(null);
    try {
      await api.evidenceCenter.analyzeSingle(detail.id, force);
      await loadDetail();
    } catch (e: any) {
      setErr(e?.message || "分析失败");
    } finally {
      setAnalyzing(false);
    }
  }

  async function onBuildChain() {
    if (!detail) return;
    setBuilding(true);
    setGraphMsg(null);
    try {
      const res = await api.evidenceCenter.buildChain({
        case_id: detail.case_id ?? null,
        evidence_ids: detail.case_id ? null : [detail.id],
        infer_relations: true,
        build_timeline: !!detail.case_id,
      });
      setGraphMsg(
        `已处理 ${res.evidence_count} 份证据，新建关系 ${res.relations_created} 条` +
          (detail.case_id ? `，时间线节点 ${res.timeline_nodes} 个` : "") +
          (res.note ? `（${res.note}）` : "")
      );
      await Promise.all([loadRelationsAndGraph(detail), loadTimeline(detail)]);
    } catch (e: any) {
      setGraphMsg(e?.message || "构建失败");
    } finally {
      setBuilding(false);
    }
  }

  async function onCreateRelation() {
    if (!detail || !targetId) return;
    try {
      await api.evidenceCenter.createRelation({
        source_id: detail.id,
        target_id: targetId,
        relation_type: relationType,
        note: relationNote.trim() || null,
      });
      setRelationNote("");
      setTargetId("");
      await loadRelationsAndGraph(detail);
    } catch (e: any) {
      setGraphMsg(e?.message || "建立关系失败");
    }
  }

  async function onDeleteRelation(relId: string) {
    try {
      await api.evidenceCenter.deleteRelation(relId);
      if (detail) await loadRelationsAndGraph(detail);
    } catch (e: any) {
      setGraphMsg(e?.message || "删除关系失败");
    }
  }

  async function onDelete() {
    if (!detail) return;
    if (!confirm(`确认删除证据「${detail.name}」？此操作不可恢复。`)) return;
    try {
      await api.evidenceCenter.remove(detail.id);
      router.push("/evidence-center");
    } catch (e: any) {
      setErr(e?.message || "删除失败");
    }
  }

  // 关系两端证据名（来自图谱节点）
  const nameMap = useMemo(() => {
    const m: Record<string, string> = {};
    graph?.nodes.forEach((n) => (m[n.id] = n.name));
    return m;
  }, [graph]);

  const TABS: { key: Tab; label: string }[] = [
    { key: "overview", label: "概览" },
    { key: "preview", label: "预览" },
    { key: "analysis", label: "AI 分析" },
    { key: "graph", label: "关系与链图" },
    { key: "timeline", label: "时间线" },
  ];

  if (loading) {
    return (
      <AppShell>
        <div className="flex items-center justify-center py-20 text-gray-400">
          <Spinner className="mr-2" /> 加载中…
        </div>
      </AppShell>
    );
  }

  if (err && !detail) {
    return (
      <AppShell>
        <Card className="text-center text-sm text-red-600 dark:text-red-300">{err}</Card>
        <div className="mt-4 text-center">
          <Link href="/evidence-center" className="text-sm text-brand-600 hover:underline">
            ← 返回证据列表
          </Link>
        </div>
      </AppShell>
    );
  }

  if (!detail) return null;

  const a = detail.analysis;
  const dims = (a?.dimensions ?? null) as Record<string, number> | null;

  return (
    <AppShell>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link
            href="/evidence-center"
            className="text-sm text-gray-500 hover:underline dark:text-gray-400"
          >
            ← 返回证据列表
          </Link>
          <div className="mt-1 flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">{detail.name}</h1>
            <Badge tone={evidenceFileCategoryTone[detail.category] ?? "gray"}>
              {evidenceFileCategoryLabels[detail.category] ?? detail.category}
            </Badge>
            <Badge tone={evidenceFileStatusTone[detail.status] ?? "gray"}>
              {evidenceFileStatusLabels[detail.status] ?? detail.status}
            </Badge>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            onClick={() => api.evidenceCenter.downloadFile(detail.id, detail.name)}
          >
            下载原件
          </Button>
          <Link href={`/evidence-center/${detail.id}/report`}>
            <Button variant="outline">生成报告</Button>
          </Link>
          <Button variant="danger" onClick={onDelete}>
            删除
          </Button>
        </div>
      </div>

      {err && (
        <div className="mb-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/15 dark:text-red-300">
          {err}
        </div>
      )}

      {/* Tab 切换 */}
      <div className="mb-5 flex flex-wrap gap-2 border-b border-gray-100 dark:border-white/10">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              "-mb-px border-b-2 px-3 py-2 text-sm transition",
              tab === t.key
                ? "border-brand-500 font-medium text-brand-600 dark:text-brand-300"
                : "border-transparent text-gray-500 hover:text-gray-900 dark:hover:text-gray-100"
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 概览 */}
      {tab === "overview" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-200">
              基本信息
            </h3>
            <dl className="space-y-2 text-sm">
              <Row label="文件类型" value={detail.file_type?.toUpperCase() ?? "—"} />
              <Row label="大小" value={formatSize(detail.size_bytes)} />
              <Row label="来源" value={detail.source ?? "—"} />
              <Row label="形成时间" value={formatDate(detail.formed_at)} />
              <Row label="归属案件" value={detail.case_id ? "已关联案件" : "未关联"} />
              <Row label="上传时间" value={formatDate(detail.created_at)} />
              <Row
                label="标签"
                value={
                  detail.tags && detail.tags.length
                    ? detail.tags.map((t) => `#${t}`).join(" ")
                    : "—"
                }
              />
            </dl>
          </Card>
          <Card>
            <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-200">
              AI 分析摘要
            </h3>
            {a ? (
              <div className="space-y-3 text-sm">
                <div>
                  <span className="text-gray-500">证明力：</span>
                  <Stars value={a.proof_strength} />
                </div>
                <p className="whitespace-pre-wrap text-gray-700 dark:text-gray-200">
                  {a.summary ?? "（无摘要）"}
                </p>
                {a.proof_point && (
                  <p className="text-gray-500">
                    <span className="text-gray-700 dark:text-gray-200">证明事项：</span>
                    {a.proof_point}
                  </p>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-sm text-gray-400">尚未进行 AI 分析。</p>
                <Button onClick={() => onAnalyze(false)} disabled={analyzing}>
                  {analyzing ? (
                    <>
                      <Spinner className="mr-1" /> 分析中…
                    </>
                  ) : (
                    "开始分析"
                  )}
                </Button>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* 预览 */}
      {tab === "preview" && (
        <Card>
          {previewKind === "image" && previewUrl && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={previewUrl}
              alt={detail.name}
              className="mx-auto max-h-[70vh] rounded-lg object-contain"
            />
          )}
          {previewKind === "pdf" && previewUrl && (
            <iframe src={previewUrl} className="h-[70vh] w-full rounded-lg" title={detail.name} />
          )}
          {previewKind === "audio" && previewUrl && (
            <audio controls src={previewUrl} className="w-full" />
          )}
          {previewKind === "video" && previewUrl && (
            <video controls src={previewUrl} className="mx-auto max-h-[70vh] rounded-lg" />
          )}
          {previewKind === "text" && (
            <div>
              {detail.ocr_text ? (
                <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap text-sm text-gray-700 dark:text-gray-200">
                  {detail.ocr_text}
                </pre>
              ) : (
                <p className="text-sm text-gray-400">
                  该类型暂不支持在线预览。可点击右上角「下载原件」查看。
                </p>
              )}
            </div>
          )}
        </Card>
      )}

      {/* AI 分析 */}
      {tab === "analysis" && (
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200">
              AI 证据分析
            </h3>
            <Button variant="outline" size="sm" onClick={() => onAnalyze(true)} disabled={analyzing}>
              {analyzing ? (
                <>
                  <Spinner className="mr-1" /> 分析中…
                </>
              ) : (
                "重新分析"
              )}
            </Button>
          </div>
          {a ? (
            <div className="space-y-4 text-sm">
              <div className="flex items-center gap-3">
                <span className="w-16 text-gray-500">证明力</span>
                <Stars value={a.proof_strength} />
              </div>
              <Field label="摘要" value={a.summary} />
              <Field label="证明事项" value={a.proof_point} />
              <Field label="风险 / 瑕疵" value={a.risk} />
              <Field label="补强建议" value={a.suggestion} />
              {dims && (
                <div>
                  <div className="mb-2 text-gray-500">五维评分</div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {Object.entries(dims).map(([k, v]) => (
                      <div key={k} className="flex items-center gap-2">
                        <span className="w-16 shrink-0 text-gray-600 dark:text-gray-300">
                          {DIMENSION_LABELS[k] ?? k}
                        </span>
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100 dark:bg-white/10">
                          <div
                            className="h-full rounded-full bg-brand-500"
                            style={{ width: `${((v ?? 0) / 5) * 100}%` }}
                          />
                        </div>
                        <span className="w-8 text-right text-xs text-gray-400">
                          {v ?? 0}/5
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {a.model_used && (
                <p className="text-xs text-gray-400">分析模型：{a.model_used}</p>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-gray-400">尚未进行 AI 分析。</p>
              <Button onClick={() => onAnalyze(false)} disabled={analyzing}>
                {analyzing ? (
                  <>
                    <Spinner className="mr-1" /> 分析中…
                  </>
                ) : (
                  "开始分析"
                )}
              </Button>
            </div>
          )}
        </Card>
      )}

      {/* 关系与链图 */}
      {tab === "graph" && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-200">
              证据关系与证据链图谱
            </h3>
            <Button variant="outline" size="sm" onClick={onBuildChain} disabled={building}>
              {building ? (
                <>
                  <Spinner className="mr-1" /> 构建中…
                </>
              ) : (
                "构建 / 刷新证据链"
              )}
            </Button>
          </div>
          {graphMsg && (
            <div className="rounded-xl bg-brand-50 px-3 py-2 text-sm text-brand-700 dark:bg-brand-500/15 dark:text-brand-300">
              {graphMsg}
            </div>
          )}

          <Card>
            {graph && graph.nodes.length > 0 ? (
              <EvidenceGraph graph={graph} currentId={detail.id} />
            ) : (
              <p className="py-8 text-center text-sm text-gray-400">
                该证据暂无关联的其他证据，可在下方手动建立关系，或在案件层面「构建证据链」。
              </p>
            )}
          </Card>

          {/* 建立关系 */}
          <Card>
            <h4 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-200">
              建立关系
            </h4>
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex-1 min-w-[200px]">
                <label className="mb-1 block text-xs text-gray-500">关联到的证据</label>
                <select
                  value={targetId}
                  onChange={(e) => setTargetId(e.target.value)}
                  className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
                >
                  <option value="">请选择…</option>
                  {graph?.nodes
                    .filter((n) => n.id !== detail.id)
                    .map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.name}
                      </option>
                    ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs text-gray-500">关系类型</label>
                <select
                  value={relationType}
                  onChange={(e) => setRelationType(e.target.value as EvidenceRelationType)}
                  className="rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
                >
                  {RELATION_TYPES.map((r) => (
                    <option key={r} value={r}>
                      {evidenceRelationLabels[r]}
                    </option>
                  ))}
                </select>
              </div>
              <Button onClick={onCreateRelation} disabled={!targetId}>
                建立
              </Button>
            </div>
            <div className="mt-3">
              <Textarea
                value={relationNote}
                onChange={(e) => setRelationNote(e.target.value)}
                placeholder="关系说明（可选）"
                rows={2}
              />
            </div>
          </Card>

          {/* 关系列表 */}
          <Card>
            <h4 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-200">
              已有关系（{relations.length}）
            </h4>
            {relations.length === 0 ? (
              <p className="text-sm text-gray-400">暂无关系。</p>
            ) : (
              <ul className="space-y-2">
                {relations.map((r) => (
                  <li
                    key={r.id}
                    className="flex items-center justify-between gap-3 rounded-xl border border-gray-100 px-3 py-2 text-sm dark:border-white/10"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{nameMap[r.source_id] ?? r.source_id}</span>
                      <Badge tone={evidenceRelationTone[r.relation_type] ?? "gray"}>
                        {evidenceRelationLabels[r.relation_type] ?? r.relation_type}
                      </Badge>
                      <span className="text-gray-400">→</span>
                      <span className="font-medium">{nameMap[r.target_id] ?? r.target_id}</span>
                      {r.note && <span className="text-gray-500">（{r.note}）</span>}
                    </div>
                    <button
                      onClick={() => onDeleteRelation(r.id)}
                      className="shrink-0 text-xs text-gray-400 hover:text-red-500"
                    >
                      删除
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}

      {/* 时间线 */}
      {tab === "timeline" && (
        <Card>
          <h3 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-200">
            案件时间线
          </h3>
          {!detail.case_id ? (
            <p className="text-sm text-gray-400">
              该证据未关联案件，时间线仅在归入案件后可用。可在列表页上传时指定归属案件，或「构建证据链」时选择案件。
            </p>
          ) : timeline.length === 0 ? (
            <p className="text-sm text-gray-400">
              暂无时间线节点。点击「构建 / 刷新证据链」可依据证据形成时间自动生成。
            </p>
          ) : (
            <ol className="relative ml-3 border-l border-gray-200 dark:border-white/10">
              {timeline.map((node) => (
                <li key={node.id} className="mb-5 ml-5">
                  <div className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border border-white bg-brand-500 dark:border-[#090b10]" />
                  <time className="text-xs text-gray-400">
                    {node.event_time ? formatDate(node.event_time) : `第 ${node.order_index + 1} 节点`}
                  </time>
                  <p className="mt-1 text-sm font-medium text-gray-800 dark:text-gray-100">
                    {node.event}
                  </p>
                  {node.description && (
                    <p className="mt-1 text-sm text-gray-500">{node.description}</p>
                  )}
                </li>
              ))}
            </ol>
          )}
        </Card>
      )}
    </AppShell>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-gray-50 pb-1 last:border-0 dark:border-white/5">
      <dt className="text-gray-500">{label}</dt>
      <dd className="text-right font-medium text-gray-800 dark:text-gray-100">{value}</dd>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div>
      <div className="text-gray-500">{label}</div>
      <p className="mt-1 whitespace-pre-wrap text-gray-800 dark:text-gray-100">{value}</p>
    </div>
  );
}
