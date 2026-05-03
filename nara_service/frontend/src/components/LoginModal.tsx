"use client";

import { signIn } from "next-auth/react";
import {
  Dialog,
  DialogContent,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Lightbulb, X } from "lucide-react";

interface LoginModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function LoginModal({ open, onOpenChange }: LoginModalProps) {
  const handleGoogleLogin = async () => {
    await signIn("google", { callbackUrl: "/" });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-7xl h-[90vh] p-0 gap-0 overflow-hidden">
        {/* Close Button */}
        <button
          onClick={() => onOpenChange(false)}
          className="absolute right-4 top-4 z-50 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground"
        >
          <X className="h-4 w-4" />
          <span className="sr-only">Close</span>
        </button>

        <div className="flex h-full overflow-hidden">
          {/* Left Side - Catchphrase */}
          <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-primary/10 via-primary/5 to-background relative overflow-hidden">
            {/* Background decorative elements */}
            <div className="absolute inset-0 opacity-5">
              <div className="absolute top-20 left-20 w-72 h-72 bg-primary rounded-full blur-3xl"></div>
              <div className="absolute bottom-20 right-20 w-96 h-96 bg-primary rounded-full blur-3xl"></div>
            </div>

            {/* Content */}
            <div className="relative z-10 flex flex-col justify-center px-16 w-full">
              <div className="space-y-8">
                {/* Icon */}
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary/10 backdrop-blur-sm">
                  <Lightbulb className="w-8 h-8 text-primary" />
                </div>

                {/* Main Catchphrase */}
                <div className="space-y-4">
                  <h1 className="text-5xl font-bold tracking-tight text-foreground leading-tight">
                    창조는
                    <br />
                    <span className="text-primary">관점</span>에서
                    <br />
                    시작한다
                  </h1>
                  <div className="w-24 h-1 bg-primary rounded-full"></div>
                </div>

                {/* Subtitle */}
                <p className="text-xl text-muted-foreground leading-relaxed max-w-md">
                  공공데이터의 새로운 관점과 연결을 발견하고,
                  <br />
                  창조적 인사이트를 만들어보세요.
                </p>

                {/* Feature highlights */}
                <div className="space-y-3 pt-4">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-primary"></div>
                    <p className="text-sm text-muted-foreground">AI 기반 문서 관계 분석</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-primary"></div>
                    <p className="text-sm text-muted-foreground">지식 그래프 시각화</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-primary"></div>
                    <p className="text-sm text-muted-foreground">통찰 대화형 인터페이스</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Side - Login Form */}
          <div className="flex w-full lg:w-1/2 items-center justify-center px-4 py-12 overflow-y-auto">
            <div className="w-full max-w-md space-y-8">
              {/* Mobile Catchphrase */}
              <div className="lg:hidden text-center space-y-4 mb-8">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-primary/10">
                  <Lightbulb className="w-6 h-6 text-primary" />
                </div>
                <h2 className="text-3xl font-bold">
                  창조는 <span className="text-primary">관점</span>에서 시작한다
                </h2>
              </div>

              <Card className="shadow-lg border-border/50">
                <CardHeader className="text-center space-y-2 pb-6">
                  <CardTitle className="text-2xl font-bold tracking-tight">로그인</CardTitle>
                  <CardDescription className="text-base">
                    서비스를 이용하기 위해 로그인해주세요
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-4 pb-8">
                  <Button
                    variant="outline"
                    className="w-full h-12 text-base relative hover:bg-muted/50 transition-colors"
                    onClick={handleGoogleLogin}
                  >
                    {/* Google SVG Icon */}
                    <svg className="mr-3 h-5 w-5" viewBox="0 0 24 24">
                      <path
                        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                        fill="#4285F4"
                      />
                      <path
                        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                        fill="#34A853"
                      />
                      <path
                        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                        fill="#FBBC05"
                      />
                      <path
                        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                        fill="#EA4335"
                      />
                    </svg>
                    Google 계정으로 계속하기
                  </Button>

                  <div className="relative">
                    <div className="absolute inset-0 flex items-center">
                      <span className="w-full border-t" />
                    </div>
                    <div className="relative flex justify-center text-xs uppercase">
                      <span className="bg-background px-2 text-muted-foreground">
                        빠르고 안전한 로그인
                      </span>
                    </div>
                  </div>

                  <div className="text-center text-xs text-muted-foreground">
                    로그인하시면{" "}
                    <a href="#" className="underline hover:text-primary transition-colors">
                      이용약관
                    </a>
                    {" "}및{" "}
                    <a href="#" className="underline hover:text-primary transition-colors">
                      개인정보처리방침
                    </a>
                    에 동의하는 것으로 간주됩니다.
                  </div>
                </CardContent>
              </Card>

              {/* Additional Info */}
              <div className="text-center text-sm text-muted-foreground">
                <p>아직 계정이 없으신가요?</p>
                <p className="mt-1">Google 계정으로 바로 시작하실 수 있습니다.</p>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
