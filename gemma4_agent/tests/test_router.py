"""Router test: verify the deterministic planner picks the right subset.

Does NOT call the LLM. Runs `plan_mission` + `select_tool_names` on a battery
of realistic queries and asserts that the chosen subset:
  - contains the tools we expect (required),
  - does not exceed the size cap,
  - excludes obviously-wrong tools (forbidden, optional).

Run with: python -m gemma4_agent.test_router
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

from ..routing.planner import MAX_SELECTED_TOOLS, plan_mission, select_tool_names


@dataclass
class Case:
    query: str
    must_include: tuple[str, ...]
    must_exclude: tuple[str, ...] = ()


CASES: list[Case] = [
    # Casual / no PC action
    Case("quien es batman", must_include=(), must_exclude=("steam", "filesystem", "browser_real")),
    Case("hola", must_include=(), must_exclude=("steam", "media", "filesystem")),

    # Apps / Steam
    Case("abre Steam y ve a mi biblioteca", must_include=("steam",), must_exclude=()),
    Case("abre el bloc de notas", must_include=("app",), must_exclude=("steam",)),
    Case("cierra Logitech G HUB", must_include=("app",)),

    # Media
    Case("pon Billie Jean en YouTube", must_include=("media",)),
    Case("baja el volumen", must_include=("audio",)),
    Case("cambia el dispositivo de audio a AUX", must_include=("audio_device",)),

    # Browser
    Case("abre Chrome y busca el clima de hoy en Google", must_include=("browser",)),
    Case("investiga noticias del mercado cripto con fuentes", must_include=("web", "source_manager")),
    Case("rellena el formulario de la web", must_include=("form_filler", "browser_real")),

    # Filesystem / docs
    Case("crea un archivo notas.txt en escritorio", must_include=("filesystem",)),
    Case("hazme un powerpoint sobre Gemma 4", must_include=("office",)),
    Case("lee este PDF y resumelo", must_include=("document",)),

    # Phase C/D/F3 tools
    Case("corre los tests del proyecto", must_include=("developer",)),
    Case("hazme ping a google.com", must_include=("network",)),
    Case("estado del firewall y windows defender", must_include=("maintenance",)),
    Case("analiza este csv y haz un histograma", must_include=("data_analysis",)),
    Case("conecta al wifi MiCasa con esta clave", must_include=("device_settings",)),
    Case("apaga las luces del living en home assistant", must_include=("smart_home",)),
    Case("lanza Fortnite desde Epic", must_include=("game_launcher",)),
    Case("recorta este video del segundo 30 al 60", must_include=("media_edit",)),
    Case("dame los contenedores docker que estan corriendo", must_include=("container",)),
    Case("consulta la base de datos sqlite users.db", must_include=("database",)),
    Case("genera una imagen con stable diffusion", must_include=("creative_local",)),
    Case("organiza mis fotos por fecha", must_include=("photo_library",)),
    Case("haz una flashcard del tema fotosintesis", must_include=("study",)),
    Case("activa la lupa de windows", must_include=("accessibility",)),
    Case("status de los controles xbox conectados", must_include=("peripheral",)),
    Case("vigila este archivo y avisame cuando cambie", must_include=("watcher",)),
    Case("verifica si la afirmacion 'python es interpretado' es cierta", must_include=("fact_check",)),

    # Cleanup expected
    Case("cierra todo lo que abriste", must_include=("state",)),

    # ---- Multi-language (English) ----
    Case("open Steam and go to my library", must_include=("steam",)),
    Case("play Billie Jean on YouTube", must_include=("media",)),
    Case("turn down the volume", must_include=("audio",)),
    Case("open Chrome and search for the weather", must_include=("browser",)),
    Case("read this PDF and summarize it", must_include=("document",)),
    Case("ping google.com", must_include=("network",)),
    Case("turn off the living room light", must_include=("smart_home",)),
    Case("run the project tests", must_include=("developer",)),
    Case("analyze this csv and plot a histogram", must_include=("data_analysis",)),
    Case("organize my photos by date", must_include=("photo_library",)),
    Case("verify if the claim 'python is interpreted' is true", must_include=("fact_check",)),
    Case("close the application", must_include=("app",)),

    # ---- Multi-language (Portuguese) ----
    Case("abra o Steam e va para minha biblioteca", must_include=("steam",)),
    Case("toque uma musica no YouTube", must_include=("media",)),
    Case("baixe o volume", must_include=("audio",)),
    Case("leia este pdf e resuma", must_include=("document",)),
    Case("apague a luz da sala", must_include=("smart_home",)),
    Case("organize minhas fotos por data", must_include=("photo_library",)),

    # ---- Multi-language (French) ----
    Case("ouvre Steam et va dans ma bibliotheque", must_include=("steam",)),
    Case("joue une chanson sur YouTube", must_include=("media",)),
    Case("baisse le volume", must_include=("audio",)),
    Case("lis ce pdf et resume-le", must_include=("document",)),
    Case("eteins la lumiere du salon", must_include=("smart_home",)),
    Case("organise mes photos par date", must_include=("photo_library",)),

    # ---- Multi-language (Italian) ----
    Case("apri Steam e vai alla mia libreria", must_include=("steam",)),
    Case("riproduci una canzone su YouTube", must_include=("media",)),
    Case("abbassa il volume", must_include=("audio",)),
    Case("leggi questo pdf e riassumilo", must_include=("document",)),
    Case("spegni la luce del soggiorno", must_include=("smart_home",)),
]


def test_open_browser_not_abstained() -> None:
    """S3c (2026-05-30) regression. "abre el navegador" used to yield an EMPTY
    domain subset: its nearest exemplar was a reflexive question ("me abrí el
    navegador?" label []) whose abstain vote edged 4 command-neighbors by ~0.005,
    and the exemplar abstention short-circuited the whole planner. The
    abstain-MARGIN fix requires the no-tool vote to BEAT the best tool vote, not
    merely tie it. A bare "open the browser" imperative must offer app/browser.
    NB: we assert recall only (app reachable), not the cap — these queries pull a
    same-domain cluster (app+browser+browser_real+computer_use) that exceeds 5;
    trimming that noise is the precision sprint, tracked separately."""
    for q in ("abre el navegador", "Abri el navegador",
              "abre el navegador predeterminado"):
        subset = set(select_tool_names(q, plan_mission(q), safety_enabled=False))
        assert "app" in subset or "browser" in subset, (
            f"{q!r} must offer app/browser, got {sorted(subset)}")
    # The fix must NOT silence genuine no-tool turns (reflexive question / meta).
    for q in ("me abrí el navegador?",):
        subset = set(select_tool_names(q, plan_mission(q), safety_enabled=False))
        domain = subset - {"session", "safety"}
        assert not domain, f"{q!r} should abstain, got {sorted(domain)}"


def test_local_state_question_offers_window_not_only_session() -> None:
    """BUG real (log voz turnos 13/14, 2026-06-03): "¿qué juego estoy jugando?"
    -> el abstain_head trató la pregunta de ESTADO LOCAL como smalltalk (FP frágil
    a mayúscula/?/wake-leak) y el fallback devolvía solo ['session'] -> el 4B
    forzaba session.cancel_turn ante una PREGUNTA. La responde window(action=
    'active'). El router debe ofrecer `window` y NUNCA dejar SOLO ['session']."""
    for q in ("Bixby, ¿qué juego estoy jugando?",   # wake-leak + acento + ?
              "Max ¿qué juego estoy jugando?",
              "¿qué juego estoy jugando?",
              "Que juego estoy jugando?",            # May + ? sin ¿ (caía a session)
              "qué aplicación está abierta",
              "qué ventana está activa",
              "what game am I playing"):
        subset = select_tool_names(q, plan_mission(q), safety_enabled=False)
        assert "window" in subset, f"{q!r} must offer window, got {subset}"
        assert subset != ["session"], f"{q!r} fell back to only session"

    # ANTI-REGRESIÓN: el detector NO debe robar acciones ni smalltalk genuino.
    # Una ACCIÓN ("cerrá la ventana") sigue su ruta (window por keyword, no por
    # el fallback de estado-local); smalltalk real NO debe traer window por esto.
    for q in ("hola qué tal", "gracias", "contame un chiste"):
        subset = set(select_tool_names(q, plan_mission(q), safety_enabled=False))
        assert "window" not in subset, f"{q!r} should not offer window, got {sorted(subset)}"


def test_app_state_check_offers_system_not_app_tool() -> None:
    """BUG real (eval dataset run2, 2026-06-04): "¿Steam está abierto?" ofrecía
    `steam` (cuyo default es ABRIR) -> el 4B abría Steam y MENTÍA "Listo, abrí
    Steam". Una pregunta de ESTADO read-only la responde system(processes)/window;
    el router debe RETIRAR steam/browser/app e inyectar system/window."""
    for q in ("revisa si Steam está abierto", "Steam está cerrado?",
              "revisa si Chrome está abierto", "is Discord running?"):
        subset = select_tool_names(q, plan_mission(q), safety_enabled=False)
        assert "system" in subset or "window" in subset, f"{q!r} -> {subset}"
        assert "steam" not in subset and "browser" not in subset, (
            f"{q!r} no debe ofrecer la tool de la app (abre, no chequea): {subset}")

    # ANTI-REGRESIÓN: una ACCIÓN sobre la app NO debe ser tratada como chequeo.
    s_open = select_tool_names("abrí Steam", plan_mission("abrí Steam"))
    assert "steam" in s_open or "app" in s_open, f"'abrí Steam' debe ofrecer steam/app: {s_open}"
    # "si X está abierto, cerralo" lleva acción -> NO retirar (debe quedar window/app)
    s_cond = select_tool_names("si Chrome está abierto cierralo",
                               plan_mission("si Chrome está abierto cierralo"))
    assert "window" in s_cond or "app" in s_cond, f"condicional-acción: {s_cond}"


def test_howto_question_suppresses_destructive_tools() -> None:
    """BUG real (cacería tanda 1): "cómo elimino una carpeta" -> filesystem.delete
    BORRÓ la carpeta ante una PREGUNTA (daño irreversible). Una pregunta how-to/info
    pide EXPLICACIÓN, no ejecución: el router retira las tools destructivas."""
    from ..routing.planner import _is_howto_or_info_question
    # detector: how-to/info = True, imperativo = False
    for q in ("cómo elimino una carpeta de pruebas", "cómo cierro Spotify",
              "qué es Python", "para qué sirve pytest", "how do I delete a folder"):
        assert _is_howto_or_info_question(q), f"{q!r} debe ser how-to"
    for q in ("elimina la carpeta de pruebas", "cerrá Spotify",
              "borra mi carpeta Documentos", "como siempre abrí Discord",
              "ordená como quieras"):
        assert not _is_howto_or_info_question(q), f"{q!r} NO es how-to"

    # routing: how-to no ofrece destructivas; imperativo sí.
    DESTRUCTIVE = {"filesystem", "system", "package", "developer"}
    s_howto = set(select_tool_names("cómo elimino una carpeta de pruebas",
                                    plan_mission("cómo elimino una carpeta de pruebas")))
    assert not (s_howto & DESTRUCTIVE), f"how-to no debe ofrecer destructivas: {s_howto}"
    s_imp = set(select_tool_names("elimina la carpeta de pruebas",
                                  plan_mission("elimina la carpeta de pruebas")))
    assert "filesystem" in s_imp, f"imperativo SÍ debe ofrecer filesystem: {s_imp}"


def test_trigger_declaration_routes_to_routine_not_action() -> None:
    """BUG real (cacería tanda 1, B2): "cuando diga X quiero que hagas Y" debe CREAR
    una rutina, NO ejecutar Y ahora. "cuando diga pantallazo saca captura" sacaba la
    captura YA. El detector retira las tools de acción y deja routine."""
    from ..routing.planner import _is_trigger_declaration
    for q in ("cuando diga pantallazo quiero que saques una captura",
              "cuando te diga tiempo apretá la tecla",
              "cada vez que diga siguiente apretá next",
              "when I say next press the key"):
        assert _is_trigger_declaration(q), f"{q!r} es declaración de trigger"
    for q in ("sacá una captura", "abrí Spotify", "cuando llegues a casa avisame",
              "cuando termine el proceso cerralo"):
        assert not _is_trigger_declaration(q), f"{q!r} NO es trigger"

    # routing: trigger -> routine, sin la tool de acción inmediata
    s = set(select_tool_names("cuando diga pantallazo quiero que saques una captura",
                              plan_mission("cuando diga pantallazo quiero que saques una captura")))
    assert "routine" in s, f"trigger debe ofrecer routine: {s}"
    assert not (s & {"gui", "media", "audio"}), f"trigger no debe ofrecer acción: {s}"


def test_low_signal_noise_abstains() -> None:
    """BUG real (cacería tanda 1, B3): un número/medición suelto ("2.14s", "7.63",
    "12.66") no es un comando — el router lo ruteaba a window.active/media.play
    arbitrariamente ("Listo, abrí Steam" ante ruido). El gate de ruido abstiene
    para que el LLM pida aclaración. ESTRUCTURAL, mide la FORMA."""
    from ..routing.planner import _is_low_signal_noise
    # POSITIVOS: número/medida puro = ruido.
    for q in ("2.14s", "7.63", "12.66", "11.22s", "100%", "64 GB", "60fps", "12,66"):
        assert _is_low_signal_noise(q), f"{q!r} es ruido (número/medida suelto)"
    # NEGATIVOS: comando con número, o texto con palabras = NO ruido.
    for q in ("pon el volumen al 50", "abre 3 pestañas", "sube el volumen al 80",
              "minimiza la ventana", "abre steam", "que hora es", "el tercero"):
        assert not _is_low_signal_noise(q), f"{q!r} NO es ruido"
    # GUARDA pending_intent: un número es la RESPUESTA esperada, no ruido.
    assert not _is_low_signal_noise("50", has_pending_intent=True), (
        "número con pending_intent es la respuesta, no ruido")

    # routing: ruido -> abstención (NO window/media/app), solo session.
    for q in ("2.14s", "7.63", "12.66"):
        s = set(select_tool_names(q, plan_mission(q)))
        assert not (s & {"window", "media", "app", "audio", "browser", "job_manager"}), (
            f"ruido {q!r} no debe rutear a acción: {s}")
    # con pending_intent un número NO se gatea (debe poder routear normal).
    s_pending = set(select_tool_names(
        "50", plan_mission("50"),
        pending_intent={"tool": "audio", "args": {}, "asks_for": "volume"}))
    # el gate no disparó -> el subset NO es solo el abstain base.
    assert "audio" in s_pending or s_pending != {"session"}, (
        f"número con pending no debe gatearse a abstain: {s_pending}")


def test_browser_real_collapsed_on_simple_nav() -> None:
    """S3d (2026-05-30) precision. browser_real (fine CDP control) was offered
    on EVERY browser turn as noise (measured: 78 noise rows vs 2 that truly need
    it). The hierarchical collapse drops browser_real when the turn wants simple
    navigation — discriminated by score (encoder ranks `browser` > `browser_real`
    for "open/go to", and `browser_real` >= `browser` for "fill the form"/"click").
    Recall-neutral, measured 0 loss on both corpora. NOT a keyword rule."""
    # Simple navigation → browser_real must be gone (browser stays).
    for q in ("abre el navegador", "abre chrome", "ve a youtube"):
        subset = set(select_tool_names(q, plan_mission(q), safety_enabled=False))
        assert "browser_real" not in subset, (
            f"{q!r} is simple nav; browser_real is noise, got {sorted(subset)}")
    # Real web control → browser_real MUST be kept (score protects it).
    for q in ("llena el formulario de esta pagina", "rellena el formulario de la web"):
        subset = set(select_tool_names(q, plan_mission(q), safety_enabled=False))
        assert "browser_real" in subset, (
            f"{q!r} needs CDP control; browser_real must stay, got {sorted(subset)}")


def run() -> int:
    passes = 0
    fails: list[str] = []
    for case in CASES:
        plan = plan_mission(case.query)
        subset = select_tool_names(case.query, plan, safety_enabled=False)
        subset_set = set(subset)
        problems: list[str] = []
        if len(subset) > MAX_SELECTED_TOOLS:
            problems.append(f"subset oversize {len(subset)} > {MAX_SELECTED_TOOLS}")
        missing = [t for t in case.must_include if t not in subset_set]
        if missing:
            problems.append(f"missing required {missing}")
        forbidden = [t for t in case.must_exclude if t in subset_set]
        if forbidden:
            problems.append(f"forbidden present {forbidden}")
        if problems:
            fails.append(f"FAIL: {case.query!r}\n  subset={subset}\n  -> {'; '.join(problems)}")
        else:
            passes += 1

    print(f"router tests: {passes}/{len(CASES)} passing")
    for line in fails:
        print(line)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(run())
