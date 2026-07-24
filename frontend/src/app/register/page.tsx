// 注册页
"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { Button, Card, Input } from "@/components/ui";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(email, password, displayName || undefined);
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "注册失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AppShell>
      <div className="mx-auto max-w-md py-10">
        <h1 className="mb-2 text-2xl font-bold">创建账户</h1>
        <p className="mb-6 text-sm text-gray-500 dark:text-gray-400">
          拥有你自己的 AI 法律办事助手。
        </p>
        <Card>
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium">昵称（选填）</label>
              <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="如何称呼你" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">邮箱</label>
              <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">密码（至少 8 位）</label>
              <Input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? "创建中…" : "注册并登录"}
            </Button>
          </form>
        </Card>
        <p className="mt-4 text-center text-sm text-gray-500 dark:text-gray-400">
          已有账号？{" "}
          <Link href="/login" className="text-brand-600 hover:underline">
            去登录
          </Link>
        </p>
      </div>
    </AppShell>
  );
}
