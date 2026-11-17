"""VD-35: compact page-head bands (owner request 2026-11-17).

Source contracts only. The measured head heights (1440 and 390 px, no overflow, no overlap with the
plane) were checked in a browser against the assembled preview; see scratch/vd35/ for the run.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
COMPONENTS = SRC / "design" / "components.css"
EXPERTS_CSS = SRC / "components" / "experts.css"
FUNDING_CSS = SRC / "components" / "funding.css"


def _block(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css, flags=re.DOTALL)
    assert match is not None, f"missing CSS rule for {selector}"
    return match.group(1)


def test_band_padding_is_about_half_the_old_32_px_block() -> None:
    css = COMPONENTS.read_text(encoding="utf-8")
    band = _block(css, ".atlas-page-head:not(.drawer-header)")
    assert "padding-block: var(--atlas-space-4);" in band
    mobile = re.search(
        r"@media \(max-width: 42rem\) \{.*?\.atlas-page-head:not\(\.drawer-header\) \{([^}]*)\}",
        css,
        flags=re.DOTALL,
    )
    assert mobile is not None, "the 42rem breakpoint must reduce the band padding"
    assert "padding-block: var(--atlas-space-3);" in mobile.group(1)


def test_band_eyebrow_lead_and_meta_spacing_is_tight() -> None:
    css = COMPONENTS.read_text(encoding="utf-8")
    assert "margin: 0 0 var(--atlas-space-1);" in _block(css, ".atlas-page-head__eyebrow")
    assert "margin: var(--atlas-space-2) 0 0;" in _block(css, ".atlas-page-head__lead")
    assert "margin-top: var(--atlas-space-3);" in _block(css, ".atlas-page-head__meta")


def test_lead_is_body_size_and_the_framework_measure_cap_is_overridden() -> None:
    css = COMPONENTS.read_text(encoding="utf-8")
    lead = _block(css, ".atlas-page-head__lead")
    assert "font-size: var(--atlas-type-body-size);" in lead
    assert "1.05rem" not in lead
    # The framework's `#observablehq-main p` caps paragraphs at 70ch; a prefixed rule outranks it.
    assert "max-width: none;" in _block(css, "#observablehq-main .atlas-page-head__lead")


def test_no_page_re_caps_the_head_lead() -> None:
    for path in sorted(SRC.rglob("*.css")):
        css = path.read_text(encoding="utf-8")
        for selectors, body in re.findall(r"([^{}]*__lead[^{}]*)\{([^}]*)\}", css):
            if "max-width" in body:
                assert "max-width: none;" in body, f"{path.name}: {selectors.strip()} caps the lead"


def test_experts_and_funding_heads_follow_the_shared_lead() -> None:
    assert "80ch" not in EXPERTS_CSS.read_text(encoding="utf-8")
    assert "80ch" not in FUNDING_CSS.read_text(encoding="utf-8")
    experts = EXPERTS_CSS.read_text(encoding="utf-8")
    assert "#experts-root .experts-page-head {" in experts
    assert "padding-inline: clamp(1rem, 2.5vw, 1.75rem);" in experts
    assert "padding: 0.65rem" not in experts


def test_plane_is_absolutely_positioned_so_it_never_sets_the_band_height() -> None:
    css = COMPONENTS.read_text(encoding="utf-8")
    pseudo = _block(
        css,
        ".atlas-page-head:not(.drawer-header)::before,\n.atlas-page-head:not(.drawer-header)::after",
    )
    assert "position: absolute;" in pseudo
    assert "bottom: 0;" in pseudo
    assert "padding-right: calc(var(--atlas-plane-w) + var(--atlas-space-4));" in css
