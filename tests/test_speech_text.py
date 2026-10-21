"""What BAXY's voice reads (src/baxy_mind/speech_text.py): numbers with their gender, times, dates, money, units and
English names as a Latin-American says them."""
import pytest

from baxy_mind.speech_text import cardinal, spoken


@pytest.mark.parametrize(("n", "words"), [
    (0, "cero"), (16, "dieciséis"), (21, "veintiuno"), (31, "treinta y uno"), (100, "cien"), (101, "ciento uno"),
    (500, "quinientos"), (1000, "mil"), (1500, "mil quinientos"), (21000, "veintiún mil"),
    (1_000_001, "un millón uno"), (2_000_000, "dos millones"),
])
def test_cardinal(n: int, words: str) -> None:
    assert cardinal(n) == words


@pytest.mark.parametrize(("text", "said"), [
    ("Bajé el volumen al 30%.", "Bajé el volumen al treinta por ciento."),
    ("Tienes 21 archivos y 1 carpeta.", "Tienes veintiún archivos y una carpeta."),
    ("1.500 fotos y 200 ventanas.", "mil quinientas fotos y doscientas ventanas."),
    ("Hay 1 programa y 31 días.", "Hay un programa y treinta y un días."),
    ("A la 1:30 y a las 21:00.", "A la una y media y a las veintiuna en punto."),
    ("El 17/10/2026.", "El diecisiete de octubre de dos mil veintiséis."),
    ("Son $1.990 y pesa 2,5 kg.", "Son mil novecientos noventa pesos y pesa dos coma cinco kilos."),
    ("Está a 1 km y hace 17 °C.", "Está a un kilómetro y hace diecisiete grados."),
    ("Tu 1.ª reunión con el Sr. Pérez.", "Tu primera reunión con el señor Pérez."),
    ("Abrí Steam y Spotify en Disney+.", "Abrí Estím y Espótifai en Dísni plus."),
    ("Hola, soy BAXY.", "Hola, soy Báksi."),
    ("Déjame ver… listo — ya está.", "Déjame ver... listo, ya está."),
])
def test_spoken(text: str, said: str) -> None:
    assert spoken(text) == said


def test_words_that_contain_a_name_are_left_alone() -> None:
    assert spoken("Steamboat y apps") == "Steamboat y aps"
