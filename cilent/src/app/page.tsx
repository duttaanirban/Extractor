"use client";

import { useEffect, useState } from "react";

export default function Home() {
  const [status, setStatus] = useState("Checking backend...");

  useEffect(() => {
    fetch("http://localhost:8000/api/health")
      .then((response) => {
        if (!response.ok) {
          throw new Error("Backend request failed");
        }
        return response.json();
      })
      .then((data) => {
        setStatus(`Backend connected ✓ — ${data.status}`);
      })
      .catch(() => {
        setStatus("Backend connection failed ✗");
      });
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-50">
      <div className="rounded-xl border bg-white p-10 text-center shadow-sm">
        <h1 className="mb-4 text-3xl font-bold text-zinc-900">
          EXPORT Automation
        </h1>

        <p className="text-lg text-zinc-600">{status}</p>
      </div>
    </main>
  );
}