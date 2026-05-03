"use client";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { LogIn, LogOut, Database, Save, FolderOpen } from "lucide-react";
import { useSession, signIn, signOut } from "next-auth/react";

interface PrometheusHeaderProps {
  onSave?: () => void;
  onLoad?: () => void;
  onLoginClick?: () => void;
}

export function PrometheusHeader({ onSave, onLoad, onLoginClick }: PrometheusHeaderProps) {
  const { data: session } = useSession();

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="w-full h-12 px-4 flex items-center justify-between">
        {/* Left: Title */}
        <div className="flex items-center gap-2 h-full">
          <Database className="h-4 w-4 text-primary" />
          <h1 className="text-sm font-semibold tracking-tight text-foreground">
            the map
          </h1>
        </div>

        {/* Right: Actions, Theme & Auth */}
        <div className="flex items-center gap-2 h-full">
          <div className="flex items-center gap-1 mr-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              onClick={onSave}
              title="프로메테우스 저장"
            >
              <Save className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              onClick={onLoad}
              title="프로메테우스 불러오기"
            >
              <FolderOpen className="h-4 w-4" />
            </Button>
          </div>

          <div className="scale-90">
            <ThemeToggle />
          </div>
          
          <div className="h-4 w-[1px] bg-border mx-1" />

          {session ? (
            <div className="flex items-center gap-2 h-full">
              <span className="text-xs text-muted-foreground hidden sm:inline-block">
                {session.user?.name}
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => signOut()}
                title="로그아웃"
              >
                <LogOut className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <div className="flex items-center h-full">
              <Button
                variant="ghost"
                size="sm"
                onClick={onLoginClick}
                className="gap-2 h-8 text-xs"
              >
                <LogIn className="h-3.5 w-3.5" />
                <span>로그인</span>
              </Button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}