// 案件列表页
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import api, { type CaseOut } from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { Badge, Card, Spinner } from "@/components/ui";
import { caseStatusLabels, caseTypeLabels } from "@/lib/constants";

export default function CasesPage() {
  const { user, loading } = useAuth();
  const [cases, setCases] = useState<CaseOut[]>([]);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    if (loading) return;
    if (!user) return;
    api
      .listCases({ page: 1, page_size: 50 })
      .then((p) => setCases(p.items))
      .catch(() => setCases([]))
      .finally(() => setBusy(false));
  }, [user, loading]);

  if (!loading && !user) {
    return (
      <AppShell>
        <div className="py-20 text-center text-gray-500 dark:text-gray-400">
          请先
          <Link href="/login" className="mx-1 text-brand-600 hover:underline">
            登录
          </Link>
          查看你的案件。
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">我的案件</h1>
        <Link href="/">
          <span className="text-sm text-brand-600 hover:underline">+ 新建案件</span>
        </Link>
      </div>

      {busy ? (
        <div className="flex justify-center py-20">
          <Spinner />
        </div>
      ) : cases.length === 0 ? (
        <Card className="py-16 text-center text-gray-500 dark:text-gray-400">
          还没有案件。回到
          <Link href="/" className="mx-1 text-brand-600 hover:underline">
            首页
          </Link>
          描述你的遭遇，开始第一步。
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {cases.map((c) => (
            <Link key={c.id} href={`/cases/${c.id}`}>
              <Card className="h-full transition hover:-translate-y-0.5 hover:shadow-md">
                <div className="flex items-start justify-between">
                  <span className="font-medium">{c.title}</span>
                  <Badge tone="brand">{caseTypeLabels[c.case_type]}</Badge>
                </div>
                <div className="mt-3">
                  <Badge tone="gray">{caseStatusLabels[c.status]}</Badge>
                </div>
                <p className="mt-3 line-clamp-2 text-sm text-gray-500 dark:text-gray-400">
                  {c.description || "（暂无描述）"}
                </p>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </AppShell>
  );
}
