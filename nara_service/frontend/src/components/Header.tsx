"use client";

import { useState } from "react";
import { ApiResponse } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Loader2, XCircle, CheckCircle2, Database, LogIn, LogOut, User, FlaskConical, Network } from "lucide-react";
import { useSession, signOut } from "next-auth/react";
import Link from "next/link";
import { LoginModal } from "@/components/LoginModal";
import { Home, Lightbulb } from "lucide-react";

interface HeaderProps {
  loading?: boolean;
  error?: string | null;
  apiData?: ApiResponse | null;
}

export default function Header({ loading, error, apiData }: HeaderProps = {}) {
  const { data: session } = useSession();
  const [loginModalOpen, setLoginModalOpen] = useState(false);

  // API 상태 배지를 표시할지 여부 (props가 전달된 경우에만)
  const showApiStatus = loading !== undefined || error !== undefined || apiData !== undefined;

  return (
    <>
      <LoginModal open={loginModalOpen} onOpenChange={setLoginModalOpen} />
    <header className="sticky top-0 z-50 w-full border-b border-border dark:border-neutral-800 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-20 items-center justify-between">
          {/* Logo & Title */}
          <div className="flex items-center gap-4">
            <div className="rounded-xl bg-primary p-3">
              <Database className="h-6 w-6 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">
                NARA Service
              </h1>
              <p className="text-sm text-muted-foreground">
                공공데이터 포털 대시보드
              </p>
            </div>
          </div>

          {/* Connection Status & Navigation & Theme Toggle & Auth */}
          <div className="flex items-center gap-2 sm:gap-4">
            {showApiStatus && (
              <>
                <div className="hidden lg:flex items-center gap-2">
                  {loading && (
                    <Badge variant="secondary" className="gap-1.5 p-1.5">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    </Badge>
                  )}
                  {error && (
                    <Badge variant="destructive" className="gap-1.5 p-1.5">
                      <XCircle className="h-3.5 w-3.5" />
                    </Badge>
                  )}
                  {apiData && (
                    <Badge className="gap-1.5 p-1.5 bg-green-600 hover:bg-green-700 text-white">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                    </Badge>
                  )}
                </div>
                <Separator orientation="vertical" className="h-6 hidden lg:block" />
              </>
            )}

            <Link href="/">
              <Button variant="outline" size="sm" className="gap-2">
                <Home className="h-4 w-4" />
                <span className="hidden sm:inline">Home</span>
              </Button>
            </Link>

            <Link href="/didyouknow">
              <Button variant="outline" size="sm" className="gap-2">
                <Lightbulb className="h-4 w-4" />
                <span className="hidden sm:inline">Did You Know</span>
              </Button>
            </Link>

            <Link href="/search">
              <Button variant="outline" size="sm" className="gap-2">
                <FlaskConical className="h-4 w-4" />
                <span className="hidden sm:inline">RAG 검색</span>
              </Button>
            </Link>

            <Link href="/prometheus">
              <Button variant="outline" size="sm" className="gap-2">
                <Network className="h-4 w-4" />
                <span className="hidden sm:inline">Graph</span>
              </Button>
            </Link>

            <Separator orientation="vertical" className="h-6 hidden lg:block" />

            <ThemeToggle />

            {session ? (
              <div className="flex items-center gap-3">
                <div className="hidden sm:flex flex-col items-end">
                  <span className="text-sm font-medium">{session.user?.name}</span>
                  <span className="text-xs text-muted-foreground">{session.user?.email}</span>
                </div>
                <Button 
                  variant="ghost" 
                  size="icon"
                  onClick={() => signOut()}
                  title="로그아웃"
                >
                  <LogOut className="h-5 w-5" />
                </Button>
              </div>
            ) : (
              <Button
                onClick={() => setLoginModalOpen(true)}
                className="gap-2"
              >
                <LogIn className="h-4 w-4" />
                <span className="hidden sm:inline">로그인</span>
              </Button>
            )}
          </div>
        </div>
      </div>
    </header>
    </>
  );
}
