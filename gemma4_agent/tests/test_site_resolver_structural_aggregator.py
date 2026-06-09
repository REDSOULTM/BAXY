"""La señal ESTRUCTURAL anti-agregador reemplaza la lista hardcoded
_NON_SITE_HOSTS (2026-06-09): un nombre identifica AL SITIO solo si es un LABEL
COMPLETO del dominio, no un substring parcial de un label.

Esto descarta perfiles/redes de tercero SIN una lista de dominios -> universal:
cubre los casos que la lista protegía (insta/reddi/face: fragmentos de redes
famosas) Y los agregadores no-occidentales que la lista NO contemplaba
(VK/Weibo/Naver). Medición: scripts/_diag/_diag_non_site_hosts.py.
"""
from __future__ import annotations

import unittest

from gemma4_agent.tools_pkg.site_resolver import resolve_site_by_search

_FILLERS = frozenset({"el", "la", "de", "del", "the", "to", "go", "ir", "ve",
                      "portal", "pagina", "página", "sitio", "web"})


def _mk_search(urls):
    return lambda args: {"ok": True, "results": [{"url": u} for u in urls]}


def _resolve(name, urls):
    return resolve_site_by_search(
        name,
        web_search=_mk_search(urls),
        fillers=_FILLERS,
        search_all_backends=lambda q, lim=12: [],
    )


class StructuralAggregatorSignalTest(unittest.TestCase):
    def test_third_party_profile_in_path_is_discarded(self):
        # instagram.com/foo -> 'foo' está en el PATH, no en el dominio -> None.
        self.assertIsNone(_resolve("foo", ["https://www.instagram.com/foo/"]))

    def test_partial_fragment_of_famous_network_is_discarded(self):
        # 'insta' es substring de 'instagram' pero NO un label completo -> prefiere
        # el sitio real cuyo label ES 'insta'.
        got = _resolve("insta", ["https://www.instagram.com/",
                                 "https://insta.com.br/"])
        self.assertIsNotNone(got)
        self.assertIn("insta.com.br", got)

    def test_fragment_with_no_real_site_returns_none(self):
        # 'reddi' ⊂ 'reddit' pero no es label -> y no hay sitio 'reddi' -> None
        # (honesto: no abrir reddit.com que el user no pidió).
        self.assertIsNone(_resolve("reddi", ["https://www.reddit.com/"]))

    def test_asking_the_network_itself_resolves(self):
        # pedir 'youtube'/'instagram' EN SÍ -> el token ES la SLD -> sí resuelve.
        self.assertIn("youtube.com", _resolve("youtube", ["https://www.youtube.com/"]))
        self.assertIn("instagram.com",
                      _resolve("instagram", ["https://www.instagram.com/"]))

    def test_real_site_over_aggregator_profile(self):
        # caso clásico pivigames: perfil IG primero, sitio real 2do -> gana el sitio.
        got = _resolve("pivigames", ["https://www.instagram.com/pivigames/",
                                     "https://pivigames.blog/"])
        self.assertIn("pivigames.blog", got)

    def test_non_western_aggregators_discarded_without_list(self):
        # VK/Weibo/Naver NO estaban en la vieja lista; la señal estructural los
        # descarta igual porque el nombre va en el path / no es label del agregador.
        self.assertIn("mimarca.ru",
                      _resolve("mimarca", ["https://vk.com/mimarca",
                                           "https://mimarca.ru/"]))
        self.assertIn("algunos.cn",
                      _resolve("algunos", ["https://weibo.com/algunos",
                                           "https://algunos.cn/"]))

    def test_multiword_with_filler_token_resolves_by_remaining_label(self):
        # 'portal uniej': 'portal' es filler -> queda 'uniej', que ES un label de
        # portal.uniej.edu.sv -> resuelve (no se rompe por el filtro de labels).
        got = _resolve("portal uniej", ["https://portal.uniej.edu.sv/"])
        self.assertIsNotNone(got)
        self.assertIn("uniej", got)

    def test_long_exact_sld_resolves(self):
        got = _resolve("mercadolibre", ["https://www.mercadolibre.com.ar/"])
        self.assertIn("mercadolibre", got)


if __name__ == "__main__":
    unittest.main()
