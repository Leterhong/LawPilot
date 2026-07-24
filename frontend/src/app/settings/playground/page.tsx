"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  api,
  type PlaygroundModelOut,
  type RoutingRuleSimpleOut,
  type EvaluationDatasetOut,
} from "@/lib/api";
import { playgroundModules } from "@/lib/constants";
import { AppShell } from "@/components/AppShell";
import { Spinner } from "@/components/ui";
import { cn } from "@/lib/utils";

// 各测试面板按需懒加载：首次进入只编译轻量外壳，切到对应 Tab 时才加载该面板，
// 大幅降低首屏编译模块数（dev 首屏）与首屏 JS 体积（生产）。
function PanelLoading({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center py-20 text-gray-400">
      <Spinner className="mr-2" /> {label}加载中…
    </div>
  );
}

const SingleTestPanel = dynamic(
  () => import("@/components/playground/SingleTestPanel").then((m) => ({ default: m.SingleTestPanel })),
  { ssr: false, loading: () => <PanelLoading label="单模型测试" /> }
);
const ComparePanel = dynamic(
  () => import("@/components/playground/ComparePanel").then((m) => ({ default: m.ComparePanel })),
  { ssr: false, loading: () => <PanelLoading label="多模型对比" /> }
);
const PromptTestPanel = dynamic(
  () => import("@/components/playground/PromptTestPanel").then((m) => ({ default: m.PromptTestPanel })),
  { ssr: false, loading: () => <PanelLoading label="Prompt 测试" /> }
);
const EvalPanel = dynamic(
  () => import("@/components/playground/EvalPanel").then((m) => ({ default: m.EvalPanel })),
  { ssr: false, loading: () => <PanelLoading label="模型评测" /> }
);
const RoutingTestPanel = dynamic(
  () => import("@/components/playground/RoutingTestPanel").then((m) => ({ default: m.RoutingTestPanel })),
  { ssr: false, loading: () => <PanelLoading label="AI 路由测试" /> }
);
const HistoryPanel = dynamic(
  () => import("@/components/playground/HistoryPanel").then((m) => ({ default: m.HistoryPanel })),
  { ssr: false, loading: () => <PanelLoading label="测试历史" /> }
);
const LibraryPanel = dynamic(
  () => import("@/components/playground/LibraryPanel").then((m) => ({ default: m.LibraryPanel })),
  { ssr: false, loading: () => <PanelLoading label="我的收藏" /> }
);

export default function PlaygroundPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [active, setActive] = useState("single");
  const [ready, setReady] = useState(false);

  const [models, setModels] = useState<PlaygroundModelOut[]>([]);
  const [routing, setRouting] = useState<RoutingRuleSimpleOut[]>([]);
  const [datasets, setDatasets] = useState<EvaluationDatasetOut[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [m, r, d] = await Promise.all([
        api.playground.listModels(),
        api.playground.routing(),
        api.playground.listDatasets(),
      ]);
      setModels(m);
      setRouting(r);
      setDatasets(d);
      setErr(null);
    } catch (e: any) {
      setErr(e.message || "加载失败");
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    load();
  }, [user, loading, router, load]);

  if (loading || !ready) {
    return (
      <AppShell>
        <div className="flex items-center justify-center py-20 text-gray-400">
          <Spinner className="mr-2" /> 加载中…
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="grid gap-6 md:grid-cols-[200px_1fr]">
        <aside className="h-fit rounded-2xl border border-gray-100 bg-white p-2 dark:border-white/10 dark:bg-white/5">
          <div className="px-3 py-2 text-xs font-medium uppercase tracking-wide text-gray-400">AI Playground</div>
          <nav className="space-y-1">
            {playgroundModules.map((m) => (
              <button
                key={m.key}
                onClick={() => setActive(m.key)}
                title={m.desc}
                className={cn(
                  "w-full rounded-xl px-3 py-2 text-left text-sm transition",
                  active === m.key
                    ? "bg-brand-50 font-medium text-brand-700 dark:bg-brand-500/15 dark:text-brand-300"
                    : "hover:bg-gray-100 dark:hover:bg-white/5"
                )}
              >
                {m.label}
              </button>
            ))}
          </nav>
        </aside>

        <section className="min-w-0">
          {err && (
            <div className="mb-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/15 dark:text-red-300">
              {err}
            </div>
          )}
          {active === "single" && <SingleTestPanel models={models} />}
          {active === "compare" && <ComparePanel models={models} />}
          {active === "prompt" && <PromptTestPanel models={models} />}
          {active === "eval" && <EvalPanel models={models} datasets={datasets} />}
          {active === "routing" && (
            <RoutingTestPanel
              models={models}
              routing={routing}
              isSuperuser={!!user?.is_superuser}
              onRoutingChange={load}
            />
          )}
          {active === "history" && <HistoryPanel />}
          {active === "library" && <LibraryPanel />}
        </section>
      </div>
    </AppShell>
  );
}
