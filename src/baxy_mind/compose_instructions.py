"""What the writer is told to name of a result: the shape instruction for every kind of result.
"""

from __future__ import annotations

from .semantic.normalize import _accent_folded_with_punctuation
from .semantic import search_address as semantic_search_address
from .semantic.network import asks_calendar_part
from .semantic.apps import asks_to_install_or_remove, wants_to_work_in_it
from .clock_facts import _calendar_instruction, _local_clock_from_observed
from .compose_situation import (
    _computer_use_mission, _downloaded_and_opened_picture, _merged_observed, _recalled_records, _situation_steps,
    _verified_empty_known_file_query, _verified_notification_dues,
)
from .search_report import _search_results_of


def _opened_search_in_navigation(situation: dict) -> tuple[str, str] | None:
    """WEB1481: the site and query of a verified navigation whose address is a
    search-results page (YouTube results, Bing search); None otherwise."""

    observed = _merged_observed(situation)
    searches = [
        found for key in ("finalUrl", "requestedUrl")
        if isinstance(value := observed.get(key), str) and value
        and (found := _search_of_address(value)) is not None
    ]
    if len(searches) == 2 and searches[0][0] == searches[1][0] and (
        " ".join(searches[0][1].casefold().split()) != " ".join(searches[1][1].casefold().split())
    ):
        # Uso real v3 t4 (c10): the address read was another search of the same site (a tab the person already had),
        # so neither search is named as the one opened.
        return None
    return searches[0] if searches else None


# Twin of the provider's UserBrowserSurface.AlreadyShownAuthority (review r10a finding 6).
_ALREADY_SHOWN_AUTHORITY = "user_browser_front_already_showed"


def _search_of_address(value: str) -> tuple[str, str] | None:
    """The site and query of a search-results address; None otherwise. Review r10a finding 7: the engines are data
    (data/search_addresses.v1.json, read by semantic.search_address), not a table in code."""

    return semantic_search_address.search_of_address(value)


def _compose_shape_instruction(situation: dict, language: str, user_text: str) -> str:
    """Describe what to name. Never the sentence the person should read. Whatever the result, after a correction the
    last final's words are named as not to be told again (``correctedFinal``, uso real v3 t2: c03-2, c04-4)."""

    shape = _result_shape_instruction(situation, language, user_text)
    open_search = situation.get("openSearch")
    out_of_view = situation.get("searchOutOfView")
    if isinstance(out_of_view, dict) and out_of_view.get("query"):
        # Review r10a finding 2: another page was in front, not the search; nothing of it reaches the writer.
        shape = (
            f"The {out_of_view.get('site') or 'web'} search «{out_of_view['query']}» is no longer in front in the "
            "person's browser: another page was, and you did not read the search. Say the search is no longer in "
            "view and offer to open it again; say nothing of any page, result or item."
        )
    elif isinstance(open_search, dict) and open_search.get("query"):
        # Semilla fix2: the search was already open in the person's browser; it was read, not opened again.
        where = f"The {open_search.get('site') or 'web'} search «{open_search['query']}» is already open in the person's browser (you did not open it again). "
        if situation.get("verified") is True and situation.get("succeeded") is True:
            count = situation.get("askedCount")
            wanted = f"the top {count} it lists" if type(count) is int and count > 0 else "what the person asked"
            shape = (
                where + f"You read that results page: give {wanted}, taken only from seen.lead, and name the source "
                f"in a few words (as «según {open_search.get('site') or 'la búsqueda'}»). If seen.lead does not hold "
                "them (an error page, menus only), say the search is open in their browser and offer to read it to "
                "them; never invent an item. Answer in the person's language: never quote the page in another one."
            )
        else:
            shape = (
                where + "Reading it failed: say it is open in their browser and offer to read it to them; say nothing "
                "of what it shows."
            )
    if not isinstance(situation.get("correctedFinal"), dict):
        return shape
    corrected = (
        "The person corrected or reproached your last answer (correctedFinal.previousReply): answer their correction "
        "with this result in other words, and if the outcome is the same, say plainly that it still is. Never repeat "
        "correctedFinal.previousReply nor any sentence of it."
    )
    if situation["correctedFinal"].get("previousTurnActed") is False:
        # Ronda 24 (r23 t2-c03 #3 «No, cerré la ventana…» after a turn that only asked): the reproach is of a question;
        # this turn's act is the answer, told without denying the person.
        corrected += (
            " Your last answer only asked or talked (correctedFinal.previousTurnActed is false): do not open with a "
            "denial; say what this turn did."
        )
    return f"{shape} {corrected}" if shape else corrected


def _result_shape_instruction(situation: dict, language: str, user_text: str) -> str:
    """What to name of the result itself (``_compose_shape_instruction``)."""

    failed_mission = _computer_use_mission(situation)
    if failed_mission is not None and str(situation.get("polarity") or "").strip().lower() == "failure":
        # Live 2026-10-07 (v2-n5, v2-e2, v2-g1, v2-n1, v2-v6): a failed computer-use mission got no voice of its own;
        # eight drafts said «No pudiste…» or told the cause with no failure («La pantalla dejó de cambiar…») and died
        # as missing_failure. The mission's failure voice is the one its success has (cu_projection._result_instruction).
        from . import cu_projection as _cu_projection

        observed = _merged_observed(failed_mission)
        if observed:
            return _cu_projection.compose_instruction(_cu_projection.project_seen(observed, language), language) + (
                "" if failed_mission is situation else " Those facts are in reason.seen."
            )
    if str(situation.get("polarity") or "").strip().lower() != "success":
        return ""
    kind = str(situation.get("kind") or "").strip().lower()
    cause = str(situation.get("cause") or "").strip().lower()
    if cause == "acting" or kind in {"welcome", "confirmation", "clarification"}:
        return ""
    bits: list[str] = []
    if kind == "status":
        bits.append("Report the verified results.")
    again = situation.get("sameResultAgain")
    if isinstance(again, dict):
        # Uso real 2026-10-07: «si pero quiero buscar un top 3» got the same sentence twice. Revisión: the offer to
        # open the search fits a web search only; any other read says it found the same again.
        searched = situation.get("operation") == "web.search" or again.get("operation") == "web.search"
        bits.append(
            "The person corrected or insisted, and looking again found the same as before (sameResultAgain): say "
            + (
                "briefly that it is all you found, and offer to open the search in their browser. "
                if searched
                else "briefly that reading it again gave the same. "
            )
            + "Never repeat sameResultAgain.previousReply nor any sentence of it."
        )
    held = situation.get("alreadyHolds")
    if isinstance(held, dict):
        # Ronda 19, revisión adversarial 2 (cero respuestas fijas): a correction that asks for what the last turn
        # already told is answered with that fact, in the writer's words; nothing was done again. Encargo TZ-HOLD: only
        # a held count reaches the writer — a held effect is said with its sentence (data: operation_floor «heldFact»).
        bits.append(
            "The person corrected you, but the alreadyHolds.count items they ask for were already told: give those "
            "same items again, only their names, as a short clean list, without opening with a denial and without "
            "arguing. Never say you did anything now, and never repeat alreadyHolds.previousReply nor any sentence "
            "of it."
        )
    undone = situation.get("undoNothing")
    if isinstance(undone, dict):
        # Ronda 24 (r23 t2-c04 #3 «regresala como estaba» after a turn that only asked): nothing was changed, so
        # nothing is put back; the writer says so, in its own words.
        bits.append(
            "The person asked you to put back how it was, but your last turn (undoNothing.request) changed nothing: "
            "say briefly that you had not changed it, so it is still as it was. Never say you changed, restored or "
            "did anything now."
        )
    asked_count = situation.get("askedCount")
    if type(asked_count) is int and situation.get("operation") == "web.search":
        # Revisión 2026-10-07: results are pages or headlines, not the items of the ranking; counting them as the
        # «top 3» is a false success.
        bits.append(
            f"The person asked for a listing of {asked_count} (askedCount). The search results are pages, not the "
            "items of that listing: name as items only works or things whose names appear in a result's title or "
            "snippet, and never present the page titles themselves as the listing."
        )
        if len(_search_results_of(situation)) < asked_count:
            bits.append(
                "The search found fewer than askedCount: say that only these were found, name each one found, and "
                "offer to open the search in their browser. Never present what was found as the whole listing asked "
                "for."
            )
    # Planner steps include internal prerequisites, such as resolving a window
    # before closing it. They are evidence, not a demand to narrate every step.
    observed = _merged_observed(situation)
    if _verified_empty_known_file_query(situation) is not None:
        bits.append(
            "The file-name search completed without matches. Preserve the query "
            "and limit the negative finding to the folders searched. Their names "
            "are not retained in this empty result: do not infer them from the "
            "request or claim absence throughout the computer. This is not a "
            "failure to search, missing permission, or an unperformed search. "
            "Explain the finding briefly and naturally in the person's language."
        )
    if situation.get("operation") == "mission.computer.use" and isinstance(observed, dict):
        from . import cu_projection as _cu_projection

        bits.append(_cu_projection.compose_instruction(
            _cu_projection.project_seen(observed, language), language,
        ))
    if (
        situation.get("operation") == "client.channel.locate"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
    ):
        # DISCORD1839: the channel was located in the client's quick switcher and
        # NOT joined; the person decides.
        bits.append(
            "This result looked the place up in the desktop client's quick switcher and "
            "did NOT join or open it: seen.found says whether a match exists, "
            "seen.channelName its exact name, seen.channelKind voice or text, seen.server "
            "the server it belongs to, seen.joined is false. If seen.found is true, say in "
            "one or two sentences, in the person's language, that you found that channel "
            "(exact name, kind, server) in the client and ASK whether they want you to join "
            "it; you did not join. If seen.found is false, say you did not find a channel or "
            "chat with that name in the client. Never say you joined, entered or opened it."
        )
    if (
        situation.get("operation") == "message.draft"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
    ):
        # MSG1837: the message was left written in the composer and NOT sent.
        bits.append(
            "This result left the message written in the desktop client's message "
            "box and did NOT send it: seen.channel is the client, seen.displayName "
            "the chat that was opened, seen.text the message left written, "
            "seen.sent is false. Say in one or two sentences, in the person's "
            "language, that you left that message (quote seen.text exactly, in its "
            "own quotation marks) written in the chat with displayName in that "
            "client and did not send it, so the person can send it when they want. "
            "Never say it was sent or delivered; no other claims."
        )
        if (situation.get("observed") or {}).get("clientOpened") is True:
            # D59 §1: the client was closed and was opened for this draft.
            bits.append(
                "seen.clientOpened is true: the client was closed and you opened it first; say so in a few words "
                "(for example that you opened it to leave the message)."
            )
    if situation.get("cause") == "mission_completed" and any(
        step.get("operation") == "message.send" for step in _situation_steps(situation)
    ):
        # REOPEN1993 grupo E: the recipient was looked up in the clients and the
        # message went to the single chat found; the reply names both.
        sent = next(
            (step for step in _situation_steps(situation) if step.get("operation") == "message.send"), {}
        )
        observed = sent.get("observed") if isinstance(sent.get("observed"), dict) else {}
        display_name = str(observed.get("displayName") or "").strip()
        channel_name = {"whatsapp": "WhatsApp", "discord": "Discord"}.get(str(observed.get("channel") or ""), str(observed.get("channel") or ""))
        if display_name and channel_name:
            bits.append(
                f"This mission really SENT the message to the chat «{display_name}» in {channel_name}: "
                "that chat was found by name in that client and the send was verified. Say in one "
                "or two sentences, in the person's language, that you sent it to that chat by that "
                "client, quoting the text sent exactly; never say it was drafted, never name another "
                "recipient or client, no question."
            )
    if situation.get("cause") == "mission_completed" and (
        picture := _downloaded_and_opened_picture(situation)
    ) is not None:
        # MEME2055 «Tienes algun meme?»: the first image the search listed was
        # written and the viewer opened it; the reply names that file.
        name, folder = picture
        bits.append(
            f"This mission downloaded the picture «{name}» into the {folder} folder and opened "
            "it in the image viewer, which is showing it now. Say so in one or two sentences, "
            f"in the person's language, naming the file «{name}» exactly and saying it is open; "
            "never say you sent, mailed or attached it; no question."
        )
    if (
        situation.get("operation") == "email.send"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
    ):
        # Fase 7 (D4): the mail really went to seen.to with seen.subject.
        bits.append(
            "This result really SENT a mail from the owner's Outlook: seen.to is the "
            "address it went to, seen.subject its subject and seen.text its body, "
            "seen.sent is true (the copy in Sent Items was found). Say in one or two "
            "sentences, in the person's language, that you sent that mail to seen.to "
            "with that subject, quoting seen.text exactly; never say it was drafted, "
            "never name another address, no question."
        )
    if (
        situation.get("operation") == "message.send.test"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
    ):
        # MSG §6: the message was really SENT, but the destination was forced to
        # the owner's own test channel, not the requested recipient. When the
        # person named that very channel (MSGSEND1845 «Musica» / «Música»), the
        # send went exactly where asked and nothing was withheld from anyone.
        seen_send = _merged_observed(situation)
        if _accent_folded_with_punctuation(
            str(seen_send.get("requestedRecipient") or "")
        ) == _accent_folded_with_punctuation(str(seen_send.get("forcedDestination") or "")):
            bits.append(
                "This result really SENT the message to the owner's own test channel, "
                "which is exactly the recipient the person named: seen.channel is the "
                "client, seen.forcedDestination is where it went, seen.text is the "
                "message, seen.sent is true. Say in one sentence, in the person's "
                "language, that you sent «seen.text» (quote it exactly) to "
                "seen.forcedDestination. Do not say it was not sent to anyone, and "
                "never say it was only drafted."
            )
        else:
            bits.append(
                "This result really SENT the message, but only to the owner's own test "
                "channel, not to the person's requested recipient: seen.channel is the "
                "client, seen.forcedDestination is the test channel it actually went to "
                "(the WhatsApp group «Música» or the Discord direct message «Ron92»), "
                "seen.requestedRecipient is who the person named, seen.text is the message, "
                "seen.sent is true. Say in one or two sentences, in the person's language, "
                "that you sent «seen.text» (quote it exactly) to seen.forcedDestination, the "
                "owner's test channel, and make clear it did NOT go to "
                "seen.requestedRecipient. Never say it went to seen.requestedRecipient, "
                "and never say it was only drafted or not sent."
            )
    if (
        situation.get("operation") == "game.entitlement.named"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
    ):
        _store_name = (
            "Epic Games" if _merged_observed(situation).get("store") == "epic" else "Steam"
        )
        bits.append(
            f"This result reads the person's {_store_name} library only: owned says "
            "whether the title is in their authenticated library, installed "
            "whether it is on disk. Nothing was downloaded, installed, "
            "uninstalled, purchased or opened. If owned is false, say the game "
            f"is not in their {_store_name} library, so it cannot be downloaded or "
            "installed (for an uninstall request: it is not installed); do not "
            "offer to buy it, open the store, search or add it. If owned is true "
            "and installed is false, say it is in the library but not installed "
            + (
                # H0578: BAXY drives no Epic install; the launcher does that.
                "and that the download is started from the Epic Games launcher; "
                "do not claim a download started. "
                if _store_name == "Epic Games"
                else "and that installing needs their confirmation; do not claim a "
                "download started. "
            )
            + "If installed is true, say it is installed; for an uninstall request "
            "say it is installed and that uninstalling is done from the "
            f"{_store_name} client — never say it was uninstalled, removed or "
            "deleted, never say something failed or could not be done, and say "
            "nothing about opening or not opening anything. Name the game as the "
            "person named it, in one or two sentences, in the person's language."
        )
    if (
        situation.get("operation") == "window.close.all"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
    ):
        # CLOSEALL1733 «cerrame todo»: every desktop window was asked to close
        # except the editor hosting the person's work; the counts are observed.
        bits.append(
            "This result asked every visible desktop window to close except the "
            "editor the person works in and counted the outcome: say how many "
            "windows were closed (closedWindows, as a digit), that Visual Studio "
            "Code was kept open on purpose when keptOpenOnPurpose is present, and, "
            "when windowsStillOpenAfterAsking is above 0, that exactly that many "
            "other windows stayed open after being asked (as a digit; they were "
            "asked, not forced, so nothing unsaved was lost) — never say that all "
            "the windows were closed in that case. One or two sentences, in the "
            "person's language, plain noun (ventanas / windows), no process names "
            "other than Visual Studio Code, no other numbers. If closedWindows is 0 "
            "and windowsStillOpenAfterAsking is 0, say there was no window to close."
        )
    if (
        situation.get("operation") in {"capture.screenshot", "capture.active.window"}
        and situation.get("verified") is True
        and situation.get("succeeded") is True
    ):
        # Uso real 2026-09-23 «haz una captura de pantalla»: with the capture
        # taken and verified, eighteen drafts answered from the model's own
        # belief — «No puedo hacer una captura… no tengo acceso a la pantalla».
        observed_capture = situation.get("observed") if isinstance(situation.get("observed"), dict) else {}
        if isinstance(observed_capture.get("savedFolder"), str) and isinstance(observed_capture.get("fileName"), str):
            # Ronda 22 (uso real r18 t3-c11 «…y guárdala en el escritorio porfa» → «Hice la captura de pantalla.»): the
            # copy asked to be kept was saved and read back; where it is is what the person needs to find it.
            bits.append(
                "This result is a screenshot you have just taken, saved where the person asked and verified on "
                "disk: seen.captured is what it shows, seen.savedIn the folder it was saved in and seen.fileName "
                "its file name. Say in the first person, in the past, that you took it and saved it, naming that "
                "folder and the file name exactly as given, in one or two sentences, in the person's language. "
                "Do not call it private and do not name any other folder."
            )
        else:
            bits.append(
                "This result is a screenshot you have just taken and verified: "
                "seen.captured is what it shows (the whole screen or the active "
                "window), width and height its size in pixels, and storedPrivately "
                "means it stays private on this PC. Say in the first person, in the "
                "past, that you took it and what it captured, in one or two sentences, "
                "in the person's language. Never say you cannot take screenshots or "
                "have no access to the screen, and do not name a folder or file: no "
                "path was given."
            )
    if (
        situation.get("operation") == "window.minimize.all"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
    ):
        # MINALL1687 «minimizá todas las ventanas»: the desktop windows were
        # minimized and re-observed iconic; nothing was closed.
        # Owner 2026-09-24 (concise): «…se minimizaron 6 ventanas y no se cerró
        # ninguna» said a thing nobody asked; nothing closed is a limit on the
        # claim, not a fact to recite.
        bits.append(
            "This result minimized every visible desktop window and verified "
            "each is now minimized: say that the windows were minimized "
            "(with the count from minimized if it is present), in one short "
            "sentence, in the person's language, calling them by the plain noun "
            "(ventanas / windows) and no other word; never say any was closed. If "
            "minimized is 0, say there was no open window to minimize."
        )
    if (
        situation.get("operation") == "app.installed"
        and situation.get("verified") is True
        and situation.get("succeeded") is True
    ):
        if asks_to_install_or_remove(user_text):
            # INSTALL1625: an install or uninstall request answered by the
            # presence read; nothing was installed or removed.
            bits.append(
                "The person asked to install or uninstall this application and "
                "this result only reads its presence: nothing was installed, "
                "downloaded or removed. If installed is true and installing was "
                "asked, say it is already installed. If installed is true and "
                "uninstalling was asked, say it is installed and that removing it "
                "is done from Windows Settings > Apps, as a fact, without saying "
                "you cannot or failed. If installed is false and installing was "
                "asked, say it is not in the Windows Start catalog and that "
                "installing it is done with the vendor's own installer, as a "
                "fact, without saying you cannot or failed and without offering "
                "to download it. If installed is false and uninstalling was asked, "
                "say it is not in the Windows Start catalog. One or two sentences, "
                "the person's language, the application named as they named it."
            )
        if wants_to_work_in_it(user_text):
            # APPS1671 «quiero editar una foto en photoshop»: the person wants
            # to work in a program the presence read did not find. Every
            # draft that added «no puedo editarte la foto» / «cannot be opened»
            # was vetoed as an asserted failure or a reversed result; the fact
            # is the absence, stated on its own.
            bits.append(
                "The person wants to work in this program and this result only "
                "reads its presence. If installed is false, say only that the "
                "program is not in the Windows Start catalog of this PC, as a "
                "fact: do not say you cannot, could not or failed, do not say it "
                "cannot be opened, do not offer to install or search for it, and "
                "do not mention the photo or task beyond naming it. One sentence, "
                "the person's language, the program named as they named it."
            )
        bits.append(
            "This result verifies application presence only, not an opening. "
            "Preserve requestedName and the original purpose of the request. "
            "If opening was requested and installed is false, explain that the "
            "requested application was not found in the observed authority's "
            "catalog, so its opening could not proceed. Do not claim physical "
            "absence beyond that catalog, a launch attempt, or a completed opening."
        )
    if observed:
        scheduled_dues = _verified_notification_dues(situation)
        if scheduled_dues:
            # Uso real 2026-09-23: «a las seis de la mañana» was confirmed as
            # «09:00 UTC». The person hears their own clock; the conversion is
            # done here, never left to the model. Tanda 6b: two alarms due
            # tomorrow were told «today»; the day is said as sent (scheduledDay).
            times = " and ".join(f"{due.astimezone():%H:%M}" for due in scheduled_dues)
            bits.append(
                "Briefly confirm the alarm or timer was scheduled and give its "
                f"scheduled local time, {times}, as HH:MM; never "
                "mention UTC or a time zone. This is "
                "not the current time or a new relative countdown. Say the day only as "
                "sent (scheduledDay or scheduledLocalDate); without them it is today. "
                "Do not expose internal field names. "
                "Preserve any explicitly named title; a descriptive alarm label "
                "may be paraphrased. Address the person naturally in their language."
            )
        if (
            situation.get("operation") in {"browser.navigate", "browser.navigate.named", "streaming.navigate"}
            and situation.get("verified") is True
            and situation.get("succeeded") is True
        ):
            # WEB1259: «Voy a youtube.» / «Vamos a github.» promised a navigation
            # that had already been verified by its final URL.
            opened_search = _opened_search_in_navigation(situation)
            if opened_search is not None:
                # WEB1481 «buscá videos de gatos en youtube»: the verified page
                # is a results page; the final must name the search it opened,
                # not just the site («Abrí YouTube en el navegador» hid it).
                site, query = opened_search
                bits.append(
                    f"You have just opened, in the browser, the {site} search results "
                    f"for «{query}» and the final URL was verified: report in the past "
                    f"that you opened that search on {site}, naming «{query}» exactly; "
                    "do not say you merely opened the site, do not describe or invent "
                    "any result, never promise to search later and never say it was "
                    "already open before. Address the person naturally in their language."
                )
            else:
                bits.append(
                    "You have just opened the site in the browser and its final URL was "
                    "verified: report that in the past, naming the site the person asked "
                    "for (for example «Abrí YouTube en el navegador»). If finalUrl is a "
                    "sign-in page, say the site asks to sign in. Never promise to go or "
                    "open it later, and never say it was already open before. "
                    "Address the person naturally in their language."
                )
        if (
            situation.get("operation") == "browser.control"
            and situation.get("verified") is True
            and situation.get("succeeded") is True
            and _merged_observed(situation).get("action") == "new_tab"
        ):
            # BROWSER1493: the tab exists now; say so in the past, nothing else.
            bits.append(
                "You have just opened a new, empty tab in the browser and its "
                "presence was verified: say that in the past in one short sentence "
                "(for example «Abrí una pestaña nueva en el navegador»). Do not "
                "mention identifiers, states or codes, do not promise anything "
                "and do not say it was already open. Address the person naturally "
                "in their language."
            )
        browser_step_example = {
            "went_back": "Volví a la página anterior",
            "reloaded": "Recargué la página",
            "scrolled": "Bajé la página" if _merged_observed(situation).get("action") == "scroll_down" else "Subí la página",
            "tab_closed": "Cerré la pestaña",
            "fullscreen": "Puse el video en pantalla completa",
        }.get(str(_merged_observed(situation).get("observedState") or ""))
        if (
            situation.get("operation") == "browser.control"
            and situation.get("verified") is True
            and situation.get("succeeded") is True
            and browser_step_example
        ):
            # Live check 2026-10-06 (the person's Opera GX): «El video ya está en pantalla completa» read as if it
            # already was, «Has vuelto a la página…» as if the person did it. The assistant did it, just now.
            bits.append(
                "You have just done this step yourself in the person's web browser and read the result back: say it "
                f"in the past, as yours, in one short sentence (for example «{browser_step_example}»). Never say it "
                "already was so, and never say the person did it. Address the person naturally in their language."
            )
        if (
            situation.get("operation") == "browser.control"
            and situation.get("verified") is True
            and situation.get("succeeded") is True
            and _merged_observed(situation).get("action") == "close_all"
        ):
            # BROWSER1841 «cerrá todas las pestañas»: the person's browser keeps
            # its last tab (closing it would close the browser); the tabs closed
            # and the one left were read back.
            bits.append(
                "You have just closed the tabs of the person's web browser one at a time and read the result back: "
                "seen.closedTabs is how many you closed and seen.tabCount how many are left open (the browser keeps "
                "its last tab, since closing it would close the browser). Say it in the past in one short sentence "
                "with those numbers (for example «Cerré 3 pestañas; queda una abierta»). Never say every tab was "
                "closed, do not mention identifiers, states or codes, and do not promise anything. Address the "
                "person naturally in their language."
            )
        if (
            situation.get("operation") in {"note.create", "task.create"}
            and situation.get("verified") is True
            and situation.get("succeeded") is True
        ):
            bits.append(
                "Briefly confirm what you saved, using its title and relevant "
                "content. Address the person naturally in their language."
            )
        if _recalled_records(situation):
            # MEMORY1599: the record is about the person who asks; «Me llamo
            # Valentina» and «Me gusta tomar mate» made it BAXY's own.
            bits.append(
                "The records are facts about the person who is asking, kept in this "
                "computer's private memory. Answer their question with the recorded "
                "value exactly as stored, addressing them in the second person "
                "(«te llamás …», «te gusta …», «your name is …»); never say it in the "
                "first person as if it were about you, and never invent a record."
            )
        if (
            situation.get("operation") in {"memory.save", "memory.sensitive.save", "memory.correct"}
            and situation.get("verified") is True
            and situation.get("succeeded") is True
        ):
            # MEMORY1247: «el archivo fue guardado… ni acciones de replay» read
            # the raw flags as facts. The datum is private local memory.
            bits.append(
                "Briefly confirm that you will remember it: quote observed.remembered "
                "when present as the thing remembered, in the private local memory "
                "of this computer. There is no file and no other action: never "
                "mention files, corrections, replay or internal field names. "
                "Address the person naturally in their language."
            )
        if situation.get("operation") == "media.status" or (
            situation.get("operation") == "media.control"
            and situation.get("verified") is True
            and situation.get("succeeded") is True
            and observed.get("authority") in {"windows_smtc", "local_youtube_player"}
            and isinstance(observed.get("sourceAppUserModelId"), str)
            and bool(observed["sourceAppUserModelId"].strip())
            and observed.get("playbackStatus") in {"playing", "paused", "stopped"}
        ):
            # Tanda 6b: told to «identify the observed title», the draft opened «El título observado es…»; a title
            # like «Artist - Song (Official Video) - YouTube» names the song and who performs it.
            bits.append(
                "Answer with seen.title and seen.artist when supplied: a title like «Artist - Song (Official "
                "Video) - YouTube» names the song and who performs it, so say those names as a person would, "
                "never calling it a title that was observed. When the question asks what is playing, say "
                "whether it plays, is paused or stopped (seen.playbackStatus). A loaded track is not evidence "
                "that it is playing: paused or stopped means it is not playing. Do not repeat the "
                "question's playing premise as a fact or claim PC-wide silence. "
                "If no session or metadata was observed, report only that scope."
            )
            if observed.get("authority") == "local_youtube_player":
                # MUSIC1593: the local player's finals listed fields («Título
                # observado: … Estado de reproducción: "stopped"») or quoted a
                # fragment of the title; one sentence in the person's words.
                bits.append(
                    "This is the local YouTube player. Answer in one natural sentence "
                    "in the person's language: quote the whole title exactly as "
                    "observed, inside quotation marks, and say in words whether it is "
                    "playing or was stopped. No field list, no internal status words "
                    "such as playing or stopped in English, no artist unless observed, "
                    "and never translate any part of the title."
                )
            elif (
                situation.get("operation") == "media.control"
                and observed.get("playbackStatus") in {"paused", "stopped"}
            ):
                # ctx-dueno-06 (2026-09-22, «para la canción»): the verified stop
                # came out as «No se observó título ni artista. El estado de
                # reproducción es "stopped"»; one sentence in the person's words.
                bits.append(
                    "The control was verified. Answer in one natural sentence in the "
                    "person's language saying that you stopped or paused the playback "
                    "(whichever playbackStatus says), quoting the title only when one "
                    "was observed; if title and artist are empty, do not mention them "
                    "at all. No field list and no internal status words in English."
                )
        if isinstance(observed.get("app"), str) and observed["app"].strip():
            bits.append(
                "Name observed.app. State open, closed or playing from the facts."
            )
        clock = _local_clock_from_observed(observed)
        has_audio = "level" in observed or "muted" in observed
        if "level" in observed:
            bits.append("Name the volume number.")
        if "muted" in observed and situation.get("operation") == "audio.microphone.mute":
            # M69 (guion v3h t46): «muted: false» told as «desactivado»; seen.microphone says the state in words.
            bits.append("Say whether the microphone is now active or muted, as seen.microphone says.")
        elif "muted" in observed:
            bits.append("Describe whether sound is silenced.")
        if clock and asks_calendar_part(user_text):
            bits.append(_calendar_instruction(user_text))
        elif clock and has_audio:
            bits.append("Name the local clock.")
        elif clock:
            bits.append("State the time in clock.")
        if "online" in observed or "connected" in observed:
            bits.append("Name whether the PC is online.")
    if language == "en" and bits:
        bits.append("English only.")
    return " ".join(bits)
