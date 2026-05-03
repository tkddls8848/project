import React from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Loader2, Search, Plus } from 'lucide-react';
import { getTypeIcon, getTypeDisplayName } from '../utils';
import { APIDoc, NodeFilters } from '../types';

interface SidebarProps {
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  handleSearch: () => void;
  isSearching: boolean;
  searchResults: APIDoc[];
  addToCanvas: (doc: APIDoc) => void;

  // Filters
  nodeFilters: NodeFilters;
  toggleFilter: (key: keyof NodeFilters) => void;
  setAllFilters: (value: boolean) => void;
}

export const Sidebar = ({
  searchQuery,
  setSearchQuery,
  handleSearch,
  isSearching,
  searchResults,
  addToCanvas,
  nodeFilters,
  toggleFilter,
  setAllFilters,
}: SidebarProps) => {
  return (
    <div className="w-64 flex-shrink-0 border-r flex flex-col bg-card">
      <div className="p-3 border-b space-y-3">
        <div className="flex gap-2">
          <Input
            placeholder="Search API docs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="h-8 text-xs"
          />
          <Button variant="outline" size="icon" onClick={handleSearch} disabled={isSearching} className="h-8 w-8">
            {isSearching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
          </Button>
        </div>
      </div>

      {/* Filters Section */}
      <div className="p-3 border-b border-border/50 bg-muted/20">
        <div className="flex items-center justify-between mb-2">
          <div className="text-xs font-semibold text-foreground">Filters</div>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-[10px] px-2"
            onClick={() => {
              const allOn = Object.values(nodeFilters).every(v => v);
              setAllFilters(!allOn);
            }}
          >
            {Object.values(nodeFilters).every(v => v) ? 'Clear' : 'All'}
          </Button>
        </div>
        <div className="space-y-1.5">
          {(Object.keys(nodeFilters) as Array<keyof typeof nodeFilters>).map((key) => (
            <label key={key} className="flex items-center gap-2 text-[10px] cursor-pointer hover:bg-muted/50 p-1.5 rounded">
              <input
                type="checkbox"
                checked={nodeFilters[key]}
                onChange={() => toggleFilter(key)}
                className="rounded border-border w-3.5 h-3.5"
              />
              <span className="text-muted-foreground">{key}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-2 no-scrollbar">
        {searchResults.map((doc) => {
           const TypeIcon = getTypeIcon(doc.category);
           const keywords = doc.keyword ? doc.keyword.split(',').map(k => k.trim()).filter(k => k) : [];
           
           return (
            <Card key={doc.id} className="cursor-pointer group flex flex-col hover:shadow-md transition-all duration-200 hover:border-primary/30 overflow-hidden border-border/50 bg-card/50">
              <CardHeader className="p-2.5 pb-1.5 space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                   <div className="flex items-center gap-1 min-w-0">
                      <div className="p-0.5 rounded-md bg-muted/50">
                        <TypeIcon className="h-3 w-3 text-muted-foreground shrink-0" />
                      </div>
                      <span className="text-[10px] text-muted-foreground truncate leading-none">{getTypeDisplayName(doc.category)}</span>
                   </div>
                </div>
                <CardTitle className="text-xs font-medium leading-tight group-hover:text-primary transition-colors line-clamp-2">
                  {doc.title}
                </CardTitle>
              </CardHeader>
              
              <CardContent className="p-2.5 pt-0 pb-1.5">
                {keywords.length > 0 ? (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {keywords.slice(0, 3).map((k, i) => (
                      <span key={i} className="inline-flex items-center px-1 py-0.5 rounded text-[9px] font-medium bg-muted text-muted-foreground leading-none">
                        #{k}
                      </span>
                    ))}
                  </div>
                ) : (
                   <p className="text-[9px] text-muted-foreground italic">No keywords</p>
                )}
              </CardContent>

              <CardFooter className="p-2.5 pt-0">
                <Button 
                  className="w-full h-6 text-[10px] bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground shadow-none border-none transition-colors"
                  onClick={() => addToCanvas(doc)}
                  variant="ghost"
                >
                  <Plus className="mr-1 h-3 w-3" />
                  추가
                </Button>
              </CardFooter>
            </Card>
          );
        })}
        {searchResults.length === 0 && !isSearching && (
          <div className="text-center text-[10px] text-muted-foreground mt-8">
            검색 결과가 없습니다. <br/> 키워드로 검색해보세요.
          </div>
        )}
      </div>
    </div>
  );
};