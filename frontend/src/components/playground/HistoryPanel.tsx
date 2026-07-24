// 功能六：测试历史。
"use client";

import { useEffect, useState } from "react";
import { api, type PlaygroundSessionOut } from "@/lib/api";
import { Card, Badge, Button, Spinner } from "@/components/ui";

const TYPE_LABELS: Record<string, string> = {
  single: "单模型测试",
  compare: "多模型对比",
  prompt: "Prompt 测试",
  evaluate: "模型评测",
  routing: "AI 路由测试",
};

export function HistoryPanel() {
  const [items, setItems] = useState<PlaygroundSessionOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setItems(await api.playground.history({ limit: 100 }));
    } catch (e: any) {
      setError(e.message || "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <Card>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">测试历史</h2>
        <Button variant="outline" size="sm" onClick={load}>刷新</Button>
      </div>
      {loading && <div className="flex items-center text-sm text-gray-400"><Spinner className="mr-2" /> 加载中…</div>}
      {error && <div className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-500/15 dark:text-red-300">{error}</div>}
      {!loading && items.length === 0 && <div className="text-sm text-gray-400">暂无测试记录。</div>}

      <div className="space-y-2">
        {items.map((s) => {
          const tu = s.token_usage as { in?: number; out?: number; cost?: number | null } | null;
          const out = s.output as { content?: string } | null;
          const open = expanded === s.id;
          return (
            <div key={s.id} className="rounded-xl border border-gray-100 dark:border-white/10">
              <button
                className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left text-sm"
                onClick={() => setExpanded(open ? null : s.id)}
              >
                <div className="flex min-w-0 items-center gap-2">
                  <Badge tone="brand">{TYPE_LABELS[s.type] ?? s.type}</Badge>
                  <span className="truncate text-gray-500">{s.user_prompt ?? s.title ?? "(无输入)"}</span>
                </div>
                <div className="flex shrink-0 items-center gap-3 text-xs text-gray-400">
                  {s.score != null && <span>评分 {s.score.toFixed(1)}</span>}
                  <span>{s.latency_ms}ms</span>
                  <span>{new Date(s.created_at).toLocaleString()}</span>
                </div>
              </button>
              {open && (
                <div className="border-t border-gray-100 px-3 py-3 dark:border-white/10">
                  <div className="grid grid-cols-3 gap-2 text-xs text-gray-500">
                    <span>输入 Token：{tu?.in ?? 0}</span>
                    <span>输出 Token：{tu?.out ?? 0}</span>
                    <span>成本：{tu?.cost != null ? `$${tu.cost.toFixed(5)}` : "—"}</span>
                  </div>
                  <div className="mt-2 whitespace-pre-wrap rounded-xl bg-gray-50 p-3 text-sm dark:bg-white/5">
                    {out?.content ?? <span className="text-gray-400">{s.error_text ?? "（无输出）"}</span>}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
