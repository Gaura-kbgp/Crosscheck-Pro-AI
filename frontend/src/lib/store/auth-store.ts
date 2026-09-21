import { create } from "zustand";
import { authApi } from "@/lib/api/endpoints";
import { getStoredAuthToken, setStoredAuthToken } from "@/lib/api/client";
import {
  UserProfile,
  LoginInput,
  RegisterInput,
  RegisterResponse,
} from "@/lib/api/types";

interface SessionData {
  access_token: string;
}

interface AuthState {
  token: string | null;
  session: SessionData | null;
  user: UserProfile | null;
  profile: UserProfile | null;
  isInitialized: boolean;
  isLoading: boolean;
  error: string | null;

  initialize: () => Promise<void>;
  login: (data: LoginInput) => Promise<void>;
  register: (data: RegisterInput) => Promise<RegisterResponse>;
  loginWithGoogle: () => Promise<void>;
  handleGoogleCallback: (code: string) => Promise<void>;
  logout: () => void;
  fetchProfile: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  session: null,
  user: null,
  profile: null,
  isInitialized: false,
  isLoading: false,
  error: null,

  initialize: async () => {
    try {
      set({ isLoading: true, error: null });
      const storedToken = getStoredAuthToken();

      if (storedToken) {
        set({
          token: storedToken,
          session: { access_token: storedToken },
        });
        await get().fetchProfile();
      } else {
        set({
          token: null,
          session: null,
          user: null,
          profile: null,
        });
      }
    } catch {
      // If token is invalid or expired, clear it
      setStoredAuthToken(null);
      set({
        token: null,
        session: null,
        user: null,
        profile: null,
      });
    } finally {
      set({ isInitialized: true, isLoading: false });
    }
  },

  login: async (data: LoginInput) => {
    try {
      set({ isLoading: true, error: null });
      const response = await authApi.login(data);
      const token = response.access_token;
      setStoredAuthToken(token);
      set({
        token,
        session: { access_token: token },
        user: response.user,
        profile: response.user,
        isLoading: false,
      });
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Invalid email or password.";
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  register: async (data: RegisterInput): Promise<RegisterResponse> => {
    try {
      set({ isLoading: true, error: null });
      const response = await authApi.register(data);
      set({ isLoading: false });
      return response;
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Registration failed.";
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  loginWithGoogle: async () => {
    try {
      set({ isLoading: true, error: null });
      const { url } = await authApi.getGoogleAuthUrl();
      if (typeof window !== "undefined" && url) {
        window.location.assign(url);
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to initialize Google login.";
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  handleGoogleCallback: async (code: string) => {
    try {
      set({ isLoading: true, error: null });
      const response = await authApi.googleCallback({ code });
      const token = response.access_token;
      setStoredAuthToken(token);
      set({
        token,
        session: { access_token: token },
        user: response.user,
        profile: response.user,
        isLoading: false,
      });
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Google authentication failed.";
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  logout: () => {
    setStoredAuthToken(null);
    set({
      token: null,
      session: null,
      user: null,
      profile: null,
      isLoading: false,
      error: null,
    });
  },

  fetchProfile: async () => {
    try {
      const profile = await authApi.getMe();
      set({ profile, user: profile });
    } catch {
      set({ profile: null, user: null });
    }
  },

  clearError: () => set({ error: null }),
}));
