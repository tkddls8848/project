import { FileJson } from "lucide-react";

export function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="rounded-full bg-muted p-8 mb-6">
        <FileJson className="h-16 w-16 text-muted-foreground" />
      </div>
      <h3 className="text-2xl font-semibold mb-3">데이터가 없습니다</h3>
      <p className="text-base text-muted-foreground max-w-md">
        선택한 필터에 해당하는 데이터를 찾을 수 없습니다.
        다른 필터를 선택해보세요.
      </p>
    </div>
  );
}
