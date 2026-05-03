'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Loader2, GitBranch, Target, Lightbulb } from 'lucide-react';
import {
  getRelationshipChains,
  getHiddenConnections,
  type RelationshipChainsResponse,
  type HiddenConnectionsResponse,
} from '@/lib/api/graph';

interface InsightsDashboardProps {
  selectedDocId: string | null;
  onAddToGraph?: (doc: { id: string; title: string; description: string; category: string }) => void;
  onCreateRelationship?: (sourceId: string, targetId: string, suggestedType: string) => void;
}

export default function InsightsDashboard({
  selectedDocId,
  onAddToGraph,
  onCreateRelationship,
}: InsightsDashboardProps) {
  const [activeTab, setActiveTab] = useState('chains');

  // State for each feature
  const [chains, setChains] = useState<RelationshipChainsResponse | null>(null);
  const [hiddenConns, setHiddenConns] = useState<HiddenConnectionsResponse | null>(null);

  // Loading states
  const [loadingChains, setLoadingChains] = useState(false);
  const [loadingHidden, setLoadingHidden] = useState(false);

  // Load data based on active tab and selected document
  useEffect(() => {
    if (activeTab === 'chains' && selectedDocId && !chains) {
      loadChains();
    } else if (activeTab === 'hidden' && selectedDocId && !hiddenConns) {
      loadHiddenConnections();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, selectedDocId]);

  const loadChains = async () => {
    if (!selectedDocId) return;
    setLoadingChains(true);
    const result = await getRelationshipChains(selectedDocId);
    if (result.success) {
      setChains(result.data);
    } else {
      console.error('Failed to load chains:', result.error.message);
    }
    setLoadingChains(false);
  };

  const loadHiddenConnections = async () => {
    if (!selectedDocId) return;
    setLoadingHidden(true);
    const result = await getHiddenConnections(selectedDocId);
    if (result.success) {
      setHiddenConns(result.data);
    } else {
      console.error('Failed to load hidden connections:', result.error.message);
    }
    setLoadingHidden(false);
  };

  // Refresh current tab data
  const refreshCurrentTab = () => {
    switch (activeTab) {
      case 'chains':
        setChains(null);
        loadChains();
        break;
      case 'hidden':
        setHiddenConns(null);
        loadHiddenConnections();
        break;
    }
  };

  return (
    <div className="w-full h-full flex flex-col">
      <div className="p-3 border-b border-border/50 flex items-center justify-between shrink-0">
         <div className="flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold text-foreground">Insights</h3>
         </div>
      </div>
      
      <div className="flex-1 p-3">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-4 bg-muted/50 p-1 h-auto">
            <TabsTrigger value="chains" className="text-xs px-1 py-2 h-auto data-[state=active]:bg-background data-[state=active]:shadow-sm">
              <div className="flex flex-col items-center gap-1.5">
                 <GitBranch className="h-4 w-4" />
                 <span>Chains</span>
              </div>
            </TabsTrigger>
            <TabsTrigger value="hidden" className="text-xs px-1 py-2 h-auto data-[state=active]:bg-background data-[state=active]:shadow-sm">
               <div className="flex flex-col items-center gap-1.5">
                 <Target className="h-4 w-4" />
                 <span>Hidden</span>
               </div>
            </TabsTrigger>
          </TabsList>

          {/* Relationship Chains Tab */}
          <TabsContent value="chains" className="space-y-4 focus-visible:outline-none focus-visible:ring-0">
            {!selectedDocId ? (
              <div className="text-center text-xs text-muted-foreground py-8">
                Select a document to view chains.
              </div>
            ) : loadingChains ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : chains && chains.chains.length > 0 ? (
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <p className="text-xs text-muted-foreground">
                    {chains.total} chains found
                  </p>
                  <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={refreshCurrentTab}>
                    Refresh
                  </Button>
                </div>
                {chains.chains.map((chain) => (
                  <Card key={chain.chain_id} className="p-3 bg-card/50">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Badge variant="secondary" className="text-[10px] px-1.5">{chain.length} steps</Badge>
                        <Badge variant="outline" className="text-[10px] px-1.5">{chain.chain_types[0]}</Badge>
                      </div>
                      <p className="text-xs font-medium leading-relaxed">{chain.insight}</p>
                      <div className="flex flex-wrap gap-1 text-[10px] text-muted-foreground items-center">
                        {chain.nodes.map((node, idx) => (
                          <React.Fragment key={node.id}>
                            <span className="font-medium text-foreground">{node.title}</span>
                            {idx < chain.nodes.length - 1 && <span className="text-muted-foreground/50">→</span>}
                          </React.Fragment>
                        ))}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            ) : (
              <div className="text-center text-xs text-muted-foreground py-8">
                No chains found.
              </div>
            )}
          </TabsContent>

          {/* Hidden Connections Tab */}
          <TabsContent value="hidden" className="space-y-4 focus-visible:outline-none focus-visible:ring-0">
            {!selectedDocId ? (
              <div className="text-center text-xs text-muted-foreground py-8">
                Select a document to view hidden connections.
              </div>
            ) : loadingHidden ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : hiddenConns && hiddenConns.connections.length > 0 ? (
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <p className="text-xs text-muted-foreground">
                    {hiddenConns.total} connections found
                  </p>
                  <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={refreshCurrentTab}>
                    Refresh
                  </Button>
                </div>
                {hiddenConns.connections.map((conn, idx) => (
                  <Card key={idx} className="p-3 bg-card/50">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between gap-2">
                        <Badge variant="secondary" className="text-[10px] truncate max-w-[100px]">{conn.suggested_relationship}</Badge>
                        <Progress value={conn.connection_strength * 100} className="w-16 h-1.5" />
                      </div>
                      <p className="text-xs font-medium">{conn.target_doc.title}</p>
                      <p className="text-[10px] text-muted-foreground line-clamp-2">{conn.reason}</p>
                      <div className="flex flex-wrap gap-1">
                        {conn.common_attributes.keywords.slice(0, 3).map((kw) => (
                          <Badge key={kw} variant="outline" className="text-[10px] px-1.5 py-0 h-4">
                            {kw}
                          </Badge>
                        ))}
                      </div>
                      <div className="flex gap-2 pt-1">
                        {onAddToGraph && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 text-xs flex-1"
                            onClick={() => onAddToGraph(conn.target_doc)}
                          >
                            Add
                          </Button>
                        )}
                        {onCreateRelationship && selectedDocId && (
                          <Button
                            size="sm"
                            variant="default"
                            className="h-7 text-xs flex-1"
                            onClick={() =>
                              onCreateRelationship(
                                selectedDocId,
                                conn.target_doc.id,
                                conn.suggested_relationship
                              )
                            }
                          >
                            Connect
                          </Button>
                        )}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            ) : (
              <div className="text-center text-xs text-muted-foreground py-8">
                No hidden connections found.
              </div>
            )}
          </TabsContent>

        </Tabs>
      </div>
    </div>
  );
}
