import { NextRequest } from "next/server";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ docId: string }> }
) {
  const { docId } = await params;
  const response = await fetch(`http://localhost:8000/pdf/${docId}`);
  if (!response.ok) {
    return new Response("PDF not found", { status: 404 });
  }
  return new Response(response.body, {
    headers: { "Content-Type": "application/pdf" },
  });
}
