"""What BAXY's voice reads (src/baxy_mind/speech_text.py): numbers with their gender, times, dates, money, units and
English names as a Latin-American says them; and, with the interface in English, the same as an English speaker says
them."""
import pytest

from baxy_mind.speech_text import Utterance, cardinal, cardinal_en, language, ordinal_en, spoken


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
    # A unit of several words counts its first (w8): it was «una kilómetros por hora», «veintiuna kilómetros».
    ("Va a 1 km/h y el viento a 21 km/h.", "Va a un kilómetro por hora y el viento a veintiún kilómetros por hora."),
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


# --- English (Steam release: the interface in English, voice.speak's «lang» «en») ------------------------------------

@pytest.mark.parametrize(("n", "words"), [
    (0, "zero"), (75, "seventy five"), (105, "one hundred five"), (1000, "one thousand"), (1500, "one thousand five hundred"),
    (2026, "two thousand twenty six"), (21000, "twenty one thousand"), (1_000_001, "one million one"),
    (2_500_000_000, "two billion five hundred million"), (-7, "minus seven"),
])
def test_cardinal_en(n: int, words: str) -> None:
    assert cardinal_en(n) == words


@pytest.mark.parametrize(("n", "words"), [
    (1, "first"), (2, "second"), (3, "third"), (4, "fourth"), (5, "fifth"), (8, "eighth"), (9, "ninth"), (12, "twelfth"),
    (20, "twentieth"), (21, "twenty first"), (100, "one hundredth"),
])
def test_ordinal_en(n: int, words: str) -> None:
    assert ordinal_en(n) == words


@pytest.mark.parametrize(("text", "said"), [
    # numbers: US thousands and decimals, any size, negatives, letters written against them
    ("You have 21 files and 1 folder.", "You have twenty one files and one folder."),
    ("It is 1,500 and 1,250,000.", "It is one thousand five hundred and one million two hundred fifty thousand."),
    ("Use 1.5 or 0.25 of it.", "Use one point five or zero point two five of it."),
    ("It went down to -7.", "It went down to minus seven."),
    ("In 4K and 1080p.", "In four K and one thousand eighty p."),
    # percentages
    ("I set the volume to 30%.", "I set the volume to thirty percent."),
    ("The CPU is at 0.69 %.", "The CPU is at zero point six nine percent."),
    # money
    ("It costs $1,990.", "It costs one thousand nine hundred ninety dollars."),
    ("It is $1, US$5, USD 20 or 15 USD.", "It is one dollar, five dollars, twenty dollars or fifteen dollars."),
    ("Pay $4.99 or $0.50.", "Pay four dollars and ninety nine cents or fifty cents."),
    # times
    ("At 10:30 and at 10:00.", "At ten thirty and at ten o'clock."),
    ("At 10:05 a.m. and 5 pm.", "At ten oh five A M and five P M."),
    ("It ends at 21:00 or 00:15.", "It ends at nine P M or twelve fifteen A M."),
    ("Meet at 10 a.m. tomorrow.", "Meet at ten A M tomorrow."),
    ("It ends at 9 p.m. Then rest.", "It ends at nine P M. Then rest."),  # the sentence still ends there
    # dates: month names; a slash date only when its order is certain
    ("On November 4, 2026.", "On November fourth, twenty twenty six."),
    ("On 4 November 2026 and May 2026.", "On the fourth of November twenty twenty six and May twenty twenty six."),
    ("Due 2026-11-04.", "Due November fourth, twenty twenty six."),
    ("On 10/17/2026 or 17/10/2026.", "On October seventeenth, twenty twenty six or October seventeenth, twenty twenty six."),
    ("On 11/04/2026.", "On eleven slash four slash twenty twenty six."),
    ("Open 24/7.", "Open twenty four/seven."),
    # review 2026-11-04: without a year a slash pair is not a date (a score, a fraction)
    ("All 3/3. Then 1/2 of it.", "All three/three. Then one/two of it."),
    # a bare 1100-2099 is a year after a word that places it in time or closing a clause; elsewhere a quantity
    ("In 1984 and 1905.", "In nineteen eighty four and nineteen oh five."),
    ("Since 1999, by 2030 and in 2005 we grew.", "Since nineteen ninety nine, by twenty thirty and in two thousand five we "
                                                 "grew."),
    ("It was 2026. It has 2026 files and 2,026 rows.", "It was twenty twenty six. It has two thousand twenty six files and "
                                                       "two thousand twenty six rows."),
    # dotted groups, digit by digit
    ("Ping 192.168.1.20 or 1.2.3.", "Ping one nine two dot one six eight dot one dot two zero or one dot two dot three."),
    # units
    ("It is 1 km away at 21 km/h.", "It is one kilometer away at twenty one kilometers per hour."),
    ("It weighs 2.5 kg and it is 17 °C.", "It weighs two point five kilograms and it is seventeen degrees Celsius."),
    ("It is -3 °F, 1 °C and 60 mph.", "It is minus three degrees Fahrenheit, one degree Celsius and sixty miles per hour."),
    ("16 GB, 512 MB, 2 TB at 3.2 GHz.", "sixteen gigabytes, five hundred twelve megabytes, two terabytes at three point two "
                                        "gigahertz."),
    ("Wait 2 h 30 min and 1 h.", "Wait two hours thirty minutes and one hour."),
    # ordinals, abbreviations, «@»
    ("Your 1st, 2nd, 3rd and 21st try.", "Your first, second, third and twenty first try."),
    ("Mr. Smith, Mrs. Lee, Ms. Kim and Dr. Jones.", "Mister Smith, Missus Lee, Miz Kim and Doctor Jones."),
    ("Apples, e.g. green ones, vs. pears.", "Apples, for example green ones, versus pears."),
    ("Room No. 5.", "Room number five."),
    ("Write to ana@example.com.", "Write to ana at example.com."),
    ("Let me see… done — all set.", "Let me see... done, all set."),
    # no Spanish respellings
    ("Opened Steam and Spotify, BAXY.", "Opened Steam and Spotify, BAXY."),
    # «etc.» closing a sentence keeps the sentence's end; mid-sentence it does not
    ("Apples, pears, etc. Then rest, etc. and more.", "Apples, pears, et cetera. Then rest, et cetera and more."),
    ("Fruit, etc.", "Fruit, et cetera."),
    # «AM»/«PM» only right after a clock time, written as one
    ("Is it 3 Am I? PM Smith at 5 PM, 7 A.M. sharp.", "Is it three Am I? PM Smith at five P M, seven A M sharp."),
])
def test_spoken_en(text: str, said: str) -> None:
    assert spoken(text, "en") == said
    assert spoken(Utterance(text, "en")) == said  # an Utterance says itself in its own language


@pytest.mark.parametrize(("tag", "lang"), [
    ("en", "en"), ("EN", "en"), ("en-US", "en"), ("en_GB", "en"), ("es", "es"), ("es-CL", "es"), (None, "es"), ("", "es"),
    ("fr", "es"), (5, "es"),
])
def test_an_unknown_or_missing_language_is_spanish(tag: object, lang: str) -> None:
    assert language(tag) == lang
    assert Utterance("Hola.", tag).lang == lang


def test_spanish_stays_as_it_was_for_a_plain_text_and_a_spanish_utterance() -> None:
    text = "Son $1.990 a las 10:30, Sr. Pérez, en Steam."
    assert spoken(text) == spoken(text, "es") == spoken(Utterance(text, "es")) == spoken(Utterance(text, None))
    assert spoken(text) == "Son mil novecientos noventa pesos a las diez y media, señor Pérez, en Estím."
