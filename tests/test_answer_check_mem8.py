"""MEM8 (MEM7, Esencial with BAXY's memory on, 4 records and no tool that reads them): «No tengo nada guardado de ti»
19 of 80, and no rule read it (memory_off_empty only with the switch off; unread_memory's «no lo tengo guardado» only
with a reading tool shown). On and unread here, the store keeps what it kept: the same rule, with that state's fact; the
model writes its answer again, words only (nothing is cut out of it)."""
from baxy_mind.answer_check import MEMORY_OFF_FACT, MEMORY_UNREAD_FACT, check

ASKED = "¿Qué tienes guardado de mí?"


def test_with_the_memory_on_and_unread_saying_nothing_is_kept_is_a_finding() -> None:
    found = [f for f in check("No tengo nada guardado de ti.", ASKED, [], [], memory_unread=True)
             if f["rule"] == "memory_off_empty"]
    assert [f["fact"] for f in found] == [MEMORY_UNREAD_FACT], found
    assert "encendida" in found[0]["fact"], found


def test_the_honest_answer_is_not_and_the_switch_off_keeps_its_fact() -> None:
    assert not [f for f in check("Tengo recuerdos guardados, pero en este perfil no puedo leerlos.", ASKED, [], [],
                                 memory_unread=True) if f["rule"] == "memory_off_empty"]
    off = [f["fact"] for f in check("No tengo nada guardado de ti.", ASKED, [], [], memory_off=True)
           if f["rule"] == "memory_off_empty"]
    assert off == [MEMORY_OFF_FACT]
    assert not [f for f in check("No tengo nada guardado de ti.", ASKED, [], []) if f["rule"] == "memory_off_empty"]


def test_d4b_with_none_kept_saying_nothing_is_kept_is_true() -> None:
    """D4b (revisión ciega #6): with 0 facts kept (the App's count at the start), «no tengo nada guardado» is so."""
    assert not [f for f in check("No tengo nada guardado de ti.", ASKED, [], [], memory_unread=True, memory_records=0)
                if f["rule"] == "memory_off_empty"]


def test_d4b_with_a_count_the_fact_says_it_and_never_maybe() -> None:
    from baxy_mind.answer_check import MEMORY_KEPT_UNREAD_FACT
    found = [f["fact"] for f in check("No tengo nada guardado de ti.", ASKED, [], [], memory_unread=True,
                                      memory_records=4) if f["rule"] == "memory_off_empty"]
    assert found == [MEMORY_KEPT_UNREAD_FACT.format(n=4)], found
    assert "4 datos" in found[0] and "puede tener" not in found[0], found


def test_d4b_the_mind_keeps_the_count_out_of_the_prompt(tmp_path) -> None:
    """The count is the check's: the system text and the tools are byte for byte the ones without it. MEM8C (REV20 M-1):
    it comes with each turn (turn.decide), not in catalog.configure, which no longer reads it."""
    from test_mente_ese7 import HELD_ENABLE, HELD_SAVE, REST, SETTINGS
    from test_mind_final import _mind
    message = {"capabilities": [SETTINGS], "withheld": [HELD_SAVE, HELD_ENABLE, *REST], "memoryOff": False}
    plain, _ = _mind(tmp_path / "a", [])
    plain.configure(dict(message))
    counted, _ = _mind(tmp_path / "b", [])
    counted.configure({**message, "memoryRecords": 4})
    assert counted.memory_records is None and plain.memory_records is None
    counted.memory_records = 4
    assert counted._system() == plain._system() and counted.tools == plain.tools


def test_final_after_a_save_completed_the_start_count_is_not_used() -> None:
    """Revisión ciega 3 #3: 0 at the start, then «Recuerda que…» saved with the «sí»: «no tengo nada» is a finding again,
    with the prudent fact (the count is not known now)."""
    from baxy_mind.answer_check import MEMORY_UNREAD_FACT
    saved = [("memory.save", True, False)]
    found = [f["fact"] for f in check("No tengo nada guardado de ti.", ASKED, [], saved, memory_unread=True,
                                      memory_records=0) if f["rule"] == "memory_off_empty"]
    assert found == [MEMORY_UNREAD_FACT], found
    # A read changes nothing kept: the 0 stands.
    read = [("memory.status", True, True)]
    assert not [f for f in check("No tengo nada guardado de ti.", ASKED, [], read, memory_unread=True,
                                 memory_records=0) if f["rule"] == "memory_off_empty"]
