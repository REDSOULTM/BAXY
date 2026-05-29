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
