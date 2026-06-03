Filesystem rule: filesystem(...) for local file OPERATIONS. Actions: list, read, write, search, delete, copy, move, rename, mkdir, diff, archive, unarchive, open.
- Distinct from download(...) (web fetches) and backup_sync(...) (ZIP backups w/ restore policy).

DESTRUCTIVE: delete requires confirmed=true (hard gate). Mutating actions create rollback checkpoints when possible.

PATH HANDLING: "desktop"/"downloads"/"documents" resolve to %USERPROFILE%/Desktop etc. ALWAYS echo the resolved absolute path in your reply so next turns retain it (see EVIDENCE CITATION in core.md). copy honors overwrite=false by default.

NOT FOR DATA/DOCUMENTS: read = plain text/code/config ONLY.
- .csv/.xlsx -> data_analysis (real analysis).
- .pdf/.docx/.pptx/.html -> document (text/table/OCR extraction).
- filesystem.read on those returns raw/garbage bytes, not usable content.
- Use filesystem for file OPERATIONS (move, copy, delete, rename, search, list) regardless of extension.
