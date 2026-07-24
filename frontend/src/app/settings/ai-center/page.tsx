"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api, type AIMeta, type AIModelOut, type ProviderOut, type RoutingRuleOut, type PromptTemplateOut } from "@/lib/api";
import { aiCenterModules } from "@/lib/constants";
import { AppShell } from "@/components/AppShell";
import { Spinner } from "@/components/ui";
import { cn } from "@/lib/utils";

// 各能力中心面板按需懒加载：首次进入只编译轻量外壳，切到对应 Tab 时才加载该面板，
// 降低首屏编译模块数（dev 首屏）与首屏 JS 体积（生产）。
function PanelLoading({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center py-20 text-gray-400">
      <Spinner className="mr-2" /> {label}加载中…
    </div>
  );
}

const ModelsPanel = dynamic(
  () => import("@/components/ai-center/ModelsPanel").then((m) => ({ default: m.ModelsPanel })),
  { ssr: false, loading: () => <PanelLoading label="模型管理" /> }
);
const ProvidersPanel = dynamic(
  () => import("@/components/ai-center/ProvidersPanel").then((m) => ({ default: m.ProvidersPanel })),
  { ssr: false, loading: () => <PanelLoading label="Provider 管理" /> }
);
const RoutingPanel = dynamic(
  () => import("@/components/ai-center/RoutingPanel").then((m) => ({ default: m.RoutingPanel })),
  { ssr: false, loading: () => <PanelLoading label="路由规则" /> }
);
const PromptsPanel = dynamic(
  () => import("@/components/ai-center/PromptsPanel").then((m) => ({ default: m.PromptsPanel })),
  { ssr: false, loading: () => <PanelLoading label="Prompt 模板" /> }
);
const StatsPanel = dynamic(
  () => import("@/components/ai-center/StatsPanel").then((m) => ({ default: m.StatsPanel })),
  { ssr: false, loading: () => <PanelLoading label="调用统计" /> }
);
const LogsPanel = dynamic(
  () => import("@/components/ai-center/LogsPanel").then((m) => ({ default: m.LogsPanel })),
  { ssr: false, loading: () => <PanelLoading label="调用日志" /> }
);
const HealthPanel = dynamic(
  () => import("@/components/ai-center/HealthPanel").then((m) => ({ default: m.HealthPanel })),
  { ssr: false, loading: () => <PanelLoading label="健康度" /> }
);

export default function AICenterPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [active, setActive] = useState("models");
  const [ready, setReady] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [meta, setMeta] = useState<AIMeta | null>(null);
  const [models, setModels] = useState<AIModelOut[]>([]);
  const [providers, setProviders] = useState<ProviderOut[]>([]);
  const [routing, setRouting] = useState<RoutingRuleOut[]>([]);
  const [prompts, setPrompts] = useState<PromptTemplateOut[]>([]);

  const load = useCallback(async () => {
    try {
      const [m, p, r, pr, mt] = await Promise.all([
        api.aiCenter.listModels(),
        api.aiCenter.listProviders(),
        api.aiCenter.listRouting(),
        api.aiCenter.listPrompts(),
        api.aiCenter.meta(),
      ]);
      setModels(m);
      setProviders(p);
      setRouting(r);
      setPrompts(pr);
      setMeta(mt);
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
    if (!user.is_superuser) {
      router.replace("/");
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
  if (!user?.is_superuser) {
    return (
      <AppShell>
        <div className="py-20 text-center text-gray-500">无访问权限：AI 能力中心仅对超级管理员开放。</div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="grid gap-6 md:grid-cols-[220px_1fr]">
        {/* 模块侧边栏 */}
        <aside className="h-fit rounded-2xl border border-gray-100 bg-white p-2 dark:border-white/10 dark:bg-white/5">
          <div className="px-3 py-2 text-xs font-medium uppercase tracking-wide text-gray-400">AI 能力中心</div>
          <nav className="space-y-1">
            {aiCenterModules.map((m) => (
              <button
                key={m.key}
                onClick={() => setActive(m.key)}
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

        {/* 内容区 */}
        <section className="min-w-0">
          {err && (
            <div className="mb-4 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/15 dark:text-red-300">
              {err}
            </div>
          )}
          {active === "models" && meta && (
            <ModelsPanel models={models} providers={providers} meta={meta} reload={load} />
          )}
          {active === "providers" && meta && (
            <ProvidersPanel providers={providers} meta={meta} reload={load} />
          )}
          {active === "routing" && meta && (
            <RoutingPanel routing={routing} models={models} meta={meta} reload={load} />
          )}
          {active === "prompts" && (
            <PromptsPanel prompts={prompts} models={models} reload={load} />
          )}
          {active === "stats" && <StatsPanel />}
          {active === "logs" && meta && <LogsPanel meta={meta} />}
          {active === "health" && <HealthPanel />}
        </section>
      </div>
    </AppShell>
  );
}
