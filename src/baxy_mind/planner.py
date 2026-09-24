"""Planner estructurado de BAXY.

El modelo propone una estructura pequeña; este módulo conserva el control:

* el catálogo del ``hello`` es la única fuente de operaciones;
* ``memory.*`` nunca entra al planner general;
* la shortlist se calcula antes de llamar al LLM;
* un plan es un DAG acotado, sin autoridad ni riesgo declarados por el modelo;
* los argumentos literales se validan contra el schema exacto de la tool;
* los argumentos que dependen de un resultado se groundean después de observarlo.

No ejecuta tools. La ejecución, confirmación y verificación siguen en el core
determinista.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence

from .semantic import lexicon
from .effect_intent import (
    _fold,
    enumerated_note_dependency_order,
    has_named_window_target,
    process_report_file_request,
)

MAX_PLAN_STEPS = 16
# Cuántas operaciones ve el decisor. El ranking es por operación: no hay ventana
# por familia, porque rankear familias y luego repartir plazas dentro de ellas
# perdía la hoja correcta a manos de sus hermanas -- 73/124 contra 102/124 sobre
# el corpus de paráfrasis frescas del goal 03.
# El tope se midió: bajarlo a 8 sólo sube el acierto condicionado del decisor de
# 79,6 % a 82,4 % y cuesta doce filas de recuperación.
MAX_SHORTLIST_OPERATIONS = 28
MAX_PURPOSE_CHARS = 512
MAX_QUESTION_CHARS = 512
MAX_OBJECTIVE_CHARS = 16_384

_STEP_ID = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_UNSAFE_FORMAT_CODEPOINTS = {
    0x061C,
    0x200B,
    0x200C,
    0x200D,
    0x200E,
    0x200F,
    0x202A,
    0x202B,
    0x202C,
    0x202D,
    0x202E,
    0x2060,
    0x2066,
    0x2067,
    0x2068,
    0x2069,
    0xFEFF,
}
_ENUM_EVIDENCE_ALIASES = {
    # A wake-up request names the alarm by its purpose (TIME1189/000, /007, /008).
    "alarm": (
        "alarm", "alarma", "timer", "temporizador",
        "despertame", "despiertame", "levantame", "wake me", "despertador",
        # Uso real 2026-09-23 «pon alerta para las dos de la tarde».
        "alerta", "alert",
        # A countdown names the timer by counting («contá 10 minutos»).
        "conta", "contame", "cuentame", "cuenta", "count",
    ),
    "reminder": ("reminder", "recordatorio"),
    "whatsapp": ("whatsapp", "wsp"),
    "am": ("am", "a.m.", "a. m.", "de la manana", "in the morning"),
    "pm": (
        "pm",
        "p.m.",
        "p. m.",
        "de la tarde",
        "de la noche",
        "in the afternoon",
        "in the evening",
    ),
    "windows.calculator": ("calculator", "calculadora"),
    "windows.notepad": ("notepad", "bloc de notas"),
    "spotify": ("spotify", "musica", "music", "cancion", "song"),
    "next": ("next", "siguiente", "proxima", "saltar"),
    "pause": ("pause", "pausa", "pausar"),
    "play": ("play", "reproduce", "reproducir", "pon", "inicia"),
    "previous": ("previous", "anterior", "atras"),
    "stop": ("stop", "deten", "detener", "para"),
    "docx": ("docx", "word", "documento"),
    "xlsx": ("xlsx", "excel", "spreadsheet", "hoja de calculo", "tabla"),
    # H0516 «Abre Opera GX, …»: el valor del catálogo lleva guion bajo y la persona
    # escribe «Opera GX»; sin el alias, «opera» —substring de «opera gx»— pasaba por
    # fundamentado y «opera_gx» no, justo al revés de lo dicho.
    "opera_gx": ("opera gx", "opera_gx", "operagx"),
    "netflix": ("netflix",),
    "disney_plus": ("disney plus", "disney+", "disneyplus", "disney"),
    "prime_video": ("prime video", "amazon prime", "prime"),
    "youtube": ("youtube",),
    "all_known": (
        "all known",
        "known folders",
        "archivos",
        "carpetas conocidas",
    ),
    # ARRANGE1783 «poné chrome a la izquierda»: the side of window.snap is the
    # person's word in either language.
    "left": ("left", "izquierda", "izquierdo"),
    "right": ("right", "derecha", "derecho"),
    "desktop": ("desktop", "escritorio"),
    "documents": ("documents", "documentos"),
    "downloads": (
        "downloads",
        "downloaded",
        "descargas",
        "descargue",
    ),
    # Tanda 3 «Muéstrame mi Gallery.»: Explorer's Gallery (Galería) is the pictures folder shown (lexicon.GALLERY_NOUNS,
    # which semantic.surface rewrites the same way); a proposal naming it is grounded, not asked which folder.
    "pictures": ("pictures", "photos", "imagenes", "fotos", "gallery", "galeria"),
    "brightness": ("brightness", "brillo"),
    "night_light": ("night light", "luz nocturna"),
    "lock": ("lock", "bloquea", "bloquear"),
    "restart": ("restart", "reboot", "reinicia", "reiniciar", "reiniciame"),
    # H0714 variants: «shut down the computer», «turn off the pc», «power off».
    "shutdown": ("shutdown", "shut down", "turn off", "power off", "switch off", "apaga", "apagar", "apagame"),
    "sleep": ("sleep", "suspende", "suspender"),
    "up": (
        "up",
        "increase",
        "raise",
        "sube",
        "subir",
        "aumenta",
        "aumentar",
        "incrementa",
        "incrementar",
    ),
    "down": (
        "down",
        "decrease",
        "lower",
        "baja",
        "bajar",
        "reduce",
        "reducir",
    ),
}
_NUMBER_ALIASES = {
    0: ("zero", "cero"),
    1: ("one", "uno", "una"),
    5: ("five", "cinco"),
    10: ("ten", "diez"),
    15: ("fifteen", "quince"),
    20: ("twenty", "veinte"),
    25: ("twenty five", "veinticinco"),
    30: ("thirty", "treinta"),
    35: ("thirty five", "treinta y cinco"),
    40: ("forty", "cuarenta"),
    45: ("forty five", "cuarenta y cinco"),
    50: ("fifty", "cincuenta"),
    55: ("fifty five", "cincuenta y cinco"),
    60: ("sixty", "sesenta"),
    65: ("sixty five", "sesenta y cinco"),
    70: ("seventy", "setenta"),
    75: ("seventy five", "setenta y cinco"),
    80: ("eighty", "ochenta"),
    85: ("eighty five", "ochenta y cinco"),
    90: ("ninety", "noventa"),
    95: ("ninety five", "noventa y cinco"),
    100: ("one hundred", "cien", "ciento"),
}
_TRUE_CUES = frozenset(
    {
        "true",
        "on",
        "enable",
        "enabled",
        "activa",
        "activar",
        "activame",
        "activalo",
        "enciende",
        "enciendelo",
        # NETWORK1293: voseo and clitic forms («encendé», «prendeme el
        # bluetooth») asked for the state already said.
        "encende",
        "encendeme",
        "encendelo",
        "encender",
        "prende",
        "prendeme",
        "prendelo",
        "prender",
        "mute",
        "mutea",
        "mudo",
        "silencia",
        "silenciame",
        "silencio",
    }
)
_FALSE_CUES = lexicon.AUDIO_RESTORE_WORDS | frozenset(
    {"false", "off", "disable", "disabled", "desactiva", "desactivame", "desactivalo", "desactivar",
     "apaga", "apagame", "apagalo", "apagar", "unmute", "reactiva"}
)
# Owner's test 2026-09-21 (turn 205): a microphone's boolean is «muted», so the
# generic on/off cues read «activa mi micrófono» as state=true and muted an
# already muted microphone. Activating, enabling or unmuting a microphone is
# false; silencing, muting or turning it off is true.
_MICROPHONE_TOKENS = lexicon.MICROPHONE_NOUNS
_MICROPHONE_MUTED_CUES = lexicon.MICROPHONE_MUTE_WORDS | {"true"}
_MICROPHONE_ACTIVE_CUES = lexicon.MICROPHONE_UNMUTE_WORDS | {"false"}
_CONDITIONAL_IDENTITY_PREDECESSORS = {
    # Search returns the authenticated URL that a following navigation must
    # consume. A named page is not itself an exact URL and must never be
    # materialized as one before the verified search result exists.
    "browser.navigate": ("web.search",),
    "browser.navigate.named": ("web.search",),
    # A documentId is opaque and cannot legitimately be inferred from a title.
    # When the same plan creates a document, bind the subsequent read to that
    # verified output unless the user supplied a real opaque ID explicitly.
    "office.document.read": ("office.document.create",),
    # A newly-created note already returns its opaque identity. Reading it by
    # that verified ID is stronger than repeating a title or emitting an empty
    # selector that Core must reject.
    "note.read": ("note.create",),
    # REOPEN1957 H0069: the picture a download writes is the file the viewer
    # opens; its name is known only from the verified download.
    "file.open": ("web.download",),
}
_OPAQUE_ID_EVIDENCE = {
    "browser.navigate": re.compile(r"https?://[^\s]+", re.IGNORECASE),
    "browser.navigate.named": re.compile(r"https?://[^\s]+", re.IGNORECASE),
    "office.document.read": re.compile(r"\bdocument_[0-9a-f]{24}\b", re.IGNORECASE),
    "note.read": re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    ),
}
_OPAQUE_ID = re.compile(
    r"(?:[a-z][a-z0-9]*_[a-z0-9_-]{6,}|"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|"
    r"[1-9][0-9]{0,18})",
    re.IGNORECASE,
)


def conditional_predecessors(
    operation: str,
    objective: str = "",
) -> tuple[str, ...]:
    """Return optional identity producers unless the user supplied the ID."""

    predecessors = _CONDITIONAL_IDENTITY_PREDECESSORS.get(operation, ())
    if (
        operation == "filesystem.write.text"
        and objective
        and process_report_file_request(_fold(objective)) is not None
    ):
        # FILES1705: the file carries the process listing; the listing
        # must be observed before the write can be grounded.
        return ("system.process.list",)
    opaque_evidence = _OPAQUE_ID_EVIDENCE.get(operation)
    if (
        predecessors
        and objective
        and (opaque_evidence is not None and opaque_evidence.search(objective))
    ):
        return ()
    return predecessors


class PlannerContractError(ValueError):
    """Una propuesta del modelo no satisface el contrato del planner."""


@dataclass(frozen=True, slots=True)
class PlannerTool:
    name: str
    description: str
    risk: str
    schema: dict[str, Any]

    @property
    def family(self) -> str:
        return self.name.split(".", 1)[0]

    @property
    def required(self) -> tuple[str, ...]:
        values = self.schema.get("required") or []
        return tuple(value for value in values if isinstance(value, str))


@dataclass(frozen=True, slots=True)
class ProposedStep:
    step_id: str
    operation: str
    purpose: str
    depends_on: tuple[str, ...]
    arguments_mode: str
    arguments: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.step_id,
            "operation": self.operation,
            "purpose": self.purpose,
            "dependsOn": list(self.depends_on),
            "argumentsMode": self.arguments_mode,
            "arguments": self.arguments,
        }


@dataclass(frozen=True, slots=True)
class PlanProposal:
    kind: str
    question: str
    steps: tuple[ProposedStep, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "kind": self.kind,
            "question": self.question,
            "steps": [step.as_dict() for step in self.steps],
        }


Encoder = Callable[..., Any]


class PlannerCatalog:
    """Catálogo planificable y retrieval por familias.

    El encoder es opcional para que las pruebas y el fallback funcionen sin el
    modelo. En producción se reutiliza el mismo e5-small ya cargado por el
    router, evitando un segundo modelo residente.
    """

    def __init__(self, tools: Iterable[dict[str, Any]], encoder: Encoder | None = None):
        parsed: list[PlannerTool] = []
        for raw in tools:
            function = raw.get("function") if isinstance(raw, dict) else None
            if not isinstance(function, dict):
                continue
            name = str(function.get("canonical_name") or "").strip()
            if not name:
                name = str(function.get("name") or "").replace("_", ".").strip()
            risk = str(function.get("risk") or "").strip()
            description = str(function.get("description") or "").strip()
            schema = function.get("parameters")
            if (
                not name
                or name.startswith("memory.")
                or name == "app.status"
                or risk == "forbidden_destructive"
                or not isinstance(schema, dict)
            ):
                continue
            parsed.append(PlannerTool(name, description, risk, schema))
        parsed.sort(key=lambda item: item.name)
        if not parsed:
            raise PlannerContractError("el catálogo planificable está vacío")
        if len({tool.name for tool in parsed}) != len(parsed):
            raise PlannerContractError("el catálogo planificable contiene duplicados")
        self._tools = tuple(parsed)
        self._by_name = {tool.name: tool for tool in parsed}
        families: dict[str, list[PlannerTool]] = {}
        for tool in parsed:
            families.setdefault(tool.family, []).append(tool)
        self._families = {key: tuple(value) for key, value in families.items()}
        self._encoder = encoder
        self._tool_names = tuple(tool.name for tool in self._tools)
        self._tool_documents = tuple(
            f"{tool.name}. {tool.description}. {_compact_schema_hint(tool.schema)}"
            for tool in self._tools
        )
        # The catalogue entries are what a request is matched *against*, so
        # they are encoded on E5's passage side.
        self._tool_vectors = (
            encoder(self._tool_documents, prefix="passage")
            if encoder is not None
            else None
        )

    @property
    def tools(self) -> tuple[PlannerTool, ...]:
        return self._tools

    @property
    def ranks_semantically(self) -> bool:
        """Whether this snapshot ranks with E5 or only with token overlap."""

        return self._tool_vectors is not None

    def get(self, name: str) -> PlannerTool | None:
        return self._by_name.get(name)

    def operation_is_relevant(
        self,
        objective: str,
        operation: str,
        *,
        # Los scores semánticos ya vienen reescalados a 0-1 por consulta. El
        # margen histórico de 0,03 se medía sobre la banda cruda de e5 (~0,05),
        # o sea algo más de la mitad de ella; 0,6 es esa misma tolerancia en la
        # escala nueva.
        margin: float = 0.6,
    ) -> bool:
        if operation not in self._by_name:
            return False
        objective_tokens = _tokens(objective)
        tool = self._by_name[operation]
        if objective_tokens & _tokens(f"{tool.name} {tool.description}"):
            return True
        scores = self._semantic_tool_scores(objective)
        if not scores:
            return True
        best = max(scores.values())
        score = scores.get(operation)
        return score is not None and score >= best - margin

    def shortlist(self, objective: str) -> tuple[PlannerTool, ...]:
        """Rank the authenticated operations for one request, best first.

        Operations are ranked directly. The previous design ranked families and
        then handed out a window inside each one, which is a coarser question
        than the one being asked: the leaf the user meant lost its place to
        siblings of a family that merely scored well. Measured end to end on the
        fresh paraphrase corpus of goal 03 with the same decider, the expected
        operation reached the decider in 73 turns of 124 that way and in 102
        this way.
        """

        objective = _safe_text(objective, "objective", MAX_OBJECTIVE_CHARS)
        tool_scores = self._semantic_tool_scores(objective)
        lexical = _tokens(objective)
        ranked = sorted(
            self._tools,
            key=lambda tool: (
                tool_scores.get(tool.name, 0.0)
                + min(_tool_lexical_score(lexical, tool), 1.0) * 0.12
                + (0.06 if lexical & _tokens(tool.name.rsplit(".", 1)[-1]) else 0.0),
                -len(tool.required),
                tool.name,
            ),
            reverse=True,
        )
        selected = list(ranked[:MAX_SHORTLIST_OPERATIONS])

        # Las dependencias de identidad son conocimiento del contrato, no una
        # inferencia del modelo. Se incluyen si su consumidor quedó visible.
        names = {tool.name for tool in selected}
        for required in _dependency_operations(names):
            tool = self._by_name.get(required)
            if tool is not None and tool.name not in names:
                selected.append(tool)
                names.add(tool.name)
        # Preserve retrieval rank for the constrained LLM. Alphabetizing here
        # discarded the semantic ordering computed above and routinely buried
        # the best operation behind unrelated candidates. Every upstream sort
        # already has a canonical name tie-breaker, so this remains fully
        # deterministic without leaking corpus labels or scores into prompts.
        return tuple(selected[:MAX_SHORTLIST_OPERATIONS])

    def compact_prompt(self, tools: Sequence[PlannerTool]) -> str:
        lines: list[str] = []
        for tool in tools:
            required = ",".join(tool.required) or "-"
            lines.append(
                f"{tool.name} | risk={tool.risk} | required={required} | "
                f"schema={_compact_schema_hint(tool.schema)} | "
                f"{tool.description}"
            )
        return "\n".join(lines)

    def _semantic_tool_scores(self, objective: str) -> dict[str, float]:
        return self._semantic_scores(
            objective,
            self._tool_names,
            self._tool_vectors,
        )

    def _semantic_scores(
        self,
        objective: str,
        names: Sequence[str],
        vectors: Any,
    ) -> dict[str, float]:
        if self._encoder is None or vectors is None:
            return {}
        try:
            # The full objective is the only semantic query. Splitting on a
            # hand-authored conjunction vocabulary made retrieval depend on
            # languages and phrasings known at development time. Lexical
            # catalog evidence still preserves literal operation leaves, while
            # the constrained LLM owns decomposition into individual steps.
            query = self._encoder([objective])
            scores = query @ vectors.T
            raw = {
                name: max(float(row[index]) for row in scores)
                for index, name in enumerate(names)
                if all(math.isfinite(float(row[index])) for row in scores)
            }
        except Exception:
            return {}
        # E5 cosines over short catalogue entries live inside a band of about
        # 0.05, so mixing them with a lexical bonus on a 0-1 scale let a single
        # shared token outrank the meaning of the request. Rescaling this
        # query's scores onto 0-1 makes the mix comparable; measured on the
        # fresh paraphrase corpus it moved the expected operation into the
        # shortlist in 8 more turns out of 124.
        if not raw:
            return {}
        lowest = min(raw.values())
        span = max(raw.values()) - lowest
        if span <= 0.0:
            return {name: 0.0 for name in raw}
        return {name: (value - lowest) / span for name, value in raw.items()}


def skeleton_schema(operation_names: Sequence[str]) -> dict[str, Any]:
    names = sorted(set(operation_names))
    if not names:
        raise PlannerContractError("la shortlist está vacía")
    return {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["clarify", "conversation", "plan"]},
            "question": {"type": "string", "maxLength": MAX_QUESTION_CHARS},
            "steps": {
                "type": "array",
                "maxItems": MAX_PLAN_STEPS,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "maxLength": 32},
                        "operation": {"type": "string", "enum": names},
                        "purpose": {"type": "string", "maxLength": MAX_PURPOSE_CHARS},
                        "dependsOn": {
                            "type": "array",
                            "maxItems": MAX_PLAN_STEPS - 1,
                            "items": {"type": "string", "maxLength": 32},
                        },
                        "argumentsMode": {
                            "type": "string",
                            "enum": ["after_dependencies", "literal"],
                        },
                    },
                    "required": [
                        "argumentsMode",
                        "dependsOn",
                        "id",
                        "operation",
                        "purpose",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["kind", "question", "steps"],
        "additionalProperties": False,
    }


def validate_skeleton(
    raw: Any,
    catalog: PlannerCatalog,
    shortlist: Sequence[PlannerTool],
    objective: str = "",
) -> PlanProposal:
    if not isinstance(raw, dict) or set(raw) != {"kind", "question", "steps"}:
        raise PlannerContractError("la propuesta no tiene la forma exacta")
    kind = raw.get("kind")
    question = raw.get("question")
    steps = raw.get("steps")
    if kind not in {"clarify", "conversation", "plan"}:
        raise PlannerContractError("kind no es canónico")
    if not isinstance(question, str) or len(question) > MAX_QUESTION_CHARS:
        raise PlannerContractError("question no es válida")
    question = _safe_text(question, "question", MAX_QUESTION_CHARS, allow_empty=True)
    if not isinstance(steps, list) or len(steps) > MAX_PLAN_STEPS:
        raise PlannerContractError("steps no es una lista acotada")
    if kind == "conversation":
        if steps:
            raise PlannerContractError("conversation no puede proponer pasos")
        return PlanProposal(kind, "", ())
    if kind == "clarify":
        if not question.strip() or steps:
            raise PlannerContractError(
                "clarify requiere una sola pregunta y cero pasos"
            )
        return PlanProposal(kind, question, ())
    if not steps:
        raise PlannerContractError("plan requiere pasos")

    allowed = {tool.name for tool in shortlist}
    parsed: list[ProposedStep] = []
    seen: set[str] = set()
    for index, raw_step in enumerate(steps):
        if not isinstance(raw_step, dict) or set(raw_step) != {
            "argumentsMode",
            "dependsOn",
            "id",
            "operation",
            "purpose",
        }:
            raise PlannerContractError(f"step {index} no tiene la forma exacta")
        step_id = raw_step.get("id")
        operation = raw_step.get("operation")
        purpose = raw_step.get("purpose")
        dependencies = raw_step.get("dependsOn")
        mode = raw_step.get("argumentsMode")
        if not isinstance(step_id, str) or _STEP_ID.fullmatch(step_id) is None:
            raise PlannerContractError(f"step {index} tiene id inválido")
        if step_id in seen:
            raise PlannerContractError("los step IDs deben ser únicos")
        if not isinstance(operation, str) or operation not in allowed:
            raise PlannerContractError(
                f"step {step_id} usa una operación fuera de shortlist"
            )
        tool = catalog.get(operation)
        if tool is None:
            raise PlannerContractError(f"step {step_id} usa una operación desconocida")
        purpose = _safe_text(purpose, "purpose", MAX_PURPOSE_CHARS)
        if (
            not isinstance(dependencies, list)
            or len(dependencies) > MAX_PLAN_STEPS - 1
            or any(
                not isinstance(value, str) or value not in seen
                for value in dependencies
            )
            or len(set(dependencies)) != len(dependencies)
        ):
            raise PlannerContractError(
                f"step {step_id} solo puede depender de pasos anteriores únicos"
            )
        if mode not in {"after_dependencies", "literal"}:
            raise PlannerContractError(f"step {step_id} tiene argumentsMode inválido")
        if mode == "after_dependencies" and not dependencies:
            raise PlannerContractError(
                f"step {step_id} no puede groundearse después sin dependencias"
            )
        parsed.append(
            ProposedStep(
                step_id,
                operation,
                purpose,
                tuple(dependencies),
                mode,
            )
        )
        seen.add(step_id)
    by_id = {step.step_id: step for step in parsed}
    positions = {step.step_id: index for index, step in enumerate(parsed)}
    note_creates = [step for step in parsed if step.operation == "note.create"]
    note_reads = [step for step in parsed if step.operation == "note.read"]
    requested_note_order = enumerated_note_dependency_order(objective)
    note_dependency_by_read: dict[str, str] = {}
    if (
        requested_note_order
        and len(note_creates) == len(requested_note_order)
        and len(note_reads) == len(requested_note_order)
    ):
        candidate_bindings = {
            read.step_id: note_creates[ordinal - 1].step_id
            for read, ordinal in zip(
                note_reads,
                requested_note_order,
                strict=True,
            )
        }
        if all(
            positions[producer] < positions[read]
            for read, producer in candidate_bindings.items()
        ):
            note_dependency_by_read = candidate_bindings
    normalized: list[ProposedStep] = []
    for index, step in enumerate(parsed):
        dependencies = step.depends_on
        mode = step.arguments_mode
        if step.step_id in note_dependency_by_read:
            requested_dependency = note_dependency_by_read[step.step_id]
            dependencies = tuple(
                dependency
                for dependency in dependencies
                if by_id[dependency].operation != "note.create"
            )
            dependencies = tuple(dict.fromkeys((*dependencies, requested_dependency)))
            mode = "after_dependencies"
        conditional = conditional_predecessors(step.operation, objective)
        if conditional and objective:
            if not any(
                by_id[dependency].operation in conditional
                for dependency in dependencies
            ):
                producer = next(
                    (
                        candidate
                        for candidate in reversed(parsed[:index])
                        if candidate.operation in conditional
                    ),
                    None,
                )
                if producer is not None:
                    dependencies = tuple(
                        dict.fromkeys((*dependencies, producer.step_id))
                    )
            if any(
                by_id[dependency].operation in conditional
                for dependency in dependencies
            ):
                mode = "after_dependencies"
        required_predecessors = _required_predecessors(step.operation)
        if not required_predecessors:
            normalized.append(
                ProposedStep(
                    step.step_id,
                    step.operation,
                    step.purpose,
                    dependencies,
                    mode,
                )
            )
            continue
        if not any(
            by_id[dependency].operation in required_predecessors
            for dependency in dependencies
        ):
            raise PlannerContractError(
                f"{step.operation} requiere uno de {required_predecessors} verificado"
            )
        normalized.append(
            ProposedStep(
                step.step_id,
                step.operation,
                step.purpose,
                dependencies,
                "after_dependencies",
            )
        )
    return PlanProposal("plan", "", tuple(normalized))


def attach_arguments(
    proposal: PlanProposal,
    arguments_by_step: dict[str, dict[str, Any]],
    catalog: PlannerCatalog,
) -> PlanProposal:
    if proposal.kind != "plan":
        return proposal
    steps: list[ProposedStep] = []
    for step in proposal.steps:
        arguments = arguments_by_step.get(step.step_id)
        if step.arguments_mode == "literal":
            tool = catalog.get(step.operation)
            if tool is None or not validate_json_schema_instance(
                arguments, tool.schema
            ):
                raise PlannerContractError(
                    f"los argumentos de {step.step_id} no cumplen el schema"
                )
        elif arguments is not None:
            raise PlannerContractError(
                f"{step.step_id} no puede materializar argumentos antes de observar dependencias"
            )
        steps.append(
            ProposedStep(
                step.step_id,
                step.operation,
                step.purpose,
                step.depends_on,
                step.arguments_mode,
                arguments,
            )
        )
    return PlanProposal("plan", "", tuple(steps))


def plan_structure_signature(proposal: PlanProposal) -> tuple[Any, ...]:
    """Compare reviewed plans without trusting cosmetic IDs or prose."""

    if proposal.kind != "plan":
        return (proposal.kind,)
    positions = {step.step_id: index for index, step in enumerate(proposal.steps)}
    return (
        "plan",
        *(
            (
                step.operation,
                tuple(positions[dependency] for dependency in step.depends_on),
                step.arguments_mode,
            )
            for step in proposal.steps
        ),
    )


def validate_json_schema_instance(value: Any, schema: dict[str, Any]) -> bool:
    """Valida el subconjunto cerrado publicado por ``ProductCatalog``."""

    if not isinstance(value, dict) or schema.get("type") != "object":
        return False
    properties = schema.get("properties")
    required = schema.get("required")
    if not isinstance(properties, dict) or not isinstance(required, list):
        return False
    if schema.get("additionalProperties") is not False:
        return False
    if any(key not in properties for key in value):
        return False
    if any(key not in value for key in required):
        return False
    return all(_validate_property(item, properties[key]) for key, item in value.items())


def _validate_property(value: Any, contract: Any) -> bool:
    if not isinstance(contract, dict):
        return False
    declared = contract.get("type")
    types = set(declared if isinstance(declared, list) else [declared])
    actual = _json_type(value)
    if actual not in types:
        return False
    enum = contract.get("enum")
    if isinstance(enum, list) and value not in enum:
        return False
    if (
        isinstance(value, bool)
        and "const" in contract
        and value is not contract["const"]
    ):
        return False
    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in contract and value < contract["minimum"]:
            return False
        if "maximum" in contract and value > contract["maximum"]:
            return False
    if isinstance(value, str):
        if "minLength" in contract and len(value) < contract["minLength"]:
            return False
        if "maxLength" in contract and len(value) > contract["maxLength"]:
            return False
        if (
            "x-maxUtf8Bytes" in contract
            and len(value.encode("utf-8")) > contract["x-maxUtf8Bytes"]
        ):
            return False
        if contract.get("x-nonWhitespace") is True and not value.strip():
            return False
        if _contains_unsafe_text(value):
            return False
    if isinstance(value, list):
        if "minItems" in contract and len(value) < contract["minItems"]:
            return False
        if "maxItems" in contract and len(value) > contract["maxItems"]:
            return False
        item_contract = contract.get("items")
        if not isinstance(item_contract, dict):
            return False
        if not all(_validate_property(item, item_contract) for item in value):
            return False
    if isinstance(value, dict):
        return validate_json_schema_instance(value, contract)
    return True


def validate_argument_grounding(
    arguments: dict[str, Any],
    schema: dict[str, Any],
    trusted_source: str,
) -> bool:
    """Exige evidencia textual para strings literales aportados por el modelo."""

    if not validate_json_schema_instance(arguments, schema):
        return False
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return False
    if (
        "byTitle" in properties
        and has_named_window_target(identity_text(trusted_source))
        and arguments.get("byTitle") is not True
    ):
        # Removing an optional selector must not silently turn a title into
        # a process name. Unlike a default limit, it changes target identity.
        return False
    for name, value in arguments.items():
        property_schema = properties.get(name)
        if not isinstance(property_schema, dict):
            return False
        if not _value_is_grounded(
            value,
            property_schema,
            trusted_source,
            property_name=name,
        ):
            return False
    return True


def normalize_grounded_arguments(
    arguments: dict[str, Any],
    schema: dict[str, Any],
    trusted_source: str,
) -> dict[str, Any] | None:
    """Drop invented optional defaults while preserving every required value.

    Providers own defaults for optional fields. A model-proposed optional value
    without textual evidence is removed instead of turning an otherwise valid
    plan into an error. Required values remain subject to the full grounding
    contract and are never synthesized or weakened.
    """

    if not isinstance(arguments, dict) or not isinstance(schema, dict):
        return None
    required = {value for value in schema.get("required", []) if isinstance(value, str)}
    candidate = dict(arguments)
    if validate_argument_grounding(candidate, schema, trusted_source):
        return candidate
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return None
    for name in tuple(candidate):
        property_schema = properties.get(name)
        if name not in required and (
            not isinstance(property_schema, dict)
            or not _validate_property(candidate[name], property_schema)
            or not _value_is_grounded(
                candidate[name], property_schema, trusted_source, property_name=name
            )
        ):
            candidate.pop(name)
    return (
        candidate
        if validate_argument_grounding(candidate, schema, trusted_source)
        else None
    )


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float) and math.isfinite(value):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "invalid"


def _safe_text(
    value: Any,
    label: str,
    maximum: int,
    *,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str) or len(value) > maximum:
        raise PlannerContractError(f"{label} no es texto acotado")
    if not allow_empty and not value.strip():
        raise PlannerContractError(f"{label} está vacío")
    if _contains_unsafe_text(value):
        raise PlannerContractError(f"{label} contiene caracteres de control")
    return value


def _contains_unsafe_text(value: str) -> bool:
    return any(
        ord(character) in _UNSAFE_FORMAT_CODEPOINTS or char_is_control(character)
        for character in value
    )


def char_is_control(character: str) -> bool:
    category = unicodedata.category(character)
    return category in {"Cc", "Cs"} and character not in {"\n", "\r", "\t"}


def _tokens(value: str) -> frozenset[str]:
    folded = unicodedata.normalize("NFKD", value.casefold())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return frozenset(re.findall(r"[a-z0-9]{2,}", folded))


def _grounding_tokens(value: str) -> frozenset[str]:
    """Tokenize literal evidence without restricting it to the Latin alphabet."""

    return frozenset(re.findall(r"[^\W_]+", identity_text(value), re.UNICODE))


def _tool_lexical_score(query: frozenset[str], tool: PlannerTool) -> float:
    candidate = _tokens(f"{tool.name} {tool.description}")
    if not candidate:
        return 0.0
    return len(query & candidate) / math.sqrt(len(candidate))


def _compact_schema_hint(schema: dict[str, Any]) -> str:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return "{}"
    hints: list[str] = []
    for name, raw in properties.items():
        if not isinstance(name, str) or not isinstance(raw, dict):
            continue
        if isinstance(raw.get("enum"), list):
            values = ",".join(str(value) for value in raw["enum"][:12])
            hints.append(f"{name}=enum({values})")
        elif "const" in raw:
            hints.append(f"{name}=const({raw['const']})")
        else:
            kind = raw.get("type", "value")
            if isinstance(kind, list):
                kind = "/".join(str(item) for item in kind)
            hints.append(f"{name}:{kind}")
    return "{" + ",".join(hints) + "}"


def _required_predecessors(operation: str) -> tuple[str, ...]:
    return {
        "app.close": ("window.resolve", "window.active"),
        "bluetooth.device.pair": ("bluetooth.device.list",),
        "filesystem.read.text": ("filesystem.search", "filesystem.list"),
        "game.install.commit": ("game.install.prepare",),
        "game.purchase.commit": ("game.purchase.prepare",),
        "message.send": ("message.recipient.resolve",),
        "notification.dismiss": ("notification.list.due",),
        "ocr.read": ("capture.screenshot", "capture.active.window"),
        "package.install.commit": ("package.install.prepare",),
        "peripheral.print": ("peripheral.list",),
        "peripheral.scan": ("peripheral.list",),
        "reminder.delete": ("reminder.resolve.exact",),
        "vision.describe": ("capture.screenshot",),
        "window.focus": ("window.resolve", "window.active"),
        "window.maximize": ("window.resolve", "window.active"),
        "window.minimize": ("window.resolve", "window.active"),
        "window.move": ("window.resolve", "window.active"),
        "window.resize": ("window.resolve", "window.active"),
        "window.restore": ("window.resolve", "window.active"),
        "window.snap": ("window.resolve", "window.active"),
        "wifi.connect": ("wifi.profile.list",),
    }.get(operation, ())


def required_predecessors(operation: str) -> tuple[str, ...]:
    """Return the closed prerequisite alternatives for one operation."""

    return _required_predecessors(operation)


def is_required_predecessor(operation: str, steps: Sequence[ProposedStep]) -> bool:
    return any(
        operation
        in (
            *_required_predecessors(step.operation),
            *_CONDITIONAL_IDENTITY_PREDECESSORS.get(step.operation, ()),
        )
        for step in steps
    )


def _value_is_grounded(
    value: Any,
    schema: dict[str, Any],
    source: str,
    *,
    property_name: str = "",
) -> bool:
    if value is None:
        declared_type = schema.get("type")
        null_only = declared_type == "null" or (
            isinstance(declared_type, list)
            and bool(declared_type)
            and set(declared_type) == {"null"}
        )
        return null_only or ("const" in schema and schema["const"] is None)
    if isinstance(value, bool):
        if "const" in schema:
            return value is schema["const"]
        if property_name == "byTitle":
            # A selector describes which identity the request supplies; it is
            # not an on/off effect requiring "enable" or "disable" vocabulary.
            return value is has_named_window_target(identity_text(source))
        tokens = _tokens(source)
        if property_name == "state" and tokens & _MICROPHONE_TOKENS:
            muted_signal = bool(tokens & _MICROPHONE_MUTED_CUES)
            active_signal = bool(tokens & _MICROPHONE_ACTIVE_CUES)
            return muted_signal != active_signal and value is muted_signal
        true_signal = bool(tokens & _TRUE_CUES)
        false_signal = bool(tokens & _FALSE_CUES)
        return true_signal != false_signal and value is true_signal
    if isinstance(value, (int, float)):
        return _number_is_grounded(value, source)
    if isinstance(value, list):
        item_schema = schema.get("items")
        return isinstance(item_schema, dict) and all(
            _value_is_grounded(item, item_schema, source) for item in value
        )
    if not isinstance(value, str):
        return False
    if "const" in schema:
        return value == schema["const"]
    enum = schema.get("enum")
    if isinstance(enum, list):
        aliases = _ENUM_EVIDENCE_ALIASES.get(value, (value,))
        source_key = identity_text(source)
        return any(identity_text(alias) in source_key for alias in aliases)
    if property_name == "appId":
        # Steam operation schemas cap AppIDs at 16 characters and require the
        # literal numeric identity. app.open deliberately accepts a Start-menu
        # display name up to 512 UTF-8 bytes; treating both schemas as Steam
        # IDs made valid requests such as "ouvre Steam" impossible to ground.
        if schema.get("maxLength") == 16:
            return bool(re.fullmatch(r"[1-9][0-9]{0,9}", value)) and value in source
        value_tokens = _tokens(value)
        source_tokens = _tokens(source)
        return bool(value_tokens) and value_tokens <= source_tokens
    if property_name in {"url", "resourceUri"}:
        return bool(re.fullmatch(r"https?://[^\s]+", value, re.IGNORECASE)) and (
            value.casefold() in source.casefold()
        )
    if property_name.endswith("Id"):
        return (
            _OPAQUE_ID.fullmatch(value) is not None
            and value.casefold() in source.casefold()
        )
    if (
        property_name == "relativePath"
        and value.lower().endswith(".txt")
        and re.search(r"\b(?:texto|text|txt)\b", identity_text(source)) is not None
    ):
        # FILES1705 «un archivo de texto»: the extension is what the words
        # «de texto» / «text file» mean; the name itself still grounds.
        value = value[:-4]
    value_key = identity_text(value)
    source_key = identity_text(source)
    if not value_key:
        return False
    if value_key in source_key:
        return True
    value_tokens = _grounding_tokens(value_key)
    source_tokens = _grounding_tokens(source_key)
    return bool(value_tokens) and value_tokens <= source_tokens


def _number_is_grounded(value: int | float, source: str) -> bool:
    source_key = identity_text(source)
    rendered = format(value, "g")
    if re.search(rf"(?<![0-9]){re.escape(rendered)}(?![0-9])", source_key):
        return True
    if isinstance(value, int):
        return any(
            re.search(rf"\b{re.escape(identity_text(alias))}\b", source_key)
            for alias in _NUMBER_ALIASES.get(value, ())
        )
    return False


def identity_text(value: str) -> str:
    # Historical corpora contain a small number of UTF-8 strings that were
    # decoded as Windows-1252/Latin-1 one or more times.  Repair only when the
    # round-trip is valid and removes common mojibake markers; correctly
    # decoded Unicode is left untouched.
    for _ in range(2):
        marker_count = sum(value.count(marker) for marker in ("Ã", "Â", "â", "ð"))
        if marker_count == 0:
            break
        repaired = None
        for legacy_encoding in ("cp1252", "latin-1"):
            try:
                repaired = value.encode(legacy_encoding).decode("utf-8")
                break
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        if repaired is None:
            break
        repaired_markers = sum(
            repaired.count(marker) for marker in ("Ã", "Â", "â", "ð")
        )
        if repaired_markers >= marker_count:
            break
        value = repaired
    folded = unicodedata.normalize("NFKD", value.casefold())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return " ".join(folded.split())


def _dependency_operations(names: set[str]) -> tuple[str, ...]:
    required: set[str] = set()
    independently_observable_windows = {
        "window.active",
        "window.application.status",
        "window.resolve",
    }
    if any(
        name.startswith("window.") and name not in independently_observable_windows
        for name in names
    ):
        required.add("window.resolve")
    if "app.close" in names:
        required.add("window.resolve")
    if "backup.create" in names:
        required.add("filesystem.list")
    if "filesystem.read.text" in names and not {"filesystem.search", "filesystem.list"} & names:
        required.add("filesystem.search")
    if any(name.endswith(".pair") for name in names):
        required.add("bluetooth.device.list")
    if "game.install.commit" in names:
        required.add("game.install.prepare")
    if "game.purchase.commit" in names:
        required.add("game.purchase.prepare")
    if "message.send" in names:
        required.add("message.recipient.resolve")
    if "package.install.commit" in names:
        required.add("package.install.prepare")
    if any(name in names for name in {"peripheral.print", "peripheral.scan"}):
        required.add("peripheral.list")
    if "wifi.connect" in names:
        required.add("wifi.profile.list")
    return tuple(sorted(required))
