"""Repro OFFLINE del bug de honestidad app.open->web fallback (2026-06-01).

Sin LLM, sin abrir nada real: mockeamos app_open (no-encuentra), web_search
(el buscador SIEMPRE devuelve algo) y web_open_url (no abre nada). Ejercemos
t_app(action=open) con:
  - gibberish 'ZxqwInexistente9000'  -> el buscador resuelve a un sitio IRRELEVANTE
  - sitio real 'pivigames'           -> el buscador resuelve a pivigames.blog
  - dominio 'gmail.com'              -> dominio directo
  - 'instant gaming'                 -> instant-gaming.com (host CONTIENE el nombre)
"""
from __future__ import annotations

from unittest.mock import MagicMock

from gemma4_agent.tools_pkg.tools import ToolRegistry


def _reg():
    reg = ToolRegistry.__new__(ToolRegistry)
    # app_open: no encuentra la app (caso gibberish / sitios)
    reg.app_open = lambda a: {"ok": False, "error": "app not found", "query": a.get("name")}
    # web_open_url: NO abre nada; devuelve el shape de éxito honesto del deeplink.
    def _web_open(a):
        return {"ok": True, "opened": True, "url": a.get("url"),
                "completion_status": "open_url_requested"}
    reg.web_open_url = _web_open
    return reg


# Mapa controlado de lo que el buscador "devuelve" por nombre.
SEARCH_DB = {
    "aplicacion ZxqwInexistente9000": [
        # gibberish: el buscador da CUALQUIER cosa irrelevante (caso real Bing).
        {"url": "https://www.softonic.com/downloads/applications"},
        {"url": "https://es.wikipedia.org/wiki/Aplicaci%C3%B3n"},
    ],
    "ZxqwInexistente9000": [
        {"url": "https://www.softonic.com/downloads/applications"},
        {"url": "https://es.wikipedia.org/wiki/Aplicaci%C3%B3n"},
    ],
    "pivigames": [
        {"url": "https://pivigames.blog/2018/old-mirror/category/aviso/"},
        {"url": "https://pivigames.blog/"},
    ],
    "gmail.com": [
        {"url": "https://mail.google.com/"},
        {"url": "https://www.gmail.com/"},
    ],
    "instant gaming": [
        {"url": "https://www.instant-gaming.com/es/"},
    ],
    "portal uniej": [
        # caso real: Canvas de la UNIEJ; el host NO contiene "portal uniej" textual,
        # pero contiene "uniej".
        {"url": "https://aulavirtual.uniej.cl/login"},
        {"url": "https://www.uniej.cl/"},
    ],
}


def main():
    for nm in ["aplicacion ZxqwInexistente9000", "pivigames", "gmail.com",
               "instant gaming", "portal uniej"]:
        reg = _reg()
        reg.web_search = lambda a, _nm=nm: {"ok": True, "results": SEARCH_DB.get(_nm, [])}
        resolved = reg._resolve_site_by_search(nm)
        out = reg.t_app({"action": "open", "name": nm})
        verdict = "OPENED(success)" if (out.get("ok") and out.get("opened")) else "honest-not-opened"
        print(f"name={nm!r}")
        print(f"  resolved={resolved!r}")
        print(f"  ok={out.get('ok')} opened={out.get('opened')} "
              f"completion={out.get('completion_status')} error={out.get('error')!r}")
        print(f"  resolved_url={out.get('resolved_url')!r}")
        print(f"  note={out.get('note')!r}")
        print(f"  => {verdict}")
        print()


if __name__ == "__main__":
    main()
