import { NextRequest } from 'next/server';

const BACKEND_URL = (process.env.BACKEND_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API_KEY = process.env.NEXT_API_ROUTE_KEY || 'dev-api-key-change-in-production';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    const response = await fetch(`${BACKEND_URL}/query/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      return new Response(
        JSON.stringify({ error: 'Backend request failed' }),
        { status: response.status, headers: { 'Content-Type': 'application/json' } }
      );
    }

    // 스트리밍 응답을 그대로 전달
    return new Response(response.body, {
      status: response.status,
      headers: {
        'Content-Type': 'application/x-ndjson',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
    });
  } catch (error) {
    console.error('API Route Error:', error);
    return new Response(
      JSON.stringify({ error: 'Internal server error' }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
}
