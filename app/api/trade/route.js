import { NextResponse } from "next/server";

export async function POST(req) {
  try {
    const body = await req.json();
    // In a real system, persist trade logs. Here we just echo.
    return NextResponse.json({ received: true, body });
  } catch (e) {
    return NextResponse.json({ error: e?.message || "Invalid request" }, { status: 400 });
  }
}

export async function GET() {
  return NextResponse.json({ ok: true, endpoint: "/api/trade" });
}
