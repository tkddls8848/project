"use client";

import React from 'react';
import { useGraphStats } from '../hooks/useGraphStats';

interface PrometheusFooterProps {
  showStats?: boolean;
}

export function PrometheusFooter({ showStats = true }: PrometheusFooterProps) {
  const { stats, isLoadingStats } = useGraphStats();

  return (
    <footer className="w-full border-t border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 h-9 flex items-center justify-between px-4 text-xs text-muted-foreground shrink-0 z-50">
      <div className="flex items-center gap-4">
        {showStats && stats ? (
          <>
            <div className="flex items-center gap-1.5">
              <span className="font-medium text-foreground">Docs:</span>
              <span>{stats.stats.total_documents}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-medium text-foreground">Keywords:</span>
              <span>{stats.stats.total_keywords}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-medium text-foreground">Categories:</span>
              <span>{stats.stats.total_categories}</span>
            </div>
          </>
        ) : showStats && isLoadingStats ? (
          <span>Loading stats...</span>
        ) : (
          <span>© 2025 NARA Service</span>
        )}
      </div>
      <div className="flex items-center gap-2">
         <span>Prometheus v2.0</span>
      </div>
    </footer>
  );
}