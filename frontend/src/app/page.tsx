"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export default function HomePage() {
  const {user, loading} = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (!loading) router.replace(!user ? "/login" : user.role === "CUSTOMER" ? "/portal" : "/app");
  }, [user, loading, router]);
  return <main className="flex min-h-screen items-center justify-center"><p role="status">Opening your workspace…</p></main>;
}
