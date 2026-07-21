"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store/authStore";

export default function RootPage() {
  const router = useRouter();
  const { role, profile } = useAuthStore();

  useEffect(() => {
    if (!role || !profile) {
      router.replace("/auth/login");
      return;
    }
    router.replace("/dashboard");
  }, [role, profile, router]);

  return null;
}
