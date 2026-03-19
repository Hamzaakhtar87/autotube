import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest) {
    const url = req.nextUrl.searchParams.get("url");

    if (!url) {
        return new NextResponse("Missing URL parameter", { status: 400 });
    }

    try {
        // Fetch the file from the remote backend (e.g. Oracle server via Ngrok)
        const response = await fetch(url, {
            method: "GET",
            headers: {
                "ngrok-skip-browser-warning": "69420",
            },
        });

        if (!response.ok) {
            return new NextResponse(`Backend error: ${response.statusText}`, { status: response.status });
        }

        // Get headers from the response to proxy them
        const contentType = response.headers.get("Content-Type") || "video/mp4";
        const contentLength = response.headers.get("Content-Length");
        const contentDisposition = response.headers.get("Content-Disposition") || "attachment";

        const headers = new Headers();
        headers.set("Content-Type", contentType);
        headers.set("Content-Disposition", contentDisposition);
        if (contentLength) {
            headers.set("Content-Length", contentLength);
        }

        // Stream the response directly to the client
        return new NextResponse(response.body, {
            status: 200,
            headers,
        });
    } catch (error) {
        console.error("Proxy download error:", error);
        return new NextResponse("Internal Server Error while downloading file", { status: 500 });
    }
}
