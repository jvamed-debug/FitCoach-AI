import axios, { AxiosError } from "axios";
import { supabase } from "@/lib/supabase";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
  timeout: 15_000,
});

// Attach Supabase JWT on every request
api.interceptors.request.use(async (config) => {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401, try to refresh then retry once
api.interceptors.response.use(
  (res) => res,
  async (err: AxiosError) => {
    const original = err.config as typeof err.config & { _retry?: boolean };
    if (err.response?.status === 401 && !original?._retry) {
      original._retry = true;
      const { data, error } = await supabase.auth.refreshSession();
      if (!error && data.session) {
        original.headers = {
          ...original.headers,
          Authorization: `Bearer ${data.session.access_token}`,
        };
        return api(original);
      }
      // Refresh failed — redirect to login
      window.location.href = "/auth/login";
    }
    return Promise.reject(err);
  }
);

export default api;
