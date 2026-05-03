import { notFound } from "next/navigation";

type ApiPageProps = {
  params: Promise<{
    type: string;
    id: string;
    endpoint: string;
  }>;
  searchParams: Promise<{
    [key: string]: string | string[] | undefined;
  }>;
};

async function getApiData(
  type: string,
  id: string,
  endpoint: string,
  searchParams: Record<string, string>
) {
  const params = new URLSearchParams(searchParams);

  // 백엔드 URL 구성
  let backendUrl = "";

  if (endpoint === "getAll" || endpoint === "getEach") {
    // /api/fileData/{id}/getAll -> /detail/fileData/{id}/getAll
    // /api/standard/{id}/getEach -> /detail/standard/{id}/getEach
    // /api/link/{id}/getAll -> /detail/link/{id}/getAll
    backendUrl = `http://localhost:8000/detail/${type}/${id}/${endpoint}`;
  } else {
    // 기본 detail 엔드포인트
    backendUrl = `http://localhost:8000/detail/${type}/${id}`;
  }

  // query parameters가 있으면 추가
  const queryString = params.toString();
  if (queryString) {
    backendUrl += `?${queryString}`;
  }

  const res = await fetch(backendUrl, {
    cache: "no-store",
  });

  if (!res.ok) {
    if (res.status === 404) {
      return null;
    }
    throw new Error(`Failed to fetch data: ${res.statusText}`);
  }

  return res.json();
}

export default async function ApiPage({
  params,
  searchParams,
}: ApiPageProps) {
  const { type, id, endpoint } = await params;
  const resolvedSearchParams = await searchParams;

  // searchParams를 문자열 Record로 변환
  const cleanedParams = Object.entries(resolvedSearchParams).reduce((acc, [key, value]) => {
    if (value !== undefined) {
      acc[key] = Array.isArray(value) ? value[0] : value;
    }
    return acc;
  }, {} as Record<string, string>);

  const data = await getApiData(type, id, endpoint, cleanedParams);

  if (!data) {
    notFound();
  }

  return (
    <div className="min-h-screen bg-background p-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-3xl font-bold mb-2">
            {type} API - {id} / {endpoint}
          </h1>
          <p className="text-muted-foreground">
            API Response Data
          </p>
        </div>

        {Object.keys(cleanedParams).length > 0 && (
          <div className="mb-4 flex flex-wrap gap-2 text-sm text-muted-foreground">
            <span>Parameters:</span>
            {Object.entries(cleanedParams).map(([key, value]) => (
              <code key={key} className="bg-muted px-2 py-1 rounded">
                {key}={value}
              </code>
            ))}
          </div>
        )}

        <div className="bg-muted/50 rounded-lg border p-6 overflow-auto">
          <pre className="text-sm">
            <code>{JSON.stringify(data, null, 2)}</code>
          </pre>
        </div>

        <div className="mt-6 text-sm text-muted-foreground">
          <p className="font-semibold mb-2">API Endpoint:</p>
          <code className="bg-muted px-3 py-2 rounded block">
            GET /{type}/{id}/{endpoint}
          </code>
        </div>
      </div>
    </div>
  );
}
