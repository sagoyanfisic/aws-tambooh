Local text fixtures represent extracted table text for four source families and are demonstration data.

`sisap_mananero_2026-11-16.pdf` is the real one-page report found in the operator's downloaded local files. Its date is November 16, 2026, 06:17 Lima time; it contains 18 rows across three wholesale markets. The adjacent `.provenance.json` preserves its supplied source URL, original transport, size and SHA-256. File authenticity and the original HTTP download were not independently verified. Treat its prices as a dated fixture, never as current live data.

The Mañanero regression test reads the real PDF using pdfplumber and checks header mapping, observation date, markets and extracted amounts. It skips if the test interpreter lacks the PDF dependency; CI installs the project dependencies. The other three source families still require real PDF fixtures and layout verification. No source was downloaded by contacting AWS or using the local default profile to prepare this fixture.
