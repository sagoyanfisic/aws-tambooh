import { useCallback, useEffect, useState } from "react";
import { fetchPrices } from "../services/prices";
import type { PricesResponse } from "../types/prices";

export function usePrices() {
  const [data, setData] = useState<PricesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    let timedOut = false;
    const timeout = window.setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, 12000);
    setLoading(true);
    setError(null);
    fetchPrices(import.meta.env.VITE_API_BASE_URL || "", controller.signal)
      .then((result) => {
        if (active && !controller.signal.aborted) setData(result);
      })
      .catch((reason: unknown) => {
        if (!active || (controller.signal.aborted && !timedOut)) return;
        setError(
          timedOut
            ? "El servicio está tardando en responder. Puedes volver a intentarlo."
            : reason instanceof Error
              ? reason.message
              : "No pudimos cargar los precios.",
        );
      })
      .finally(() => {
        window.clearTimeout(timeout);
        if (active && (!controller.signal.aborted || timedOut))
          setLoading(false);
      });
    return () => {
      active = false;
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [revision]);

  return { data, loading, error, refresh };
}
