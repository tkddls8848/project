"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ExternalLink } from "lucide-react";
import type { RelatedAPI } from "@/lib/api";

interface RelatedAPIsGridProps {
  apis: RelatedAPI[];
}

export function RelatedAPIsGrid({ apis }: RelatedAPIsGridProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // 최대 20개만 표시
  const displayApis = apis.slice(0, 20);

  return (
    <div className="w-full">
      <div className="grid grid-cols-10 gap-2">
        {displayApis.map((api, index) => (
          <a
            key={api.id}
            href={api.url}
            target="_blank"
            rel="noopener noreferrer"
            className="relative"
            onMouseEnter={() => setHoveredIndex(index)}
            onMouseLeave={() => setHoveredIndex(null)}
          >
            {/* Compact Card - 폭을 넓고 위아래를 좁게 */}
            <Card className="h-24 flex flex-col hover:shadow-lg transition-all duration-200 hover:border-primary/50 overflow-hidden border border-gray-200 dark:border-neutral-700 group">
              <CardHeader className="p-2 pb-1 space-y-0">
                <div className="flex items-start justify-between gap-1">
                  <Badge className="text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 whitespace-nowrap">
                    #{index + 1}
                  </Badge>
                  <ExternalLink className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              </CardHeader>

              <CardContent className="p-2 pt-1 flex-1 flex flex-col justify-center">
                <CardTitle className="text-xs font-semibold line-clamp-2 leading-tight text-center">
                  {api.title}
                </CardTitle>
                <p className="text-[10px] text-muted-foreground text-center mt-1 truncate">
                  {api.provider}
                </p>
              </CardContent>

              {/* Score badge */}
              <div className="absolute top-1 right-1">
                <Badge variant="outline" className="text-[9px] px-1 py-0 h-4 bg-white/90 dark:bg-gray-800/90">
                  {api.score.toFixed(1)}
                </Badge>
              </div>
            </Card>

            {/* Tooltip on hover */}
            {hoveredIndex === index && (
              <div className="absolute z-50 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg shadow-xl p-3 w-64 -translate-x-1/2 left-1/2 top-full mt-2">
                <h4 className="font-semibold text-sm mb-2">{api.title}</h4>
                <p className="text-xs text-muted-foreground mb-2 line-clamp-3">
                  {api.description}
                </p>
                <div className="flex flex-wrap gap-1">
                  {api.keywords.slice(0, 4).map((keyword, i) => (
                    <Badge key={i} variant="secondary" className="text-[10px] px-1.5 py-0">
                      {keyword}
                    </Badge>
                  ))}
                </div>
                <p className="text-[10px] text-muted-foreground mt-2">
                  유사도: {api.score.toFixed(2)}
                </p>
              </div>
            )}
          </a>
        ))}
      </div>
    </div>
  );
}
