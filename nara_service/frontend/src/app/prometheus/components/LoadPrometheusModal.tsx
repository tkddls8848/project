import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Trash2, FileText } from 'lucide-react';
import { Prometheus } from '../types';
import { format } from 'date-fns';

interface LoadPrometheusModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  prometheuss: Prometheus[];
  onLoad: (prometheus: Prometheus) => void;
  onDelete: (id: string) => void;
}

export function LoadPrometheusModal({
  open,
  onOpenChange,
  prometheuss,
  onLoad,
  onDelete,
}: LoadPrometheusModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>프로메테우스 불러오기</DialogTitle>
        </DialogHeader>
        <ScrollArea className="h-[400px] w-full pr-4">
          <div className="flex flex-col gap-2">
            {prometheuss.length === 0 ? (
              <div className="text-center text-muted-foreground py-8">
                저장된 프로메테우스가 없습니다.
              </div>
            ) : (
              prometheuss.map((prometheus) => (
                <div
                  key={prometheus.id}
                  className="flex items-center justify-between p-3 border rounded-lg hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors"
                >
                  <div className="flex items-center gap-3 overflow-hidden">
                    <div className="h-8 w-8 bg-primary/10 rounded-full flex items-center justify-center shrink-0">
                        <FileText className="h-4 w-4 text-primary" />
                    </div>
                    <div className="flex flex-col overflow-hidden">
                      <span className="font-medium truncate">{prometheus.name}</span>
                      <span className="text-xs text-muted-foreground">
                        {format(new Date(prometheus.updated_at), 'yyyy-MM-dd HH:mm')}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        onLoad(prometheus);
                        onOpenChange(false);
                      }}
                    >
                      불러오기
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground hover:text-destructive"
                      onClick={() => onDelete(prometheus.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}