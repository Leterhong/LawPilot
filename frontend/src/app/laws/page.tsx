// 法律搜索页（Law Search 模块）：关键词 / 法律名 / 条款号检索。
// 接口公开，无需登录即可使用；登录用户会被后端记入搜索历史。
"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import api, { type LawSearchItem, type LawSearchResult } from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { Badge, Button, Card, Input, Spinner } from "@/components/ui";
import { lawStatusLabels } from "@/lib/constants";

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

const EXAMPLES = ["劳动合同", "租房押金", "离婚财产分割", "民间借贷", "消费者权益"];

export default function LawsPage() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [items, setItems] = useState<LawSearchItem[]>([]);
  const [total, setTotal] = useState(0);
  const [parsed, setParsed] = useState<LawSearchResult["parsed"]>(null);
  const [searched, setSearched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [offset, setOffset] = useState(0);
  const [lastQuery, setLastQuery] = useState("");
  const [lastStatus, setLastStatus] = useState("");

  const runSearch = useCallback(
    async (query: string, st: string, nextOffset: number, append: boolean) => {
      const term = query.trim();
      if (!term) return;
      setBusy(true);
      try {
        const res = await api.lawSearch(term, {
          status: st || undefined,
          limit: PAGE_SIZE,
          offset: nextOffset,
        });
        setParsed(res.parsed);
        setTotal(res.total);
        setItems((prev) => (append ? [...prev, ...res.items] : res.items));
        if (!append) {
          setSearched(true);
          setLastQuery(term);
          setLastStatus(st);
        }
      } catch {
        if (!append) setItems([]);
      } finally {
        setBusy(false);
      }
    },
    []
  );

  const submit = (query?: string) => {
    const term = (query ?? q).trim();
    if (!term) return;
    setQ(term);
    setOffset(0);
    runSearch(term, status, 0, false);
  };

  const loadMore = () => {
    const next = offset + PAGE_SIZE;
    setOffset(next);
    runSearch(lastQuery, lastStatus, next, true);
  };

  const hasMore = items.length < total;

  return (
    <AppShell>
      {/* 标题 + 搜索框 */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">法律搜索</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          支持法律名称、条款号（如「第38条」）、关键词或自然语言检索。
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
              placeholder="搜索法条，例如：劳动合同 第38条"
              className="pl-11"
            />
          </div>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded-xl border border-gray-200 bg-white px-3 py-2.5 text-sm dark:border-white/10 dark:bg-white/5"
          >
            <option value="">全部状态</option>
            <option value="effective">现行有效</option>
            <option value="amended">已被修正</option>
            <option value="repealed">已废止</option>
            <option value="pending">尚未施行</option>
          </select>
          <Button type="submit" disabled={busy || !q.trim()}>
            {busy ? <Spinner /> : "搜索"}
          </Button>
        </form>

        {!searched && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-xs text-gray-400">试试：</span>
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                onClick={() => submit(ex)}
                className="rounded-full border border-gray-200 px-3 py-1 text-xs text-gray-500 transition hover:border-brand-400 hover:text-brand-600 dark:border-white/10"
              >
                {ex}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 解析提示 */}
      {searched && parsed && (parsed.law_name || parsed.article) && (
        <div className="mb-4 flex flex-wrap gap-2 text-xs text-gray-500 dark:text-gray-400">
          <span>识别到：</span>
          {parsed.law_name && (
            <Badge tone="brand">法律《{parsed.law_name}》</Badge>
          )}
          {parsed.article && <Badge tone="brand">{parsed.article}</Badge>}
          {parsed.terms && parsed.terms.length > 0 && (
            <span className="self-center">
              关键词：{parsed.terms.join("、")}
            </span>
          )}
        </div>
      )}

      {/* 结果区 */}
      {busy && items.length === 0 ? (
        <div className="flex justify-center py-20">
          <Spinner />
        </div>
      ) : searched && items.length === 0 ? (
        <Card className="py-16 text-center text-gray-500 dark:text-gray-400">
          没有找到与「{lastQuery}」相关的法条，换个说法试试。
        </Card>
      ) : (
        items.length > 0 && (
          <div className="space-y-4">
            <div className="text-sm text-gray-400">
              共找到 <span className="font-medium text-gray-700 dark:text-gray-200">{total}</span> 条结果
            </div>
            {items.map((it) => (
              <Link key={it.id} href={`/laws/${it.id}`}>
                <Card className="h-full transition hover:-translate-y-0.5 hover:shadow-md">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold">{it.law_name}</span>
                    {it.article && (
                      <Badge tone="gray">{it.article}</Badge>
                    )}
                    <Badge tone={it.status === "effective" ? "green" : "amber"}>
                      {lawStatusLabels[it.status] ?? it.status}
                    </Badge>
                  </div>
                  {it.chapter && (
                    <div className="mt-1 text-xs text-gray-400">{it.chapter}</div>
                  )}
                  <p
                    className="mt-2 line-clamp-3 text-sm text-gray-600 dark:text-gray-300"
                    dangerouslySetInnerHTML={{
                      __html: sanitizeMarks(it.snippet || it.content),
                    }}
                  />
                  {it.keywords && it.keywords.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {it.keywords.map((k) => (
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
        )
      )}
    </AppShell>
  );
}
