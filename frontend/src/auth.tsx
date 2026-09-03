import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, ApiError } from "./api";

interface AuthState {
  user: string | null;
  loading: boolean;
  login: (u: string, p: string) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthState>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<{ user: string }>("/api/auth/me")
      .then((r) => setUser(r.user))
      .catch((e) => { if (!(e instanceof ApiError)) console.error(e); })
      .finally(() => setLoading(false));
  }, []);

  const login = async (username: string, password: string) => {
    const r = await api.post<{ user: string }>("/api/auth/login", { username, password });
    setUser(r.user);
  };
  const logout = async () => {
    await api.post("/api/auth/logout");
    setUser(null);
  };

  return <Ctx.Provider value={{ user, loading, login, logout }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
