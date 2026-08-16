---
name: whatsapp-messaging
description: Resolve a WhatsApp contact or group and send one exact message without cross-chat leakage.
operations:
  - message.recipient.resolve
  - message.send
priority: 90
---
# WhatsApp messaging

Resolve the exact contact or group with `channel=whatsapp`. The resolver must
verify the selected chat identity and return a single `recipientId`; a search
term alone is not an identity. Then send the user-provided body unchanged with
`message.send`. Require a receipt or visible postcondition bound to both chat and
body. Never press Enter when the active application or selected chat cannot be
verified. Do not duplicate a send after an ambiguous response.
