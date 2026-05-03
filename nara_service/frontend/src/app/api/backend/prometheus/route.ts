/**
 * Prometheus CRUD API Proxy Route
 *
 * Why: 프론트엔드에서 백엔드 Prometheus API로 요청을 프록시합니다.
 *      저장된 그래프 관계도를 생성, 조회, 수정, 삭제할 수 있습니다.
 */

import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_API_URL || 'http://127.0.0.1:8000';
const API_KEY = process.env.NEXT_API_ROUTE_KEY || '';

// POST: Create new Prometheus
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    const response = await fetch(`${BACKEND_URL}/prometheus`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: error || 'Failed to create prometheus' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Prometheus create error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

// GET: List all Prometheus for a user
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const userId = searchParams.get('user_id');

    if (!userId) {
      return NextResponse.json(
        { error: 'user_id is required' },
        { status: 400 }
      );
    }

    const response = await fetch(
      `${BACKEND_URL}/prometheus?user_id=${encodeURIComponent(userId)}`,
      {
        method: 'GET',
        headers: {
          'X-API-Key': API_KEY,
        },
      }
    );

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: error || 'Failed to fetch prometheus list' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Prometheus list error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
