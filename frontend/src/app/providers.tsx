// 客户端 Provider 聚合（供根布局以 Server Component 形式引入）。
"use client";

import { AuthProvider } from "@/lib/auth";

export function Providers({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}
