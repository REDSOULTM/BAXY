session(action='cancel_turn'): the ONLY valid action. Use when the user interrupts/aborts mid-turn (any phrasing/language: stop, wait, hold on, cancel). NOT a domain tool — no filesystem/network/etc.
DO NOT invent other actions. session(action='search') was a hallucination (Bug D4) — that intent belongs to web(...). Only cancel_turn is valid.
