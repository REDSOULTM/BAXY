"""Ronda 23, referente del seguimiento (comprobación en vivo r21, v3-50 t2, falso éxito).

Turno 1 «en 7zip abrí el prueba.zip que está en baxy-prueba-v3»; turno 2 «decime cuántos archivos tiene adentro». El
decisor lo reformuló «en 7-Zip File Manager, decime cuántos archivos tiene adentro» (turn_audit request 12), sin
«prueba.zip»: la misión contó la carpeta y BAXY dijo «hay 7 archivos en la carpeta» (el zip tiene 3). Dos arreglos:
la forma de la pregunta (un verbo de contener o un «adentro» sin complemento) depende del turno anterior
(``dialogue.leans_on_context``), y la reformulación de un turno que depende conserva el objeto nombrado antes
(``dialogue.objective_with_the_antecedent_object``, aplicado en ``_context_decided_result``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from baxy_mind.planner import PlannerCatalog  # noqa: E402
from baxy_mind.semantic import dialogue, missions  # noqa: E402
from baxy_mind.semantic.decider import ContextDecision  # noqa: E402

from test_cu_v3_r20b_preguntas import (  # noqa: E402
    FOLLOW_OPERATIONS, SEVEN_ZIP_APPS, SEVEN_ZIP_TURN, _decided, _Decider, _tool,
)
from baxy_mind import engine_handoff
from baxy_mind import context_decision

SEEN = "decime cuántos archivos tiene adentro"
RESTATED = "en 7-Zip File Manager, decime cuántos archivos tiene adentro"


@pytest.mark.parametrize(
    "said", [SEEN, "¿qué tiene?", "¿cuántos hay adentro?", "what is inside", "What's inside?", "¿y qué traen?"],
)
def test_a_question_for_the_inside_with_nothing_named_leans_on_the_turn_before(said: str) -> None:
    assert dialogue.leans_on_context(said)
    slot = dialogue.read_slot({}, [{"role": "user", "content": SEVEN_ZIP_TURN}, {"role": "user", "content": said}], said)
    assert dialogue.dependency(said, slot) == "followup"


@pytest.mark.parametrize(
    "said",
    [
        "¿qué hora es?", "cuántos archivos tiene la carpeta Descargas", "¿qué tiene adentro un huevo?",
        "¿qué contiene la vitamina C?", "qué tiene de bueno el plan premium", "how many files are inside the zip",
        "¿cuántos años tiene Messi?",
    ],
)
def test_a_question_complete_by_itself_does_not_lean(said: str) -> None:
    # Contracaso: un sujeto, un lugar o un complemento propio; o nada que preguntar de lo anterior.
    assert not dialogue.asks_the_inside_of_the_last(said)


def test_the_objects_a_request_names() -> None:
    assert dialogue.named_objects(SEVEN_ZIP_TURN) == ("prueba.zip",)
    assert dialogue.named_objects("abrí «Spotify» y poné «Queen»") == ("Spotify", "Queen")
    assert dialogue.named_objects("abrí «Informe final» en el bloc") == ("Informe final",)
    # Contracaso: una dirección web, un lugar, un complemento con mayúscula o una pregunta que sólo apunta no nombran
    # objeto (m174 «la lista para el paseo a Santa Marta»).
    assert dialogue.named_objects("andá a youtube.com") == ()
    assert dialogue.named_objects("hace una lista para el paseo a Santa Marta") == ()
    assert dialogue.named_objects(SEEN) == ()


def test_the_restatement_that_lost_the_object_is_repaired_with_it() -> None:
    is_application = engine_handoff._names_an_application(SEVEN_ZIP_APPS)
    assert dialogue.objective_with_the_antecedent_object(
        RESTATED, SEEN, SEVEN_ZIP_TURN, is_application=is_application,
    ) == f"{RESTATED} (prueba.zip)"
    assert dialogue.objective_with_the_antecedent_object("qué tiene", "¿qué tiene?", SEVEN_ZIP_TURN) == (
        "qué tiene (prueba.zip)")


@pytest.mark.parametrize(
    ("restated", "said", "antecedent"),
    [
        # Contracaso: la reformulación ya conserva el objeto.
        ("en 7-Zip, contá los archivos de prueba.zip", SEEN, SEVEN_ZIP_TURN),
        # Contracaso: el mensaje nombra su propio objeto.
        ("contá los archivos de otro.zip", "cuántos archivos tiene otro.zip", SEVEN_ZIP_TURN),
        # Contracaso: lo nombrado antes es la aplicación, que la reformulación enmarca ella misma.
        ("en Spotify, qué tiene", "¿qué tiene?", "abrí «Spotify»"),
        # Contracaso: el turno anterior no nombró objeto alguno.
        ("en la calculadora, qué tiene", "¿qué tiene?", "abrí la calculadora"),
        # Revisión 1, contracaso: la reformulación ya dio a la pregunta un objeto o un lugar propio.
        ("qué tiene la carpeta Descargas", "¿qué tiene?", "abrí la carpeta Descargas y seleccioná foto.jpg"),
        ("en la carpeta Descargas, qué tiene", "¿qué tiene?", "abrí la carpeta Descargas y seleccioná foto.jpg"),
        # Revisión 1, contracaso: un pedido que no pregunta por el contenido de lo anterior, dependa o no de él.
        ("calcula 37*12", "en la calculadora calculá 37*12", SEVEN_ZIP_TURN),
        ("buscá el clima de mañana", "buscá el clima de mañana", "abrí informe.pdf"),
        ("seguí", "dale, seguí", "en el explorador borrá foto.jpg"),
        ("abrí la Calculadora", "y ahora abrí la calculadora", "en el bloc de notas abrí informe.txt"),
    ],
)
def test_nothing_is_repaired_when_nothing_was_lost(restated: str, said: str, antecedent: str) -> None:
    is_application = engine_handoff._names_an_application((*SEVEN_ZIP_APPS, "Spotify"))
    assert dialogue.objective_with_the_antecedent_object(
        restated, said, antecedent, is_application=is_application,
    ) is None


def test_the_follow_up_of_v3_50_keeps_the_zip_in_the_mission() -> None:
    result = _decided(SEEN, ContextDecision(RESTATED, "action", ("mission.computer.use",), ""))
    assert result["operation"] == "mission.computer.use"
    assert result["objective"] == f"{RESTATED} (prueba.zip)"
    mission = missions.mission_request(result["objective"], SEVEN_ZIP_APPS)
    assert mission is not None and "prueba.zip" in mission.goal


def test_a_self_sufficient_question_after_the_mission_keeps_the_decider_request() -> None:
    # Contracaso: «¿qué hora es?» no depende del turno anterior; nada se le agrega.
    decision = ContextDecision("¿Qué hora es?", "action", ("system.time",), "")
    result = _decided("¿qué hora es?", decision)
    assert "prueba.zip" not in str(result.get("objective") or "")


def test_the_lexicon_words_are_folded() -> None:
    from baxy_mind.semantic import lexicon
    from baxy_mind.semantic.normalize import fold

    assert all(fold(word) == word for word in lexicon.BARE_HOLDING_VERBS | lexicon.FILE_EXTENSIONS)


# Revisión 1: turnos del banco (s01, v8, g1) tras el turno del zip, con el decisor reformulando igual que la persona;
# en la base ya dependían del turno anterior, y nada del zip debe pegárseles.
BANK_TURNS = (
    "en la calculadora calculá 37*12",
    "en Spotify andá a Inicio",
    "abrí Steam, andá a la biblioteca y buscá Cuphead",
)


@pytest.mark.parametrize("said", BANK_TURNS)
def test_a_new_order_after_the_zip_turn_gets_nothing_of_it(said: str) -> None:
    result = _decided(said, ContextDecision(said, "action", ("mission.computer.use",), ""))
    assert "prueba.zip" not in str(result.get("objective") or "")
    mission = missions.mission_request(str(result.get("objective") or said), SEVEN_ZIP_APPS)
    assert mission is None or "prueba.zip" not in mission.goal


@pytest.mark.parametrize(
    ("antecedent", "said", "decision", "named"),
    [
        ("abrí informe.pdf", "buscá el clima de mañana",
         ContextDecision("buscá el clima de mañana", "action", ("web.search",), ""), "informe.pdf"),
        ("en el bloc de notas abrí informe.txt", "y ahora abrí la calculadora",
         ContextDecision("abrí la Calculadora", "action", ("app.open",), ""), "informe.txt"),
        ("en el explorador borrá foto.jpg", "dale, seguí",
         ContextDecision("seguí", "action", ("mission.computer.use",), ""), "foto.jpg"),
        ("abrí la carpeta Descargas y seleccioná foto.jpg", "¿qué tiene?",
         ContextDecision("qué tiene la carpeta Descargas", "action", ("mission.computer.use",), ""), "foto.jpg"),
    ],
)
def test_a_typed_or_unrelated_turn_after_a_named_file_keeps_the_decider_request(
    antecedent: str, said: str, decision: ContextDecision, named: str,
) -> None:
    # Contracaso de punta a punta: web.search, app.open, una continuación y una pregunta que el decisor ya completó.
    result = _decided(said, decision, history=[{"role": "user", "content": antecedent}])
    assert named not in str(result.get("objective") or "")
    assert named not in str(result.get("request") or "")


# Revisión 2: una pregunta por el adentro sólo vale para un contenedor (comprimido o imagen de disco), y un turno
# anterior que nombró además un lugar propio no se repara: la base contaba ese lugar, que era lo pedido.
EXPLORER = "en Explorador de archivos"


@pytest.mark.parametrize(
    ("antecedent", "said", "restated", "expected"),
    [
        ("en el explorador abrí la carpeta Descargas y seleccioná foto.jpg", "¿cuántos archivos hay adentro?",
         f"{EXPLORER}, ¿cuántos archivos hay adentro?", f"{EXPLORER}, decime cuántos archivos hay adentro"),
        ("en el explorador borrá foto.jpg", "¿qué hay adentro?",
         f"{EXPLORER}, ¿qué hay adentro?", f"{EXPLORER}, decime qué hay adentro"),
        (r"en el explorador abrí C:\fotos y seleccioná viaje.zip", "¿cuántos archivos hay adentro?",
         f"{EXPLORER}, ¿cuántos archivos hay adentro?", f"{EXPLORER}, decime cuántos archivos hay adentro"),
    ],
)
def test_the_inside_of_a_file_that_holds_nothing_or_of_a_named_place_is_not_repaired(
    antecedent: str, said: str, restated: str, expected: str,
) -> None:
    result = _decided(said, ContextDecision(restated, "action", ("mission.computer.use",), ""),
                      history=[{"role": "user", "content": antecedent}])
    assert result["operation"] == "mission.computer.use"
    assert result["objective"] == expected


def test_the_inside_is_asked_only_of_the_container() -> None:
    # «comprimí informe.pdf en informe.zip»: el pdf no contiene nada; el zip sí.
    assert dialogue.objective_with_the_antecedent_object(
        "¿qué hay adentro?", "¿qué hay adentro?", "comprimí informe.pdf en informe.zip",
    ) == "¿qué hay adentro? (informe.zip)"
    # Contracaso: una imagen de disco es un contenedor; una pregunta por lo que dice vale para cualquier archivo.
    assert dialogue.objective_with_the_antecedent_object("qué tiene", "¿qué tiene?", "montá respaldo.iso") == (
        "qué tiene (respaldo.iso)")
    assert dialogue.objective_with_the_antecedent_object("qué dice", "¿qué dice?", "abrí informe.pdf") == (
        "qué dice (informe.pdf)")


# Revisión 2: el texto entre comillas que la persona mandó escribir no es el objeto del que pregunta después; si
# quedara en el objetivo, el motor recibiría la respuesta esperada sin haberla visto.
@pytest.mark.parametrize("said", ["¿qué dice?", "¿qué muestra?"])
def test_the_text_written_is_not_the_object_asked_of(said: str) -> None:
    restated = f"en Bloc de notas, {said}"
    result = _decided(said, ContextDecision(restated, "action", ("mission.computer.use",), ""),
                      history=[{"role": "user", "content": "en el bloc de notas escribí «hola mundo»"}])
    assert result["operation"] == "mission.computer.use"
    assert "hola mundo" not in str(result.get("objective") or "")
    assert result["objective"] == f"en Bloc de notas, decime {said.strip('¿?')}"


def test_a_quote_is_never_an_object_asked_of_later() -> None:
    # Revisión 3: lo citado es el texto del acto (escrito, pegado, mandado, buscado), sea cual sea el verbo.
    for antecedent in (
        "en el bloc de notas escribí «hola mundo»", 'type "hello world" in the notepad', "tipeá «Queen» en el buscador",
        "en el bloc de notas poné «hola mundo»", "pegá «hola mundo» en el bloc de notas",
        "en WhatsApp mandale «hola» a Ana", "en Discord mandá «jaja» en #general", "en Steam buscá «Hollow Knight»",
        "en Spotify buscá «Queen»", "buscá en google «clima ñuñoa»", "abrí «Informe final» y escribí «hola»",
        "buscá «setup.exe»",
    ):
        assert dialogue.files_acted_on(antecedent) == (), antecedent
    # Contracaso: un archivo nombrado fuera de la cita sigue siendo el objeto, aunque el turno también cite texto.
    assert dialogue.files_acted_on("en el bloc de notas escribí en informe.txt") == ("informe.txt",)
    assert dialogue.files_acted_on("pegá «hola» en notas.txt") == ("notas.txt",)
    assert dialogue.files_acted_on(SEVEN_ZIP_TURN) == ("prueba.zip",)


# Revisión 3: los vecinos de la revisión 2 con otro verbo que deja la cita en pantalla (poner, pegar, mandar, buscar),
# de punta a punta con un catálogo donde esas aplicaciones están instaladas. La cita no viaja en el objetivo.
REAL_APPS = (*SEVEN_ZIP_APPS, "WhatsApp", "Discord", "Steam", "Spotify", "Google Chrome")


def _decided_in(text: str, decision: ContextDecision, antecedent: str) -> dict:
    catalog = PlannerCatalog([_tool(name) for name in FOLLOW_OPERATIONS])
    history = [{"role": "user", "content": antecedent}, {"role": "user", "content": text}]
    return context_decision._context_decided_result(
        {"id": "r23-rev3", "text": text, "history": history},
        llm=_Decider(decision), planner_catalog=catalog, application_names=REAL_APPS,
    )


@pytest.mark.parametrize(
    ("antecedent", "said", "restated", "quoted"),
    [
        ("en el bloc de notas poné «hola mundo»", "¿qué dice?", "en Bloc de notas, ¿qué dice?", "hola mundo"),
        ("pegá «hola mundo» en el bloc de notas", "¿qué dice?", "en Bloc de notas, ¿qué dice?", "hola mundo"),
        ("en WhatsApp mandale «hola» a Ana", "¿qué dice?", "en WhatsApp, ¿qué dice?", "hola"),
        ("en Discord mandá «jaja» en #general", "¿qué dice?", "en Discord, ¿qué dice?", "jaja"),
        ("en Steam buscá «Hollow Knight»", "¿qué muestra?", "en Steam, ¿qué muestra?", "Hollow Knight"),
        ("en Spotify buscá «Queen»", "¿qué muestra?", "en Spotify, ¿qué muestra?", "Queen"),
        ("buscá en google «clima ñuñoa»", "¿qué dice?", "¿qué dice?", "clima ñuñoa"),
    ],
)
def test_the_text_a_turn_left_on_screen_is_not_the_object_asked_of(
    antecedent: str, said: str, restated: str, quoted: str,
) -> None:
    is_application = engine_handoff._names_an_application(REAL_APPS)
    assert dialogue.objective_with_the_antecedent_object(
        restated, said, antecedent, is_application=is_application,
    ) is None
    result = _decided_in(said, ContextDecision(restated, "action", ("mission.computer.use",), ""), antecedent)
    assert quoted not in str(result.get("objective") or "")
    assert quoted not in str(result.get("request") or "")


def test_a_file_named_beside_the_quoted_text_is_still_kept() -> None:
    # Contracaso: la pregunta por lo que dice conserva el archivo, nunca el texto que se le escribió.
    assert dialogue.objective_with_the_antecedent_object(
        "en Bloc de notas, qué dice", "¿qué dice?", "en el bloc de notas escribí «hola» en notas.txt",
        is_application=engine_handoff._names_an_application(REAL_APPS),
    ) == "en Bloc de notas, qué dice (notas.txt)"


def test_the_revision_2_lexicon_is_folded() -> None:
    from baxy_mind.semantic import lexicon
    from baxy_mind.semantic.normalize import fold

    assert lexicon.CONTAINER_EXTENSIONS <= lexicon.FILE_EXTENSIONS
    assert all(fold(word) == word for word in lexicon.CONTAINER_EXTENSIONS | lexicon.PLACE_NOUNS)
