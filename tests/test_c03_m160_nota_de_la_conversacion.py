"""M160 (2026-10-04, App run v4w): a note takes from the conversation what the person points at, and a note the
conversation just made is the one an addition goes to. Each row is reproduced on the path the App takes (the arguments
request carries the decider's restatement as its text and the lived conversation as its history; a note.update crosses
the planner as the kernel's dependency relation says).

1. DEV-H H-w11-t3 «save that whole thing as a note called banana bread» after the recipe and «350 degrees Fahrenheit is
   177 degrees Celsius.» → «What content should be saved in the private note called banana bread?»: M67 offered the
   extraction only BAXY's last reply, the temperature, and the model said it was not the content.
2. DEV-I I-w18-t3 «perfecto, ¿me la guardas en una nota con esas cantidades?» after the recipe and the flour for 20 →
   «¿Cuál es la receta de sopaipillas con 500 g de harina para 20 unidades que debes guardar en una nota?».
3. DEV-F F-w34-t3 «Guárdamela en una nota que se llame tortilla» after the recipe for 4 and the quantities for 8 → saved
   the decider's words «receta de tortilla de patatas con cebolla para cuatro personas». The gold asks the version for 8
   («10 patatas | 12 huevos | 2 cebollas» on the scripted history; on the lived one only «2 cebollas» is said, in the
   reply for 8): it does not take the recipe for 4 alone. The note keeps the recipe and the quantities that adjusted
   it, both BAXY's words.
4. DEV-G G-w12-t2 «agrégale que quiero comprarle un ramo de flores» after «He guardado la nota con el título "ideas para
   el cumpleaños de juliana".» → «¿Cuál es el título de la nota que deseas editar?» on every run since v3d (M141
   diagnosed it). note.update requires noteId, expectedRevision, expectedTitle, title and content (the WHOLE new content,
   not an addition), and only a read of the note gives the first three; nothing fed them. Now note.update crosses
   note.read (kernel ``MissionPlanValidator`` and ``planner._required_predecessors``), the read is of the note the
   conversation is on (``DialogueState.edited_note_title``), and the update keeps what the note says followed by what
   the person adds (``semantic.notes.note_addition``).

Also changed in v4w: G-w29-t4 «guárdame la de javascript en una nota…» (the decider's «función de celsius a fahrenheit
en JavaScript» was saved instead of the code) and F-w42-t3 «…con las dos versiones» (only the JavaScript was saved).
Rows are quoted with their real text and the history the App lived; every other phrasing is our own.
"""

from __future__ import annotations

from typing import Any

from baxy_mind import __main__ as sidecar
from baxy_mind.planner import required_predecessors
from baxy_mind.semantic.dialogue import DialogueState
from baxy_mind.semantic.notes import names_a_note, note_addition, pointed_note_content
from baxy_mind import turn_history
from baxy_mind import decided_arguments
from baxy_mind import direct_arguments
from baxy_mind import plan_dependencies
from baxy_mind import argument_grounding
from baxy_mind import plan_shape
from baxy_mind import argument_payload

NOTE = {"type": "object", "properties": {
    "content": {"type": "string", "x-maxUtf8Bytes": 65536},
    "title": {"type": "string", "x-maxUtf8Bytes": 512, "x-nonWhitespace": True},
}, "required": ["content", "title"], "additionalProperties": False}
NOTE_UPDATE = {"type": "object", "properties": {
    "content": {"type": "string", "x-maxUtf8Bytes": 65536},
    "expectedRevision": {"type": "integer", "minimum": 1},
    "expectedTitle": {"type": "string", "x-maxUtf8Bytes": 512, "x-nonWhitespace": True},
    "noteId": {"type": "string", "maxLength": 36, "x-nonWhitespace": True},
    "title": {"type": "string", "x-maxUtf8Bytes": 512, "x-nonWhitespace": True},
}, "required": ["content", "expectedRevision", "expectedTitle", "noteId", "title"], "additionalProperties": False}
NOTE_SELECTOR = {"type": "object", "properties": {
    "expectedIsTrashed": {"type": ["boolean", "null"]},
    "expectedRevision": {"type": ["integer", "null"], "minimum": 1},
    "expectedTitle": {"type": ["string", "null"], "x-maxUtf8Bytes": 512, "x-nonWhitespace": True},
    "noteId": {"type": ["string", "null"], "maxLength": 36},
    "title": {"type": ["string", "null"], "x-maxUtf8Bytes": 512, "x-nonWhitespace": True},
}, "required": [], "additionalProperties": False}


def _tool(operation: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {"type": "function", "function": {"name": operation.replace(".", "_"), "canonical_name": operation,
                                             "description": operation, "risk": "low_reversible", "parameters": schema}}


def _history(said: list[str]) -> list[dict[str, str]]:
    return [{"role": "user" if index % 2 == 0 else "assistant", "content": line} for index, line in enumerate(said)]


def _exchanges(said: list[str]) -> list[tuple[str, str]]:
    return turn_history._conversation_exchanges(_history(said))


class _Extraction:
    """The model's own extraction: abstains; records the reply it was offered as the possible content (M67)."""

    def __init__(self) -> None:
        self.offered: str | None = None
        self.asked: list[tuple[str, ...]] = []

    def extract_direct_arguments(self, *_args: object, **kwargs: object) -> argument_payload.DirectArgumentExtraction:
        self.offered = kwargs.get("previous_reply")  # type: ignore[assignment]
        return argument_payload.DirectArgumentExtraction(arguments=None, evidence=(), fallback_question="¿Qué guardo en la nota?")

    def formulate_missing_argument_question(self, _objective, _purpose, _tool, fields, **_kwargs) -> str:
        self.asked.append(tuple(fields))
        return "¿Qué quieres que diga la nota?"


def _arguments(said: list[str], request: str, decided: tuple[tuple[str, Any], ...],
               model: _Extraction | None = None) -> tuple[Any, str]:
    """The App's arguments request for note.create: the decider's restatement as text, the lived conversation."""

    decided_arguments._DECIDED_ARGUMENTS.clear()
    decided_arguments._remember_decided_arguments(request, ("note.create",), decided)
    return direct_arguments._direct_arguments_result(
        {"operation": "note.create", "text": request, "history": _history(said), "responseLanguage": "es"},
        llm=model or _Extraction(), tool=_tool("note.create", NOTE), dialogue_state=DialogueState(),
    )


# ------------------------------------------------------------------ the lived conversations (window/v4w RUN.jsonl)

BANANA = (
    "Banana Bread I is a basic, reliable recipe for over-ripe bananas.\nIngredients:\n- 1 cup White sugar\n- ½ cup "
    "Butter, softened\n- 3 Bananas, mashed\n- 2 Eggs\n- 2 cups All-purpose flour\n- ½ tsp Baking soda\n- ⅓ cup Sour "
    "milk or buttermilk\n- ¼ tsp Salt\n- 1 tsp Vanilla extract\nSteps:\n1. Preheat oven to 350°F (175°C).\n2. Lightly "
    "grease an 8 x 4-inch loaf pan.\n3. Combine all ingredients into a large mixing bowl and beat well.\n4. Pour batter "
    "into the pan.\n5. Bake on the middle shelf of the oven for 60 minutes, or until a toothpick inserted into the "
    "center of the loaf comes out clean."
)
H_W11 = [
    "could you give me a simple recipe for banana bread? I've got three overripe bananas sitting on the counter and no "
    "idea what to do with them",
    BANANA,
    "what's 350 in celsius?",
    "350 degrees Fahrenheit is 177 degrees Celsius.",
    "save that whole thing as a note called banana bread",
]
SOPAIPILLAS = (
    "Sopaipillas pasadas son una comida chilena de masa de trigo servida en crema de chancaca, naranja y canela.\n"
    "Ingredientes:\n- Harina de trigo\n- Manteca\n- Sal\n- Polvos de hornear\n- Zapallo\n- Pan de chancaca\n- Agua\n"
    "- Canela en rama\n- Clavos de olor\n- Maicena\n- Cáscara de naranja\n- Aceite de maravilla\nPreparación:\n1. En un "
    "bol, coloque la harina cernida formando un volcán, agregue la sal por los costados y los polvos de hornear en el "
    "centro.\n2. Cocine el zapallo en agua fría hasta que hierva y luego durante 20 minutos más.\n3. Retire el zapallo "
    "del agua, reserve este último y muela el zapallo para obtener un puré limpio.\n4. Derrita la manteca.\n5. Agregue "
    "el puré de zapallo y la manteca derretida al volcán de harina, mezcle y forme la masa sin trabajarla mucho.\n6. "
    "Tápela y déjela reposar durante 10 minutos.\n7. Estire la masa hasta que quede de 3 milímetros de grosor.\n8. Corte "
    "discos de 8 centímetros de diámetro y pinche cada sopaipilla con un tenedor."
)
I_W18 = [
    "¿me podrías dar una receta de sopaipillas pasadas?",
    SOPAIPILLAS,
    "y pa hacer 20, ¿cuánta harina sería?",
    "Para hacer 20 sopaipillas necesitas 500 gramos de harina.",
    "perfecto, ¿me la guardas en una nota con esas cantidades?",
]
TORTILLA = (
    "Tortilla de patatas con cebolla:\n- 8 huevos grandes\n- 1 kg de patatas\n- 1 cebolla mediana o grande\n- 1/2 litro "
    "de aceite de oliva\n- Sal\n\nPreparación:\n1. Pelar, lavar y secar las patatas, cortarlas en taquitos, volver a "
    "lavarlas, añadir sal y freirlas en aceite caliente hasta que estén fritas pero no doradas, luego escurrirlas.\n2. "
    "Cortar la cebolla en cuadraditos pequeños y dorarla en la sartén hasta que esté transparente, retirándola junto con "
    "las patatas y eliminando el exceso de aceite.\n3. Batir los 8 huevos con una pizca de sal por cada yema hasta "
    "obtener un batido homogéneo con espumita, mezclarlo con las patatas y la cebolla fritas en una fuente."
)
FOR_EIGHT = (
    "Para ocho personas, necesitas el doble de ingredientes: 16 huevos, 2 kg de patatas, 2 cebollas y 1 litro de aceite "
    "de oliva. El proceso de preparación se mantiene igual, ajustando solo las cantidades."
)
F_W34 = [
    "Oye, ¿cómo se hace una tortilla de patatas para cuatro personas? Con cebolla, eh, que en casa somos de cebolla",
    TORTILLA,
    "¿Y si al final somos ocho?",
    FOR_EIGHT,
    "Guárdamela en una nota que se llame tortilla",
]
G_W29 = [
    "¿me escribes una función en python que pase grados celsius a fahrenheit?",
    "```python\ndef celsius_a_fahrenheit(c):\n    return (c * 9/5) + 32\n```",
    "pásamela tal cual a javascript, que es para una página que estoy armando",
    "```javascript\nfunction celsius_a_fahrenheit(c) {\n    return (c * 9/5) + 32;\n}\n```",
    "y con eso, ¿cuánto son 37 grados?",
    "37 grados celsius son 98.6 grados fahrenheit.",
    "chido. guárdame la de javascript en una nota que se llame conversiones",
]
PYTHON_DNI = (
    "def validar_dni(dni):\n    if not isinstance(dni, str) or len(dni) != 9:\n        return False\n    if not "
    "dni[0:8].isdigit() or not dni[8].isalpha():\n        return False\n    letras = \"TRWAGMYFPDXBNJZSQVHLCKE\"\n    "
    "return letras[int(dni[0:8]) % 23] == dni[8]"
)
JS_DNI = (
    "function validarDni(dni) {\n    if (!dni || dni.length !== 9) return false;\n    if (!/^\\d{8}[A-Z]$/.test(dni)) "
    "return false;\n    const letras = \"TRWAGMYFPDXBNJZSQVHLCKE\";\n    return letras[parseInt(dni.slice(0, 8)) % 23] "
    "=== dni[8];\n}"
)
F_W42 = [
    "Hazme una función en Python que compruebe si un DNI es válido mirando la letra del final, que la necesito para un "
    "formulario del curro",
    f"```python\n{PYTHON_DNI}\n```",
    "Ahora lo mismo en JavaScript",
    f"```javascript\n{JS_DNI}\n```",
    "Guárdamelo en una nota que se llame validar dni, con las dos versiones",
]


# ------------------------------------------------------------------ 1–3. the note keeps what the person points at


def test_h_w11_t3_that_whole_thing_is_the_recipe_and_what_followed_it() -> None:
    request = "Save the banana bread recipe as a note called banana bread."  # turn-audit request 1150
    expected = {"title": "banana bread", "content": f"{BANANA}\n\n350 degrees Fahrenheit is 177 degrees Celsius."}
    # The decider's title, or none at all (its content the start of a recipe, cut): the person's title and BAXY's words.
    for decided in ((("title", "banana bread"),), (("content", "Mash 3 bananas, mix in 1/2 cup melted butter"),)):
        arguments, question = _arguments(H_W11, request, decided)
        assert question == "" and arguments == expected


def test_i_w18_t3_with_those_quantities_is_the_recipe_and_its_quantities() -> None:
    request = "Guarda en una nota la receta de sopaipillas con 500 g de harina para 20 unidades."  # request 1226
    arguments, question = _arguments(I_W18, request, (("title", "Receta de sopaipillas"),))
    assert question == ""
    assert arguments == {
        "title": "Receta de sopaipillas",
        "content": f"{SOPAIPILLAS}\n\nPara hacer 20 sopaipillas necesitas 500 gramos de harina.",
    }
    # No title known: the extraction reads those words where it read the last reply alone (M67), and may ask the title.
    model = _Extraction()
    arguments, question = _arguments(I_W18, request, (), model)
    assert model.offered == f"{SOPAIPILLAS}\n\nPara hacer 20 sopaipillas necesitas 500 gramos de harina."


def test_f_w34_t3_the_recipe_goes_with_the_quantities_for_eight() -> None:
    request = "Guarda la receta de tortilla de patatas en una nota llamada tortilla."
    decided = (("title", "tortilla"), ("content", "receta de tortilla de patatas con cebolla para cuatro personas"))
    arguments, question = _arguments(F_W34, request, decided)
    assert question == ""
    assert arguments == {"title": "tortilla", "content": f"{TORTILLA}\n\n{FOR_EIGHT}"}
    assert "2 cebollas" in arguments["content"]  # what the gold reads of the version for 8
    # On the scripted history the reply for 8 names the tortillas itself: it is the last reply, offered as M67 did.
    scripted = ["…para cuatro personas…", "Para 4: 5 patatas, 6 huevos, 1 cebolla, aceite de oliva y sal.",
                "¿Y si al final somos ocho?", "Para 8, mejor dos tortillas: 10 patatas, 12 huevos y 2 cebollas en total.",
                "Guárdamela en una nota que se llame tortilla"]
    assert pointed_note_content(scripted[-1], "tortilla", _exchanges(scripted)) is None


def test_g_w29_t4_the_javascript_one_is_its_code() -> None:
    request = "Guarda la función de JavaScript en una nota llamada conversiones."
    decided = (("title", "conversiones"), ("content", "función de celsius a fahrenheit en JavaScript"))
    arguments, question = _arguments(G_W29, request, decided)
    assert question == ""
    assert arguments == {"title": "conversiones",
                         "content": "function celsius_a_fahrenheit(c) {\n    return (c * 9/5) + 32;\n}"}


def test_f_w42_t3_both_versions_are_both_codes() -> None:
    request = "Guarda las dos versiones en una nota llamada validar dni."
    arguments, question = _arguments(F_W42, request, (("title", "validar dni"),))
    assert question == "" and arguments == {"title": "validar dni", "content": f"{PYTHON_DNI}\n\n{JS_DNI}"}


def test_the_same_in_other_words_and_the_other_language() -> None:
    lasagna = ["how do I make a quick lasagna?",
               "Quick lasagna: layer cooked sheets, 500 g of ragù and 300 g of béchamel three times, top with parmesan "
               "and bake 40 minutes.",
               "how long should it rest?", "About 15 minutes, so the layers set before cutting.",
               "keep it in a note called lasagna"]
    assert pointed_note_content(lasagna[-1], "lasagna", _exchanges(lasagna)) == f"{lasagna[1]}\n\n{lasagna[3]}"
    panqueques = ["dame una receta de panqueques",
                  "Panqueques: mezcla 1 taza de harina, 1 huevo y 1 taza de leche; cocina en sartén.",
                  "¿qué hora es?", "Son las 17:40.",
                  "guárdame la receta en una nota que se llame panqueques"]
    # The time asked between them goes on with nothing of the recipe: the recipe alone.
    assert pointed_note_content(panqueques[-1], "panqueques", _exchanges(panqueques)) == panqueques[1]
    fib = ["write a python fib function", "```python\ndef fib(n):\n    return n if n < 2 else fib(n-1) + fib(n-2)\n```",
           "now in js", "```js\nconst fib = n => n < 2 ? n : fib(n - 1) + fib(n - 2);\n```",
           "what is fib of 10?", "fib(10) is 55.",
           "save the python one as a note called fib"]
    assert pointed_note_content(fib[-1], "fib", _exchanges(fib)) == (
        "def fib(n):\n    return n if n < 2 else fib(n-1) + fib(n-2)"
    )
    assert pointed_note_content("save both versions in a note called fib", "fib", _exchanges(fib[:4])) == (
        "def fib(n):\n    return n if n < 2 else fib(n-1) + fib(n-2)\n\n"
        "const fib = n => n < 2 ? n : fib(n - 1) + fib(n - 2);"
    )


# ------------------------------------------------------------------ what must not change


def test_the_last_reply_stays_the_one_meant() -> None:
    # One reply only: «guárdalo en una nota» offers it to the extraction as M67 did.
    single = ["dame la lista de cosas para la playa", "Toalla, bloqueador, agua, gorro y lentes de sol.",
              "guárdalo en una nota que se llame playa"]
    model = _Extraction()
    arguments, _ = _arguments(single, "Guarda la lista en una nota llamada playa.", (("title", "playa"),), model)
    assert arguments is None and model.offered == single[1]
    assert pointed_note_content(single[-1], "playa", _exchanges(single)) is None
    # «ese código» after two versions (DEV-F F-w03-t3), «save that one» (DEV-I I-w05-t4), «eso … titulala dentista»
    # (DEV-F F-w55-t5), «guárdame eso … ponle de título tortilla» (DEV-G G-w44-t3), «save that in a note called home
    # network» (DEV-F F-w10-t3): the last reply, as before.
    leap = ["hey baxy, write me una función en javascript que diga si un año es leap year o no",
            "```javascript\nfunction esAñoBisesto(año) {\n    return (año % 4 === 0 && año % 100 !== 0) || (año % 400 === 0);\n}\n```",
            "nice, ahora en python",
            "```python\ndef es_año_bisesto(año):\n    return (año % 4 == 0 and año % 100 != 0) or (año % 400 == 0)\n```",
            "mete ese código en una nota, title it leap year snippet"]
    assert pointed_note_content(leap[-1], "leap year snippet", _exchanges(leap)) is None
    fib = ["write me a python function that returns the nth fibonacci number", "```python\ndef fib(n): ...\n```",
           "can you make it recursive instead", "```javascript\nfunction fib(n) {\n    return fib(n - 1) + fib(n - 2);\n}\n```",
           "save that one as a note called fib snippets"]
    assert pointed_note_content(fib[-1], "fib snippets", _exchanges(fib)) is None
    dentist = ["mañana a las 10 tengo turno con el dentista en Palermo, recordámelo una hora antes",
               "Te he programado una alarma para mañana a las 09:00 con el título \"turno con el dentista en Palermo\".",
               "cambiando de tema, cuánto está saliendo una limpieza dental en Buenos Aires más o menos?",
               "No encontré información que diga cuánto cuesta la limpieza dental en Buenos Aires.",
               "eso mandalo a una nota, titulala dentista así después lo encuentro"]
    assert pointed_note_content(dentist[-1], "dentista", _exchanges(dentist)) is None
    tortilla = ["oye baxy cómo se hace la tortilla de patatas pa cuatro personas", "¿Te explico cómo hacerla?",
                "y eso pa dos", "Tortilla de patatas:\n- 4 huevos grandes\n- 500 g de patatas",
                "vale guárdame eso en una nota y ponle de título tortilla"]
    assert pointed_note_content(tortilla[-1], "tortilla", _exchanges(tortilla)) is None
    network = ["am i actually connected to the internet right now", "Yes, the PC is online.", "whats my ip on it",
               "The PC has the IPv4 addresses 100.64.0.11 and 192.168.1.106.",
               "save that in a note called home network"]
    assert pointed_note_content(network[-1], "home network", _exchanges(network)) is None
    # DEV-F v4v F-w53-t4: the trip the title names was the person's word in passing, not what a reply was about.
    trip = ["oye en cuanto anda el dolar hoy, voy a cambiar plata pal viaje",
            "El dólar cierra en nuevos máximos desde abril de 2025, superando los $990 con una alza semanal de casi $30.",
            "y el euro como amanecio", "No encontré el precio del euro hoy.",
            "ya entonces cuanto serian 350 lucas en euros mas o menos",
            "350 dólares equivaldrían a aproximadamente 190 euros, considerando el cambio actual del dólar en máximos y el "
            "valor del euro que no tengo disponible hoy.",
            "anotalo en una nota q se llame viaje lisboa"]
    assert pointed_note_content(trip[-1], "viaje lisboa", _exchanges(trip)) is None


def test_a_dictated_or_unsaid_note_does_not_change() -> None:
    # A note dictated in the message keeps what was dictated (M111), whatever was said before.
    said = [*H_W11[:4], "crea una nota que se llame compras y pon ahí: pan y leche"]
    arguments, question = _arguments(said, "Crea una nota llamada «compras» con el contenido «pan y leche».",
                                     (("content", "pan y leche"), ("title", "compras")))
    assert question == "" and arguments == {"title": "compras", "content": "pan y leche"}
    # A note named only by what it is about still asks what it says (M157).
    junta = ["oye, busca el archivo que se llama presupuesto_2026 en mis documentos",
             "No he encontrado un archivo llamado presupuesto_2026 en la carpeta Documentos.",
             "órale, ábremelo por favor",
             "No se pudo abrir el archivo presupuesto_2026 porque no existe en la carpeta Documentos.",
             "oye, de paso, crea una nota de la junta de hoy"]
    model = _Extraction()
    arguments, question = _arguments(junta, "Crea una nota de la junta de hoy.",
                                     (("content", "Junta de hoy."), ("title", "Junta de hoy")), model)
    assert arguments is None and question == "¿Qué quieres que diga la nota?" and model.asked == [("content",)]
    # Another operation never takes it (DEV-F F-w03-t6 «la nota del snippet, léemela» is a read).
    assert decided_arguments._pointed_note_content("note.read", "Lee la nota.", "léemela", _history(H_W11), NOTE, "", None) is None


# ------------------------------------------------------------------ 4. G-w12-t2, an addition to the note just made

G_W12 = [
    "crea una nota que diga ideas para el cumpleaños de juliana",
    "He guardado la nota con el título \"ideas para el cumpleaños de juliana\".",
    "agrégale que quiero comprarle un ramo de flores",
]
# turn-audit request 1153 (v4w), 1126 (v4v): the same restatement.
G_W12_REQUEST = "Agrega «quiero comprarle un ramo de flores» a la nota «ideas para el cumpleaños de juliana»."


def _created(state: DialogueState, request: str, title: str, content: str) -> DialogueState:
    """The note.create the App verified, as the composer's situation carries it (no identity: OperationVisibleFacts)."""

    state.expect(request, ["note.create"])
    state.record({"kind": "operation", "operation": "note.create", "polarity": "success", "verified": True,
                  "succeeded": True, "observed": {"title": title, "content": content, "revision": 1,
                                                  "isTrashed": False}})
    return state


def _read(note_id: str, title: str, content: str, revision: int) -> list[dict[str, Any]]:
    return [{"stepId": "step_1", "operation": "note.read", "verified": True, "status": "completed",
             "result": {"noteId": note_id, "title": title, "content": content, "createdAtUtc": "2026-10-04T15:31:54Z",
                        "updatedAtUtc": "2026-10-04T15:31:54Z", "trashedAtUtc": None, "revision": revision,
                        "isTrashed": False}}]


def _grounded_update(objective: str, observations: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The plan.ground request for the note.update step, as the sidecar answers it."""

    tool = _tool("note.update", NOTE_UPDATE)
    arguments = plan_dependencies._verified_dependency_identity_arguments(
        "note.update", objective, observations, tool, purpose=objective,
    )
    if arguments is None:
        return None
    grounded = sidecar.normalize_grounded_arguments(
        arguments, NOTE_UPDATE, argument_grounding.trusted_plan_grounding_source(objective, observations),
    )
    return argument_grounding._normalize_grounded_operation_arguments("note.update", grounded, objective) if grounded else None


def test_g_w12_t2_the_note_just_made_takes_the_addition() -> None:
    assert required_predecessors("note.update") == ("note.read",)
    skeleton = plan_shape._explicit_plan_skeleton(("note.update",), (G_W12_REQUEST,))
    assert [(step["operation"], step["dependsOn"], step["argumentsMode"]) for step in skeleton["steps"]] == [
        ("note.read", [], "literal"),
        ("note.update", ["step_1"], "after_dependencies"),
    ]
    state = _created(DialogueState(), "Crea una nota que diga ideas para el cumpleaños de juliana.",
                     "ideas para el cumpleaños de juliana", "ideas para el cumpleaños de juliana")
    state.expect(G_W12_REQUEST, ["note.update"])
    operations = ("note.read", "note.update")
    assert plan_dependencies._conversation_note_selector("note.read", operations, G_W12[-1], state, NOTE_SELECTOR) == {
        "title": "ideas para el cumpleaños de juliana",
    }
    note_id = "3f2b8c1e-6a0d-4e57-9b1a-2c4d5e6f7a80"
    observations = _read(note_id, "ideas para el cumpleaños de juliana", "ideas para el cumpleaños de juliana", 1)
    assert _grounded_update(G_W12_REQUEST, observations) == {
        "noteId": note_id,
        "expectedRevision": 1,
        "expectedTitle": "ideas para el cumpleaños de juliana",
        "title": "ideas para el cumpleaños de juliana",
        "content": "ideas para el cumpleaños de juliana\nquiero comprarle un ramo de flores",
    }


def test_additions_in_other_words_and_the_other_language() -> None:
    assert note_addition(G_W12[-1]) == "quiero comprarle un ramo de flores"
    assert note_addition("añádele que el viernes no puedo") == "el viernes no puedo"
    assert note_addition("súmale una botella de vino, porfa") == "una botella de vino"
    assert note_addition("Agrega tomates a la nota Lista del súper.") == "tomates"  # DEV-D v4w D-w03-t2's restatement
    assert note_addition("also add that she likes tulips") == "she likes tulips"
    assert note_addition('Add "buy candles" to the note "birthday ideas".') == "buy candles"
    assert note_addition("add milk to my shopping note please") == "milk"
    observations = _read("0d8f6a52-1c3b-4e9a-8f7d-6b5a4c3d2e1f", "Lista del súper", "pan, palta y leche", 2)
    assert _grounded_update("Agrega tomates a la nota Lista del súper.", observations)["content"] == (
        "pan, palta y leche\ntomates"
    )
    observations = _read("0d8f6a52-1c3b-4e9a-8f7d-6b5a4c3d2e1f", "birthday ideas", "- cake\n- balloons", 4)
    update = _grounded_update("Add that she likes tulips to the note.", observations)
    assert update is not None and update["expectedRevision"] == 4 and update["content"] == (
        "- cake\n- balloons\nshe likes tulips"
    )


def test_what_an_addition_must_not_take() -> None:
    operations = ("note.read", "note.update")
    # «agrégale X» with no note in the conversation: no selector; the read is extracted and asked as before.
    fresh = DialogueState()
    fresh.expect("Agrega que quiero comprarle un ramo de flores a la nota.", ["note.update"])
    assert plan_dependencies._conversation_note_selector("note.read", operations, G_W12[-1], fresh, NOTE_SELECTOR) is None
    assert argument_grounding._ground_explicit_arguments("note.read", G_W12[-1], NOTE_SELECTOR) is None
    # Another effect after the note: the conversation is no longer on it (as M80's task).
    moved_on = _created(DialogueState(), "crea una nota que diga ideas", "ideas", "ideas")
    moved_on.expect("Abre Spotify.", ["app.open"])
    moved_on.record({"operation": "app.open", "verified": True, "succeeded": True, "observed": {}})
    moved_on.expect(G_W12_REQUEST, ["note.update"])
    assert plan_dependencies._conversation_note_selector("note.read", operations, G_W12[-1], moved_on, NOTE_SELECTOR) is None
    # The person names another note: that one, read as before.
    state = _created(DialogueState(), "crea una nota que diga ideas", "ideas", "ideas")
    assert names_a_note("agrégale huevos a la nota de compras")
    assert plan_dependencies._conversation_note_selector(
        "note.read", operations, "agrégale huevos a la nota de compras", state, NOTE_SELECTOR,
    ) is None
    # A read that is not before an update, and a request that adds nothing (a new title), keep their own paths.
    assert plan_dependencies._conversation_note_selector("note.read", ("note.read",), "léemela", state, NOTE_SELECTOR) is None
    assert note_addition("ponle de título viaje a Lisboa") is None
    assert note_addition("Agrega a la nota «compras».") is None
    observations = _read("3f2b8c1e-6a0d-4e57-9b1a-2c4d5e6f7a80", "ideas", "ideas", 1)
    assert _grounded_update("Cambia el título de la nota a viaje.", observations) is None
