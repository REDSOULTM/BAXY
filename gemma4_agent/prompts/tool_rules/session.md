Session rule: session(action='cancel_turn') is the ONLY available action. Use it when the user is interrupting / aborting the agent mid-turn (any phrasing in any language signaling stop, wait, hold on, cancel). Not a domain tool — does not perform filesystem / network / etc. work.

DO NOT invent other actions. session(action='search') was a real hallucination from Bug D4 — that intent belongs to web(...). The only valid action is cancel_turn.
