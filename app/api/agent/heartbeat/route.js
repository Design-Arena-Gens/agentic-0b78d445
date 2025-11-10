import { NextResponse } from "next/server";

let lastHeartbeat = null;

export async function POST(req) {
  try {
    const body = await req.json();
    lastHeartbeat = { ...body, at: Date.now() };
    return NextResponse.json({ ok: true, lastHeartbeat });
  } catch (e) {
    return NextResponse.json({ error: e?.message || "Invalid request" }, { status: 400 });
  }
}

export async function GET() {
  return NextResponse.json({ ok: true, lastHeartbeat });
}
