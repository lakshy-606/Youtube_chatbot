import { NextRequest, NextResponse } from "next/server";

// Runs on Next.js's own (Node) runtime — separate from the Python RAG function — so fetching
// oEmbed here is a same-origin call from the browser's perspective, no CORS concerns. Video
// metadata (title/thumbnail) is display-only; it never reaches the RAG pipeline.
export async function GET(request: NextRequest) {
  const videoId = request.nextUrl.searchParams.get("videoId");
  if (!videoId) {
    return NextResponse.json({ error: "videoId is required" }, { status: 400 });
  }

  const oembedUrl = `https://www.youtube.com/oembed?url=${encodeURIComponent(
    `https://www.youtube.com/watch?v=${videoId}`
  )}&format=json`;

  try {
    const res = await fetch(oembedUrl);
    if (!res.ok) {
      return NextResponse.json({ error: "Video not found" }, { status: 404 });
    }
    const data = await res.json();
    return NextResponse.json({
      title: data.title as string,
      author: data.author_name as string,
      // YouTube's thumbnail CDN — reliable and doesn't depend on oEmbed's own thumbnail field.
      thumbnailUrl: `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`,
    });
  } catch {
    return NextResponse.json({ error: "Could not fetch video metadata" }, { status: 502 });
  }
}
