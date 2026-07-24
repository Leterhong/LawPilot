// 应用外壳：顶部导航 + 主题切换 + 认证状态。
// 在客户端页面中包裹内容，提供统一导航体验。
"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { ThemeToggle } from "./ThemeToggle";
import { Button } from "./ui";
import { cn } from "@/lib/utils";

function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500 text-white shadow-soft">
        <span className="text-base font-bold">L</span>
      </span>
      <span className="text-lg font-semibold tracking-tight">LawPilot</span>
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const navItems = [
    { href: "/", label: "首页" },
    { href: "/case-center", label: "📁 我的案件" },
    { href: "/contracts", label: "📄 合同中心" },
    { href: "/evidence-center", label: "🗂️ 证据中心" },
    { href: "/laws", label: "📚 法律搜索" },
    { href: "/case-search", label: "⚖️ 案例搜索" },
    { href: "/research", label: "📖 法律研究" },
  ];

  return (
    <div className="min-h-screen bg-white text-gray-900 dark:bg-[#090b10] dark:text-gray-100">
      <header className="sticky top-0 z-20 border-b border-gray-100 bg-white/80 backdrop-blur dark:border-white/10 dark:bg-[#090b10]/80">
        <div className="mx-auto flex h-14 max-w-screen-2xl items-center justify-between gap-4 px-6 lg:px-10">
          <div className="flex items-center gap-8">
            <Logo />
            <nav className="hidden items-center gap-2 sm:flex">
              {navItems.map((item) => {
                const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "rounded-lg px-3 py-1.5 text-sm transition",
                      active
                        ? "bg-gray-100 font-medium dark:bg-white/10"
                        : "text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
                    )}
                  >
                    {item.label}
                  </Link>
                );
              })}
              {user && (
                <div className="ml-2 flex items-center gap-1 border-l border-gray-200 pl-3 dark:border-white/10">
                  <span className="px-2 py-1.5 text-xs font-medium text-gray-400 dark:text-gray-500">
                    系统设置
                  </span>
                  <Link
                    href="/settings/playground"
                    className={cn(
                      "rounded-lg px-3 py-1.5 text-sm transition",
                      pathname.startsWith("/settings/playground")
                        ? "bg-brand-50 font-medium text-brand-700 dark:bg-brand-500/15 dark:text-brand-300"
                        : "text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5"
                    )}
                  >
                    🧪 AI Playground
                  </Link>
                  {user.is_superuser && (
                    <Link
                      href="/settings/ai-center"
                      className={cn(
                        "rounded-lg px-3 py-1.5 text-sm transition",
                        pathname.startsWith("/settings/ai-center")
                          ? "bg-brand-50 font-medium text-brand-700 dark:bg-brand-500/15 dark:text-brand-300"
                          : "text-brand-600 hover:bg-brand-50 dark:text-brand-400 dark:hover:bg-brand-500/10"
                      )}
                    >
                      ⚙️ AI 能力中心
                    </Link>
                  )}
                </div>
              )}
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            {loading ? null : user ? (
              <div className="flex items-center gap-2">
                <span className="hidden text-sm text-gray-500 dark:text-gray-400 sm:inline">
                  {user.display_name || user.email}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    logout();
                    router.push("/");
                  }}
                >
                  退出
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Link href="/login">
                  <Button variant="ghost" size="sm">
                    登录
                  </Button>
                </Link>
                <Link href="/register">
                  <Button size="sm">注册</Button>
                </Link>
              </div>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-8 lg:px-10">{children}</main>
    </div>
  );
}
