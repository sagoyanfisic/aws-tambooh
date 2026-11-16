import type { Price } from "../types/prices.js";
import { pricesUrl } from "./prices.js";

export interface ShoppingLineInput {
  product_id: string;
  market: string;
  source_url: string;
  quantity_kg: number;
}

export interface InventoryLineInput {
  product_id: string;
  market: string;
  quantity_kg: number;
}

export interface ShoppingListInput {
  items: ShoppingLineInput[];
  inventory: InventoryLineInput[];
}

export interface ShoppingListLine {
  product_id: string;
  product_name: string;
  market: string;
  observation_date: string;
  source_institution: string;
  source_url: string;
  quantity_needed_kg: number;
  quantity_in_pantry_kg: number;
  quantity_to_buy_kg: number;
  price_pen_per_kg: number;
  estimated_cost_pen: number;
  currency: "PEN";
  price_type: "wholesale";
  quality_flags: string[];
}

export interface ShoppingListResponse {
  items: ShoppingListLine[];
  total_pen: number;
  currency: "PEN";
  basis: "wholesale_reference";
  notice: string;
}

export const shoppingEligible = (price: Price): boolean =>
  price.normalized_value !== null &&
  price.normalized_value > 0 &&
  price.normalization_unit === "kg" &&
  price.price_type === "wholesale" &&
  !price.market.toLocaleLowerCase("es-PE").includes("aves vivas");

export async function createShoppingList(
  base: string,
  input: ShoppingListInput,
  signal?: AbortSignal,
): Promise<ShoppingListResponse> {
  if (!base) throw new Error("Falta configurar el servicio de precios.");
  const endpoint = pricesUrl(base).replace(/\/prices$/, "/shopping-lists");
  let response: Response;
  try {
    response = await fetch(endpoint, {
      method: "POST",
      signal,
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      cache: "no-store",
      credentials: "omit",
      body: JSON.stringify(input),
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new Error("No pudimos calcular la lista. Intenta nuevamente.");
  }
  if (!response.ok) {
    let message = "No pudimos calcular la lista de compras.";
    try {
      const body: unknown = await response.json();
      if (
        typeof body === "object" &&
        body !== null &&
        "error" in body &&
        typeof body.error === "object" &&
        body.error !== null &&
        "message" in body.error &&
        typeof body.error.message === "string"
      ) {
        message = body.error.message;
      }
    } catch {
      // Keep the generic message if the gateway response is not JSON.
    }
    throw new Error(message);
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new Error("No pudimos leer el resultado del cálculo.");
  }
  if (
    typeof body !== "object" ||
    body === null ||
    !Array.isArray((body as ShoppingListResponse).items) ||
    (body as ShoppingListResponse).currency !== "PEN" ||
    (body as ShoppingListResponse).basis !== "wholesale_reference" ||
    typeof (body as ShoppingListResponse).total_pen !== "number" ||
    !Number.isFinite((body as ShoppingListResponse).total_pen)
  ) {
    throw new Error("La respuesta de la lista no tiene el formato esperado.");
  }
  return body as ShoppingListResponse;
}
