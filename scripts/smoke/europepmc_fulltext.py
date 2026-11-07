"""One-request, bounded smoke of the Europe PMC OA fullTextXML endpoint."""

from __future__ import annotations

import urllib.request

PMCID = "PMC9417507"
URL = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{PMCID}/fullTextXML"
USER_AGENT = "CA-Plastics-Atlas/0.1 (S6.1 endpoint smoke; no article text retained)"


def smoke() -> None:
    request = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        assert response.status == 200
        assert "xml" in response.headers.get_content_type()
        # Read only a bounded prefix to verify the JATS document shape; do not
        # save, parse, or process the article body in this smoke.
        prefix = response.read(2048)
    assert b"<!DOCTYPE article" in prefix or b"<article" in prefix
    print(f"Europe PMC {PMCID}: HTTP 200; XML content type; bounded JATS prefix received")


if __name__ == "__main__":
    smoke()
