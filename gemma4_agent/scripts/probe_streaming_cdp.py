"""Probe REAL post-login via CDP attach al Opera GX del user.

Abre un tab nuevo por cada URL candidata. Reporta:
  - http_status / url_after_load (redirects)
  - is_404 (heuristica)
  - clase de pagina (search/home/login_wall)
  - inputs encontrados con varios selectores
  - links de result_card encontrados
  - buttons aria/data-* visibles

Cierra los tabs al terminar.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

CDP_ENDPOINT = "http://127.0.0.1:9222"

CANDIDATES: dict[str, list[dict[str, Any]]] = {
    "disney": [
        {"url": "https://www.disneyplus.com/", "label": "root"},
        {"url": "https://www.disneyplus.com/home", "label": "home"},
        {"url": "https://www.disneyplus.com/search", "label": "search_root"},
        {"url": "https://www.disneyplus.com/es-419/search", "label": "search_es419"},
        # Buscar con ?q= directo por si funciona post-login.
        {"url": "https://www.disneyplus.com/search?q=Loki", "label": "search_q_root"},
        {"url": "https://www.disneyplus.com/es-419/search?q=Loki", "label": "search_q_es419"},
    ],
    "netflix": [
        {"url": "https://www.netflix.com/browse", "label": "browse"},
        {"url": "https://www.netflix.com/search?q=Stranger+Things", "label": "search_q"},
    ],
    "hbo_max": [
        {"url": "https://play.hbomax.com/", "label": "play_root"},
        {"url": "https://play.hbomax.com/search", "label": "play_search"},
        {"url": "https://play.hbomax.com/search?q=House", "label": "play_search_q"},
        {"url": "https://www.hbomax.com/", "label": "www_root"},
        {"url": "https://play.max.com/", "label": "max_root"},
        {"url": "https://play.max.com/search?q=House", "label": "max_search_q"},
    ],
    "prime_video": [
        {"url": "https://www.primevideo.com/", "label": "root"},
        {"url": "https://www.primevideo.com/search/ref=atv_nb_sr?phrase=The+Boys",
         "label": "search_phrase"},
    ],
}


def classify(page) -> dict[str, Any]:
    try:
        title = page.title() or ""
    except Exception:
        title = ""
    try:
        body = page.inner_text("body", timeout=2500)[:600]
    except Exception:
        body = ""
    txt = (title + " " + body).lower()

    is_404 = any(p in txt for p in [
        "cannot be found", "could not be found",
        "no se encontró", "no se encontro",
        "no encontramos la página", "no encontramos la pagina",
        "page you were looking for",
    ])
    is_login = (
        ("sign in" in txt or "iniciar sesión" in txt or "iniciar sesion" in txt
         or "log in" in txt)
        and not is_404
    )

    classification = (
        "404" if is_404
        else "login_wall" if is_login
        else "page_loaded"
    )

    # Inputs candidatos.
    inputs = []
    for sel in [
        "input[type='search']",
        "input[role='searchbox']",
        "input[aria-label*='search' i]",
        "input[aria-label*='buscar' i]",
        "input[placeholder*='search' i]",
        "input[placeholder*='buscar' i]",
        "input[data-uia*='search' i]",
        "input[data-testid*='search' i]",
        "input[name='phrase']",
        "input[name='searchTerm']",
        "input[name='q']",
    ]:
        try:
            n = page.locator(sel).count()
            if n > 0:
                inputs.append({"sel": sel, "count": n})
        except Exception:
            pass

    # Botones de play visibles.
    play_btns = []
    for sel in [
        "[data-uia='play-button']",
        "button[data-testid='play']",
        "button[data-testid='playButton']",
        "button[data-automation-id='playButton']",
        "button[aria-label*='Reproducir' i]",
        "button[aria-label*='Play' i]",
        "[data-testid='hero-play-cta']",
    ]:
        try:
            n = page.locator(sel).count()
            if n > 0:
                play_btns.append({"sel": sel, "count": n})
        except Exception:
            pass

    # Result cards.
    cards = []
    for sel in [
        "[data-uia='search-title-card'] a[href*='/watch/']",
        "[data-uia*='title-card'] a[href*='/watch/']",
        "a[href*='/watch/']",
        "a[href*='/es-419/video/']",
        "a[href*='/es-419/movies/']",
        "a[href*='/es-419/series/']",
        "a[href*='/es-cl/video/']",
        "a[href*='/es-cl/movies/']",
        "a[href*='/es-cl/series/']",
        "a[href*='/video/watch/']",
        "a[href*='/detail/']",
        "a[data-testid*='card']",
        "article a[href*='/detail/']",
    ]:
        try:
            n = page.locator(sel).count()
            if n > 0:
                cards.append({"sel": sel, "count": n})
        except Exception:
            pass

    return {
        "title": title[:120],
        "body_excerpt": body[:200].replace("\n", " ⏎ "),
        "url_after_load": page.url,
        "is_404": is_404,
        "classification": classification,
        "inputs": inputs,
        "play_buttons": play_btns,
        "result_cards": cards,
    }


def main() -> int:
    out_path = Path(__file__).parent.parent / "docs" / "streaming_probe_cdp.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    findings: list[dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_ENDPOINT)
        # Tomar el contexto existente (el del user).
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        print(f"Connected. Existing contexts: {len(browser.contexts)}, "
              f"pages: {sum(len(c.pages) for c in browser.contexts)}",
              file=sys.stderr)

        for platform, cands in CANDIDATES.items():
            print(f"\n=== {platform} ===", file=sys.stderr)
            plat_results: list[dict[str, Any]] = []
            for cand in cands:
                url = cand["url"]
                label = cand["label"]
                print(f"  -> [{label}] {url}", file=sys.stderr)
                page = ctx.new_page()
                try:
                    resp = page.goto(url, wait_until="domcontentloaded",
                                     timeout=25000)
                    status = resp.status if resp else None
                    time.sleep(3.5)  # SPA render time
                    info = classify(page)
                    info["http_status"] = status
                except Exception as exc:
                    info = {"error": f"{type(exc).__name__}: {exc}"}
                info["url_requested"] = url
                info["label"] = label
                plat_results.append(info)
                try:
                    page.close()
                except Exception:
                    pass
            findings.append({"platform": platform, "candidates": plat_results})

        # No cerramos el browser — es del user.

    out_path.write_text(json.dumps(findings, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    # Resumen.
    print("\n\n========== SUMMARY ==========", file=sys.stderr)
    for fp in findings:
        print(f"\n{fp['platform']}:", file=sys.stderr)
        for c in fp["candidates"]:
            tag = c.get("classification", c.get("error", "?"))[:14]
            print(f"  [{tag:>14}] {c.get('label'):>16}  {c.get('url_requested', '?')[:70]}",
                   file=sys.stderr)
            if c.get("url_after_load") and c["url_after_load"] != c.get("url_requested"):
                print(f"                       redirected_to= {c['url_after_load'][:90]}",
                       file=sys.stderr)
            inp = [x["sel"] for x in c.get("inputs") or []][:3]
            cards = [x["sel"] for x in c.get("result_cards") or []][:3]
            btns = [x["sel"] for x in c.get("play_buttons") or []][:3]
            if inp:
                print(f"                       inputs= {inp}", file=sys.stderr)
            if cards:
                print(f"                       cards = {cards}", file=sys.stderr)
            if btns:
                print(f"                       play  = {btns}", file=sys.stderr)
    print(f"\nFull JSON: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
