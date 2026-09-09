---
name: office-documents
description: Create or read an Office document using exact paths and verified document identity.
operations:
  - office.document.create
  - office.document.read
priority: 70
---
# Office documents

Create only the requested `docx` or `xlsx` title with
`office.document.create`; missing format or title requires clarification. The
provider chooses a new non-overwriting file under the user's BAXY documents
folder and returns an opaque document ID. Verify by reopening that exact
identity, not by observing that an Office app launched. `office.document.read`
must depend on the create step and consume its observed document ID when the
user says to read the same newly created document. A title is never a
`documentId`; never invent a path or ID.
