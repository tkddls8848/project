"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface GenerateFactsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onGenerate: (config: GenerateConfig) => void;
  isGenerating: boolean;
}

export interface GenerateConfig {
  counts: {
    api_introduction: number;
    provider_introduction: number;
    usage_tip: number;
  };
  llm_params: {
    temperature: number;
    top_p: number;
    max_tokens: number;
  };
}

export function GenerateFactsModal({
  isOpen,
  onClose,
  onGenerate,
  isGenerating,
}: GenerateFactsModalProps) {
  const [counts, setCounts] = useState({
    api_introduction: 34,
    provider_introduction: 34,
    usage_tip: 34,
  });

  const [llmParams, setLlmParams] = useState({
    temperature: 0.8,
    top_p: 0.9,
    max_tokens: 150,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onGenerate({
      counts,
      llm_params: llmParams,
    });
  };

  if (!isOpen) return null;

  const totalCount =
    counts.api_introduction +
    counts.provider_introduction +
    counts.usage_tip;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4 flex items-center justify-between">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            콘텐츠 생성 설정
          </h2>
          <button
            onClick={onClose}
            disabled={isGenerating}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-50"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          <div>
            <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
              카테고리별 생성 개수
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  API 소개
                </label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={counts.api_introduction}
                  onChange={(e) =>
                    setCounts({
                      ...counts,
                      api_introduction: parseInt(e.target.value) || 0,
                    })
                  }
                  disabled={isGenerating}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 disabled:opacity-50"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  제공 기관 소개
                </label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={counts.provider_introduction}
                  onChange={(e) =>
                    setCounts({
                      ...counts,
                      provider_introduction: parseInt(e.target.value) || 0,
                    })
                  }
                  disabled={isGenerating}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 disabled:opacity-50"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  활용 팁
                </label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={counts.usage_tip}
                  onChange={(e) =>
                    setCounts({
                      ...counts,
                      usage_tip: parseInt(e.target.value) || 0,
                    })
                  }
                  disabled={isGenerating}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 disabled:opacity-50"
                />
              </div>

              <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
                <p className="text-sm font-medium text-blue-900 dark:text-blue-300">
                  총 {totalCount}개의 콘텐츠가 생성됩니다
                </p>
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-gray-100">
              LLM 생성 파라미터
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Temperature: {llmParams.temperature.toFixed(2)}
                  <span className="text-xs text-gray-500 ml-2">
                    (창의성 조절: 낮을수록 일관적, 높을수록 다양함)
                  </span>
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={llmParams.temperature}
                  onChange={(e) =>
                    setLlmParams({
                      ...llmParams,
                      temperature: parseFloat(e.target.value),
                    })
                  }
                  disabled={isGenerating}
                  className="w-full disabled:opacity-50"
                />
                <div className="flex justify-between text-xs text-gray-500">
                  <span>0.0 (일관적)</span>
                  <span>1.0 (창의적)</span>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Top P: {llmParams.top_p.toFixed(2)}
                  <span className="text-xs text-gray-500 ml-2">
                    (다양성 조절)
                  </span>
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={llmParams.top_p}
                  onChange={(e) =>
                    setLlmParams({
                      ...llmParams,
                      top_p: parseFloat(e.target.value),
                    })
                  }
                  disabled={isGenerating}
                  className="w-full disabled:opacity-50"
                />
                <div className="flex justify-between text-xs text-gray-500">
                  <span>0.0</span>
                  <span>1.0</span>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Max Tokens: {llmParams.max_tokens}
                  <span className="text-xs text-gray-500 ml-2">
                    (최대 생성 길이)
                  </span>
                </label>
                <input
                  type="number"
                  min="50"
                  max="500"
                  step="10"
                  value={llmParams.max_tokens}
                  onChange={(e) =>
                    setLlmParams({
                      ...llmParams,
                      max_tokens: parseInt(e.target.value) || 100,
                    })
                  }
                  disabled={isGenerating}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 disabled:opacity-50"
                />
              </div>
            </div>
          </div>

          <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
            <p className="text-sm text-yellow-800 dark:text-yellow-300">
              ⚠️ 콘텐츠 생성에는 5-10분이 소요될 수 있습니다.
              <br />
              기존 facts.json 파일은 삭제되고 새로 생성됩니다.
            </p>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200 dark:border-gray-700">
            <Button
              type="button"
              onClick={onClose}
              disabled={isGenerating}
              variant="outline"
            >
              취소
            </Button>
            <Button type="submit" disabled={isGenerating || totalCount === 0}>
              {isGenerating ? "생성 중..." : "생성 시작"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
