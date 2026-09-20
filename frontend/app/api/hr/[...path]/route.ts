import { NextRequest, NextResponse } from "next/server";

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const token = process.env.HR_API_TOKEN;
  if (!token) {
    return NextResponse.json(
      { detail: "HR API authorization is not configured" },
      { status: 503 },
    );
  }
  const { path } = await context.params;
  const backend = (
    process.env.BACKEND_API_URL
    ?? process.env.NEXT_PUBLIC_API_URL
    ?? "http://localhost:8000"
  ).replace(/\/$/, "");
  const target = `${backend}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const response = await fetch(target, {
    method: request.method,
    headers: {
      "Content-Type": request.headers.get("content-type") ?? "application/json",
      Authorization: `Bearer ${token}`,
      "X-HR-User": process.env.HR_USER_NAME ?? "Local HR User",
    },
    body: request.method === "GET" ? undefined : await request.text(),
    cache: "no-store",
  });
  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/json",
    },
  });
}

export const POST = proxy;
