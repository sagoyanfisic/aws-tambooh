"""Bounded official-file discovery with TLS checks, robots and domain pacing."""

import re
import time
from datetime import date
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

SOURCE_URLS = {
    "sisap_mananero": "http://sistemas.midagri.gob.pe/sisap/intranet/mayoristas_lima/modulos/reporte_precios.pdf",
    "papa_boletin": "https://www.gob.pe/institucion/midagri/colecciones/5-boletin-diario-de-abastecimiento-y-precio-de-papa",
    "productores": "https://www.gob.pe/institucion/midagri/colecciones/18-reporte-de-ingreso-y-precios-en-el-mercado-mayorista-de-productores",
}
ALLOWED_HOSTS = {"sistemas.midagri.gob.pe", "siea.midagri.gob.pe", "www.gob.pe", "cdn.www.gob.pe"}
MONTH_NAMES = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]
MAX_BYTES = 12 * 1024 * 1024
USER_AGENT = "TamBooh-ingest/0.2 (+https://github.com/sagoyanfisic/aws-tambooh)"
REDIRECT_CODES = {301, 302, 303, 307, 308}
MAX_DISCOVERY_PAGES = 5


class TransientSourceError(RuntimeError):
    pass


class SourceConfigurationError(ValueError):
    pass


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.entries = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = next((v for k, v in attrs if k == "href" and v), None)
            if href:
                self.links.append(href)
                self.current = [href, ""]
                self.entries.append(self.current)

    def handle_data(self, data):
        if self.current is not None:
            self.current[1] += f" {data}"

    def handle_endtag(self, tag):
        if tag == "a":
            self.current = None


def validate_source_url(url):
    parts = urlsplit(url)
    if (
        parts.hostname not in ALLOWED_HOSTS
        or parts.scheme not in {"http", "https"}
        or parts.username
        or parts.password
        or parts.port not in {None, 80, 443}
    ):
        raise SourceConfigurationError("URL is outside the official allow-list")
    if any(key.lower() == "sheet" for key in parse_qs(parts.query, keep_blank_values=True)):
        raise SourceConfigurationError("Collection pagination is not supported")
    return parts


def public_url(url):
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.hostname}{parts.path}"


class OfficialClient:
    def __init__(self):
        self.client = httpx.Client(
            timeout=httpx.Timeout(10, connect=5),
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT},
            verify=True,
        )
        self.last = {}
        self.robots = {}
        self.deadline = time.monotonic() + 110

    def close(self):
        self.client.close()

    def _request(self, url):
        host = validate_source_url(url).hostname
        for attempt in range(3):
            delay = max(0, 3 - (time.monotonic() - self.last.get(host, -100)))
            if time.monotonic() + delay + 10 > self.deadline:
                raise TransientSourceError(f"Download time budget exhausted: {public_url(url)}")
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
                    raise TransientSourceError(
                        f"Official source unavailable after 3 attempts: {public_url(url)}; "
                        f"{type(exc).__name__}: {str(exc)[:250]}"
                    ) from exc
                time.sleep(2**attempt)

    def _robots_for(self, url):
        parts = validate_source_url(url)
        origin = (parts.scheme, parts.hostname)
        if origin not in self.robots:
            robot_url = f"{parts.scheme}://{parts.hostname}/robots.txt"
            for redirects in range(6):
                status, headers, body = self._request(robot_url)
                if status not in REDIRECT_CODES:
                    break
                if redirects == 5 or not headers.get("location"):
                    raise SourceConfigurationError("robots.txt redirect limit or missing Location")
                target = urljoin(robot_url, headers["location"])
                validate_source_url(target)
                if robot_url.startswith("https://") and target.startswith("http://"):
                    raise SourceConfigurationError("robots.txt HTTPS downgrade refused")
                robot_url = target
            if status not in {200, 404}:
                raise SourceConfigurationError(
                    f"robots.txt unavailable or restricted: HTTP {status}; {public_url(robot_url)}"
                )
            robot = RobotFileParser()
            robot.parse(body.decode(errors="replace").splitlines() if status == 200 else [])
            self.robots[origin] = robot
        return self.robots[origin]

    def get(self, url, redirects=0):
        validate_source_url(url)
        if not self._robots_for(url).can_fetch(USER_AGENT, url):
            raise SourceConfigurationError(f"robots.txt disallows request: {public_url(url)}")
        status, headers, body = self._request(url)
        if status in REDIRECT_CODES:
            if redirects >= 3 or not headers.get("location"):
                raise SourceConfigurationError("Too many redirects or missing Location")
            target = urljoin(url, headers["location"])
            if url.startswith("https://") and target.startswith("http://"):
                raise SourceConfigurationError("HTTPS downgrade refused")
            return self.get(target, redirects + 1)
        if status not in {200, 404}:
            raise SourceConfigurationError(f"Source returned HTTP {status}: {public_url(url)}")
        return status, headers, body, url


def date_matches(url, day):
    text = unquote(url).lower()
    return bool(
        re.search(rf"(?<!\d)0?{day.day}[-_/]0?{day.month}[-_/]{day.year}(?!\d)", text)
        or re.search(rf"(?<!\d){day.year}[-_/]0?{day.month}[-_/]0?{day.day}(?!\d)", text)
    )


def resolve_and_download(client, source_id, day: date, source_url=None):
    if source_id == "gmml_ingreso" and (not source_url or source_url.endswith("/mml/")):
        months = [
            "ene",
            "feb",
            "mar",
            "abr",
            "may",
            "jun",
            "jul",
            "ago",
            "set",
            "oct",
            "nov",
            "dic",
        ]
        candidates = [months[day.month - 1]] + (["sep"] if day.month == 9 else [])
        result = None
        for month in candidates:
            url = (
                f"https://siea.midagri.gob.pe/files/datos_estadisticas/diarias/mml/"
                f"{day:%Y/%m}/sisap-ingreso-gmml-{day:%d}{month}{day:%y}.pdf"
            )
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
    # Collection -> optional year collection -> month publication. Never paginate.
    pages = [(result, 0)]
    visited = {result[3]}
    inspected = 0
    while pages and inspected < MAX_DISCOVERY_PAGES:
        (_, _, body, page_url), depth = pages.pop(0)
        inspected += 1
        links = Links()
        links.feed(body.decode(errors="replace"))
        candidates = []
        for href, label in links.entries:
            link = urljoin(page_url, href)
            parts = urlsplit(link)
            if parts.hostname not in ALLOWED_HOSTS or any(
                key.lower() == "sheet" for key in parse_qs(parts.query, keep_blank_values=True)
            ):
                continue
            text = unquote(f"{link} {label}").lower()
            if ".pdf" in unquote(parts.path).lower() and date_matches(text, day):
                return client.get(link)
            if depth >= 2 or parts.hostname != "www.gob.pe" or link in visited:
                continue
            if not parts.path.startswith("/institucion/midagri/"):
                continue
            relevant = ("papa" in text) if source_id == "papa_boletin" else ("productores" in text)
            month_matches = MONTH_NAMES[day.month - 1] in text or (
                day.month == 9 and "setiembre" in text
            )
            publication = "/informes-publicaciones/" in parts.path and (
                date_matches(text, day) or (str(day.year) in text and month_matches)
            )
            year_collection = "/colecciones/" in parts.path and str(day.year) in text
            if relevant and (publication or year_collection):
                candidates.append((not publication, link))
        for _, link in sorted(candidates, key=lambda item: item[0]):
            if link not in visited and len(visited) < MAX_DISCOVERY_PAGES:
                visited.add(link)
                pages.append((client.get(link), depth + 1))
    raise SourceConfigurationError(
        f"No dated PDF for {day.isoformat()} found within {inspected} official pages; "
        "supply a verified dated PDF source_url or import_s3_key"
    )
