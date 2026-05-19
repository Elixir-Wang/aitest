"use client";

import { create } from "zustand";

import {
  getLocalStorageValue,
  getSessionStorageValue,
  removeLocalStorageValue,
  removeSessionStorageValue,
  setLocalStorageValue,
  setSessionStorageValue,
} from "@/lib/local-storage.client";

const AUTH_TOKEN_KEY = "ai-testing.auth.token";
const AUTH_USER_KEY = "ai-testing.auth.user";

interface AuthUser {
  name: string;
  email: string;
  role: "admin" | "tester" | "guest";
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  hasHydrated: boolean;
  hydrate: () => void;
  setAuth: (payload: { token: string; user: AuthUser }) => void;
  login: (payload: { token: string; user: AuthUser; remember?: boolean }) => void;
  logout: () => void;
}

function readStoredUser(): AuthUser | null {
  const raw = getLocalStorageValue(AUTH_USER_KEY) ?? getSessionStorageValue(AUTH_USER_KEY);

  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    removeLocalStorageValue(AUTH_USER_KEY);
    removeSessionStorageValue(AUTH_USER_KEY);
    return null;
  }
}

function readStoredToken() {
  return getLocalStorageValue(AUTH_TOKEN_KEY) ?? getSessionStorageValue(AUTH_TOKEN_KEY);
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  hasHydrated: false,
  hydrate: () => {
    set({
      token: readStoredToken(),
      user: readStoredUser(),
      hasHydrated: true,
    });
  },
  setAuth: ({ token, user }) => {
    set({
      token,
      user,
      hasHydrated: true,
    });
  },
  login: ({ token, user, remember }) => {
    removeLocalStorageValue(AUTH_TOKEN_KEY);
    removeLocalStorageValue(AUTH_USER_KEY);
    removeSessionStorageValue(AUTH_TOKEN_KEY);
    removeSessionStorageValue(AUTH_USER_KEY);

    if (remember) {
      setLocalStorageValue(AUTH_TOKEN_KEY, token);
      setLocalStorageValue(AUTH_USER_KEY, JSON.stringify(user));
    } else {
      setSessionStorageValue(AUTH_TOKEN_KEY, token);
      setSessionStorageValue(AUTH_USER_KEY, JSON.stringify(user));
    }

    set({ token, user, hasHydrated: true });
  },
  logout: () => {
    removeLocalStorageValue(AUTH_TOKEN_KEY);
    removeLocalStorageValue(AUTH_USER_KEY);
    removeSessionStorageValue(AUTH_TOKEN_KEY);
    removeSessionStorageValue(AUTH_USER_KEY);
    set({ token: null, user: null, hasHydrated: true });
  },
}));
