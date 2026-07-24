"use client";

import { useEffect, useState } from "react";
import { api, type StatisticsOut } from "@/lib/api";
import { Card, Button } from "@/components/ui";
import { Banner } from "./Modal";

export function StatsPanel() {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<StatisticsOut | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.aiCenter
      .statistics(days)
      .then((d) => setData(d))
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [days]);

  const totals = data?.totals ?? {};
  const maxDayTokens =
    data?.per_day.reduce((m, r) => Math.max(m, (r.tokens_in || 0) + (r.tokens_out || 0)), 0) || 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Token 统计</h2>
          <p className="text-sm text-gray-500">用量 / 费用 / 调用次数 / 失败率（按天与按模型）。</p>
        </div>
        <div className="flex gap-2">
          {[7, 30, 90, 365].map((d) => (
            <Button
              key={d}
              size="sm"
              variant={days === d ? "primary" : "outline"}
              onClick={() => setDays(d)}
            >
              {d}天
            </Button>
          ))}
        </div>
      </div>

      {err && <Banner tone="red">{err}</Banner>}

      {loading ? (
        <Card className="text-center text-sm text-gray-400">加载中…</Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Card>
              <div className="text-xs text-gray-500">总 Token</div>
              <div className="mt-1 text-xl font-semibold">
                {((totals.tokens_in as number) || 0) + ((totals.tokens_out as number) || 0)}
              </div>
            </Card>
            <Card>
              <div className="text-xs text-gray-500">总调用</div>
              <div className="mt-1 text-xl font-semibold">{totals.calls ?? 0}</div>
            </Card>
            <Card>
              <div className="text-xs text-gray-500">总费用</div>
              <div className="mt-1 text-xl font-semibold">
                {String(totals.cost ?? 0)} {totals.cost_currency ?? "USD"}
              </div>
            </Card>
            <Card>
              <div className="text-xs text-gray-500">失败率</div>
              <div className="mt-1 text-xl font-semibold">
                {(((totals.failures as number) || 0) / Math.max(1, (totals.calls as number) || 1) * 100).toFixed(1)}%
              </div>
            </Card>
          </div>

          <Card>
            <div className="mb-3 text-sm font-medium text-gray-700 dark:text-gray-300">每日 Token 趋势</div>
            {data?.per_day.length ? (
              <div className="flex h-40 items-end gap-1 overflow-x-auto">
                {data.per_day.map((r) => {
                  const t = (r.tokens_in || 0) + (r.tokens_out || 0);
                  const h = maxDayTokens ? Math.max(4, (t / maxDayTokens) * 100) : 4;
                  return (
                    <div key={r.date} className="flex w-3 flex-col items-center justify-end" title={`${r.date}: ${t}`}>
                      <div className="w-full rounded-t bg-brand-400 dark:bg-brand-500" style={{ height: `${h}%` }} />
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-sm text-gray-400">暂无统计数据。</div>
            )}
          </Card>

          <Card>
            <div className="mb-3 text-sm font-medium text-gray-700 dark:text-gray-300">按模型</div>
            {data?.per_model.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left text-gray-500">
                    <tr>
                      <th className="py-2">模型</th>
                      <th>Token(in/out)</th>
                      <th>调用</th>
                      <th>失败</th>
                      <th>费用</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.per_model.map((r, i) => (
                      <tr key={i} className="border-t border-gray-100 dark:border-white/10">
                        <td className="py-2">{r.model_name ?? "—"}</td>
                        <td>{(r.tokens_in || 0)} / {(r.tokens_out || 0)}</td>
                        <td>{r.calls}</td>
                        <td className={r.failures > 0 ? "text-red-500" : ""}>{r.failures}</td>
                        <td>{String(r.cost)} {r.cost_currency}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-sm text-gray-400">暂无统计数据。</div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
