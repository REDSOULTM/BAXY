Document ingestion rule: read / summarize / extract text|tables|images / analyze a PDF/DOCX/XLSX/PPTX/HTML file -> document(action="extract_text|extract_tables|extract_images|ocr_pdf|summarize|ingest_to_knowledge|compare_documents"). Prefer over filesystem.read for binary office formats.
- document.summarize returns text_preview ONLY; you must write the summary from that preview yourself.

ALWAYS use document (NOT filesystem.read) for .pdf/.docx/.pptx/.html — even with generic verbs ("what does X say", "read X", "summarize X", "what's in X"). filesystem.read on these returns garbage binary (compressed PDF/OOXML streams); document.extract_text decodes them properly.
