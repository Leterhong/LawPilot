// 法律研究文档详情页（Legal Research Center / Detail）。
// 展示全文、时效与来源、关联文档、AI 通俗解读与摘要，并提供收藏 / 引用 / 复制 / 下载 / 打印。
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  BookOpen,
  Calendar,
  Building2,
  MapPin,
  Tag,
  Star,
  Quote,
  Copy,
  Download,
  Printer,
  FileText,
  ArrowLeft,
  Sparkles,
  Link2,
} from "lucide-react";
import api, {
  type ResearchDocDetail,
  type ResearchRecommendResult,
  type RelatedDocRef,
} from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { Badge, Button, Card, Spinner } from "@/components/ui";
import { researchDocTypeTone, researchCategoryLabels } from "@/lib/constants";

const FAV_KEY = "lp_research_favs";

function loadFavs(): Record<string, boolean> {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(FAV_KEY) || "{}");
  } catch {
    return {};
  }
}

export default function ResearchDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [doc, setDoc] = useState<ResearchDocDetail | null>(null);
  const [rec, setRec] = useState<ResearchRecommendResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [faved, setFaved] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const flash = (msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(null), 1800);
  };

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setNotFound(false);
    Promise.all([
      api.research.detail(id),
      api.research.recommend({ doc_id: id, limit: 5 }).catch(() => null),
    ])
      .then(([d, r]) => {
        setDoc(d);
        setRec(r);
        setFaved(loadFavs()[id] ?? false);
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [id]);

  const toggleFav = () => {
    const next = !faved;
    setFaved(next);
    const favs = loadFavs();
    if (next) favs[id] = true;
    else delete favs[id];
    localStorage.setItem(FAV_KEY, JSON.stringify(favs));
    flash(next ? "已加入收藏" : "已取消收藏");
  };

  const buildCitation = (d: ResearchDocDetail): string => {
    const num = d.doc_number ? `〔${d.doc_number}〕` : "";
    const src = d.source ? `（${d.source}` : "（来源不详";
    const date = d.publish_date ? `，${d.publish_date}）` : "）";
    return `《${d.title}》${num}${src}${date}`;
  };

  const copy = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      flash(label);
    } catch {
      flash("复制失败，请手动选择");
    }
  };

  const download = (d: ResearchDocDetail) => {
    const meta = [
      `# ${d.title}`,
      "",
      `- 分类：${d.category_label ?? d.category}`,
      `- 类型：${d.doc_type_label ?? d.doc_type}`,
      d.doc_number ? `- 文号：${d.doc_number}` : "",
      d.source ? `- 来源：${d.source}` : "",
      d.issuing_authority ? `- 发文机关：${d.issuing_authority}` : "",
      d.level ? `- 效力层级：${d.level}` : "",
      d.region ? `- 地区：${d.region}` : "",
      d.publish_date ? `- 发布日期：${d.publish_date}` : "",
      d.effective_date ? `- 生效日期：${d.effective_date}` : "",
      d.expiry_date ? `- 失效日期：${d.expiry_date}` : "",
      `- 现行有效：${d.is_current ? "是" : "否"}`,
      "",
      "## 正文",
      "",
      d.full_text ?? "",
    ]
      .filter((l) => l !== "")
      .join("\n");
    const blob = new Blob([meta], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${d.title}.md`;
    a.click();
    URL.revokeObjectURL(url);
    flash("已下载 Markdown");
  };

  if (loading) {
    return (
      <AppShell>
        <div className="flex justify-center py-24">
          <Spinner />
        </div>
      </AppShell>
    );
  }

  if (notFound || !doc) {
    return (
      <AppShell>
        <Card className="py-16 text-center text-gray-500 dark:text-gray-400">
          未找到该文档，可能已被移除。
          <div className="mt-4">
            <Link href="/research">
              <Button variant="outline">返回法律研究</Button>
            </Link>
          </div>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <Link href="/research" className="mb-4 inline-flex items-center gap-1 text-sm text-gray-400 hover:text-brand-600">
        <ArrowLeft className="h-4 w-4" />
        返回法律研究
      </Link>

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        {/* 主栏 */}
        <section>
          <Card>
            <div className="flex flex-wrap items-center gap-2">
              {doc.category_label && (
                <Badge tone={researchDocTypeTone[doc.doc_type] ?? "gray"}>
                  {doc.category_label}
                </Badge>
              )}
              {doc.doc_type_label && doc.doc_type_label !== doc.category_label && (
                <Badge tone="gray">{doc.doc_type_label}</Badge>
              )}
              <Badge tone={doc.is_current ? "green" : "red"}>
                {doc.is_current ? "现行有效" : "已失效 / 未施行"}
              </Badge>
            </div>

            <h1 className="mt-3 text-2xl font-bold leading-snug">{doc.title}</h1>

            {/* 元信息 */}
            <div className="mt-4 grid gap-2 text-sm text-gray-500 dark:text-gray-400 sm:grid-cols-2">
              {doc.doc_number && (
                <span className="inline-flex items-center gap-1">
                  <FileText className="h-4 w-4" /> 文号：{doc.doc_number}
                </span>
              )}
              {doc.source && (
                <span className="inline-flex items-center gap-1">
                  <Building2 className="h-4 w-4" /> 来源：{doc.source}
                </span>
              )}
              {doc.issuing_authority && (
                <span className="inline-flex items-center gap-1">
                  <Building2 className="h-4 w-4" /> 发文机关：{doc.issuing_authority}
                </span>
              )}
              {doc.level && <span>效力层级：{doc.level}</span>}
              {doc.region && (
                <span className="inline-flex items-center gap-1">
                  <MapPin className="h-4 w-4" /> 地区：{doc.region}
                </span>
              )}
              {doc.publish_date && (
                <span className="inline-flex items-center gap-1">
                  <Calendar className="h-4 w-4" /> 发布：{doc.publish_date}
                </span>
              )}
              {doc.effective_date && (
                <span className="inline-flex items-center gap-1">
                  <Calendar className="h-4 w-4" /> 生效：{doc.effective_date}
                </span>
              )}
              {doc.expiry_date && (
                <span className="inline-flex items-center gap-1">
                  <Calendar className="h-4 w-4" /> 失效：{doc.expiry_date}
                </span>
              )}
            </div>

            {/* 操作 */}
            <div className="mt-5 flex flex-wrap gap-2">
              <Button variant={faved ? "primary" : "outline"} size="sm" onClick={toggleFav}>
                <Star className="h-4 w-4" fill={faved ? "currentColor" : "none"} />
                {faved ? "已收藏" : "收藏"}
              </Button>
              <Button variant="outline" size="sm" onClick={() => copy(buildCitation(doc), "引用已复制")}>
                <Quote className="h-4 w-4" /> 引用
              </Button>
              <Button variant="outline" size="sm" onClick={() => copy(doc.full_text ?? "", "全文已复制")}>
                <Copy className="h-4 w-4" /> 复制全文
              </Button>
              <Button variant="outline" size="sm" onClick={() => download(doc)}>
                <Download className="h-4 w-4" /> 下载
              </Button>
              <Button variant="outline" size="sm" onClick={() => window.print()}>
                <Printer className="h-4 w-4" /> 打印
              </Button>
            </div>
          </Card>

          {/* AI 摘要 + 通俗解读 */}
          {(doc.ai_summary || doc.ai_explanation) && (
            <div className="mt-4 space-y-4">
              {doc.ai_summary && (
                <Card className="border-brand-200 dark:border-brand-500/30">
                  <div className="flex items-center gap-2 text-sm font-semibold text-brand-600 dark:text-brand-300">
                    <Sparkles className="h-4 w-4" /> AI 一句话摘要
                  </div>
                  <p className="mt-2 text-sm text-gray-700 dark:text-gray-200">{doc.ai_summary}</p>
                </Card>
              )}
              {doc.ai_explanation && (
                <Card>
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    <Sparkles className="h-4 w-4 text-brand-500" /> AI 通俗解读
                  </div>
                  <p className="mt-2 whitespace-pre-line text-sm text-gray-700 dark:text-gray-200">
                    {doc.ai_explanation}
                  </p>
                </Card>
              )}
            </div>
          )}

          {/* 核心要点 / 适用范围 / 常见误区 */}
          {(doc.core_points?.length || doc.scope || doc.common_misconceptions?.length) && (
            <Card className="mt-4 space-y-4">
              {doc.core_points && doc.core_points.length > 0 && (
                <div>
                  <div className="text-sm font-semibold">核心要点</div>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-gray-600 dark:text-gray-300">
                    {doc.core_points.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}
              {doc.scope && (
                <div>
                  <div className="text-sm font-semibold">适用范围</div>
                  <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">{doc.scope}</p>
                </div>
              )}
              {doc.common_misconceptions && doc.common_misconceptions.length > 0 && (
                <div>
                  <div className="text-sm font-semibold">常见误区</div>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-gray-600 dark:text-gray-300">
                    {doc.common_misconceptions.map((p, i) => (
                      <li key={i}>{p}</li>
                    ))}
                  </ul>
                </div>
              )}
            </Card>
          )}

          {/* 全文 */}
          <Card className="mt-4">
            <div className="text-sm font-semibold">全文</div>
            <div className="mt-3 whitespace-pre-line text-sm leading-relaxed text-gray-700 dark:text-gray-200 print:whitespace-pre-wrap">
              {doc.full_text || "（暂无全文内容）"}
            </div>
          </Card>
        </section>

        {/* 侧栏 */}
        <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          {doc.related_docs && doc.related_docs.length > 0 && (
            <Card>
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Link2 className="h-4 w-4 text-brand-500" /> 关联文档
              </div>
              <ul className="mt-3 space-y-2">
                {doc.related_docs.map((d: RelatedDocRef) => (
                  <li key={d.id}>
                    <Link
                      href={`/research/${d.id}`}
                      className="group block rounded-lg p-2 transition hover:bg-gray-50 dark:hover:bg-white/5"
                    >
                      <span className="block text-sm text-gray-700 group-hover:text-brand-600 dark:text-gray-200">
                        {d.title}
                      </span>
                      <span className="text-xs text-gray-400">
                        {researchCategoryLabels[d.category] ?? d.category}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {rec && rec.items.length > 0 && (
            <Card>
              <div className="flex items-center gap-2 text-sm font-semibold">
                <FileText className="h-4 w-4 text-brand-500" /> 相关推荐
              </div>
              <ul className="mt-3 space-y-2">
                {rec.items.map((it) => (
                  <li key={it.id}>
                    <Link
                      href={`/research/${it.id}`}
                      className="group block rounded-lg p-2 transition hover:bg-gray-50 dark:hover:bg-white/5"
                    >
                      <span className="block text-sm text-gray-700 group-hover:text-brand-600 dark:text-gray-200">
                        {it.title}
                      </span>
                      {it.category_label && (
                        <span className="text-xs text-gray-400">{it.category_label}</span>
                      )}
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {doc.keywords && doc.keywords.length > 0 && (
            <Card>
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Tag className="h-4 w-4 text-brand-500" /> 关键词
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {doc.keywords.map((k) => (
                  <span
                    key={k}
                    className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500 dark:bg-white/10 dark:text-gray-300"
                  >
                    {k}
                  </span>
                ))}
              </div>
            </Card>
          )}
        </aside>
      </div>

      {/* 复核信息（开发期透明化） */}
      <p className="mt-6 text-xs text-gray-400">
        复核提示：本页内容来自法律研究中心数据库；AI 摘要与解读在接入模型后自动生成，仅供参考，不构成法律意见。
      </p>

      {toast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-xl bg-gray-900 px-4 py-2 text-sm text-white shadow-lg dark:bg-white dark:text-gray-900">
          {toast}
        </div>
      )}
    </AppShell>
  );
}
