import React from 'react';
import {
  Handle,
  Position,
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  getStraightPath,
  useReactFlow,
  type EdgeProps,
  type NodeProps,
  type Node,
  NodeTypes,
  EdgeTypes,
} from '@xyflow/react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Trash2, ExternalLink, MessageSquare, ArrowDown, ArrowUp, Container, X } from 'lucide-react';
import { getTypeIcon, getTypeDisplayName } from '../utils';
import { APIDoc, APIDocData } from '../types';
import { cn } from '@/lib/utils';
import { isHierarchyRelation, getHierarchyTypeName } from '../types/hierarchyTypes';

// --- Helper for Category Colors ---
const getCategoryColor = (category: string) => {
  switch (category) {
    case 'fileData': return 'bg-blue-500';
    case 'openapi_link': return 'bg-green-500';
    case 'openapi_new': return 'bg-purple-500';
    case 'openapi_old': return 'bg-orange-500';
    case 'standard': return 'bg-pink-500';
    default: return 'bg-slate-500';
  }
};

// --- Custom Edge Component ---
export const RelationshipEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data,
}: EdgeProps) => {
  const { setEdges } = useReactFlow();
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const onDeleteEdge = (evt: React.MouseEvent) => {
    evt.stopPropagation();
    setEdges((edges) => edges.filter((edge) => edge.id !== id));
  };

  const rel = data?.relationship as string | undefined;
  const isPositive = rel === 'positive';
  const isNegative = rel === 'negative';

  const label = isPositive ? '긍정' : isNegative ? '부정' : '';
  const color = isPositive
    ? 'bg-green-100 text-green-700 border-green-200'
    : isNegative
      ? 'bg-red-100 text-red-700 border-red-200'
      : 'bg-slate-50 text-slate-400 border-slate-200';

  const edgeColor = isPositive ? '#22c55e' : isNegative ? '#ef4444' : '#94a3b8';

  return (
    <>
      <BaseEdge path={edgePath} markerEnd={markerEnd} style={{ ...style, stroke: edgeColor, strokeWidth: 1.5 }} />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            fontSize: 12,
            pointerEvents: 'all',
          }}
          className="nodrag nopan flex items-center gap-1"
        >
          {label && (
            <div
              className={cn(
                "px-2 py-0.5 text-[10px] font-bold border rounded-full shadow-sm",
                color
              )}
            >
              {label}
            </div>
          )}
          <button
            className="p-0.5 bg-red-100 hover:bg-red-200 text-red-700 border border-red-200 rounded-full shadow-sm transition-all transform hover:scale-110"
            onClick={onDeleteEdge}
            title="삭제"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      </EdgeLabelRenderer>
    </>
  );
};

// --- Hierarchy Edge Component ---
export const HierarchyEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data,
}: EdgeProps) => {
  const { setEdges } = useReactFlow();
  const [edgePath, labelX, labelY] = getStraightPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
  });

  const onDeleteEdge = (evt: React.MouseEvent) => {
    evt.stopPropagation();
    setEdges((edges) => edges.filter((edge) => edge.id !== id));
  };

  const hierarchyType = data?.hierarchyType as string | undefined;
  const label = hierarchyType ? getHierarchyTypeName(hierarchyType) : '위계';

  // 위계 타입별 아이콘
  const getHierarchyIcon = () => {
    if (hierarchyType === 'PARENT_OF') return <ArrowDown className="h-3 w-3" />;
    if (hierarchyType === 'CHILD_OF') return <ArrowUp className="h-3 w-3" />;
    if (hierarchyType === 'INCLUDES') return <Container className="h-3 w-3" />;
    return null;
  };

  // 위계 관계는 굵은 파란색 실선
  const hierarchyColor = '#3b82f6'; // blue-500

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          ...style,
          stroke: hierarchyColor,
          strokeWidth: 2.5,
          strokeDasharray: '5,5'
        }}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: 'absolute',
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            fontSize: 12,
            pointerEvents: 'all',
          }}
          className="nodrag nopan flex items-center gap-1"
        >
          <div
            className={cn(
              "px-2.5 py-1 text-[10px] font-bold border-2 rounded-md shadow-md",
              "bg-blue-50 text-blue-700 border-blue-300",
              "dark:bg-blue-950 dark:text-blue-300 dark:border-blue-700",
              "flex items-center gap-1"
            )}
          >
            {getHierarchyIcon()}
            <span>{label}</span>
          </div>
          <button
            className="p-0.5 bg-red-100 hover:bg-red-200 text-red-700 border border-red-200 rounded-full shadow-sm transition-all transform hover:scale-110"
            onClick={onDeleteEdge}
            title="삭제"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      </EdgeLabelRenderer>
    </>
  );
};

// --- Custom Node Components ---

// 1. Minimal Group Node
export const GroupNode = ({ id, data }: NodeProps) => {
  return (
    <div className="relative w-full h-full bg-slate-100/40 dark:bg-slate-800/40 rounded-3xl transition-colors group"
        onClick={(e) => {
            e.stopPropagation();
            if (typeof data.onClick === 'function') {
                (data.onClick as (id: string) => void)(id);
            }
        }}>
      <div className="absolute -top-6 left-0 px-2 text-sm font-bold text-muted-foreground/60 tracking-tight uppercase">
        {data.label as string || 'Group'}
      </div>
      <div className="absolute -top-8 right-0 flex gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={(e) => {
              e.stopPropagation();
              if (typeof data.onChatClick === 'function') {
                  (data.onChatClick as (id: string) => void)(id);
              }
          }}
          title="Chat with Group"
        >
          <MessageSquare className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-muted-foreground hover:text-destructive opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={(e) => {
              e.stopPropagation();
              if (typeof data.onDelete === 'function') {
                  (data.onDelete as (id: string) => void)(id);
              }
          }}
          title="Delete Group"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
};

// 2. Minimal Context Node (The main redesign)
export const ContextNode = ({ id, data }: NodeProps<Node<APIDocData>>) => {
  const TypeIcon = getTypeIcon(data.category);
  const keywords = data.keyword ? data.keyword.split(',').map(k => k.trim()).filter(k => k) : [];
  const categoryColor = getCategoryColor(data.category);
  
  return (
    <div className="relative group/node">
      {/* Handles - Left (source + target for bidirectional connections) */}
      <Handle
        type="target"
        position={Position.Left}
        id="left"
        isConnectable={true}
        className="!w-2 !h-2 !bg-muted-foreground/30 !border-none transition-all group-hover/node:!bg-primary"
      />
      <Handle
        type="source"
        position={Position.Left}
        id="left"
        isConnectable={true}
        className="!w-2 !h-2 !bg-muted-foreground/30 !border-none transition-all group-hover/node:!bg-primary"
      />

      {/* Handles - Top (source + target for bidirectional connections) */}
      <Handle
        type="target"
        position={Position.Top}
        id="top"
        isConnectable={true}
        className="!w-2 !h-2 !bg-muted-foreground/30 !border-none transition-all group-hover/node:!bg-primary"
      />
      <Handle
        type="source"
        position={Position.Top}
        id="top"
        isConnectable={true}
        className="!w-2 !h-2 !bg-muted-foreground/30 !border-none transition-all group-hover/node:!bg-primary"
      />

      {/* Handles - Bottom (source + target for bidirectional connections) */}
      <Handle
        type="target"
        position={Position.Bottom}
        id="bottom"
        isConnectable={true}
        className="!w-2 !h-2 !bg-muted-foreground/30 !border-none transition-all group-hover/node:!bg-primary"
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="bottom"
        isConnectable={true}
        className="!w-2 !h-2 !bg-muted-foreground/30 !border-none transition-all group-hover/node:!bg-primary"
      />

      {/* Main Card */}
      <div className="w-[340px] bg-background border border-border/60 shadow-sm rounded-xl overflow-hidden hover:shadow-md hover:border-primary/40 transition-all duration-300">
        <div className="flex h-full">
          
          <div className="flex-1 p-4 flex flex-col gap-2">
            {/* Header: Type & Controls */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <TypeIcon className="h-3.5 w-3.5" />
                <span className="font-medium">{getTypeDisplayName(data.category)}</span>
              </div>
              
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 -mr-1 text-muted-foreground hover:text-destructive opacity-0 group-hover/node:opacity-100 transition-opacity duration-200"
                onClick={(e) => {
                    e.stopPropagation();
                    if (typeof data.onDelete === 'function') {
                        data.onDelete(id);
                    }
                }}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>

            {/* Title */}
            <h3 className="text-sm font-bold leading-tight text-foreground line-clamp-2">
              {data.title}
            </h3>

            {/* Description */}
            <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-3">
              {data.description}
            </p>

            {/* Keywords */}
            {keywords.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {keywords.slice(0, 4).map((k, i) => (
                   <span key={i} className="text-[10px] font-medium text-muted-foreground/80 bg-muted/50 px-1.5 py-0.5 rounded-sm">
                     #{k}
                   </span>
                ))}
              </div>
            )}
            
            {/* URL Link (Subtle) */}
            {data.url && (
             <div className="pt-2 mt-auto border-t border-dashed border-border/50">
               <a
                 href={data.url}
                 target="_blank"
                 rel="noopener noreferrer"
                 className="flex items-center gap-1.5 text-[10px] text-muted-foreground hover:text-primary transition-colors truncate"
               >
                 <ExternalLink className="h-3 w-3 shrink-0" />
                 <span className="truncate opacity-70 hover:opacity-100">{data.url}</span>
               </a>
             </div>
           )}
          </div>
        </div>
      </div>

      {/* Handles - Right (source + target for bidirectional connections) */}
      <Handle
        type="target"
        position={Position.Right}
        id="right"
        isConnectable={true}
        className="!w-2 !h-2 !bg-muted-foreground/30 !border-none transition-all group-hover/node:!bg-primary"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="right"
        isConnectable={true}
        className="!w-2 !h-2 !bg-muted-foreground/30 !border-none transition-all group-hover/node:!bg-primary"
      />
    </div>
  );
};

export const nodeTypes: NodeTypes = {
  contextNode: ContextNode,
  groupNode: GroupNode,
};

export const edgeTypes: EdgeTypes = {
  default: RelationshipEdge,
  hierarchy: HierarchyEdge,
};