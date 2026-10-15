"""M54 (2026-09-28): what BAXY says about a verified reading states only what the reading says.

The payloads and drafts are the real ones of the official-window run v3b-final
(%LOCALAPPDATA%/BAXY/comprension-2026-09-25/window/v3b-final/compose-audit.jsonl, traces t66, t182, t102, t118, t190,
t124, t107, t125, t150, t183; the questions of t133 and t159 come from RUN.jsonl), the development set reviewed by
hand, and of the DEV-D iteration run v3b-devD (D-s004, D-s005, D-s007, D-s042): a comparison, an absence or a place
the reading did not carry was published, a figure the reading carried was denied, and the wording spoke jargon.
"""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

from baxy_mind.turn_recovery import _recover_failed_turn, _recovery_question_is_valid
from baxy_mind.deterministic_finals import _deterministic_final
from baxy_mind.payload_fact_checks import _payload_fact_defect
from baxy_mind.search_report import _search_report_says_unseen_name
from baxy_mind.compose_situation import _situation_from_facts
from baxy_mind.visible_defect import compose_visible_defect
from baxy_mind.argument_payload import validate_missing_argument_clarification
from baxy_mind.unsupported_answers import _unsupported_answer_contract_failure
from baxy_mind.reply_language_checks import limit_breaks_the_asked_verb
from baxy_mind.search_report import _search_report_absence_claim
from baxy_mind.compose_situation import _cause_in_prose
from baxy_mind.argument_payload import _question_without_time_format
from baxy_mind.weather_facts import _weather_unsupported_comparison
from baxy_mind import turn_audit


# v3b-final t66
S066_PAYLOAD = {'seen': {'location': 'San Juan',
          'country': '',
          'locatedBy': 'named_place_geocoded',
          'observedAtLocal': '2026-09-28T18:45',
          'timezone': 'America/Puerto_Rico',
          'temperatureC': 29.3,
          'apparentC': 32.4,
          'humidityPercent': 72,
          'windKmh': 18.7,
          'precipitationMm': 0,
          'uvIndex': 0,
          'dewPointC': 23.7,
          'weatherCode': 3,
          'condition': 'nublado',
          'today': {'date': '2026-09-28',
                    'weekday': 'lunes',
                    'maxC': 30.5,
                    'minC': 25.8,
                    'rainProbabilityPercent': 34,
                    'uvIndexMax': 7.8,
                    'sunrise': '06:14',
                    'sunset': '18:15'},
          'tomorrow': {'date': '2026-09-29',
                       'weekday': 'martes',
                       'maxC': 29.3,
                       'minC': 26.2,
                       'rainProbabilityPercent': 84,
                       'uvIndexMax': 8.4,
                       'condition': 'llovizna',
                       'sunrise': '06:14',
                       'sunset': '18:14'},
          'airQuality': {'usAqi': 22, 'category': 'buena', 'pm25': 5.3, 'pm10': 8.4},
          'authority': 'open_meteo_forecast_v1'},
 'operation': 'weather.current'}


# v3b-final t182
W11_T2_PAYLOAD = {'seen': {'query': 'taquerías cerca que tengan servicio a domicilio',
          'count': 5,
          'results': [{'title': 'Taquerías con servicio a domicilio cerca de mi ubicación',
                       'url': 'https://buscarcercademi.net/taquerias-con-servicio-a-domicilio-cerca-de-mi/',
                       'snippet': 'Dado ...'},
                      {'title': 'Tacos cerca de mi, taco y taqueria de diferentes guisados',
                       'url': 'https://buscatacos.com/',
                       'snippet': 'Excelente manera de encontrar taquerías abiertas cerca de mi ubicación, me '
                                  'gusta comer tacos a todas horas y esta plataforma realmente funciona, también '
                                  'me gustan las promociones que ofrece.'},
                      {'title': 'Tacos cerca de mi. Taco y taqueria de diferentes guisados. Encuentra tacos',
                       'url': 'https://tacoscerca.com/public/',
                       'snippet': 'Tacos, taquerías cerca de mí y mucho más En buscatacos.com, te ofrecemos la '
                                  'oportunidad de conectar con amantes de los tacos que buscan la mejor '
                                  'experiencia en taquerías de tu área.'},
                      {'title': 'Ordenar en el mejor Taco cerca de mí en 2026 - DoorDash',
                       'url': 'https://www.doordash.com/es/near-me/category/taco/',
                       'snippet': 'Haz tu orden en Taco cerca de ti y disfruta de tus platos favoritos en tu '
                                  'puerta rápidamente. Explora las opciones de menú mejor calificadas, disponibles '
                                  'para entrega a domicilio o para retirar. Cómodo, delicioso y a solo unos clics '
                                  'de distancia: ¡haz tu orden ahora y satisface tus antojos hoy mismo!'},
                      {'title': 'Restaurantes cerca de mí - Ordenar comida a domicilio - DoorDash',
                       'url': 'https://www.doordash.com/es-US/restaurants-near-me',
                       'snippet': 'DashPass es un servicio de suscripción que provee entregas gratis (sin tarifas '
                                  'de entrega) para las órdenes de los restaurantes elegibles. Es posible que se '
                                  'apliquen tarifas de servicio y subtotal mínimo.'}],
          'authority': 'duckduckgo_lite_https'},
 'operation': 'web.search'}


# v3b-final t102
P01_T2_PAYLOAD = {'seen': {'query': 'un aparcamiento para motocicletas en el centro de la ciudad Curico',
          'near': 'Curico',
          'count': 5,
          'results': [{'title': 'parking',
                       'url': 'https://www.openstreetmap.org/way/743712946',
                       'snippet': 'East Lincolnway, Curico, Porter County, Indiana, 46383, Estados Unidos de '
                                  'América'},
                      {'title': 'parking',
                       'url': 'https://www.openstreetmap.org/way/1091938114',
                       'snippet': 'McCord Road, Curico, Porter County, Indiana, 46383, Estados Unidos de '
                                  'América'},
                      {'title': 'parking',
                       'url': 'https://www.openstreetmap.org/way/1348419951',
                       'snippet': 'East Chicago Street, Curico, Porter County, Indiana, 46383, Estados Unidos '
                                  'de América'},
                      {'title': 'parking',
                       'url': 'https://www.openstreetmap.org/way/1098424784',
                       'snippet': 'Carrsbrooke Drive, Curico, Porter County, Indiana, 46483, Estados Unidos de '
                                  'América'},
                      {'title': 'parking',
                       'url': 'https://www.openstreetmap.org/way/1348640036',
                       'snippet': 'Legend Drive, Curico, Porter County, Indiana, 46383, Estados Unidos de '
                                  'América'}],
          'authority': 'openstreetmap_nominatim'},
 'operation': 'web.search'}


# v3b-final t118
P06_T3_PAYLOAD = {'seen': {'query': 'aparcamiento en la calle Génova en Madrid',
          'count': 5,
          'results': [{'title': 'parking',
                       'url': 'https://www.openstreetmap.org/way/1550539478',
                       'snippet': 'Calle de Campoamor, Chueca, Justicia, Centro, Madrid, Comunidad de Madrid, '
                                  '28004, España'},
                      {'title': 'parking',
                       'url': 'https://www.openstreetmap.org/way/1547417618',
                       'snippet': 'Calle del Conde de Xiquena, Chueca, Justicia, Centro, Madrid, Comunidad de '
                                  'Madrid, 28004, España'},
                      {'title': 'Parking Escuelas Pías de San Antón',
                       'url': 'https://www.openstreetmap.org/node/13167699221',
                       'snippet': 'Parking Escuelas Pías de San Antón, Calle de Santa Brígida, Chueca, Justicia, '
                                  'Centro, Madrid, Comunidad de Madrid, 28004, España'},
                      {'title': 'parking',
                       'url': 'https://www.openstreetmap.org/way/1395156681',
                       'snippet': 'Calle de Larra, Chueca, Justicia, Centro, Madrid, Comunidad de Madrid, 28004, '
                                  'España'},
                      {'title': 'Parking Garaje AML',
                       'url': 'https://www.openstreetmap.org/node/1285573358',
                       'snippet': 'Parking Garaje AML, 8, Calle de Hernán Cortés, Chueca, Justicia, Centro, '
                                  'Madrid, Comunidad de Madrid, 28004, España'}],
          'authority': 'openstreetmap_nominatim'},
 'operation': 'web.search'}


# v3b-final t190
W13_T2_PAYLOAD = {'seen': {'query': '¿Cuánto me sale cargar 40 litros de nafta Super en Córdoba?',
          'count': 4,
          'results': [{'title': 'Cuánto cuesta llenar el tanque de nafta de un auto en septiembre 2026',
                       'url': 'https://www.lanacion.com.ar/autos/cuanto-cuesta-llenar-el-tanque-de-nafta-de-un-auto-en-septiembre-2026-nid18092026/',
                       'snippet': 'A partir de esos precios, llenar un tanque de 40 litros con nafta súper demanda '
                                  '$82.360, mientras que completar uno de 50 litros requiere $102.950. Si el '
                                  'vehículo utiliza premium, los mismos ...'},
                      {'title': 'Cuánto cuesta llenar el tanque de nafta de un auto en agosto 2026',
                       'url': 'https://www.estaciones.com.ar/2026/08/26/cuanto-cuesta-llenar-el-tanque-de-nafta-de-un-auto-en-agosto-2026/',
                       'snippet': 'Para establecer referencias concretas pueden tomarse tres vehículos de amplia '
                                  'presencia en el mercado argentino, como el Fiat Cronos, el Volkswagen Gol Trend '
                                  'y la Toyota Hilux. El Fiat Cronos tiene un tanque con capacidad para 48 litros '
                                  '. Por lo tanto, llenarlo desde cero con nafta súper cuesta $98.160.'},
                      {'title': 'Cuánto sale llenar el tanque de nafta de un auto en septiembre 2026',
                       'url': 'https://www.eldestapeweb.com/economia/cuanto-sale-llenar-tanque-nafta-auto-septiembre-2026-2026922145240',
                       'snippet': 'Cuánto sale llenar el tanque de nafta en septiembre 2026 Para un auto con un '
                                  'tanque de 40 litros , una carga completa de nafta súper demanda $82.360. Si la '
                                  'capacidad aumenta a 50 litros , el gasto asciende a $102.950. Con nafta '
                                  'premium, los valores son más elevados: llenar un depósito de 40 litros requiere '
                                  '$90.360 y completar uno de 50 litros cuesta $112.950. Los valores quedan de la '
                                  '...'},
                      {'title': 'Calculadora de combustibles: conocé cuánto cuesta llenar el tanque de ...',
                       'url': 'https://www.infobae.com/autos/2023/11/15/calculadora-de-combustibles-conoce-cuanto-cuesta-llenar-el-tanque-de-cada-auto/',
                       'snippet': 'Estos precios de referencia son entonces los siguientes para 1 litro de los '
                                  'distintos combustibles que hay en el mercado: Nafta Súper $272, Infinia $349, '
                                  'diésel 500 $292 e Infinia diésel $398 ...'}],
          'authority': 'duckduckgo_lite_https'},
 'operation': 'web.search'}


# v3b-final t124
P08_T2_PAYLOAD = {'seen': {'query': 'stage shows in Cape Town',
          'count': 1,
          'results': [{'title': 'Cape Town Stadium',
                       'url': 'https://en.wikipedia.org/wiki/Cape_Town_Stadium',
                       'snippet': 'The Cape Town Stadium (Afrikaans: Kaapstad-stadion; Xhosa: Inkundla yezemidlalo '
                                  'yaseKapa; known since 2021 as the DHL Stadium for sponsorship reasons) is a '
                                  'football (soccer) and rugby union stadium in Cape Town, South Africa, that was '
                                  "built as part of the country's hosting of the 2010 FIFA World Cup. During the "
                                  'planning stage, it was known as the Green Point Stadium, which was the name of '
                                  'the older stadium on an adjacent site, and this name was also used frequently '
                                  'during World Cup media coverage. It is the home ground of WP Rugby, the '
                                  'Stormers XXIII and the Stormers (since 2021), and was used by Cape Town City '
                                  'from 2016 when they played in the Premiership.'}],
          'authority': 'wikipedia_en_api'},
 'operation': 'web.search'}



def test_s066_a_colder_tomorrow_needs_both_days_figures_to_show_it():
    draft = "En San Juan hace 29.3 °C y está nublado. Mañana será más frío, con 29.3 °C y llovizna."
    user = "¿Qué tiempo hará en San Juan?"
    assert _payload_fact_defect(draft, S066_PAYLOAD, user) == "weather_unsupported_comparison"
    assert _payload_fact_defect(
        "En San Juan hace 29,3 °C y está nublado. Mañana, 29,3 °C con llovizna.", S066_PAYLOAD, user
    ) == ""
    # Tomorrow's rain chance (84 %) is above today's (34 %): «más lluvia» is shown.
    assert not _weather_unsupported_comparison("Mañana habrá más lluvia.", S066_PAYLOAD["seen"])
    assert _weather_unsupported_comparison("Mañana habrá menos lluvia.", S066_PAYLOAD["seen"])
    # Nothing of yesterday is read.
    assert _weather_unsupported_comparison("Hoy hace más calor que ayer.", S066_PAYLOAD["seen"])
    # «por la mañana» is a time of today, not tomorrow: nothing is compared across days.
    assert not _weather_unsupported_comparison("Por la mañana estuvo más fresco.", S066_PAYLOAD["seen"])
    cooler = copy.deepcopy(S066_PAYLOAD["seen"])
    cooler["tomorrow"].update(maxC=27.0, minC=24.9)
    assert not _weather_unsupported_comparison("Mañana será más fresco.", cooler)


def test_w11_t2_directories_do_not_say_there_are_no_taquerias():
    user = "Busca taquerías cerca que tengan servicio a domicilio."
    clipped = "No hay taquerías específicas con servicio a domicilio."
    assert _search_report_absence_claim(clipped, W11_T2_PAYLOAD)
    assert _payload_fact_defect(clipped, W11_T2_PAYLOAD, user) == "search_report_absence_claim"
    assert _payload_fact_defect("No lo encontré.", W11_T2_PAYLOAD, user) == ""
    # A page that states the absence grounds it.
    stated = copy.deepcopy(W11_T2_PAYLOAD)
    stated["seen"]["results"][0]["snippet"] = "La taquería del barrio no tiene servicio a domicilio los domingos."
    assert not _search_report_absence_claim("La taquería del barrio no tiene servicio a domicilio.", stated)


def test_p01_t2_and_p06_t3_places_read_from_openstreetmap_are_not_denied():
    genova = "Busca aparcamiento en la calle Génova en Madrid."
    assert _payload_fact_defect(
        "No encontré aparcamiento en la calle Génova en Madrid.", P06_T3_PAYLOAD, genova
    ) == "search_places_denied"
    assert _payload_fact_defect(
        "Hay aparcamientos en la calle de Campoamor y en el Parking Garaje AML, en Chueca.", P06_T3_PAYLOAD, genova
    ) == ""
    centro = "Busca un aparcamiento para motocicletas en el centro de la ciudad."
    assert _payload_fact_defect(
        "No hay aparcamiento para motocicletas en el centro de la ciudad Curico.", P01_T2_PAYLOAD, centro
    ) == "search_places_denied"
    situation = {
        "kind": "operation", "operation": "web.search", "polarity": "success", "verified": True, "succeeded": True,
        "observed": P06_T3_PAYLOAD["seen"],
    }
    told = _deterministic_final(situation, P06_T3_PAYLOAD, genova, "es")
    assert told == (
        "Encontré: Calle de Campoamor, Calle del Conde de Xiquena y "
        "Parking Escuelas Pías de San Antón (Calle de Santa Brígida)."
    )
    assert _payload_fact_defect(told, P06_T3_PAYLOAD, genova) == ""


def test_w13_t2_the_countrys_price_is_said_without_placing_it_in_cordoba():
    user = "¿Cuánto me sale cargar 40 litros de nafta Super en Córdoba?"
    first = "Llenar 40 litros de nafta súper en Córdoba cuesta $82.360."
    retry = "40 litros de nafta súper cuestan 82.360 pesos."
    assert _payload_fact_defect(first, W13_T2_PAYLOAD, user) == "search_report_off_subject"
    assert _search_report_says_unseen_name(first, W13_T2_PAYLOAD, user) == ["Córdoba"]
    # The retry was published nowhere: «pesos» for «$» and the missing «Córdoba» both killed it.
    assert _payload_fact_defect(retry, W13_T2_PAYLOAD, user) == ""
    assert _payload_fact_defect("Cargar 40 litros de nafta súper sale $82.360.", W13_T2_PAYLOAD, user) == ""


def test_p08_t2_an_article_on_a_narrower_subject_does_not_answer_the_place():
    user = "Search for stage shows in Cape Town."
    draft = "The Cape Town Stadium is a football and rugby union stadium in Cape Town, South Africa."
    assert _payload_fact_defect(draft, P08_T2_PAYLOAD, user) == "search_report_off_subject"
    assert _payload_fact_defect("I couldn't find it.", P08_T2_PAYLOAD, user) == ""
    # The article named after the place itself still answers about it.
    plain = copy.deepcopy(P08_T2_PAYLOAD)
    plain["seen"]["query"] = "Cape Town population"
    plain["seen"]["results"][0].update(
        title="Cape Town", snippet="Cape Town is the legislative capital of South Africa, with a population of 4.7 million."
    )
    assert _payload_fact_defect("Cape Town has a population of 4.7 million.", plain, "Cape Town population") == ""


def test_p03_t1_a_note_the_list_does_not_hold_is_not_found_not_a_failure():
    situation = json.dumps({
        "kind": "operation", "operation": "note.list", "polarity": "success", "verified": True, "succeeded": True,
        "observed": {
            "notes": [{"title": "«Llego tarde hoy»", "createdAtUtc": "2026-09-28T22:49:11.7694215+00:00",
                       "updatedAtUtc": "2026-09-28T22:49:11.7694215+00:00", "revision": 1, "isTrashed": False}],
            "count": 1, "totalCount": 1, "scope": "active", "limit": 50, "offset": 0,
        },
    })
    user = "Actually, can you find the note called grocery?"
    first = 'I cannot find a note called "grocery" in your active notes; the only note visible is titled "Llego tarde hoy".'
    assert compose_visible_defect(first, "status", user, {"situation": situation}) == ""
    # A note the list does hold, or a failure of the reading, is still a failure asserted.
    assert compose_visible_defect(
        'I cannot find a note called "Llego tarde hoy".', "status", user, {"situation": situation}
    ) == "asserted_failure"
    assert compose_visible_defect("I could not read your notes.", "status", user, {"situation": situation}) == (
        "asserted_failure"
    )


def test_w05_t3_the_date_is_asked_without_its_machine_format():
    question = validate_missing_argument_clarification(
        {
            "requested_fields": ["dueUtc"],
            "question": "¿Cuál es la fecha y hora exacta en formato UTC para la renovación del contrato del piso?",
        },
        ("dueUtc",),
    )
    assert question == "¿Cuál es la fecha y hora exacta para la renovación del contrato del piso?"
    assert _question_without_time_format("What time (UTC) should I set it for?") == "What time should I set it for?"
    assert _question_without_time_format("¿A qué hora lo pongo?") == "¿A qué hora lo pongo?"


def test_p10_t2_a_clarification_never_hands_the_request_back():
    assert not _recovery_question_is_valid(
        "¿Podrías explicarme paso a paso cómo instalar y ejecutar ese código en tu computadora?"
    )
    assert _recovery_question_is_valid("¿Qué ejemplo de la calculadora quieres ver?")
    assert _recovery_question_is_valid("¿En qué carpeta está el archivo?")


def test_p08_t3_and_d_s007_the_provided_information_is_the_prompt():
    clarification = json.dumps({"kind": "clarification", "polarity": "pending", "cause": "ambiguous_request"})
    assert compose_visible_defect(
        "The venue is not specified in the provided information.", "clarification",
        "What is the venue of the event?", {"situation": clarification},
    ) == "copied_instruction"
    conversation = json.dumps({"kind": "conversation", "polarity": "success"})
    assert compose_visible_defect(
        "La lista de destinatarios y remitentes no está disponible en la situación proporcionada.", "conversation",
        "hazme una lista de los destinatarios y remitentes de los emails de la ultima semana",
        {"situation": conversation},
    ) == "copied_instruction"


VOLUME_AT_MAXIMUM_MUTED = json.dumps({
    "kind": "failure", "polarity": "failure", "cause": "mission_failed", "stepCount": 0, "steps": [],
    "reason": json.dumps({
        "kind": "operation", "operation": "audio.volume.adjust", "polarity": "failure", "verified": False,
        "succeeded": False, "error": "volume_already_at_maximum_muted",
    }),
})


def test_w02_t4_and_w11_t3_the_volume_at_its_maximum_and_muted_is_said_plainly():
    user = "Sube el volumen 20."
    plain = "El volumen ya está al máximo, pero en silencio. ¿Lo activo?"
    assert compose_visible_defect(plain, "error", user, {"situation": VOLUME_AT_MAXIMUM_MUTED}) == ""
    assert compose_visible_defect(
        "Subí el volumen al máximo.", "error", user, {"situation": VOLUME_AT_MAXIMUM_MUTED}
    ) != ""
    situation = _situation_from_facts({"situation": VOLUME_AT_MAXIMUM_MUTED})
    assert _deterministic_final(situation, {"outcome": "failed"}, user, "es") == plain
    assert "muted" in _cause_in_prose("volume_already_at_maximum_muted", "es")
    assert "maximum" in _cause_in_prose("volume_already_at_maximum", "es")
    assert "minimum" in _cause_in_prose("volume_already_at_minimum", "es")


def test_d_s004_a_limit_conjugates_the_verb_the_person_wrote():
    request = "recomprar el último billete de tren a huesca"
    assert _unsupported_answer_contract_failure(
        "No recomprobo el billete de tren a Huesca.", request
    ) == "unsupported_broken_person"
    assert not limit_breaks_the_asked_verb("No recompro billetes de tren.", request)
    # Diphthongs, closed vowels and spelling changes are forms of the verb.
    assert not limit_breaks_the_asked_verb("No recomiendo restaurantes.", "recomendar un restaurante")
    assert not limit_breaks_the_asked_verb("No conduzco coches.", "conducir el coche")
    assert not limit_breaks_the_asked_verb("No construyo casas.", "construir una casa")
    assert not limit_breaks_the_asked_verb("No protejo esa carpeta.", "proteger la carpeta")
    assert not limit_breaks_the_asked_verb("No obtengo entradas.", "obtener dos entradas")
    assert not limit_breaks_the_asked_verb("No adquiero acciones.", "adquirir acciones de Tesla")


def test_d_s042_wanting_a_cake_from_a_bakery_is_not_asking_to_make_it():
    assert _unsupported_answer_contract_failure(
        "No preparo el pastel de camote de una panadería local.", "quiero pastel de camote de una panadería local"
    ) == "unsupported_changed_act"
    assert _unsupported_answer_contract_failure("No preparo pasteles.", "hazme un pastel de camote") != (
        "unsupported_changed_act"
    )


def test_d_s005_a_recovered_limit_is_audited_as_unsupported(monkeypatch, tmp_path):
    audit_path = tmp_path / "turn-audit.jsonl"
    monkeypatch.setenv(turn_audit.TURN_AUDIT_ENV, str(audit_path))
    llm = SimpleNamespace(compose_user_message=lambda *args, **kwargs: "No enciendo la pantalla.")

    result = _recover_failed_turn(
        {"id": "d-s005", "text": "Turn on la pantalla", "history": [], "uiLanguage": "es"},
        llm,
        attempts=1,
        failure_kinds=(turn_audit.LIMIT_WORDING_FAILURE,),
    )

    record = json.loads(audit_path.read_text(encoding="utf-8"))
    assert result["conversationKind"] == "unsupported"
    assert result["reply"] == "No enciendo la pantalla."
    assert record["stages"][0]["conversation_kind"] == "unsupported"
