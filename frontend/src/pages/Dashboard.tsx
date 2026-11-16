import { useMemo, useState } from "react";
import PriceCard from "../components/PriceCard";
import { usePrices } from "../hooks/usePrices";
import { ageInDays, filterPrices, formatDate } from "../services/presentation";

export default function Dashboard() {
  const { data, loading, error, refresh } = usePrices();
  const [query, setQuery] = useState("");
  const [market, setMarket] = useState("");
  const [people, setPeople] = useState(4);
  const [budget, setBudget] = useState(65);
  const items = data?.items ?? [];
  const markets = useMemo(
    () => [...new Set(items.map((item) => item.market))].sort(),
    [items],
  );
  const visible = filterPrices(items, query, market);
  const staleCount = items.filter(
    (item) => ageInDays(item.observation_date) > 2,
  ).length;
  const sources = [
    ...new Map(items.map((item) => [item.source_url, item])).values(),
  ];

  return (
    <>
      <a className="skip-link" href="#contenido">
        Saltar al contenido
      </a>
      <header className="site-header">
        <div className="shell header-inner">
          <a className="brand" href="#" aria-label="TamBooh, inicio">
            <span className="brand-mark" aria-hidden="true">
              t.
            </span>
            TamBooh<span className="brand-dot">.</span>
          </a>
          <nav aria-label="Navegación principal">
            <a href="#precios">Precios</a>
            <a href="#fuentes">Fuentes</a>
            <a href="#hogar">Mi hogar</a>
          </nav>
          <span className="country-badge">
            <span aria-hidden="true">●</span> Perú · piloto
          </span>
        </div>
      </header>
      <main className="shell" id="contenido">
        <section className="hero" aria-labelledby="hero-title">
          <div>
            <p className="eyebrow">
              <span aria-hidden="true">↗</span> Información para decidir mejor
            </p>
            <h1 id="hero-title">
              Conoce los precios.
              <br />
              <em>Planea con confianza.</em>
            </h1>
            <p className="hero-copy">
              Consulta cotizaciones de mercados mayoristas del Perú, con su
              fecha y fuente a la vista. Una base transparente para cuidar el
              presupuesto familiar.
            </p>
            <a className="button button-dark" href="#precios">
              Explorar precios <span aria-hidden="true">↓</span>
            </a>
          </div>
          <aside
            className="observation-card"
            aria-label="Fecha de los datos publicados"
          >
            <span className="observation-icon" aria-hidden="true">
              ◷
            </span>
            <p>Última observación publicada</p>
            <strong>
              {data?.last_updated
                ? formatDate(data.last_updated)
                : loading
                  ? "Consultando…"
                  : error
                    ? "Consulta no disponible"
                    : "Sin publicación"}
            </strong>
            <div className="observation-meta">
              <span className="small-dot" aria-hidden="true" />
              Precios fechados, siempre
            </div>
            <p className="observation-note">
              La fecha corresponde al reporte de origen. No implica una descarga
              automática en este momento.
            </p>
          </aside>
        </section>
        <section className="stats" aria-label="Resumen de datos">
          <div>
            <strong>{data ? items.length : "—"}</strong>
            <span>Cotizaciones publicadas</span>
          </div>
          <div>
            <strong>{data ? markets.length : "—"}</strong>
            <span>Mercados representados</span>
          </div>
          <div>
            <strong>PEN</strong>
            <span>Moneda original · soles</span>
          </div>
          <div>
            <strong>Mayorista</strong>
            <span>Nivel comercial de los precios</span>
          </div>
        </section>
        <div className="notice">
          <span className="notice-symbol" aria-hidden="true">
            i
          </span>
          <p>
            <strong>Un precio mayorista no es un precio de tienda.</strong> Las
            cotizaciones no incluyen un cálculo de compra minorista, transporte
            ni preparación. Tampoco son pronósticos.
          </p>
        </div>
        <section
          id="precios"
          className="prices-section"
          aria-labelledby="prices-title"
          aria-busy={loading}
        >
          <div className="section-heading">
            <div>
              <p className="eyebrow">Del reporte a tu pantalla</p>
              <h2 id="prices-title">Precios con contexto</h2>
              <p>
                Compara productos y consulta el mercado al que pertenece cada
                cotización.
              </p>
            </div>
            <button
              className="button button-outline"
              onClick={refresh}
              disabled={loading}
            >
              <span aria-hidden="true">↻</span>
              {loading ? "Consultando…" : "Actualizar consulta"}
            </button>
          </div>
          {error && (
            <div className="error-banner" role="alert">
              <strong>No pudimos actualizar los precios.</strong>
              <p>{error}</p>
              {data && (
                <p>
                  Se conservan los últimos datos recibidos en esta sesión, con
                  sus fechas originales.
                </p>
              )}
            </div>
          )}
          {staleCount > 0 && (
            <div className="stale-banner" role="status">
              Hay {staleCount} cotizaciones con más de dos días de antigüedad.
              Revisa la fecha de cada producto antes de usar su precio como
              referencia.
            </div>
          )}
          <div className="filters">
            <label className="search-field">
              <span className="sr-only">Buscar producto</span>
              <span aria-hidden="true">⌕</span>
              <input
                type="search"
                placeholder="Buscar papa, zanahoria, manzana…"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <label className="market-select">
              <span>Mercado</span>
              <select
                value={market}
                onChange={(event) => setMarket(event.target.value)}
              >
                <option value="">Todos los mercados</option>
                {markets.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="results-count" aria-live="polite">
            {data
              ? `${visible.length} de ${items.length} cotizaciones`
              : loading
                ? "Cargando cotizaciones publicadas…"
                : "Sin datos disponibles"}
          </p>
          {loading && !data ? (
            <div className="prices-grid" aria-label="Cargando precios">
              {Array.from({ length: 6 }, (_, index) => (
                <div key={index} className="skeleton-card" aria-hidden="true">
                  <div />
                  <div />
                  <div />
                </div>
              ))}
            </div>
          ) : visible.length > 0 ? (
            <div className="prices-grid">
              {visible.map((item) => (
                <PriceCard
                  key={`${item.product_id}-${item.market}-${item.observation_date}-${item.unit_original}`}
                  item={item}
                />
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <span aria-hidden="true">◇</span>
              <h3>
                {items.length
                  ? "No encontramos coincidencias"
                  : error
                    ? "No pudimos cargar los precios"
                    : "Aún no hay precios para mostrar"}
              </h3>
              <p>
                {items.length
                  ? "Prueba otro producto o selecciona todos los mercados."
                  : error
                    ? "Usa Actualizar consulta para volver a intentarlo."
                    : "Cuando haya un reporte publicado disponible, aparecerá aquí. Puedes volver a consultar más tarde."}
              </p>
              {items.length > 0 && (
                <button
                  className="button button-outline"
                  onClick={() => {
                    setQuery("");
                    setMarket("");
                  }}
                >
                  Limpiar filtros
                </button>
              )}
            </div>
          )}
        </section>
        <div className="lower-grid">
          <section
            id="fuentes"
            className="info-panel"
            aria-labelledby="sources-title"
          >
            <p className="eyebrow">Transparencia primero</p>
            <h2 id="sources-title">Detrás de cada dato</h2>
            <p>
              Los valores conservan la moneda y el nivel comercial del
              documento. La fecha del reporte y la fecha de procesamiento son
              datos diferentes.
            </p>
            {sources.length ? (
              <ul className="sources-list">
                {sources.map((source) => (
                  <li key={source.source_url}>
                    <strong>{source.source_institution}</strong>
                    <a
                      href={source.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Consultar fuente de origen{" "}
                      <span aria-hidden="true">↗</span>
                    </a>
                    {source.source_url.startsWith("http:") && (
                      <small>
                        El servidor de origen utiliza HTTP sin cifrar.
                      </small>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">
                Las fuentes aparecerán al cargar las cotizaciones.
              </p>
            )}
            <p className="fine-print">
              Un reporte puede cargarse mediante un archivo oficial importado.
              El enlace de origen puede cambiar su contenido cuando la
              institución publique un nuevo reporte.
            </p>
          </section>
          <section
            id="hogar"
            className="household-panel"
            aria-labelledby="household-title"
          >
            <p className="eyebrow">Pensemos en tu semana</p>
            <h2 id="household-title">Una referencia para tu hogar</h2>
            <p>
              Configura el escenario de demostración. Estos valores no se
              guardan y todavía no generan un menú ni una lista de compras.
            </p>
            <div className="household-fields">
              <label>
                Integrantes
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={people}
                  onChange={(event) => {
                    const value = Number(event.target.value);
                    if (Number.isInteger(value) && value >= 1 && value <= 20)
                      setPeople(value);
                  }}
                />
              </label>
              <label>
                Presupuesto semanal (USD)
                <input
                  type="number"
                  min="1"
                  max="10000"
                  value={budget}
                  onChange={(event) => {
                    const value = Number(event.target.value);
                    if (Number.isFinite(value) && value >= 1 && value <= 10000)
                      setBudget(value);
                  }}
                />
              </label>
            </div>
            <p className="budget-note">
              USD {budget} para {people}{" "}
              {people === 1 ? "integrante" : "integrantes"} es una referencia
              ilustrativa, no el costo oficial de una canasta. Los precios se
              muestran en PEN: no aplicamos un tipo de cambio sin una fuente
              validada.
            </p>
          </section>
        </div>
      </main>
      <footer className="site-footer">
        <div className="shell footer-inner">
          <a className="brand" href="#">
            TamBooh<span className="brand-dot">.</span>
          </a>
          <p>Alimentación informada, familias más resilientes.</p>
          <span>Perú · Precios mayoristas · Fuentes visibles</span>
        </div>
      </footer>
    </>
  );
}
