"use client";
import { useEffect, useState } from "react";

export default function Home() {
  const [status, setStatus] = useState({ ok: false });
  const [message, setMessage] = useState("");

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((d) => setStatus(d))
      .catch(() => setStatus({ ok: false }));
  }, []);

  const triggerDemo = async () => {
    setMessage("Running analysis...");
    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: "EURUSD",
          timeframe: "M5",
          candles: [], // agent should send candles; this is a placeholder
        }),
      });
      const data = await res.json();
      setMessage(`Signal: ${data.action?.toUpperCase()} | Confidence: ${data.confidence ?? 0}`);
    } catch (e) {
      setMessage("Analysis failed");
    }
  };

  return (
    <main style={{ maxWidth: 820, margin: "40px auto", padding: 24, fontFamily: "ui-sans-serif, system-ui" }}>
      <h1 style={{ fontSize: 28, fontWeight: 700 }}>AI Forex Trading Bot</h1>
      <p style={{ color: "#555" }}>Backend ready: {status.ok ? "Yes" : "No"}</p>
      <div style={{ marginTop: 24, display: "flex", gap: 12 }}>
        <button onClick={triggerDemo} style={{ padding: "10px 16px", borderRadius: 8, border: "1px solid #ccc" }}>Run Demo Analysis</button>
      </div>
      {message && <pre style={{ marginTop: 16, background: "#fafafa", padding: 16, borderRadius: 8 }}>{message}</pre>}
      <section style={{ marginTop: 32 }}>
        <h2 style={{ fontSize: 22, fontWeight: 600 }}>Agent Endpoints</h2>
        <ul style={{ lineHeight: 1.9 }}>
          <li><code>POST /api/analyze</code>: send symbol, timeframe, candles for AI signal</li>
          <li><code>POST /api/agent/heartbeat</code>: agent heartbeat with id/secret</li>
          <li><code>POST /api/trade</code>: report trade execution result</li>
        </ul>
      </section>
    </main>
  );
}
