"use client";

import { useState, useEffect } from "react";
import { useApiConnection } from "@/hooks";
import { Header, Footer } from "@/components";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Search, FileText, Link2, Code2, Database, Loader2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

// ==================== Types ====================
interface EndpointInfo {
  path: string;
  method: string;
  operation_id: string;
  summary: string;
  url_template: string;
  required_params: string[];
  optional_params: string[];
  score: number;
}

interface SearchResult {
  chunk_id: string;
  score: number;
  doc_id: string;
  api_id: string;
  title: string;
  provider: string;
  doc_type: string;
  content_preview: string;
  metadata: Record<string, any>;
  endpoints: EndpointInfo[];
}

interface SearchResponse {
  query: string;
  total_results: number;
  results: SearchResult[];
}

interface StatsResponse {
  total_chunks: number;
  total_documents: number;
  index_size: number;
  doc_types: Record<string, number>;
  storage_path: string;
}

type DocTypeFilter = "all" | "rest_api" | "file_data" | "standard_data";

// ==================== Constants ====================
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const DOC_TYPE_FILTERS: { label: string; value: DocTypeFilter; icon: React.ElementType }[] = [
  { label: "전체", value: "all", icon: FileText },
  { label: "REST API", value: "rest_api", icon: Code2 },
  { label: "파일데이터", value: "file_data", icon: Link2 },
  { label: "표준 데이터", value: "standard_data", icon: Database },
];

const DOC_TYPE_LABELS: Record<string, string> = {
  rest_api: "REST API",
  file_data: "파일데이터",
  standard_data: "표준 데이터",
  metadata_only: "메타데이터",
};

// ==================== Components ====================
function StatsBar({ stats, loading }: { stats: StatsResponse | null; loading: boolean }) {
  if (loading) {
    return (
      <div className="flex justify-center py-4">
        <Skeleton className="h-6 w-64 rounded-full" />
      </div>
    );
  }

  if (!stats) {
    return null;
  }

  return (
    <div className="flex justify-center py-4 animate-in fade-in duration-500">
      <Badge variant="outline" className="text-sm px-4 py-1 gap-2 bg-background/50 backdrop-blur-sm">
        <span className="font-normal text-muted-foreground">검색 가능 데이터:</span>
        <span className="font-semibold text-primary">{stats.total_documents}개 문서</span>
        <span className="text-muted-foreground">/</span>
        <span className="font-semibold text-primary">{stats.total_chunks}개 청크</span>
      </Badge>
    </div>
  );
}

function ResultCard({ result, index }: { result: SearchResult; index: number }) {
  return (
    <Card
      className="group hover:shadow-xl transition-all duration-300 border-border/50 overflow-hidden animate-in fade-in slide-in-from-bottom-4"
      style={{ animationDelay: `${index * 100}ms`, animationFillMode: 'backwards' }}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1.5 flex-1">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-xs font-normal">
                {result.provider}
              </Badge>
              <Badge variant="secondary" className="text-xs font-normal bg-muted/50">
                {DOC_TYPE_LABELS[result.doc_type] || result.doc_type}
              </Badge>
            </div>
            <CardTitle className="text-xl font-bold leading-tight group-hover:text-primary transition-colors">
              {result.title}
            </CardTitle>
          </div>
          <Badge className={cn(
            "px-2.5 py-0.5 text-xs font-semibold transition-colors",
            result.score > 0.8 ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 hover:bg-green-100" :
            result.score > 0.6 ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 hover:bg-blue-100" :
            "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400 hover:bg-gray-100"
          )}>
            {(result.score * 100).toFixed(0)}% 일치
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <CardDescription className="text-sm leading-relaxed whitespace-pre-wrap bg-muted/30 p-4 rounded-lg">
          {result.content_preview}
        </CardDescription>

        {result.endpoints && result.endpoints.length > 0 && (
          <div className="space-y-3 pt-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
              <Code2 className="h-4 w-4" />
              <span>관련 엔드포인트</span>
            </div>
            <div className="grid gap-3">
              {result.endpoints.map((endpoint, idx) => (
                <div key={idx} className="bg-card border rounded-lg p-3 text-sm hover:border-primary/30 transition-colors">
                  <div className="flex items-center gap-3 mb-2">
                    <Badge
                      className={cn(
                        "font-bold uppercase w-16 justify-center shrink-0",
                        endpoint.method === "GET" && "bg-green-500 hover:bg-green-600",
                        endpoint.method === "POST" && "bg-blue-500 hover:bg-blue-600",
                        endpoint.method === "PUT" && "bg-yellow-500 hover:bg-yellow-600",
                        endpoint.method === "DELETE" && "bg-red-500 hover:bg-red-600"
                      )}
                    >
                      {endpoint.method}
                    </Badge>
                    <code className="flex-1 font-mono text-xs bg-muted/50 px-2 py-1 rounded truncate">
                      {endpoint.path}
                    </code>
                  </div>
                  {endpoint.summary && (
                    <p className="text-muted-foreground text-xs pl-[4.5rem]">
                      {endpoint.summary}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function LoadingResults() {
  return (
    <div className="space-y-4 max-w-4xl mx-auto w-full">
      {[...Array(3)].map((_, i) => (
        <Card key={i} className="w-full">
          <CardHeader>
            <div className="flex justify-between items-start gap-4">
              <div className="space-y-3 flex-1">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-6 w-3/4" />
                <Skeleton className="h-5 w-32" />
              </div>
              <Skeleton className="h-6 w-20" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function EmptyState({ query }: { query: string }) {
  const exampleQueries = ["연안 자료 API", "날씨 특보", "대기오염 데이터", "관광 정보 조회"];

  return (
    <div className="flex flex-col items-center justify-center py-20 text-center animate-in fade-in zoom-in-95 duration-500">
      <div className="rounded-full bg-muted/50 p-8 mb-6 ring-1 ring-border">
        <Search className="h-12 w-12 text-muted-foreground" />
      </div>
      <h3 className="text-2xl font-bold tracking-tight mb-3">
        {query ? "검색 결과가 없습니다" : "무엇을 찾고 계신가요?"}
      </h3>
      <p className="text-muted-foreground mb-8 max-w-md text-lg">
        {query ? "다른 키워드로 검색해보세요." : "자연어로 공공데이터 API를 검색하고 실행 가능한 정보를 찾아보세요."}
      </p>
      {!query && (
        <div className="space-y-4">
          <p className="text-sm font-medium text-muted-foreground uppercase tracking-wider">추천 검색어</p>
          <div className="flex flex-wrap gap-2 justify-center max-w-lg mx-auto">
            {exampleQueries.map((example) => (
              <Button
                key={example}
                variant="outline"
                className="rounded-full hover:border-primary/50 hover:bg-primary/5 hover:text-primary transition-all"
                onClick={() => {
                  const input = document.querySelector('input[type="text"]') as HTMLInputElement;
                  if (input) {
                    input.value = example;
                    input.focus();
                    // React state update requires dispatching event if direct DOM manipulation
                    // Ideally pass a handler to EmptyState, but simpler here is just visual cue or handle in parent
                  }
                }}
              >
                {example}
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ==================== Main Component ====================
export default function SearchPage() {
  const { apiData, loading: apiLoading, error: apiError } = useApiConnection();
  
  const [query, setQuery] = useState("");
  const [currentFilter, setCurrentFilter] = useState<DocTypeFilter>("all");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [statsLoading, setStatsLoading] = useState(true);
  const [hasSearched, setHasSearched] = useState(false);

  // Load stats on mount
  useEffect(() => {
    const loadStats = async () => {
      setStatsLoading(true);
      try {
        const response = await fetch(`${API_BASE_URL}/search/stats`);
        if (response.ok) {
          const data = await response.json();
          setStats(data);
        }
      } catch (error) {
        console.error("Failed to load stats:", error);
      } finally {
        setStatsLoading(false);
      }
    };

    loadStats();
  }, []);

  // Search function
  const handleSearch = async () => {
    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      return;
    }

    setLoading(true);
    setHasSearched(true);

    try {
      const requestBody: any = {
        query: trimmedQuery,
        n_results: 5,  // 최종 반환 개수
        initial_results: 20,  // 초기 검색 개수 (그룹핑 전)
      };

      if (currentFilter !== "all") {
        requestBody.doc_type = currentFilter;
      }

      const response = await fetch(`${API_BASE_URL}/search/search`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data: SearchResponse = await response.json();
      setResults(data.results);
    } catch (error) {
      console.error("Search error:", error);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSearch();
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header loading={apiLoading} error={apiError} apiData={apiData} />

      <main className="flex-1 flex flex-col w-full">
        {/* Search Hero Section */}
        <div className="w-full flex flex-col items-center justify-center px-4 sm:px-6 lg:px-8 py-16 transition-all duration-500 ease-in-out">
          <div className="w-full max-w-3xl mx-auto space-y-8">
            <div className="text-center space-y-4">
              <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-foreground">
                공공데이터 RAG 검색
              </h1>
              <p className="text-lg text-muted-foreground text-balance">
                원하는 데이터를 자연어로 질문하고 관련된 API와 문서를 찾아보세요
              </p>
            </div>

            {/* Search Input */}
            <div className="relative group">
              <div className="relative flex items-center w-full">
                <Search className="absolute left-5 h-5 w-5 text-muted-foreground" />
                <Input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="예: 실시간 대기오염 정보, 전국 캠핑장 현황..."
                  className="h-14 text-lg pl-12 pr-14 w-full rounded-full border border-input shadow-sm hover:shadow-md focus-visible:ring-1 focus-visible:ring-primary/50 transition-all bg-background/50 backdrop-blur-sm"
                />
                {query && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="absolute right-14 top-1/2 -translate-y-1/2 h-8 w-8 hover:bg-transparent"
                    onClick={() => setQuery("")}
                  >
                    <XCircle className="h-5 w-5 text-muted-foreground" />
                  </Button>
                )}
                <Button
                  onClick={handleSearch}
                  disabled={loading || !query.trim()}
                  variant="ghost"
                  size="icon"
                  className="absolute right-3 top-1/2 -translate-y-1/2 h-10 w-10 rounded-full hover:bg-muted"
                >
                  {loading ? <Loader2 className="h-5 w-5 animate-spin text-primary" /> : <Search className="h-5 w-5 text-primary" />}
                </Button>
              </div>
            </div>

            {/* Filter Buttons */}
            <div className="flex flex-wrap justify-center gap-3">
              {DOC_TYPE_FILTERS.map((filter) => {
                const Icon = filter.icon;
                const isActive = currentFilter === filter.value;

                return (
                  <Button
                    key={filter.value}
                    variant={isActive ? "default" : "outline"}
                    onClick={() => setCurrentFilter(filter.value)}
                    className={cn(
                      "gap-2 transition-all h-10 rounded-full px-5",
                      isActive && "shadow-md ring-2 ring-primary/20 ring-offset-2 ring-offset-background"
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {filter.label}
                  </Button>
                );
              })}
            </div>

            <StatsBar stats={stats} loading={statsLoading} />
          </div>
        </div>

        {/* Results Section */}
        <div className="w-full max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pb-20">
          {loading ? (
            <LoadingResults />
          ) : !hasSearched ? (
            <EmptyState query="" />
          ) : results.length === 0 ? (
            <EmptyState query={query} />
          ) : (
            <div className="space-y-6 animate-in fade-in slide-in-from-top-4 duration-500">
              <div className="flex items-center justify-between pb-2 border-b">
                <h2 className="text-2xl font-bold tracking-tight">
                  검색 결과
                  <span className="ml-2 text-muted-foreground text-lg font-normal">({results.length}건)</span>
                </h2>
              </div>
              
              <div className="grid gap-6">
                {results.map((result, index) => (
                  <ResultCard key={result.chunk_id} result={result} index={index} />
                ))}
              </div>
            </div>
          )}
        </div>
      </main>

      <Footer />
    </div>
  );
}
