import { Node, Edge } from '@xyflow/react';

export interface APIDoc {
  id: string;
  title: string;
  description: string;
  category: string;
  type: string;
  url: string;
  keyword?: string;
  org?: string;
  similarity_score?: number;
}

export type APIDocData = APIDoc & Record<string, unknown>;

export type AppNode = Node<APIDocData, 'contextNode'> | Node<Record<string, unknown>, 'groupNode'>;

export interface SearchResponse {
  documents: APIDoc[];
  total: number;
}

export interface Prometheus {
  id: string;
  user_id: string;
  name: string;
  nodes: AppNode[];
  edges: Edge[];
  created_at: string;
  updated_at: string;
}

export interface GraphNodeData {
  id: string;
  label: string;
  type: string;
  properties: Record<string, any>;
}

export interface NodeFilters {
  Document: boolean;
  Keyword: boolean;
  Category: boolean;
  Provider: boolean;
}

export type GraphAppNode = AppNode;
export type GraphAppEdge = Edge;

export interface GraphSummaryResponse {
  stats: {
    total_documents?: number;
    total_relationships?: number;
    total_keywords?: number;
    total_categories?: number;
    total_providers?: number;
    [key: string]: any;
  };
  top_keywords: Array<{ name: string; count: number }>;
  top_providers: Array<{ name: string; count: number }>;
  top_categories: Array<{ name: string; count: number }>;
}

export interface PathSelectionState {
  sourceId: string | null;
  targetId: string | null;
}

export interface GraphEdge {
  type: string;
  strength: number;
  [key: string]: any;
}

export interface PathFindResponse {
  path: GraphNodeData[];
  relationships: GraphEdge[];
  insights: string;
}
