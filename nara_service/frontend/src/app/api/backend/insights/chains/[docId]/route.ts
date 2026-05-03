import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = (process.env.BACKEND_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const API_KEY = process.env.NEXT_API_ROUTE_KEY || 'dev-api-key-change-in-production';

// GET /api/backend/insights/chains/[docId] - 관계 체인 발견
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ docId: string }> }
) {
  try {
    const { docId } = await params;
    const { searchParams } = new URL(request.url);
    const minLength = searchParams.get('min_length') || '2';
    const maxLength = searchParams.get('max_length') || '4';
    const limit = searchParams.get('limit') || '10';

    const response = await fetch(
      `${BACKEND_URL}/insights/chains/${encodeURIComponent(docId)}?min_length=${minLength}&max_length=${maxLength}&limit=${limit}`,
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
    console.error('Relationship Chains API Error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
