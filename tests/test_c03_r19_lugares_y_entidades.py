"""Uso real v3 ronda 19, palanca «lugares y entidades» (tandas r17, %LOCALAPPDATA%/BAXY/cu-v3/tandas_r17/t1..t3):
places were resolved by their literal form, with nothing the person's words already said.

- t1-c05 #1 «va a llover mañana en valpo?» asked the geocoder for «valpo» (weather_place_not_found).
- t2-c13 T1 «¿qué tiempo va a hacer mañana en Valencia? ¿cojo paraguas?» read Valencia, Venezuela, the most populous,
  and did not say the country; the speech («cojo») marks Spain.

The providers' half (namesakes, the work page of a count, the YouTube choice) is tested in
Baxy.Providers.Windows.Tests (OpenMeteoWeatherAdapterTests, Ronda19LugaresYEntidadesTests).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from baxy_mind.weather_facts import _project_weather_read
from baxy_mind.semantic.arguments import _explicit_arguments_from_evidence
from baxy_mind.semantic.system import _weather_location, dialect_country, official_place_name
from baxy_mind import direct_arguments

ROOT = Path(__file__).resolve().parents[1]


def test_t1_c05_a_colloquial_town_is_asked_by_its_official_name() -> None:
    assert _weather_location("va a llover mañana en valpo?") == "Curicó"
    assert _explicit_arguments_from_evidence("weather.current", "va a llover mañana en valpo?") == {
        "location": "Curicó"
    }


def test_the_time_of_a_colloquial_town_is_asked_by_its_official_name() -> None:
    assert _explicit_arguments_from_evidence("system.time", "qué hora es en valpo") == {"place": "Curicó"}


def test_contracase_a_name_that_exists_as_said_is_not_rewritten() -> None:
    assert _weather_location("¿va a llover mañana en Valpovo?") == "Valpovo"
    assert official_place_name("Valpovo") == "Valpovo"
    assert official_place_name("Curicó") == "Curicó"
    assert official_place_name(None) is None


def test_t2_c13_the_speech_of_the_person_goes_with_the_place_as_a_hint() -> None:
    text = "¿qué tiempo va a hacer mañana en Valencia? ¿cojo paraguas?"
    assert dialect_country(text) == "ES"
    assert _explicit_arguments_from_evidence("weather.current", text) == {"location": "Valencia", "dialectCountry": "ES"}


def test_contracase_the_region_said_goes_with_the_town_and_the_hint_never_passes_over_it() -> None:
    text = "¿qué tiempo va a hacer mañana en Valencia, Carabobo? ¿cojo paraguas?"
    # The hint goes along; the adapter places the town in the region said before it reads the hint
    # (OpenMeteoWeatherAdapterTests: «Valencia, Carabobo» with ES reads Venezuela).
    assert _explicit_arguments_from_evidence("weather.current", text) == {
        "location": "Valencia, Carabobo",
        "dialectCountry": "ES",
    }
    # A time or a courtesy after the comma is not a region.
    assert _weather_location("clima en Madrid, mañana") == "Madrid"
    assert _weather_location("va a llover en Lima, por favor?") == "Lima"


def test_contracase_no_marked_speech_or_two_marks_give_no_hint() -> None:
    assert _explicit_arguments_from_evidence("weather.current", "¿qué tiempo va a hacer mañana en Valencia?") == {
        "location": "Valencia"
    }
    assert dialect_country("che, ¿cojo paraguas para Valencia?") is None
    # No place named: this PC's own place is read, and no hint is sent.
    assert _explicit_arguments_from_evidence("weather.current", "¿va a llover mañana? ¿cojo paraguas?") == {
        "location": None
    }


def test_the_hint_values_are_the_catalogs() -> None:
    source = (ROOT / "src/Baxy.Kernel/Operations/ProductCatalog.cs").read_text(encoding="utf-8")
    declared = re.search(r'String\("dialectCountry",[^\]]*values:\s*\[([^\]]*)\]', source)
    assert declared is not None
    values = sorted(re.findall(r'"([A-Z]{2})"', declared.group(1)))
    data = json.loads((ROOT / "src/baxy_mind/data/place_words.v1.json").read_text(encoding="utf-8"))
    assert values == sorted(data["dialectCountries"])


def test_the_narrator_gets_the_namesakes_with_the_place() -> None:
    seen = {
        "location": "Valencia",
        "region": "Carabobo",
        "country": "Venezuela",
        "namesakesElsewhere": True,
        "today": {"date": "2026-10-09", "sunrise": "06:30", "sunset": "18:40"},
        "tomorrow": {"date": "2026-10-10", "sunrise": "06:30", "sunset": "18:40"},
    }
    projected = _project_weather_read(seen, "¿a qué hora sale el sol mañana en Valencia?")
    assert projected["country"] == "Venezuela"
    assert projected["namesakesElsewhere"] is True


# Revisión r19: a vocative closing the sentence after the place is not a region.
WEATHER = {
    "type": "object",
    "properties": {
        "dialectCountry": {"type": ["string", "null"], "enum": ["AR", "CL", "CO", "ES", "MX", "VE", None]},
        "location": {"type": ["string", "null"], "x-maxUtf8Bytes": 128},
    },
    "required": [],
    "additionalProperties": False,
}


def test_contracase_the_name_of_the_assistant_after_the_place_is_a_vocative_not_a_region() -> None:
    assert _weather_location("¿Cómo está el clima en Curicó, Baxy?") == "Curicó"
    assert _weather_location("what's the weather in London, Jarvis?") == "London"
    assert _weather_location("¿va a llover en Rosario, Che?") == "Rosario"
    # The region said still goes with the town.
    assert _weather_location("¿Cómo está el clima en Valencia, Carabobo?") == "Valencia, Carabobo"


def test_contracase_a_square_said_with_a_vocative_keeps_the_town_the_conversation_fixed() -> None:
    history = [
        {"role": "user", "content": "¿Qué tiempo hace en Plaza Victoria, Curicó?"},
        {"role": "assistant", "content": "En Curicó hay 16 °C."},
        {"role": "user", "content": "¿Cómo está el clima en Plaza Sotomayor, Baxy?"},
    ]
    arguments = _explicit_arguments_from_evidence("weather.current", history[-1]["content"])
    assert arguments == {"location": "Plaza Sotomayor"}
    assert direct_arguments._with_conversation_place("weather.current", arguments, history, WEATHER) == {
        "location": "Plaza Sotomayor, Curicó"
    }


def test_contracase_the_speech_hint_survives_a_comma_part_that_is_not_a_known_vocative() -> None:
    # «Juan» cannot be told from a region by the words; the adapter keeps the town by its name when the part places
    # nothing, and the speech still chooses among namesakes.
    assert _explicit_arguments_from_evidence("weather.current", "¿qué tiempo hace en Valencia, Juan? ¿cojo paraguas?") == {
        "location": "Valencia, Juan",
        "dialectCountry": "ES",
    }
