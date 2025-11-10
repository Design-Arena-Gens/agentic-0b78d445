import { NextResponse } from "next/server";
import { z } from "zod";
import { analyzeWithGemini } from "../../../lib/gemini";

const Candle = z.object({ time: z.number().or(z.string()), open: z.number(), high: z.number(), low: z.number(), close: z.number(), tick_volume: z.number().optional(), volume: z.number().optional() });
const Body = z.object({ symbol: z.string(), timeframe: z.string(), candles: z.array(Candle).default([]) });

export async function POST(req) {
  try {
    const json = await req.json();
    const body = Body.parse(json);

    const signal = await analyzeWithGemini(body);

    // ensure safe defaults
    const safe = {
      action: ["buy", "sell", "hold"].includes(signal.action) ? signal.action : "hold",
      entry: typeof signal.entry === "number" ? signal.entry : null,
      stopLoss: typeof signal.stopLoss === "number" ? signal.stopLoss : null,
      takeProfit: typeof signal.takeProfit === "number" ? signal.takeProfit : null,
      confidence: typeof signal.confidence === "number" ? signal.confidence : 0.5,
      rationale: signal.rationale || "",
    };

    return NextResponse.json(safe);
  } catch (e) {
    return NextResponse.json({ error: e?.message || "Invalid request" }, { status: 400 });
  }
}

export async function GET() {
  return NextResponse.json({ ok: true, endpoint: "/api/analyze" });
}
