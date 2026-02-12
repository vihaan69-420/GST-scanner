"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

const ALLOWED_PATHS = ["/dashboard"];

function RedirectInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const to = searchParams.get("to");
    if (to && ALLOWED_PATHS.includes(to)) {
      router.replace(to);
    } else {
      router.replace("/");
    }
  }, [searchParams, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--background)]">
      <p className="text-[var(--muted)]">Redirectingâ€¦</p>
    </div>
  );
}

export default function AuthRedirectPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[var(--background)]">
          <p className="text-[var(--muted)]">Loadingâ€¦</p>
        </div>
      }
    >
      <RedirectInner />
    </Suspense>
  );
}

