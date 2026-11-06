import { create } from "zustand";
import { authApi } from "@/lib/api/endpoints";
import { getStoredAuthToken, setStoredAuthToken } from "@/lib/api/client";
import { supabase } from "@/lib/supabase/client";
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

function isSupabaseConfigured(): boolean {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  return !!url && !url.includes("placeholder.supabase.co");
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

      // 1. Check Supabase session first if configured
      if (isSupabaseConfigured()) {
        try {
          const { data: { session } } = await supabase.auth.getSession();
          if (session?.access_token) {
            setStoredAuthToken(session.access_token);
            set({
              token: session.access_token,
              session: { access_token: session.access_token },
            });
            await get().fetchProfile();
            return;
          }
        } catch {
          // If Supabase session fails, fallback to local storage
        }
      }

      // 2. Check local storage token
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

      // 1. Try Supabase Auth first if configured
      if (isSupabaseConfigured()) {
        try {
          const { data: sbData, error: sbError } = await supabase.auth.signInWithPassword({
            email: data.email,
            password: data.password,
          });

          if (!sbError && sbData.session?.access_token) {
            const token = sbData.session.access_token;
            setStoredAuthToken(token);
            set({ token, session: { access_token: token }, isLoading: false });
            // fire without await — backend cold start must not block the login redirect
            get().fetchProfile();
            return;
          } else if (sbError && !sbError.message.toLowerCase().includes("invalid login credentials")) {
            // If it's a specific Supabase error other than invalid credentials, throw it
            throw sbError;
          }
        } catch (sbErr: unknown) {
          // If Supabase is unreachable or failed, check if backend local auth can handle it
          console.warn("Supabase auth attempt failed, attempting backend auth fallback:", sbErr);
        }
      }

      // 2. Fallback to FastAPI backend login
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

      // 1. Try Supabase Auth signup if configured
      if (isSupabaseConfigured()) {
        const { data: sbData, error: sbError } = await supabase.auth.signUp({
          email: data.email,
          password: data.password,
          options: {
            data: {
              full_name: data.full_name,
              organization_name: data.organization_name,
              business_role: data.business_role,
            },
            // Without this, Supabase falls back to its dashboard "Site URL"
            // for the confirm-signup link regardless of where the user
            // actually signed up — on production that defaulted to
            // localhost:3000. Match the real origin, like forgot-password
            // and Google OAuth already do.
            emailRedirectTo: typeof window !== "undefined" ? `${window.location.origin}/login` : undefined,
          },
        });

        if (sbError) {
          throw sbError;
        }

        if (sbData.user) {
          // If session returned immediately (email confirmation disabled)
          if (sbData.session?.access_token) {
            const token = sbData.session.access_token;
            setStoredAuthToken(token);
            set({
              token,
              session: { access_token: token },
            });
            await get().fetchProfile();
          }

          set({ isLoading: false });
          return {
            message: "Registration successful. Please check your email to verify your account.",
            email: data.email,
            user_id: sbData.user.id,
            is_verified: !!sbData.session,
          };
        }
      }

      // 2. Fallback to FastAPI backend registration
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

      if (isSupabaseConfigured()) {
        const { error } = await supabase.auth.signInWithOAuth({
          provider: "google",
          options: {
            redirectTo: typeof window !== "undefined" ? `${window.location.origin}/auth/callback` : undefined,
          },
        });
        if (error) throw error;
        return;
      }

      // Fallback to backend Google OAuth
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

      // 1. If Supabase configured, exchange code for session or get session
      if (isSupabaseConfigured()) {
        try {
          const { data, error } = await supabase.auth.exchangeCodeForSession(code);
          if (!error && data.session?.access_token) {
            const token = data.session.access_token;
            setStoredAuthToken(token);
            set({
              token,
              session: { access_token: token },
            });
            await get().fetchProfile();
            set({ isLoading: false });
            return;
          }
        } catch {
          // If exchangeCodeForSession is not needed or fails, try getSession
          const { data: { session } } = await supabase.auth.getSession();
          if (session?.access_token) {
            const token = session.access_token;
            setStoredAuthToken(token);
            set({
              token,
              session: { access_token: token },
            });
            await get().fetchProfile();
            set({ isLoading: false });
            return;
          }
        }
      }

      // 2. Fallback to FastAPI backend exchange
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

  logout: async () => {
    try {
      if (isSupabaseConfigured()) {
        await supabase.auth.signOut();
      }
    } catch {
      // ignore
    }
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
