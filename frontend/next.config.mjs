/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // 允许后端 API 跨域图片/资源（如需远程图片）
  images: {
    remotePatterns: [],
  },
  // 修复 Windows 上 "Jest worker encountered 2 child process exceptions"：
  // 本机进程树受 Windows Job Object 限制（AssignProcessToJobObject 错误 50），
  // Next dev 的 static-paths worker 以子进程方式启动会被系统立即杀死，
  // 导致所有动态路由（/xxx/[id]）500。改用 worker_threads（线程）即可绕开，
  // 同时将 worker 数限制为 1，降低内存占用。
  experimental: {
    cpus: 1,
    workerThreads: true,
  },
};

export default nextConfig;
