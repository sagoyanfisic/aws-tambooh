import { pricesUrl } from "./prices.js";
import { shoppingEligible } from "./shopping.js";
import type { Price } from "../types/prices.js";

export interface ScenarioLineInput {
  product_id: string;
  market: string;
  source_url: string;
  quantity_kg: number;
  change_percent: number;
}

export interface ScenarioInput {
  items: ScenarioLineInput[];
}

export interface ScenarioLine {
  product_id: string;
  product_name: string;
  market: string;
  source_institution: string;
  source_url: string;
  observation_date: string;
  quantity_kg: number;
  price_pen_per_kg: number;
  simulated_price_pen_per_kg: number;
  base_cost_pen: number;
  simulated_cost_pen: number;
  difference_pen: number;
  change_percent: number;
  quality_flags: string[];
}

export interface ScenarioResponse {
  is_simulation: true;
  items: ScenarioLine[];
  base_total_pen: number;
  simulated_total_pen: number;
  difference_pen: number;
  currency: "PEN";
  basis: "hypothetical_price_simulation";
  notice: string;
}

export const scenarioEligible = (price: Price): boolean =>
  shoppingEligible(price);

export async function calculateScenario(
  base: string,
  input: ScenarioInput,
): Promise<ScenarioResponse> {
  if (!base) throw new Error("Falta configurar el servicio de precios.");
  const endpoint = pricesUrl(base).replace(/\/prices$/, "/price-scenarios");
  let response: Response;
  try {
    response = await fetch(endpoint, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      cache: "no-store",
      credentials: "omit",
      body: JSON.stringify(input),
    });
  } catch {
    throw new Error("No pudimos calcular la simulación. Intenta nuevamente.");
  }
  if (!response.ok) {
    let message = "No pudimos calcular la simulación.";
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
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new Error("No pudimos leer el resultado de la simulación.");
  }
  if (
    typeof payload !== "object" ||
    payload === null ||
    (payload as ScenarioResponse).is_simulation !== true ||
    (payload as ScenarioResponse).currency !== "PEN" ||
    (payload as ScenarioResponse).basis !== "hypothetical_price_simulation" ||
    !Array.isArray((payload as ScenarioResponse).items) ||
    ![
      (payload as ScenarioResponse).base_total_pen,
      (payload as ScenarioResponse).simulated_total_pen,
      (payload as ScenarioResponse).difference_pen,
    ].every((amount) => typeof amount === "number" && Number.isFinite(amount))
  ) {
    throw new Error("La respuesta de la simulación no tiene el formato esperado.");
  }
  return payload as ScenarioResponse;
}
