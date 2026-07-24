"use client";

import { useEffect, useState } from "react";
import { api, type ModelLogOut, type AIMeta } from "@/lib/api";
import { aiFeatureLabels } from "@/lib/constants";
import { Card, Badge, Button } from "@/components/ui";
import { Banner } from "./Modal";

export function LogsPanel({ meta }: { meta: AIMeta }) {
  const [logs, setLogs] = useState<ModelLogOut[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [feature, setFeature] = useState("");
  const [limit, setLimit] = useState(100);

  useEffect(() => {
    setLoading(true);
    api.aiCenter
      .logs({ limit, feature: feature || undefined })
      .then(setLogs)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [feature, limit]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">日志中心</h2>
          <p className="text-sm text-gray-500">每次模型调用的明细：模型 / 功能 / 耗时 / Token / 费用 / 状态。</p>
        </div>
        <div className="flex gap-2">
          <select
            className="rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm dark:border-white/10 dark:bg-white/5"
            value={feature}
            onChange={(e) => setFeature(e.target.value)}
          >
            <option value="">全部功能</option>
            {meta.features.map((f) => (
              <option key={f} value={f}>{aiFeatureLabels[f] ?? f}</option>
            ))}
          </select>
          <select
            className="rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm dark:border-white/10 dark:bg-white/5"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
          >
            <option value={100}>100 条</option>
            <option value={300}>300 条</option>
            <option value={1000}>1000 条</option>
          </select>
        </div>
      </div>

      {err && <Banner tone="red">{err}</Banner>}

      <Card className="p-0">
        {loading ? (
          <div className="p-6 text-center text-sm text-gray-400">加载中…</div>
        ) : logs.length === 0 ? (
          <div className="p-6 text-center text-sm text-gray-400">暂无日志。</div>
        ) : (
          <div className="max-h-[70vh] overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-white text-left text-gray-500 dark:bg-[#11151c]">
                <tr>
                  <th className="px-4 py-2">时间</th>
                  <th>功能</th>
                  <th>模型</th>
                  <th>耗时</th>
                  <th>Token</th>
                  <th>费用</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id} className="border-t border-gray-100 dark:border-white/10">
                    <td className="px-4 py-2 text-xs text-gray-500">{l.created_at}</td>
                    <td>{l.feature ? aiFeatureLabels[l.feature] ?? l.feature : "—"}</td>
                    <td>{l.model_name ?? "—"}</td>
                    <td>{l.latency_ms}ms</td>
                    <td>{(l.tokens_in || 0) + (l.tokens_out || 0)}</td>
                    <td>{String(l.cost)}</td>
                    <td>
                      <Badge tone={l.status === "ok" || l.status === "success" ? "green" : "red"}>
                        {l.status}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
