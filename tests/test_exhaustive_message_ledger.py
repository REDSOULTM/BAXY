import json
import hashlib
import os
import unittest

from scripts.build_exhaustive_message_ledger import (
    SourceDocument,
    clean_codex_user_text,
    document_messages,
    is_candidate_path,
    json_messages,
    plausible_user_text,
)
from scripts.build_exhaustive_runtime_oracle import (
    baseline_expectation,
    choose_expectations,
    expectation,
    operation_families,
    reviewed_semantic_expectation,
)
from scripts.build_exhaustive_runtime_language_scope import confident_non_target_pattern
from scripts.run_exhaustive_runtime_model_gate import (
    assess,
    conversation_quality,
    operation_family,
    process_exists,
    process_start_time,
    request_turn_and_optional_plan,
)
from scripts.build_historical_runtime_hints import hint_rows
from baxy_mind.historical_intents import (
    HistoricalIntentRegistry,
    operation_allowed_by_hint,
)


class ExhaustiveMessageLedgerTests(unittest.TestCase):
    def test_verified_clipboard_paste_satisfies_both_clipboard_and_input_intents(self):
        plan = {
            "type": "plan.result",
            "kind": "plan",
            "steps": [{"operation": "clipboard.paste", "arguments": {}}],
        }
        status, families = assess(
            {"expected_effect": "operation", "expected_families": ["input"]},
            {"type": "turn.result", "kind": "plan"},
            plan,
            "pega texto del portapapeles",
        )

        self.assertEqual(status, "pass_operation_family")
        self.assertEqual(families, ["clipboard", "input"])

    def test_language_scope_excludes_reviewed_portuguese_shapes_not_entities(self):
        for text in (
            "pode abrir o Notion?",
            "Poderia fechar a Calculadora?",
            "fecha o Word",
            "feche o Spotify",
            "fazer o copy agora",
        ):
            with self.subTest(text=text):
                self.assertIsNotNone(confident_non_target_pattern(text))
        for text in ("abre Word", "cierra Spotify", "open Notion", "pause the video"):
            with self.subTest(text=text):
                self.assertIsNone(confident_non_target_pattern(text))

    def test_candidate_filter_includes_historical_logs_but_not_derived_ledgers(self):
        self.assertTrue(is_candidate_path("legacy/Carter_v4/audit/runs/C07.json"))
        self.assertTrue(is_candidate_path("gemma4_agent/data/traces.jsonl"))
        self.assertFalse(is_candidate_path("tests/data/historical_messages.jsonl"))
        self.assertFalse(is_candidate_path("models/history.gguf"))
        self.assertFalse(
            is_candidate_path(
                "Extras/Optimizacion Hermes3/lm-evaluation-harness-main/"
                "results/chat_prompts.json"
            )
        )
        self.assertFalse(
            is_candidate_path(
                "legacy/Carter_v1/.runtime/tabbyAPI/venv/"
                "Lib/site-packages/pkg/test_history.json"
            )
        )

    def test_json_walker_recovers_user_turns_and_command_fields(self):
        value = {
            "rows": [
                {"utterance": "que hora es", "reply": "21:00"},
                {"messages": [{"role": "user", "content": "abre Steam"}]},
                {"kind": "request_start", "content": {"preview": "cuanta ram tengo"}},
            ]
        }

        recovered = [text for _, text in json_messages(value)]

        self.assertEqual(
            recovered,
            ["que hora es", "abre Steam", "cuanta ram tengo"],
        )

    def test_codex_cleanup_keeps_only_the_actual_request(self):
        wrapped = (
            "# Context from my IDE setup:\n\n## Open tabs:\n- app.py\n\n"
            "## My request for Codex:\nHaz que todos los casos funcionen"
        )
        self.assertEqual(
            clean_codex_user_text(wrapped),
            "Haz que todos los casos funcionen",
        )
        self.assertEqual(
            clean_codex_user_text("<recommended_plugins>\n- Gmail"),
            "",
        )

    def test_document_parser_does_not_treat_assistant_reply_as_user_input(self):
        data = json.dumps(
            {
                "rows": [
                    {
                        "utterance": "cierra steam",
                        "reply": "Listo",
                        "evidence": "verified",
                    }
                ]
            }
        ).encode()
        document = SourceDocument(
            "carter_os_ai",
            "git_blob",
            "a" * 40,
            "Carter_v4/audit/runs/case.json",
            data,
        )

        self.assertEqual(
            list(document_messages(document)),
            [("/rows/0/utterance", "cierra steam")],
        )

    def test_system_prompt_mislabeled_as_prompt_is_not_a_user_message(self):
        self.assertFalse(
            plausible_user_text(
                "/rows/0/prompt",
                "You are an assistant. Available tools: app.open, app.close",
            )
        )
        self.assertTrue(plausible_user_text("/rows/0/prompt", "abre steam"))

    def test_independent_oracle_maps_legacy_labels_and_preserves_no_effect(self):
        families, unknown = operation_families(
            ["steam/gui", "media_volume", "notes_tasks"]
        )
        self.assertEqual(
            families,
            ["audio", "game", "note_task"],
        )
        self.assertEqual(unknown, [])
        self.assertEqual(
            expectation("baseline", "exact", ["ninguna"])["expected_effect"],
            "none",
        )

    def test_baseline_also_valid_does_not_force_an_optional_effect(self):
        conversational = baseline_expectation(
            {
                "cat": "conversacion",
                "tools_expected": [],
                "also_valid": ["web", "browser"],
                "reply": "¿Querés que busque algo en Google? Decime qué.",
            }
        )
        operational = baseline_expectation(
            {
                "cat": "accion",
                "tools_expected": ["browser"],
                "also_valid": ["web"],
                "reply": "Listo.",
            }
        )

        self.assertEqual(conversational["expected_effect"], "none")
        self.assertEqual(conversational["families"], [])
        self.assertEqual(
            conversational["alternative_families"], ["browser", "web"]
        )
        self.assertEqual(operational["expected_effect"], "operation")
        self.assertEqual(operational["families"], ["browser", "web"])

    def test_independent_oracle_prefers_exact_authority_before_normalized_fallback(self):
        baseline = expectation("baseline", "exact", ["system"])
        legacy = expectation("legacy", "exact", [])
        authority, rows = choose_expectations(
            "¿Qué hora es?",
            [
                ("baseline", {"¿Qué hora es?": [baseline]}, {}),
                ("existing", {}, {"que hora es": [legacy]}),
            ],
        )

        self.assertEqual(authority, "baseline_exact")
        self.assertEqual(rows[0]["families"], ["system"])

    def test_independent_oracle_corrects_obvious_legacy_label_omissions(self):
        file_search = reviewed_semantic_expectation("buscá el archivo informe.pdf")
        app_open = reviewed_semantic_expectation("abrí Chrome Chrome Chrome")

        self.assertEqual(file_search["families"], ["filesystem"])
        self.assertEqual(app_open["families"], ["app"])
        for text in (
            "Te invenstaste ese link",
            "you made up that link",
            "abri el mejor",
            "open the best",
            "muestra TURN_TRACE",
            "show router_trace",
            "Powerpoint, necesito",
            "Word help",
            "open the music thingy",
            "quello el otro app",
            "Si lo hiciste pero no funciono",
            "you did it but it did not work",
            "pero por qué carajo no me abriste el juego, abrilo ya",
            "Recuérdame que pague la factura",
            "remind me to pay the invoice",
            "Pues hazlo",
            "then do it",
            "multiplicá 6 por 7",
            "multiply 8 by 9",
        ):
            with self.subTest(text=text):
                followup = reviewed_semantic_expectation(text)
                self.assertEqual(followup["expected_effect"], "none")
                self.assertEqual(followup["families"], [])
        for text in ("escribí 12+12", "type 5+3"):
            with self.subTest(text=text):
                typed = reviewed_semantic_expectation(text)
                self.assertEqual(typed["expected_effect"], "operation")
                self.assertEqual(typed["families"], ["input"])
        for text in (
            "is ComfyUI running",
            "is the notepad application open?",
            "Visual Studio está cerrado",
        ):
            with self.subTest(text=text):
                status = reviewed_semantic_expectation(text)
                self.assertEqual(status["expected_effect"], "operation")
                self.assertEqual(status["families"], ["window"])
        for text in ("apri il browser", "open the browser", "abre el navegador"):
            with self.subTest(text=text):
                browser = reviewed_semantic_expectation(text)
                self.assertEqual(browser["families"], ["app"])
        self.assertEqual(
            expectation("legacy", "exact", ["fact_check"])["expected_effect"],
            "none",
        )
        self.assertEqual(
            expectation("legacy", "exact", ["uia"])["expected_effect"],
            "unsupported",
        )
        self.assertEqual(
            reviewed_semantic_expectation("what is a hard disk")["expected_effect"],
            "none",
        )
        self.assertEqual(
            reviewed_semantic_expectation(
                "Você conhece alguma música do Coldplay?"
            )["expected_effect"],
            "none",
        )
        process_list = reviewed_semantic_expectation("regarde les processus")
        self.assertEqual(process_list["expected_effect"], "operation")
        self.assertEqual(process_list["families"], ["system"])
        for text, expected_family in (
            ("Ver procesos ahora", "system"),
            ("view running processes now", "system"),
            ("qué estoy escuchando", "media"),
            ("what am I listening to", "media"),
            ("abre el último archivo que descargué", "filesystem"),
            ("current laptop prices", "web"),
            ("anotá que hoy salí a correr", "note_task"),
            ("qué versión de Chrome tengo instalada", "app"),
            ("volvé a la página anterior", "browser"),
            ("when is the Backrooms movie coming out", "web"),
            ("lock my pc", "system"),
            ("busca información sobre Rust y explícamelo", "web"),
            ("Recuérdame que prefiero el té verde", "memory"),
            ("recordame que prefiero el café sin azúcar", "memory"),
            (
                "cuando diga evidencia quiero que tomes una captura de pantalla de la ventana activa",
                "routine",
            ),
        ):
            with self.subTest(text=text):
                reviewed = reviewed_semantic_expectation(text)
                self.assertEqual(reviewed["expected_effect"], "operation")
                self.assertEqual(reviewed["families"], [expected_family])
        for text in (
            "sonorito, ¿ya?",
            "Steam, lo otro también",
            "buscame pro",
            "Find the result of 7 raised to the power of 3 (7³).",
            "consulta una app por nombre en español/inglés",
            "no, dejalo, cierrala",
            "abre ese pdf ahora",
            "abre la cuestión del volumen",
            "por favor bájalo",
            "la que estaba ahí",
            "mirar lo de las fotos",
            "agenda next",
            "I need my list",
            "run npm install",
            "Sub zero le gana a kung lao?",
            "Reproduce el último video que vi",
            "Reproducí el último video que vi",
            "Can you remind me about the meeting later",
            "por favor el volumen",
            "Please deduplicate my stored files",
            "Tiempo",
            "¿Puedes ver si tengo comprado ese juego en Steam?",
            "ve a mi biblioteca",
        ):
            with self.subTest(text=text):
                reviewed = reviewed_semantic_expectation(text)
                self.assertEqual(reviewed["expected_effect"], "none")
                self.assertEqual(reviewed["families"], [])
        self.assertEqual(
            reviewed_semantic_expectation(
                "Could you sort the words from longest to shortest?"
            )["expected_effect"],
            "review_required",
        )

    def test_final22_oracle_distinguishes_missing_targets_from_executable_requests(self):
        for text in (
            "Resume este PDF",
            "summarize this document",
            "te pedi que lo instales, no que habras la pagina",
            "install it instead of opening its page",
        ):
            with self.subTest(text=text):
                reviewed = reviewed_semantic_expectation(text)
                self.assertIsNotNone(reviewed)
                self.assertEqual(reviewed["expected_effect"], "none")

        expected = (
            ("taskkill /F /IM steam.exe", "system"),
            ("matá Steam a la fuerza con taskkill", "system"),
            ("¿Puedes hacer un respaldo ahora mismo?", "backup"),
            ("make a backup right now", "backup"),
            ("Restaura mi respaldo, por favor", "backup"),
            ("Respaldo de datos, por favor", "backup"),
            ("comprime mi escritorio en un zip", "backup"),
            ("info de la película", "web"),
            ("o que está tocando", "media"),
            ("Quiero ver bane", "web"),
            ("saber la cita", "calendar"),
            ("verificar dns rápido", "network"),
            ("ping el nodo", "network"),
            ("ping google.com", "network"),
            ("show whoami", "system"),
            ("recordame la reunión mañana 9am", "notification"),
            ("Juega cualquier cosa", "game"),
            ("déconnecte ma session", "system"),
            ("metti qui la cosa", "clipboard"),
        )
        for text, family in expected:
            with self.subTest(text=text):
                reviewed = reviewed_semantic_expectation(text)
                self.assertIsNotNone(reviewed)
                self.assertEqual(reviewed["expected_effect"], "operation")
                self.assertIn(family, reviewed["families"])

    def test_write_or_type_requires_literal_content_not_only_constraints(self):
        for text in (
            "Escribe la frase en español",
            "Escribí el texto en inglés",
            "Escribe en el bloc de notas",
            "Type the sentence in Spanish",
            "Write the text in English",
            "Type in Notepad",
            "Write in uppercase",
        ):
            with self.subTest(text=text):
                result = reviewed_semantic_expectation(text)
                self.assertEqual(result["expected_effect"], "none")
                self.assertEqual(result["families"], [])
                self.assertEqual(
                    result["review_rule"],
                    "write_or_type_literal_content_missing_requires_clarification",
                )

        for text in (
            "escribí 12+12",
            "type 5+3",
            "escribe hola en español",
            "type hello in Notepad",
        ):
            with self.subTest(text=text):
                self.assertFalse(
                    reviewed_semantic_expectation(text) is not None
                    and reviewed_semantic_expectation(text).get("review_rule")
                    == "write_or_type_literal_content_missing_requires_clarification"
                )

    def test_bare_selector_requires_context_but_explicit_media_target_does_not(self):
        for text in (
            "Próximo",
            "siguiente uno",
            "el siguiente",
            "the previous one",
            "next",
            "Anterior",
        ):
            with self.subTest(text=text):
                result = reviewed_semantic_expectation(text)
                self.assertEqual(result["expected_effect"], "none")
                self.assertEqual(result["families"], [])
                self.assertEqual(
                    result["review_rule"],
                    "bare_context_dependent_selector_requires_clarification",
                )

        for text in (
            "next track please",
            "play next one",
            "poné la siguiente canción",
            "siguiente cancion",
        ):
            with self.subTest(text=text):
                result = reviewed_semantic_expectation(text)
                self.assertFalse(
                    result is not None
                    and result.get("review_rule")
                    == "bare_context_dependent_selector_requires_clarification"
                )

    def test_bare_name_location_question_does_not_authorize_file_search(self):
        for text in (
            "pórtico onde tá o nome",
            "dónde está el nombre",
            "onde está o nome",
            "where is the name",
        ):
            with self.subTest(text=text):
                result = reviewed_semantic_expectation(text)
                self.assertEqual(result["expected_effect"], "none")
                self.assertEqual(result["families"], [])
                self.assertEqual(
                    result["review_rule"],
                    "bare_name_location_question_has_no_file_search_authority",
                )

        for text in (
            "dónde está el archivo informe.txt",
            "where is the file named report.txt",
        ):
            with self.subTest(text=text):
                result = reviewed_semantic_expectation(text)
                self.assertFalse(
                    result is not None
                    and result.get("review_rule")
                    == "bare_name_location_question_has_no_file_search_authority"
                )
        for text, expected_family in (
            ("olvida todo lo de Carter", "memory"),
            ("borra tus recuerdos sobre mi", "memory"),
            ("recuerda temporalmente que esta corrida es smoke 12", "memory"),
        ):
            with self.subTest(text=text):
                memory = reviewed_semantic_expectation(text)
                self.assertEqual(memory["expected_effect"], "operation")
                self.assertEqual(memory["families"], [expected_family])
        self.assertEqual(
            reviewed_semantic_expectation(
                "Busca información sobre la reunión"
            )["expected_effect"],
            "review_required",
        )
        self.assertEqual(
            reviewed_semantic_expectation("silenzia l audio")["families"],
            ["audio"],
        )
        self.assertEqual(
            reviewed_semantic_expectation("abre Photoshop")["families"],
            ["app"],
        )
        self.assertEqual(
            reviewed_semantic_expectation("abre el editor")["families"],
            ["app"],
        )
        self.assertEqual(
            reviewed_semantic_expectation("abre el navegador pls")["families"],
            ["app"],
        )
        self.assertEqual(
            reviewed_semantic_expectation("recuerda que uso Windows")["families"],
            ["memory"],
        )
        self.assertEqual(
            reviewed_semantic_expectation("abre Chrome y busca Carter")["families"],
            ["web"],
        )
        self.assertEqual(
            reviewed_semantic_expectation("Abre Portal desde Steam")["families"],
            ["game"],
        )
        self.assertEqual(
            reviewed_semantic_expectation("y en Tokio?")["expected_effect"],
            "review_required",
        )
        self.assertEqual(
            reviewed_semantic_expectation("Pode ler este texto por favor")["families"],
            ["vision"],
        )
        self.assertEqual(
            reviewed_semantic_expectation("fug es ein")["expected_effect"],
            "none",
        )
        self.assertEqual(
            reviewed_semantic_expectation("donde esta la info")["expected_effect"],
            "none",
        )
        for text, family in (
            ("¿Qué hora es?", "system"),
            ("cuánta memoria me queda libre", "system"),
            ("navegá a youtube.com", "browser"),
            ("buscá el clima en Madrid", "web"),
            ("cerrá chrome", "app"),
            ("spring zum nächsten Lied", "media"),
            ("busca en mis apuntes qué decía sobre la fotosíntesis", "note_task"),
        ):
            with self.subTest(text=text):
                self.assertIn(
                    family,
                    reviewed_semantic_expectation(text)["families"],
                )
        for text in (
            "qué es Python",
            "what does CPU stand for",
            "who directed Oppenheimer",
            "Connais-tu des chansons de Drake?",
            "Conosci qualche canzone di Tini?",
            "Have you heard any songs by Rosalía?",
            "¿Has visto la película Dune?",
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    reviewed_semantic_expectation(text)["expected_effect"],
                    "none",
                )

    def test_model_gate_assesses_operations_without_executing_them(self):
        oracle = {
            "expected_effect": "operation",
            "expected_families": ["vision"],
        }
        status, families = assess(
            oracle,
            {"type": "turn.result", "kind": "plan"},
            {
                "type": "plan.result",
                "kind": "plan",
                "steps": [{"operation": "capture.screenshot"}],
            },
        )

        self.assertEqual(status, "pass_operation_family")
        self.assertEqual(families, ["vision"])
        self.assertEqual(operation_family("ocr.read"), "vision")
        browser_status, _ = assess(
            {
                "expected_effect": "operation",
                "expected_families": ["browser"],
            },
            {"type": "turn.result", "kind": "plan"},
            {
                "type": "plan.result",
                "kind": "plan",
                "steps": [{"operation": "web.search"}],
            },
        )
        self.assertEqual(browser_status, "pass_operation_family")

    def test_model_gate_uses_turn_reply_without_a_second_conversation_request(self):
        class ConversationMind:
            def __init__(self):
                self.calls = []

            def request(self, message, timeout, *, expected_type):
                self.calls.append((message, timeout, expected_type))
                return {
                    "type": "turn.result",
                    "id": message["id"],
                    "kind": "conversation",
                    "operation": None,
                    "question": "",
                    "reply": "La RAM es memoria de trabajo temporal.",
                }

        mind = ConversationMind()
        turn, plan, turn_seconds, plan_seconds = request_turn_and_optional_plan(
            mind,
            "case-conversation",
            "¿Qué es la RAM?",
        )

        self.assertEqual(turn["reply"], "La RAM es memoria de trabajo temporal.")
        self.assertIsNone(plan)
        self.assertGreaterEqual(turn_seconds, 0)
        self.assertEqual(plan_seconds, 0)
        self.assertEqual(
            mind.calls,
            [
                (
                    {
                        "type": "turn.decide",
                        "id": "case-conversation",
                        "text": "¿Qué es la RAM?",
                    },
                    22,
                    "turn.result",
                )
            ],
        )

    def test_model_gate_requests_plan_only_after_turn_plan_decision(self):
        class PlanningMind:
            def __init__(self):
                self.calls = []

            def request(self, message, timeout, *, expected_type):
                self.calls.append((message, timeout, expected_type))
                if message["type"] == "turn.decide":
                    return {
                        "type": "turn.result",
                        "id": message["id"],
                        "kind": "plan",
                        "operation": None,
                        "question": "",
                        "reply": "",
                    }
                return {
                    "type": "plan.result",
                    "id": message["id"],
                    "kind": "plan",
                    "question": "",
                    "steps": [{"operation": "system.time", "arguments": {}}],
                }

        mind = PlanningMind()
        turn, plan, turn_seconds, plan_seconds = request_turn_and_optional_plan(
            mind,
            "case-plan",
            "Dime la hora y el estado del equipo",
        )

        self.assertEqual(turn["kind"], "plan")
        self.assertEqual(plan["kind"], "plan")
        self.assertGreaterEqual(turn_seconds, 0)
        self.assertGreaterEqual(plan_seconds, 0)
        self.assertEqual(
            mind.calls,
            [
                (
                    {
                        "type": "turn.decide",
                        "id": "case-plan",
                        "text": "Dime la hora y el estado del equipo",
                    },
                    22,
                    "turn.result",
                ),
                (
                    {
                        "type": "plan",
                        "id": "case-plan_plan",
                        "text": "Dime la hora y el estado del equipo",
                    },
                    60,
                    "plan.result",
                ),
            ],
        )

    def test_model_gate_assesses_direct_turn_action_without_calling_plan(self):
        status, families = assess(
            {"expected_effect": "operation", "expected_families": ["app"]},
            {
                "type": "turn.result",
                "kind": "action",
                "operation": "app.open",
                "question": "",
                "reply": "",
            },
            None,
            "abre la calculadora",
        )

        self.assertEqual(status, "pass_operation_family")
        self.assertEqual(families, ["app"])
        pointer_status, pointer_families = assess(
            {"expected_effect": "operation", "expected_families": ["input"]},
            {
                "type": "turn.result",
                "kind": "action",
                "operation": "input.pointer.control",
                "question": "",
                "reply": "",
            },
            None,
            "Mueve el mouse al centro de la pantalla",
        )
        self.assertEqual(pointer_status, "pass_operation_family")
        self.assertEqual(pointer_families, ["input"])

    def test_model_gate_does_not_accept_plan_as_conversation_generator(self):
        status, _ = assess(
            {"expected_effect": "none", "expected_families": []},
            {
                "type": "turn.result",
                "kind": "plan",
                "operation": None,
                "question": "",
                "reply": "",
            },
            {
                "type": "plan.result",
                "kind": "conversation",
                "question": "",
                "steps": [],
            },
            "¿Qué es la RAM?",
        )

        self.assertEqual(status, "invalid_conversation")

    def test_model_gate_rejects_same_family_with_wrong_physical_semantics(self):
        oracle = {"expected_effect": "operation", "expected_families": ["input"]}
        wrong, _ = assess(
            oracle,
            {"type": "turn.result", "kind": "plan"},
            {
                "type": "plan.result",
                "kind": "plan",
                "steps": [{"operation": "input.select.all", "arguments": {}}],
            },
            "Mueve el mouse al centro de la pantalla",
        )
        correct, _ = assess(
            oracle,
            {"type": "turn.result", "kind": "plan"},
            {
                "type": "plan.result",
                "kind": "plan",
                "steps": [{
                    "operation": "input.pointer.control",
                    "arguments": {"action": "move_center"},
                }],
            },
            "Mueve el mouse al centro de la pantalla",
        )
        mouse_inventory, _ = assess(
            {"expected_effect": "operation", "expected_families": ["peripheral"]},
            {"type": "turn.result", "kind": "plan"},
            {
                "type": "plan.result",
                "kind": "plan",
                "steps": [{
                    "operation": "peripheral.list",
                    "arguments": {"kind": "mouse"},
                }],
            },
            "que mouse tengo?",
        )

        self.assertEqual(wrong, "wrong_operation")
        self.assertEqual(correct, "pass_operation_family")
        self.assertEqual(mouse_inventory, "pass_operation_family")

    def test_oracle_recognizes_newly_verified_physical_input_capabilities(self):
        cases = (
            ("Mueve el mouse al centro de la pantalla", ["input"]),
            ("mouse click there fast", ["input"]),
            ("Presiona control shift escape", ["input"]),
            ("Presiona la tecla Windows", ["input"]),
            ("escribí hola mundo", ["input"]),
            ("type 15*3 in Notepad", ["app", "input"]),
        )
        for text, expected_families in cases:
            with self.subTest(text=text):
                reviewed = reviewed_semantic_expectation(text)
                self.assertEqual(reviewed["expected_effect"], "operation")
                self.assertEqual(reviewed["families"], expected_families)

        for text in (
            "Escribe la frase en español",
            "escribe esto ya",
            "Escribe un email a Sarah, por favor",
            "Escribe un acróstico para la palabra campo",
        ):
            with self.subTest(text=text):
                reviewed = reviewed_semantic_expectation(text)
                self.assertTrue(
                    reviewed is None or "input" not in reviewed.get("families", [])
                )

    def test_model_gate_rejects_effect_for_conversation_and_empty_turn_reply(self):
        no_effect = {"expected_effect": "none", "expected_families": []}
        status, _ = assess(
            no_effect,
            {"type": "turn.result", "kind": "plan"},
            {
                "type": "plan.result",
                "kind": "plan",
                "steps": [{"operation": "app.open"}],
            },
        )
        invalid, _ = assess(
            no_effect,
            {
                "type": "turn.result",
                "kind": "conversation",
                "reply": "",
            },
            None,
        )

        self.assertEqual(status, "false_effect")
        self.assertEqual(invalid, "invalid_conversation")

    def test_model_gate_rejects_planner_errors_disguised_as_conversation(self):
        self.assertEqual(
            conversation_quality(
                "que hora es",
                "Necesito un dato más para producir un plan verificable.",
            ),
            "irrelevant_conversation",
        )
        self.assertEqual(
            conversation_quality(
                "What is RAM?",
                'media(action="play", provider="spotify")',
            ),
            "irrelevant_conversation",
        )
        self.assertIsNone(
            conversation_quality(
                "cuál es la capital de Francia",
                "La capital de Francia es París.",
            )
        )

    def test_model_gate_requires_an_answer_for_grounded_conversation(self):
        status, _ = assess(
            {"expected_effect": "none", "expected_families": []},
            {
                "type": "turn.result",
                "kind": "clarify",
                "question": "¿Qué quieres decir?",
            },
            None,
            "cuál es la capital de Francia",
        )
        safe, _ = assess(
            {"expected_effect": "review_required", "expected_families": []},
            {
                "type": "turn.result",
                "kind": "clarify",
                "question": "¿Qué archivo exacto?",
            },
            None,
            "resume este archivo",
        )

        self.assertEqual(status, "pass_safe_clarification")
        self.assertEqual(safe, "pass_safe_clarification")

    def test_model_gate_process_lock_detects_live_and_stale_owners(self):
        self.assertTrue(process_exists(os.getpid()))
        self.assertFalse(process_exists(2_147_483_647))
        self.assertIsNotNone(process_start_time(os.getpid()))
        self.assertIsNone(process_start_time(2_147_483_647))

    def test_historical_hint_bank_contains_no_text_arguments_or_authority(self):
        text = "historical request"
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        rows = hint_rows([
            {
                "text_sha256": text_hash,
                "expected_effect": "operation",
                "expected_families": ["vision"],
            },
            {
                "text_sha256": "b" * 64,
                "expected_effect": "review_required",
                "expected_families": [],
            },
        ])
        registry = HistoricalIntentRegistry(rows)

        self.assertEqual(len(rows), 1)
        self.assertNotIn("text_literal", rows[0])
        self.assertNotIn("arguments", rows[0])
        self.assertTrue(
            operation_allowed_by_hint("capture.screenshot", registry.lookup(text))
        )


if __name__ == "__main__":
    unittest.main()
