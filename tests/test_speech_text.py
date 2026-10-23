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
    # a word after the number that is not what it counts leaves the number in its own form (it said «el un de
    # noviembre», «del una a diez», «doscientas para ti»)
    ("El 1 de noviembre, del 1 a 10.", "El uno de noviembre, del uno a diez."),
    ("Son 21 en total y 200 para ti; 1 o 2.", "Son veintiuno en total y doscientos para ti; uno o dos."),
    ("La 1 y la 2, 1 más 1.", "La uno y la dos, uno más uno."),
    ("Usa el 0,69 % de la CPU.", "Usa el cero coma sesenta y nueve por ciento de la CPU."),
    ("Faltan 2 h 30 min y 1 h; a las 10:30 h.", "Faltan dos horas treinta minutos y una hora; a las diez y media."),
    ("En 4K y 1080p.", "En cuatro K y mil ochenta p."),
])
def test_spoken(text: str, said: str) -> None:
    assert spoken(text) == said


def test_words_that_contain_a_name_are_left_alone() -> None:
    assert spoken("Steamboat y apps") == "Steamboat y aps"
