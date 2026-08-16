---
name: discord-messaging
description: Resolve one Discord destination and send exactly one user-provided message with a receipt.
operations:
  - message.recipient.resolve
  - message.send
priority: 90
---
# Discord messaging

Use `message.recipient.resolve` first with `channel=discord` and the exact visible
recipient or channel name. Continue only when it returns one unambiguous
`recipientId`. Pass that observed ID to `message.send`; never invent it and never
reuse an ID for another recipient. Preserve the message text exactly. A changed
window or a keypress is not delivery evidence: require the provider receipt tied
to the destination and content. If resolution is ambiguous, clarify before any
send. One request means one send; retries reuse the same operation identity.
