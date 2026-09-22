"""Keep verified observed names opaque to vocabulary checks, not factual checks."""
from __future__ import annotations

import json
import re


def without_observed_names(text: str, situation: object) -> str:
    """Mask complete observed names in a scratch copy; never change public prose.

    Only successful typed observations supply vocabulary. Mission steps
    keep their own verification envelope; merged observations and dialogue do not.
    """
    names: set[str] = set()

    def collect(node: object, depth: int = 0) -> None:
        if depth > 8:
            return
        if isinstance(node, str):
            try:
                node = json.loads(node)
            except (ValueError, TypeError):
                return
        if not isinstance(node, dict):
            return
        operation = node.get("operation")
        if (node.get("kind") == "operation"
                and isinstance(operation, str)
                and (operation.startswith("window.") or operation in {"system.process.list", "app.installed"})
                and node.get("verified") is True and node.get("succeeded") is True
                and node.get("polarity") == "success"):
            observed = node.get("observed")
            if (operation == "app.installed" and isinstance(observed, dict)
                    and observed.get("authority") == "windows_start_catalog_snapshot"):
                # The provider's human-readable authority is observed data too.
                names.update(("catálogo de inicio de Windows", "Windows Start application catalog"))
            process_inventory = operation == "system.process.list"
            entries = observed.get("processes" if process_inventory else "windows") if isinstance(observed, dict) else None
            fields = ("name",) if process_inventory else ("title", "processName")
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        names.update(value for key in fields
                                     if isinstance(value := entry.get(key), str)
                                     and value.strip() and len(value) <= 4096)
        if (node.get("kind") == "operation" and operation == "web.search"
                and node.get("verified") is True and node.get("succeeded") is True
                and node.get("polarity") == "success"):
            # WEB1447 «qué clima hace hoy»: a result's title and host («tiempo.cl»,
            # «eltiempoen.com») are observed data, not dotted operation names.
            observed = node.get("observed")
            found = observed.get("results") if isinstance(observed, dict) else None
            if isinstance(found, list):
                for entry in found:
                    if not isinstance(entry, dict):
                        continue
                    title = entry.get("title")
                    if isinstance(title, str) and 0 < len(title.strip()) <= 4096:
                        names.add(title.strip())
                    url = entry.get("url")
                    if isinstance(url, str):
                        host = re.match(r"^(?:https?://)?(?:www\.)?([^/?#]+)", url)
                        if host and 0 < len(host.group(1)) <= 253:
                            names.add(host.group(1))
        if (node.get("kind") == "operation" and operation == "web.news.headlines"
                and node.get("verified") is True and node.get("succeeded") is True
                and node.get("polarity") == "success"):
            # NEWS2027 «buscá noticias de hoy»: a headline's title and its source
            # («cooperativa.cl», «dw.com») are observed data, not dotted codes.
            observed = node.get("observed")
            found = observed.get("headlines") if isinstance(observed, dict) else None
            if isinstance(found, list):
                for entry in found:
                    if isinstance(entry, dict):
                        names.update(value.strip() for key in ("title", "source")
                                     if isinstance(value := entry.get(key), str) and 0 < len(value.strip()) <= 4096)
        if node.get("kind") == "confirmation":
            # H0081 «quiero que abras opera gx y entras a pivigames» → «¿Quieres
            # confirmar o cancelar que abra Opera GX y entre a pivigames.es?»: the
            # host of the navigation proposed for confirmation is observed data
            # (it came from the verified search), not a dotted operation name.
            pending = node.get("pendingAction")
            arguments = pending.get("arguments") if isinstance(pending, dict) else None
            url = arguments.get("url") if isinstance(arguments, dict) else None
            if isinstance(url, str):
                host = re.match(r"^(?:https?://)?(?:www\.)?([^/?#]+)", url)
                if host and 0 < len(host.group(1)) <= 253:
                    names.add(host.group(1))
        if (node.get("kind") == "operation" and operation in {"browser.navigate", "browser.navigate.named"}
                and node.get("verified") is True and node.get("succeeded") is True
                and node.get("polarity") == "success"):
            # The host the browser actually reached («entré a pivigames.es») is
            # observed data as much as a search result's host.
            observed = node.get("observed")
            url = observed.get("finalUrl") if isinstance(observed, dict) else None
            if isinstance(url, str):
                host = re.match(r"^(?:https?://)?(?:www\.)?([^/?#]+)", url)
                if host and 0 < len(host.group(1)) <= 253:
                    names.add(host.group(1))
        if (node.get("kind") == "operation" and operation in {"message.send.test", "message.draft"}
                and node.get("verified") is True and node.get("succeeded") is True
                and node.get("polarity") == "success"):
            # MAIL1853 «escribile un mail a X» sent to the owner's test mailbox: the
            # forced destination («autor@example.com»), the requested
            # recipient (an address, a name, the survey's «[EMAIL_REDACTED]») and the
            # sent text are observed data, never dotted or snake-cased codes.
            observed = node.get("observed")
            if isinstance(observed, dict):
                names.update(value.strip() for key in ("forcedDestination", "requestedRecipient", "displayName", "text")
                             if isinstance(value := observed.get(key), str) and 0 < len(value.strip()) <= 4096)
        if (node.get("kind") == "operation" and operation == "notification.list"
                and node.get("verified") is True and node.get("succeeded") is True
                and node.get("polarity") == "success"):
            # AGENDA1435 «listá los timers»: a scheduled title is observed data.
            observed = node.get("observed")
            scheduled = observed.get("notifications") if isinstance(observed, dict) else None
            if isinstance(scheduled, list):
                names.update(title.strip() for entry in scheduled if isinstance(entry, dict)
                             and isinstance(title := entry.get("title"), str)
                             and 0 < len(title.strip()) <= 4096)
        if (node.get("kind") == "operation"
                and operation in {"media.play.youtube", "media.play.query", "media.play.exact"}
                and node.get("verified") is True and node.get("succeeded") is True
                and node.get("polarity") == "success"):
            # MUSIC1749 «pon michael jackson en spotify»: the observed title («… I
            # Just Can't Stop Loving You …») is data in its own language.
            observed = node.get("observed")
            if isinstance(observed, dict):
                for key in ("title", "artist"):
                    value = observed.get(key)
                    if isinstance(value, str) and 0 < len(value.strip()) <= 4096:
                        names.add(value.strip())
        if (node.get("kind") == "operation" and operation == "filesystem.known.list"
                and node.get("verified") is True and node.get("succeeded") is True
                and node.get("polarity") == "success"):
            # FILES1425 «lista los archivos del escritorio»: a listed name is
            # observed data (dots, hyphens and underscores included).
            observed = node.get("observed")
            listed = observed.get("entries") if isinstance(observed, dict) else None
            if isinstance(listed, list):
                names.update(name.strip() for entry in listed if isinstance(entry, dict)
                             and isinstance(name := entry.get("name"), str)
                             and 0 < len(name.strip()) <= 4096)
        if (node.get("kind") == "operation" and operation == "filesystem.write.text"
                and node.get("verified") is True and node.get("succeeded") is True
                and node.get("polarity") == "success"):
            # FILES1709 «crea un archivo de texto con los 5 procesos que más
            # memoria usan»: the name of the file just written («procesos-memoria.txt»)
            # is observed data the report must say, not a dotted operation name.
            observed = node.get("observed")
            written = observed.get("name") if isinstance(observed, dict) else None
            if isinstance(written, str) and 0 < len(written.strip()) <= 4096:
                names.add(written.strip())
        if (node.get("kind") == "operation"
                and operation in {"document.text.read", "document.pdf.read"}
                and node.get("verified") is True and node.get("succeeded") is True
                and node.get("polarity") == "success"):
            # TEXTREAD2063 H0299: what the file says is the file's own words.
            # The ROADMAP the person pasted reads «lee el catalogo» and the
            # final that quotes it died in forbidden_term. The read text, its
            # headings and each of its lines are observed data, not the
            # assistant's vocabulary.
            observed = node.get("observed")
            if isinstance(observed, dict):
                for key in ("text", "lead"):
                    value = observed.get(key)
                    if isinstance(value, str) and value.strip():
                        names.add(value.strip())
                        names.update(
                            line.strip() for line in value.splitlines() if len(line.strip()) >= 3
                        )
                headings = observed.get("headings")
                if isinstance(headings, list):
                    names.update(
                        item.strip() for item in headings
                        if isinstance(item, str) and item.strip()
                    )
                label = observed.get("reviewLabel")
                if isinstance(label, str) and 0 < len(label.strip()) <= 4096:
                    names.add(label.strip())
        if (node.get("kind") == "operation"
                and operation in {"web.download", "file.compress", "file.open", "filesystem.create.directory"}
                and node.get("verified") is True and node.get("succeeded") is True
                and node.get("polarity") == "success"):
            # DOWNLOAD2047 «descarga la imagen de portada de wikipedia.org»: the
            # file just written («250px-Wikipedia-logo-v2.svg.png»), the zip
            # («Nueva carpeta.zip») and the source's host are observed data the
            # report must say, not dotted operation names.
            observed = node.get("observed")
            if isinstance(observed, dict):
                names.update(value.strip() for key in ("name", "zipName")
                             if isinstance(value := observed.get(key), str) and 0 < len(value.strip()) <= 4096)
                url = observed.get("sourceUrl")
                if isinstance(url, str):
                    host = re.match(r"^(?:https?://)?(?:www\.)?([^/?#]+)", url)
                    if host and 0 < len(host.group(1)) <= 253:
                        names.add(host.group(1))
        if (node.get("kind") == "operation" and operation == "wifi.scan"
                and node.get("verified") is True and node.get("succeeded") is True
                and node.get("polarity") == "success"):
            # NETWORK1729 «qué redes wifi hay»: a visible network name
            # («Fibertel-2.4GHz») is observed data, dots included.
            observed = node.get("observed")
            networks = observed.get("networks") if isinstance(observed, dict) else None
            if isinstance(networks, list):
                names.update(ssid.strip() for network in networks if isinstance(network, dict)
                             and isinstance(ssid := network.get("ssid"), str)
                             and 0 < len(ssid.strip()) <= 4096)
        if (node.get("kind") == "operation" and operation == "ocr.read"
                and node.get("verified") is True and node.get("succeeded") is True
                and node.get("polarity") == "success"):
            # SCREEN1411 «leéme lo que dice la pantalla»: the person asked for the
            # screen's words; a quoted recognized line (identifiers, paths and
            # dotted names included) is observed data, not vocabulary about BAXY.
            observed = node.get("observed")
            recognized = observed.get("text") if isinstance(observed, dict) else None
            if isinstance(recognized, str) and recognized.strip():
                names.update(line.strip() for line in recognized.split("\n")
                             if 1 < len(line.strip()) <= 4096)
                names.update(re.findall(r"[\w-]+(?:[._][\w-]+)+", recognized))
            # SCREEN1421: the provider joins `text` with spaces; the recognized
            # lines (what the composer quotes) live in layout.lines[].text.
            layout = observed.get("layout") if isinstance(observed, dict) else None
            layout_lines = layout.get("lines") if isinstance(layout, dict) else None
            if isinstance(layout_lines, list):
                names.update(line_text.strip() for line in layout_lines if isinstance(line, dict)
                             and isinstance(line_text := line.get("text"), str)
                             and 1 < len(line_text.strip()) <= 4096)
        if (node.get("kind") == "operation" and operation == "media.play.youtube"
                and node.get("verified") is True and node.get("succeeded") is True
                and node.get("polarity") == "success"):
            # MUSIC1573 «poneme una canción» → «algo de jazz»: the observed
            # YouTube title («4K Cozy Coffee Shop with Smooth Piano Jazz Music…»)
            # keeps its own language; quoted in a Spanish reply it is observed
            # data, not the reply's vocabulary.
            observed = node.get("observed")
            title = observed.get("title") if isinstance(observed, dict) else None
            if (isinstance(observed, dict) and observed.get("titleObserved") is True
                    and isinstance(title, str) and 0 < len(title.strip()) <= 4096):
                names.add(title.strip())
        steps = node.get("steps")
        if isinstance(steps, list):
            for step in steps:
                collect(step, depth + 1)

    collect(situation)
    if not names:
        return text
    # Do not hide part of a dotted/hyphenated identifier. A sentence-ending dot
    # is punctuation, whereas a dot or hyphen followed by a word extends it.
    pattern = r"(?<![\w.-])(?:" + "|".join(re.escape(name) for name in sorted(names, key=len, reverse=True)) + r")(?!\w|[.-]\w)"
    return re.sub(pattern, "\ufffc", text, flags=re.IGNORECASE)
