// 1. Core Interfaces
export interface ApiResponse {
  message: string;
  version: string;
}

// 2. Data Models (Reflecting Backend Structure)
export interface APIDocData {
  id: string;
  title: string;
  description: string;
  category: string;
  type: string;
  url: string;
  keyword?: string;
  org?: string;
  org_code?: string;
  national_primary?: string;
  similarity_score?: number;
  [key: string]: unknown; // Safe handling for dynamic properties
}

// API Search Response
export interface SearchResponse {
  documents: APIDocData[];
  total: number;
}

// 3. Detail Models
export interface Parameter {
  name: string;
  required?: boolean;
  description?: string;
  [key: string]: unknown;
}

export interface EndpointResponse {
  description?: string;
  content?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface Endpoint {
  path: string;
  method: string;
  summary?: string;
  description?: string;
  parameters?: Parameter[];
  responses?: Record<string, EndpointResponse | unknown>;
}

export interface DetailContent {
  base_url?: string;
  endpoints?: Endpoint[];
  target_url?: string;
  download_urls?: Record<string, string>;
  [key: string]: unknown;
}

// Loose type for dynamic table rows
export type GridRow = Record<string, string | number | boolean | null | undefined>;

export interface DetailData {
  content?: DetailContent;
  grid_table?: GridRow[];
  [key: string]: unknown;
}

// 4. Type Aliases & Unions
export type LLMType = "openai" | "ollama" | "gemini" | "claude";

export type FeedbackType = "like" | "dislike" | null;

// Utility Types Examples
export type APIDocSummary = Pick<APIDocData, 'id' | 'title' | 'category'>;

// Alias for backward compatibility
export type APIDoc = APIDocData;
