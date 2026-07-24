import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";

/**
 * 根布局。
 * - 中文语言环境
 * - 支持暗色模式（class 策略，由客户端主题脚本切换 <html class="dark">）
 * - 预连接字体与基础元信息
 */
export const metadata: Metadata = {
  title: "LawPilot · 你的AI法律办事助手",
  description:
    "LawPilot 让每个人都拥有自己的 AI 法律办事助手：识别问题、明确权益、准备证据、规划下一步。",
};

export const viewport: Viewport = {
  themeColor: "#3366ff",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        {/* 在首屏渲染前应用主题，避免暗色闪烁 */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem('lp-theme');if(t==='dark'||(!t&&window.matchMedia('(prefers-color-scheme:dark)').matches)){document.documentElement.classList.add('dark')}}catch(e){}`,
          }}
        />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
