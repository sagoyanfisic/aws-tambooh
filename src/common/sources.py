"""Bounded official-file discovery with TLS checks, robots and domain pacing."""
import time
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

SOURCE_URLS = {
    "sisap_mananero": "http://sistemas.midagri.gob.pe/sisap/intranet/mayoristas_lima/modulos/reporte_precios.pdf",
    "papa_boletin": "https://www.gob.pe/institucion/midagri/colecciones/5-boletin-diario-de-abastecimiento-y-precio-de-papa",
    "productores": "https://www.gob.pe/institucion/midagri/colecciones/18-reporte-de-ingreso-y-precios-en-el-mercado-mayorista-de-productores",
}
ALLOWED_HOSTS = {"sistemas.midagri.gob.pe", "siea.midagri.gob.pe", "www.gob.pe", "cdn.www.gob.pe"}
MONTH_NAMES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
               "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MAX_BYTES = 12 * 1024 * 1024
USER_AGENT = "TamBooh-ingest/0.2 (+https://github.com/sagoyanfisic/aws-tambooh)"


class TransientSourceError(RuntimeError):
    pass


class SourceConfigurationError(ValueError):
    pass


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.extend(v for k, v in attrs if k == "href" and v)


class OfficialClient:
    def __init__(self):
        self.client = httpx.Client(timeout=httpx.Timeout(10, connect=5), follow_redirects=False,
                                   headers={"User-Agent": USER_AGENT}, verify=True)
        self.last = {}
        self.robots = {}
        self.deadline = time.monotonic() + 110

    def close(self):
        self.client.close()

    def _request(self, url):
        host = urlsplit(url).hostname
        if host not in ALLOWED_HOSTS or urlsplit(url).scheme not in {"http", "https"}:
            raise SourceConfigurationError("URL is outside the official allow-list")
        for attempt in range(3):
            delay = max(0, 3 - (time.monotonic() - self.last.get(host, -100)))
            if time.monotonic() + delay + 10 > self.deadline:
                raise TransientSourceError("Download time budget exhausted")
            time.sleep(delay)
            self.last[host] = time.monotonic()
            try:
                with self.client.stream("GET", url) as response:
                    if response.status_code in {429, 500, 502, 503, 504}:
                        raise TransientSourceError(f"HTTP {response.status_code}")
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        if time.monotonic() > self.deadline:
                            raise TransientSourceError("Download deadline exceeded")
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise ValueError("Response exceeds 12 MiB")
                        chunks.append(chunk)
                    return response.status_code, dict(response.headers), b"".join(chunks)
            except (httpx.TransportError, TransientSourceError) as exc:
                if attempt == 2:
                    raise TransientSourceError("Official source unavailable after 3 attempts") from exc
                time.sleep(2 ** attempt)

    def get(self, url, redirects=0):
        host = urlsplit(url).hostname
        if host not in ALLOWED_HOSTS:
            raise SourceConfigurationError("Unofficial host")
        if host not in self.robots:
            robot_url = f"{urlsplit(url).scheme}://{host}/robots.txt"
            status, _, body = self._request(robot_url)
            if status not in {200, 404}:
                raise SourceConfigurationError("robots.txt unavailable or restricted")
            robot = RobotFileParser()
            robot.parse(body.decode(errors="replace").splitlines() if status == 200 else [])
            self.robots[host] = robot
        if not self.robots[host].can_fetch(USER_AGENT, url):
            raise SourceConfigurationError("robots.txt disallows request")
        status, headers, body = self._request(url)
        if status in {301, 302, 303, 307, 308}:
            if redirects >= 3:
                raise SourceConfigurationError("Too many redirects")
            return self.get(urljoin(url, headers["location"]), redirects + 1)
        if status not in {200, 404}:
            raise SourceConfigurationError(f"Source returned HTTP {status}")
        return status, headers, body, url


def date_matches(url, day):
    return any(token in url.lower() for token in (
        day.strftime("%d-%m-%Y"), day.strftime("%d_%m_%Y"), day.isoformat()))


def resolve_and_download(client, source_id, day: date, source_url=None):
    if source_id == "gmml_ingreso" and (not source_url or source_url.endswith("/mml/")):
        months = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic"]
        candidates = [months[day.month - 1]] + (["sep"] if day.month == 9 else [])
        result = None
        for month in candidates:
            url = (f"https://siea.midagri.gob.pe/files/datos_estadisticas/diarias/mml/"
                   f"{day:%Y/%m}/sisap-ingreso-gmml-{day:%d}{month}{day:%y}.pdf")
            result = client.get(url)
            if result[0] == 200:
                return result
        return result
    url = source_url or SOURCE_URLS.get(source_id)
    if not url:
        raise SourceConfigurationError("A dated official PDF URL is required")
    result = client.get(url)
    if result[0] == 404 or result[2].startswith(b"%PDF"):
        return result
    # Only two page levels: the supplied collection, then its current month publication.
    pages = [result]
    visited = {url}
    for depth in range(2):
        next_pages = []
        for _, _, body, page_url in pages:
            links = Links()
            links.feed(body.decode(errors="replace"))
            absolute = [urljoin(page_url, link) for link in links.links]
            for link in absolute:
                if "?sheet=" in link or urlsplit(link).hostname not in ALLOWED_HOSTS:
                    continue
                if ".pdf" in link.lower() and date_matches(link, day):
                    return client.get(link)
            if depth == 0:
                for link in absolute:
                    if ("/informes-publicaciones/" in link and str(day.year) in link
                            and (MONTH_NAMES[day.month - 1] in link.lower()
                                 or (day.month == 9 and "setiembre" in link.lower())
                                 or date_matches(link, day))
                            and urlsplit(link).hostname == "www.gob.pe" and link not in visited):
                        visited.add(link)
                        next_pages.append(client.get(link))
                        if len(next_pages) >= 2:
                            break
        pages = next_pages
    raise SourceConfigurationError("No dated PDF found within bounded discovery; supply source_url")
