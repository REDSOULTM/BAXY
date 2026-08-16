from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_historical_corpus import (
    Collector,
    acceptance_scope_key,
    build_acceptance_scope_oracle,
    canonical_digest,
    classify,
    consolidate_derived_occurrences,
    disambiguate_operation_candidates,
    extract_codex,
    frozen_source_text,
    normalize,
    operation_names,
    markdown_sources,
    mission_signature,
    redact,
    resolve_operation_polarity,
    risk_policy,
    validate_manifest_payload,
    _FROZEN_OPERATION_OVERRIDES,
    _verified_live_bytes,
)


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def digest_sorted_lines(values: list[str] | set[str]) -> str:
    payload = "".join(f"{value}\n" for value in sorted(values))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def codex_event_line(timestamp: str, text: str) -> bytes:
    event = {
        "timestamp": timestamp,
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
        },
    }
    return (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")


def codex_prefix_manifest(*, line_count: int, byte_count: int, sha256: str) -> dict:
    return {
        "sources": [
            {"id": "codex_relevant_root_threads", "records": []},
            {
                "id": "current_codex_thread_prefix",
                "thread_id": "fixture-session",
                "line_count": line_count,
                "bytes": byte_count,
                "sha256": sha256,
            },
        ]
    }


class HistoricalCorpusUnitTests(unittest.TestCase):
    def test_normalize_removes_wake_word_and_accents(self) -> None:
        self.assertEqual(normalize("Baxy, pon MÚSICA!"), "pon musica")

    def test_redaction_covers_windows_paths_and_credentials(self) -> None:
        text, changed = redact(
            r"C:\Users\alice\file.txt c:/Users/alice/file.txt password=hunter2 a@b.com"
        )
        self.assertTrue(changed)
        self.assertNotIn("alice", text)
        self.assertNotIn("hunter2", text)
        self.assertNotIn("a@b.com", text)

    def test_compound_steam_spotify_uses_composable_operations(self) -> None:
        operations = operation_names(
            "Instálame Batman Arkham Knight en Steam y pon una canción en Spotify"
        )
        self.assertIn("game.install", operations)
        self.assertIn("media.play", operations)

    def test_direct_effect_denials_have_no_actionable_operation(self) -> None:
        cases = {
            "no subas el volumen": {"audio.volume"},
            "no cierres spotify": {"app.close"},
            "don't open chrome": {"app.open", "browser.navigate"},
            "don’t open chrome": {"app.open", "browser.navigate"},
            "no bajes el brillo": {"system.settings"},
            "no pongas música": {"media.play"},
            "no abras juegos pesados durante suite mínima": {"game.launch"},
            "solo responde, no uses herramientas: abre Steam": {"app.open"},
            "stop, don't do it": set(),
        }
        for text, denied in cases.items():
            with self.subTest(text=text):
                polarity = resolve_operation_polarity(text)
                self.assertEqual(polarity.actionable_operations, ())
                self.assertEqual(set(polarity.denied_operations), denied)
                self.assertEqual(polarity.kind, "no_action")

    def test_partial_denials_keep_only_authorized_operations(self) -> None:
        cases = {
            "abre YouTube, busca música lofi y no reproduzcas nada": (
                {"browser.navigate", "streaming.navigate", "web.search"},
                {"media.play"},
            ),
            "abre Steam pero no maximices ni lances juegos": (
                {"app.open"},
                {"game.launch", "window.manage"},
            ),
            "open Steam but do not launch any game": (
                {"app.open"},
                {"game.launch"},
            ),
            "abre Steam Store de Batman en navegador, no app": (
                {"browser.navigate"},
                {"app.open", "game.launch", "game.manage"},
            ),
            "Dejalo asi, no toques streaming, en la imagen habian mas probelmas arreglalo": (
                {"vision.describe"},
                {"streaming.navigate"},
            ),
            "si la RAM está alta no cargues visión": (
                {"system.status"},
                {"vision.describe"},
            ),
        }
        for text, (actionable, denied) in cases.items():
            with self.subTest(text=text):
                polarity = resolve_operation_polarity(text)
                self.assertEqual(set(polarity.actionable_operations), actionable)
                self.assertEqual(set(polarity.denied_operations), denied)
                self.assertEqual(polarity.kind, "partial")

    def test_polarity_rules_do_not_consume_unrelated_negation(self) -> None:
        cases = (
            "no me molesta, poné música",
            "open Steam but don't say it's done if you can't verify it",
            "recuerda que prefiero no usar taskkill /F",
            "resume log largo sin cargar todo si no hace falta",
            "no, mejor abrí Firefox",
            "No solo abre la app; verifica la ventana",
            "No olvides mi preferencia",
            "Documento de producto: no debe prometer launch; ejemplo: abre Steam",
            "Session summary: never launch a game unless the user asks",
        )
        for text in cases:
            with self.subTest(text=text):
                polarity = resolve_operation_polarity(text)
                expected = disambiguate_operation_candidates(
                    text, operation_names(text)
                )
                self.assertEqual(list(polarity.actionable_operations), expected)
                self.assertEqual(polarity.denied_operations, ())

    def test_volume_assignment_is_not_media_playback(self) -> None:
        pure_volume = resolve_operation_polarity("no, mejor pon el volumen a 30")
        self.assertEqual(pure_volume.actionable_operations, ("audio.volume",))
        self.assertEqual(pure_volume.denied_operations, ())

        compound = resolve_operation_polarity(
            "abre Spotify, pon rock y baja el volumen"
        )
        self.assertIn("audio.volume", compound.actionable_operations)
        self.assertIn("media.play", compound.actionable_operations)

        for text in (
            "set volume to 20 and play a podcast",
            "pon el volumen a 30 y reproduce un video",
        ):
            with self.subTest(text=text):
                resolved = resolve_operation_polarity(text)
                self.assertIn("audio.volume", resolved.actionable_operations)
                self.assertIn("media.play", resolved.actionable_operations)

    def test_opening_steam_is_not_launching_a_game(self) -> None:
        steam = resolve_operation_polarity("abre Steam")
        self.assertEqual(steam.actionable_operations, ("app.open",))

        direct_game = resolve_operation_polarity("Abre Portal desde Steam")
        self.assertEqual(direct_game.actionable_operations, ("game.launch",))

        chained_game = resolve_operation_polarity(
            "Abre Steam y ejecuta el juego instalado Portal"
        )
        self.assertIn("app.open", chained_game.actionable_operations)
        self.assertIn("game.launch", chained_game.actionable_operations)

        for text in (
            "abre Steam y ejecuta Portal",
            "abre Steam y juega Portal",
            "abre Steam y lanza Portal",
        ):
            with self.subTest(text=text):
                resolved = resolve_operation_polarity(text)
                self.assertIn("app.open", resolved.actionable_operations)
                self.assertIn("game.launch", resolved.actionable_operations)

        denied_game = resolve_operation_polarity(
            "open Steam but do not launch any game"
        )
        self.assertEqual(denied_game.actionable_operations, ("app.open",))
        self.assertEqual(denied_game.denied_operations, ("game.launch",))

        store = resolve_operation_polarity("abre Steam store en navegador")
        self.assertEqual(store.actionable_operations, ("browser.navigate",))

        store_page = resolve_operation_polarity(
            "abre la página de tienda de un juego, no compres nada"
        )
        self.assertEqual(store_page.actionable_operations, ("browser.navigate",))

        properties = resolve_operation_polarity(
            "abre propiedades de un juego solo si está seleccionado"
        )
        self.assertEqual(properties.actionable_operations, ("game.manage",))

        epic = resolve_operation_polarity("Abre Epic Games Launcher")
        self.assertEqual(epic.actionable_operations, ("app.open",))

        last_game = resolve_operation_polarity("abre el último juego que jugué")
        self.assertEqual(last_game.actionable_operations, ("game.launch",))

    def test_game_management_is_distinct_from_web_install_and_launch(self) -> None:
        cases = {
            "Abre mi biblioteca de Steam": {"game.manage"},
            "Abre Steam y ve a biblioteca": {"app.open", "game.manage"},
            "busca Batman en Steam": {"game.manage"},
            "Abre Epic Games y busca Rocket League": {
                "app.open",
                "game.manage",
            },
            "abre Steam, busca el juego y empieza la descarga": {
                "app.open",
                "game.install",
                "game.manage",
            },
            "abre la página de Steam de Marvel Rivals": {"browser.navigate"},
            "Busca el App ID de Doom Eternal en Steam usando la API publica": {
                "web.search"
            },
            "busca juegos de Batman para comprar": {"game.manage"},
            "compra Portal en Steam": {"game.purchase"},
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                resolved = resolve_operation_polarity(text)
                self.assertEqual(set(resolved.actionable_operations), expected)

        no_launch = resolve_operation_polarity(
            "busca Hades en mi biblioteca, no lo ejecutes"
        )
        self.assertEqual(no_launch.actionable_operations, ("game.manage",))
        self.assertEqual(no_launch.denied_operations, ("game.launch",))
        self.assertEqual(no_launch.kind, "partial")

        no_purchase = resolve_operation_polarity(
            "si Batman no está en biblioteca, dime eso sin comprar nada"
        )
        self.assertEqual(no_purchase.actionable_operations, ("game.manage",))
        self.assertEqual(no_purchase.denied_operations, ("game.purchase",))
        self.assertEqual(
            risk_policy(
                "si Batman no está en biblioteca, dime eso sin comprar nada",
                list(no_purchase.actionable_operations),
            )["confirmation"],
            "not_required",
        )

    def test_frozen_operation_override_oracle_has_no_silent_scope_growth(self) -> None:
        self.assertEqual(len(_FROZEN_OPERATION_OVERRIDES), 178)
        by_contract: dict[tuple[str, ...], int] = {}
        for operations in _FROZEN_OPERATION_OVERRIDES.values():
            key = tuple(sorted(operations))
            by_contract[key] = by_contract.get(key, 0) + 1
        self.assertEqual(
            by_contract,
            {
                (): 1,
                ("app.open",): 2,
                ("audio.status",): 4,
                ("browser.navigate",): 6,
                ("game.manage",): 85,
                ("game.purchase",): 5,
                ("game.install",): 17,
                ("game.launch",): 28,
                ("app.open", "game.install"): 4,
                ("app.open", "game.launch"): 1,
                ("app.open", "game.manage"): 22,
                ("app.open", "game.install", "game.manage"): 3,
            },
        )

    def test_audio_status_semantic_amendment_is_exact_and_read_only(self) -> None:
        for text in (
            "qué volumen tengo",
            "mostrame el volumen",
            "show me the volume",
            "show me el volumen",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    resolve_operation_polarity(text).actionable_operations,
                    ("audio.status",),
                )
                self.assertEqual(
                    risk_policy(text, ["audio.status"]),
                    {
                        "class": "read_only",
                        "confirmation": "not_required",
                        "reason": (
                            "La consulta solo lee el estado actual; no autoriza "
                            "efectos físicos."
                        ),
                    },
                )

        corpus_dir = Path(__file__).resolve().parent / "data"
        messages = read_jsonl(corpus_dir / "historical_messages.jsonl")
        mappings = read_jsonl(corpus_dir / "historical_message_mapping.jsonl")
        status_rows = [row for row in messages if row["operations"] == ["audio.status"]]
        status_ids = {row["message_id"] for row in status_rows}
        self.assertEqual(len(status_rows), 16)
        self.assertEqual(len({normalize(row["text_literal"]) for row in status_rows}), 2)
        self.assertEqual(
            digest_sorted_lines(status_ids),
            "cd3512c246ca7b4fe29f98e944eac5885cd73ca478a4fa9183d21edb409c60fb",
        )
        self.assertEqual(
            {row["canonical_mission_id"] for row in status_rows},
            {"mission_user_mission_audio_status_3f06791dcc"},
        )
        self.assertTrue(
            all(
                row["class"] == "user_mission"
                and row["acceptance_scope"] == "product_1_0"
                and row["risk"]["class"] == "read_only"
                and row["risk"]["confirmation"] == "not_required"
                for row in status_rows
            )
        )
        status_mappings = [row for row in mappings if row["message_id"] in status_ids]
        self.assertEqual(len(status_mappings), 16)
        self.assertTrue(
            all(
                row["operations"] == ["audio.status"]
                and row["provider_roles"] == ["audio_adapter"]
                and row["risk"]["class"] == "read_only"
                for row in status_mappings
            )
        )

    def test_target_language_game_launch_and_install_oracles(self) -> None:
        launch_cases = (
            "Abre Counter Strike",
            "launch Hollow Knight",
            "y sí, lánzalo",
            "abre Steam Role",
            "why the hell didn't you open the game, open it now",
            "ya lo tengo comprado",
        )
        for text in launch_cases:
            with self.subTest(text=text):
                self.assertEqual(
                    resolve_operation_polarity(text).actionable_operations,
                    ("game.launch",),
                )

        self.assertEqual(
            resolve_operation_polarity(
                "Abre Steam y ejecuta el juego instalado Portal"
            ).actionable_operations,
            ("app.open", "game.launch"),
        )
        for text in (
            "abre Steam y instala Fall Guys",
            "open Steam and install Stardew Valley",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    resolve_operation_polarity(text).actionable_operations,
                    ("app.open", "game.install"),
                )
        self.assertEqual(
            resolve_operation_polarity("Desinstala Portal").actionable_operations,
            ("game.install",),
        )
        self.assertEqual(
            resolve_operation_polarity(
                "app.uninstall`, `steam.install"
            ).actionable_operations,
            (),
        )
        for text in (
            "desinstala Hades de Steam",
            "uninstall Hades from Steam",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    resolve_operation_polarity(text).actionable_operations,
                    ("game.install",),
                )
        for text in (
            "confirmo",
            "instálala pls",
            "quiero que lo instales, ya lo tengo comprado",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    resolve_operation_polarity(text).actionable_operations,
                    ("game.install",),
                )

        # "Batman" alone is intentionally ambiguous, and non-target-language
        # variants remain trace-only rather than 1.0 acceptance commitments.
        self.assertNotIn(
            "game.launch",
            resolve_operation_polarity("Abre Batman").actionable_operations,
        )
        self.assertNotIn(
            "game.launch",
            resolve_operation_polarity("Apri Stardew Valley").actionable_operations,
        )

        root = Path(__file__).resolve().parents[1]
        manifest = json.loads(
            (root / "artifacts" / "corpus_cutoff" / "source_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        scope_oracle = build_acceptance_scope_oracle(manifest)
        self.assertEqual(len(scope_oracle.source_decisions), 2_846)
        self.assertEqual(len(scope_oracle.cross_source_keys), 2_786)
        self.assertEqual(len(scope_oracle.cross_source_normalized_keys), 2_746)
        self.assertEqual(scope_oracle.exact_exception_keys, 18)
        for literal in ("ahah", "haha"):
            self.assertNotIn(
                acceptance_scope_key(literal), scope_oracle.cross_source_keys
            )
            self.assertNotIn(
                normalize(literal), scope_oracle.cross_source_normalized_keys
            )
        self.assertIn(
            acceptance_scope_key("\u4f60\u597d"), scope_oracle.cross_source_keys
        )

    def test_ocr_implementation_guidance_is_not_an_empty_user_mission(self) -> None:
        collector = Collector("a" * 64)
        collector.add(
            'Usa control + f -> enter +> "Escribir mensaje", es asi de simple\n\n'
            "NO USES OCR, es un gasto de latencia innecesario",
            origin="observed_user",
            source="fixture",
            location="line:1",
            source_sha256="b" * 64,
        )
        self.assertEqual(len(collector.rows), 1)
        row = collector.rows[0]
        self.assertEqual(row["class"], "engineering_instruction")
        self.assertEqual(row["operations"], [])
        self.assertEqual(row["denied_operations"], ["ocr.read"])

    def test_frozen_hypothetical_occurrence_cannot_become_a_tool_call(self) -> None:
        source = "fixture"
        location = "line:1"
        literal = "Por ejemplo, explícame qué pasaría si te digo instala Batman y pon una canción"
        text_sha = hashlib.sha256(literal.encode("utf-8")).hexdigest()
        stable = f"{source}|{location}|{text_sha}"
        message_id = "msg_" + hashlib.sha256(stable.encode("utf-8")).hexdigest()[:20]
        collector = Collector("a" * 64)
        with patch(
            "scripts.build_historical_corpus._FROZEN_CONVERSATION_MESSAGE_IDS",
            frozenset({message_id}),
        ):
            collector.add(
                literal,
                origin="observed_user",
                source=source,
                location=location,
                source_sha256="b" * 64,
            )
        row = collector.rows[0]
        self.assertEqual(row["class"], "conversation_question")
        self.assertEqual(row["operations"], [])

    def test_engineering_instruction_is_not_a_user_tool(self) -> None:
        text = "Revisa el repo, implementa la arquitectura y ejecuta todos los tests"
        self.assertEqual(
            classify(text, "observed_user", operation_names(text)),
            "engineering_instruction",
        )

    def test_generated_ledgers_do_not_feed_back_into_the_corpus(self) -> None:
        names = {
            path.name
            for path in markdown_sources()
            if path.parent.name == "documentacion"
        }
        self.assertIn("05_FALLOS_Y_REGRESIONES.md", names)
        self.assertNotIn("07_LEDGER_REQUISITOS_HISTORICOS.md", names)

    def test_baxy_markdown_is_read_from_the_frozen_commit(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads(
            (root / "artifacts" / "corpus_cutoff" / "source_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        path = root / "documentacion" / "05_FALLOS_Y_REGRESIONES.md"
        frozen, _ = frozen_source_text(path, manifest)
        self.assertNotIn("R-036", frozen)
        self.assertIn("R-036", path.read_text(encoding="utf-8"))

    def test_manifest_bound_live_file_fails_closed_after_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.txt"
            path.write_text("changed", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                _verified_live_bytes(path, "0" * 64)

    def test_manifest_payload_digest_is_validated(self) -> None:
        payload = {"schema_version": 1, "sources": []}
        digest = canonical_digest(payload)
        manifest = {
            **payload,
            "generated_at": "2026-07-14T12:00:00+00:00",
            "manifest_payload_sha256": digest,
        }
        self.assertEqual(validate_manifest_payload(manifest), digest)
        with self.assertRaisesRegex(RuntimeError, "payload mismatch"):
            validate_manifest_payload({**manifest, "schema_version": 2})
        with self.assertRaisesRegex(RuntimeError, "no valid manifest_payload_sha256"):
            validate_manifest_payload(payload)

    def test_codex_extraction_fails_when_manifested_session_is_missing(self) -> None:
        manifest = codex_prefix_manifest(
            line_count=1,
            byte_count=1,
            sha256="0" * 64,
        )
        with patch(
            "scripts.build_historical_corpus.codex_session_index",
            return_value={},
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Frozen Codex session unavailable: fixture-session"
            ):
                extract_codex(Collector("a" * 64), manifest)

    def test_codex_extraction_fails_on_any_prefix_mismatch(self) -> None:
        before = codex_event_line("2026-07-14T10:51:49.000Z", "before cutoff")
        expected = {
            "line_count": 1,
            "byte_count": len(before),
            "sha256": hashlib.sha256(before).hexdigest(),
        }
        mismatches = {
            "line_count": {**expected, "line_count": 2},
            "bytes": {**expected, "byte_count": len(before) + 1},
            "sha256": {**expected, "sha256": "0" * 64},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            path.write_bytes(before)
            for field, values in mismatches.items():
                with self.subTest(field=field):
                    manifest = codex_prefix_manifest(**values)
                    with patch(
                        "scripts.build_historical_corpus.codex_session_index",
                        return_value={"fixture-session": path},
                    ):
                        with self.assertRaisesRegex(
                            RuntimeError, rf"prefix mismatch.*{field}"
                        ):
                            extract_codex(Collector("a" * 64), manifest)

    def test_codex_extraction_accepts_append_after_frozen_prefix(self) -> None:
        before = codex_event_line("2026-07-14T10:51:49.000Z", "before cutoff")
        after = codex_event_line("2026-07-14T10:51:50.000Z", "after cutoff")
        untimestamped = (
            json.dumps(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": "unbound append"}],
                    },
                },
                ensure_ascii=False,
            )
            + "\n"
        ).encode("utf-8")
        manifest = codex_prefix_manifest(
            line_count=1,
            byte_count=len(before),
            sha256=hashlib.sha256(before).hexdigest(),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            path.write_bytes(untimestamped + before)
            with patch(
                "scripts.build_historical_corpus.codex_session_index",
                return_value={"fixture-session": path},
            ):
                with self.assertRaisesRegex(RuntimeError, "prefix mismatch"):
                    extract_codex(Collector("a" * 64), manifest)

            path.write_bytes(before + untimestamped + after)
            collector = Collector("a" * 64)
            with patch(
                "scripts.build_historical_corpus.codex_session_index",
                return_value={"fixture-session": path},
            ):
                extract_codex(collector, manifest)

        self.assertEqual(len(collector.rows), 1)
        self.assertEqual(collector.rows[0]["text_literal"], "before cutoff")
        self.assertEqual(collector.rows[0]["source_location"], "event_line:1")
        self.assertEqual(
            collector.rows[0]["source_sha256"], manifest["sources"][1]["sha256"]
        )

    def test_distinct_requirements_and_failures_do_not_overmerge(self) -> None:
        first = mission_signature(
            "product_requirement", [], ["gui"], "BAXY debe mostrar progreso"
        )
        second = mission_signature(
            "product_requirement", [], ["gui"], "BAXY debe ocultar secretos"
        )
        self.assertNotEqual(first, second)
        self.assertNotEqual(
            mission_signature(
                "feedback_failure", [], [], "La GUI mostró cero capacidades"
            ),
            mission_signature(
                "feedback_failure", [], [], "El STT devolvió texto vacío"
            ),
        )

    def test_risk_is_proportional(self) -> None:
        self.assertEqual(
            risk_policy("compra el juego", ["game.purchase"])["confirmation"],
            "required",
        )
        self.assertEqual(
            risk_policy("busca juegos para comprar", ["game.manage"])["confirmation"],
            "not_required",
        )
        self.assertEqual(
            risk_policy(
                "agrega un juego gratis al carrito",
                ["game.purchase"],
            )["confirmation"],
            "not_required",
        )
        self.assertEqual(
            risk_policy("instala el juego que ya tengo", ["game.install"])[
                "confirmation"
            ],
            "conditional",
        )
        self.assertEqual(
            risk_policy("borra System32", ["filesystem.trash"])["confirmation"],
            "blocked",
        )

    def test_derived_reruns_consolidate_but_observed_turns_do_not(self) -> None:
        base = {
            "acceptance_scope": "product_1_0",
            "acceptance_scope_basis": "fixture_product_scope",
            "acceptance_scope_bases": ["fixture_product_scope"],
            "acceptance_scope_source_labels": [],
            "text_literal": "hola",
            "source": "fixture/a",
            "source_location": "line:1",
            "source_sha256": "a" * 64,
            "source_hints": {},
        }
        rows = [
            {**base, "origin": "historical_test"},
            {
                **base,
                "origin": "historical_test",
                "source_location": "line:2",
                "acceptance_scope_basis": "fixture_secondary_evidence",
                "acceptance_scope_bases": ["fixture_secondary_evidence"],
                "acceptance_scope_source_labels": ["es"],
            },
            {**base, "origin": "observed_user", "source_location": "turn:1"},
            {**base, "origin": "observed_user", "source_location": "turn:2"},
        ]
        consolidated, occurrences = consolidate_derived_occurrences(rows)
        self.assertEqual(occurrences, 4)
        self.assertEqual(len(consolidated), 3)
        derived = next(
            row for row in consolidated if row["origin"] == "historical_test"
        )
        self.assertEqual(derived["provenance_occurrence_count"], 2)
        self.assertEqual(
            derived["acceptance_scope_bases"],
            ["fixture_product_scope", "fixture_secondary_evidence"],
        )
        self.assertEqual(derived["acceptance_scope_source_labels"], ["es"])


class GeneratedCorpusContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        preview = os.environ.get("BAXY_CORPUS_DIR")
        corpus_dir = Path(preview) if preview else root / "tests" / "data"
        cls.message_path = corpus_dir / "historical_messages.jsonl"
        cls.mission_path = corpus_dir / "historical_missions.jsonl"
        cls.mapping_path = corpus_dir / "historical_message_mapping.jsonl"
        cls.report_path = (
            corpus_dir / "extraction_report.json"
            if preview
            else root / "artifacts" / "corpus_cutoff" / "extraction_report.json"
        )

    def test_every_message_maps_exactly_once(self) -> None:
        message_ids = [row["message_id"] for row in read_jsonl(self.message_path)]
        mapping_ids = [row["message_id"] for row in read_jsonl(self.mapping_path)]
        self.assertEqual(len(message_ids), len(set(message_ids)))
        self.assertEqual(len(mapping_ids), len(set(mapping_ids)))
        self.assertEqual(set(message_ids), set(mapping_ids))

    def test_all_mapping_missions_exist(self) -> None:
        mission_ids = {
            row["canonical_mission_id"] for row in read_jsonl(self.mission_path)
        }
        mapped = {row["canonical_mission_id"] for row in read_jsonl(self.mapping_path)}
        self.assertTrue(mapped <= mission_ids)

    def test_no_user_mission_lacks_operations(self) -> None:
        for row in read_jsonl(self.message_path):
            if row["class"] == "user_mission":
                self.assertTrue(row["operations"], row["message_id"])

    def test_every_canonical_mission_has_an_executable_acceptance_contract(
        self,
    ) -> None:
        required = {
            "acceptance_scope",
            "acceptance_scope_bases",
            "acceptance_scope_source_labels",
            "acceptance_test_id",
            "canonical_mission_id",
            "class",
            "denied_operations",
            "expected_state",
            "fallback",
            "historical_operations",
            "implementation_status",
            "natural_response",
            "operations",
            "outcome_type",
            "plan",
            "provider_roles",
            "risk",
            "verification",
        }
        for row in read_jsonl(self.mission_path):
            self.assertTrue(required <= row.keys(), row.get("canonical_mission_id"))
            self.assertTrue(row["acceptance_test_id"])
            self.assertTrue(row["expected_state"])
            self.assertTrue(row["plan"])
            self.assertTrue(row["verification"])

    def test_regression_ledger_has_36_unique_structural_failures(self) -> None:
        root = Path(__file__).resolve().parents[1]
        text = (root / "documentacion" / "05_FALLOS_Y_REGRESIONES.md").read_text(
            encoding="utf-8"
        )
        identifiers = re.findall(r"^\| (R-\d{3}) \|", text, flags=re.MULTILINE)
        self.assertEqual(len(identifiers), 36)
        self.assertEqual(len(set(identifiers)), 36)
        self.assertEqual(identifiers, [f"R-{number:03d}" for number in range(1, 37)])

    def test_report_has_no_unclassified_user_missions(self) -> None:
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["dynamic_unclassified_missions"], 0)
        messages = read_jsonl(self.message_path)
        missions = read_jsonl(self.mission_path)
        mappings = read_jsonl(self.mapping_path)
        self.assertEqual(report["raw_messages"], len(messages))
        self.assertEqual(
            report["source_occurrences"],
            sum(row.get("provenance_occurrence_count", 1) for row in messages),
        )
        self.assertEqual(report["messages_sha256"], canonical_digest(messages))
        self.assertEqual(report["missions_sha256"], canonical_digest(missions))
        self.assertEqual(report["mapping_sha256"], canonical_digest(mappings))

    def test_schema_v2_carries_explicit_scope_and_denied_effects(self) -> None:
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(
            report["semantic_revision"],
            "2026-07-15-audio-status-v3",
        )
        self.assertEqual(report["product_language_scope"], ["es", "en", "spanglish"])
        self.assertEqual(
            report["non_target_language_history_policy"],
            "trace_only_not_acceptance_commitment",
        )
        self.assertEqual(report["operation_catalog_size"], 43)
        self.assertEqual(report["raw_messages"], 14_836)
        self.assertEqual(report["canonical_missions"], 2_084)
        self.assertEqual(report["messages_with_denied_operations"], 98)
        self.assertEqual(report["by_class"]["no_action_constraint"], 79)
        self.assertEqual(
            report["by_acceptance_scope"],
            {
                "product_1_0": 12_036,
                "trace_only_not_acceptance_commitment": 2_800,
            },
        )
        oracle = report["acceptance_scope_oracle"]
        self.assertEqual(
            oracle,
            {
                "coverage_claim": (
                    "positive_source_evidence_and_exact_audit_not_heuristic_"
                    "exhaustiveness"
                ),
                "cross_source_trace_only_keys": 2_786,
                "cross_source_trace_only_normalized_keys": 2_746,
                "exact_exception_keys": 18,
                "literal_key_sha256": (
                    "144b1f85278a711759cbfec79d136c422b7c330ad8ba73275b07bc680ba9b110"
                ),
                "matched_literal_keys": 2_769,
                "matched_rows": 2_800,
                "matched_source_occurrences": 5_182,
                "message_contract_sha256": (
                    "1e86f6ff4503458db6e6c0bb312f8e77928b0a63911f166745d6dcd6116c5363"
                ),
                "message_id_sha256": (
                    "603faa6e1624e040ba3182580fa85f2b7de45c1f5f6a7251b24aa7a8dc4f80a1"
                ),
                "name": "frozen_audited_non_target_oracle",
                "source_files": [
                    {
                        "path": "functiongemma/finetune_llm/curated/train_v3.jsonl",
                        "sha256": (
                            "6ccf110a23090ce274695d24a7c7956f2ea36e91b51fe001509be4a9abd01643"
                        ),
                    },
                    {
                        "path": (
                            "functiongemma/router/data/router_corpus_curated_ft.jsonl"
                        ),
                        "sha256": (
                            "c7d15542b7da5d1b8ad6eacc683687bb8a6c1cc26fef3918ee3ca9f3878fd423"
                        ),
                    },
                    {
                        "path": (
                            "functiongemma/router/data/router_eval_corpus.curated.jsonl"
                        ),
                        "sha256": (
                            "c234df94bdb71befc8ba36fd8b9d40399cd140ae3e2ec76be48330c16369dfdb"
                        ),
                    },
                ],
                "source_labeled_trace_only_locations": 2_846,
                "target_wins_or_source_override_keys": 18,
            },
        )

        for path in (self.message_path, self.mission_path, self.mapping_path):
            for row in read_jsonl(path):
                self.assertIn("acceptance_scope", row)
                self.assertIn("denied_operations", row)
                self.assertIsInstance(row["denied_operations"], list)

        messages = read_jsonl(self.message_path)
        self.assertEqual(
            Counter(row["acceptance_scope_basis"] for row in messages),
            Counter(
                {
                    "audited_exact_non_target_exception": 17,
                    "audited_router_eval_non_target_block": 102,
                    "cross_source_exact_non_target_literal": 72,
                    "cross_source_normalized_non_target_literal": 1,
                    "not_in_audited_non_target_oracle": 12_036,
                    "router_eval_non_target_language_label": 128,
                    "train_v3_non_target_language_label": 2_480,
                }
            ),
        )
        self.assertTrue(
            any(
                row["language"] == "other" and row["acceptance_scope"] == "product_1_0"
                for row in messages
            )
        )
        for row in messages:
            self.assertIn("acceptance_scope_bases", row)
            self.assertIsInstance(row["acceptance_scope_bases"], list)
            self.assertTrue(row["acceptance_scope_bases"])
            self.assertIn(row["acceptance_scope_basis"], row["acceptance_scope_bases"])
            self.assertIn("acceptance_scope_source_labels", row)
            self.assertIsInstance(row["acceptance_scope_source_labels"], list)
            provenance = row.get("provenance_occurrences", [])
            if provenance:
                self.assertEqual(
                    row["acceptance_scope_bases"],
                    sorted(
                        {
                            occurrence["acceptance_scope_basis"]
                            for occurrence in provenance
                        }
                    ),
                )
                self.assertEqual(
                    row["acceptance_scope_source_labels"],
                    sorted(
                        {
                            label
                            for occurrence in provenance
                            for label in occurrence.get(
                                "acceptance_scope_source_labels", []
                            )
                        }
                    ),
                )

        missions = {
            row["canonical_mission_id"]: row for row in read_jsonl(self.mission_path)
        }
        for mapping in read_jsonl(self.mapping_path):
            self.assertIn("acceptance_scope_basis", mapping)
            self.assertIn("acceptance_scope_bases", mapping)
            self.assertIn("acceptance_scope_source_labels", mapping)
            mission = missions[mapping["canonical_mission_id"]]
            self.assertIn(
                mapping["acceptance_scope_basis"], mapping["acceptance_scope_bases"]
            )
            self.assertTrue(
                set(mapping["acceptance_scope_bases"])
                <= set(mission["acceptance_scope_bases"])
            )
            self.assertTrue(
                set(mapping["acceptance_scope_source_labels"])
                <= set(mission["acceptance_scope_source_labels"])
            )
            self.assertEqual(mapping["acceptance_scope"], mission["acceptance_scope"])
            self.assertEqual(mapping["denied_operations"], mission["denied_operations"])
            self.assertEqual(mapping["operations"], mission["operations"])
            self.assertEqual(mapping["risk"], mission["risk"])
            if mapping["acceptance_scope"] == "trace_only_not_acceptance_commitment":
                self.assertEqual(mapping["operations"], [])
                self.assertEqual(mapping["provider_roles"], [])
                self.assertEqual(mapping["risk"]["class"], "no_effect")
                self.assertEqual(mapping["risk"]["confirmation"], "not_required")

    def test_target_language_game_oracles_are_exact(self) -> None:
        messages = read_jsonl(self.message_path)
        expressive_target_rows = [
            row
            for row in messages
            if normalize(row["text_literal"]) in {"ahah", "haha"}
        ]
        self.assertEqual(
            {row["message_id"] for row in expressive_target_rows},
            {
                "msg_39ebd89a7f4ecbee7e35",
                "msg_3f8d8560bae10d9e838d",
                "msg_923356b4e8c8ac2bc2f4",
            },
        )
        self.assertEqual(
            sum(row["provenance_occurrence_count"] for row in expressive_target_rows),
            88,
        )
        self.assertEqual(
            {row["acceptance_scope"] for row in expressive_target_rows},
            {"product_1_0"},
        )

        launch = [row for row in messages if "game.launch" in row["operations"]]
        self.assertEqual(len(launch), 46)
        self.assertEqual(len({normalize(row["text_literal"]) for row in launch}), 29)
        self.assertEqual(
            Counter(tuple(row["operations"]) for row in launch),
            Counter({("game.launch",): 45, ("app.open", "game.launch"): 1}),
        )
        self.assertEqual(
            digest_sorted_lines([row["message_id"] for row in launch]),
            "7b9ccccd5c643660e786e7699cdb15062a2fef46671a1edcea641bd72eb2c3cc",
        )
        self.assertEqual(
            digest_sorted_lines({normalize(row["text_literal"]) for row in launch}),
            "d51a40fdf93920a8b5ce67f4bbb74977f9e8702792b179eef333116d5ae752ba",
        )
        self.assertEqual(
            digest_sorted_lines(
                [f"{row['message_id']}|{','.join(row['operations'])}" for row in launch]
            ),
            "0e6dc7fa308df565c67fce47e394e1eeaffd0c8182ee907d9ba85278f963d363",
        )
        self.assertEqual(
            digest_sorted_lines(
                {
                    f"{normalize(row['text_literal'])}|{','.join(row['operations'])}"
                    for row in launch
                }
            ),
            "1b2a3cd86fdb305d94127fc85b34277254ad999b6cf9bb618bb7c1ce75a2c8e3",
        )
        self.assertEqual({row["acceptance_scope"] for row in launch}, {"product_1_0"})

        # The language detector is heuristic. Scope is bound by this audited
        # semantic exclusion, not by treating every row marked "other" as foreign.
        non_target_install_literals = {
            "installier mortal kombat 11 auf steam",
            "installe terraria depuis steam",
            "o instala pra mim o batman arkham nike",
            "instala o terraria pelo steam",
            "installier mir terraria uber steam",
            "installier terraria uber steam",
            "installa hades da steam",
        }
        all_install = [row for row in messages if "game.install" in row["operations"]]
        non_target = [
            row
            for row in all_install
            if normalize(row["text_literal"]) in non_target_install_literals
        ]
        install = [row for row in all_install if row not in non_target]
        self.assertEqual(len(all_install), 81)
        self.assertEqual(len(non_target), 7)
        self.assertEqual(
            {normalize(row["text_literal"]) for row in non_target},
            non_target_install_literals,
        )
        self.assertEqual(
            {row["acceptance_scope"] for row in non_target},
            {"trace_only_not_acceptance_commitment"},
        )
        self.assertEqual(
            {row["acceptance_scope"] for row in install},
            {"product_1_0"},
        )
        self.assertEqual(len(install), 74)
        self.assertEqual(len({normalize(row["text_literal"]) for row in install}), 63)
        self.assertEqual(
            Counter(tuple(row["operations"]) for row in install),
            Counter(
                {
                    ("game.install",): 62,
                    ("app.open", "game.install"): 6,
                    ("app.open", "game.install", "game.manage"): 4,
                    ("game.install", "media.play"): 1,
                    ("game.install", "web.search"): 1,
                }
            ),
        )
        self.assertEqual(
            digest_sorted_lines([row["message_id"] for row in install]),
            "76faffd5817be902a5f6477d40acdd78bbf678a0ae2b17bbbaf8bbe6d9f24d90",
        )
        self.assertEqual(
            digest_sorted_lines({normalize(row["text_literal"]) for row in install}),
            "486d6e182491b0689544e03ebfd80190b0b3c5763d2f985a50041d27cc2aa595",
        )
        self.assertEqual(
            digest_sorted_lines(
                [
                    f"{row['message_id']}|{','.join(row['operations'])}"
                    for row in install
                ]
            ),
            "e341eec4c3173b62d87ea21fbb0718dc61a9998a8102674e3650138a1709ed5e",
        )
        self.assertEqual(
            digest_sorted_lines(
                {
                    f"{normalize(row['text_literal'])}|{','.join(row['operations'])}"
                    for row in install
                }
            ),
            "6df7649cedc7bdd19123bba6bb4d292d3f2d16cc011ad21ffe5de458336814f0",
        )

        mappings = {row["message_id"]: row for row in read_jsonl(self.mapping_path)}
        missions = {
            row["canonical_mission_id"]: row for row in read_jsonl(self.mission_path)
        }
        trace_mission_ids = {
            mappings[row["message_id"]]["canonical_mission_id"] for row in non_target
        }
        self.assertEqual(len(trace_mission_ids), 1)
        for row in non_target:
            mapping = mappings[row["message_id"]]
            self.assertEqual(
                mapping["acceptance_scope"],
                "trace_only_not_acceptance_commitment",
            )
            self.assertEqual(mapping["outcome_type"], "historical_trace_only")
            self.assertEqual(mapping["status"], "trace_only_not_acceptance_commitment")
            self.assertEqual(mapping["operations"], [])
            self.assertEqual(mapping["provider_roles"], [])
            self.assertEqual(mapping["risk"]["class"], "no_effect")
            self.assertEqual(mapping["risk"]["confirmation"], "not_required")
        trace_mission = missions[trace_mission_ids.pop()]
        self.assertEqual(
            trace_mission["acceptance_scope"],
            "trace_only_not_acceptance_commitment",
        )
        self.assertEqual(trace_mission["provider_roles"], [])
        self.assertEqual(trace_mission["operations"], [])
        self.assertEqual(trace_mission["risk"]["class"], "no_effect")
        self.assertEqual(trace_mission["risk"]["confirmation"], "not_required")
        self.assertEqual(
            trace_mission["implementation_status"],
            "trace_only_not_acceptance_commitment",
        )

    def test_game_management_purchase_and_polarity_regressions_are_bound(self) -> None:
        messages = read_jsonl(self.message_path)
        by_id = {row["message_id"]: row for row in messages}
        mappings = {row["message_id"]: row for row in read_jsonl(self.mapping_path)}
        missions = {
            row["canonical_mission_id"]: row for row in read_jsonl(self.mission_path)
        }
        manage = [row for row in messages if "game.manage" in row["operations"]]
        purchase = [row for row in messages if "game.purchase" in row["operations"]]
        self.assertEqual(len(manage), 169)
        self.assertEqual(
            digest_sorted_lines([row["message_id"] for row in manage]),
            "9b8313bfa1e72b6ec145ddfe2c25446ab46ce145b6e4c0f48e389d476bb14287",
        )
        self.assertEqual(
            digest_sorted_lines(
                [f"{row['message_id']}|{','.join(row['operations'])}" for row in manage]
            ),
            "0f1df1847f8eb0dc84297ebced16a9d9423c41dc4f49dbdcd0edfc06252265ff",
        )
        self.assertEqual(
            digest_sorted_lines(
                {
                    f"{normalize(row['text_literal'])}|{','.join(row['operations'])}"
                    for row in manage
                }
            ),
            "8b9a5101ce994b9231bd3d2d78f03ed9bd9d15da16f61e4951843392084ec134",
        )
        self.assertEqual(len(purchase), 6)
        self.assertEqual(
            digest_sorted_lines([row["message_id"] for row in purchase]),
            "599ef4158d0d4342cc369203618995c32160884631f5369f5e0641763ca9c754",
        )
        self.assertEqual(
            digest_sorted_lines(
                [
                    f"{row['message_id']}|{','.join(row['operations'])}"
                    for row in purchase
                ]
            ),
            "f113a6e37d2d63a703a0749e83ee6f06320eb48d10db0dd3fb7c083fb59f11ee",
        )
        self.assertEqual(
            digest_sorted_lines(
                {
                    f"{normalize(row['text_literal'])}|{','.join(row['operations'])}"
                    for row in purchase
                }
            ),
            "867431d4cfb60cfbf40e689ca7398bcbc02f4d502668cb1a895bdc014344fecc",
        )

        free_id = "msg_6ef2f141b958d77e9d25"
        paid_id = "msg_6f8fb74dccdf819e7c65"
        free_mapping = mappings[free_id]
        paid_mapping = mappings[paid_id]
        self.assertNotEqual(
            free_mapping["canonical_mission_id"],
            paid_mapping["canonical_mission_id"],
        )
        self.assertEqual(
            free_mapping["risk"]["confirmation"],
            "not_required",
        )
        self.assertEqual(free_mapping["outcome_type"], "mission_must_implement")
        self.assertEqual(paid_mapping["risk"]["confirmation"], "required")
        self.assertEqual(
            paid_mapping["outcome_type"], "risk_or_external_dependency_flow"
        )
        self.assertEqual(
            missions[free_mapping["canonical_mission_id"]]["risk"]["class"],
            "low_reversible",
        )
        self.assertEqual(
            missions[paid_mapping["canonical_mission_id"]]["risk"]["class"],
            "monetary",
        )

        expected = {
            "msg_43ba649bfe2f0db1366e": ("engineering_instruction", [], []),
            "msg_513b25ade5b30e155623": ("conversation_question", [], []),
            "msg_2b20616ab9f74ea9e0fc": (
                "no_action_constraint",
                [],
                ["game.launch"],
            ),
            "msg_58a158d6411825bdbd9e": (
                "no_action_constraint",
                [],
                ["game.launch"],
            ),
            "msg_1ed2d4308fc4b83558f1": (
                "product_requirement",
                ["app.open", "web.search"],
                [],
            ),
            "msg_3513ebf4589a20deba2a": ("engineering_instruction", [], []),
            "msg_652a750e39c5a0b025ba": (
                "no_action_constraint",
                [],
                ["app.open"],
            ),
        }
        for message_id, contract in expected.items():
            row = by_id[message_id]
            self.assertEqual(
                (row["class"], row["operations"], row["denied_operations"]),
                contract,
                message_id,
            )

    def test_semantic_amendment_binds_sources_and_regenerated_files(self) -> None:
        root = Path(__file__).resolve().parents[1]
        amendment = json.loads(
            (
                root / "artifacts" / "corpus_cutoff" / "semantic_amendment.json"
            ).read_text(encoding="utf-8")
        )
        authority = amendment["authority"]
        protected = {
            root / "artifacts" / "corpus_cutoff" / "source_manifest.json": authority[
                "source_manifest_file_sha256"
            ],
            root / "scripts" / "freeze_historical_sources.py": authority[
                "freeze_script_sha256"
            ],
            root / "artifacts" / "technology_tournament" / "protocol.json": authority[
                "tournament_protocol_sha256"
            ],
            root / "scripts" / "build_historical_corpus.py": authority[
                "builder_sha256"
            ],
        }
        for path, expected in protected.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)

        regenerated = {
            "historical_messages.jsonl": self.message_path,
            "historical_missions.jsonl": self.mission_path,
            "historical_message_mapping.jsonl": self.mapping_path,
            "extraction_report.json": self.report_path,
        }
        for name, path in regenerated.items():
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                amendment["file_sha256"]["after"][name],
            )
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertEqual(
            amendment["language_contract"]["acceptance_scope_oracle"],
            report["acceptance_scope_oracle"],
        )
        self.assertEqual(
            amendment["metrics"]["after"]["acceptance_scope"],
            report["by_acceptance_scope"],
        )
        self.assertEqual(
            amendment["metrics"]["after"]["raw_messages"],
            report["raw_messages"],
        )
        self.assertEqual(
            amendment["metrics"]["after"]["canonical_missions"],
            report["canonical_missions"],
        )
        self.assertEqual(
            amendment["canonical_digests"]["after"],
            {
                "mapping_sha256": report["mapping_sha256"],
                "messages_sha256": report["messages_sha256"],
                "missions_sha256": report["missions_sha256"],
            },
        )

        reproduction = amendment["reproduction"]
        expected_output_hashes = amendment["file_sha256"]["after"]
        self.assertEqual(
            reproduction["commands"],
            {
                "isolated_preview": (
                    "python -X utf8 scripts/build_historical_corpus.py --output-dir "
                    "<isolated-output-dir> --report "
                    "<isolated-output-dir>/extraction_report.json"
                ),
                "canonical": "python -X utf8 scripts/build_historical_corpus.py",
            },
        )
        passes = reproduction["passes"]
        self.assertEqual(len(passes), 2)
        self.assertEqual(
            {run["mode"] for run in passes}, {"isolated_preview", "canonical"}
        )
        self.assertEqual(len({run["run_id"] for run in passes}), 2)
        for run in passes:
            self.assertEqual(run["builder_sha256"], authority["builder_sha256"])
            self.assertEqual(run["output_sha256"], expected_output_hashes)
            self.assertLess(run["started_utc"], run["ended_utc"])
        self.assertEqual(
            reproduction["byte_comparison"],
            {name: True for name in expected_output_hashes},
        )
        self.assertTrue(authority["source_manifest_unchanged"])
        self.assertTrue(authority["tournament_protocol_unchanged"])
        self.assertEqual(amendment["verification"]["reproduction_passes"], len(passes))
        self.assertTrue(
            amendment["verification"]["canonical_matches_preview_byte_for_byte"]
        )
        self.assertEqual(amendment["release_status"]["must_gates_approved"], 5)
        self.assertEqual(
            amendment["release_status"]["blockers_unchanged"],
            ["B-004", "B-005", "B-006"],
        )

    def test_cutoff_manifest_binds_git_ignored_message_sources(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads(
            (root / "artifacts" / "corpus_cutoff" / "source_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        sources = {row["id"]: row for row in manifest["sources"]}
        self.assertEqual(len(sources), 17)
        for source_id in (
            "probando_router_corpus_real_logs",
            "probando_runtime_traces",
            "probando_thesis_deliverables",
            "probando_documentation",
        ):
            self.assertIn(source_id, sources)
        self.assertEqual(sources["probando_thesis_deliverables"]["file_count"], 38)
        self.assertEqual(sources["probando_documentation"]["file_count"], 594)

    def test_versioned_literals_do_not_expose_absolute_user_paths(self) -> None:
        raw = self.message_path.read_text(encoding="utf-8").casefold()
        self.assertNotIn("c:\\users\\", raw)
        self.assertNotIn("c:/users/", raw)
        self.assertNotIn("\x00", raw)


if __name__ == "__main__":
    unittest.main()
