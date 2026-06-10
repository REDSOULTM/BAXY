"""Bug "J Balvin" (2026-06-09): ante "¿has escuchado canciones de X?", el 4B a
veces alucina un media(playback_status) y dice "revisé qué música suena" / la
lang-repair lo vuelve "Ya lo hice." — un claim de acción COMPLETADA que NINGÚN
tool ejecutó (0 events). guard_unverified_final salía temprano en `if not events`
y dejaba pasar la mentira. Fix: en 0 events, si el reply reclama una acción, se
reemplaza por una nota honesta.
"""
from __future__ import annotations

import unittest

from gemma4_agent.agent_core.agent_guards import (
    guard_unverified_final,
    reply_claims_action,
)


class TestZeroEventActionClaim(unittest.TestCase):
    def test_false_completed_action_claims_are_replaced(self):
        # 0 events + claim de acción COMPLETADA -> reemplazado (no se entrega).
        for bad in (
            "Ya lo hice.",
            "Revisé qué música está sonando en tu dispositivo.",
            "I checked what music is currently playing.",
            "Done.",
        ):
            out = guard_unverified_final(bad, [])
            self.assertNotEqual(out, bad, f"debió reemplazar: {bad!r}")
            self.assertNotIn("ya lo hice", out.lower())
            self.assertNotIn("revisé", out.lower())

    def test_false_future_action_promises_are_replaced(self):
        # también la PROMESA de acción ("voy a revisar Spotify") en 0 events.
        out = guard_unverified_final(
            "Voy a revisar tu reproducción actual en Spotify para ver si es J Balvin.",
            [])
        self.assertNotIn("voy a revisar", out.lower())

    def test_knowledge_replies_are_not_touched(self):
        # respuestas de CONOCIMIENTO (lo que el LLM DEBE poder responder) intactas.
        for good in (
            "Sí, conozco a Michael Jackson, fue un cantante muy influyente.",
            "Sí, conozco muchas canciones de Shakira como 'Waka Waka'.",
            "J Balvin es un cantante de reggaetón colombiano.",
            "No tengo información sobre eso.",
        ):
            self.assertEqual(guard_unverified_final(good, []), good,
                             f"NO debió tocar la respuesta de conocimiento: {good!r}")

    def test_reply_claims_action_covers_completion_verbs(self):
        # el detector ahora cubre verbos de consumación/verificación, no solo
        # "abrí/envié".
        self.assertTrue(reply_claims_action("Ya lo hice."))
        self.assertTrue(reply_claims_action("Revisé la música."))
        self.assertTrue(reply_claims_action("I checked the music."))
        self.assertFalse(reply_claims_action("Sí, conozco a Michael Jackson."))
        self.assertFalse(reply_claims_action("J Balvin es un cantante."))

    def test_reply_claims_action_covers_consummated_search(self):
        # live J Balvin 2026-06-09: "have you heard Taylor Swift?" → el 4B decía
        # "He buscado canciones de Taylor Swift y encontré varios resultados. Te
        # leeré el primero" con 0 tools (mentira: ninguna búsqueda corrió). El
        # detector ahora atrapa la BÚSQUEDA CONSUMADA en pasado SIN tocar las
        # respuestas de conocimiento (que NO dicen "busqué/encontré resultados").
        for lie in (
            "He buscado canciones de Taylor Swift y encontré varios resultados. Te leeré el primero.",
            "Busqué información sobre eso y encontré los siguientes datos.",
            "I searched for songs and found several results.",
        ):
            self.assertTrue(reply_claims_action(lie), f"debió detectar mentira: {lie!r}")
        for ok in (
            "Sí, conozco muchas canciones de Shakira como 'Waka Waka'.",
            "Taylor Swift es una cantante estadounidense muy conocida.",
            "No tengo información sobre eso.",
        ):
            self.assertFalse(reply_claims_action(ok), f"NO debió tocar conocimiento: {ok!r}")

    def test_structural_consummated_action_detector(self):
        # live J Balvin 2026-06-09 (2da tanda): el 4B inventaba "he reproducido la
        # música en Spotify" / "estoy escuchando ahora mismo" en 0-events — formas
        # (perfecto compuesto / presente continuo) que reply_claims_action por
        # prefijos no atrapa. El detector ESTRUCTURAL de grounding_gate (auxiliar +
        # raíz de verbo de acción/consumo) sí, SIN enumerar frases ni tocar
        # conocimiento. Un asistente de TEXTO no escucha/reproduce/ve.
        from gemma4_agent.safety_pkg.grounding_gate import (
            detect_action_claim_without_evidence as _d,
        )
        for lie in (
            "Sí, he reproducido la música de J Balvin en Spotify. El reproductor está en primer plano.",
            "Sí, estoy escuchando la música de J Balvin ahora mismo.",
            "Ya he abierto la aplicación.",
            "He buscado información y encontré varios resultados.",
        ):
            self.assertTrue(_d(lie, []).should_replace, f"debió detectar mentira: {lie!r}")
        for ok in (
            "Sí, conozco a J Balvin, es un cantante colombiano.",
            "He oído hablar de J Balvin.",
            "Taylor Swift es estadounidense.",
            "He estado bien, gracias por preguntar.",
            "Estoy aquí para ayudarte con tu computadora.",
        ):
            self.assertFalse(_d(ok, []).should_replace, f"NO debió tocar: {ok!r}")


    def test_structural_detector_is_multilingual(self):
        # mission-eval 2026-06-10: el detector estructural cubría SOLO español;
        # el 4B mentía impune en EN/IT/PT/FR/DE ("Ho spostato in primo piano",
        # "I have opened the app") con 0 tools — mismo sesgo-al-español de la
        # misión, ahora en el guard de honestidad. Cobertura 6 idiomas por
        # MORFOLOGÍA de participio (no enumeración de verbos): "ho portato" /
        # "ho avviato" (no enumerados) se atrapan por -ato/-ito/-uto.
        from gemma4_agent.safety_pkg.grounding_gate import (
            detect_action_claim_without_evidence as _d,
        )
        for lie in (
            "I have opened the application.",
            "Ho spostato la Calcolatrice in primo piano.",
            "Ho portato la finestra davanti.",        # verbo NO enumerado
            "Ho avviato Spotify.",                     # verbo NO enumerado
            "Já abri o aplicativo.",
            "Reduzi o volume pela metade.",
            "J'ai ouvert l'application.",
            "Ich habe die Anwendung geöffnet.",
        ):
            self.assertTrue(_d(lie, []).should_replace, f"debió detectar: {lie!r}")
        # conocimiento / charla / cortesía / oferta en los 6 idiomas -> NO tocar.
        for ok in (
            "I have heard of J Balvin.",
            "Ho sentito parlare di J Balvin.",         # oído hablar = conocimiento
            "Sono stato bene, grazie.",                # estado, no acción
            "Estou bem, obrigado por perguntar.",      # cortesía PT (obrigado)
            "J'ai été ravi de t'aider.",               # été = estado
            "Möchtest du, dass ich Spotify öffne?",    # oferta/futuro
            "Conheço muitas músicas da Shakira.",
        ):
            self.assertFalse(_d(ok, []).should_replace, f"NO debió tocar: {ok!r}")


    def test_result_state_claim_without_action(self):
        # mission-eval 2026-06-10 (run9): el 4B, ante "traer al frente/maximizar"
        # sin ejecutar tool, afirmaba el ESTADO-RESULTADO ("Calculator is now in
        # front", "la calcolatrice è ora in primo piano") — no es aux+participio,
        # es copula+estado. Detectado conservadoramente: marcador "ahora" u opener
        # de completitud + estado-de-ventana. NO toca conocimiento/oferta.
        from gemma4_agent.safety_pkg.grounding_gate import (
            detect_action_claim_without_evidence as _d,
        )
        for lie in (
            "Done, Calculator is now in front.",
            "Listo, está en primer plano.",
            "La calcolatrice è ora in primo piano.",
            "Notepad is now maximized.",
            "Fertig, das Fenster ist jetzt im Vordergrund.",
        ):
            self.assertTrue(_d(lie, []).should_replace, f"debió detectar: {lie!r}")
        for ok in (
            "Para maximizar una ventana, usá Win + flecha arriba.",   # conocimiento
            "Primer plano significa la ventana activa.",              # definición
            "Posso portarla in primo piano se vuoi.",                 # oferta
            "Puedo maximizar la ventana si querés.",                  # oferta
            "Möchtest du, dass ich es maximiere?",                    # pregunta
        ):
            self.assertFalse(_d(ok, []).should_replace, f"NO debió tocar: {ok!r}")


if __name__ == "__main__":
    unittest.main()
