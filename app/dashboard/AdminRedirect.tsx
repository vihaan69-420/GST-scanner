"use client";

import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useEffect } from "react";

export default function AdminRedirect() {
  const { session } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (session?.role === "admin") {
      router.replace("/dashboard");
    }
  }, [session?.role, router]);

  return null;
}
