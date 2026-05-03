/**
 * Right Sidebar Component for Prometheus Page
 *
 * Why: page.tsx가 644줄로 CODING_RULES 300줄 제한을 초과하여
 *      Controls와 Insights 영역을 별도 컴포넌트로 분리합니다.
 */

'use client';

import React from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Link2, Network, ArrowDownUp } from 'lucide-react';
import type { APIDoc } from '../types';
import InsightsDashboard from './InsightsDashboard';

interface RightSidebarProps {
  // State
  rightSidebarOpen: boolean;
  setRightSidebarOpen: (open: boolean) => void;
  interactionMode: 'relationship' | 'hierarchy';
  setInteractionMode: (mode: 'relationship' | 'hierarchy') => void;

  // Relationship Mode
  relationshipSelection: {
    selectedNodes: Array<{ id: string; label: string; type: string; properties: any }>;
  };
  selectNodeForRelationship: (node: { id: string; label: string; type: string; properties: any }) => void;
  clearRelationshipSelection: () => void;
  canCreateRelationship: boolean;
  openRelationshipModal: () => void;
  openHierarchyModal: () => void;

  // Insights
  selectedDocId: string | null;
  searchResults: APIDoc[];
  addToCanvas: (doc: APIDoc) => void;

  // Hierarchy Relations
  showHierarchyRelations: boolean;
  setShowHierarchyRelations: (show: boolean) => void;

  // Link Relations
  showLinkRelations: boolean;
  setShowLinkRelations: (show: boolean) => void;
}

/**
 * Right Sidebar - Controls and Insights Panel
 *
 * Why: 사이드바를 분리하여 page.tsx의 복잡도를 낮추고
 *      Controls 관련 로직을 독립적으로 관리합니다.
 */
export function RightSidebar({
  rightSidebarOpen,
  setRightSidebarOpen,
  interactionMode,
  setInteractionMode,
  relationshipSelection,
  selectNodeForRelationship,
  clearRelationshipSelection,
  canCreateRelationship,
  openRelationshipModal,
  openHierarchyModal,
  selectedDocId,
  searchResults,
  addToCanvas,
  showHierarchyRelations,
  setShowHierarchyRelations,
  showLinkRelations,
  setShowLinkRelations,
}: RightSidebarProps) {
  if (!rightSidebarOpen) {
    return (
      <div className="w-8 border-l border-border bg-card/50 flex flex-col items-center py-4 gap-4 backdrop-blur-sm z-10">
        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setRightSidebarOpen(true)}>
          <span className="text-xs">⚙️</span>
        </Button>
        <div className="h-px w-4 bg-border" />
        <div className="writing-mode-vertical text-[10px] text-muted-foreground font-medium tracking-widest uppercase opacity-70">
          Controls
        </div>
      </div>
    );
  }

  return (
    <div className="w-72 flex-shrink-0 border-l border-border bg-card/50 backdrop-blur-sm z-10 flex flex-col transition-all duration-300">
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {/* Interaction Mode Toggle */}
        <div className="p-3 border-b border-border/50">
          <div className="text-xs font-semibold text-foreground mb-2">Interaction Mode</div>
          <div className="flex gap-2">
            <Button
              variant={interactionMode === 'relationship' ? 'default' : 'outline'}
              size="sm"
              className="flex-1 h-8 text-xs px-2"
              onClick={() => setInteractionMode('relationship')}
            >
              <Link2 className="h-3.5 w-3.5 mr-1.5" />
              Link
            </Button>
            <Button
              variant={interactionMode === 'hierarchy' ? 'default' : 'outline'}
              size="sm"
              className="flex-1 h-8 text-xs px-2"
              onClick={() => setInteractionMode('hierarchy')}
            >
              <ArrowDownUp className="h-3.5 w-3.5 mr-1.5" />
              Hierarchy
            </Button>
          </div>
        </div>

        {/* Hierarchy Controls */}
        {interactionMode === 'hierarchy' && (
          <div className="p-3 border-b border-border/50">
            <div className="text-xs font-semibold text-foreground mb-2">위계 관계 설정</div>
            <div className="space-y-2">
              <div className="text-[10px] text-muted-foreground">
                {relationshipSelection.selectedNodes.length === 0
                  ? '문서를 두 개 선택하여 위계 관계를 설정하세요'
                  : relationshipSelection.selectedNodes.length === 1
                  ? '대상 문서를 하나 더 선택하세요'
                  : '위계 관계를 생성할 준비가 되었습니다'}
              </div>
              {relationshipSelection.selectedNodes[0] && (
                <div className="flex items-center gap-1.5 text-xs">
                  <Badge variant="secondary" className="text-[10px] px-1.5 h-5">원본</Badge>
                  <span className="truncate text-muted-foreground text-[10px]">
                    {relationshipSelection.selectedNodes[0].label}
                  </span>
                </div>
              )}
              {relationshipSelection.selectedNodes[1] && (
                <div className="flex items-center gap-1.5 text-xs">
                  <Badge variant="secondary" className="text-[10px] px-1.5 h-5">대상</Badge>
                  <span className="truncate text-muted-foreground text-[10px]">
                    {relationshipSelection.selectedNodes[1].label}
                  </span>
                </div>
              )}

              {canCreateRelationship && (
                <div className="flex gap-2 pt-1">
                  <Button
                    size="sm"
                    className="flex-1 h-7 text-xs px-2"
                    onClick={openHierarchyModal}
                  >
                    관계 설정
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs px-2"
                    onClick={clearRelationshipSelection}
                  >
                    Clear
                  </Button>
                </div>
              )}

              <div className="mt-3 p-2 bg-blue-50 dark:bg-blue-950/30 rounded text-[10px] text-muted-foreground">
                <div className="font-medium mb-1 text-blue-900 dark:text-blue-100">위계 관계 타입:</div>
                <ul className="space-y-0.5 list-disc list-inside">
                  <li>상위 문서 (PARENT_OF)</li>
                  <li>하위 문서 (CHILD_OF)</li>
                  <li>포함 (INCLUDES)</li>
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* Relationship Controls */}
        {interactionMode === 'relationship' && (
          <div className="p-3 border-b border-border/50">
            <div className="text-xs font-semibold text-foreground mb-2">관계 설정</div>
            <div className="space-y-2">
              <div className="text-[10px] text-muted-foreground">
                {relationshipSelection.selectedNodes.length === 0
                  ? '문서를 두 개 선택하여 관계를 설정하세요'
                  : relationshipSelection.selectedNodes.length === 1
                  ? '대상 문서를 하나 더 선택하세요'
                  : '관계를 생성할 준비가 되었습니다'}
              </div>
              {relationshipSelection.selectedNodes[0] && (
                <div className="flex items-center gap-1.5 text-xs">
                  <Badge variant="secondary" className="text-[10px] px-1.5 h-5">원본</Badge>
                  <span className="truncate text-muted-foreground text-[10px]">
                    {relationshipSelection.selectedNodes[0].label}
                  </span>
                </div>
              )}
              {relationshipSelection.selectedNodes[1] && (
                <div className="flex items-center gap-1.5 text-xs">
                  <Badge variant="secondary" className="text-[10px] px-1.5 h-5">대상</Badge>
                  <span className="truncate text-muted-foreground text-[10px]">
                    {relationshipSelection.selectedNodes[1].label}
                  </span>
                </div>
              )}

              {canCreateRelationship && (
                <div className="flex gap-2 pt-1">
                  <Button
                    size="sm"
                    className="flex-1 h-7 text-xs px-2"
                    onClick={openRelationshipModal}
                  >
                    관계 설정
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs px-2"
                    onClick={clearRelationshipSelection}
                  >
                    Clear
                  </Button>
                </div>
              )}

              <div className="mt-3 p-2 bg-blue-50 dark:bg-blue-950/30 rounded text-[10px] text-muted-foreground">
                <div className="font-medium mb-1 text-blue-900 dark:text-blue-100">관계 타입:</div>
                <ul className="space-y-0.5 list-disc list-inside">
                  <li>긍정 관계 (Positive)</li>
                  <li>부정 관계 (Negative)</li>
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* Hierarchy Relations Toggle */}
        <div className="p-3 border-b border-border/50">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <Network className="h-3.5 w-3.5 text-blue-500" />
              <div className="text-xs font-semibold text-foreground">위계 관계</div>
            </div>
          </div>
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-[10px] cursor-pointer hover:bg-muted/50 p-1.5 rounded">
              <input
                type="checkbox"
                checked={showHierarchyRelations}
                onChange={(e) => setShowHierarchyRelations(e.target.checked)}
                className="rounded border-border w-3.5 h-3.5"
              />
              <span className="text-muted-foreground">상하위 위계 관계선 표시</span>
            </label>
            {showHierarchyRelations && (
              <div className="ml-2 pl-2 border-l-2 border-blue-200 dark:border-blue-800">
                <div className="space-y-1 text-[9px] text-muted-foreground">
                  <div className="flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                    <span>상위 문서 (PARENT_OF)</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                    <span>하위 문서 (CHILD_OF)</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                    <span>포함 (INCLUDES)</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Link Relations Toggle */}
        <div className="p-3 border-b border-border/50">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <Link2 className="h-3.5 w-3.5 text-purple-500" />
              <div className="text-xs font-semibold text-foreground">링크 관계</div>
            </div>
          </div>
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-[10px] cursor-pointer hover:bg-muted/50 p-1.5 rounded">
              <input
                type="checkbox"
                checked={showLinkRelations}
                onChange={(e) => setShowLinkRelations(e.target.checked)}
                className="rounded border-border w-3.5 h-3.5"
              />
              <span className="text-muted-foreground">긍정/부정 관계선 표시</span>
            </label>
            {showLinkRelations && (
              <div className="ml-2 pl-2 border-l-2 border-purple-200 dark:border-purple-800">
                <div className="space-y-1 text-[9px] text-muted-foreground">
                  <div className="flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full bg-green-500"></div>
                    <span>긍정 관계 (Positive)</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <div className="w-2 h-2 rounded-full bg-red-500"></div>
                    <span>부정 관계 (Negative)</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Insights Dashboard - Bottom Section */}
        <div className="flex-1 min-h-[300px]">
          <InsightsDashboard
            selectedDocId={selectedDocId}
            onAddToGraph={(doc) => {
              // Convert hidden connection doc to APIDoc format
              const apiDoc: APIDoc = {
                id: doc.id,
                title: doc.title,
                description: doc.description,
                category: doc.category,
                type: doc.category, // Use category as type for hidden connections
                keyword: '', // Hidden connections don't have keywords
                url: '', // Hidden connections don't have URLs
              };
              addToCanvas(apiDoc);
            }}
            onCreateRelationship={(sourceId, targetId, suggestedType) => {
              // TODO: Implement relationship creation
              console.log('Create relationship:', sourceId, targetId, suggestedType);
            }}
          />
        </div>
      </div>

      <div className="p-2 border-t border-border/50 flex justify-center">
        <Button variant="ghost" size="sm" className="h-6 w-full text-[10px] text-muted-foreground" onClick={() => setRightSidebarOpen(false)}>
          Hide Controls
        </Button>
      </div>
    </div>
  );
}
