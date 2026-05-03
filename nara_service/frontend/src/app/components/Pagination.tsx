import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export function Pagination({
  currentPage,
  totalPages,
  onPageChange,
}: PaginationProps) {
  const pages = [];
  const maxVisiblePages = 5;

  let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
  let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);

  if (endPage - startPage < maxVisiblePages - 1) {
    startPage = Math.max(1, endPage - maxVisiblePages + 1);
  }

  for (let i = startPage; i <= endPage; i++) {
    pages.push(i);
  }

  return (
    <div className="flex items-center justify-center gap-2 py-8">
      <Button
        variant="outline"
        size="default"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className="gap-2 h-11 px-4"
      >
        <ChevronLeft className="h-5 w-5" />
        이전
      </Button>

      {startPage > 1 && (
        <>
          <Button
            variant="outline"
            size="default"
            onClick={() => onPageChange(1)}
            className="h-11 min-w-[2.75rem]"
          >
            1
          </Button>
          {startPage > 2 && <span className="px-2 text-base text-muted-foreground">...</span>}
        </>
      )}

      {pages.map((page) => (
        <Button
          key={page}
          variant={currentPage === page ? "default" : "outline"}
          size="default"
          onClick={() => onPageChange(page)}
          className={cn(
            "min-w-[2.75rem] h-11",
            currentPage === page && "shadow-md"
          )}
        >
          {page}
        </Button>
      ))}

      {endPage < totalPages && (
        <>
          {endPage < totalPages - 1 && <span className="px-2 text-base text-muted-foreground">...</span>}
          <Button
            variant="outline"
            size="default"
            onClick={() => onPageChange(totalPages)}
            className="h-11 min-w-[2.75rem]"
          >
            {totalPages}
          </Button>
        </>
      )}

      <Button
        variant="outline"
        size="default"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className="gap-2 h-11 px-4"
      >
        다음
        <ChevronRight className="h-5 w-5" />
      </Button>
    </div>
  );
}
