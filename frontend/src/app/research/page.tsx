// 法律研究中心（Legal Research Center）主页。
// 三栏布局：左=资源分类，中=检索框 + 高级过滤 + 结果列表，右=AI 摘要 + 相关推荐。
// 所有接口公开，无需登录即可使用（知网 / Google Scholar 风格）。
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  BookOpen,
  Search,
  SlidersHorizontal,
  Sparkles,
  FileText,
  Calendar,
  Building2,
  MapPin,
  Tag,
  ArrowRight,
  X,
} from "lucide-react";
import api, {
  type ResearchSearchItem,
  type ResearchRecommendResult,
} from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { Badge, Button, Card, Input, Spinner } from "@/components/ui";
import {
  researchCategories,
  researchCategoryLabels,
  researchDocTypeTone,
  researchSearchModes,
  researchHotQueries,
} from "@/lib/constants";

const PAGE_SIZE = 10;

// 仅放行后端返回的 <mark> 标签，其余转义，防止高亮注入脚本。
function sanitizeMarks(html: string): string {
  const escaped = html
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return escaped
    .replace(/&lt;mark&gt;/g, "<mark>")
    .replace(/&lt;\/mark&gt;/g, "</mark>");
}

interface AdvancedFilters {
  level: string;
  region: string;
  issuing_authority: string;
  is_current: string; // "" | "true" | "false"
  publish_from: string;
  publish_to: string;
}

const EMPTY_ADV: AdvancedFilters = {
  level: "",
  region: "",
  issuing_authority: "",
  is_current: "",
  publish_from: "",
  publish_to: "",
};

// 由左侧分类 key 推导后端过滤参数（法律/行政法规/指导性案例/典型案例 落在 legal_document 表内用 category 区分）
function paramsForCategory(key: string | null): { doc_type?: string; category?: string } {
  if (!key) return {};
  const def = researchCategories.find((c) => c.key === key);
  if (!def) return {};
  const p: { doc_type?: string; category?: string } = {};
  if (def.doc_type) p.doc_type = def.doc_type;
  if (def.category) p.category = def.category;
  return p;
}

export default function ResearchPage() {
  const [q, setQ] = useState("");
  const [searchMode, setSearchMode] = useState("auto");
  const [categoryKey, setCategoryKey] = useState<string | null>(null);
  const [adv, setAdv] = useState<AdvancedFilters>(EMPTY_ADV);
  const [advOpen, setAdvOpen] = useState(false);

  const [items, setItems] = useState<ResearchSearchItem[]>([]);
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState<Record<string, { label: string; count: number }> | null>(null);
  const [searched, setSearched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [lastQuery, setLastQuery] = useState("");

  // 右侧相关推荐
  const [rec, setRec] = useState<ResearchRecommendResult | null>(null);
  const [recBusy, setRecBusy] = useState(false);

  const reqId = useRef(0);

  const runSearch = useCallback(
    async (query: string, mode: string, catKey: string | null, a: AdvancedFilters) => {
      const myId = ++reqId.current;
      setBusy(true);
      try {
        const catParams = paramsForCategory(catKey);
        const res = await api.research.search(query, {
          ...catParams,
          level: a.level || undefined,
          region: a.region || undefined,
          issuing_authority: a.issuing_authority || undefined,
          is_current: a.is_current ? a.is_current === "true" : undefined,
          publish_from: a.publish_from || undefined,
          publish_to: a.publish_to || undefined,
          search_mode: mode,
          limit: PAGE_SIZE,
          offset: 0,
        });
        if (myId !== reqId.current) return; // 丢弃过期响应
        setItems(res.items);
        setTotal(res.total);
        setFacets(res.facets);
        setSearched(true);
        setLastQuery(query);
      } catch {
        if (myId === reqId.current) setItems([]);
      } finally {
        if (myId === reqId.current) setBusy(false);
      }
    },
    []
  );

  // 首屏：浏览全部研究文档
  useEffect(() => {
    runSearch("", "auto", null, EMPTY_ADV);
  }, [runSearch]);

  // 右侧相关推荐：以结果首条为种子（无种子时回退到当前查询）
  useEffect(() => {
    if (items.length === 0) {
      setRec(null);
      return;
    }
    const myId = reqId.current;
    setRecBusy(true);
    api.research
      .recommend({ doc_id: items[0].id, limit: 6 })
      .then((r) => {
        if (myId === reqId.current) setRec(r);
      })
      .catch(() => {
        if (myId === reqId.current) setRec(null);
      })
      .finally(() => {
        if (myId === reqId.current) setRecBusy(false);
      });
  }, [items]);

  const submit = (query?: string) => {
    const term = (query ?? q).trim();
    setQ(term);
    runSearch(term, searchMode, categoryKey, adv);
  };

  const selectCategory = (key: string | null) => {
    setCategoryKey(key);
    runSearch(q.trim(), searchMode, key, adv);
  };

  const applyAdv = () => {
    setAdvOpen(false);
    runSearch(q.trim(), searchMode, categoryKey, adv);
  };

  const resetAll = () => {
    setQ("");
    setCategoryKey(null);
    setAdv(EMPTY_ADV);
    runSearch("", "auto", null, EMPTY_ADV);
  };

  const activeFilterCount =
    (categoryKey ? 1 : 0) +
    (adv.level || adv.region || adv.issuing_authority || adv.is_current || adv.publish_from || adv.publish_to ? 1 : 0);

  return (
    <AppShell>
      {/* 标题 + 检索框 */}
      <div className="mb-6">
        <div className="flex items-center gap-2">
          <BookOpen className="h-6 w-6 text-brand-500" />
          <h1 className="text-2xl font-bold">法律研究中心</h1>
        </div>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          跨法律 / 行政法规 / 司法解释 / 案例 / 规章 / 地方性法规 / 办事指南 / 政策文件的一站式检索与研究平台。
        </p>

        <form
          className="mt-4 flex flex-col gap-3 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="全文 / 语义检索，支持 AND OR NOT 布尔，例如：合同 AND 格式条款"
              className="pl-11"
            />
          </div>
          <Button type="submit" disabled={busy}>
            {busy && items.length === 0 ? <Spinner /> : "检索"}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => setAdvOpen((v) => !v)}
            className="relative"
          >
            <SlidersHorizontal className="h-4 w-4" />
            高级
            {activeFilterCount > 0 && (
              <span className="ml-1 rounded-full bg-brand-500 px-1.5 text-xs text-white">
                {activeFilterCount}
              </span>
            )}
          </Button>
        </form>

        {/* 检索模式 */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-xs text-gray-400">检索模式：</span>
          <div className="flex gap-1 rounded-xl bg-gray-100 p-1 dark:bg-white/5">
            {researchSearchModes.map((m) => (
              <button
                key={m.value}
                type="button"
                onClick={() => {
                  setSearchMode(m.value);
                  runSearch(q.trim(), m.value, categoryKey, adv);
                }}
                className={`rounded-lg px-3 py-1 text-xs transition ${
                  searchMode === m.value
                    ? "bg-white font-medium shadow-sm dark:bg-white/15"
                    : "text-gray-500 hover:text-gray-900 dark:text-gray-400"
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
          <span className="text-xs text-gray-400">
            热门：
            {researchHotQueries.map((h) => (
              <button
                key={h}
                type="button"
                onClick={() => submit(h)}
                className="ml-1 rounded-full border border-gray-200 px-2.5 py-0.5 text-xs text-gray-500 transition hover:border-brand-400 hover:text-brand-600 dark:border-white/10"
              >
                {h}
              </button>
            ))}
          </span>
        </div>

        {/* 高级过滤面板 */}
        {advOpen && (
          <Card className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs text-gray-400">效力层级</label>
              <Input
                value={adv.level}
                onChange={(e) => setAdv({ ...adv, level: e.target.value })}
                placeholder="如：法律 / 行政法规"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">地区</label>
              <Input
                value={adv.region}
                onChange={(e) => setAdv({ ...adv, region: e.target.value })}
                placeholder="如：北京市"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">发文机关</label>
              <Input
                value={adv.issuing_authority}
                onChange={(e) => setAdv({ ...adv, issuing_authority: e.target.value })}
                placeholder="如：最高人民法院"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">时效性</label>
              <select
                value={adv.is_current}
                onChange={(e) => setAdv({ ...adv, is_current: e.target.value })}
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
              >
                <option value="">不限</option>
                <option value="true">现行有效</option>
                <option value="false">已失效 / 未施行</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">发布日期起</label>
              <Input
                type="date"
                value={adv.publish_from}
                onChange={(e) => setAdv({ ...adv, publish_from: e.target.value })}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-400">发布日期止</label>
              <Input
                type="date"
                value={adv.publish_to}
                onChange={(e) => setAdv({ ...adv, publish_to: e.target.value })}
              />
            </div>
            <div className="flex items-end gap-2 sm:col-span-2 lg:col-span-3">
              <Button type="button" onClick={applyAdv} disabled={busy}>
                应用过滤
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setAdv(EMPTY_ADV);
                  runSearch(q.trim(), searchMode, categoryKey, EMPTY_ADV);
                }}
              >
                清空
              </Button>
            </div>
          </Card>
        )}
      </div>

      {/* 三栏 */}
      <div className="grid gap-6 lg:grid-cols-[200px_1fr_280px]">
        {/* 左：资源分类 */}
        <aside className="lg:sticky lg:top-20 lg:self-start">
          <Card className="space-y-1 p-3">
            <div className="px-2 pb-1 text-xs font-semibold text-gray-400">资源分类</div>
            <button
              type="button"
              onClick={() => selectCategory(null)}
              className={`block w-full rounded-lg px-3 py-1.5 text-left text-sm transition ${
                categoryKey === null
                  ? "bg-gray-100 font-medium dark:bg-white/10"
                  : "text-gray-500 hover:text-gray-900 dark:text-gray-400"
              }`}
            >
              全部
            </button>
            {researchCategories.map((c) => (
              <button
                key={c.key}
                type="button"
                onClick={() => selectCategory(c.key)}
                className={`block w-full rounded-lg px-3 py-1.5 text-left text-sm transition ${
                  categoryKey === c.key
                    ? "bg-gray-100 font-medium dark:bg-white/10"
                    : "text-gray-500 hover:text-gray-900 dark:text-gray-400"
                }`}
              >
                {c.label}
              </button>
            ))}
          </Card>
        </aside>

        {/* 中：结果 */}
        <section>
          {/* 分类 facets */}
          {facets && Object.keys(facets).length > 0 && (
            <div className="mb-3 flex flex-wrap gap-2">
              {Object.entries(facets).map(([key, f]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => {
                    const def = researchCategories.find((c) => c.category === key);
                    selectCategory(def ? def.key : null);
                  }}
                  className="rounded-full border border-gray-200 px-3 py-1 text-xs text-gray-500 transition hover:border-brand-400 hover:text-brand-600 dark:border-white/10"
                >
                  {f.label} · {f.count}
                </button>
              ))}
            </div>
          )}

          {busy && items.length === 0 ? (
            <div className="flex justify-center py-20">
              <Spinner />
            </div>
          ) : !searched ? (
            <Card className="py-16 text-center text-gray-400">输入关键词或选择分类开始检索。</Card>
          ) : items.length === 0 ? (
            <Card className="py-16 text-center text-gray-500 dark:text-gray-400">
              没有找到与「{lastQuery || "当前筛选"}」相关的研究文档，换个说法或放宽条件试试。
            </Card>
          ) : (
            <div className="space-y-4">
              <div className="text-sm text-gray-400">
                共找到{" "}
                <span className="font-medium text-gray-700 dark:text-gray-200">{total}</span>{" "}
                份研究文档
              </div>

              {items.map((it) => (
                <Link key={it.id} href={`/research/${it.id}`}>
                  <Card className="h-full transition hover:-translate-y-0.5 hover:shadow-md">
                    <div className="flex flex-wrap items-center gap-2">
                      {it.category_label && (
                        <Badge tone={researchDocTypeTone[it.doc_type] ?? "gray"}>
                          {it.category_label}
                        </Badge>
                      )}
                      <span className="font-semibold">{it.title}</span>
                      {it.doc_number && (
                        <span className="text-xs text-gray-400">{it.doc_number}</span>
                      )}
                    </div>

                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-400">
                      {it.source && (
                        <span className="inline-flex items-center gap-1">
                          <Building2 className="h-3.5 w-3.5" />
                          {it.source}
                        </span>
                      )}
                      {it.region && (
                        <span className="inline-flex items-center gap-1">
                          <MapPin className="h-3.5 w-3.5" />
                          {it.region}
                        </span>
                      )}
                      {it.publish_date && (
                        <span className="inline-flex items-center gap-1">
                          <Calendar className="h-3.5 w-3.5" />
                          {it.publish_date}
                        </span>
                      )}
                      <Badge tone={it.is_current ? "green" : "gray"}>
                        {it.is_current ? "现行有效" : "已失效 / 未施行"}
                      </Badge>
                    </div>

                    {it.summary_one_line && (
                      <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
                        {it.summary_one_line}
                      </p>
                    )}

                    {it.snippet && (
                      <p
                        className="mt-1 line-clamp-2 text-sm text-gray-500 dark:text-gray-400"
                        dangerouslySetInnerHTML={{ __html: sanitizeMarks(it.snippet) }}
                      />
                    )}

                    {it.keywords && it.keywords.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {it.keywords.slice(0, 6).map((k) => (
                          <span
                            key={k}
                            className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500 dark:bg-white/10 dark:text-gray-300"
                          >
                            <Tag className="h-3 w-3" />
                            {k}
                          </span>
                        ))}
                      </div>
                    )}
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </section>

        {/* 右：AI 摘要 + 相关推荐 */}
        <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          <Card>
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Sparkles className="h-4 w-4 text-brand-500" />
              AI 研究助手
            </div>
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              接入大模型后，将自动为每份文档生成「通俗解读」与「一句话摘要」，并在此处给出检索概览。
            </p>
            <div className="mt-3 rounded-xl bg-gray-50 p-3 text-xs text-gray-500 dark:bg-white/5">
              当前检索：<span className="font-medium text-gray-700 dark:text-gray-200">{lastQuery || "全部文档"}</span>
              <br />
              命中：<span className="font-medium text-gray-700 dark:text-gray-200">{total}</span> 份
            </div>
          </Card>

          <Card>
            <div className="flex items-center gap-2 text-sm font-semibold">
              <FileText className="h-4 w-4 text-brand-500" />
              相关推荐
            </div>
            {recBusy ? (
              <div className="flex justify-center py-6">
                <Spinner />
              </div>
            ) : rec && rec.items.length > 0 ? (
              <ul className="mt-3 space-y-2">
                {rec.items.map((it) => (
                  <li key={it.id}>
                    <Link
                      href={`/research/${it.id}`}
                      className="group flex items-start gap-2 rounded-lg p-2 transition hover:bg-gray-50 dark:hover:bg-white/5"
                    >
                      <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-gray-300 group-hover:text-brand-500" />
                      <span>
                        <span className="block text-sm text-gray-700 group-hover:text-brand-600 dark:text-gray-200">
                          {it.title}
                        </span>
                        {it.category_label && (
                          <span className="text-xs text-gray-400">{it.category_label}</span>
                        )}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-xs text-gray-400">
                暂无推荐。选择一份文档查看更精准的关联阅读。
              </p>
            )}
          </Card>

          {(categoryKey || activeFilterCount > 0) && (
            <Button variant="ghost" size="sm" onClick={resetAll} className="w-full">
              <X className="h-4 w-4" />
              重置检索
            </Button>
          )}
        </aside>
      </div>
    </AppShell>
  );
}
