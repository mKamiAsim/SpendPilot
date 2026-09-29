import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, type ReactNode } from "react";

import { api, readJson } from "../lib/api";

export type SessionUser = {
  id: string;
  username: string;
  email: string;
  role: string;
  email_verified: boolean;
  session_locked: boolean;
};

type SessionState = {
  user: SessionUser | null;
  locked: boolean;
  loading: boolean;
  refresh: () => Promise<void>;
};

const SessionContext = createContext<SessionState>({
  user: null,
  locked: false,
  loading: true,
  refresh: async () => undefined,
});

async function loadSession(): Promise<{ user: SessionUser | null; locked: boolean }> {
  const response = await api("/api/v1/auth/session");
  if (response.status === 401) return { user: null, locked: false };
  if (response.status === 423) return { user: null, locked: true };
  const body = await readJson<{ user: SessionUser }>(response);
  return { user: body.user, locked: false };
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["session"], queryFn: loadSession });
  const value: SessionState = {
    user: query.data?.user ?? null,
    locked: query.data?.locked ?? false,
    loading: query.isLoading,
    refresh: async () => {
      await queryClient.invalidateQueries({ queryKey: ["session"] });
    },
  };
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  return useContext(SessionContext);
}
