import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AdminProfile, AthleteProfile, UserRole } from "@/lib/types";

interface AuthStore {
  role: UserRole | null;
  profile: AdminProfile | AthleteProfile | null;
  setAuth: (role: UserRole, profile: AdminProfile | AthleteProfile) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      role: null,
      profile: null,
      setAuth: (role, profile) => set({ role, profile }),
      clearAuth: () => set({ role: null, profile: null }),
    }),
    { name: "fitcoach-auth" }
  )
);
