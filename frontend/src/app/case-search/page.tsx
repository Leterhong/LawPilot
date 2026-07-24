// 案例智能搜索页（Legal Case Search 模块）。
// 关键词 / 语义 / 条件过滤（省份 / 法院级别 / 案件类型 / 时间范围）三合一检索。
// 接口公开，无需登录即可使用（知网 / Google Scholar 风格）。
"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Scale, Search, MapPin, Gavel } from "lucide-react";
import api, {
  type CaseFilterFacets,
  type LegalCaseSearchItem,
} from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { Badge, Button, Card, Input, Spinner } from "@/components/ui";
import {
  courtLevelLabels,
  legalCaseTypeLabels,
  legalCaseTypeTone,
} from "@/lib/constants";

const PAGE_SIZE = 10;

// 仅允许后端返回的 <mark> 标签，其余全部转义，避免高亮注入脚本。
function sanitizeMarks(html: string): string {
  const escaped = html
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return escaped
    .replace(/&lt;mark&gt;/g, "<mark>")
    .replace(/&lt;\/mark&gt;/g, "</mark>");
}

// 热门案例（规范指定）
const HOT_CASES = [
  "房屋租赁纠纷",
  "劳动仲裁",
  "合同违约",
  "消费欺诈",
  "借贷纠纷",
];

interface Filters {
  province: string;
  court_level: string;
  case_type: string;
  time_range: string;
}

const EMPTY_FILTERS: Filters = {
  province: "",
  court_level: "",
  case_type: "",
  time_range: "",
};

export default function CaseSearchPage() {
  const [q, setQ] = useState("");
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [facets, setFacets] = useState<CaseFilterFacets | null>(null);

  const [items, setItems] = useState<LegalCaseSearchItem[]>([]);
  const [total, setTotal] = useState(0);
  const [searched, setSearched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [offset, setOffset] = useState(0);
  const [lastQuery, setLastQuery] = useState("");
  const [lastFilters, setLastFilters] = useState<Filters>(EMPTY_FILTERS);

  // 载入过滤面（省份 / 法院级别 / 案件类型 / 时间范围）
  useEffect(() => {
    api.legalCase
      .filter()
      .then(setFacets)
      .catch(() => setFacets(null));
  }, []);

  const runSearch = useCallback(
    async (query: string, f: Filters, nextOffset: number, append: boolean) => {
      const term = query.trim();
      if (!term) return;
      setBusy(true);
      try {
        const res = await api.legalCase.search(term, {
          province: f.province || undefined,
          court_level: f.court_level || undefined,
          case_type: f.case_type || undefined,
          time_range: f.time_range || undefined,
          limit: PAGE_SIZE,
          offset: nextOffset,
        });
        setTotal(res.total);
        setItems((prev) => (append ? [...prev, ...res.items] : res.items));
        if (!append) {
          setSearched(true);
          setLastQuery(term);
          setLastFilters(f);
        }
      } catch {
        if (!append) setItems([]);
      } finally {
        setBusy(false);
      }
    },
    []
  );

  const submit = (query?: string, f?: Filters) => {
    const term = (query ?? q).trim();
    if (!term) return;
    const useFilters = f ?? filters;
    setQ(term);
    setOffset(0);
    runSearch(term, useFilters, 0, false);
  };

  // 修改过滤条件后，若已搜索则立即重新检索
  const changeFilter = (key: keyof Filters, value: string) => {
    const next = { ...filters, [key]: value };
    setFilters(next);
    if (searched && lastQuery) {
      setOffset(0);
      runSearch(lastQuery, next, 0, false);
    }
  };

  const resetFilters = () => {
    setFilters(EMPTY_FILTERS);
    if (searched && lastQuery) {
      setOffset(0);
      runSearch(lastQuery, EMPTY_FILTERS, 0, false);
    }
  };

  const loadMore = () => {
    const next = offset + PAGE_SIZE;
    setOffset(next);
    runSearch(lastQuery, lastFilters, next, true);
  };

  const hasMore = items.length < total;
  const hasActiveFilter =
    filters.province || filters.court_level || filters.case_type || filters.time_range;

  const selectClass =
    "w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm dark:border-white/10 dark:bg-white/5";

  return (
    <AppShell>
      {/* 标题 + 搜索框 */}
      <div className="mb-6">
        <div className="flex items-center gap-2">
          <Scale className="h-6 w-6 text-brand-500" />
          <h1 className="text-2xl font-bold">案例智能搜索</h1>
        </div>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          检索真实裁判文书，支持关键词、语义与条件过滤，辅助判断案件走向与赔偿参考。
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
              placeholder="搜索案例，例如：押金不退、违法辞退、买到假货"
              className="pl-11"
            />
          </div>
          <Button type="submit" disabled={busy || !q.trim()}>
            {busy && items.length === 0 ? <Spinner /> : "搜索"}
          </Button>
        </form>

        {/* 热门案例 */}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-xs text-gray-400">热门案例：</span>
          {HOT_CASES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => submit(ex)}
              className="rounded-full border border-gray-200 px-3 py-1 text-xs text-gray-500 transition hover:border-brand-400 hover:text-brand-600 dark:border-white/10"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {/* 两栏：左过滤 + 右结果 */}
      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        {/* 过滤面板 */}
        <aside className="lg:sticky lg:top-20 lg:self-start">
          <Card className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold">筛选条件</span>
              {hasActiveFilter && (
                <button
                  type="button"
                  onClick={resetFilters}
                  className="text-xs text-brand-600 hover:underline"
                >
                  重置
                </button>
              )}
            </div>

            <div>
              <label className="mb-1 block text-xs text-gray-400">案件类型</label>
              <select
                value={filters.case_type}
                onChange={(e) => changeFilter("case_type", e.target.value)}
                className={selectClass}
              >
                <option value="">全部类型</option>
                {(facets?.case_types ?? []).map((it) => (
                  <option key={it.value} value={it.value}>
                    {it.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs text-gray-400">法院级别</label>
              <select
                value={filters.court_level}
                onChange={(e) => changeFilter("court_level", e.target.value)}
                className={selectClass}
              >
                <option value="">全部级别</option>
                {(facets?.court_levels ?? []).map((it) => (
                  <option key={it.value} value={it.value}>
                    {it.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs text-gray-400">地区（省份）</label>
              <select
                value={filters.province}
                onChange={(e) => changeFilter("province", e.target.value)}
                className={selectClass}
              >
                <option value="">全部地区</option>
                {(facets?.provinces ?? []).map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-1 block text-xs text-gray-400">审理时间</label>
              <select
                value={filters.time_range}
                onChange={(e) => changeFilter("time_range", e.target.value)}
                className={selectClass}
              >
                <option value="">全部时间</option>
                {(facets?.time_ranges ?? []).map((it) => (
                  <option key={it.value} value={it.value}>
                    {it.label}
                  </option>
                ))}
              </select>
            </div>
          </Card>
        </aside>

        {/* 结果区 */}
        <section>
          {busy && items.length === 0 ? (
            <div className="flex justify-center py-20">
              <Spinner />
            </div>
          ) : searched && items.length === 0 ? (
            <Card className="py-16 text-center text-gray-500 dark:text-gray-400">
              没有找到与「{lastQuery}」相关的案例，换个说法或放宽筛选条件试试。
            </Card>
          ) : !searched ? (
            <Card className="py-16 text-center text-gray-400">
              输入关键词或点击上方热门案例开始检索。
            </Card>
          ) : (
            <div className="space-y-4">
              <div className="text-sm text-gray-400">
                共找到{" "}
                <span className="font-medium text-gray-700 dark:text-gray-200">
                  {total}
                </span>{" "}
                个相关案例
              </div>

              {items.map((it) => (
                <Link key={it.id} href={`/case-search/${it.id}`}>
                  <Card className="h-full transition hover:-translate-y-0.5 hover:shadow-md">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold">{it.title}</span>
                      <Badge tone={legalCaseTypeTone[it.case_type] ?? "gray"}>
                        {legalCaseTypeLabels[it.case_type] ?? it.case_type}
                      </Badge>
                      {it.court_level && (
                        <Badge tone="gray">
                          {courtLevelLabels[it.court_level] ?? it.court_level}
                        </Badge>
                      )}
                    </div>

                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-400">
                      {it.court && (
                        <span className="inline-flex items-center gap-1">
                          <Gavel className="h-3.5 w-3.5" />
                          {it.court}
                        </span>
                      )}
                      {(it.province || it.city) && (
                        <span className="inline-flex items-center gap-1">
                          <MapPin className="h-3.5 w-3.5" />
                          {[it.province, it.city].filter(Boolean).join(" · ")}
                        </span>
                      )}
                      {it.case_number && <span>{it.case_number}</span>}
                      {it.trial_date && <span>{it.trial_date}</span>}
                    </div>

                    <p
                      className="mt-2 line-clamp-3 text-sm text-gray-600 dark:text-gray-300"
                      dangerouslySetInnerHTML={{
                        __html: sanitizeMarks(
                          it.snippet || it.cause_of_action || it.title
                        ),
                      }}
                    />

                    {(it.winner || it.compensation) && (
                      <div className="mt-3 flex flex-wrap gap-2 text-xs">
                        {it.winner && (
                          <Badge tone="green">胜诉方：{it.winner}</Badge>
                        )}
                        {it.compensation && (
                          <Badge tone="amber">赔偿：{it.compensation}</Badge>
                        )}
                      </div>
                    )}

                    {it.keywords && it.keywords.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {it.keywords.slice(0, 6).map((k) => (
                          <span
                            key={k}
                            className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500 dark:bg-white/10 dark:text-gray-300"
                          >
                            {k}
                          </span>
                        ))}
                      </div>
                    )}
                  </Card>
                </Link>
              ))}

              {hasMore && (
                <div className="flex justify-center pt-2">
                  <Button variant="outline" onClick={loadMore} disabled={busy}>
                    {busy ? <Spinner /> : "加载更多"}
                  </Button>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}
