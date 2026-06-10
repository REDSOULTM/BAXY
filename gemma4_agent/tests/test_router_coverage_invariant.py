"""Invariante de ROBUSTEZ del router (S5, 2026-05-30).

El router debe seguir funcionando y no desconfigurarse cuando se agreguen más
tools o MCPs. Estos tests son la red que atrapa esa desconfiguración ANTES de que
llegue a producción.

La fragilidad real: el router decide el subset por VARIAS capas (keyword regex,
per-tool head, tool2vec, descripciones semánticas). Una tool de DOMINIO nueva que
se agregue al schema PERO no se enrole en ninguna de esas capas queda INVISIBLE:
el router nunca la ofrece, el LLM nunca la ve, y nadie se entera hasta que un
usuario la pide y "no pasa nada". Estos tests fallan RUIDOSO con el nombre exacto
de la tool huérfana, así que el que agrega la tool sabe qué le falta.

Tools META/INTERNAL están exentas a propósito (entran por otra vía, no por el
router de dominio): session/state/verify/safety (siempre alcanzables),
skill_load/subagent (meta-tools del system prompt), mcp/file_process (gated,
inyectadas por su propio path), computer_use (rescate semántico operacional).
Si agregás una tool META nueva, sumala a _EXEMPT con un comentario del por qué.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from ..tools_pkg.tool_schemas import COMPOUND_TOOL_SCHEMAS

ROOT = Path(__file__).resolve().parent.parent

# Tools que NO rutean por el router de dominio (entran por otra vía). Exentas del
# requisito de cobertura. Cada una con su razón.
_EXEMPT: frozenset[str] = frozenset({
    "session", "state", "verify", "safety",  # meta: siempre alcanzables / append post-cap
    "skill_load", "subagent",                # meta-tools del system prompt (no router)
    "mcp",                                    # bridge MCP: inyectada cuando hay enrolados
    "file_process",                           # gate B6: agregada por _file_processor_on()
    "computer_use",                           # rescate semántico operacional (_CU_SEM_RESCUE)
})


def _all_tool_names() -> set[str]:
    return {s["function"]["name"] for s in COMPOUND_TOOL_SCHEMAS}


def _tool_head_tools() -> set[str]:
    try:
        from ..tools_pkg.tool_head import load as th_load
        th = th_load()
        return set(getattr(th, "tools", []) or []) if th is not None else set()
    except Exception:
        return set()


def _semantic_described() -> set[str]:
    try:
        from ..routing.semantic_router import TOOL_DESCRIPTIONS
        return set(TOOL_DESCRIPTIONS.keys())
    except Exception:
        return set()


def _tool2vec_tools() -> set[str]:
    p = ROOT / "data" / "tool2vec_queries.jsonl"
    if not p.exists():
        return set()
    out: set[str] = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.add(json.loads(line)["tool"])
        except Exception:
            continue
    return out


class TestRouterCoverageInvariant(unittest.TestCase):
    """Toda tool de dominio debe ser ALCANZABLE por el router."""

    def test_every_domain_tool_has_router_coverage(self) -> None:
        """Una tool de dominio sin NINGUNA capa (head/sem/t2v) es invisible: el
        router jamás la ofrecería. Esto atrapa el "agregué una tool y el router
        no la conoce" — la desconfiguración exacta que este invariante previene."""
        domain = _all_tool_names() - _EXEMPT
        covered = _tool_head_tools() | _semantic_described() | _tool2vec_tools()
        orphaned = sorted(domain - covered)
        self.assertEqual(
            orphaned, [],
            f"Tools de DOMINIO sin cobertura del router (invisibles): {orphaned}. "
            f"Enrolá cada una en al menos una capa: descripción semántica "
            f"(TOOL_DESCRIPTIONS), per-tool head (reentrenar tool_head), o "
            f"tool2vec_queries.jsonl. Si es una META-tool, agregala a _EXEMPT.")

    def test_domain_tools_have_redundant_coverage(self) -> None:
        """ROBUSTEZ por capas: una tool de dominio con UNA sola capa es frágil
        (si esa capa falla, desaparece). Exigimos >=2 capas — así ninguna tool
        depende de un único punto. Hoy se cumple (medido); el test lo congela."""
        domain = _all_tool_names() - _EXEMPT
        head, sem, t2v = _tool_head_tools(), _semantic_described(), _tool2vec_tools()
        # Si las fuentes no cargaron (entorno sin modelo/datos), no afirmar.
        if not (head or sem or t2v):
            self.skipTest("ninguna fuente de cobertura cargó (entorno mínimo)")
        fragile = []
        for t in sorted(domain):
            layers = sum(1 for s in (head, sem, t2v) if t in s)
            if layers <= 1:
                fragile.append((t, layers))
        self.assertEqual(
            fragile, [],
            f"Tools de dominio con cobertura FRÁGIL (<=1 capa): {fragile}. "
            f"Una tool de una sola capa desaparece si esa capa falla. "
            f"Dale al menos una descripción semántica + ejemplos tool2vec.")

    def test_no_zombie_tools_in_head(self) -> None:
        """El tool_head no debe disparar tools que ya NO existen en el schema
        (un rename/borrado dejaría un zombie que el router ofrece pero el
        dispatcher rechaza)."""
        head = _tool_head_tools()
        if not head:
            self.skipTest("tool_head no cargó")
        zombies = sorted(head - _all_tool_names())
        self.assertEqual(
            zombies, [],
            f"tool_head dispara tools inexistentes (zombies tras rename/borrado): "
            f"{zombies}. Reentrená el head o quitá esas tools del schema.")

    def test_semantic_descriptions_match_schema(self) -> None:
        """Toda descripción semántica debe corresponder a una tool real (un
        rename dejaría la descripción apuntando a la nada)."""
        sem = _semantic_described()
        if not sem:
            self.skipTest("TOOL_DESCRIPTIONS no cargó")
        # mcp__* son enrolamientos dinámicos, no del schema base: exentos.
        stale = sorted(t for t in (sem - _all_tool_names())
                       if not t.startswith("mcp__"))
        self.assertEqual(
            stale, [],
            f"Descripciones semánticas de tools inexistentes: {stale}.")


class TestAddingToolsDoesNotRegress(unittest.TestCase):
    """ROBUSTEZ dinámica: enrolar tools/MCPs nuevas NO debe quitarle a una
    query nativa la tool que ya le correspondía. Esta es la garantía exacta del
    invariante: no desconfigurarse al meter más tools o MCPs."""

    def _subset(self, q: str):
        from ..routing.planner import select_tool_names, plan_mission
        return set(select_tool_names(q, plan_mission(q), safety_enabled=True))

    def _router_available(self) -> bool:
        # Si el encoder no cargó, el ruteo semántico no corre — no afirmar.
        try:
            from ..routing.semantic_router import _ensure_loaded
            return bool(_ensure_loaded())
        except Exception:
            return False

    def test_enrolling_mcps_preserves_native_recall(self) -> None:
        """Con N MCPs irrelevantes enrolados, las queries nativas deben seguir
        ofreciendo su tool de dominio. Mide ANTES y DESPUÉS de enrolar: ninguna
        debe perder su tool nativa por el ruido del enrolamiento."""
        if not self._router_available():
            self.skipTest("encoder semántico no disponible")
        from ..routing import semantic_router as SR
        native_cases = [
            ("abre whatsapp", "app"),
            ("sube el volumen", "audio"),
            ("pon una cancion en spotify", "media"),
            ("hablame de bruno mars", "web"),
            ("abre el navegador", "browser"),
        ]
        # baseline sin MCPs
        SR.enroll_mcp_tools([])
        before = {q: self._subset(q) for q, _ in native_cases}
        # enrolar MCPs irrelevantes (un dominio totalmente distinto)
        fake_mcps = [
            {"id": f"mcp__crm__action_{i}",
             "server": "crm", "tool": f"action_{i}",
             "description": f"CRM customer relationship operation number {i}"}
            for i in range(12)
        ]
        try:
            SR.enroll_mcp_tools(fake_mcps)
            for q, must in native_cases:
                after = self._subset(q)
                self.assertIn(
                    must, after,
                    f"enrolar MCPs le quitó {must!r} a {q!r}: {sorted(after)}")
                # y NO debe haberse colado una CRM MCP en una query nativa.
                leaked = [t for t in after if t.startswith("mcp__crm__")]
                self.assertEqual(
                    leaked, [],
                    f"MCP irrelevante se coló en {q!r}: {leaked}")
        finally:
            SR.enroll_mcp_tools([])  # limpiar siempre
        # tras de-enrolar, el subset vuelve EXACTO al baseline (0 residuo).
        for q, _ in native_cases:
            self.assertEqual(
                self._subset(q), before[q],
                f"de-enrolar MCPs no restauró el subset de {q!r}")


class TestDeadMetaToolsNotOfferedToLLM(unittest.TestCase):
    """R1+R2 (2026-05-30): skill_load y subagent son meta-tools MUERTAS — el 4B
    las emitió 1 y 0 veces respectivamente en 117.764 eventos reales. No deben
    llegar al 4B: ni el router las ofrece, ni el menú de skills las anuncia. Las
    skills entran por AUTO-INJECT (determinista), no por skill_load. Estos tests
    congelan que nadie las reintroduzca al prompt del 4B por accidente."""

    def _router_available(self) -> bool:
        try:
            from ..routing.semantic_router import _ensure_loaded
            return bool(_ensure_loaded())
        except Exception:
            return False

    def test_router_never_offers_dead_meta_tools(self) -> None:
        """Ni siquiera en queries que 'ameritarían' skill_load/subagent el router
        debe ofrecerlas (el 4B no las usa; las skills entran por auto-inject)."""
        if not self._router_available():
            self.skipTest("encoder semántico no disponible")
        from ..routing.planner import select_tool_names, plan_mission
        tempting = [
            "saca una captura y decime que ves",       # screenshot skill
            "investiga sobre rust en internet",         # research skill
            "busca en mi biblioteca los juegos metroidvania",  # subagent-bait
            "hace backup antes de limpiar",             # backup skill
            "delega esta tarea a otro agente",          # subagent-bait literal
        ]
        for q in tempting:
            sub = set(select_tool_names(q, plan_mission(q), safety_enabled=True))
            self.assertNotIn("skill_load", sub,
                             f"el router ofreció skill_load (muerta) en {q!r}")
            self.assertNotIn("subagent", sub,
                             f"el router ofreció subagent (muerta) en {q!r}")

    def test_skills_menu_empty_by_default(self) -> None:
        """R1: el menú '# SKILLS AVAILABLE' (que instruye skill_load) está vacío
        por default — ~558 tok/turno que el 4B ignoraba. Restaurable con
        GEMMA4_SKILLS_MENU=1."""
        import os
        from ..tools_pkg.skills_registry import scan_skills, build_menu
        # Asegurar el default (el test no debe depender del env del runner).
        prev = os.environ.pop("GEMMA4_SKILLS_MENU", None)
        try:
            menu = build_menu(scan_skills())
            self.assertEqual(menu, "",
                             "el menú de skills debe estar vacío por default (R1)")
            # Con el gate ON, el menú vuelve (no se perdió la capacidad).
            os.environ["GEMMA4_SKILLS_MENU"] = "1"
            menu_on = build_menu(scan_skills())
            # Puede estar vacío si no hay skills, pero con skills debe traer el header.
            if scan_skills():
                self.assertIn("SKILLS AVAILABLE", menu_on)
        finally:
            os.environ.pop("GEMMA4_SKILLS_MENU", None)
            if prev is not None:
                os.environ["GEMMA4_SKILLS_MENU"] = prev

    def test_purchase_guard_still_active(self) -> None:
        """La skill critical de SEGURIDAD (purchase-guard) NO se ve afectada por
        R1 — entra por el critical block, no por el menú."""
        from ..tools_pkg.skills_registry import scan_skills, build_critical_block
        crit = build_critical_block(scan_skills())
        self.assertIn("purchase-guard", crit,
                      "purchase-guard (seguridad) debe seguir en el critical block")


if __name__ == "__main__":
    unittest.main()
