"""Account for every frozen historical user mission without replaying noise.

The corpus was recovered from long-lived development conversations.  Some rows
are direct BAXY requests, while others are IDE context, build notifications,
implementation instructions, or non-target-language traces.  This audit keeps
all rows in the denominator and only exposes bounded, context-free runtime
requests to the no-effect planner gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from audit_planner_corpus import clean_candidate as base_clean_candidate


ROOT = Path(__file__).resolve().parents[1]
MISSIONS = ROOT / "tests/data/historical_missions.jsonl"
CATALOG = ROOT / "src/Baxy.Kernel/Operations/ProductCatalog.cs"
DEFAULT_OUT = ROOT / "artifacts/planner_recovery/historical_user_mission_audit.json"


META_CONTAMINATION = re.compile(
    r"(?:"
    r"<ide_|\[external unsupported block|%USERPROFILE%|[A-Z]:\\|"
    r"(?:^|[\\/])(?:src|tests?|scripts?|artifacts?|scratchpad)[\\/]|"
    r"\b(?:codex|claude|chatgpt|functiongemma|qwen|nemotron|gguf|"
    r"llama-server|fine-?tun(?:e|ing)?|encoder|qat|lora|vram|wasapi|aec|"
    r"pipeline|roadmap|dataset|benchmark|pytest|github|commit|branch|"
    r"router|planner|provider|adapter|schema|skill\.md|tool-use-id|"
    r"output-file|training|entrenamiento|arquitectura|implementaci[oó]n|"
    r"papers?|logs?|suite|pruebas?\s+(?:end.to.end|e2e)|gui|wake\s*word|"
    r"repo)\b|"
    r"\b(?:arregla|audita|revisa|investiga|diseña|desarrolla|programa)\b"
    r".{0,60}\b(?:baxy|sistema|c[oó]digo|app|programa|modelo|llm|wake|voz|tool)|"
    r"\b(?:sistema|app|programa|modelo|llm|wake\s*word)\b.{0,60}"
    r"\b(?:funciona|debe|falla|error|latencia|entrena|implementa|arregla|revisa)|"
    r"\b(?:me voy a dormir|mi pc es todo tuyo|permisos? totales?|conf[ií]o en ti|"
    r"presentar[eé] ma[nñ]ana|todo lo anterior|lo que te ped[ií] proteger|"
    r"qu[eé] tal sali[oó] todo|haz todo|sigue avanzando)\b|"
    r"\b(?:BAXY_[A-Z0-9_]+|context_size|keep_tail|tool_call\w*|"
    r"mission failed|unverified|paddleocr|full-screen|on-device|"
    r"bench|verifiers?|wire)\b|"
    r"\b(?:reply|traces?)\b.{0,80}\b(?:tool|mission|user|failed)|"
    r"^\s*(?:helper:|routine\.|ocr\s+paddleocr|cierre de Word pod[ií]a)|"
    r"\b(?:simplifica|resume) el texto anterior\b|"
    r"\ba cu[aá]l categor[ií]a pertenece\b|"
    r"\b(?:motor importa|pendiente de prueba|d[eé]jalo as[ií]|arreglalo)\b|"
    r"screenshot\s*\+|(?:^|\s)\*\*|\|\s*---|"
    r"(?:^|\n)\s*\d{1,2}[.)\t]\s+\S"
    r")",
    re.IGNORECASE | re.MULTILINE,
)


FAMILY_CUES = {
    "app": re.compile(
        r"\b(?:abre|abr[ií]|abrir|open|cierra|cerr[aá]|cerrar|close|"
        r"inicia|ejecuta|lanza|enfoca)\b",
        re.IGNORECASE,
    ),
    "audio": re.compile(
        r"\b(?:volumen|volume|silencia|mutea|mute|sonido|audio)\b",
        re.IGNORECASE,
    ),
    "backup": re.compile(
        r"\b(?:backup|respaldo|copia de seguridad|restaura(?:r|ci[oó]n)?)\b",
        re.IGNORECASE,
    ),
    "bluetooth": re.compile(r"\bbluetooth\b", re.IGNORECASE),
    "browser": re.compile(
        r"\b(?:navegador|browser|pesta[nñ]a|tab|url)\b|https?://|example\.com",
        re.IGNORECASE,
    ),
    "calendar": re.compile(
        r"\b(?:calendario|calendar|evento|reuni[oó]n|meeting|agenda)\b",
        re.IGNORECASE,
    ),
    "capture": re.compile(
        r"\b(?:captura|screenshot|pantallazo)\b", re.IGNORECASE
    ),
    "clipboard": re.compile(
        r"\b(?:portapapeles|clipboard|copia y pega|copiar y pegar)\b",
        re.IGNORECASE,
    ),
    "filesystem": re.compile(
        r"\b(?:archivo|carpeta|directorio|file|folder|descargas|documentos|"
        r"escritorio|disco [a-z]|renombra|mueve el archivo|busca archivo)\b",
        re.IGNORECASE,
    ),
    "game": re.compile(
        r"\b(?:steam|juego|game|biblioteca|library|portal|batman|"
        r"mortal kombat|marvel rivals)\b",
        re.IGNORECASE,
    ),
    "media": re.compile(
        r"\b(?:m[uú]sica|canci[oó]n|playlist|spotify|reproduce|pon|toca|"
        r"play|pausa|siguiente|sonando)\b",
        re.IGNORECASE,
    ),
    "message": re.compile(
        r"\b(?:whatsapp|discord|mensaje|message|env[ií]a(?:le)?|manda(?:le)?|"
        r"escr[ií]bele|dile|decile)\b",
        re.IGNORECASE,
    ),
    "note": re.compile(r"\b(?:nota|note|anota)\b", re.IGNORECASE),
    "notification": re.compile(
        r"\b(?:alarma|timer|temporizador|notificaci[oó]n|no molestar)\b",
        re.IGNORECASE,
    ),
    "office": re.compile(
        r"\b(?:word|excel|powerpoint|documento|hoja de c[aá]lculo|tabla|"
        r"google docs)\b",
        re.IGNORECASE,
    ),
    "ocr": re.compile(r"\bocr\b|\blee el texto\b", re.IGNORECASE),
    "package": re.compile(
        r"\b(?:instala|instalar|desinstala|actualiza)\b", re.IGNORECASE
    ),
    "peripheral": re.compile(
        r"\b(?:impresora|printer|esc[aá]ner|scanner|micr[oó]fono|c[aá]mara)\b",
        re.IGNORECASE,
    ),
    "reminder": re.compile(
        r"\b(?:recu[eé]rdame|recordatorio|remind me)\b", re.IGNORECASE
    ),
    "routine": re.compile(
        r"\b(?:rutina|routine|todos los d[ií]as|cada d[ií]a|se repita|recurrente)\b",
        re.IGNORECASE,
    ),
    "streaming": re.compile(
        r"\b(?:youtube|netflix|disney\+?|prime video|pel[ií]cula|serie|"
        r"streaming|video)\b",
        re.IGNORECASE,
    ),
    "system": re.compile(
        r"\b(?:ram|cpu|gpu|bater[ií]a|qu[eé] hora|dame la hora|windows|"
        r"brillo|reinicia|apaga|estado (?:del|de mi) (?:pc|equipo)|procesos?)\b",
        re.IGNORECASE,
    ),
    "task": re.compile(r"\b(?:tarea|task|to-?do|pendiente)\b", re.IGNORECASE),
    "vision": re.compile(
        r"\b(?:qu[eé] (?:hay|ves) en (?:mi |la )?pantalla|describe (?:mi |la )?"
        r"pantalla|describe (?:la )?imagen|mira (?:mi |la )?pantalla)\b",
        re.IGNORECASE,
    ),
    "web": re.compile(
        r"\b(?:busca|buscar|search|google|internet|web|noticias|clima|"
        r"precio|vuelos?)\b",
        re.IGNORECASE,
    ),
    "wifi": re.compile(r"\b(?:wi-?fi|red inal[aá]mbrica)\b", re.IGNORECASE),
    "window": re.compile(
        r"\b(?:ventana|window|minimiza|maximiza|mueve la ventana|"
        r"ventana activa|cambia de ventana)\b",
        re.IGNORECASE,
    ),
}

DIRECT_REQUEST = re.compile(
    r"^\s*(?:baxy[,:]?\s*)?(?:por favor\s+|podr[ií]as?\s+)?"
    r"(?:abre|abr[ií]|cierra|cerr[aá]|pon|reproduce|pausa|sube|baja|"
    r"silencia|busca|lee|describe|crea|anota|env[ií]a|manda|escribe|"
    r"dime|cu[aá]nt[oa]|qu[eé]|quiero|necesito|entra|ve|mueve|minimiza|"
    r"maximiza|conecta|activa|desactiva|instala|lanza|ejecuta|recordame|"
    r"recu[eé]rdame|open|close|play|search|send|create)\b",
    re.IGNORECASE,
)


def detected_families(value: str) -> set[str]:
    return {family for family, cue in FAMILY_CUES.items() if cue.search(value)}


def clean_runtime_candidate(value: str) -> bool:
    value = value.strip()
    return (
        base_clean_candidate(value)
        and value.count("\n") <= 2
        and value.count("`") < 2
        and "→" not in value
        and META_CONTAMINATION.search(value) is None
        and bool(detected_families(value))
    )


def representative(candidates: list[str], expected: set[str]) -> str:
    def score(value: str) -> tuple[float, int, int, int, int]:
        detected = detected_families(value)
        covered = detected & expected
        ratio = len(covered) / max(1, len(expected))
        return (
            ratio,
            len(covered),
            int(bool(DIRECT_REQUEST.search(value))),
            -len(detected - expected),
            -len(value),
        )

    return max(candidates, key=score)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    source_bytes = MISSIONS.read_bytes()
    rows = [
        json.loads(line)
        for line in source_bytes.decode("utf-8").splitlines()
        if line.strip()
    ]
    user_missions = [row for row in rows if row.get("class") == "user_mission"]
    catalog_names = set(
        re.findall(
            r'Descriptor\(\s*"([a-z0-9.]+)"',
            CATALOG.read_text(encoding="utf-8"),
        )
    )
    catalog_families = {name.split(".", 1)[0] for name in catalog_names}

    audited = []
    for row in user_missions:
        operations = tuple(row.get("operations") or ())
        historical_operations = tuple(row.get("historical_operations") or ())
        expected_families = {
            operation.split(".", 1)[0]
            for operation in operations
            if not operation.startswith("memory.")
        }
        candidates = [
            example.strip()
            for example in row.get("examples") or []
            if clean_runtime_candidate(example)
        ]

        if (
            row.get("acceptance_scope") == "trace_only_not_acceptance_commitment"
            or not operations
        ):
            classification = "trace_only"
            reason = "provenance-only row outside the product acceptance commitment"
            chosen = None
        elif any(operation.startswith("memory.") for operation in operations):
            classification = "private_boundary"
            reason = "memory input must remain outside the public model planner"
            chosen = None
        elif candidates:
            classification = "natural_evaluable"
            reason = "bounded context-free runtime request with an observable intent cue"
            chosen = representative(candidates, expected_families)
        else:
            classification = "contaminated_trace"
            reason = "only development context, dependent follow-up, logs, or oversized prose"
            chosen = None

        observed_families = detected_families(chosen) if chosen else set()
        represented = observed_families & expected_families
        audited.append(
            {
                "mission_id": row["canonical_mission_id"],
                "acceptance_scope": row.get("acceptance_scope"),
                "classification": classification,
                "reason": reason,
                "representative_objective": chosen,
                "representative_detected_families": sorted(observed_families),
                "represented_historical_families": sorted(represented),
                "unrepresented_historical_families": sorted(
                    expected_families - represented
                ),
                "historical_operations": list(historical_operations),
                "current_operations": list(operations),
                "operation_count": len(operations),
                "missing_public_families": sorted(
                    family
                    for family in expected_families
                    if family not in catalog_families
                ),
            }
        )

    counts = Counter(item["classification"] for item in audited)
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(MISSIONS.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "policy": {
            "natural_evaluable": "may enter the no-effect planner evaluation",
            "contaminated_trace": "counted for coverage but never replayed as a request",
            "private_boundary": "tested before the public planner; private text is not replayed",
            "trace_only": "preserved provenance outside the product acceptance commitment",
        },
        "summary": {
            "all_historical_user_missions": len(user_missions),
            "product_acceptance_rows": sum(
                row.get("acceptance_scope") == "product_1_0"
                for row in user_missions
            ),
            "trace_only_rows": sum(
                row.get("acceptance_scope")
                == "trace_only_not_acceptance_commitment"
                for row in user_missions
            ),
            "classification_counts": dict(sorted(counts.items())),
            "missions_missing_public_family": sum(
                bool(item["missing_public_families"]) for item in audited
            ),
            "all_accounted_once": len(audited)
            == len({item["mission_id"] for item in audited}),
            "tools_executed": 0,
        },
        "missions": audited,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
