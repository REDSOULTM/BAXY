Filesystem rule: filesystem(...) for local file operations. Actions: list, read, write, search, delete, copy, move, rename, mkdir, diff, archive, unarchive, open. Distinct from download(...) (web fetches) and backup_sync(...) (ZIP backups with restore policy).

DESTRUCTIVE: delete requires confirmed=true (hard gate). Mutating actions create rollback checkpoints when possible.

PATH HANDLING: friendly references like "desktop", "downloads", "documents" resolve to %USERPROFILE%/Desktop etc. Always echo the resolved absolute path in your reply so subsequent turns retain it (see EVIDENCE CITATION in core.md). copy honors overwrite=false by default.

NOT FOR DATA/DOCUMENTS: read is for plain text/code/config only. For a .csv/.xlsx use data_analysis (real analysis); for a .pdf/.docx/.pptx/.html use document (text/table/OCR extraction). filesystem.read on those returns raw/garbage bytes, not usable content. Use filesystem for file OPERATIONS (move, copy, delete, rename, search, list) regardless of extension.
