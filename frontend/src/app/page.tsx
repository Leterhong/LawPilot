// 首页：苹果风极简——超大输入框 + 四类快捷入口 + 最近案件。
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowRight, Banknote, Briefcase, Home, ShoppingBag } from "lucide-react";
import { useAuth } from "@/lib/auth";
import api, { type CaseOut, type CaseType } from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { Button, Card, Spinner } from "@/components/ui";
import { caseTypeLabels, quickEntries } from "@/lib/constants";

const iconMap = { home: Home, briefcase: Briefcase, shopping: ShoppingBag, banknote: Banknote };

export default function HomePage() {
  const { user } = useAuth();
  const router = useRouter();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [recent, setRecent] = useState<CaseOut[]>([]);
  const [loadingRecent, setLoadingRecent] = useState(false);

  useEffect(() => {
    if (user) {
      setLoadingRecent(true);
      api
        .listCases({ page: 1, page_size: 5 })
        .then((p) => setRecent(p.items))
        .catch(() => setRecent([]))
        .finally(() => setLoadingRecent(false));
    }
  }, [user]);

  const createCase = async (type: CaseType, title: string, description?: string) => {
    setBusy(true);
    try {
      const c = await api.createCase(title, type, description);
      router.push(`/cases/${c.id}`);
    } catch {
      setBusy(false);
    }
  };

  const submitText = async () => {
    if (!text.trim()) return;
    await createCase("other", text.trim().slice(0, 30), text.trim());
  };

  const onQuick = (type: CaseType, label: string) => createCase(type, label);

  return (
    <AppShell>
      <div className="grid flex-1 grid-cols-1 gap-10 lg:grid-cols-[1fr_320px]">
        {/* 左：主输入区 */}
        <section className="flex flex-col justify-center">
          <h1 className="mb-3 text-4xl font-bold tracking-tight sm:text-5xl">
            你的 AI 法律办事助手
          </h1>
          <p className="mb-8 max-w-xl text-lg text-gray-500 dark:text-gray-400">
            用一句话描述你的遭遇，LawPilot 陪你走完整个维权流程。
          </p>

          {user ? (
            <>
              <div className="relative">
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="请告诉我发生了什么。例如：老板拖欠工资 / 房东不退押金 / 朋友借钱不还…"
                  rows={4}
                  className="lp-input resize-none"
                />
                <Button
                  disabled={!text.trim() || busy}
                  onClick={submitText}
                  className="absolute bottom-4 right-4"
                >
                  {busy ? <Spinner /> : "开始分析"} <ArrowRight className="h-4 w-4" />
                </Button>
              </div>

              <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
                {quickEntries.map((e) => {
                  const Icon = iconMap[e.icon];
                  return (
                    <button
                      key={e.type}
                      disabled={busy}
                      onClick={() => onQuick(e.type, e.label)}
                      className="lp-quick text-left"
                    >
                      <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-500/15 dark:text-brand-300">
                        <Icon className="h-5 w-5" />
                      </span>
                      <span className="text-sm font-medium">{e.label}</span>
                      <span className="text-xs text-gray-400">{e.hint}</span>
                    </button>
                  );
                })}
              </div>
            </>
          ) : (
            <div className="rounded-2xl border border-gray-100 bg-white p-8 text-center shadow-soft dark:border-white/10 dark:bg-white/5">
              <p className="mb-4 text-gray-500 dark:text-gray-400">
                登录后即可创建案件，让 AI 陪你维权。
              </p>
              <div className="flex justify-center gap-3">
                <Link href="/login">
                  <Button variant="outline">登录</Button>
                </Link>
                <Link href="/register">
                  <Button>免费注册</Button>
                </Link>
              </div>
            </div>
          )}
        </section>

        {/* 右：最近案件 */}
        <aside className="hidden lg:block">
          <h2 className="mb-4 text-sm font-medium text-gray-400">最近案件</h2>
          {loadingRecent ? (
            <div className="flex justify-center py-10">
              <Spinner />
            </div>
          ) : recent.length === 0 ? (
            <p className="text-sm text-gray-400">暂无案件</p>
          ) : (
            <div className="space-y-3">
              {recent.map((c) => (
                <Link key={c.id} href={`/cases/${c.id}`}>
                  <Card className="transition hover:-translate-y-0.5 hover:shadow-md">
                    <div className="text-sm font-medium">{c.title}</div>
                    <div className="mt-1 flex items-center justify-between text-xs text-gray-400">
                      <span>{caseTypeLabels[c.case_type]}</span>
                    </div>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </aside>
      </div>

      <footer className="mt-12 text-center text-xs text-gray-400">
        本平台提供法律信息参考，不构成法律意见。
      </footer>
    </AppShell>
  );
}
