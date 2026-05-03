import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";

// 백엔드 URL과 API Key (서버 측 환경변수 - 브라우저에 노출되지 않음)
const BACKEND_URL = (process.env.BACKEND_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const API_KEY = process.env.NEXT_API_ROUTE_KEY || 'dev-api-key-change-in-production';

/**
 * GET 요청 핸들러 - Did You Know API 프록시
 *
 * 지원 엔드포인트:
 * - GET /didyouknow/facts?category={category}
 * - GET /didyouknow/random?category={category}
 * - GET /didyouknow/stats
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  try {
    const { path: pathArray } = await params;
    const path = pathArray?.join('/') || '';
    const searchParams = request.nextUrl.searchParams.toString();
    const url = `${BACKEND_URL}/didyouknow${path ? `/${path}` : ''}${searchParams ? `?${searchParams}` : ''}`;

    console.log('[Did You Know API] GET request:', url);

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[Did You Know API] Backend error:', errorText);
      return NextResponse.json(
        { error: 'Backend request failed', details: errorText },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('[Did You Know API] Error:', error);
    return NextResponse.json(
      {
        error: 'Internal server error',
        message: error instanceof Error ? error.message : String(error)
      },
      { status: 500 }
    );
  }
}

/**
 * POST 요청 핸들러 - Did You Know API 프록시
 *
 * 지원 엔드포인트:
 * - POST /didyouknow/generate (관리자 전용)
 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path?: string[] }> }
) {
  try {
    const { path: pathArray } = await params;
    const path = pathArray?.join('/') || '';

    // generate 엔드포인트는 admin 전용
    if (path === 'generate') {
      const session = await getServerSession(authOptions);

      if (!session || !session.user) {
        return NextResponse.json(
          { detail: "Unauthorized - Please login first" },
          { status: 401 }
        );
      }

      if (session.user.role !== "admin") {
        return NextResponse.json(
          { detail: "Forbidden - Admin only" },
          { status: 403 }
        );
      }
    }

    const url = `${BACKEND_URL}/didyouknow${path ? `/${path}` : ''}`;
    const body = await request.json();

    console.log('[Did You Know API] POST request:', url);

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[Did You Know API] Backend error:', errorText);
      return NextResponse.json(
        { error: 'Backend request failed', details: errorText },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('[Did You Know API] Error:', error);
    return NextResponse.json(
      {
        error: 'Internal server error',
        message: error instanceof Error ? error.message : String(error)
      },
      { status: 500 }
    );
  }
}
