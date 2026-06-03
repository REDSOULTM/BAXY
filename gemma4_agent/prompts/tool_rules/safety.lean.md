safety(...): confirmation surface for DESTRUCTIVE actions. Actions: status|pending|confirm|cancel.
NOT a domain tool — no filesystem/network/OS work. Sole job: another tool returns needs_confirmation -> you ask the user -> after EXPLICIT approval call safety(action='confirm', confirmation_id='...'); on rejection call safety(action='cancel', ...).
NEVER call confirm without the user clearly saying yes THIS turn. confirmation_id ALWAYS comes from a prior tool result — never invent one.
