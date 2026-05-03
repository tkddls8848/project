import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { FILTER_BUTTONS } from "../helpers";
import type { FilterValue, DataCard } from "../types";

interface FilterButtonsProps {
  filterType: FilterValue;
  setFilterType: (type: FilterValue) => void;
  searchText: string;
  setSearchText: (text: string) => void;
  cards: DataCard[];
}

export function FilterButtonsComponent({
  filterType,
  setFilterType,
  searchText,
  setSearchText,
  cards,
}: FilterButtonsProps) {
  const getFilterCount = (type: FilterValue) => {
    if (type === "ALL") return cards.length;
    return cards.filter(card => card.type === type).length;
  };

  return (
    <div className="space-y-6 mb-10">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">데이터 목록</h2>
          <p className="text-base text-muted-foreground mt-2">
            공공데이터 포털의 크롤링된 데이터를 확인하세요
          </p>
        </div>
      </div>

      {/* Search Input */}
      <div className="relative max-w-2xl">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
        <Input
          type="text"
          placeholder="제목으로 검색..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          className="pl-12 h-12 text-base rounded-xl"
        />
      </div>

      {/* Filter Buttons */}
      <div className="flex flex-wrap gap-3">
        {FILTER_BUTTONS.map((button) => {
          const Icon = button.icon;
          const isActive = filterType === button.value;
          const count = getFilterCount(button.value);

          return (
            <Button
              key={button.value}
              variant={isActive ? "default" : "outline"}
              onClick={() => setFilterType(button.value)}
              className={cn(
                "gap-2 transition-all h-11 px-5 text-base rounded-lg",
                isActive && "shadow-md"
              )}
            >
              <Icon className="h-5 w-5" />
              {button.label}
              <Badge
                variant="secondary"
                className={cn(
                  "ml-1 text-sm",
                  isActive ? "bg-primary-foreground/20" : "bg-muted"
                )}
              >
                {count}
              </Badge>
            </Button>
          );
        })}
      </div>
    </div>
  );
}
