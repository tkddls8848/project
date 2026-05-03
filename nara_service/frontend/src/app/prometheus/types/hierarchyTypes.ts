/**
 * 문서 간 상하위 위계 관계 타입 정의
 */

export enum HierarchyRelationType {
  PARENT_OF = "PARENT_OF",
  CHILD_OF = "CHILD_OF",
  INCLUDES = "INCLUDES",
}

export interface HierarchyType {
  id: string;
  name: string;
  description: string;
  direction: "up" | "down";
  examples: string[];
}

export const HIERARCHY_TYPES: Record<HierarchyRelationType, HierarchyType> = {
  [HierarchyRelationType.PARENT_OF]: {
    id: "PARENT_OF",
    name: "상위 문서",
    description: "이 문서는 대상 문서의 상위 개념/정책입니다",
    direction: "down",
    examples: ["총괄 정책 → 세부 정책", "법률 → 시행령"],
  },
  [HierarchyRelationType.CHILD_OF]: {
    id: "CHILD_OF",
    name: "하위 문서",
    description: "이 문서는 대상 문서의 하위 개념/세부사항입니다",
    direction: "up",
    examples: ["세부 지침 → 상위 정책", "시행규칙 → 법률"],
  },
  [HierarchyRelationType.INCLUDES]: {
    id: "INCLUDES",
    name: "포함",
    description: "이 문서는 대상 문서를 포함합니다",
    direction: "down",
    examples: ["종합 보고서 → 부분 보고서", "전체 계획 → 세부 항목"],
  },
};

export function getHierarchyTypesList(): HierarchyType[] {
  return Object.values(HIERARCHY_TYPES);
}

export function getHierarchyTypeName(typeId: string): string {
  const hierarchyType = HIERARCHY_TYPES[typeId as HierarchyRelationType];
  return hierarchyType ? hierarchyType.name : typeId;
}

export function isHierarchyRelation(edgeType?: string): boolean {
  if (!edgeType) return false;
  return Object.keys(HIERARCHY_TYPES).includes(edgeType);
}
