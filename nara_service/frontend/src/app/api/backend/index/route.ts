import { NextRequest, NextResponse } from 'next/server';

// 백엔드 URL과 API Key (서버 측 환경변수 - 브라우저에 노출되지 않음)
const BACKEND_URL = (process.env.BACKEND_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API_KEY = process.env.NEXT_API_ROUTE_KEY || 'dev-api-key-change-in-production';

export async function GET(request: NextRequest) {
  try {
    console.log('=== API Route Debug Info ===');
    console.log('BACKEND_URL:', BACKEND_URL);
    console.log('API_KEY exists:', !!API_KEY);
    console.log('API_KEY length:', API_KEY?.length || 0);
    console.log('API_KEY first 10 chars:', API_KEY?.substring(0, 10) || 'undefined');
    console.log('Environment variables:', {
      BACKEND_API_URL: process.env.BACKEND_API_URL || 'not set',
      NEXT_API_ROUTE_KEY: process.env.NEXT_API_ROUTE_KEY ? 'exists' : 'not set'
    });

    const response = await fetch(`${BACKEND_URL}/index`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
      },
    });

    console.log('Backend response status:', response.status);

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Backend error:', errorText);
      return NextResponse.json(
        { error: 'Backend request failed', details: errorText },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('API Route Error:', error);
    return NextResponse.json(
      { error: 'Internal server error', message: error instanceof Error ? error.message : String(error) },
      { status: 500 }
    );
  }
}
