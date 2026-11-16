export interface Price {
  product_id: string;
  product_name: string;
  market: string;
  observation_date: string;
  source_institution: string;
  source_url: string;
  original_currency: "PEN";
  price_type: "wholesale";
  unit_original: string;
  original_value: number | null;
  normalized_value: number | null;
  normalization_unit?: string | null;
  price_pen_per_l: number | null;
  quality_flags: string[];
}

export interface PricesResponse {
  items: Price[];
  currency: "PEN";
  last_updated: string | null;
}
