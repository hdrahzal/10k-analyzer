import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const response = await fetch("http://localhost:8000/ingest", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      return NextResponse.json(data, { status: response.status });
    }
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error proxying upload:", error);
    return NextResponse.json(
      { error: "Failed to reach backend service" },
      { status: 502 }
    );
  }
}
