import { test, mock } from "node:test";
import assert from "node:assert/strict";
import {
  fetchPrices,
  parsePrices,
  pricesUrl,
  validDate,
} from "../.test-build/services/prices.js";
import {
  ageInDays,
  filterPrices,
  formatDate,
  priceLabel,
} from "../.test-build/services/presentation.js";

test("reports a malformed response as an understandable service error", async () => {
  const fake = mock.method(
    globalThis,
    "fetch",
    async () => new Response("<html>Error</html>", { status: 200 }),
  );
  try {
    await assert.rejects(
      fetchPrices("https://api.test"),
      /No pudimos leer la respuesta/,
    );
  } finally {
    fake.mock.restore();
  }
});

const item = {
  product_id: "papa-canchan",
  product_name: "PAPA CANCHÁN",
  market: "GRAN MERCADO MAYORISTA DE LIMA",
  observation_date: "2026-11-16",
  source_institution: "MIDAGRI",
  source_url: "http://sistemas.midagri.gob.pe/report.pdf",
  original_currency: "PEN",
  price_type: "wholesale",
  unit_original: "kg",
  original_value: 2.93,
  normalized_value: 2.93,
  price_pen_per_l: null,
  quality_flags: [],
};
const payload = (row = item) => ({
  items: [row],
  currency: "PEN",
  last_updated: "2026-11-16",
});

test("accepts attributed wholesale prices and keeps original amounts", () => {
  assert.deepEqual(parsePrices(payload()).items[0], item);
});

test("rejects retail prices, invalid currency, date, amounts and unsafe source links", () => {
  for (const change of [
    { price_type: "retail" },
    { original_currency: "USD" },
    { original_value: NaN },
    { normalized_value: Infinity },
    { normalized_value: -2 },
    { observation_date: "2026-02-30" },
    { source_url: "javascript:alert(1)" },
    { source_url: "https://user:secret@example.com" },
  ])
    assert.throws(() => parsePrices(payload({ ...item, ...change })));
});

test("accepts empty and explicitly missing datasets without inventing amounts", () => {
  assert.deepEqual(
    parsePrices({ items: [], currency: "PEN", last_updated: null }).items,
    [],
  );
  const missing = { ...item, original_value: null, normalized_value: null };
  assert.equal(
    priceLabel(parsePrices(payload(missing)).items[0]).value,
    "Sin dato",
  );
});

test("preserves API Gateway stage and avoids duplicate slashes", () => {
  assert.equal(
    pricesUrl("https://example.execute-api.us-east-2.amazonaws.com/dev/"),
    "https://example.execute-api.us-east-2.amazonaws.com/dev/api/v1/prices",
  );
  assert.equal(
    pricesUrl("http://localhost:3000"),
    "http://localhost:3000/api/v1/prices",
  );
  for (const base of [
    "http://public.test",
    "javascript:alert(1)",
    "https://user:pass@example.com",
    "https://example.com/?key=secret",
  ])
    assert.throws(() => pricesUrl(base));
});

test("filters accent-insensitively and keeps markets separate", () => {
  const another = { ...item, market: "OTRO MERCADO" };
  assert.deepEqual(filterPrices([item, another], "canchan", item.market), [
    item,
  ]);
  assert.equal(filterPrices([item], "ARROZ", "").length, 0);
});

test("uses PEN and only labels kilograms or liters when normalized", () => {
  assert.equal(priceLabel(item).unit, "por kg");
  assert.match(priceLabel(item).value, /2\.93/);
  assert.equal(
    priceLabel({ ...item, normalized_value: null, price_pen_per_l: 5 }).unit,
    "por litro",
  );
  assert.equal(
    priceLabel({ ...item, normalized_value: null, unit_original: "caja" }).unit,
    "por caja",
  );
});

test("formats observation day in Lima and calculates freshness at Lima midnight", () => {
  assert.match(formatDate("2026-11-16"), /16.*noviembre.*2026/);
  assert.equal(ageInDays("2026-11-16", new Date("2026-11-17T04:59:00Z")), 0);
  assert.equal(ageInDays("2026-11-16", new Date("2026-11-17T05:00:00Z")), 1);
  assert.equal(validDate("2026-02-30"), false);
});

test("fetches the published API using an abort signal and no browser credentials", async () => {
  const controller = new AbortController();
  const fake = mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url, "https://api.test/dev/api/v1/prices");
    assert.equal(options.signal, controller.signal);
    assert.equal(options.credentials, "omit");
    assert.deepEqual(options.headers, { Accept: "application/json" });
    return new Response(JSON.stringify(payload()), { status: 200 });
  });
  try {
    assert.equal(
      (await fetchPrices("https://api.test/dev", controller.signal)).items
        .length,
      1,
    );
  } finally {
    fake.mock.restore();
  }
});

test("handles missing configuration and unavailable data without sample fallback", async () => {
  await assert.rejects(fetchPrices(""), /Falta configurar/);
  const fake = mock.method(
    globalThis,
    "fetch",
    async () => new Response("{}", { status: 503 }),
  );
  try {
    await assert.rejects(fetchPrices("https://api.test"), /Todavía no hay/);
  } finally {
    fake.mock.restore();
  }
});

test("network errors remain understandable without exposing transport details", async () => {
  const fake = mock.method(globalThis, "fetch", async () => {
    throw new TypeError("Failed to fetch");
  });
  try {
    await assert.rejects(
      fetchPrices("https://api.test"),
      /No pudimos comunicarnos/,
    );
  } finally {
    fake.mock.restore();
  }
});

test("request cancellation is preserved for the hook timeout and cleanup", async () => {
  const controller = new AbortController();
  controller.abort();
  const fake = mock.method(globalThis, "fetch", async () => {
    throw new DOMException("Aborted", "AbortError");
  });
  try {
    await assert.rejects(fetchPrices("https://api.test", controller.signal), {
      name: "AbortError",
    });
  } finally {
    fake.mock.restore();
  }
});
