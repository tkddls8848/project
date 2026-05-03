"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { LLMType, FeedbackType } from "@/types";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ThumbsUp, ThumbsDown, Lightbulb, CheckCircle2, BrainCircuit, Loader2, Send, Search, XCircle, LayoutGrid } from "lucide-react";
import { OllamaIcon, ChatGPTIcon, GeminiIcon, ClaudeIcon } from "@/components/icons";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { submitQuery, saveFeedback } from "@/lib/api";
import RelatedDocumentsSection from "@/components/RelatedDocumentsSection";


const DESCRIPTION_MESSAGES = [
  "말하듯이 검색하면 딱 맞는 데이터를 찾아드려요",
  "궁금한 것을 물어보면 필요한 데이터를 찾아드립니다",
  "편하게 물어보세요, 원하는 데이터를 찾아드릴게요",
  "어떤 데이터가 필요하세요? 편하게 물어보세요",
  "궁금한 데이터를 대화하듯 찾아보세요",
  "말로 설명하면 AI가 딱 맞는 데이터를 찾아드려요",
  "AI가 수많은 공공데이터 중에서 꼭 필요한 것만 찾아드립니다",
  "복잡한 검색 없이, 말로 물어보면 정확한 데이터를 추천받아보세요"
];

export default function QuerySection({ 
  onToggleDataList, 
  isDataListVisible 
}: { 
  onToggleDataList?: () => void, 
  isDataListVisible?: boolean 
}) {
  const [query, setQuery] = useState("");
  const [fullResponse, setFullResponse] = useState<string | null>(null);
  const [displayedResponse, setDisplayedResponse] = useState<string>("");
  const [queryLoading, setQueryLoading] = useState(false);
  const [llmType, setLlmType] = useState<LLMType>("ollama");
  const [feedback, setFeedback] = useState<FeedbackType>(null);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [descriptionMessage, setDescriptionMessage] = useState(""); // Re-introduced
  const [relatedDocuments, setRelatedDocuments] = useState<any[]>([]);
  const [contextInsights, setContextInsights] = useState<string[]>([]);
  const { data: session } = useSession();

  useEffect(() => { // Re-introduced
    const randomIndex = Math.floor(Math.random() * DESCRIPTION_MESSAGES.length);
    setDescriptionMessage(DESCRIPTION_MESSAGES[randomIndex]);
  }, []);

  // Typewriter effect logic
  useEffect(() => {
    if (!fullResponse) {
      setDisplayedResponse("");
      return;
    }

    if (displayedResponse !== fullResponse) {
      const timeout = setTimeout(() => {
        const delta = fullResponse.length - displayedResponse.length;
        const chunk = Math.max(1, Math.min(delta, 5));
        setDisplayedResponse(fullResponse.slice(0, displayedResponse.length + chunk));
      }, 15);
      return () => clearTimeout(timeout);
    }
  }, [fullResponse, displayedResponse]);

  const handleQuerySubmit = async () => {
    if (!query.trim() || queryLoading) return;

    setQueryLoading(true);
    setFullResponse("");
    setDisplayedResponse("");
    setFeedback(null);
    setFeedbackSubmitted(false);
    setRelatedDocuments([]);
    setContextInsights([]);

    try {
      const response = await submitQuery(query, llmType, (token) => {
        setFullResponse((prev) => (prev || "") + token);
      });
      setFullResponse(response.message);

      // Neo4j 관련 문서 및 인사이트 저장
      if (response.related_documents) {
        setRelatedDocuments(response.related_documents);
      }
      if (response.context_insights) {
        setContextInsights(response.context_insights);
      }
    } catch (error) {
      console.error("Query failed:", error);
      setFullResponse("오류가 발생했습니다. 다시 시도해주세요.");
    } finally {
      setQueryLoading(false);
    }
  };

  const handleFeedback = async (newFeedback: "like" | "dislike") => {
    if (!fullResponse) return;
    setFeedback(newFeedback);
    setFeedbackSubmitted(false);
    try {
      await saveFeedback(query, fullResponse, newFeedback, llmType, session?.user?.email || "");
      setFeedbackSubmitted(true);
      setTimeout(() => setFeedbackSubmitted(false), 3000);
    } catch (error) {
      console.error("Feedback submission failed:", error);
    }
  };

  const showCursor = queryLoading || (fullResponse && displayedResponse.length < fullResponse.length);

  return (
    <div className="flex flex-col items-center w-full max-w-3xl mx-auto space-y-8">
      {/* Hero Section - Restored */}
      <div className="text-center space-y-4 px-4">
        <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight text-foreground">
          무엇을 도와드릴까요?
        </h1>
        <p className={`text-lg sm:text-xl text-muted-foreground max-w-3xl mx-auto text-balance min-h-[1.75rem] transition-opacity duration-700 ease-in-out ${descriptionMessage ? "opacity-100" : "opacity-0"}`}>
          {descriptionMessage || "말하듯이 검색하면 딱 맞는 데이터를 찾아드려요"}
        </p>
      </div>

      {/* Search Bar Section */}
      <div className="w-full relative group">
        <div className="relative flex items-center w-full">
          <Search className="absolute left-5 h-5 w-5 text-muted-foreground" />
          <Input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleQuerySubmit()}
            placeholder="검색어를 입력하거나 AI에게 질문하세요"
            disabled={queryLoading}
            className="h-14 text-lg pl-12 pr-14 w-full rounded-full border border-gray-200 dark:border-gray-700 shadow-sm hover:shadow-md focus-visible:ring-0 focus-visible:border-primary/50 transition-shadow bg-background"
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
            onClick={handleQuerySubmit}
            disabled={queryLoading || !query.trim()}
            variant="ghost"
            size="icon"
            className="absolute right-3 top-1/2 -translate-y-1/2 h-10 w-10 rounded-full hover:bg-muted"
          >
            {queryLoading ? <Loader2 className="h-5 w-5 animate-spin text-primary" /> : <Send className="h-5 w-5 text-primary" />}
          </Button>
        </div>
      </div>

      {/* Action Buttons Row */}
      <div className="flex flex-wrap items-center justify-center gap-4 w-full">
        {/* LLM Selector */}
        <div className="flex items-center">
          <Select value={llmType} onValueChange={(value) => setLlmType(value as LLMType)} disabled={queryLoading}>
            <SelectTrigger className="h-10 px-4 min-w-[140px] rounded-md border-0 bg-muted/50 hover:bg-muted/80 focus:ring-0 gap-2">
              <div className="flex items-center gap-2">
                {llmType === "openai" && <ChatGPTIcon className="w-4 h-4" />}
                {llmType === "ollama" && <OllamaIcon className="w-4 h-4" />}
                {llmType === "gemini" && <GeminiIcon className="w-4 h-4" />}
                {llmType === "claude" && <ClaudeIcon className="w-4 h-4" />}
                <SelectValue placeholder="모델 선택" />
              </div>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="openai"><span className="font-medium">ChatGPT</span></SelectItem>
              <SelectItem value="ollama"><span className="font-medium">Ollama</span></SelectItem>
              <SelectItem value="gemini"><span className="font-medium">Gemini (미구현)</span></SelectItem>
              <SelectItem value="claude"><span className="font-medium">Claude (미구현)</span></SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Data List Toggle Button */}
        {onToggleDataList && (
          <Button
            variant="secondary"
            onClick={onToggleDataList}
            className="h-10 px-6 bg-muted/50 hover:bg-muted/80 border-0"
          >
            <LayoutGrid className="mr-2 h-4 w-4" />
            데이터 목록 {isDataListVisible ? "숨기기" : "보기"}
          </Button>
        )}
      </div>

      {llmType === "ollama" && !queryLoading && !fullResponse && (
        <div className="text-sm text-muted-foreground flex items-center gap-1.5 animate-in fade-in slide-in-from-top-2">
          <Lightbulb className="h-4 w-4" />
          <span>Ollama는 초기 실행 시 시간이 소요될 수 있습니다</span>
        </div>
      )}

      {/* Response Display Area */}
      {(queryLoading || displayedResponse) && (
        <div className="w-full pt-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <Card className="border shadow-lg bg-card/80 backdrop-blur-sm">
            <CardContent className="p-6 space-y-4">
              {/* Loading Skeleton */}
              {queryLoading && !displayedResponse && (
                <div className="space-y-4">
                  <div className="flex items-center gap-3 mb-4">
                    <Skeleton className="h-8 w-8 rounded-full" />
                    <Skeleton className="h-4 w-32" />
                  </div>
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-3/4" />
                </div>
              )}

              {/* Actual Response */}
              {displayedResponse && (
                <>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                      <BrainCircuit className="h-4 w-4" />
                      AI 응답 결과
                    </div>
                  </div>
                  <div className="prose dark:prose-invert max-w-none text-base leading-relaxed whitespace-pre-wrap">
                    {displayedResponse}
                    {showCursor && <span className="inline-block w-1.5 h-4 ml-1 align-middle bg-primary animate-pulse"/>}
                  </div>

                  <Separator className="my-4" />

                  <div className="flex items-center justify-end gap-2">
                    <span className="text-xs text-muted-foreground mr-2">이 답변이 도움이 되었나요?</span>
                    <Button
                      variant={feedback === "like" ? "default" : "ghost"}
                      size="sm"
                      onClick={() => handleFeedback("like")}
                      className="h-8 w-8 p-0 rounded-full"
                    >
                      <ThumbsUp className="h-4 w-4" />
                    </Button>
                    <Button
                      variant={feedback === "dislike" ? "destructive" : "ghost"}
                      size="sm"
                      onClick={() => handleFeedback("dislike")}
                      className="h-8 w-8 p-0 rounded-full"
                    >
                      <ThumbsDown className="h-4 w-4" />
                    </Button>
                  </div>
                  {feedbackSubmitted && (
                    <div className="text-right text-xs text-green-600 font-medium animate-in fade-in">
                      피드백이 반영되었습니다
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Related Documents Section (Neo4j) */}
      {!queryLoading && relatedDocuments.length > 0 && (
        <div className="w-full pt-4">
          <RelatedDocumentsSection
            documents={relatedDocuments}
            insights={contextInsights}
          />
        </div>
      )}
    </div>
  );
}