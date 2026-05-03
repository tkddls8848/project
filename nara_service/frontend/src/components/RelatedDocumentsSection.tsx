"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Link2, FileText, Database, Box, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState } from "react";

interface RelatedDocument {
  id: string;
  title: string;
  description?: string;
  type?: string;
  category?: string;
  url?: string;
  keyword?: string;
}

interface RelatedDocumentsSectionProps {
  documents: RelatedDocument[];
  insights: string[];
}

export default function RelatedDocumentsSection({
  documents,
  insights
}: RelatedDocumentsSectionProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  if (!documents || documents.length === 0) {
    return null;
  }

  const getTypeIcon = (type?: string) => {
    switch (type?.toLowerCase()) {
      case 'filedata':
        return <FileText className="h-4 w-4" />;
      case 'openapi_link':
      case 'openapi_new':
      case 'openapi_old':
        return <Database className="h-4 w-4" />;
      case 'standard':
        return <Box className="h-4 w-4" />;
      default:
        return <FileText className="h-4 w-4" />;
    }
  };

  const getTypeBadgeVariant = (type?: string): "default" | "secondary" | "outline" => {
    switch (type?.toLowerCase()) {
      case 'filedata':
        return "default";
      case 'openapi_link':
      case 'openapi_new':
      case 'openapi_old':
        return "secondary";
      case 'standard':
        return "outline";
      default:
        return "default";
    }
  };

  return (
    <div className="w-full animate-in fade-in slide-in-from-bottom-4 duration-500">
      <Card className="border-2 border-primary/20 shadow-lg bg-card/80 backdrop-blur-sm">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Link2 className="h-5 w-5 text-primary" />
              <CardTitle className="text-lg font-semibold">
                관계 기반 추천 문서
              </CardTitle>
              <Badge variant="secondary" className="ml-2">
                {documents.length}개
              </Badge>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsExpanded(!isExpanded)}
              className="h-8 w-8 p-0"
            >
              {isExpanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Neo4j 그래프에서 키워드와 카테고리 관계를 통해 찾은 관련 데이터입니다
          </p>
        </CardHeader>

        {isExpanded && (
          <CardContent className="space-y-4">
            {/* Context Insights */}
            {insights && insights.length > 0 && (
              <div className="p-3 rounded-lg bg-muted/50 space-y-2">
                <h4 className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                  <Link2 className="h-3.5 w-3.5" />
                  데이터 관계 분석
                </h4>
                <ul className="text-sm space-y-1.5 ml-5">
                  {insights.map((insight, idx) => (
                    <li key={idx} className="text-foreground/90 leading-relaxed">
                      {insight}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Related Documents Grid */}
            <div className="grid grid-cols-1 gap-3">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="group p-3 rounded-lg border border-border hover:border-primary/50 hover:bg-accent/50 transition-all duration-200"
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-1 p-2 rounded-md bg-primary/10 text-primary group-hover:bg-primary/20 transition-colors">
                      {getTypeIcon(doc.type)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <h4 className="font-medium text-sm leading-snug line-clamp-1">
                          {doc.title || 'Untitled'}
                        </h4>
                        {doc.type && (
                          <Badge variant={getTypeBadgeVariant(doc.type)} className="text-xs shrink-0">
                            {doc.type}
                          </Badge>
                        )}
                      </div>
                      {doc.description && (
                        <p className="text-xs text-muted-foreground line-clamp-2 mb-2">
                          {doc.description}
                        </p>
                      )}
                      {doc.keyword && (
                        <div className="flex flex-wrap gap-1">
                          {doc.keyword.split(',').slice(0, 3).map((kw, idx) => (
                            <Badge key={idx} variant="outline" className="text-xs">
                              #{kw.trim()}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        )}
      </Card>
    </div>
  );
}
