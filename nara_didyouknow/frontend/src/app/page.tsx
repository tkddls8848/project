"use client";

import { useState, useEffect, useCallback } from "react";
import { Header, Footer } from "@/components";
import { getAllFacts, generateFacts, type Fact } from "@/lib/api";
import { ChevronLeft, ChevronRight, Pause, Play, Sparkles, ExternalLink } from "lucide-react";
import { GenerateFactsModal, type GenerateConfig } from "@/components/GenerateFactsModal";
import { cn } from "@/lib/utils";

const CATEGORY_LABELS: Record<string, string> = {
  api_introduction: "API 소개",
  provider_introduction: "제공 기관",
  usage_tip: "활용 팁",
  api_statistics: "API 통계",
};

export default function HomePage() {
  const [facts, setFacts] = useState<Fact[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);

  useEffect(() => {
    async function loadFacts() {
      setLoading(true);
      setError(null);

      try {
        const result = await getAllFacts(selectedCategory || undefined);

        if (result.success) {
          setFacts(result.data.facts);
          setCurrentIndex(0);
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

  useEffect(() => {
    if (isPaused || facts.length === 0) return;

    const timer = setInterval(() => {
      handleTransition(() => {
        setCurrentIndex((prev) => (prev + 1) % facts.length);
      });
    }, 6000);

    return () => clearInterval(timer);
  }, [facts.length, isPaused]);

  const handleTransition = (callback: () => void) => {
    setIsTransitioning(true);
    setTimeout(() => {
      callback();
      setTimeout(() => {
        setIsTransitioning(false);
      }, 50);
    }, 300);
  };

  const goToNext = useCallback(() => {
    handleTransition(() => {
      setCurrentIndex((prev) => (prev + 1) % facts.length);
    });
  }, [facts.length]);

  const goToPrev = useCallback(() => {
    handleTransition(() => {
      setCurrentIndex((prev) => (prev - 1 + facts.length) % facts.length);
    });
  }, [facts.length]);

  const handleGenerate = async (config: GenerateConfig) => {
    setIsGenerating(true);
    setIsModalOpen(false);

    try {
      const result = await generateFacts(config);

      if (result.success) {
        const refreshResult = await getAllFacts(selectedCategory || undefined);
        if (refreshResult.success) {
          setFacts(refreshResult.data.facts);
          setCurrentIndex(0);
        }
      } else {
        console.error(`콘텐츠 생성 실패: ${result.error.message}`);
        const refreshResult = await getAllFacts(selectedCategory || undefined);
        if (refreshResult.success) {
          setFacts(refreshResult.data.facts);
        }
      }
    } catch (err) {
      console.error("콘텐츠 생성 중 오류:", err);
    } finally {
      setIsGenerating(false);
    }
  };

  const currentFact = facts[currentIndex];

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          <p className="text-muted-foreground animate-pulse">지식을 불러오는 중...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background flex flex-col">
        <Header onGenerateClick={() => setIsModalOpen(true)} isGenerating={isGenerating} />
        <main className="flex-1 flex flex-col items-center justify-center p-4">
          <div className="bg-destructive/10 text-destructive px-6 py-4 rounded-lg max-w-md text-center">
            <h3 className="font-semibold mb-2">오류가 발생했습니다</h3>
            <p className="text-sm opacity-90">{error}</p>
          </div>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
          >
            다시 시도
          </button>
        </main>
        <Footer />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-background font-sans selection:bg-primary/20">
      <Header onGenerateClick={() => setIsModalOpen(true)} isGenerating={isGenerating} />

      <main className="flex-1 flex flex-col items-center justify-center p-4 md:p-8 relative overflow-hidden">
        {/* Background Decorative Elements */}
        <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10 opacity-30 pointer-events-none">
          <div className="absolute -top-[20%] -left-[10%] w-[50%] h-[50%] bg-blue-500/10 rounded-full blur-[100px]" />
          <div className="absolute top-[40%] -right-[10%] w-[40%] h-[40%] bg-indigo-500/10 rounded-full blur-[100px]" />
        </div>

        <div className="w-full max-w-5xl mx-auto flex flex-col gap-8 md:gap-12">

          {/* Header Section */}
          <div className="text-center space-y-4">
            <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-indigo-600 dark:from-blue-400 dark:to-indigo-400">
              그거 아셨나요?
            </h1>
            <p className="text-lg md:text-xl text-gray-700 dark:text-gray-300 max-w-2xl mx-auto font-medium">
              공공데이터 포털의 숨겨진 보물을 발견하세요
            </p>
          </div>

          {/* Category Filter */}
          <div className="flex flex-wrap justify-center gap-2">
            <button
              onClick={() => setSelectedCategory(null)}
              className={cn(
                "px-4 py-2 rounded-full text-sm font-medium transition-all duration-300 border",
                selectedCategory === null
                  ? "bg-foreground text-background border-foreground hover:opacity-90"
                  : "bg-background text-muted-foreground border-transparent hover:bg-secondary hover:text-foreground"
              )}
            >
              전체 보기
            </button>
            {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setSelectedCategory(key)}
                className={cn(
                  "px-4 py-2 rounded-full text-sm font-medium transition-all duration-300 border",
                  selectedCategory === key
                    ? "bg-foreground text-background border-foreground hover:opacity-90"
                    : "bg-background text-muted-foreground border-transparent hover:bg-secondary hover:text-foreground"
                )}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Main Card Area */}
          <div className="relative w-full max-w-3xl mx-auto">
            {facts.length > 0 ? (
              <div className="relative group">
                {/* Navigation Buttons (Desktop) */}
                <div className="absolute top-1/2 -left-12 -translate-y-1/2 hidden md:flex flex-col gap-4 z-20">
                  <button
                    onClick={goToPrev}
                    className="p-3 rounded-full bg-background/50 hover:bg-background border border-border shadow-sm hover:shadow-md transition-all backdrop-blur-sm group-hover:-translate-x-2"
                    aria-label="이전"
                  >
                    <ChevronLeft className="w-6 h-6 text-foreground/80" />
                  </button>
                </div>
                <div className="absolute top-1/2 -right-12 -translate-y-1/2 hidden md:flex flex-col gap-4 z-20">
                  <button
                    onClick={goToNext}
                    className="p-3 rounded-full bg-background/50 hover:bg-background border border-border shadow-sm hover:shadow-md transition-all backdrop-blur-sm group-hover:translate-x-2"
                    aria-label="다음"
                  >
                    <ChevronRight className="w-6 h-6 text-foreground/80" />
                  </button>
                </div>

                {/* Card */}
                <div className="bg-card text-card-foreground rounded-[2.5rem] shadow-2xl shadow-primary/5 border border-border/50 overflow-hidden relative min-h-[400px] flex flex-col transition-all duration-500 hover:shadow-primary/10">

                  {/* Card Content */}
                  <div className={cn(
                    "flex-1 flex flex-col justify-center items-center p-8 md:p-12 text-center transition-opacity duration-300",
                    isTransitioning ? "opacity-0 scale-95" : "opacity-100 scale-100"
                  )}>
                    <p className="text-3xl md:text-4xl font-bold leading-[1.6] tracking-wide break-keep text-balance text-foreground/90">
                      {currentFact.content}
                    </p>

                    <div className="mt-10 flex flex-col items-center gap-3 animate-in fade-in slide-in-from-bottom-4 duration-700 delay-100">
                      {currentFact.metadata?.provider && (
                        <span className="inline-flex items-center px-3 py-1 rounded-full bg-secondary text-secondary-foreground text-sm font-medium">
                          {currentFact.metadata.provider}
                        </span>
                      )}

                      {currentFact.metadata?.doc_url && (
                        <a
                          href={currentFact.metadata.doc_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-muted-foreground hover:text-primary transition-colors flex items-center gap-1 mt-2 border-b border-transparent hover:border-primary/50 pb-0.5"
                        >
                          <ExternalLink className="w-3 h-3" />
                          원본 데이터 확인하기
                        </a>
                      )}
                    </div>
                  </div>

                  {/* Mobile Navigation & Progress */}
                  <div className="p-6 border-t border-border/50 bg-secondary/20 flex items-center justify-between">
                    <button
                      onClick={() => setIsPaused(!isPaused)}
                      className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {isPaused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
                      <span className="hidden sm:inline">{isPaused ? "재생" : "일시정지"}</span>
                    </button>

                    <div className="flex gap-1.5">
                      {facts.slice(0, 10).map((_, idx) => (
                        <button
                          key={idx}
                          onClick={() => {
                            handleTransition(() => setCurrentIndex(idx));
                          }}
                          className={cn(
                            "h-1.5 rounded-full transition-all duration-300",
                            idx === currentIndex
                              ? "w-6 bg-primary"
                              : "w-1.5 bg-primary/20 hover:bg-primary/40"
                          )}
                          aria-label={`Go to fact ${idx + 1}`}
                        />
                      ))}
                    </div>

                    <div className="flex md:hidden gap-2">
                       <button onClick={goToPrev} className="p-2 hover:bg-secondary rounded-full">
                         <ChevronLeft className="w-5 h-5" />
                       </button>
                       <button onClick={goToNext} className="p-2 hover:bg-secondary rounded-full">
                         <ChevronRight className="w-5 h-5" />
                       </button>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-card rounded-[2.5rem] border-2 border-dashed border-border p-12 flex flex-col items-center justify-center text-center min-h-[300px]">
                <div className="w-16 h-16 rounded-full bg-secondary flex items-center justify-center mb-4">
                  <Sparkles className="w-8 h-8 text-muted-foreground" />
                </div>
                <h3 className="text-xl font-semibold mb-2">아직 데이터가 없어요</h3>
                <p className="text-muted-foreground mb-6">새로운 지식을 생성해보세요!</p>
                <button
                  onClick={() => setIsModalOpen(true)}
                  className="px-6 py-3 bg-primary text-primary-foreground rounded-xl font-medium shadow-lg shadow-primary/20 hover:shadow-xl hover:shadow-primary/30 transition-all hover:-translate-y-0.5"
                >
                  지식 생성하기
                </button>
              </div>
            )}
          </div>
        </div>
      </main>

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
