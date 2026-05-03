import { Mail, Github, ExternalLink } from "lucide-react";
import { Separator } from "@/components/ui/separator";

export default function Footer() {
  return (
    <footer className="border-t bg-muted/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* About Section */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">공공데이터 RAG 검색</h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              AI 기반 자연어 처리로 공공데이터를 쉽고 빠르게 찾아보세요.
              <br />
              복잡한 검색 없이 대화하듯이 원하는 데이터를 찾을 수 있습니다.
            </p>
          </div>

          {/* Contact Section */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">문의 및 의견</h3>
            <div className="space-y-3">
              <a
                href="mailto:tkddls8848@gmail.com"
                className="flex items-center gap-3 text-sm text-muted-foreground hover:text-primary transition-colors group"
              >
                <div className="rounded-full bg-primary/10 p-2 group-hover:bg-primary/20 transition-colors">
                  <Mail className="h-4 w-4" />
                </div>
                <div>
                  <div className="font-medium text-foreground">이메일 문의</div>
                  <div className="text-xs">tkddls8848@gmail.com</div>
                </div>
              </a>
              <p className="text-xs text-muted-foreground pl-11">
                사용 관련 문의사항이나 사이트 이용에 대한 의견을 보내주세요.
              </p>
            </div>
          </div>
        </div>

        <Separator className="my-8" />

        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-muted-foreground">
          <p>© 2026 공공데이터 검색 서비스. All rights reserved.</p>
          <p className="text-xs">
            Powered by Claude • OpenAI • Ollama
          </p>
        </div>
      </div>
    </footer>
  );
}
