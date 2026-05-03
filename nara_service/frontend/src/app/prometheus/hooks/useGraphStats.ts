/**
 * Graph Statistics Hook
 */

import { useState, useCallback, useEffect } from 'react';
import { getGraphSummary } from '@/lib/api/graph';
import type { GraphSummaryResponse } from '../types';

export const useGraphStats = () => {
  const [stats, setStats] = useState<GraphSummaryResponse | null>(null);
  const [isLoadingStats, setIsLoadingStats] = useState(false);
  const [statsError, setStatsError] = useState<string | null>(null);

  const loadStats = useCallback(async () => {
    setIsLoadingStats(true);
    setStatsError(null);

    const result = await getGraphSummary<GraphSummaryResponse>();
    if (result.success) {
      setStats(result.data);
    } else {
      console.error('Error loading stats:', result.error.message);
      setStatsError(result.error.message);
    }
    setIsLoadingStats(false);
  }, []);

  const refreshStats = useCallback(() => {
    loadStats();
  }, [loadStats]);

  // Load stats on mount
  useEffect(() => {
    loadStats();
  }, [loadStats]);

  return {
    stats,
    isLoadingStats,
    statsError,
    refreshStats,
  };
};
