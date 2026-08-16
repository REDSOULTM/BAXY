"""Probe real LLM dependency grounding without dispatching any operation.

Every row configures the authenticated Core catalogue and sends only a
``plan.ground`` request with synthetic, explicitly verified observations. The
probe never sends a plan to App or an operation to Core/provider. It measures
whether opaque identities and remaining literals are materialized from the
user objective plus the permitted producer result, without invented authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
for path in (REPO, REPO / "src", REPO / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.baxy_runtime_config import (  # noqa: E402
    DEFAULT_RUNTIME_MANIFEST,
    file_sha256,
    public_runtime_identity,
    resolve_runtime,
)
from scripts.measure_mind_budget import (  # noqa: E402
    DEFAULT_CORE_CANDIDATES,
    JsonLineProcess,
    PROFILE_LIMITS,
    current_core_catalog_snapshot,
    discover_core,
    sidecar_environment,
    write_json_atomic,
)


OUTPUT = REPO / "artifacts/fixes/dependency_grounding_matrix_r1.json"


def observation(operation: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "stepId": "producer",
        "operation": operation,
        "verified": True,
        "status": "completed",
        "result": result,
    }


def build_cases() -> list[dict[str, Any]]:
    window_id = "window_0123456789abcdef0123456789ab"
    capture_id = "capture_matrix_01"
    return [
        {
            "case_id": "window-close",
            "operation": "app.close",
            "producer": "window.resolve",
            "objective": "Cierra la ventana de Notepad que acabas de resolver.",
            "purpose": "Cerrar la ventana verificada.",
            "observations": [observation(
                "window.resolve",
                {"windows": [{"windowId": window_id}]},
            )],
            "expected": {"windowId": window_id},
        },
        {
            "case_id": "bluetooth-pair",
            "operation": "bluetooth.device.pair",
            "producer": "bluetooth.device.list",
            "objective": "Empareja el dispositivo Bluetooth llamado BAXY Keyboard.",
            "purpose": "Emparejar el teclado verificado.",
            "observations": [observation(
                "bluetooth.device.list",
                {
                    "devices": [
                        {"deviceId": "bt_keyboard", "name": "BAXY Keyboard", "canPair": True},
                        {"deviceId": "bt_speaker", "name": "BAXY Speaker", "canPair": True},
                    ],
                },
            )],
            "expected": {"deviceId": "bt_keyboard"},
        },
        {
            "case_id": "browser-search-result",
            "operation": "browser.navigate",
            "producer": "web.search",
            "objective": "Navega al resultado verificado de la búsqueda.",
            "purpose": "Abrir el resultado verificado.",
            "observations": [observation(
                "web.search",
                {"results": [{"url": "https://example.com/verified"}]},
            )],
            "expected": {"url": "https://example.com/verified"},
        },
        {
            "case_id": "browser-named-search-result",
            "operation": "browser.navigate.named",
            "producer": "web.search",
            "objective": "Navega Opera al resultado verificado de la búsqueda.",
            "purpose": "Abrir el resultado verificado en Opera.",
            "observations": [observation(
                "web.search",
                {"results": [{"url": "https://example.com/opera"}]},
            )],
            "expected": {"browser": "opera", "url": "https://example.com/opera"},
        },
        {
            "case_id": "game-install-commit",
            "operation": "game.install.commit",
            "producer": "game.install.prepare",
            "objective": "Confirma la instalación de juego que acaba de prepararse.",
            "purpose": "Consumir la confirmación verificada.",
            "observations": [observation(
                "game.install.prepare",
                {"confirmationId": "game_install_confirmation_01"},
            )],
            "expected": {"confirmationId": "game_install_confirmation_01"},
        },
        {
            "case_id": "game-purchase-commit",
            "operation": "game.purchase.commit",
            "producer": "game.purchase.prepare",
            "objective": "Confirma la compra preparada exactamente por 1299 centavos.",
            "purpose": "Consumir precio y confirmación verificados.",
            "observations": [observation(
                "game.purchase.prepare",
                {
                    "confirmationId": "game_purchase_confirmation_01",
                    "expectedPriceCents": 1299,
                },
            )],
            "expected": {
                "confirmationId": "game_purchase_confirmation_01",
                "expectedPriceCents": 1299,
            },
        },
        {
            "case_id": "message-recipient",
            "operation": "message.send",
            "producer": "message.recipient.resolve",
            "objective": 'Envía a Ana el texto exacto "hola matriz".',
            "purpose": "Enviar el texto al destinatario verificado.",
            "observations": [observation(
                "message.recipient.resolve",
                {"recipientId": "recipient_ana_01"},
            )],
            "expected": {"recipientId": "recipient_ana_01", "text": "hola matriz"},
        },
        {
            "case_id": "note-created-read",
            "operation": "note.read",
            "producer": "note.create",
            "objective": "Lee la misma nota que acabas de crear.",
            "purpose": "Leer la nota verificada.",
            "observations": [observation("note.create", {"noteId": "note_matrix_01"})],
            "expected": {"noteId": "note_matrix_01"},
            "allowed_extra": (
                "expectedIsTrashed",
                "expectedRevision",
                "expectedTitle",
                "title",
            ),
        },
        {
            "case_id": "notification-dismiss",
            "operation": "notification.dismiss",
            "producer": "notification.list.due",
            "objective": "Descarta el único recordatorio vencido verificado.",
            "purpose": "Descartar el recordatorio verificado.",
            "observations": [observation(
                "notification.list.due",
                {"reminders": [{"reminderId": "reminder_due_01", "version": 7}]},
            )],
            "expected": {"reminderId": "reminder_due_01", "expectedVersion": 7},
        },
        {
            "case_id": "capture-ocr",
            "operation": "ocr.read",
            "producer": "capture.screenshot",
            "objective": "Lee con OCR la captura verificada usando el idioma literal es.",
            "purpose": "Leer la captura en el idioma pedido.",
            "observations": [observation("capture.screenshot", {"captureId": capture_id})],
            "expected": {"captureId": capture_id, "language": "es"},
        },
        {
            "case_id": "office-created-read",
            "operation": "office.document.read",
            "producer": "office.document.create",
            "objective": "Lee el mismo documento de Office que acabas de crear.",
            "purpose": "Leer el documento verificado.",
            "observations": [observation(
                "office.document.create",
                {"documentId": "document_matrix_01"},
            )],
            "expected": {"documentId": "document_matrix_01"},
        },
        {
            "case_id": "package-install-commit",
            "operation": "package.install.commit",
            "producer": "package.install.prepare",
            "objective": "Confirma la instalación de paquete que acaba de prepararse.",
            "purpose": "Consumir la confirmación verificada.",
            "observations": [observation(
                "package.install.prepare",
                {"confirmationId": "package_confirmation_01"},
            )],
            "expected": {"confirmationId": "package_confirmation_01"},
        },
        {
            "case_id": "peripheral-scan",
            "operation": "peripheral.scan",
            "producer": "peripheral.list",
            "objective": "Escanea usando el periférico llamado BAXY Scanner.",
            "purpose": "Usar el escáner verificado.",
            "observations": [observation(
                "peripheral.list",
                {
                    "devices": [
                        {"deviceId": "scanner_device_01", "name": "BAXY Scanner", "kind": "scanner"},
                        {"deviceId": "printer_device_01", "name": "BAXY Printer", "kind": "printer"},
                    ],
                },
            )],
            "expected": {"deviceId": "scanner_device_01"},
        },
        {
            "case_id": "peripheral-print",
            "operation": "peripheral.print",
            "producer": "peripheral.list",
            "objective": (
                "Imprime el documento con ID literal document_matrix_01 usando el "
                "periférico llamado BAXY Printer."
            ),
            "purpose": "Imprimir el documento literal en la impresora verificada.",
            "observations": [observation(
                "peripheral.list",
                {
                    "devices": [
                        {"deviceId": "printer_device_01", "name": "BAXY Printer", "kind": "printer"},
                        {"deviceId": "scanner_device_01", "name": "BAXY Scanner", "kind": "scanner"},
                    ],
                },
            )],
            "expected": {
                "deviceId": "printer_device_01",
                "documentId": "document_matrix_01",
            },
        },
        {
            "case_id": "reminder-delete",
            "operation": "reminder.delete",
            "producer": "reminder.resolve.exact",
            "objective": "Elimina el recordatorio exacto Entrega que acabas de resolver.",
            "purpose": "Eliminar el recordatorio verificado.",
            "observations": [observation(
                "reminder.resolve.exact",
                {
                    "reminderId": "reminder_exact_01",
                    "expectedVersion": 11,
                    "reviewLabel": "Entrega",
                },
            )],
            "expected": {
                "reminderId": "reminder_exact_01",
                "expectedVersion": 11,
                "reviewLabel": "Entrega",
            },
        },
        {
            "case_id": "capture-vision",
            "operation": "vision.describe",
            "producer": "capture.screenshot",
            "objective": 'Describe la captura verificada con el prompt exacto "solo iconos".',
            "purpose": "Describir la captura con el prompt pedido.",
            "observations": [observation("capture.screenshot", {"captureId": capture_id})],
            "expected": {"captureId": capture_id, "prompt": "solo iconos"},
        },
        {
            "case_id": "wifi-profile",
            "operation": "wifi.connect",
            "producer": "wifi.profile.list",
            "objective": "Conecta el perfil Wi-Fi llamado Home Lab.",
            "purpose": "Conectar el perfil verificado.",
            "observations": [observation(
                "wifi.profile.list",
                {
                    "profiles": [
                        {"profileId": "wifi_profile_home", "label": "Home Lab"},
                        {"profileId": "wifi_profile_guest", "label": "Guest"},
                    ],
                },
            )],
            "expected": {"profileId": "wifi_profile_home"},
        },
        {
            "case_id": "window-move",
            "operation": "window.move",
            "producer": "window.resolve",
            "objective": "Mueve la ventana resuelta a x 120 e y 240.",
            "purpose": "Mover la ventana a las coordenadas literales.",
            "observations": [observation(
                "window.resolve",
                {"windows": [{"windowId": window_id}]},
            )],
            "expected": {"windowId": window_id, "x": 120, "y": 240},
        },
        {
            "case_id": "window-resize",
            "operation": "window.resize",
            "producer": "window.resolve",
            "objective": "Redimensiona la ventana resuelta a ancho 1280 y alto 720.",
            "purpose": "Aplicar el tamaño literal a la ventana verificada.",
            "observations": [observation(
                "window.resolve",
                {"windows": [{"windowId": window_id}]},
            )],
            "expected": {"height": 720, "width": 1280, "windowId": window_id},
        },
    ]


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _arguments_match(case: dict[str, Any], arguments: object) -> bool:
    if not isinstance(arguments, dict):
        return False
    expected = case["expected"]
    if any(arguments.get(key) != value for key, value in expected.items()):
        return False
    allowed = set(expected) | set(case.get("allowed_extra", set()))
    return set(arguments) <= allowed


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists():
        raise RuntimeError("refusing to overwrite an existing grounding artifact")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    runtime = resolve_runtime(manifest_path=args.runtime_manifest)
    manifest_before = file_sha256(args.runtime_manifest)
    capabilities, application_catalog, game_catalog = current_core_catalog_snapshot(
        discover_core(None, candidates=reversed(DEFAULT_CORE_CANDIDATES))
    )
    available = {str(item["name"]) for item in capabilities}
    cases = build_cases()
    required = {
        str(case[key])
        for case in cases
        for key in ("operation", "producer")
    }
    if not required <= available:
        raise RuntimeError(f"authenticated catalogue lacks {sorted(required - available)}")

    limits = PROFILE_LIMITS["gpu"]
    grounding_timeout = 35.0
    environment = sidecar_environment(
        runtime,
        gpu_layers=runtime.gpu_layers,
        llm_http_timeout=limits["llm_http"],
    )
    client = JsonLineProcess(
        [str(runtime.python), "-u", "-X", "utf8", "-m", "baxy_mind"],
        environment=environment,
        cwd=REPO,
    )
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    try:
        hello = client.next_message(limits["handshake"])
        if hello.get("type") != "hello":
            raise RuntimeError("sidecar rejected its handshake")
        ready = client.request(
            {
                "type": "catalog.configure",
                "id": "grounding-catalog",
                "capabilities": capabilities,
                "applicationCatalog": application_catalog,
                "gameCatalog": game_catalog,
            },
            limits["handshake"],
        )
        if ready.get("type") != "catalog.ready":
            raise RuntimeError("sidecar rejected the authenticated catalogue")
        for case in cases:
            before = time.perf_counter()
            reply = client.request(
                {
                    "type": "plan.ground",
                    "id": f"ground-{case['case_id']}",
                    "objective": case["objective"],
                    "operation": case["operation"],
                    "purpose": case["purpose"],
                    "observations": case["observations"],
                },
                grounding_timeout,
            )
            arguments = reply.get("arguments")
            exact = (
                reply.get("type") == "plan.ground.result"
                and reply.get("operation") == case["operation"]
                and _arguments_match(case, arguments)
            )
            rows.append(
                {
                    **case,
                    "response_type": reply.get("type"),
                    "response_code": reply.get("code"),
                    "arguments": arguments,
                    "seconds": round(time.perf_counter() - before, 6),
                    "exact": exact,
                }
            )
    finally:
        client.close(
            graceful_message={"type": "shutdown", "id": "grounding-shutdown"},
            timeout=limits["shutdown"],
        )

    latencies = [float(row["seconds"]) for row in rows]
    report = {
        "schema": "baxy.dependency-grounding-matrix.v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "real_llm_plan_ground_only_synthetic_verified_observations",
        "authority": "no_plan_no_core_request_no_provider_no_effect",
        "runtime": public_runtime_identity(runtime),
        "effects_executed": 0,
        "total_seconds": round(time.perf_counter() - started, 3),
        "metrics": {
            "exact": sum(bool(row["exact"]) for row in rows),
            "total": len(rows),
            "exact_accuracy": sum(bool(row["exact"]) for row in rows) / len(rows),
            "seconds_p50": statistics.median(latencies),
            "seconds_p95": _p95(latencies),
        },
        "acceptance": {
            "all_exact": all(bool(row["exact"]) for row in rows),
            "runtime_manifest_unchanged": (
                manifest_before == file_sha256(args.runtime_manifest)
            ),
            "zero_effects": True,
        },
        "source": {
            "probe_sha256": _sha256(Path(__file__).resolve()),
        },
        "rows": rows,
    }
    write_json_atomic(args.output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-manifest",
        type=Path,
        default=DEFAULT_RUNTIME_MANIFEST,
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = run(args)
    print(json.dumps({
        "metrics": report["metrics"],
        "acceptance": report["acceptance"],
        "failures": [
            {
                "case_id": row["case_id"],
                "response_type": row["response_type"],
                "response_code": row["response_code"],
                "arguments": row["arguments"],
            }
            for row in report["rows"]
            if not row["exact"]
        ],
        "effects_executed": report["effects_executed"],
    }, ensure_ascii=False, indent=2))
    return 0 if all(report["acceptance"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
