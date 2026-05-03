"use client";

import { Lightbulb, Sparkles } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";

interface HeaderProps {
  onGenerateClick?: () => void;
  isGenerating?: boolean;
}

export default function Header({ onGenerateClick, isGenerating }: HeaderProps) {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-border dark:border-neutral-800 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-20 items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="rounded-xl bg-primary p-3">
              <Lightbulb className="h-6 w-6 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">
                Did You Know?
              </h1>
              <p className="text-sm text-muted-foreground">
                공공데이터 포털 흥미로운 사실
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {onGenerateClick && (
              <Button
                onClick={onGenerateClick}
                disabled={isGenerating}
                size="sm"
                className="flex items-center gap-2"
              >
                <Sparkles className="w-4 h-4" />
                {isGenerating ? "생성 중..." : "콘텐츠 생성"}
              </Button>
            )}
            <ThemeToggle />
          </div>
        </div>
      </div>
    </header>
  );
}
