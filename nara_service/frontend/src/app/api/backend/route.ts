import { NextRequest, NextResponse } from 'next/server';

// 백엔드 URL과 API Key (서버 측 환경변수 - 브라우저에 노출되지 않음)
const BACKEND_URL = (process.env.BACKEND_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API_KEY = process.env.NEXT_API_ROUTE_KEY || 'dev-api-key-change-in-production';

export async function GET(request: NextRequest) {
  try {
    console.log('Health Check - BACKEND_URL:', BACKEND_URL);
    console.log('Health Check - API_KEY:', API_KEY ? 'Set' : 'Not set');

    const response = await fetch(`${BACKEND_URL}/`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
      },
    });

    console.log('Backend health check status:', response.status);

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Backend health check error:', errorText);
      return NextResponse.json(
        { error: 'Backend health check failed', details: errorText },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Health Check Error:', error);
    return NextResponse.json(
      { error: 'Backend server unreachable', message: error instanceof Error ? error.message : String(error) },
      { status: 503 }
    );
  }
}
