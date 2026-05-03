"use client";

import { useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import { Header, Footer } from "@/components";
import { getAllFacts, generateFacts, getArticlesWithAPIs, getArticlesWithAPIsHybrid, type Fact, type ArticleWithAPIs } from "@/lib/api";
import { ChevronLeft, ChevronRight, Pause, Play, Sparkles, Newspaper } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GenerateFactsModal, type GenerateConfig } from "@/components/GenerateFactsModal";
import { RelatedAPIsGrid } from "@/components/RelatedAPIsGrid";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

// 카테고리 레이블 매핑
const CATEGORY_LABELS: Record<string, string> = {
  api_introduction: "API 소개",
  provider_introduction: "제공 기관",
  usage_tip: "활용 팁",
  api_statistics: "API 통계",
};

// 카테고리 색상 매핑
const CATEGORY_COLORS: Record<string, string> = {
  api_introduction: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  provider_introduction: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  usage_tip: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300",
  api_statistics: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
};

export default function DidYouKnowPage() {
  const { data: session } = useSession();
  const isAdmin = session?.user?.role === "admin";

  const [facts, setFacts] = useState<Fact[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // 관련 API 기능
  const [articlesWithAPIs, setArticlesWithAPIs] = useState<ArticleWithAPIs[]>([]);
  const [selectedArticleIndex, setSelectedArticleIndex] = useState<number | null>(null);
  const [loadingArticles, setLoadingArticles] = useState(false);

  // 하이브리드 RAG 기능
  const [hybridArticles, setHybridArticles] = useState<ArticleWithAPIs[]>([]);
  const [loadingHybrid, setLoadingHybrid] = useState(false);
  const [showHybrid, setShowHybrid] = useState(true); // 하이브리드 결과 표시 토글

  // 선택된 기사의 관련 API (미리 계산된 결과에서 동기적 추출)
  const relatedAPIs = selectedArticleIndex
    ? (articlesWithAPIs.find(a => a.index === selectedArticleIndex)?.related_apis ?? [])
    : [];

  // 데이터 로드
  useEffect(() => {
    async function loadFacts() {
      setLoading(true);
      setError(null);

      try {
        const result = await getAllFacts(selectedCategory || undefined);

        if (result.success) {
          setFacts(result.data.facts);
          setCurrentIndex(0); // 필터 변경 시 첫 번째로 리셋
        } else {
          setError(result.error.message);
        }
      } catch (err) {
        setError("데이터를 불러오는데 실패했습니다.");
        console.error("Failed to load facts:", err);
      } finally {
        setLoading(false);
      }
    }

    loadFacts();
  }, [selectedCategory]);

  // 신문기사 및 관련 API 로드 (미리 계산된 결과)
  useEffect(() => {
    async function loadArticlesWithAPIs() {
      setLoadingArticles(true);
      try {
        const result = await getArticlesWithAPIs();
        if (result.success) {
          setArticlesWithAPIs(result.data);
        } else {
          console.error("Failed to load articles with APIs:", result.error);
        }
      } catch (err) {
        console.error("Failed to load articles with APIs:", err);
      } finally {
        setLoadingArticles(false);
      }
    }

    loadArticlesWithAPIs();
  }, []);

  // 하이브리드 RAG 결과 로드
  useEffect(() => {
    async function loadHybridResults() {
      setLoadingHybrid(true);
      try {
        const result = await getArticlesWithAPIsHybrid(true, false);
        if (result.success) {
          setHybridArticles(result.data);
        } else {
          console.error("Failed to load hybrid results:", result.error);
        }
      } catch (err) {
        console.error("Failed to load hybrid results:", err);
      } finally {
        setLoadingHybrid(false);
      }
    }

    if (showHybrid) {
      loadHybridResults();
    }
  }, [showHybrid]);

  // 슬라이드쇼 자동 전환 (5초)
  useEffect(() => {
    if (isPaused || facts.length === 0) return;

    const timer = setInterval(() => {
      setCurrentIndex((prev) => (prev + 1) % facts.length);
    }, 5000);

    return () => clearInterval(timer);
  }, [facts.length, isPaused]);

  // 네비게이션 핸들러
  const goToNext = useCallback(() => {
    setCurrentIndex((prev) => (prev + 1) % facts.length);
  }, [facts.length]);

  const goToPrev = useCallback(() => {
    setCurrentIndex((prev) => (prev - 1 + facts.length) % facts.length);
  }, [facts.length]);

  const goToIndex = useCallback((index: number) => {
    setCurrentIndex(index);
  }, []);

  // 관리자 콘텐츠 생성
  const handleGenerate = async (config: GenerateConfig) => {
    if (!isAdmin) return;

    setIsGenerating(true);
    setIsModalOpen(false);

    try {
      const result = await generateFacts(config);

      if (result.success) {
        alert(
          `성공적으로 ${result.data.generated_count}개의 사실을 생성했습니다!`
        );

        // 데이터 새로고침
        const refreshResult = await getAllFacts(selectedCategory || undefined);
        if (refreshResult.success) {
          setFacts(refreshResult.data.facts);
          setCurrentIndex(0);
        }
      } else {
        // 에러를 콘솔에만 기록 (alert 띄우지 않음)
        console.error(`콘텐츠 생성 실패: ${result.error.message}`);

        // 데이터 새로고침 시도 (백그라운드에서 생성이 완료되었을 수 있음)
        const refreshResult = await getAllFacts(selectedCategory || undefined);
        if (refreshResult.success) {
          setFacts(refreshResult.data.facts);
          setCurrentIndex(0);
        }
      }
    } catch (err) {
      // 에러를 콘솔에만 기록 (alert 띄우지 않음)
      console.error("콘텐츠 생성 중 오류:", err);

      // 데이터 새로고침 시도 (백그라운드에서 생성이 완료되었을 수 있음)
      const refreshResult = await getAllFacts(selectedCategory || undefined);
      if (refreshResult.success) {
        setFacts(refreshResult.data.facts);
        setCurrentIndex(0);
      }
    } finally {
      setIsGenerating(false);
    }
  };

  // 로딩 상태
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-lg text-gray-700 dark:text-gray-300">로딩 중...</p>
        </div>
      </div>
    );
  }

  // 에러 상태
  if (error) {
    return (
      <div className="min-h-screen bg-background flex flex-col">
        <Header />
        <main className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <p className="text-xl text-red-600 mb-4">에러 발생</p>
            <p className="text-gray-600 dark:text-gray-400">{error}</p>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  // 빈 상태
  if (facts.length === 0) {
    return (
      <div className="min-h-screen bg-background flex flex-col">
        <Header />
        <main className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <p className="text-xl text-gray-600 dark:text-gray-400 mb-4">
              아직 생성된 사실이 없습니다.
            </p>
            <p className="text-sm text-gray-500">
              백엔드 서버가 초기 콘텐츠를 생성 중일 수 있습니다.
            </p>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  const currentFact = facts[currentIndex];

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800 flex flex-col">
      <Header />

      <main className="flex-1 container mx-auto px-4 py-8 md:py-16">
        {/* 제목 */}
        <div className="text-center mb-8 md:mb-12 relative">
          <h1 className="text-4xl md:text-5xl font-extrabold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-600 dark:from-blue-400 dark:to-indigo-400">
            그거 아셨나요?
          </h1>
          <p className="text-lg md:text-xl text-gray-700 dark:text-gray-300">
            공공데이터 포털의 숨겨진 보물을 발견하세요
          </p>

          {/* 관리자 버튼 (admin만 표시) */}
          {isAdmin && (
            <div className="absolute top-0 right-0">
              <Button
                onClick={() => setIsModalOpen(true)}
                disabled={isGenerating}
                size="sm"
                className="flex items-center gap-2"
              >
                <Sparkles className="w-4 h-4" />
                {isGenerating ? "생성 중..." : "콘텐츠 생성"}
              </Button>
            </div>
          )}
        </div>

        {/* 슬라이드쇼 컨테이너 */}
        <div className="max-w-4xl mx-auto mb-8 relative">
          {/* 카드 */}
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl p-8 md:p-12 min-h-[300px] md:min-h-[400px] flex flex-col justify-center items-center transition-all duration-500">
            {/* 카테고리 배지 */}
            <div className={`inline-block px-4 py-2 rounded-full text-sm font-semibold mb-6 ${CATEGORY_COLORS[currentFact.category] || "bg-gray-100 text-gray-700"}`}>
              {CATEGORY_LABELS[currentFact.category] || currentFact.category}
            </div>

            {/* 콘텐츠 */}
            <p className="text-2xl md:text-3xl font-bold text-center leading-relaxed text-gray-900 dark:text-gray-100 px-4">
              {currentFact.content}
            </p>

            {/* 메타데이터 (선택적) */}
            <div className="mt-6 flex flex-col items-center gap-2">
              {currentFact.metadata?.provider && (
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  출처: {currentFact.metadata.provider}
                </p>
              )}

              {/* API 문서 링크 */}
              {currentFact.metadata?.doc_url && (
                <a
                  href={currentFact.metadata.doc_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors shadow-sm hover:shadow-md"
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                    />
                  </svg>
                  API 문서 보러가기
                </a>
              )}
            </div>
          </div>

          {/* 이전 버튼 */}
          <button
            onClick={goToPrev}
            className="absolute left-4 top-1/2 -translate-y-1/2 bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full p-3 shadow-lg transition-all"
            aria-label="이전"
          >
            <ChevronLeft className="w-6 h-6 text-gray-700 dark:text-gray-300" />
          </button>

          {/* 다음 버튼 */}
          <button
            onClick={goToNext}
            className="absolute right-4 top-1/2 -translate-y-1/2 bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full p-3 shadow-lg transition-all"
            aria-label="다음"
          >
            <ChevronRight className="w-6 h-6 text-gray-700 dark:text-gray-300" />
          </button>
        </div>

        {/* 컨트롤 (인디케이터 + 재생/정지) */}
        <div className="flex items-center justify-center gap-6 mb-8">
          {/* 재생/정지 버튼 */}
          <button
            onClick={() => setIsPaused(!isPaused)}
            className="bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-full p-3 shadow-lg transition-all"
            aria-label={isPaused ? "재생" : "일시정지"}
          >
            {isPaused ? (
              <Play className="w-5 h-5 text-gray-700 dark:text-gray-300" />
            ) : (
              <Pause className="w-5 h-5 text-gray-700 dark:text-gray-300" />
            )}
          </button>

          {/* 인디케이터 점 */}
          <div className="flex gap-2">
            {facts.slice(0, Math.min(facts.length, 10)).map((_, index) => (
              <button
                key={index}
                onClick={() => goToIndex(index)}
                className={`transition-all rounded-full ${
                  index === currentIndex
                    ? "bg-blue-600 dark:bg-blue-400 w-8 h-2"
                    : "bg-gray-300 dark:bg-gray-600 w-2 h-2 hover:bg-gray-400"
                }`}
                aria-label={`${index + 1}번째 사실로 이동`}
              />
            ))}
            {facts.length > 10 && (
              <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">
                +{facts.length - 10}
              </span>
            )}
          </div>
        </div>

        {/* 카테고리 필터 */}
        <div className="flex flex-wrap justify-center gap-3">
          <button
            onClick={() => setSelectedCategory(null)}
            className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
              selectedCategory === null
                ? "bg-blue-600 text-white shadow-lg"
                : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
            }`}
          >
            전체
          </button>
          {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setSelectedCategory(key)}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                selectedCategory === key
                  ? "bg-blue-600 text-white shadow-lg"
                  : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* 총 개수 표시 */}
        <div className="text-center mt-8">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            총 {facts.length}개의 흥미로운 사실
          </p>
        </div>

        {/* AI 추천 API 섹션 (하이브리드 RAG) */}
        {showHybrid && (
          <div className="mt-16 max-w-7xl mx-auto">
            <div className="text-center mb-8">
              <div className="flex items-center justify-center gap-3 mb-4">
                <Sparkles className="w-8 h-8 text-purple-600 dark:text-purple-400" />
                <h2 className="text-3xl md:text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-600 to-pink-600 dark:from-purple-400 dark:to-pink-400">
                  AI가 추천하는 관련 API
                </h2>
                <span className="inline-block px-3 py-1 text-xs font-bold bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-full">
                  NEW
                </span>
              </div>
              <p className="text-lg text-gray-700 dark:text-gray-300 mb-2">
                최신 뉴스 기사를 AI가 분석하여 가장 관련성 높은 API를 추천합니다
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                하이브리드 RAG (키워드 + LLM 재랭킹) 기술 적용
              </p>
            </div>

            {loadingHybrid && (
              <div className="text-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto mb-4"></div>
                <p className="text-lg text-gray-700 dark:text-gray-300">AI가 분석 중...</p>
              </div>
            )}

            {!loadingHybrid && hybridArticles.length > 0 && (
              <div className="space-y-8">
                {hybridArticles.slice(0, 5).map((article) => (
                  <div
                    key={article.index}
                    className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 hover:shadow-xl transition-shadow"
                  >
                    <div className="flex items-start gap-4 mb-4">
                      <div className="flex-shrink-0 w-12 h-12 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg flex items-center justify-center text-white font-bold text-lg">
                        {article.index}
                      </div>
                      <div className="flex-1">
                        <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-2">
                          {article.title}
                        </h3>
                        <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
                          {article.article_preview}
                        </p>
                        <div className="mt-2 flex items-center gap-2 text-xs">
                          <span className="px-2 py-1 bg-purple-100 dark:bg-purple-900 text-purple-700 dark:text-purple-300 rounded">
                            {article.match_method === 'hybrid_rag' ? 'AI 매칭' : '키워드 매칭'}
                          </span>
                          <span className="text-gray-500 dark:text-gray-400">
                            조회수: {article.count.toLocaleString()}
                          </span>
                        </div>
                      </div>
                    </div>

                    {article.related_apis.length > 0 && (
                      <div className="mt-4 pl-16">
                        <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
                          추천 API (상위 {article.related_apis.length}개)
                        </h4>
                        <div className="grid gap-3">
                          {article.related_apis.map((api, idx) => (
                            <div
                              key={api.id}
                              className="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                            >
                              <div className="flex-shrink-0 w-6 h-6 bg-gradient-to-br from-blue-500 to-indigo-500 rounded text-white text-xs font-bold flex items-center justify-center">
                                {idx + 1}
                              </div>
                              <div className="flex-1 min-w-0">
                                <a
                                  href={api.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline line-clamp-1"
                                >
                                  {api.title}
                                </a>
                                <p className="text-xs text-gray-600 dark:text-gray-400 mt-1 line-clamp-2">
                                  {api.description}
                                </p>
                                <div className="flex items-center gap-2 mt-2 text-xs text-gray-500 dark:text-gray-400">
                                  <span>{api.provider}</span>
                                  {api.rank_method && (
                                    <span className="px-2 py-0.5 bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 rounded">
                                      {api.rank_method === 'llm_reranked' ? 'AI 선택' : '키워드'}
                                    </span>
                                  )}
                                  <span>점수: {api.score.toFixed(1)}</span>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}

                {hybridArticles.length > 5 && (
                  <div className="text-center">
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      그 외 {hybridArticles.length - 5}개 기사의 추천 결과가 더 있습니다
                    </p>
                  </div>
                )}
              </div>
            )}

            {!loadingHybrid && hybridArticles.length === 0 && (
              <div className="text-center py-12 bg-white dark:bg-gray-800 rounded-xl">
                <p className="text-lg text-gray-600 dark:text-gray-400">
                  아직 AI 추천 결과가 생성되지 않았습니다.
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-500 mt-2">
                  백엔드에서 /didyouknow/regenerate-article-matches를 호출하여 생성할 수 있습니다.
                </p>
              </div>
            )}
          </div>
        )}

        {/* 관련 API 문서 섹션 */}
        <div className="mt-16 max-w-7xl mx-auto">
          <div className="text-center mb-8">
            <div className="flex items-center justify-center gap-3 mb-4">
              <Newspaper className="w-8 h-8 text-blue-600 dark:text-blue-400" />
              <h2 className="text-3xl md:text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-600 dark:from-blue-400 dark:to-indigo-400">
                뉴스로 찾는 관련 API
              </h2>
            </div>
            <p className="text-lg text-gray-700 dark:text-gray-300 mb-6">
              최신 뉴스 기사를 선택하면 관련된 공공데이터 API를 추천해드립니다
            </p>

            {/* 신문기사 선택 */}
            <div className="max-w-2xl mx-auto">
              <Select
                value={selectedArticleIndex?.toString() || ""}
                onValueChange={(value) => setSelectedArticleIndex(value ? parseInt(value) : null)}
              >
                <SelectTrigger className="w-full h-12 text-base">
                  <SelectValue placeholder="신문기사를 선택하세요..." />
                </SelectTrigger>
                <SelectContent className="max-h-80">
                  {articlesWithAPIs.map((article) => (
                    <SelectItem key={article.index} value={article.index.toString()}>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500">#{article.index}</span>
                        <span className="truncate max-w-md">{article.title}</span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* 관련 API 그리드 */}
          {loadingArticles && (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <p className="text-lg text-gray-700 dark:text-gray-300">기사 목록을 불러오는 중...</p>
            </div>
          )}

          {!loadingArticles && relatedAPIs.length > 0 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
                  추천 API 목록 (총 {relatedAPIs.length}개)
                </h3>
                <p className="text-sm text-muted-foreground">
                  유사도 순으로 정렬됨
                </p>
              </div>
              <RelatedAPIsGrid apis={relatedAPIs} />
            </div>
          )}

          {!loadingArticles && selectedArticleIndex && relatedAPIs.length === 0 && (
            <div className="text-center py-12">
              <p className="text-lg text-gray-600 dark:text-gray-400">
                관련된 API를 찾을 수 없습니다.
              </p>
            </div>
          )}
        </div>
      </main>

      {/* 콘텐츠 생성 모달 */}
      <GenerateFactsModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onGenerate={handleGenerate}
        isGenerating={isGenerating}
      />

      <Footer />
    </div>
  );
}
