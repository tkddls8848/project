'use client';

/**
 * Unified Relationship Modal
 * Create both hierarchical and link relationships between documents
 * Consolidates HierarchyRelationshipModal and LinkRelationshipModal (95% duplicate code)
 */

import React, { useState } from 'react';
import { ArrowDown, ArrowUp, Container, ThumbsUp, ThumbsDown, FileText } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { GraphNodeData } from '../types';
import { HierarchyRelationType, HIERARCHY_TYPES } from '../types/hierarchyTypes';

export type LinkRelationType = 'positive' | 'negative';
export type RelationshipModalType = 'hierarchy' | 'link';

interface LinkRelationshipType {
  name: string;
  description: string;
  examples: string[];
}

const LINK_TYPES: Record<LinkRelationType, LinkRelationshipType> = {
  positive: {
    name: '긍정 관계',
    description: '두 문서가 서로 긍정적인 관계를 가지고 있습니다',
    examples: ['유사한 주제', '상호 보완적', '연관 개념', '함께 활용'],
  },
  negative: {
    name: '부정 관계',
    description: '두 문서가 서로 부정적이거나 대립적인 관계를 가지고 있습니다',
    examples: ['상반된 의견', '대립되는 개념', '모순되는 내용', '충돌하는 관점'],
  },
};

interface RelationshipModalProps {
  type: RelationshipModalType;
  selectedNodes: GraphNodeData[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreateHierarchy?: (sourceId: string, targetId: string, hierarchyType: HierarchyRelationType) => void;
  onCreateLink?: (sourceId: string, targetId: string, relationType: LinkRelationType) => void;
}

export const RelationshipModal: React.FC<RelationshipModalProps> = ({
  type,
  selectedNodes,
  open,
  onOpenChange,
  onCreateHierarchy,
  onCreateLink,
}) => {
  const [selectedHierarchyType, setSelectedHierarchyType] = useState<HierarchyRelationType | null>(null);
  const [selectedLinkType, setSelectedLinkType] = useState<LinkRelationType | null>(null);

  const sourceNode = selectedNodes[0];
  const targetNode = selectedNodes[1];

  const handleCreate = () => {
    if (selectedNodes.length < 2) return;

    if (type === 'hierarchy' && selectedHierarchyType && onCreateHierarchy) {
      onCreateHierarchy(sourceNode.id, targetNode.id, selectedHierarchyType);
      setSelectedHierarchyType(null);
    } else if (type === 'link' && selectedLinkType && onCreateLink) {
      onCreateLink(sourceNode.id, targetNode.id, selectedLinkType);
      setSelectedLinkType(null);
    }

    onOpenChange(false);
  };

  const handleCancel = () => {
    setSelectedHierarchyType(null);
    setSelectedLinkType(null);
    onOpenChange(false);
  };

  const getHierarchyIcon = (hierarchyType: HierarchyRelationType) => {
    switch (hierarchyType) {
      case HierarchyRelationType.PARENT_OF:
        return <ArrowDown className="h-4 w-4" />;
      case HierarchyRelationType.CHILD_OF:
        return <ArrowUp className="h-4 w-4" />;
      case HierarchyRelationType.INCLUDES:
        return <Container className="h-4 w-4" />;
      default:
        return null;
    }
  };

  const getLinkIcon = (linkType: LinkRelationType) => {
    switch (linkType) {
      case 'positive':
        return <ThumbsUp className="h-4 w-4" />;
      case 'negative':
        return <ThumbsDown className="h-4 w-4" />;
      default:
        return null;
    }
  };

  const isCreateDisabled = type === 'hierarchy' ? !selectedHierarchyType : !selectedLinkType;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {type === 'hierarchy' ? '위계 관계 생성' : '관계 생성'}
          </DialogTitle>
          <DialogDescription>
            {type === 'hierarchy'
              ? '두 문서 간의 상하위 위계 관계를 설정하세요'
              : '두 문서 간의 관계를 설정하세요'}
          </DialogDescription>
        </DialogHeader>

        {/* Selected Documents */}
        <div className="space-y-4 py-4">
          <div className="grid grid-cols-2 gap-4">
            {/* Source Node */}
            <div className="flex items-start gap-3 p-4 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg">
              <FileText className="h-5 w-5 text-blue-600 dark:text-blue-400 mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <Badge variant="outline" className="text-xs mb-2">원본 문서</Badge>
                <div className="text-sm font-semibold text-blue-900 dark:text-blue-100 line-clamp-2">
                  {sourceNode?.label || '(선택되지 않음)'}
                </div>
                {sourceNode?.properties.description && (
                  <div className="text-xs text-muted-foreground mt-1 line-clamp-2">
                    {sourceNode.properties.description as string}
                  </div>
                )}
              </div>
            </div>

            {/* Target Node */}
            <div className="flex items-start gap-3 p-4 bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-lg">
              <FileText className="h-5 w-5 text-green-600 dark:text-green-400 mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <Badge variant="outline" className="text-xs mb-2">대상 문서</Badge>
                <div className="text-sm font-semibold text-green-900 dark:text-green-100 line-clamp-2">
                  {targetNode?.label || '(선택되지 않음)'}
                </div>
                {targetNode?.properties.description && (
                  <div className="text-xs text-muted-foreground mt-1 line-clamp-2">
                    {targetNode.properties.description as string}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Type Selection */}
          {type === 'hierarchy' ? (
            // Hierarchy Type Selection
            <div className="space-y-2">
              <label className="text-sm font-medium">위계 관계 타입 선택:</label>
              <div className="grid gap-3">
                {Object.values(HierarchyRelationType).map((hierarchyType) => {
                  const typeData = HIERARCHY_TYPES[hierarchyType];
                  const isSelected = selectedHierarchyType === hierarchyType;

                  return (
                    <button
                      key={hierarchyType}
                      onClick={() => setSelectedHierarchyType(hierarchyType)}
                      className={`
                        flex items-start gap-3 p-4 rounded-lg border-2 transition-all text-left
                        ${isSelected
                          ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30'
                          : 'border-border hover:border-blue-300 bg-background'
                        }
                      `}
                    >
                      <div className={`mt-1 ${isSelected ? 'text-blue-600' : 'text-muted-foreground'}`}>
                        {getHierarchyIcon(hierarchyType)}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-sm font-semibold ${isSelected ? 'text-blue-900 dark:text-blue-100' : 'text-foreground'}`}>
                            {typeData.name}
                          </span>
                          {typeData.direction === 'down' && (
                            <ArrowDown className="h-3 w-3 text-muted-foreground" />
                          )}
                          {typeData.direction === 'up' && (
                            <ArrowUp className="h-3 w-3 text-muted-foreground" />
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground mb-2">
                          {typeData.description}
                        </p>
                        <div className="text-xs text-muted-foreground/80">
                          <span className="font-medium">예시:</span> {typeData.examples.join(', ')}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : (
            // Link Type Selection
            <div className="space-y-2">
              <label className="text-sm font-medium">관계 타입 선택:</label>
              <div className="grid gap-3">
                {Object.entries(LINK_TYPES).map(([linkTypeKey, linkTypeData]) => {
                  const relationType = linkTypeKey as LinkRelationType;
                  const isSelected = selectedLinkType === relationType;

                  return (
                    <button
                      key={linkTypeKey}
                      onClick={() => setSelectedLinkType(relationType)}
                      className={`
                        flex items-start gap-3 p-4 rounded-lg border-2 transition-all text-left
                        ${isSelected
                          ? relationType === 'positive'
                            ? 'border-green-500 bg-green-50 dark:bg-green-950/30'
                            : 'border-red-500 bg-red-50 dark:bg-red-950/30'
                          : 'border-border hover:border-blue-300 bg-background'
                        }
                      `}
                    >
                      <div className={`mt-1 ${
                        isSelected
                          ? relationType === 'positive'
                            ? 'text-green-600'
                            : 'text-red-600'
                          : 'text-muted-foreground'
                      }`}>
                        {getLinkIcon(relationType)}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-sm font-semibold ${
                            isSelected
                              ? relationType === 'positive'
                                ? 'text-green-900 dark:text-green-100'
                                : 'text-red-900 dark:text-red-100'
                              : 'text-foreground'
                          }`}>
                            {linkTypeData.name}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground mb-2">
                          {linkTypeData.description}
                        </p>
                        <div className="text-xs text-muted-foreground/80">
                          <span className="font-medium">예시:</span> {linkTypeData.examples.join(', ')}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleCancel}>
            취소
          </Button>
          <Button onClick={handleCreate} disabled={isCreateDisabled}>
            관계 생성
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
