"use client";

import { useEffect, useState } from "react";
import { api, type ModelHealthOut } from "@/lib/api";
import { Card, Badge, Button } from "@/components/ui";
import { Banner } from "./Modal";

const CAPS: { key: keyof ModelHealthOut; label: string }[] = [
  { key: "chat_ok", label: "对话" },
  { key: "vision_ok", label: "视觉" },
  { key: "embedding_ok", label: "向量" },
  { key: "streaming_ok", label: "流式" },
  { key: "json_ok", label: "JSON" },
  { key: "function_calling_ok", label: "函数" },
  { key: "web_ok", label: "联网" },
];

export function HealthPanel() {
  const [rows, setRows] = useState<ModelHealthOut[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState<string | null>(null);

  function load() {
    setLoading(true);
    api.aiCenter
      .health()
      .then(setRows)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  async function check(id: string) {
    setChecking(id);
    try {
      await api.aiCenter.checkHealth(id);
      load();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setChecking(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">模型健康检测</h2>
          <p className="text-sm text-gray-500">手动触发对各模型能力（对话 / 视觉 / 向量 / 流式 / JSON / 函数 / 联网）的探测。</p>
        </div>
        <Button variant="outline" onClick={load} disabled={loading}>刷新</Button>
      </div>

      {err && <Banner tone="red">{err}</Banner>}

      <div className="grid gap-3">
        {loading ? (
          <Card className="text-center text-sm text-gray-400">加载中…</Card>
        ) : rows.length === 0 ? (
          <Card className="text-center text-sm text-gray-400">
            暂无健康记录。点击「检测」触发对各模型的探测（自动写入 model_health）。
          </Card>
        ) : (
          rows.map((h) => (
            <Card key={h.id}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{h.model_name ?? h.model_id}</span>
                    <Badge
                      tone={
                        h.status === "ok" || h.status === "healthy"
                          ? "green"
                          : h.status === "unknown"
                          ? "gray"
                          : "red"
                      }
                    >
                      {h.status ?? "未检测"}
                    </Badge>
                    {h.latency_ms != null && <span className="text-xs text-gray-400">{h.latency_ms}ms</span>}
                  </div>
                  {h.last_checked && (
                    <div className="mt-0.5 text-xs text-gray-400">最近检测：{h.last_checked}</div>
                  )}
                  {h.error_text && <div className="mt-0.5 text-xs text-red-500">{h.error_text}</div>}
                </div>
                <Button size="sm" variant="outline" onClick={() => check(h.model_id)} disabled={checking === h.model_id}>
                  {checking === h.model_id ? "检测中…" : "检测"}
                </Button>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {CAPS.map((c) => {
                  const v = h[c.key] as boolean | null;
                  return (
                    <span
                      key={c.key}
                      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        v == null
                          ? "bg-gray-100 text-gray-400 dark:bg-white/10"
                          : v
                          ? "bg-green-50 text-green-700 dark:bg-green-500/15 dark:text-green-300"
                          : "bg-red-50 text-red-700 dark:bg-red-500/15 dark:text-red-300"
                      }`}
                    >
                      {c.label} {v == null ? "—" : v ? "✓" : "✗"}
                    </span>
                  );
                })}
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
