import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = (process.env.BACKEND_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const API_KEY = process.env.NEXT_API_ROUTE_KEY || 'dev-api-key-change-in-production';

// GET /api/backend/graph/relationship/[relId] - 관계 조회
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ relId: string }> }
) {
  try {
    const { relId } = await params;

    const response = await fetch(
      `${BACKEND_URL}/graph/relationship/${encodeURIComponent(relId)}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': API_KEY,
        },
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: errorData.detail || 'Backend request failed' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Get Relationship API Error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

// PUT /api/backend/graph/relationship/[relId] - 관계 수정
export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ relId: string }> }
) {
  try {
    const { relId } = await params;
    const body = await request.json();

    const response = await fetch(
      `${BACKEND_URL}/graph/relationship/${encodeURIComponent(relId)}`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': API_KEY,
        },
        body: JSON.stringify(body),
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: errorData.detail || 'Backend request failed' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Update Relationship API Error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

// DELETE /api/backend/graph/relationship/[relId] - 관계 삭제
export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ relId: string }> }
) {
  try {
    const { relId } = await params;

    const response = await fetch(
      `${BACKEND_URL}/graph/relationship/${encodeURIComponent(relId)}`,
      {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': API_KEY,
        },
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: errorData.detail || 'Backend request failed' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Delete Relationship API Error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
