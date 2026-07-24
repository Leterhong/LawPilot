// 法条详情页（Law Search 模块）：完整正文 + 上/下条 + 相关法条 + 司法解释/案例 + 推荐。
// 接口公开，无需登录。
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Scale, BookOpen, Gavel } from "lucide-react";
import api, { type LawDetail as LawDetailT } from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { Badge, Card, Spinner } from "@/components/ui";
import { lawStatusLabels } from "@/lib/constants";

export default function LawDetailPage({ params }: { params: { id: string } }) {
  const lawId = params.id;
  const [detail, setDetail] = useState<LawDetailT | null>(null);
  const [busy, setBusy] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let alive = true;
    setBusy(true);
    setNotFound(false);
    setDetail(null);
    api
      .lawDetail(lawId)
      .then((d) => {
        if (alive) setDetail(d);
      })
      .catch(() => {
        if (alive) setNotFound(true);
      })
      .finally(() => {
        if (alive) setBusy(false);
      });
    return () => {
      alive = false;
    };
  }, [lawId]);

  if (busy) {
    return (
      <AppShell>
        <div className="flex justify-center py-20">
          <Spinner />
        </div>
      </AppShell>
    );
  }

  if (notFound || !detail) {
    return (
      <AppShell>
        <div className="py-20 text-center text-gray-500 dark:text-gray-400">
          未找到该法条。
          <Link href="/laws" className="mx-1 text-brand-600 hover:underline">
            返回法律搜索
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <Link
        href="/laws"
        className="text-sm text-gray-400 hover:text-gray-600"
      >
        ← 返回法律搜索
      </Link>

      {/* 头部 */}
      <div className="mt-3">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-bold">{detail.law_name}</h1>
          <Badge tone={detail.status === "effective" ? "green" : "amber"}>
            {lawStatusLabels[detail.status] ?? detail.status}
          </Badge>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-400">
          {detail.article && <span>{detail.article}</span>}
          {detail.chapter && <span>{detail.chapter}</span>}
          {detail.section && <span>{detail.section}</span>}
          {detail.effective_date && <span>施行日期：{detail.effective_date}</span>}
          {detail.source && <span>来源：{detail.source}</span>}
        </div>
      </div>

      {/* 上/下条 */}
      {(detail.prev || detail.next) && (
        <div className="mt-4 flex gap-2">
          {detail.prev ? (
            <Link href={`/laws/${detail.prev.id}`} className="flex-1">
              <Card className="flex items-center gap-2 text-sm transition hover:shadow-md">
                <ArrowLeft className="h-4 w-4 flex-none text-gray-400" />
                <span className="truncate">
                  <span className="text-gray-400">上一条：</span>
                  {detail.prev.law_name} {detail.prev.article}
                </span>
              </Card>
            </Link>
          ) : (
            <div className="flex-1" />
          )}
          {detail.next && (
            <Link href={`/laws/${detail.next.id}`} className="flex-1">
              <Card className="flex items-center justify-end gap-2 text-sm transition hover:shadow-md">
                <span className="truncate text-right">
                  <span className="text-gray-400">下一条：</span>
                  {detail.next.law_name} {detail.next.article}
                </span>
                <ArrowRight className="h-4 w-4 flex-none text-gray-400" />
              </Card>
            </Link>
          )}
        </div>
      )}

      {/* 正文 */}
      <Card className="mt-4">
        <div className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-500 dark:text-gray-400">
          <Scale className="h-4 w-4" /> 法条正文
        </div>
        <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-gray-800 dark:text-gray-200">
          {detail.content}
        </p>
        {detail.keywords && detail.keywords.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-1.5">
            {detail.keywords.map((k) => (
              <span
                key={k}
                className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-500 dark:bg-white/10 dark:text-gray-300"
              >
                {k}
              </span>
            ))}
          </div>
        )}
        {/* 第四步：AI 通俗解释占位 */}
        {detail.ai_explanation ? (
          <div className="mt-4 rounded-xl bg-brand-50 p-3 text-sm text-brand-800 dark:bg-brand-500/10 dark:text-brand-200">
            {detail.ai_explanation}
          </div>
        ) : (
          <p className="mt-4 text-xs text-gray-400">
            （AI 通俗解释将在第四步语义检索接入后生成）
          </p>
        )}
      </Card>

      {/* 相关法条 */}
      {detail.related_laws.length > 0 && (
        <Section title="相关法条" icon={<BookOpen className="h-4 w-4" />}>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {detail.related_laws.map((r) => (
              <Link key={r.id} href={`/laws/${r.id}`}>
                <Card className="h-full transition hover:-translate-y-0.5 hover:shadow-md">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{r.law_name}</span>
                    {r.article && <Badge tone="gray">{r.article}</Badge>}
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm text-gray-500 dark:text-gray-400">
                    {r.content}
                  </p>
                </Card>
              </Link>
            ))}
          </div>
        </Section>
      )}

      {/* 司法解释 / 案例 */}
      {(detail.related_interpretations.length > 0 ||
        detail.related_cases.length > 0) && (
        <Section title="司法解释与案例" icon={<Gavel className="h-4 w-4" />}>
          {detail.related_interpretations.length > 0 && (
            <RefList
              title="司法解释"
              items={detail.related_interpretations}
              tone="brand"
            />
          )}
          {detail.related_cases.length > 0 && (
            <RefList title="参考案例" items={detail.related_cases} tone="amber" />
          )}
        </Section>
      )}

      {/* 推荐 */}
      {detail.recommendations.length > 0 && (
        <Section title="为你推荐">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {detail.recommendations.map((r) => (
              <Link key={r.id} href={`/laws/${r.id}`}>
                <Card className="h-full transition hover:-translate-y-0.5 hover:shadow-md">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{r.law_name}</span>
                    {r.article && <Badge tone="gray">{r.article}</Badge>}
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm text-gray-500 dark:text-gray-400">
                    {r.content}
                  </p>
                </Card>
              </Link>
            ))}
          </div>
        </Section>
      )}
    </AppShell>
  );
}

function Section({
  title,
  icon,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="mt-6">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-200">
        {icon}
        {title}
      </div>
      {children}
    </div>
  );
}

function RefList({
  title,
  items,
  tone,
}: {
  title: string;
  items: { id: string; source: string; title: string; article: string | null; snippet: string }[];
  tone: "brand" | "amber";
}) {
  return (
    <div className="mb-4">
      <div className="mb-2 text-xs font-medium text-gray-400">{title}</div>
      <div className="space-y-2">
        {items.map((it) => (
          <Card key={it.id} className="p-4">
            <div className="flex items-start gap-2">
              <Badge tone={tone}>{it.source}</Badge>
              <span className="font-medium">{it.title}</span>
              {it.article && (
                <span className="text-xs text-gray-400">{it.article}</span>
              )}
            </div>
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
              {it.snippet}
            </p>
          </Card>
        ))}
      </div>
    </div>
  );
}
