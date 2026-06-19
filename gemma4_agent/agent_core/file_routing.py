"""Ruteo de tools por EXTENSIÓN de archivo (estado del archivo), extraído de
agent.py (split del archivo-dios, 2026-06-19). Para lectura/análisis de datos o
documentos quita filesystem (lectura cruda inútil) y asegura la tool específica
(.csv/.xlsx -> data_analysis; .pdf/.docx/... -> document); para búsqueda de
archivos locales quita web. Señal ESTRUCTURAL (extensión + verbo), no keywords de
contenido. Puro (solo re/os + un lazy import de file_process). agent.py re-exporta.
"""
from __future__ import annotations


def _file_tool_routing_enabled() -> bool:
    """Bug medido en vivo: el 4B prefería filesystem.read sobre
    data_analysis (.csv/.xlsx) y document (.pdf/.docx/.pptx/.html), dando lecturas
    crudas SIN análisis / binario sin decodificar. GEMMA4_FILE_TOOL_ROUTING default
    ON (validado 6/6 en vivo + suite verde; kill-switch =0). Las
    reglas de tool no bastaron solas (1/6 en vivo); costo = unos regex en el subset."""
    import os as _os_fr
    return (_os_fr.environ.get("GEMMA4_FILE_TOOL_ROUTING", "1") or "1").strip().lower() not in {
        "0", "false", "no", "off"}


def _file_processor_on() -> bool:
    """Gate (lazy): ¿ofrecer la tool unificada file_process en el subset?
    GEMMA4_FILE_PROCESSOR (default-off). Sin él, file-routing rutea a
    document/data_analysis como siempre (file_process queda inerte)."""
    try:
        from ..domain_tools.file_process import file_processor_enabled
        return file_processor_enabled()
    except Exception:
        return False


def _route_file_by_extension(content: str, names: list[str]) -> list[str]:
    """Para LECTURA/ANÁLISIS de un archivo de datos/documento (por EXTENSIÓN = estado
    del archivo), quita filesystem (lectura cruda inútil) y asegura la tool específica:
    .csv/.xlsx -> data_analysis; .pdf/.docx/.pptx/.html -> document. NO aplica si hay
    verbo de file-op (mover/borrar/copiar/listar): ahí filesystem se queda.
    Si GEMMA4_FILE_PROCESSOR está on, AGREGA file_process (entrada unificada)
    para data/doc — additivo, document/data_analysis quedan de fallback."""
    import re as _re
    low = (content or "").lower()
    if _re.search(r"\b(borr[aá]|borrar|borralo|elimin[aá]|eliminar|mueve|mov[eé]|"
                  r"mover|movelo|copi[aá]|copiar|renombr[aá]|renombrar|comprime|"
                  r"comprim[ií]|comprimir|archiv[aá]|archivar|"
                  r"delete|move|copy|rename|archive|compress|zip)\b", low):
        return names  # file-op MUTANTE (borrar/mover/...) -> filesystem se queda
        # (listar/buscar NO mutan -> caen al routing local de abajo, que sí necesita filesystem)
    is_data = bool(_re.search(r"\.(csv|xlsx?)\b", low))
    is_doc = bool(_re.search(r"\.(pdf|docx?|pptx?|html?)\b", low))
    if is_data:
        # DATA: medido en vivo 3/3 — sin filesystem compitiendo, el 4B usa
        # data_analysis con la action correcta (csv_query/describe). Lo sacamos.
        out = [t for t in names if t != "filesystem"]
        if _file_processor_on() and "file_process" not in out:
            out.append("file_process")  # opt-in: entrada unificada
        if "data_analysis" not in out:
            out.append("data_analysis")
        return out
    if is_doc:
        # DOC: additivo (NO sacar filesystem). Medido: sacarlo EMPEORA a "sin-tool"
        # — el 4B insiste en filesystem.read para "leer" (prior arraigado). Lo
        # dejamos y filesystem.read delega a document para .pdf/.docx (ver tools.py).
        out = list(names)
        if _file_processor_on() and "file_process" not in out:
            out.append("file_process")  # opt-in: entrada unificada
        if "document" not in out:
            out.append("document")
        return out
    # Búsqueda de archivos LOCALES (folder ref + tipo de archivo + verbo de
    # búsqueda/apertura) -> filesystem, NO web. Bug medido:
    # "buscá un word en documentos" -> web (internet) 0/4. El usuario quiere SU archivo,
    # no resultados de internet. Estructural (señal de carpeta local + tipo).
    if (_re.search(r"\b(documentos?|descargas?|downloads|escritorio|desktop|carpeta|m[uú]sica|musica|videos?)\b", low)
            and _re.search(r"\b(word|docx?|pdf|excel|xlsx?|archivos?|files?|documentos?|fotos?|im[aá]genes?|imagen|canci[oó]n|m[uú]sica|musica|videos?|mp3|mp4|pptx?)\b", low)
            and _re.search(r"\b(busc|encontr|list|mostr|abr|reproduc|trae|tra[eé]|dame|necesito)\w*", low)):
        out = [t for t in names if t != "web"]
        if "filesystem" not in out:
            out.append("filesystem")
        return out
    return names
