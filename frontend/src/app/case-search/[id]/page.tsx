// 案例详情页（Legal Case Search 模块）。
// 案件事实 / 法院观点 / 裁判结果（胜诉方 + 赔偿）/ 相关法律（可链 /laws/{id}）/ AI 总结（第四步生成）。
// 操作：收藏案例 / 复制引用 / 分享 / 加入案件。search/detail 公开；收藏与加入案件需登录。
"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Scale,
  Gavel,
  BookOpen,
  FileText,
  Star,
  Share2,
  Copy,
  FolderPlus,
  Sparkles,
} from "lucide-react";
import api, {
  type LegalCaseDetail as LegalCaseDetailT,
  type CaseCenterOut,
} from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { Badge, Button, Card, Spinner } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import {
  courtLevelLabels,
  legalCaseTypeLabels,
  legalCaseTypeTone,
} from "@/lib/constants";

export default function CaseDetailPage({ params }: { params: { id: string } }) {
  const caseId = params.id;
  const { user } = useAuth();

  const [detail, setDetail] = useState<LegalCaseDetailT | null>(null);
  const [busy, setBusy] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const [fav, setFav] = useState(false);
  const [favBusy, setFavBusy] = useState(false);
  const [toast, setToast] = useState("");

  // 加入案件
  const [cases, setCases] = useState<CaseCenterOut[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [joinBusy, setJoinBusy] = useState(false);

  const flash = useCallback((msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(""), 2200);
  }, []);

  // 载入详情
  useEffect(() => {
    let alive = true;
    setBusy(true);
    setNotFound(false);
    setDetail(null);
    api.legalCase
      .detail(caseId)
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
  }, [caseId]);

  // 登录用户：判断是否已收藏
  useEffect(() => {
    if (!user) {
      setFav(false);
      return;
    }
    let alive = true;
    api.legalCase
      .favorites()
      .then((res) => {
        if (alive) setFav(res.items.some((it) => it.id === caseId));
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [user, caseId]);

  const toggleFav = async () => {
    if (!user) {
      flash("请先登录后再收藏");
      return;
    }
    setFavBusy(true);
    try {
      if (fav) {
        await api.legalCase.removeFavorite(caseId);
        setFav(false);
        flash("已取消收藏");
      } else {
        await api.legalCase.addFavorite(caseId);
        setFav(true);
        flash("已加入收藏");
      }
    } catch {
      flash("操作失败，请重试");
    } finally {
      setFavBusy(false);
    }
  };

  // 复制规范引用格式
  const copyCitation = async () => {
    if (!detail) return;
    const parts = [
      detail.court,
      detail.title,
      detail.case_number,
      detail.trial_date,
    ].filter(Boolean);
    const citation = parts.join("，") + "。";
    try {
      await navigator.clipboard.writeText(citation);
      flash("引用已复制");
    } catch {
      flash("复制失败");
    }
  };

  const share = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      flash("链接已复制");
    } catch {
      flash("复制失败");
    }
  };

  // 打开加入案件选择器：拉取用户案件
  const openPicker = async () => {
    if (!user) {
      flash("请先登录后再加入案件");
      return;
    }
    setPickerOpen((v) => !v);
    if (cases.length === 0) {
      try {
        const page = await api.caseCenter.list({ page_size: 50 });
        setCases(page.items);
      } catch {
        flash("无法加载案件列表");
      }
    }
  };

  const joinCase = async (targetId: string) => {
    if (!detail) return;
    setJoinBusy(true);
    try {
      const url = typeof window !== "undefined" ? window.location.href : "";
      const lines = [
        `参考案例：${detail.title}`,
        detail.court ? `法院：${detail.court}` : "",
        detail.winner ? `胜诉方：${detail.winner}` : "",
        detail.compensation ? `赔偿：${detail.compensation}` : "",
        url ? `链接：${url}` : "",
      ].filter(Boolean);
      await api.caseCenter.addNote(targetId, { content: lines.join("\n") });
      setPickerOpen(false);
      flash("已加入该案件的备注");
    } catch {
      flash("加入失败，请重试");
    } finally {
      setJoinBusy(false);
    }
  };

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
          未找到该案例。
          <Link
            href="/case-search"
            className="mx-1 text-brand-600 hover:underline"
          >
            返回案例搜索
          </Link>
        </div>
      </AppShell>
    );
  }

  const ai = detail.ai_summary;

  return (
    <AppShell>
      <Link
        href="/case-search"
        className="text-sm text-gray-400 hover:text-gray-600"
      >
        ← 返回案例搜索
      </Link>

      {/* 头部 */}
      <div className="mt-3">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-bold">{detail.title}</h1>
          <Badge tone={legalCaseTypeTone[detail.case_type] ?? "gray"}>
            {legalCaseTypeLabels[detail.case_type] ?? detail.case_type}
          </Badge>
          {detail.court_level && (
            <Badge tone="gray">
              {courtLevelLabels[detail.court_level] ?? detail.court_level}
            </Badge>
          )}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-400">
          {detail.court && (
            <span className="inline-flex items-center gap-1">
              <Gavel className="h-4 w-4" />
              {detail.court}
            </span>
          )}
          {detail.case_number && <span>{detail.case_number}</span>}
          {detail.cause_of_action && <span>案由：{detail.cause_of_action}</span>}
          {detail.trial_date && <span>审理日期：{detail.trial_date}</span>}
          {(detail.province || detail.city) && (
            <span>{[detail.province, detail.city].filter(Boolean).join(" · ")}</span>
          )}
          {detail.source && <span>来源：{detail.source}</span>}
        </div>

        {/* 当事人 */}
        {(detail.plaintiff || detail.defendant) && (
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            {detail.plaintiff && (
              <Badge tone="brand">原告：{detail.plaintiff}</Badge>
            )}
            {detail.defendant && (
              <Badge tone="gray">被告：{detail.defendant}</Badge>
            )}
          </div>
        )}
      </div>

      {/* 操作栏 */}
      <div className="relative mt-4 flex flex-wrap gap-2">
        <Button
          variant={fav ? "primary" : "outline"}
          size="sm"
          onClick={toggleFav}
          disabled={favBusy}
        >
          {favBusy ? (
            <Spinner />
          ) : (
            <Star className={fav ? "h-4 w-4 fill-current" : "h-4 w-4"} />
          )}
          {fav ? "已收藏" : "收藏案例"}
        </Button>
        <Button variant="outline" size="sm" onClick={openPicker}>
          <FolderPlus className="h-4 w-4" />
          加入案件
        </Button>
        <Button variant="outline" size="sm" onClick={copyCitation}>
          <Copy className="h-4 w-4" />
          复制引用
        </Button>
        <Button variant="outline" size="sm" onClick={share}>
          <Share2 className="h-4 w-4" />
          分享
        </Button>

        {toast && (
          <span className="self-center rounded-lg bg-gray-900 px-3 py-1 text-xs text-white dark:bg-white dark:text-gray-900">
            {toast}
          </span>
        )}

        {/* 加入案件下拉 */}
        {pickerOpen && (
          <div className="absolute left-0 top-11 z-10 w-72 rounded-xl border border-gray-100 bg-white p-2 shadow-soft dark:border-white/10 dark:bg-[#12151c]">
            <div className="px-2 py-1 text-xs text-gray-400">选择要加入的案件</div>
            {cases.length === 0 ? (
              <div className="px-2 py-3 text-sm text-gray-400">
                暂无案件，先到「我的案件」创建。
              </div>
            ) : (
              <div className="max-h-64 space-y-1 overflow-auto">
                {cases.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    disabled={joinBusy}
                    onClick={() => joinCase(c.id)}
                    className="block w-full truncate rounded-lg px-2 py-1.5 text-left text-sm hover:bg-gray-100 disabled:opacity-50 dark:hover:bg-white/10"
                  >
                    {c.title}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 裁判结果概览 */}
      {(detail.winner || detail.compensation) && (
        <Card className="mt-4 bg-brand-50/50 dark:bg-brand-500/10">
          <div className="flex flex-wrap items-center gap-3">
            {detail.winner && (
              <div className="text-sm">
                <span className="text-gray-400">胜诉方：</span>
                <span className="font-semibold text-green-700 dark:text-green-300">
                  {detail.winner}
                </span>
              </div>
            )}
            {detail.compensation && (
              <div className="text-sm">
                <span className="text-gray-400">赔偿金额：</span>
                <span className="font-semibold text-amber-700 dark:text-amber-300">
                  {detail.compensation}
                </span>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* 案件事实 */}
      {detail.facts && (
        <Section title="案件事实" icon={<FileText className="h-4 w-4" />}>
          <Card>
            <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-gray-800 dark:text-gray-200">
              {detail.facts}
            </p>
          </Card>
        </Section>
      )}

      {/* 法院观点 */}
      {detail.court_reasoning && (
        <Section title="法院观点" icon={<Gavel className="h-4 w-4" />}>
          <Card>
            <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-gray-800 dark:text-gray-200">
              {detail.court_reasoning}
            </p>
          </Card>
        </Section>
      )}

      {/* 裁判结果 */}
      {detail.judgement && (
        <Section title="裁判结果" icon={<Scale className="h-4 w-4" />}>
          <Card>
            <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-gray-800 dark:text-gray-200">
              {detail.judgement}
            </p>
          </Card>
        </Section>
      )}

      {/* 相关法律 */}
      {detail.related_laws.length > 0 && (
        <Section title="相关法律" icon={<BookOpen className="h-4 w-4" />}>
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

      {/* 原始法条引用（未能链到法律库时兜底展示） */}
      {detail.related_laws.length === 0 &&
        detail.related_law_citations &&
        detail.related_law_citations.length > 0 && (
          <Section title="相关法律" icon={<BookOpen className="h-4 w-4" />}>
            <div className="flex flex-wrap gap-2">
              {detail.related_law_citations.map((c) => (
                <Badge key={c} tone="brand">
                  {c}
                </Badge>
              ))}
            </div>
          </Section>
        )}

      {/* AI 总结 */}
      <Section title="AI 智能总结" icon={<Sparkles className="h-4 w-4" />}>
        <Card>
          {ai && (ai.similar_points || ai.different_points || ai.reference_value) ? (
            <div className="space-y-3 text-sm">
              {ai.reference_value && (
                <div>
                  <span className="text-gray-400">参考价值：</span>
                  <Badge tone="brand">{ai.reference_value}</Badge>
                </div>
              )}
              {ai.similar_points && (
                <div>
                  <div className="mb-1 font-medium text-gray-700 dark:text-gray-200">
                    相似点
                  </div>
                  <p className="whitespace-pre-wrap text-gray-600 dark:text-gray-300">
                    {ai.similar_points}
                  </p>
                </div>
              )}
              {ai.different_points && (
                <div>
                  <div className="mb-1 font-medium text-gray-700 dark:text-gray-200">
                    不同点
                  </div>
                  <p className="whitespace-pre-wrap text-gray-600 dark:text-gray-300">
                    {ai.different_points}
                  </p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-400">
              AI 相似度总结（相似点 / 不同点 / 参考价值）将在第四步「AI 案例关联」接入后生成。
              可先在「案件分析」中使用「查找类似案例」获取与你情形最接近的判例。
            </p>
          )}
        </Card>
      </Section>
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
