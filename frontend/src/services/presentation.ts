import type { Price } from "../types/prices.js";

const money = new Intl.NumberFormat("es-PE", {
  style: "currency",
  currency: "PEN",
});
const readableDate = new Intl.DateTimeFormat("es-PE", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "America/Lima",
});
export const formatDate = (day: string): string =>
  readableDate.format(new Date(`${day}T12:00:00Z`));
export const searchable = (text: string): string =>
  text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es-PE");

export function filterPrices(
  items: Price[],
  query: string,
  market: string,
): Price[] {
  const term = searchable(query.trim());
  return items.filter(
    (item) =>
      (!market || item.market === market) &&
      searchable(item.product_name).includes(term),
  );
}

export function priceLabel(item: Price): { value: string; unit: string } {
  if (item.normalized_value !== null)
    return { value: money.format(item.normalized_value), unit: "por kg" };
  if (item.price_pen_per_l !== null)
    return { value: money.format(item.price_pen_per_l), unit: "por litro" };
  if (item.original_value !== null)
    return {
      value: money.format(item.original_value),
      unit: `por ${item.unit_original}`,
    };
  return { value: "Sin dato", unit: "Precio no informado" };
}

export function ageInDays(day: string, now = new Date()): number {
  const parts = new Intl.DateTimeFormat("en", {
    timeZone: "America/Lima",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const get = (kind: string) =>
    Number(parts.find((part) => part.type === kind)?.value);
  const today = Date.UTC(get("year"), get("month") - 1, get("day"));
  return Math.floor(
    (today - new Date(`${day}T00:00:00Z`).valueOf()) / 86400000,
  );
}
