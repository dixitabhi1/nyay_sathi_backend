import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";

import { api, getApiAuthToken, setApiAuthToken, setApiUnauthorizedHandler } from "../services/api";

type AuthUser = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  requested_role: string;
  approval_status: string;
  professional_id: string | null;
  organization: string | null;
  city: string | null;
  preferred_language: string;
  approval_notes: string | null;
  can_access_lawyer_dashboard: boolean;
  can_access_police_dashboard: boolean;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
};

type AuthTokenResponse = {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: AuthUser;
};

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (payload: { email: string; password: string }) => Promise<void>;
  register: (payload: {
    email: string;
    full_name: string;
    password: string;
    role: string;
    professional_id?: string | null;
    organization?: string | null;
    city?: string | null;
    preferred_language?: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    setApiUnauthorizedHandler(() => {
      setApiAuthToken(null);
      setUser(null);
      setLoading(false);
    });
    return () => {
      setApiUnauthorizedHandler(null);
    };
  }, []);

  async function applyAuthResponse(response: AuthTokenResponse) {
    setApiAuthToken(response.access_token);
    setUser(response.user);
  }

  async function refresh() {
    if (!getApiAuthToken()) {
      setLoading(false);
      return;
    }
    try {
      const me = (await api.authMe()) as AuthUser;
      setUser(me);
    } catch {
      setApiAuthToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  async function login(payload: { email: string; password: string }) {
    setLoading(true);
    try {
      const response = (await api.authLogin(payload)) as AuthTokenResponse;
      await applyAuthResponse(response);
    } finally {
      setLoading(false);
    }
  }

  async function register(payload: {
    email: string;
    full_name: string;
    password: string;
    role: string;
    professional_id?: string | null;
    organization?: string | null;
    city?: string | null;
    preferred_language?: string;
  }) {
    setLoading(true);
    try {
      const response = (await api.authRegister(payload)) as AuthTokenResponse;
      await applyAuthResponse(response);
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
    try {
      if (getApiAuthToken()) {
        await api.authLogout();
      }
    } catch {
      // Local cleanup still matters even if the network call fails.
    } finally {
      setApiAuthToken(null);
      setUser(null);
    }
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      isAuthenticated: Boolean(user),
      login,
      register,
      logout,
      refresh,
    }),
    [user, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }
  return context;
}
