import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { createShoppingList, shoppingEligible } from "../services/shopping";
import type {
  InventoryLineInput,
  ShoppingLineInput,
  ShoppingListResponse,
} from "../services/shopping";
import type { Price } from "../types/prices";

interface Props {
  prices: Price[];
  apiBase: string;
}

const pantryKeyOf = (item: Pick<Price, "product_id" | "market">) =>
  `${item.product_id}::${item.market}`;
const keyOf = (item: Pick<Price, "product_id" | "market" | "source_url">) =>
  `${item.product_id}::${item.market}::${item.source_url}`;
const formatPEN = (amount: number) =>
  new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN" }).format(
    amount,
  );

export default function ShoppingPlanner({ prices, apiBase }: Props) {
  const [quantities, setQuantities] = useState<Record<string, string>>({});
  const [pantry, setPantry] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ShoppingListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const available = useMemo(
    () =>
      prices
        .filter(
          shoppingEligible,
        )
        .sort((a, b) =>
          `${a.product_name} ${a.market}`.localeCompare(
            `${b.product_name} ${b.market}`,
            "es",
          ),
        ),
    [prices],
  );

  const changeValue = (
    setter: typeof setQuantities,
    key: string,
    value: string,
  ) => setter((current) => ({ ...current, [key]: value }));

  async function calculate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const lines: ShoppingLineInput[] = available.flatMap((item) => {
      const quantity = Number(quantities[keyOf(item)] || 0);
      return Number.isFinite(quantity) && quantity > 0
        ? [
            {
              product_id: item.product_id,
              market: item.market,
              source_url: item.source_url,
              quantity_kg: quantity,
            },
          ]
        : [];
    });
    if (!lines.length) {
      setError("Ingresa una cantidad mayor que cero para al menos un producto.");
      setResult(null);
      return;
    }
    const inventory: InventoryLineInput[] = [
      ...new Map(
        lines.map((line) => [
          `${line.product_id}::${line.market}`,
          {
            product_id: line.product_id,
            market: line.market,
            quantity_kg: Number(
              pantry[`${line.product_id}::${line.market}`] || 0,
            ),
          },
        ]),
      ).values(),
    ];
    setLoading(true);
    setError(null);
    try {
      setResult(await createShoppingList(apiBase, { items: lines, inventory }));
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "No pudimos calcular la lista de compras.",
      );
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section
      id="compras"
      className="shopping-section"
      aria-labelledby="shopping-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">Cantidades e inventario del hogar</p>
          <h2 id="shopping-title">Prepara tu lista de compras</h2>
          <p>
            Elige productos con precio publicado por kg y descuenta lo que ya
            tienes. El cálculo usa la cotización mayorista como referencia.
          </p>
        </div>
      </div>
      {!available.length ? (
        <div className="empty-state">
          <h3>No hay precios normalizados por kg disponibles</h3>
          <p>
            Los productos sin equivalencia confiable no se incluyen en esta
            estimación.
          </p>
        </div>
      ) : (
        <form onSubmit={calculate}>
          <div className="shopping-grid" role="list">
            {available.map((item) => {
              const key = keyOf(item);
              const pantryKey = pantryKeyOf(item);
              return (
                <article className="shopping-product" key={key} role="listitem">
                  <div className="shopping-product-heading">
                    <h3>{item.product_name}</h3>
                    <span>{formatPEN(item.normalized_value as number)} / kg</span>
                  </div>
                  <p>{item.market}</p>
                  <div className="shopping-quantities">
                    <label>
                      Necesito (kg)
                      <input
                        type="number"
                        min="0"
                        max="1000"
                        step="0.1"
                        inputMode="decimal"
                        value={quantities[key] ?? ""}
                        onChange={(event) =>
                          changeValue(setQuantities, key, event.target.value)
                        }
                        aria-label={`Cantidad necesaria de ${item.product_name} en kg`}
                      />
                    </label>
                    <label>
                      Tengo (kg)
                      <input
                        type="number"
                        min="0"
                        max="1000"
                        step="0.1"
                        inputMode="decimal"
                        value={pantry[pantryKey] ?? ""}
                        onChange={(event) =>
                          changeValue(setPantry, pantryKey, event.target.value)
                        }
                        aria-label={`Cantidad disponible de ${item.product_name} en kg`}
                      />
                    </label>
                  </div>
                  <small>
                    Observación {item.observation_date} · {item.source_institution}
                  </small>
                </article>
              );
            })}
          </div>
          <div className="shopping-submit-row">
            <button className="button button-dark" type="submit" disabled={loading}>
              {loading ? "Calculando…" : "Calcular lista"}
            </button>
            <span>La información ingresada solo se usa en esta solicitud.</span>
          </div>
        </form>
      )}
      {error && <div className="error-banner" role="alert">{error}</div>}
      {result && (
        <div className="shopping-result" aria-live="polite">
          <div className="shopping-result-heading">
            <div>
              <p className="eyebrow">Lista calculada</p>
              <h3>Total de referencia: {formatPEN(result.total_pen)}</h3>
            </div>
            <span>Precios mayoristas · PEN</span>
          </div>
          <ul>
            {result.items.map((item) => (
              <li key={`${item.product_id}::${item.market}::${item.source_url}`}>
                <div>
                  <strong>{item.product_name}</strong>
                  <span>{item.market}</span>
                  <a href={item.source_url} target="_blank" rel="noopener noreferrer">
                    {item.source_institution} · {item.observation_date}
                  </a>
                  {item.quality_flags.length > 0 && (
                    <span className="shopping-quality-flag">
                      Revisar dato: {item.quality_flags.join(", ")}
                    </span>
                  )}
                </div>
                <div className="shopping-result-amounts">
                  <span>
                    Comprar {item.quantity_to_buy_kg.toLocaleString("es-PE")} kg
                  </span>
                  <strong>{formatPEN(item.estimated_cost_pen)}</strong>
                </div>
              </li>
            ))}
          </ul>
          <p className="fine-print">{result.notice}</p>
          <p className="fine-print">
            Cada línea usa la fuente y fecha de observación visibles en la
            cotización correspondiente.
          </p>
        </div>
      )}
    </section>
  );
}
