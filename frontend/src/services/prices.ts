import type { Price, PricesResponse } from "../types/prices.js";

const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const text = (value: unknown): value is string =>
  typeof value === "string" && value.length > 0;
const amount = (value: unknown): value is number | null =>
  value === null ||
  (typeof value === "number" && Number.isFinite(value) && value >= 0);

export function validDate(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value))
    return false;
  const date = new Date(`${value}T12:00:00Z`);
  return (
    Number.isFinite(date.valueOf()) && date.toISOString().slice(0, 10) === value
  );
}

export function sourceUrl(value: unknown): value is string {
  if (!text(value)) return false;
  try {
    const url = new URL(value);
    return (
      ["http:", "https:"].includes(url.protocol) &&
      !url.username &&
      !url.password
    );
  } catch {
    return false;
  }
}

export function parsePrices(payload: unknown): PricesResponse {
  if (
    !object(payload) ||
    payload.currency !== "PEN" ||
    !Array.isArray(payload.items) ||
    !(payload.last_updated === null || validDate(payload.last_updated))
  ) {
    throw new Error("La respuesta de precios no tiene el formato esperado.");
  }
  const items = payload.items.map((item: unknown): Price => {
    if (
      !object(item) ||
      !text(item.product_id) ||
      !text(item.product_name) ||
      !text(item.market) ||
      !validDate(item.observation_date) ||
      !text(item.source_institution) ||
      !sourceUrl(item.source_url) ||
      item.price_type !== "wholesale" ||
      item.original_currency !== "PEN" ||
      !text(item.unit_original) ||
      !amount(item.original_value) ||
      !amount(item.normalized_value) ||
      !amount(item.price_pen_per_l) ||
      !Array.isArray(item.quality_flags) ||
      !item.quality_flags.every((flag: unknown) => typeof flag === "string")
    ) {
      throw new Error(
        "Se recibió una cotización incompleta o incompatible con el piloto de Perú.",
      );
    }
    return item as unknown as Price;
  });
  return { items, currency: "PEN", last_updated: payload.last_updated };
}

export function pricesUrl(base: string): string {
  const url = new URL(base);
  if (
    (url.protocol !== "https:" &&
      !(
        url.protocol === "http:" &&
        ["localhost", "127.0.0.1"].includes(url.hostname)
      )) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash
  ) {
    throw new Error("La dirección del servicio de precios no es válida.");
  }
  return `${base.replace(/\/+$/, "")}/api/v1/prices`;
}

export async function fetchPrices(
  base: string,
  signal?: AbortSignal,
): Promise<PricesResponse> {
  if (!base)
    throw new Error(
      "Falta configurar el servicio de precios para esta aplicación.",
    );
  const endpoint = pricesUrl(base);
  let response: Response;
  try {
    response = await fetch(endpoint, {
      signal,
      headers: { Accept: "application/json" },
      cache: "no-store",
      credentials: "omit",
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new Error(
      "No pudimos comunicarnos con el servicio de precios. Intenta actualizar la consulta.",
    );
  }
  if (!response.ok) {
    throw new Error(
      response.status === 503
        ? "Todavía no hay un conjunto de precios publicado disponible. Intenta nuevamente más tarde."
        : "No pudimos consultar los precios. Intenta nuevamente en un momento.",
    );
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new Error(
      "No pudimos leer la respuesta del servicio de precios. Intenta consultar nuevamente.",
    );
  }
  return parsePrices(payload);
}
