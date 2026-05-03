import { Mail } from "lucide-react";

export default function Footer() {
  return (
    <footer className="border-t bg-muted/30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">공공데이터 Did You Know</h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              AI 기반으로 생성된 공공데이터 포털의 흥미로운 사실들을 탐색해보세요.
            </p>
          </div>

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
            </div>
          </div>
        </div>

        <div className="mt-8 pt-8 border-t flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-muted-foreground">
          <p>© 2026 Did You Know Service. All rights reserved.</p>
          <p className="text-xs">
            Powered by Claude
          </p>
        </div>
      </div>
    </footer>
  );
}
