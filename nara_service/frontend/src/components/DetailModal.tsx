"use client";

import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogClose } from "@/components/ui/dialog";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { FileText, Link2, Code2, FileJson, Database, ExternalLink, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { getDetail } from "@/lib/api";
import { DetailData, Endpoint } from "@/types";

type DataCardType = "fileData" | "openapi_link" | "openapi_new" | "openapi_old" | "standard";

const getTypeIcon = (type: string) => {
  switch (type) {
    case "fileData": return FileText;
    case "openapi_link": return Link2;
    case "openapi_new": return Code2;
    case "openapi_old": return FileJson;
    case "standard": return Database;
    default: return FileJson;
  }
};

const getTypeLabel = (type: string) => {
  switch (type) {
    case "fileData": return "파일데이터";
    case "openapi_link": return "OpenAPI(링크)";
    case "openapi_new": return "OpenAPI(신)";
    case "openapi_old": return "OpenAPI(구)";
    case "standard": return "표준데이터셋";
    default: return type;
  }
};

interface DetailModalProps {
  type: string | null;
  id: string | null;
  open: boolean;
  onClose: () => void;
}

export function DetailModal({ type, id, open, onClose }: DetailModalProps) {
  const [detailData, setDetailData] = useState<DetailData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const TypeIcon = type ? getTypeIcon(type) : FileJson;

  useEffect(() => {
    if (open && type && id) {
      const fetchDetailData = async () => {
        try {
          setLoading(true);
          setError(null);
          const data = await getDetail(type, id);
          setDetailData(data);
        } catch (err: unknown) {
          console.error("Failed to fetch detail data:", err);
          let errorMessage = "상세 정보를 불러오는데 실패했습니다.";
          if (err instanceof Error) {
            errorMessage = err.message || errorMessage;
          }
          setError(errorMessage);
        } finally {
          setLoading(false);
        }
      };

      fetchDetailData();
    } else {
      setDetailData(null);
      setError(null);
    }
  }, [open, type, id]);

  if (!type || !id) return null;

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto [&>button]:hidden">
        <div className="flex justify-end mb-2">
          <DialogClose className="rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none">
            <X className="h-4 w-4" />
            <span className="sr-only">Close</span>
          </DialogClose>
        </div>
        <DialogHeader>
          <div className="flex items-center justify-between gap-4 mb-2">
            <DialogTitle className="text-2xl">API 문서 상세</DialogTitle>
            <Badge className="text-xs bg-gray-100 text-gray-600 hover:bg-gray-100 dark:bg-gray-800/50 dark:text-gray-400">
              {getTypeLabel(type)}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            선택하신 API 문서의 상세 정보입니다.
          </p>
        </DialogHeader>

        <div className="space-y-6">
            {/* Type Info */}
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                데이터 타입
              </h3>
              <div className="flex items-center gap-3 p-4 rounded-lg bg-muted/50">
                <TypeIcon className="h-6 w-6 text-primary" />
                <div>
                  <p className="font-semibold text-base">{getTypeLabel(type)}</p>
                  <p className="text-xs text-muted-foreground">Type: {type}</p>
                </div>
              </div>
            </div>

            <Separator />

            {/* Document ID */}
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                문서 번호
              </h3>
              <div className="p-4 rounded-lg bg-muted/50">
                <p className="font-mono text-base font-semibold">{id}</p>
              </div>
            </div>

            <Separator />

            {/* Base URL Information */}
            {!loading && !error && detailData?.content?.base_url && (
              <>
                <div className="space-y-2">
                  <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                    추가 정보 - Base URL
                  </h3>
                  <div className="p-4 rounded-lg bg-muted/50 border border-border">
                    <div className="flex items-center gap-2">
                      <Link2 className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      <code className="text-xs font-mono text-foreground break-all">
                        {detailData.content.base_url}
                      </code>
                    </div>
                  </div>
                </div>

                <Separator />
              </>
            )}

            {/* Endpoints Information */}
            <div className="space-y-4">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                추가 정보 - API Endpoints
              </h3>

              {loading ? (
                <div className="space-y-3">
                  <Skeleton className="h-24 w-full" />
                  <Skeleton className="h-24 w-full" />
                  <Skeleton className="h-24 w-full" />
                </div>
              ) : error ? (
                <div className="p-8 rounded-lg bg-destructive/10 border border-destructive/20 text-center">
                  <FileJson className="h-12 w-12 text-destructive mx-auto mb-3" />
                  <p className="text-sm text-destructive font-medium mb-2">데이터 로딩 실패</p>
                  <p className="text-xs text-muted-foreground">{error}</p>
                </div>
              ) : detailData?.content?.endpoints && detailData.content.endpoints.length > 0 ? (
                <div className="space-y-3">
                  {detailData.content.endpoints.map((endpoint, index) => (
                    <Card key={index} className="border-2 hover:border-primary/50 transition-colors">
                      <CardHeader className="pb-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              <Badge
                                variant="outline"
                                className={cn(
                                  "font-mono font-semibold",
                                  endpoint.method === "GET" && "bg-green-100 text-green-700 border-green-300 dark:bg-green-900/30 dark:text-green-400",
                                  endpoint.method === "POST" && "bg-blue-100 text-blue-700 border-blue-300 dark:bg-blue-900/30 dark:text-blue-400",
                                  endpoint.method === "PUT" && "bg-yellow-100 text-yellow-700 border-yellow-300 dark:bg-yellow-900/30 dark:text-yellow-400",
                                  endpoint.method === "DELETE" && "bg-red-100 text-red-700 border-red-300 dark:bg-red-900/30 dark:text-red-400"
                                )}
                              >
                                {endpoint.method}
                              </Badge>
                              <code className="text-xs font-mono bg-muted px-2 py-1 rounded">
                                {endpoint.path}
                              </code>
                            </div>
                            {endpoint.summary && (
                              <p className="text-sm font-semibold text-foreground mb-1">
                                {endpoint.summary}
                              </p>
                            )}
                            {endpoint.description && (
                              <p className="text-xs text-muted-foreground">
                                {endpoint.description}
                              </p>
                            )}
                          </div>
                          <ExternalLink className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                        </div>
                      </CardHeader>
                      {(endpoint.parameters && endpoint.parameters.length > 0) && (
                        <CardContent className="pt-0">
                          <Separator className="mb-3" />
                          <div className="space-y-2">
                            <p className="text-xs font-semibold text-muted-foreground uppercase">Parameters</p>
                            <div className="space-y-1">
                              {endpoint.parameters.map((param, pIndex: number) => (
                                <div key={pIndex} className="text-xs">
                                  <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">
                                    {param.name}
                                  </code>
                                  {param.required && (
                                    <Badge variant="destructive" className="ml-2 text-xs">required</Badge>
                                  )}
                                  {param.description && (
                                    <span className="text-xs text-muted-foreground ml-2">- {param.description}</span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        </CardContent>
                      )}
                    </Card>
                  ))}
                </div>
              ) : detailData?.content?.target_url ? (
                <Card className="border-2 hover:border-primary/50 transition-colors">
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <Link2 className="h-5 w-5 text-green-600 dark:text-green-400" />
                          <p className="text-sm font-semibold text-foreground">
                            외부 링크
                          </p>
                        </div>
                        <a
                          href={detailData.content.target_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-primary hover:underline break-all flex items-center gap-2"
                        >
                          <code className="text-xs font-mono bg-muted px-2 py-1 rounded">
                            {detailData.content.target_url}
                          </code>
                          <ExternalLink className="h-4 w-4 flex-shrink-0" />
                        </a>
                      </div>
                    </div>
                  </CardHeader>
                </Card>
              ) : (
                <div className="p-8 rounded-lg bg-muted/30 text-center">
                  <FileJson className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
                  <p className="text-sm text-muted-foreground">
                    이 문서에는 endpoints 정보가 없습니다.
                  </p>
                </div>
              )}
            </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
