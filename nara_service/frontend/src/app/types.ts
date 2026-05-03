export interface DataCard {
  id: string;
  title: string;
  description: string;
  url: string;
  type: "fileData" | "openapi_link" | "openapi_new" | "openapi_old" | "standard";
  update_time: string;
}

export type DataCardType = DataCard["type"];
export type FilterValue = DataCardType | "ALL";

export interface FilterButton {
  label: string;
  value: FilterValue;
  icon: React.ElementType;
}
