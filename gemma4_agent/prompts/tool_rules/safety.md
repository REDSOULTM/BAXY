Safety rule: safety(...) is the confirmation surface for destructive actions. Actions: status, pending, confirm, cancel.

NOT a domain tool — it does not perform filesystem / network / OS work. Its sole job: when another tool returns needs_confirmation, you ask the user, and after EXPLICIT approval you call safety(action='confirm', confirmation_id='...'). On rejection you call safety(action='cancel', ...).

Never call safety(action='confirm') without the user having clearly said yes in this turn. The confirmation_id always comes from a prior tool result — do not invent one.
