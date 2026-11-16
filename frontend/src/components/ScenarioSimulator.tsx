import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import type {
  ScenarioLineInput,
  ScenarioResponse,
} from "../services/scenarios";
import { calculateScenario, scenarioEligible } from "../services/scenarios";
import type { Price } from "../types/prices";

interface Props {
  prices: Price[];
  apiBase: string;
}

const quoteKey = (price: Price) =>
  `${price.product_id}::${price.market}::${price.source_url}`;
const money = (value: number) =>
  new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN" }).format(
    value,
  );

export default function ScenarioSimulator({ prices, apiBase }: Props) {
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [quantities, setQuantities] = useState<Record<string, string>>({});
  const [changes, setChanges] = useState<Record<string, string>>({});
  const [result, setResult] = useState<ScenarioResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const available = useMemo(
    () =>
      prices
        .filter(scenarioEligible)
        .sort((a, b) =>
          `${a.product_name} ${a.market}`.localeCompare(
            `${b.product_name} ${b.market}`,
            "es",
          ),
        ),
    [prices],
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const selectedPrices = available.filter((price) => selected[quoteKey(price)]);
    if (!selectedPrices.length) {
      setError("Selecciona al menos un producto para simular.");
      setResult(null);
      return;
    }
    const lines: ScenarioLineInput[] = [];
    for (const price of selectedPrices) {
      const key = quoteKey(price);
      const quantityText = quantities[key] ?? "1";
      const changeText = changes[key] ?? "15";
      const quantity = Number(quantityText);
      const change = Number(changeText);
      if (
        !quantityText || !Number.isFinite(quantity) || quantity <= 0 || quantity > 1000 ||
        !changeText || !Number.isFinite(change) || change < -100 || change > 300
      ) {
        setError("Revisa las cantidades (0–1000 kg) y los cambios (-100% a 300%).");
        setResult(null);
        return;
      }
      lines.push({
        product_id: price.product_id,
        market: price.market,
        source_url: price.source_url,
        quantity_kg: quantity,
        change_percent: change,
      });
    }
    setLoading(true);
    setError(null);
    try {
      setResult(await calculateScenario(apiBase, { items: lines }));
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "No pudimos calcular la simulación.",
      );
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section
      id="escenarios"
      className="scenario-section"
      aria-labelledby="scenario-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">Explora cambios hipotéticos</p>
          <h2 id="scenario-title">Simula variaciones de precios</h2>
          <p>
            Cambia porcentajes y cantidades para comparar un escenario con los
            precios publicados. La simulación no predice precios ni atribuye
            causalidad climática.
          </p>
        </div>
      </div>
      {!available.length ? (
        <div className="empty-state">
          <h3>No hay precios por kg para simular</h3>
        </div>
      ) : (
        <form onSubmit={submit}>
          <div className="scenario-grid">
            {available.map((price) => {
              const key = quoteKey(price);
              return (
                <article className="scenario-product" key={key}>
                  <label className="scenario-select">
                    <input
                      type="checkbox"
                      checked={Boolean(selected[key])}
                      onChange={(event) => {
                        setSelected((current) => ({
                          ...current,
                          [key]: event.target.checked,
                        }));
                        if (event.target.checked && changes[key] === undefined)
                          setChanges((current) => ({ ...current, [key]: "15" }));
                        if (quantities[key] === undefined)
                          setQuantities((current) => ({ ...current, [key]: "1" }));
                      }}
                    />
                    <span>{price.product_name}</span>
                  </label>
                  <p>{price.market}</p>
                  <div className="scenario-inputs">
                    <label>
                      Cambio (%)
                      <input
                        type="number"
                        min="-100"
                        max="300"
                        step="1"
                        value={changes[key] ?? "15"}
                        disabled={!selected[key]}
                        onChange={(event) =>
                          setChanges((current) => ({
                            ...current,
                            [key]: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label>
                      Cantidad (kg)
                      <input
                        type="number"
                        min="0.1"
                        max="1000"
                        step="0.1"
                        value={quantities[key] ?? "1"}
                        disabled={!selected[key]}
                        onChange={(event) =>
                          setQuantities((current) => ({
                            ...current,
                            [key]: event.target.value,
                          }))
                        }
                      />
                    </label>
                  </div>
                  <small>
                    {price.source_institution} · {price.observation_date} · PEN/kg
                  </small>
                </article>
              );
            })}
          </div>
          <div className="shopping-submit-row">
            <button className="button button-dark" type="submit" disabled={loading}>
              {loading ? "Calculando…" : "Calcular simulación"}
            </button>
          </div>
        </form>
      )}
      {error && <div className="error-banner" role="alert">{error}</div>}
      {result && (
        <div className="scenario-result" aria-live="polite">
          <div className="scenario-totals">
            <div><span>Base</span><strong>{money(result.base_total_pen)}</strong></div>
            <div><span>Simulación</span><strong>{money(result.simulated_total_pen)}</strong></div>
            <div><span>Diferencia</span><strong>{money(result.difference_pen)}</strong></div>
          </div>
          <ul>
            {result.items.map((item) => (
              <li key={`${item.product_id}::${item.market}::${item.source_url}`}>
                <div>
                  <strong>{item.product_name}</strong>
                  <span>
                    {item.quantity_kg} kg · {item.change_percent}% · {item.observation_date}
                  </span>
                  <a href={item.source_url} target="_blank" rel="noopener noreferrer">
                    {item.source_institution}
                  </a>
                  {item.quality_flags.length > 0 && (
                    <span className="scenario-quality-flag">
                      Revisar dato: {item.quality_flags.join(", ")}
                    </span>
                  )}
                </div>
                <div className="scenario-line-cost">
                  {money(item.base_cost_pen)} → {money(item.simulated_cost_pen)}
                </div>
              </li>
            ))}
          </ul>
          <p className="fine-print">{result.notice}</p>
          <p className="fine-print">
            Se usa un kg y porcentaje por producto según lo indicado. Los
            precios mayoristas no son precios minoristas.
          </p>
        </div>
      )}
    </section>
  );
}
