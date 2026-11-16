import { formatDate, priceLabel } from "../services/presentation";
import type { Price } from "../types/prices";

export default function PriceCard({ item }: { item: Price }) {
  const price = priceLabel(item);
  return (
    <article className="price-card">
      <p className="market-label">{item.market}</p>
      <h3>{item.product_name}</h3>
      <div className="price">
        <strong>{price.value}</strong>
        <span>{price.unit}</span>
      </div>
      {item.quality_flags.length > 0 && (
        <p className="quality-note">
          Observación de calidad: {item.quality_flags.join(", ")}
        </p>
      )}
      <div className="price-card-footer">
        <span>Mayorista · PEN</span>
        <time dateTime={item.observation_date}>
          {formatDate(item.observation_date)}
        </time>
      </div>
    </article>
  );
}
