Skill-load rule: skill_load(...) reads the full body of a skill recipe by name. The agent advertises available skills in the system prompt under # SKILLS AVAILABLE.

Call this tool ONLY when the user's request matches one of the listed skill descriptions. The tool result is the markdown recipe you must follow for the rest of the turn.

NOT a domain tool — does not act on filesystem / OS. Do not invent skill names; only load names that appear in the menu. Per-turn cap applies.
