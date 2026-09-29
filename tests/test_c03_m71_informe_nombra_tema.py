"""M71 (held-out v3j t14): a search report names the subject the conversation carried.

Pinned on the compose audit of the owner's frozen held-out replayed in the real app (run conv-v3j, trace t14). The
conversation: t13 «anoche vi Oppenheimer y me gustó bastante» → t14 «averiguá qué dijo la crítica». The decider
understood «Buscá qué dijo la crítica sobre Oppenheimer.» (the composer words the result against it), web.search sent
«qué dijo la crítica sobre Oppenheimer» and Google News returned five titles about the film. The first draft died on
words no page writes; the retry «Una crítica de un científico de Infobae se menciona y John Carpenter no se subió a los
elogios de la película.» was published. It never says which film (the owner's check: «no dice oppenheimer»), and it
makes the outlet the one who speaks (owner rule 2026-09-24: BAXY says what was said, not which page said it).
"""

from __future__ import annotations

from baxy_mind.llm import _payload_fact_defect, _search_report_leaves_out_subject
from baxy_mind.semantic.web import carried_subjects, names_subject
from test_c03_cpu_actor import Recorder

_T14_SAID = "averiguá qué dijo la crítica"
_T14_ASK = "Buscá qué dijo la crítica sobre Oppenheimer."
_T14_RESULTS = [
    ("Cuál es la mirada crítica de los científicos sobre la película Oppenheimer", "Infobae, Tue, 01 Aug 2023 07:00:00 GMT"),
    ("James Cameron critica a Christopher Nolan por cómo abordó Oppenheimer", "Indie Hoy, Wed, 02 Jul 2025 07:00:00 GMT"),
    ("Así le dijo Christopher Nolan a Cillian Murphy que protagonizaría Oppenheimer",
     "palomaynacho.com, Mon, 30 Jun 2025 07:00:00 GMT"),
    ("El nieto de Oppenheimer lamenta una escena en especial de la película: \"definitivamente la habría removido\" "
     "le dijo a Time", "Xataka México, Sun, 30 Jul 2023 07:00:00 GMT"),
    ("John Carpenter no se sube a los elogios de Oppenheimer: Qué dijo", "Indie Hoy, Tue, 07 May 2024 07:00:00 GMT"),
]
# The two drafts of the audit (first, rejected on unsourced words; retry, published).
_T14_FIRST = (
    "La crítica de los científicos señala que la película no refleja con precisión la mirada de los expertos sobre "
    "Oppenheimer."
)
_T14_PUBLISHED = (
    "Una crítica de un científico de Infobae se menciona y John Carpenter no se subió a los elogios de la película."
)
_T14_NAMED = "John Carpenter no se subió a los elogios de Oppenheimer."


def _payload(query: str, results: list[tuple[str, str]]) -> dict:
    return {
        "operation": "web.search",
        "seen": {
            "query": query,
            "count": len(results),
            "results": [
                {"title": title, "url": "https://news.google.com/rss/articles/CBMi", "snippet": snippet}
                for title, snippet in results
            ],
            "authority": "google_news_rss_search",
        },
    }


def _situation(payload: dict) -> dict:
    return {"kind": "operation", "operation": "web.search", "polarity": "success", "verified": True,
            "succeeded": True, "observed": {"version": 1, **payload["seen"]}}


_T14 = _payload("qué dijo la crítica sobre Oppenheimer", _T14_RESULTS)


# The reading (semantic.web): the subject is a name of the understood request or the query the message does not write.

def test_t14_the_film_came_from_the_conversation() -> None:
    assert carried_subjects(_T14_ASK, "qué dijo la crítica sobre Oppenheimer", _T14_SAID) == ("Oppenheimer",)


def test_a_name_the_person_wrote_is_not_carried() -> None:
    assert carried_subjects(_T14_ASK, "qué dijo la crítica sobre Oppenheimer", "averiguá qué dijo la crítica de "
                            "oppenheimer") == ()
    assert carried_subjects("Buscá en Google qué dijo la crítica.", "", "buscá en google qué dijo la crítica") == ()


def test_a_title_is_one_name_and_part_of_it_names_it() -> None:
    assert carried_subjects(
        "¿Qué dijo la crítica de The Last of Us?", "qué dijo la crítica de The Last of Us", "¿y la crítica?"
    ) == ("The Last of Us",)
    assert names_subject("La crítica dice que Last of Us es la mejor serie del año.", "The Last of Us")
    assert names_subject("OPPENHEIMER", "Oppenheimer")
    assert not names_subject("La crítica elogió la película.", "Oppenheimer")


# The veto.

def test_t14_the_published_report_that_never_names_the_film_is_rejected() -> None:
    assert _search_report_leaves_out_subject(_T14_PUBLISHED, _T14, _T14_ASK, _T14_SAID) == ["Oppenheimer"]
    assert _payload_fact_defect(_T14_PUBLISHED, _T14, _T14_ASK, said=_T14_SAID) == "search_report_leaves_out_subject"
    # Without the person's own message nothing is required (the M70 pins word against the understood request).
    assert _payload_fact_defect(_T14_PUBLISHED, _T14, _T14_ASK) == ""


def test_t14_a_report_that_names_the_film_passes() -> None:
    for named in (_T14_NAMED, "James Cameron criticó a Christopher Nolan por cómo abordó Oppenheimer.",
                  "John Carpenter no se subió a los elogios de OPPENHEIMER."):
        assert _search_report_leaves_out_subject(named, _T14, _T14_ASK, _T14_SAID) == []
        assert _payload_fact_defect(named, _T14, _T14_ASK, said=_T14_SAID) == ""


def test_when_the_person_named_it_the_report_need_not_repeat_it() -> None:
    said = "averiguá qué dijo la crítica de Oppenheimer"
    assert _search_report_leaves_out_subject(_T14_PUBLISHED, _T14, _T14_ASK, said) == []
    assert _payload_fact_defect(_T14_PUBLISHED, _T14, _T14_ASK, said=said) == ""


def test_the_not_found_is_not_held_to_the_subject() -> None:
    # The last resort names what was looked up when it can (M64/M70); its bare form must stay publishable.
    for not_found in ("No lo encontré.", "No encontré qué dijo la crítica sobre Oppenheimer."):
        assert _search_report_leaves_out_subject(not_found, _T14, _T14_ASK, _T14_SAID) == []


def test_a_subject_no_result_writes_is_not_required() -> None:
    # Naming a name no page carries is what the off-subject hint tells the retry to leave out.
    other = _payload("qué dijo la crítica sobre Oppenheimer en Cannes", _T14_RESULTS)
    ask = "Buscá qué dijo la crítica sobre Oppenheimer en Cannes."
    assert carried_subjects(ask, "", _T14_SAID) == ("Oppenheimer", "Cannes")
    assert _search_report_leaves_out_subject(_T14_NAMED, other, ask, _T14_SAID) == []
    assert _search_report_leaves_out_subject(_T14_PUBLISHED, other, ask, _T14_SAID) == ["Oppenheimer"]


def test_english_the_carried_subject_is_named() -> None:
    results = [
        ("John Carpenter doesn't join the praise for Oppenheimer", "IndieWire, Tue, 07 May 2024 07:00:00 GMT"),
        ("James Cameron criticizes Christopher Nolan over how Oppenheimer handled Hiroshima",
         "Variety, Wed, 02 Jul 2025 07:00:00 GMT"),
    ]
    payload = _payload("what the critics said about Oppenheimer", results)
    ask = "Look up what the critics said about Oppenheimer."
    said = "find out what the critics said"
    bare = "John Carpenter doesn't join the praise for the film."
    assert _payload_fact_defect(bare, payload, ask, said=said) == "search_report_leaves_out_subject"
    assert _payload_fact_defect("John Carpenter didn't join the praise for Oppenheimer.", payload, ask, said=said) == ""
    assert _payload_fact_defect(bare, payload, ask, said="find out what the critics said about Oppenheimer") == ""


# The turn end to end, with the drafts the model wrote.

def test_t14_the_retry_is_told_to_name_the_film_and_not_the_outlet() -> None:
    client = Recorder([_T14_FIRST, _T14_PUBLISHED, _T14_NAMED])
    assert client.compose_user_message(_T14_ASK, "status", {"situation": _situation(_T14)}, said=_T14_SAID) == (
        _T14_NAMED
    )
    assert len(client.payloads) == 3
    third_system = client.payloads[2]["messages"][0]["content"]
    assert "Nombrá «Oppenheimer» en tu respuesta" in third_system
    assert "nunca un diario ni un sitio" in third_system


def test_t14_without_a_draft_that_names_it_ends_in_the_named_not_found() -> None:
    client = Recorder([_T14_FIRST, _T14_PUBLISHED, _T14_PUBLISHED])
    assert client.compose_user_message(_T14_ASK, "status", {"situation": _situation(_T14)}, said=_T14_SAID) == (
        "No encontré qué dijo la crítica sobre Oppenheimer."
    )


def test_t14_the_person_who_named_it_gets_the_report_as_written() -> None:
    client = Recorder([_T14_FIRST, _T14_PUBLISHED])
    said = "averiguá qué dijo la crítica de Oppenheimer"
    assert client.compose_user_message(_T14_ASK, "status", {"situation": _situation(_T14)}, said=said) == (
        _T14_PUBLISHED
    )
