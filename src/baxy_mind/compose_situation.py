"""The situation a composition tells: the typed causes and their facts, the observed values of a result or
of a mission's steps, failures by kind, and what a failed step attempted or left undone.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from . import operation_floor
from .semantic.normalize import _accent_folded_with_punctuation
from .clock_facts import _local_clock_from_observed, _local_datetime_from_observed, _local_now, _parse_core_utc


# Ungendered fact labels for the JSON the model sees. Spanish wording lives
# only in USER_MESSAGE_PROMPT, so changing the voice is editing that text.
_CAUSE_FACT = {
    "voice_wake_listening": "listening for the person's request after the wake signal",
    "voice_transcript_uncertain": "speech was detected but the request could not be understood; ask the person to repeat it",
    "turn_contract_failure": "request interpretation was not valid",
    "turn_runtime_failure": "request interpretation failed",
    "turn_unavailable": "request interpretation unavailable",
    "timeout": "wait ran out",
    "provider_down": "no response",
    "out_of_catalog": "outside what I do",
    # M56 (v3c-final F-w08-t1 «I cannot rearrange your screen layout because the plan to do so is incomplete»): the
    # App's planning codes were written as prose and the drafts narrated «the plan». What the person gets is the fact.
    "plan_incomplete": "it could not be worked out how to do this on this PC, so nothing was done",
    "plan_unverified": "it could not be worked out how to do this on this PC, so nothing was done",
    # Ronda 20 P5 (pasada r18 v3-27: «No pude abrir … en este equipo» over a 4xx of the local model
    # server's grammar): an internal fault of BAXY's own, no limit of the PC and nothing the person asked wrongly.
    "internal_fault": "an internal fault of BAXY's own stopped it before anything was done; it is no limit of this PC",
    "step_data_missing": "a detail needed for one of the actions was missing, so it was not done",
    "step_unlinkable": "the earlier result this action needed could not be used, so it was not done",
    "step_unverified": "the earlier result this action needed was not confirmed, so it was not done",
    "continue_unsafe": "going on could not be done safely, so it stopped there",
    # Tanda t4-r6 (2026-10-08): the turn's time budget ran out between two actions. What was done is said; this
    # action and the ones after it were not started.
    "turn_budget_exhausted": "it was taking too long, so this action and the ones after it were not started",
    # M45: the state of a cancelled clarification says that nothing ran and nothing is pending.
    "clarification_cancelled": "the pending question was dropped as the person asked; nothing was done",
    # Tanda 5c «Abre el gallery» → «No pude abrir el gallery porque falló el inventario»: the code named in prose.
    # The launch or the window step was sent; what failed is reading what is open, so the result is unconfirmed.
    "inventory_failed": (
        "the list of open programs and windows could not be read, so it is not confirmed whether it worked"
    ),
    # H0714: Windows rechazo la transicion de energia. La App resume eso como
    # «result_unverified», y sin un hecho detras el modelo hablaba del fallo en
    # vez de hablarle a la persona: «El fallo se debe a que el resultado no fue
    # verificado». El hecho que si se sabe es que el paso se envio y no se pudo
    # confirmar, de modo que no se afirma que haya pasado.
    # El hecho largo —que enumeraba las cuatro transiciones— se recitaba entero
    # en un caso y mataba la redacción en dos de cuatro. Dice lo mismo en una
    # cláusula: Windows no la aceptó y el equipo sigue encendido.
    "power_transition_not_accepted": (
        "Windows did not accept the power request, so nothing changed and the PC "
        "is still on"
    ),
    "result_unverified": (
        "the step was sent and its result could not be confirmed, so nothing is "
        "claimed to have happened"
    ),
    "model_invalid": "unusable answer",
    "app_not_found": "not found",
    # Review of cu-v3-documento-nuevo (finding 6): a new document asked for that the application's New command did not
    # make is said as that fact, never as the code («new document not created»).
    "new_document_not_created": (
        "the application is open, but a new blank document could not be made in it, so nothing was written in any "
        "document"
    ),
    # CLOSE1369 «cierra steam» with Steam not running: «No pude cerrar Steam
    # porque no encontré la ventana» framed a state as an inability, and the
    # English draft leaked «the operation to resolve it failed». The fact is
    # the state: no window of that application is open, nothing was closed.
    "window_not_found": (
        "that application has no open window right now, so it is not open; "
        "nothing was done to it"
    ),
    # v3 r22 revisión (bloqueante 4): app.close asked the application politely and it answered with a dialog of its
    # own (whether to save, for instance). BAXY never answers that dialog; without a fact the final said the code
    # («close prompted»), the same defect as H0714.
    "close_prompted": (
        "the application answered the close with a question of its own, such as whether to save the changes; "
        "that question was left unanswered for the person, so the window is still open"
    ),
    # H0096 «aprieta en Among Us» con Among Us sin instalar: ahora BAXY mira la
    # pantalla antes de pulsar, de modo que la ausencia es algo medido y no una
    # suposicion. El hecho es la ausencia, no el fallo. Sin hecho detras, la
    # causa se proyectaba tal cual —«visible button not found»—, que es jerga y
    # no una respuesta, el mismo defecto que el dueno rechazo en H0714.
    "visible_button_not_found": (
        "nothing on the screen is called that, so nothing was pressed"
    ),
    # v3 limits (M3, live v3-21): a click on a window that runs as administrator is refused by Windows before any
    # look; said with that cause, never as a label missing from the screen.
    "window_elevated": (
        "that application runs as administrator and Windows does not let another application control it, "
        "so nothing was pressed"
    ),
    # v3 point 0, fix 3: an act that needs the real mouse or keyboard waits for a pause of the person and stops when
    # they act during it. Said as what the person was doing, never as a code («input user not paused»).
    "input_user_not_paused": (
        "the person was using the PC and left no pause to do it without taking their mouse or keyboard, "
        "so nothing was touched"
    ),
    "input_user_interrupted": (
        "the person started using the PC while it was being done, so it stopped halfway so as not to get in their way"
    ),
    # Review of fable/cu-v3-molestia2: the leased window lost the front with no input of the person (a toast, a
    # popup), and the flow stopped before its next key so nothing landed in the other window.
    "input_window_changed": (
        "another window came to the front while it was being typed, so it stopped there and nothing more was typed"
    ),
    # A message stopped between its first character and Enter: it may sit unsent in that chat's box, where the
    # person's next Enter would send it.
    "message_draft_left_after_interruption": (
        "it stopped while the message was being typed, so the message may still be written, unsent, in that chat's "
        "message box, and pressing Enter there would send it"
    ),
    # REOPEN1957 H0188: the presentation writer names its own absences.
    "presentation_slides_invalid": ("the slides received were empty or too many, so no presentation was written"),
    "presentation_write_failed": ("the presentation file could not be written in that folder, so nothing was created"),
    "presentation_postread_failed": ("the presentation was written but its slides could not be counted back, so it is not confirmed"),
    # REOPEN1957 H0542/H0459/H0077: the file tools name their own absences.
    "zip_already_exists": ("a zip with that name already exists there, so nothing was compressed"),
    "zip_create_failed": ("the zip could not be created, so nothing was compressed"),
    "zip_postread_failed": ("the zip was written but could not be read back, so the compression is not confirmed"),
    "file_not_found": ("no file or folder with that name is in that folder, so nothing was done"),
    # Lectura-ruta (r9 t-drag-1): the code's own word «sandbox» was told as «el entorno de contenedor», a cause
    # nobody measured; the measured one is the file not found in the folder. Review of the branch (finding 7): the
    # adapter's other measured causes too, said for any of its operations (a move, an append, a comparison).
    "sandbox_named_file_not_found": ("no file with that name is in that folder, so nothing was done with it"),
    "sandbox_named_file_ambiguous": ("more than one file with that name is in that folder, so none was used"),
    "sandbox_named_root_not_found": ("the working folder was not found, so nothing was done"),
    "sandbox_named_file_name_invalid": ("that name is not a plain file name, so nothing was done"),
    "file_name_invalid": ("that name is not a plain file name, so nothing was done"),
    "file_ambiguous": ("more than one file with that name is in the person's folders, so none was opened"),
    "file_search_incomplete": ("the search for that file in the person's folders was cut short before it was sure there is only one, so none was opened"),
    "file_extension_not_openable": ("that kind of file is not opened from here, so it stays closed"),
    "file_open_dispatch_rejected": ("Windows did not open the file, so nothing appeared"),
    "file_open_not_verified": ("the file was sent to its application but no window or process appeared, so the opening is not confirmed"),
    "wallpaper_color_unknown": ("that colour is not one the desktop can be set to from here, so the background was not changed"),
    "wallpaper_file_not_an_image": ("that file is not an image, so the background was not changed"),
    "wallpaper_set_failed": ("Windows did not accept the new background, so it was not changed"),
    "wallpaper_postread_failed": ("after the change the desktop does not show the requested background, so the change is not confirmed"),
    "download_url_invalid": ("that is not a web address that can be downloaded, so nothing was saved"),
    "download_source_unavailable": ("the address did not answer, so nothing was saved"),
    "download_page_without_image": ("that page announces no cover image, so nothing was saved"),
    "download_too_large": ("that file is larger than the 50 MB this download allows, so nothing was saved"),
    "download_empty": ("the address returned an empty file, so nothing was saved"),
    "download_source_missing": ("neither an address nor a search was given, so nothing was saved"),
    "known_file_not_text": ("that file is not a text file (it holds binary data), so it was not read"),
    "known_text_too_large": ("that text file is larger than the 4 MB this reading allows, so it was not read"),
    "explorer_folder_unavailable": ("the folder of the Explorer window in front could not be read, so nothing was counted"),
    "extension_invalid": ("that is not a file extension, so nothing was counted"),
    "download_query_without_image": ("the image search listed no picture for that, so nothing was saved"),
    "download_write_failed": ("the file could not be written in that folder, so nothing was saved"),
    # REOPEN1957 H0107: airplane mode over the radios names its own absences.
    "airplane_mode_radio_access_denied": (
        "Windows did not grant access to the radios, so airplane mode was not changed"
    ),
    "airplane_mode_radios_not_found": (
        "this PC exposes no radio to switch, so there is no airplane mode to set"
    ),
    "airplane_mode_change_rejected": (
        "a radio refused to change state, so airplane mode is not confirmed"
    ),
    "airplane_mode_postread_failed": (
        "after the change a radio is not in the requested state, so airplane mode is not confirmed"
    ),
    # REOPEN1993 grupo S: the launchers name their own absences.
    "steam_title_not_resolved": (
        "no Steam title by that name is known here, so nothing was downloaded, installed or removed"
    ),
    "steam_entitlement_not_verified": (
        "that game is not in the Steam library of the account on this PC, so it was not installed (it can be bought first)"
    ),
    "steam_game_not_installed": (
        "that game is not installed on this PC, so there was nothing to uninstall"
    ),
    "steam_install_dispatch_rejected": (
        "the Steam client did not accept the install request, so nothing started"
    ),
    "steam_uninstall_dispatch_rejected": (
        "the Steam client did not accept the uninstall request, so nothing was removed"
    ),
    "steam_uninstall_not_verified": (
        "the uninstall was requested but the game still shows as installed, so the removal is not confirmed"
    ),
    "steam_install_not_verified": (
        "the install was requested but the download did not start in time, so nothing is confirmed"
    ),
    "epic_entitlement_not_verified": (
        "that game is not in the Epic Games library of the account on this PC, so it was not installed"
    ),
    "epic_launcher_data_not_found": (
        "the Epic Games launcher data is not on this PC, so nothing was installed"
    ),
    "epic_install_link_not_resolved": (
        "the Epic Games launcher gave no install identity for that game, so nothing started"
    ),
    "epic_install_dispatch_rejected": (
        "the Epic Games launcher did not accept the install request, so nothing started"
    ),
    "epic_install_not_verified": (
        "the install was requested in the Epic Games launcher but the download did not start in time, so nothing is confirmed"
    ),
    "epic_uninstall_not_supported": (
        "games are not uninstalled from the Epic Games launcher from here, so nothing was removed"
    ),
    # REOPEN1993 comandos: what the console run could not do is named.
    "shell_command_destructive": (
        "that command would delete, kill, format or change the system, so it was not run from here"
    ),
    "shell_command_directory_not_found": (
        "the folder named for the command does not exist, so the command was not run"
    ),
    "shell_command_timeout": (
        "the command did not finish within 60 seconds and was stopped"
    ),
    "shell_command_not_started": (
        "the console could not be started, so the command did not run"
    ),
    # REOPEN1993 grupo G: the package manager names its own absences.
    "winget_package_not_resolved": (
        "the Windows package manager (winget) offers no package by exactly that name, so nothing was installed"
    ),
    "winget_package_ambiguous": (
        "the Windows package manager (winget) offers several packages by that name, so none was chosen and nothing was installed"
    ),
    "winget_package_not_installed": (
        "no installed package has that name, so nothing was removed"
    ),
    "winget_install_not_verified": (
        "the installer finished but the package is not in the installed list, so the installation is not confirmed"
    ),
    "winget_uninstall_not_verified": (
        "the uninstaller finished but the package is still in the installed list, so the removal is not confirmed"
    ),
    "winget_install_not_started": (
        "the installer could not be started, so nothing was installed"
    ),
    "winget_uninstall_not_started": (
        "the uninstaller could not be started, so nothing was removed"
    ),
    "winget_confirmation_not_prepared": (
        "the installation was not prepared, so nothing was installed"
    ),
    "winget_adapter_unavailable": (
        "the Windows package manager (winget) is not available on this PC, so nothing was installed or removed"
    ),
    # REOPEN1993 grupo N: the headlines feed names its own absences.
    "news_feed_unavailable": (
        "the news feed did not answer, so no headlines were read"
    ),
    "news_feed_unreadable": (
        "the news feed answered something that is not a feed, so no headlines were read"
    ),
    "news_feed_empty": (
        "the news feed had no headlines right now, so none was read"
    ),
    "news_topic_without_headlines": (
        "the news feed has no headlines about that topic right now, so none was read"
    ),
    # REOPEN1993 grupo W: the weather read names its own absences; nothing
    # was searched in a browser and no forecast is invented.
    "weather_place_not_found": (
        "the weather service knows no place by that name, so no forecast was read"
    ),
    "weather_location_unavailable": (
        "this PC's own location could not be determined, so no forecast was read for it"
    ),
    "weather_service_unavailable": (
        "the weather service did not answer, so no forecast was read"
    ),
    # Tanda 4c: a search near the person needs this PC's city; without it nothing was searched.
    "web_search_place_unavailable": (
        "this PC's own location could not be determined, so nothing was searched near it"
    ),
    # Uso real tanda 4: the time of another place names its own absences;
    # this PC's clock is never given as that place's.
    "time_place_not_found": (
        "no place or time zone by that name is known, so its time was not read"
    ),
    "time_place_service_unavailable": (
        "the place lookup did not answer, so the time there was not read"
    ),
    "time_place_zone_ambiguous": (
        "that place spans several time zones, so a city in it is needed to give its time"
    ),
    # NETWORK1721 «conectate al wifi de casa» with no saved network of that
    # name: the fact is the absence; nothing was done. Not «connected»: the
    # truncated-word lens read the draft's «connect» as a cut of it
    # (NETWORK1723 probe) and every English final died.
    "wifi_profile_not_found": (
        "no saved Wi-Fi network has that name, so nothing was done"
    ),
    # REOPEN1957 H0170/H0376 «conectate al wifi de casa»: no network is
    # associated with that place yet; the saved networks were listed and the
    # person has to say which one it is. Nothing was connected.
    # Fase 7 (D4): mail to a free address from the owner's classic Outlook.
    "mail_address_invalid": ("that is not a mail address, so nothing was sent"),
    # Tanda 3 2026-09-24 «what do i have to do on january 1st» (a calendar read)
    # was answered «I couldn't send mail…»: the same missing profile blocks the
    # agenda and the mail, and the fact must not name an effect nobody asked for.
    # Tanda 7 «¿hoy qué día tengo que marcar en el calendario?» → «El fallo ocurre porque este PC no tiene un perfil
    # clásico de Outlook…»: the profile named as a technicality was narrated as one. What the person hears is that
    # their Outlook cannot be reached from here.
    # v3a-final F-s074/F-s091: «the person's Outlook calendar» was copied into the reply; the fact is said to them.
    "outlook_profile_not_configured": (
        "Outlook is not set up on this PC, so I cannot reach your Outlook calendar or mail here"
    ),
    # Tanda 7 «quién ganó el game de los Lakers anoche» → «…los resultados de búsqueda son irrelevantes»: the code
    # became prose about a search. The lookup is invisible; what the person hears is that it was not found.
    "web_search_results_irrelevant": "it was not found; say only that, briefly",
    # M62 (v3e2-final F-p05-t1): OpenStreetMap has sites of that kind only farther than the named place's
    # surroundings (1.5 km at least).
    "web_search_places_not_found_near": (
        "nothing of that kind was found near the place the person named; say only that, briefly, naming the place"
    ),
    # D32 (2026-09-28): no search source answered (Wikipedia and the general engine unreachable or blocked), so
    # nothing was looked up — not the same as not found. No cause is given (a «porque…» would be invented) and the
    # lookup stays invisible; the way out the owner chose is opening it in the person's own browser.
    "web_search_unavailable": (
        "it could not be looked up right now; say only that, briefly, and offer to open it in the person's web browser"
    ),
    # Owner script t22 «¿Sabes qué peli estoy viendo en potplayer?» → media.status read the browser's player, the
    # browser did not answer, and the bare code became «la conexión con PotPlayer ha fallado».
    "web_adapter_unavailable": "the web browser could not be reached, so nothing was read or done in it",
    "outlook_mail_send_failed": ("Outlook did not send the mail, so nothing went out"),
    "mail_delivery_not_verified": ("Outlook accepted the mail but its copy in Sent Items was not found, so the delivery is not verified"),
    # REOPEN1993 grupo E: the recipient was looked up in WhatsApp and Discord.
    "recipient_not_found_in_clients": (
        "no chat with that name was found in WhatsApp or Discord, so nothing was sent; the person can say which client to use"
    ),
    "recipient_channel_ambiguous": (
        "a chat with that name exists both in WhatsApp and in Discord, so nothing was sent; the person has to say which one"
    ),
    # Ronda 24 (t1-c09, t2-c07, t3-c07 «mandale a Ron92 por discord …», client opened cold): the chat search never
    # reached the recipient and nothing was typed into a conversation, so it is known that nothing went out. Said as
    # such, never as «I couldn't confirm the result», which suggests a send that was never attempted.
    "recipient_not_opened": (
        "the chat with that recipient could not be opened in the messaging app, so no message was written or sent"
    ),
    "wifi_place_unknown": (
        "no saved Wi-Fi network is associated with that place yet, so nothing was connected; "
        "the saved networks are listed and the person has to say which one it is"
    ),
    # MUSIC1753: the Spotify desktop client did not give a result to play. X3 (tandas n1/n2, «la búsqueda no devolvió
    # resultados»): what is known is that BAXY searched and picked nothing to press, not that the search had no
    # results, nor what is playing (that was not read).
    "spotify_exact_result_not_found": (
        "the request was searched in Spotify but nothing it showed could be picked to play, so nothing was pressed; "
        "whether something else is playing was not checked"
    ),
    "app_audio_session_not_found": (
        "the application has no audio session on the default output right now (it is not playing sound), so its volume could not be changed"
    ),
    "volume_level_invalid": (
        "the requested level is not a whole number from 0 to 100, so the application's volume was not changed"
    ),
    "volume_postread_mismatch": (
        "the application's volume was set but the post-read did not show the requested level, so the change is not verified"
    ),
    "spotify_play_clicked_not_verified": (
        "the Spotify play control was pressed but the client did not start playing in time, so nothing verified is playing"
    ),
    # Ronda 19 (t2-c01 T1 «pone los bunkers en spotify pa estudiar»): the press only resumed the track the client
    # already had loaded, and nothing tied it to the pressed result; something plays, it is not confirmed to be it.
    "spotify_query_result_not_confirmed": (
        "the Spotify play control was pressed but only the track the client already had loaded started again, "
        "so it is not confirmed that what is playing is what was asked for"
    ),
    "spotify_exact_play_control_not_found": (
        "the Spotify result had no play control to press, so nothing is playing"
    ),
    "spotify_client_not_running": (
        "the Spotify desktop client is not open, so nothing could be played there"
    ),
    # D59 §1 (owner, 2026-10-02): a closed WhatsApp or Discord is opened before the message is left written; these
    # are the two ways that open can end without a client to write in.
    "whatsapp_client_not_installed": (
        "WhatsApp is not installed on this PC, so the message could not be left written there"
    ),
    "discord_client_not_installed": (
        "Discord is not installed on this PC, so the message could not be left written there"
    ),
    "whatsapp_client_open_not_verified": (
        "WhatsApp was closed and opening it could not be verified in time, so the message was not "
        "left written"
    ),
    "discord_client_open_not_verified": (
        "Discord was closed and opening it could not be verified in time, so the message was not "
        "left written"
    ),
    # Encargo CS (banco fz1 s14): the client was opened cold and its main window did not show within its cold-start
    # clock (data client_cold_start.v1.json); nothing was written nor sent.
    "whatsapp_client_still_starting": (
        "WhatsApp was closed; I opened it and it was still starting when the wait for it ran out, so nothing was "
        "written or sent"
    ),
    "discord_client_still_starting": (
        "Discord was closed; I opened it and it was still starting when the wait for it ran out, so nothing was "
        "written or sent"
    ),
    # ctx-dueno-01/02 (2026-09-22): codes that reached the narrator with no fact
    # behind them, so every draft echoed the code or invented a cause.
    "media_session_not_found": (
        "nothing is playing right now that could be controlled, so nothing was changed"
    ),
    # M105 (DEV-D v4a D-s047): only that tab was looked for; the old «no YouTube video … is playing» became «No hay
    # música reproduciéndose», an absence nobody read.
    "youtube_tab_not_found": (
        "the YouTube tab the assistant opens is not open, so only that tab was checked and nothing was changed"
    ),
    # Tanda 5 «pausar el audiolibro»: the video of the assistant's YouTube tab had already ended or was paused.
    "youtube_playing_video_not_found": (
        "nothing is playing: the YouTube video the assistant opened was already paused or had ended, "
        "so nothing was changed"
    ),
    "youtube_playback_not_verified": (
        "the YouTube page opened in the browser but the video did not start playing, "
        "so playback is not confirmed"
    ),
    "youtube_tab_playback_state_not_verified": (
        "the YouTube video did not reach the requested state, so the change is not confirmed"
    ),
    # M122 (owner 2026-10-02): pages, videos and streaming open in the person's own browser, with their sessions.
    # What the assistant could not confirm there is said as such: it was opened, the rest is for the person to check.
    "user_browser_navigation_unconfirmed": (
        "the page was opened in the person's own web browser, but afterwards it could not be confirmed that the "
        "browser shows it; say it was opened there and that they can check it, without technical words"
    ),
    "user_browser_playback_unconfirmed": (
        "the video was opened in the person's own web browser, but it could not be confirmed that it started "
        "playing; say that plainly and that they can check it there"
    ),
    "user_browser_streaming_playback_unconfirmed": (
        "the streaming service was opened in the person's own web browser, with their signed-in session, but it "
        "could not be confirmed that the title started playing; say that plainly and that they can pick it there"
    ),
    # 2026-10-06 (owner: «Disney y HBO deberían de funcionar»): a «who's watching?» gate is the person's own choice.
    "user_browser_streaming_profile_choice": (
        "the streaming service opened in the person's own web browser and asks who is watching; the assistant does "
        "not choose a profile for them, so nothing was played: they can pick their profile there and ask again"
    ),
    "hbo_max_needs_default_browser": (
        "HBO Max is played only in the person's own web browser, where they are signed in, and no default web "
        "browser could be used on this PC, so nothing was played"
    ),
    "user_browser_tabs_not_automatable": (
        "the person's tabs are in their own web browser, which the assistant could not reach for this step, "
        "so nothing was done"
    ),
    # Owner 2026-10-06 («lo de mover pestañas… que el Baxi no se limite»): browser.control acts on the person's own
    # browser; what it could not do or could not confirm there is told as such.
    "user_browser_tab_step_unconfirmed": (
        "the step was sent to the person's own web browser, but afterwards its tabs and page did not show the change, "
        "so it is not confirmed; say it may not have happened and that they can check it there. When seen.closedTabs "
        "is a number above zero, that many tabs WERE closed (each seen gone) before one close was not seen: say how "
        "many you closed and that the others stayed open"
    ),
    "user_browser_tab_step_unavailable": (
        "the person's own web browser did not offer a way to do that step right now (the tab was not on screen or "
        "its control was not found), so nothing was done"
    ),
    "user_browser_last_tab_kept": (
        "that is the only tab open in the person's web browser and closing it would close the whole browser window, "
        "so it was left open; nothing was done"
    ),
    "user_browser_close_all_incomplete": (
        "closing the tabs of the person's web browser one at a time stopped before only one was left (it reached its "
        "limit of tabs or time); seen.closedTabs says how many were closed and the others are still open"
    ),
    "user_browser_fullscreen_control_missing": (
        "the page open in the person's web browser has no video full-screen control, so nothing was done"
    ),
    "user_browser_history_start": (
        "the tab in front of the person's web browser has no previous page to go back to, so nothing was done"
    ),
    "user_browser_scroll_boundary": (
        "the page in front of the person's web browser is already at that end (or does not scroll), so it did not "
        "move; nothing was done"
    ),
    # Owner 2026-10-06: «the page» and «the tabs» are always the person's own browser, never one the assistant keeps.
    "user_browser_not_running": (
        "the person's web browser is not open, so there is no page or tab to read; nothing was done"
    ),
    "user_browser_page_unreadable": (
        "the page or the tabs in the person's own web browser could not be read right now; nothing was done"
    ),
    "smtc_postcondition_not_verified": (
        "the player did not reach the requested state, so the change is not confirmed"
    ),
    # M69 (guion v3h t47 «activa mi microfono» already on → «…no hubo cambios al intentar silenciarlo»): the
    # operation's name says «mute» for both directions, so each fact names what was asked, what holds and that
    # nothing was attempted.
    "microphone_already_muted": (
        "the person asked to mute (silence) the microphone and it was already muted, not picking up sound; "
        "nothing was attempted and nothing changed"
    ),
    "airplane_mode_already_on": (
        "the person asked to turn airplane mode on and it was already on (every radio off); "
        "nothing was attempted and nothing changed"
    ),
    "airplane_mode_already_off": (
        "the person asked to turn airplane mode off and it was already off (the radios were on); "
        "nothing was attempted and nothing changed"
    ),
    "microphone_already_unmuted": (
        "the person asked to turn the microphone on (unmute it) and it was already on: active, not muted, "
        "picking up sound; nothing was attempted and nothing changed"
    ),
    # M54 (v3b-final F-w02-t4, F-w11-t3): the output level already at the end the person moves it towards.
    "volume_already_at_maximum": (
        "the volume was already at its maximum (100%), so nothing changed"
    ),
    "volume_already_at_maximum_muted": (
        "the volume was already at its maximum (100%) but the sound is muted, so nothing changed and nothing is "
        "heard; say it plainly and ask whether to unmute it, without saying it was unmuted"
    ),
    "volume_already_at_minimum": (
        "the volume was already at its minimum (0%), so nothing changed"
    ),
    "external_verification_failed": (
        "the change could not be observed afterwards, so it is not confirmed"
    ),
    "spotify_uia_process_failed": (
        "the Spotify client could not be driven, so nothing is playing"
    ),
    "spotify_session_authority_required": (
        "the Spotify client did not answer, so nothing could be played there"
    ),
    # NETWORK1729 «qué redes wifi hay» with the radio off: the state is the
    # fact; no scan happened and nothing was changed.
    "wifi_interface_off": (
        "the Wi-Fi radio of this PC is switched off, so the networks could not be scanned; nothing was changed. "
        "Offer, as the last sentence and as a question, to switch the radio on and look for networks"
    ),
    "mission_failed": "mission unfinished",
    # M79 (DEV-D v3m w19-t4 «…porque el sistema no pudo verificar la causa del fallo externo», w09-t3 «…porque el
    # efecto externo es ambiguo»): the bare code read as prose became jargon, and a failure where it may have worked.
    "external_effect_ambiguous": (
        "it was attempted, but afterwards it could not be confirmed whether it took effect, so it may or may not "
        "have been done; say that plainly, without technical words, and that the person can check it"
    ),
    # A7 E5 (DEV-A3 t388 «baxy poné la casa de papel en netflix»): the typed cause was dropped for «external effect
    # ambiguous», and the drafts narrated that jargon. What is known is that the service asks to sign in.
    "netflix_authentication_required": "Netflix asks to sign in on this PC, so nothing was played",
    "disney_authentication_required": "Disney+ asks to sign in on this PC, so nothing was played",
    "hbo_max_authentication_required": "HBO Max asks to sign in on this PC, so nothing was played",
    "streaming_authentication_required": "the streaming service asks to sign in on this PC, so nothing was played",
    # M60 (DEV-D w10-t6 v3d «Diez» → media.seek.relative): the typed cause fell back to «external effect ambiguous»
    # and the three drafts narrated that jargon («La operación de búsqueda relativa…»).
    "media_seek_postcondition_not_verified": (
        "the jump in the playback could not be confirmed afterwards, so it is not known whether it moved"
    ),
    # M62 (v3e2-final F-s019 «Cambia la alarma despertador de las 8:00 a las 9:00.» → «…porque el reloj de
    # notificaciones no se encontró»): the bare code became jargon. The fact is that nothing rings at that time; the
    # change stopped before setting the new one.
    "notification_clock_not_found": (
        "there is no alarm or reminder set at the time the person named, so nothing was cancelled, changed or set; "
        "say it plainly with that time, and if they asked to move it to another time you may ask whether to set one "
        "then"
    ),
    "notification_clock_ambiguous": (
        "several alarms or reminders are set at that same time and they cannot be told apart, so none was cancelled "
        "or changed"
    ),
    "acting": "still working",
    # M38 (official-window rehearsal 2026-09-28 «what is the timer now?»): the bare «unclear request» was copied into
    # the drafts («…because the request was unclear»), which are no question and name an internal cause; every draft
    # was vetoed and the turn failed. The fact says what the reply is.
    "ambiguous_request": (
        "one detail of what the person wants is missing: ask one short question about it, without saying why"
    ),
    "memory_forget_irreversible": "cannot be undone",
    "memory_none": "no matching memories",
    "memory_updated": "saved in the private local memory",
    "note_choice": "choose a note",
    "memory_records": "listed memories",
}
# Estabilización U (revisión H6): new cause facts live in data (operation_floor.v1.json «causeFacts»).
_CAUSE_FACT.update(operation_floor.floor_data()["causeFacts"]["facts"])


def _situation_from_facts(facts: dict) -> dict:
    raw = facts.get("situation")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.lstrip().startswith("{"):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _addressed_to_the_person(intent: str, situation: dict) -> bool:
    """M99/M134: what is said to the person themselves — a question back, or the failure of what they asked — rather
    than a piece written for someone else. «traducelo al ingles que es para mi jefa» with the file not found (DEV-D
    D-w15-t3, v4i–v4l2): «The file was not found…» was told in the language of the translation that never happened."""

    return (
        intent in {"clarification", "error"}
        or str(situation.get("kind") or "") in {"clarification", "failure"}
    )


_CAUSE_FACT_FAMILIES = ("youtube_playback_not_verified",)


def _cause_fact_key(cause: str) -> str | None:
    """The `_CAUSE_FACT` key of a code: exact, or its family when the code
    carries a diagnostic suffix («youtube_playback_not_verified_watch_ready0_…»
    names the probe's last reading; the fact is the family's)."""

    key = cause.strip().lower()
    if key in _CAUSE_FACT:
        return key
    for family in _CAUSE_FACT_FAMILIES:
        if key.startswith(family + "_"):
            return family
    return None


def _has_cause_fact(cause: str) -> bool:
    return _cause_fact_key(cause) is not None


def _cause_in_prose(cause: str, language: str) -> str:
    key = cause.strip()
    if not key:
        return ""
    fact_key = _cause_fact_key(key)
    if fact_key is not None:
        return _CAUSE_FACT[fact_key]
    return key.replace("_", " ")


def _reply_calendar_moment(situation: dict) -> datetime:
    observed = _local_datetime_from_observed(_merged_observed(situation))
    return observed if observed is not None else _local_now()


def _observed_maps_from_situation(situation: dict) -> list[dict]:
    maps: list[dict] = []
    observed = situation.get("observed")
    if isinstance(observed, dict):
        maps.append(observed)
    for step in situation.get("steps") or []:
        if not isinstance(step, str) or not step.lstrip().startswith("{"):
            continue
        try:
            parsed = json.loads(step)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue
        nested = parsed.get("observed")
        if isinstance(nested, dict):
            maps.append(nested)
        elif any(key in parsed for key in ("utc", "muted", "level", "online")):
            maps.append(parsed)
    return maps


# Typed tools whose verified receipt is the postread of an effect (REOPEN1957
# family): the change is the fact even though the receipt has no «applied» flag.
# v3 r6 lectores: switches whose receipt says whether anything had to change («changed»).
_RADIO_SWITCH_OPERATIONS = frozenset({"bluetooth.radio.set", "wifi.radio.set"})
# Ronda 22 (revisión 1): a setting already at the asked level comes back with changed:false, nothing set; the
# reply says it already was, like a radio already on.
_SETTING_ALREADY_OPERATIONS = frozenset({"system.settings.set"})
_ALREADY_IN_STATE_OPERATIONS = _RADIO_SWITCH_OPERATIONS | _SETTING_ALREADY_OPERATIONS
_TYPED_TRANSITION_OPERATIONS = frozenset({
    "desktop.wallpaper.set",
    "file.compress",
    "file.open",
    "filesystem.create.directory",
    "filesystem.write.text",
    "web.download",
    "audio.microphone.mute",
    "wifi.radio.set",
    "system.settings.set",
    "shell.command.run",
    "document.presentation.create",
})


def _lift_observed_blob(blob: dict) -> dict:
    lifted = dict(blob)
    state = blob.get("state")
    if not isinstance(state, dict):
        # Tanda 6b «Quiero el sound de nuevo please» with the sound already on: nothing was applied, but the final
        # read is still the observed state. Lifted only when applied, «No, el sonido no está activo, sigue en
        # silencio.» was published over muted=false: no mute check saw a mute state.
        state = blob.get("final")
    if isinstance(state, dict):
        if "muted" in state:
            lifted["muted"] = state["muted"]
        if "volumePercent" in state and "level" not in lifted:
            lifted["level"] = state["volumePercent"]
        elif "level" in state and "level" not in lifted:
            lifted["level"] = state["level"]
    return lifted


def _situation_steps(situation: dict) -> list[dict]:
    """Los pasos de una misión, decodificados; vacío si no es una misión."""

    steps = situation.get("steps") if isinstance(situation, dict) else None
    decoded: list[dict] = []
    for raw in steps or []:
        try:
            step = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        if isinstance(step, dict):
            decoded.append(step)
    return decoded


def _downloaded_and_opened_picture(situation: dict) -> tuple[str, str] | None:
    """MEME2055: the (name, folder) of the picture a completed mission downloaded
    (web.download) and then opened (file.open); None for any other mission."""

    steps = _situation_steps(situation)
    if not any(step.get("operation") == "file.open" for step in steps):
        return None
    download = next((step for step in steps if step.get("operation") == "web.download"), None)
    observed = download.get("observed") if download and isinstance(download.get("observed"), dict) else None
    if not isinstance(observed, dict):
        return None
    name = str(observed.get("name") or "").strip()
    folder = str(observed.get("folder") or "pictures").strip()
    return (name, folder) if name else None


def _completed_step_operation(situation: dict, operation: str) -> bool:
    """True when the mission's completed steps (MissionNarration `steps`, each a
    serialized operation result) include a verified success of `operation`."""

    steps = situation.get("steps") if isinstance(situation, dict) else None
    if not isinstance(steps, list):
        return False
    for step in steps:
        if isinstance(step, str) and step.lstrip().startswith("{"):
            try:
                step = json.loads(step)
            except json.JSONDecodeError:
                continue
        if (
            isinstance(step, dict)
            and step.get("operation") == operation
            and step.get("polarity") == "success"
            and step.get("succeeded") is True
        ):
            return True
    return False


def _failure_is_an_absence(situation: dict) -> bool:
    """The typed failure is that something was not found («youtube_tab_not_found»,
    «media_session_not_found»). Twin of UserMessagePolicy.IsNotFoundFailure."""

    return any("not_found" in code for code in _situation_error_codes(situation))


def _only_the_session_tab_read(situation: dict) -> bool:
    """M105 (DEV-D v4a D-s047): the failure is that the assistant's own YouTube tab was not found, and no reading of
    the PC's media session came with it; nothing was read about what else plays."""

    codes = set(_situation_error_codes(situation))
    return "youtube_tab_not_found" in codes and "media_session_not_found" not in codes


# M105 (DEV-D v4a D-s047): saying nothing plays on the PC at all («no hay música», «nothing is playing»). Folded.
_GENERAL_PLAYBACK_ABSENCE = re.compile(
    r"(?:\bno\s+hay\s+(?:nada|musica|ninguna\s+cancion|cancion(?:es)?|audio|sonido)\b|"
    r"\bnada\s+(?:se\s+)?(?:esta\s+)?(?:sonando|reproduciendo\w*|suena)\b|"
    r"\bno\s+(?:se\s+)?(?:esta|estan)\s+(?:sonando|reproduciendo\w*)\s+(?:nada|musica|ninguna)\b|"
    r"\bno\s+suena\s+nada\b|\bnothing\s+(?:is\s+)?playing\b|\bno\s+(?:music|song|audio)\s+(?:is\s+)?playing\b|"
    r"\bthere\s+is\s+no\s+(?:music|song|audio)\b|\bnot\s+playing\s+anything\b)"
    # «Ahora no está sonando nada en YouTube» keeps to what was checked.
    r"(?!\s+(?:en|on|in)\s+(?:(?:la|el|tu|the|your)\s+)?(?:pestana\s+de\s+|tab\s+of\s+)?youtube\b)"
)


# Saying that the thing is not there: «no hay», «ningún», «no está sonando»,
# «nothing is playing», «there is no …», «isn't playing». Twin of
# UserMessagePolicy.AbsenceStatement.
_ABSENCE_STATEMENT = re.compile(
    r"\bno\s+hay\b|\bningun[oa]?\b|\bno\s+(?:se\s+)?(?:esta|estan|estaba)\s+"
    r"(?:sonando|reproduciendo|reproduciendose|abiert[oa]s?|en\s+(?:ejecucion|reproduccion))\b|"
    r"\bno\s+suena\b|\bnothing\s+(?:is|was)\b|\bthere\s+(?:is|are|was|were)\s+no\b|"
    r"\b(?:isn't|is\s+not|aren't|are\s+not|wasn't|was\s+not)\s+(?:playing|open|running)\b|"
    r"\bno\s+\w+(?:\s+\w+)?\s+(?:is|was)\s+(?:playing|open|running)\b|"
    # Uso real tanda 5 «wat level of air pollution hay en downtown Houston» (weather_place_not_found): «el servicio
    # meteorológico no reconoce ese lugar» tells that absence; three such drafts died wanting «no pude».
    r"\bno\s+(?:se\s+)?(?:reconoce|reconocio|conoce|conocio|encuentra|encontro)\b|"
    r"\b(?:doesn't|does\s+not|didn't|did\s+not)\s+(?:recognize|recognise|know|find)\b"
)


def _failure_is_an_unchanged_state(situation: dict) -> bool:
    """The typed failure is that the target already had the asked state («microphone_already_unmuted»).
    Twin of UserMessagePolicy.IsAlreadyStateFailure."""

    return any("_already_" in code for code in _situation_error_codes(situation))


# M69 (guion v3h t46/t47): the typed codes whose asked state already holds. The adapter read the state and crossed no
# boundary; the App publishes it as a result, not an error. «volume_already_at_*» stays a failure (the asked change,
# louder or quieter, cannot happen) and «zip_already_exists» is a conflict. Twin of
# UserMessagePolicy.AskedStateAlreadyHeldCodes.
_ASKED_STATE_ALREADY_HELD = frozenset({
    "microphone_already_muted",
    "microphone_already_unmuted",
    "airplane_mode_already_on",
    "airplane_mode_already_off",
})


def _failure_is_an_asked_state_held(situation: dict) -> bool:
    """The failure told is that the asked state already held («microphone_already_unmuted»): nothing was attempted.
    Twin of UserMessagePolicy.IsAskedStateAlreadyHeld."""

    return any(code in _ASKED_STATE_ALREADY_HELD for code in _situation_error_codes(situation))


# A failure of something attempted, said in the past («no pude», «I couldn't»); twin of the App's
# UserMessagePolicy.ClaimsFailedAttempt. Casefolded text, accents kept.
_FAILED_ATTEMPT = re.compile(
    r"\b(?:no\s+(?:pude|logr[eé]|consegu[ií]|complet[eé]|realic[eé])|(?:i\s+)?(?:couldn['’]t|could\s+not)|failed\s+to)\b"
)

# M69 (guion v3h t46): the microphone said off («está desactivado», «is off») or on («está activo», «is on»); for the
# microphone off is muted and on is unmuted. Casefolded text, accents kept; «no está activo» is off, not on. Only the
# present state: «estaba activo», «was on» tell the baseline.
_MICROPHONE_NOUN = r"\b(?:micr[oó]fono|microphone|mic|micro)\s+(?:\w+\s+){0,2}?"
_MICROPHONE_SAID_OFF = re.compile(
    _MICROPHONE_NOUN
    + r"(?:no\s+est[aá]\s+(?:activ|encendid|habilitad|funcionando)|"
    r"(?:est[aá]|qued[oó]|sigue|contin[uú]a)\s+(?:desactivad|apagad|inactiv|deshabilitad)|"
    r"(?:is|stays|remains)\s+(?:off\b|disabled|inactive|deactivated|turned\s+off)|"
    r"(?:is\s+not|isn'?t)\s+(?:on\b|active|enabled))"
)
_MICROPHONE_SAID_ON = re.compile(
    _MICROPHONE_NOUN
    # «micrófono está» ends in «no »: the negation is a word of its own.
    + r"(?:(?<!\bno )(?:est[aá]|qued[oó]|sigue|contin[uú]a)\s+(?:activ|encendid|habilitad|reactivad)|"
    r"(?:is|stays|remains)\s+(?:on\b|active|enabled|live\b|turned\s+on))"
)


def _microphone_muted_fact(situation: dict) -> bool | None:
    """M69: whether the microphone is muted now — the post-read, or the state that already held."""

    observed = _merged_observed(situation)
    if str(situation.get("operation") or "") == "audio.microphone.mute" and isinstance(observed.get("muted"), bool):
        return observed["muted"]
    codes = _situation_error_codes(situation)
    if "microphone_already_muted" in codes:
        return True
    if "microphone_already_unmuted" in codes:
        return False
    return None


# Saying that it already was so: «ya estaba activo», «ya está en silencio», «it was already on». Twin of
# UserMessagePolicy.AlreadyStatement.
# Independent review A2: «Ya está, activé tu micrófono» is «done» said over a failure; «ya está» is the state only
# before a word («ya está activo»), and «I already did it» is BAXY's act.
# M101 (owner script v3z2 t45 «El micrófono estaba ya silenciado…», refused three times): «estaba ya» is «ya estaba».
# M103 (owner script t45 «silencia mi microfono», already muted): «El micrófono estaba ya silenciado, por lo que no
# hubo ningún cambio.» says it the other way round; three drafts died on missing_failure and the turn showed ⚠.
_ALREADY_STATEMENT = re.compile(
    r"\bya\s+(?:estaba|estaban|era|eran)\b|\b(?:estaba|estaban|era|eran)\s+ya\b|\bya\s+estan?\s+(?=[a-z])|"
    r"(?<!\bi )(?<!\bi've )(?<!\bi have )\balready\b"
)


def _situation_error_codes(situation: dict) -> tuple[str, ...]:
    """The typed error codes of a situation and of the step failure it wraps
    (MissionNarration serializes the step's facts inside `reason`)."""

    codes: list[str] = []
    if not isinstance(situation, dict):
        return ()
    error = situation.get("error")
    if isinstance(error, str) and error.strip():
        codes.append(error.strip().lower())
    reason = situation.get("reason")
    if isinstance(reason, str) and reason.lstrip().startswith("{"):
        try:
            reason = json.loads(reason)
        except json.JSONDecodeError:
            reason = None
    if isinstance(reason, dict):
        codes.extend(_situation_error_codes(reason))
    # M69: a step whose asked state already held counts as done and travels among the mission's steps.
    for step in situation.get("steps") or []:
        if isinstance(step, str) and step.lstrip().startswith("{"):
            try:
                step = json.loads(step)
            except json.JSONDecodeError:
                continue
        if isinstance(step, dict):
            codes.extend(_situation_error_codes(step))
    return tuple(codes)


def _failure_opened_the_page(situation: dict) -> bool:
    """M101 (DEV-D v3z D-w10-t4): the typed failure is a YouTube page that opened and whose playback was not confirmed;
    its cause fact (_CAUSE_FACT «youtube_playback_not_verified») says the page opened, so saying so claims nothing
    unverified."""

    return any(_cause_fact_key(code) == "youtube_playback_not_verified" for code in _situation_error_codes(situation))


def _merged_observed(situation: dict) -> dict:
    merged: dict = {}
    for blob in _observed_maps_from_situation(situation):
        merged.update(_lift_observed_blob(blob))
    return merged


# M87 (DEV-D v3r D-p24-t1, D-p29-t2): the notice that opens an answer from memory over a verified search («I couldn't
# check this; from memory, it may not be exact:», D35) is the scope of the read, as the not-found is. The App masked it
# since M83 (UserMessagePolicy.WithoutWebSearchObservedVocabulary) and the mind never judged those answers, so a memory
# answer the App refused went out unjudged. Twin of that mask; only the notice goes, the answer after it is judged.
_MEMORY_NOTICE = re.compile(
    r"\bno\s+(?:lo\s+|la\s+)?pude\s+comprobar(?:lo|la)?\b(?=[^.]{0,80}\bde\s+memoria\b)[^.:\n]{0,80}"
    r"|\b(?:i\s+)?(?:couldn[’']?t|could\s+not|wasn[’']?t\s+able\s+to)\s+(?:check|verify)\b"
    r"(?=[^.]{0,80}\bfrom\s+memory\b)[^.:\n]{0,80}",
    re.IGNORECASE,
)


def _without_memory_notice(text: str) -> str:
    return _MEMORY_NOTICE.sub(" ", _accent_folded_with_punctuation(text))


def _without_observed_search_vocabulary(text: str, observed: dict) -> str:
    """Mask, word by word, what a verified web search observed.

    The query, the titles and the snippets are data the reply may repeat; a
    word of three letters or more that any of them carries is blanked before
    the failure lens reads the draft, so «fallos recurrentes en WhatsApp» is
    judged as a report of the pages, while «no pude» keeps its two words.
    """

    parts: list[object] = [observed.get("query")]
    # Tanda 8: the headlines a news read observed are the same kind of data («Rechazada reforma…» is a headline,
    # not a failure of the read).
    for entry in [*(observed.get("results") or []), *(observed.get("headlines") or [])]:
        if isinstance(entry, dict):
            parts.extend((entry.get("title"), entry.get("snippet")))
    words: set[str] = set()
    for part in parts:
        if isinstance(part, str) and part.strip():
            words.update(
                re.findall(
                    r"[a-z0-9]{3,}",
                    _accent_folded_with_punctuation(part).casefold(),
                )
            )
    if not words:
        return text
    return re.sub(
        r"(?<![a-z0-9])[a-z0-9]{3,}(?![a-z0-9])",
        lambda match: " " if match.group(0).casefold() in words else match.group(0),
        _accent_folded_with_punctuation(text),
        flags=re.IGNORECASE,
    )


def _verified_empty_known_file_query(situation: dict) -> str | None:
    """A completed bounded name search is not a failed read or global absence."""
    if (
        situation.get("kind") != "operation"
        or situation.get("operation") != "filesystem.known.search"
        or situation.get("polarity") != "success"
        or situation.get("verified") is not True
        or situation.get("succeeded") is not True
    ):
        return None
    observed = _merged_observed(situation)
    query = observed.get("query")
    if (
        observed.get("authority") == "windows_known_folders_bounded_postread"
        and type(observed.get("count")) is int
        and observed["count"] == 0
        and observed.get("files") == []
        and isinstance(query, str)
        and query.strip()
    ):
        return query.strip()
    return None


def _local_clock_from_situation(situation: dict) -> str | None:
    for blob in _observed_maps_from_situation(situation):
        clock = _local_clock_from_observed(blob)
        if clock:
            return clock
    return None


def _verified_notification_due(situation: dict) -> datetime | None:
    """Use the verified next run, distinct from the requested due and current clock."""
    if (
        situation.get("operation") not in {"notification.schedule", "reminder.create"}
        or situation.get("verified") is not True
        or situation.get("succeeded") is not True
    ):
        return None
    observed = _merged_observed(situation)
    due = observed.get("dueUtc")
    if situation.get("operation") == "reminder.create":
        # M106 (DEV-D v4a D-w08-t3 «ponme recordatorio una ora antes d ese partido»): the local reminder's record is
        # read back after the write, so its due is its verified time; once the record reached the mind, the drafts
        # that said that time («el sábado 3 de octubre a las 19:00») are judged by it like an alarm's.
        return _parse_core_utc(due) if isinstance(due, str) else None
    next_run = observed.get("nextRunUtc")
    if not isinstance(due, str) or not isinstance(next_run, str):
        return None
    parsed = _parse_core_utc(due)
    return _parse_core_utc(next_run) if parsed is not None else None


def _verified_notification_dues(situation: dict) -> list[datetime]:
    """The verified next run of the scheduled alarm or timer, or of each one a mission scheduled (tanda 6b «set
    alarms for 2pm and 3pm»)."""

    single = _verified_notification_due(situation)
    if single is not None:
        return [single]
    return [due for step in _situation_steps(situation) if (due := _verified_notification_due(step)) is not None]


_ATTEMPTED_DEPTH = 3
_ATTEMPTED_TEXT = 280
_ATTEMPTED_ITEMS = 5
_NOT_DONE_ITEMS = 4


def _attempted_value(value: object, depth: int) -> object:
    """A copy of what the App projected as attempted, bounded again (the App's bounds are the authority)."""

    if isinstance(value, bool) or isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = " ".join(value.split())
        return text[:_ATTEMPTED_TEXT] if text else None
    if depth >= _ATTEMPTED_DEPTH:
        return None
    if isinstance(value, list):
        items = [kept for item in value[:_ATTEMPTED_ITEMS] if (kept := _attempted_value(item, depth + 1)) is not None]
        return items or None
    if isinstance(value, dict):
        kept_items = {
            str(key): kept for key, item in value.items()
            if isinstance(key, str) and (kept := _attempted_value(item, depth + 1)) is not None
        }
        return kept_items or None
    return None


def _attempted_facts(value: object) -> object:
    """M116: the arguments a failed or unverified step attempted (one object, or one per merged failure)."""

    return _attempted_value(value, 0) if isinstance(value, (dict, list)) else None


def _not_done_facts(value: object, language: str) -> list[dict]:
    """M116: the effects a failure left undone, each with what it acts on and what it would have used, and its plain
    clause in the reply's language (operation_floor), so the writer names the act and never the catalog id."""

    if not isinstance(value, list):
        return []
    operations = operation_floor.floor_data()["operations"]
    told: list[dict] = []
    for entry in value[:_NOT_DONE_ITEMS]:
        if not isinstance(entry, dict) or not isinstance(entry.get("operation"), str):
            continue
        clause = operations.get(entry["operation"], {}).get("en" if language == "en" else "es")
        item: dict = {"action": clause[0] if clause else entry["operation"]}
        if entry.get("target") not in (None, "", []):
            item["target"] = _attempted_value(entry["target"], 1)
        attempted = _attempted_facts(entry.get("attempted"))
        if attempted:
            item["attempted"] = attempted
        told.append(item)
    return told


def _carries_attempt(payload: object) -> bool:
    """M116: the writer's facts (or their mission's reason) say what a failed step attempted or left undone."""

    if not isinstance(payload, dict):
        return False
    return bool(payload.get("attempted") or payload.get("notDone")) or _carries_attempt(payload.get("reason"))


def attempted_texts(situation: object, depth: int = 0) -> list[str]:
    """M116: every text a failed step attempted or left undone (the words of a message, a name, a folder), found
    in the facts and in a mission's reason. Values the facts carry are no claim of the writer's own."""

    if depth > 6:
        return []
    if isinstance(situation, str) and situation.lstrip().startswith("{"):
        try:
            situation = json.loads(situation)
        except json.JSONDecodeError:
            return []
    if not isinstance(situation, dict):
        return []
    found: list[str] = []

    def strings(node: object) -> None:
        if isinstance(node, str):
            found.append(node)
        elif isinstance(node, dict):
            for item in node.values():
                strings(item)
        elif isinstance(node, list):
            for item in node:
                strings(item)

    strings(situation.get("attempted"))
    not_done = situation.get("notDone")
    for entry in not_done if isinstance(not_done, list) else []:
        if isinstance(entry, dict):
            strings(entry.get("attempted"))
            strings(entry.get("target"))
    found.extend(attempted_texts(situation.get("reason"), depth + 1))
    return found


def _computer_use_mission(situation: dict) -> dict | None:
    """The computer-use result a turn tells: the situation itself, or the reason of a mission that failed on it alone."""

    if situation.get("operation") == "mission.computer.use":
        return situation
    cause = str(situation.get("cause") or "").strip().lower()
    if cause == "mission_completed":
        # A plan whose only step was the mission (the App's OperationFloor.ComputerUseMission says the same).
        steps = _situation_steps(situation)
        return steps[0] if len(steps) == 1 and steps[0].get("operation") == "mission.computer.use" else None
    if cause != "mission_failed" or situation.get("steps"):
        # Steps of other operations beside it are told by the generic floor, each its own clause.
        return None
    reason = situation.get("reason")
    if isinstance(reason, str) and reason.lstrip().startswith("{"):
        try:
            reason = json.loads(reason)
        except json.JSONDecodeError:
            return None
    return reason if isinstance(reason, dict) and reason.get("operation") == "mission.computer.use" else None


def _decoded_reason(situation: dict) -> dict | None:
    reason = situation.get("reason")
    if isinstance(reason, str) and reason.lstrip().startswith("{"):
        try:
            reason = json.loads(reason)
        except json.JSONDecodeError:
            return None
    return reason if isinstance(reason, dict) and reason.get("operation") else None


def _recalled_records(situation: dict) -> list[dict]:
    """MEMORY1599: the records of a verified memory.recall (label/value pairs about the person)."""

    if not isinstance(situation, dict) or situation.get("operation") != "memory.recall":
        return []
    if situation.get("verified") is not True or situation.get("succeeded") is not True:
        return []
    observed = _merged_observed(situation)
    records = observed.get("records") if isinstance(observed, dict) else None
    return [r for r in records if isinstance(r, dict) and isinstance(r.get("value"), str)] if isinstance(records, list) else []
