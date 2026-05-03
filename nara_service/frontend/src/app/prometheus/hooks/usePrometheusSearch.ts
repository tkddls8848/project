import { useState } from 'react';
import { APIDoc, SearchResponse } from '../types';

export function usePrometheusSearch() {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<APIDoc[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    try {
      const res = await fetch('/api/backend/prometheus/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: searchQuery }),
      });

      if (!res.ok) throw new Error('Search failed');

      const data: SearchResponse = await res.json();
      setSearchResults(data.documents);
    } catch (error) {
      console.error(error);
    } finally {
      setIsSearching(false);
    }
  };

  return {
    searchQuery,
    setSearchQuery,
    searchResults,
    isSearching,
    handleSearch,
  };
}
