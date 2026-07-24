// 认证上下文：管理当前用户与 Token（localStorage 持久化）。
"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import api, { type Token, type UserOut } from "./api";

interface AuthContextValue {
  user: UserOut | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // 初始化：从 localStorage 恢复会话并拉取用户信息
  useEffect(() => {
    const stored = localStorage.getItem("lp_token");
    if (stored) {
      setToken(stored);
      api
        .me()
        .then(setUser)
        .catch(() => {
          localStorage.removeItem("lp_token");
          setToken(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const persist = (t: Token) => {
    localStorage.setItem("lp_token", t.access_token);
    setToken(t.access_token);
  };

  const login = async (email: string, password: string) => {
    const t = await api.login(email, password);
    persist(t);
    setUser(await api.me());
  };

  const register = async (email: string, password: string, displayName?: string) => {
    await api.register(email, password, displayName);
    await login(email, password);
  };

  const logout = () => {
    localStorage.removeItem("lp_token");
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth 必须在 AuthProvider 内使用");
  return ctx;
}
