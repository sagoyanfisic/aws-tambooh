from datetime import date

import pytest

from src.common.sources import SourceConfigurationError, resolve_and_download


class Pages:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        code, body = self.pages.get(url, (404, b""))
        return code, {}, body, url


def test_gmml_uses_dated_pdf_and_september_alternative():
    url = "https://siea.midagri.gob.pe/files/datos_estadisticas/diarias/mml/2026/09/sisap-ingreso-gmml-14sep26.pdf"
    client = Pages({url: (200, b"%PDF-test")})
    result = resolve_and_download(client, "gmml_ingreso", date(2026, 9, 14))
    assert result[3] == url
    assert len(client.calls) == 2
    assert client.calls[0].endswith("14set26.pdf")
    assert not any(call.endswith("/mml/") for call in client.calls)


def test_collection_discovers_month_page_and_exact_date_pdf():
    root = "https://www.gob.pe/institucion/midagri/colecciones/test"
    month = "https://www.gob.pe/institucion/midagri/informes-publicaciones/123-papa-noviembre-2026"
    pdf = "https://cdn.www.gob.pe/boletin-de-volumen-y-precio-de-papa-14-11-2026.pdf"
    client = Pages({root: (200, f'<a href="{month}">Month</a>'.encode()),
                    month: (200, f'<a href="{pdf}">PDF</a>'.encode()),
                    pdf: (200, b"%PDF-test")})
    assert resolve_and_download(client, "papa_boletin", date(2026, 11, 14), root)[3] == pdf
    assert len(client.calls) == 3


def test_missing_publication_does_not_guess_data():
    url = "https://www.gob.pe/test"
    with pytest.raises(SourceConfigurationError, match="No dated PDF"):
        resolve_and_download(Pages({url: (200, b"<html>No report</html>")}),
                             "papa_boletin", date(2026, 11, 14), url)


def test_404_is_a_normal_source_result():
    assert resolve_and_download(Pages({}), "sisap_mananero", date(2026, 11, 14))[0] == 404
