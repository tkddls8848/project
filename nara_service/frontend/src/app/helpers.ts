import {
  FileText,
  Link2,
  Code2,
  FileJson,
  Database,
  LayoutGrid,
} from "lucide-react";
import type { DataCardType, FilterButton } from "./types";

export const FILTER_BUTTONS: FilterButton[] = [
  { label: "전체", value: "ALL", icon: LayoutGrid },
  { label: "파일데이터", value: "fileData", icon: FileText },
  { label: "OpenAPI(링크)", value: "openapi_link", icon: Link2 },
  { label: "OpenAPI(신)", value: "openapi_new", icon: Code2 },
  { label: "OpenAPI(구)", value: "openapi_old", icon: FileJson },
  { label: "표준데이터셋", value: "standard", icon: Database }
];

export const ITEMS_PER_PAGE = 30;

export const getTypeIcon = (type: DataCardType) => {
  switch (type) {
    case "fileData": return FileText;
    case "openapi_link": return Link2;
    case "openapi_new": return Code2;
    case "openapi_old": return FileJson;
    case "standard": return Database;
    default: return FileJson;
  }
};

export const getTypeDisplayName = (type: DataCardType): string => {
  switch (type) {
    case "fileData": return "파일데이터";
    case "openapi_link": return "OpenAPI(링크)";
    case "openapi_new": return "OpenAPI(신)";
    case "openapi_old": return "OpenAPI(구)";
    case "standard": return "표준데이터셋";
    default: return type;
  }
};
