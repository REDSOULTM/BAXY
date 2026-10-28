namespace Baxy.Providers.Windows.Infrastructure;

/// <summary>
/// The aids of the «ayudas al modelo» goal (2026-10-19): facts added to what a tool's result tells the model, never a
/// choice of tool, an argument, a run or a reply. <c>BAXY_AYUDAS</c> says which are on: unset, empty or «all», every
/// one; «none» (or «0»), none, and the product reads as it did before them; otherwise the comma-separated ids that are
/// on. The mind reads the same variable for its own aids (src/baxy_mind/mind.py, <c>_aid_on</c>).
/// </summary>
public static class ModelAids
{
    /// <summary>
    /// E011: a calculator.expression.evaluate with no Calculator window says app_open can start it. Holdout v5 V5E021: a
    /// bare number, when the person's words name one operation on what it shows, goes as that operator and the number
    /// (Baxy.App.SaidVerbs).
    /// </summary>
    public const string CalculatorNext = "calculator_next";

    /// <summary>Accessible mode: system.settings.set says what the mode changes and which modes do not exist yet.</summary>
    public const string AccessibleScope = "accessible_scope";

    /// <summary>BAXY Renew cu (C14): audio.microphone.mute and audio.microphone.status say they are Windows' switch, not an
    /// application's own mute.</summary>
    public const string MicrophoneScope = "microphone_scope";

    /// <summary>BAXY Renew cu (C02): a click that changed nothing on a control already chosen says it was already so.</summary>
    public const string AlreadySelected = "already_selected";

    /// <summary>E024: a file.write with no folder says it went to BAXY's working folder (and a home folder of that name).</summary>
    public const string WorkFolder = "work_folder";

    /// <summary>F019, E015: an app.open with a place says the place was only asked for and how to look.</summary>
    public const string PlaceUnverified = "place_unverified";

    /// <summary>BAXY Renew cu (C04): an app.open with no place names the places its application opens at directly.</summary>
    public const string AppPlaces = "app_places";

    /// <summary>BAXY Renew cu (C18): a protected_window refusal says nothing was sent and how another app's window is reached.</summary>
    public const string ProtectedFrontNext = "protected_front_next";

    /// <summary>BAXY Renew cu (C18): a clipboard.paste says, as a sentence, the one window that received it.</summary>
    public const string PasteTargetNext = "paste_target_next";

    /// <summary>BAXY Renew cu (C13): a window.resolve by an application name that matched nothing lists the visible windows.</summary>
    public const string WindowCandidates = "window_candidates";

    /// <summary>Al máximo, flujos (P252): a window.resolve with no selector says the person's window in front is window_active's.</summary>
    public const string SelectorNext = "selector_next";

    /// <summary>BAXY Renew cu (C03): a click whose index names another control says so and how a read text is clicked.</summary>
    public const string IndexLabelNext = "index_label_next";

    /// <summary>BAXY Renew cu (C11): a click whose label no control has lists the collapsed entries of the last look.</summary>
    public const string CollapsedNext = "collapsed_next";

    /// <summary>Renew al máximo (6.3): a failed app.open says whether its launch was issued and where to look next.</summary>
    public const string OpenRecovery = "open_recovery";

    /// <summary>Renew al máximo (auditoría de flujos, P257): an app volume with no audio session names the apps that have one.</summary>
    public const string AppVolumeCandidates = "app_volume_candidates";

    /// <summary>Renew al máximo (auditoría de flujos, P215): a package.uninstall candidate that is a game names game_uninstall_named.</summary>
    public const string GameUninstall = "game_uninstall";

    /// <summary>Renew al máximo (E027): a known file found nowhere says nothing beyond the folders walked was searched.</summary>
    public const string SearchScope = "search_scope";

    /// <summary>
    /// Holdout v5 (V5E052: «factura marzo.pdf» dictated, factura-marzo.pdf there, nothing offered): a known file named
    /// exactly by none gives, from the same walk, up to 5 names with the same words under other separators (space, -, _,
    /// .), case or accents as candidates, and that fact; nothing is done to them, and the exact name is asked for again.
    /// (Holdout v6 V6F010: a name that differs only in its separators is the name itself, aid or not, SpokenFileNames;
    /// what this aid offers is a name that also differs in accents or extension.)
    /// </summary>
    public const string NearNames = "near_names";

    /// <summary>Holdout v5 (V5E047, «is not in no folder»): a known file call whose subdirectory does not exist says so, as a relative path.</summary>
    public const string MissingSubdirectory = "missing_subdirectory";

    /// <summary>Holdout v5 (V5E061, another file's whole content as oldText): a file.edit whose oldText is not in the file says it may not be the file meant.</summary>
    public const string EditTextAbsent = "edit_text_absent";

    /// <summary>Renew al máximo (F002): window.application.status says as a sentence whether BAXY opened the window.</summary>
    public const string ProvenanceNext = "provenance_next";

    /// <summary>Renew al máximo (w5, F004): a text typed with no window named says, as a sentence, the one window it went into.</summary>
    public const string TypedTargetNext = "typed_target_next";

    /// <summary>
    /// P1.1(b) F024 (falsedades v11): an app.close that closed a window with no dialog of its own (by appId: with no
    /// error and at least one window closed) says closePrompted false, and it and a minimized window say unsavedChanges
    /// not_readable: whether a window held unsaved changes is not something BAXY reads.
    /// </summary>
    public const string UnsavedNotRead = "unsaved_not_read";


    /// <summary>Holdout v6 V6E024: control or shift pressed alone says it writes nothing and how a window's button is pressed.</summary>
    public const string LoneModifierNext = "lone_modifier_next";

    /// <summary>Renew al máximo (w5): an act stopped by the person's input says why it stopped and how the window is seen.</summary>
    public const string InterruptedNext = "interrupted_next";

    /// <summary>
    /// Auditoría de falsedades (F001): an invalid_or_expired_window_id says the id is used up, nothing was done to the
    /// window and nothing was read of it.
    /// </summary>
    public const string WindowIdSpent = "window_id_spent";

    /// <summary>Renew al máximo (w5, E024): an append refused for a missing file says where one of that name is.</summary>
    public const string AppendElsewhere = "append_elsewhere";
    /// <summary>
    /// Holdout v6 V6E044 (told «a file of that name is in BAXY-bench/gastos.txt», answered «gastos.txt está en mi carpeta
    /// de trabajo»): that append refusal says the file by its full path, whose it is, and the file_write call that
    /// appends to it, with its arguments.
    /// </summary>
    public const string AppendElsewhereCall = "append_elsewhere_call";

    /// <summary>
    /// Holdout v6 V6E041 («agrégale al file jugadores.txt … la línea: …», written without append and refused, then read
    /// and replaced by that line alone): a write without append and without the hash, refused because the file is
    /// there, says that append adds the text at its end and that the hash replaces all the file has.
    /// </summary>
    public const string ReplaceOrAppend = "replace_or_append";

    /// <summary>
    /// Holdout v6 V6E041 (8 of 8 runs: file.write without append; in 6 the file was read and replaced under the hash the
    /// read gave by the new line alone, and the reply said «agregué»): a file.write that would replace a file of the
    /// person's that has text with a text that keeps little of it (half of its words or less, and not all of it), under
    /// the file's own hash, asks the person first in normal mode, bound to the call (FilesystemHandler's preflight,
    /// LocalFilesystemProvider.ReplacementAsksFirst); without the hash its refusal says how many lines and characters
    /// the file has and the exact file_write call that appends. Empty files and edits that keep
    /// most of the text go straight. V6E048: a file.edit that would leave its file with as little (TextLoss, the same
    /// measure) asks the person first in normal mode (WindowsKnownFileAdapter's preflight). And a file.write without append
    /// over a file of the person's, when their words say to add to it, goes as an append, and a move that can copy, when
    /// they say to copy, goes as a copy (Baxy.App.SaidVerbs).
    /// </summary>
    public const string OverwriteGuard = "overwrite_guard";

    /// <summary>Renew al máximo (w5, E020): a look at BAXY's working folder says it is BAXY's, and one that found nothing that the person's folders were not looked at.</summary>
    public const string WorkFolderScope = "work_folder_scope";

    /// <summary>
    /// Renew al máximo (w6, rutas): a file call that leaves out the folder the person named in this turn is routed there
    /// (a read) or refused before any effect with the call that names it (anything else) (Baxy.App.SaidFolders).
    /// </summary>
    public const string SaidFolder = "said_folder";
    /// <summary>
    /// Holdout v6 V6E034 (final_v5 s0: «filesystem_copy cannot name a folder of theirs», answered «no pude copiarlo:
    /// contrato.txt está en BAXY-bench, que es una carpeta de la persona»): a call of BAXY's working folder refused by
    /// <see cref="SaidFolder"/> whose act another operation does in the person's folders (a copy, a move, a read) says
    /// that operation as a call, with its arguments for the folder named (Baxy.App.SaidFolders).
    /// </summary>
    public const string SaidFolderCounterpart = "said_folder_counterpart";

    /// <summary>
    /// Fase 3 (holdout v5 V5E043): a folder made with the name the person said, spelled otherwise (viaje_chiloe_2027 for
    /// «viaje chiloé 2027»), is refused once with the call that writes it as they said it (Baxy.App.SaidFolders).
    /// </summary>
    public const string SaidName = "said_name";

    /// <summary>
    /// Feria 2026-10-27 (a creator's name searched as another one that sounds alike, and someone else's video played): a
    /// call that goes out with a query whose words share none of the person's in this session nor of what its results and
    /// memory gave is refused once, and the same words again go as written (Baxy.App.NetworkEgress).
    /// </summary>
    public const string SaidQuery = "said_query";

    /// <summary>
    /// Feria 2026-10-27 (a greeting asked for someone in the room opened a messaging client with a draft): a
    /// message.draft or message.send by a channel the person's words now or just before did not name is refused; a
    /// message.send by that channel again in that turn goes as written, since the person is asked before it goes; after the
    /// model's question, a message by that channel goes in the next turn (Baxy.App.NetworkEgress).
    /// </summary>
    public const string SaidChannel = "said_channel";

    /// <summary>
    /// Holdout v4 (en vivo: «Biblioteca» pressed 7 times in Steam, each visible_button_postread_unchanged, 50 s): the
    /// same click seen unchanged a second time in a row says so, and the places its application opens straight at.
    /// </summary>
    public const string RepeatedUnchangedNext = "repeated_unchanged_next";

    /// <summary>
    /// Práctica V5E029 («cambia la calculadora a modo científico»: the text «Modo de calculadora Estándar» clicked 3 times,
    /// unchanged, and «Abrir navegación» beside it never tried): a click that changed nothing on a static text of the last
    /// look says, from the first time, that it is a text and not a control, and names the controls nearest it.
    /// </summary>
    public const string TextClickNext = "text_click_next";

    /// <summary>
    /// Renew al máximo (w8, falsedades F019): a look at a window drawn without controls (Steam's library, read only by
    /// OCR) says its text is the screen's words, pressed by label, and that a word missing from the controls is not absent.
    /// </summary>
    public const string DrawnTextNext = "drawn_text_next";

    /// <summary>
    /// Renew al máximo (w9-dudas, falsedades F019): a look whose list of controls the reader says is not whole (drawn
    /// without controls, cut, partial, only the frame, its tree unread) says so in the heading of the list, and an empty
    /// one is «none read», never «(ninguno)».
    /// </summary>
    public const string ControlsNotComplete = "controls_not_complete";

    /// <summary>Renew al máximo (w8): a keyboard act refused for a window run as administrator says nothing was sent and why.</summary>
    public const string ElevatedNext = "elevated_next";

    /// <summary>Renew al máximo (w5): a network.ping with no reply says it does not tell a site or the internet is down.</summary>
    public const string PingScope = "ping_scope";

    /// <summary>Renew al máximo (w5): a display.mode.set shown but not saved says a restart shows the saved mode again.</summary>
    public const string DisplayRestart = "display_restart";

    /// <summary>Renew al máximo (w5): a Bluetooth device or Wi-Fi profile id no list of this session gave says which list gives one.</summary>
    public const string IdentityRelist = "identity_relist";

    /// <summary>Renew al máximo (w5): a schedule.alarms cancel that canceled nothing says so and what it looked among.</summary>
    public const string CancelScope = "cancel_scope";

    /// <summary>Renew al máximo (w5): a task not found or changed says what that taskId holds now and that nothing changed.</summary>
    public const string TaskStateNext = "task_state_next";

    /// <summary>Renew al máximo (w5): a note not found says where it was looked, the one in the trash, or titles close to it.</summary>
    public const string NoteNotFoundNext = "note_not_found_next";

    /// <summary>Renew al máximo (w9): a note.trash with no snapshot, or a snapshot the note no longer is, says what to call or how the note is now.</summary>
    public const string NoteSnapshotNext = "note_snapshot_next";

    /// <summary>Renew al máximo (w5): a calendar time or range refused says which argument, why, and that nothing ran.</summary>
    public const string CalendarTimeNext = "calendar_time_next";

    /// <summary>Renew al máximo (w8): an email.latest.reply refused for its mail (none named, or not the newest now) says which mail to name.</summary>
    public const string ReplyMessageIdNext = "reply_message_id_next";

    /// <summary>Renew al máximo (w8): a chat message refused or left unverified says what was written and what to do next.</summary>
    public const string MessageTextNext = "message_text_next";

    /// Renew al máximo (w7, apps; e2e E014, «abre la configuración de sonido»: «Configuración del sistema» with place
    /// sound 34 times in the PC's practice runs, and twice on the notebook): an app.open of an application the person did
    /// not name, at a place it does not have and only one other application has, opens that one at the place instead,
    /// and its result says so (Baxy.App.SaidApplication).
    /// </summary>
    public const string PlaceOwner = "place_owner";

    /// <summary>
    /// Renew al máximo (w7, apps; E014: msconfig opened elevated on the notebook, 2026-10-22): the tools that configure
    /// Windows itself, by the rule the guards use (VisibleControlSurface.SystemToolLaunch), are left out of the installed
    /// applications the model reads; app.open still opens them by name. It changes the prefix once (a stable list).
    /// </summary>
    public const string SystemToolsUnlisted = "system_tools_unlisted";

    /// <summary>
    /// Holdout v5 (H5, en vivo: after a web.search whose results were news.google.com, a web.fetch of vln.cl, a site
    /// none of them was, held as host_not_from_session): a call held for a host no result gave lists the hosts this
    /// session's results gave (Baxy.App.NetworkEgress.ResultHosts) and says a page at one of them is read without asking.
    /// </summary>
    public const string ResultHosts = "result_hosts";

    /// <summary>
    /// V5E016 («si alguien en Tokio mira el reloj ahora mismo, ¿qué hora ve?»: the model added the offset to the PC's
    /// local clock and missed the change of day): a system.time with a place gives that place's date, clock time and
    /// weekday at the observed instant.
    /// </summary>
    public const string PlaceClock = "place_clock";

    /// <summary>
    /// Práctica e2e E017 («guárdalo como lista.txt en C:\Users\ana\BAXY-bench»: in Notepad's «Guardar como» the model
    /// pressed «Guardar» with «Nombre de archivo» still holding «lista pilas, cables», and said it saved lista.txt): a look
    /// at a modal save dialog (a «Nombre de archivo»/«File name» edit and a «Guardar»/«Save» button) says, after that
    /// edit, that what it holds is the name the file gets, in the folder the dialog's address shows, and that a full path
    /// written in it saves there (ScreenViewProjection.SaveField).
    /// </summary>
    public const string SaveDialogNext = "save_dialog_next";

    /// <summary>
    /// Prueba en vivo de la versión final (renew_v6, «abre la biblioteca de Steam»: Steam opened with no place, and six
    /// looks at its store said only «Lugar a la vista: store» until the turn's calls ran out): a look that says which
    /// place of an application is in sight says beside it that application's other places, which app.open opens directly
    /// (ScreenViewProjection, from ApplicationPlaces).
    /// </summary>
    public const string SightPlaces = "sight_places";

    /// <summary>
    /// Práctica e2e E014 («abre la configuración de sonido», c3-junto-s0, 2026-10-25: app.open at sound, then 14 clicks
    /// and looks for a microphone nobody asked about, from a first look identical to the runs that stopped there; in 4 of
    /// 17 c3 runs on every branch the model first pressed «Sonido» in the breadcrumb of the page it was on): a look whose
    /// place in sight is the one this turn's app.open asked of that application says so, and then says no other places
    /// (sight_places); one whose place in sight is another says which was asked (ScreenViewProjection, Baxy.App.TurnPlace).
    /// </summary>
    public const string AskedPlace = "asked_place";

    /// <summary>
    /// Práctica V5E023 («en el Notepad que tengo abierto, agrega al final …»: the model typed with the caret at the start
    /// of the text, «nos vemos el lunesHola equipo…», and said «agregué al final»; nothing it read said where the caret
    /// was): a look whose focus is an edit or document with text says where its caret is, as UI Automation's TextPattern
    /// reads it against the whole text (start, end, middle, or a selection), and nothing when it cannot be read
    /// (ScreenViewProjection.CaretNote); a text typed into an edit control and read back there says where it landed in the
    /// text the control already had (WindowsTextDelivery.Landed).
    /// </summary>
    public const string CaretPlace = "caret_place";

    /// <summary>
    /// Práctica e2e V6E035 («¿qué archivo de mi carpeta X tiene anotado el dato Y?», c3-junto-s0: file.find with query Y
    /// three times, no name with Y, and «ningún archivo en X menciona Y» with Y written inside one): a file.find by name
    /// (not a pattern) that matched none says that only names were matched, how many files under it had their text
    /// unread, and the file_find call with the same folder and subdirectory and content Y (WindowsKnownFileAdapter).
    /// </summary>
    public const string FindContentNext = "find_content_next";

    private static readonly AsyncLocal<string?> Setting = new();

    public static bool On(string aid)
    {
        string setting = (Setting.Value ?? Environment.GetEnvironmentVariable("BAXY_AYUDAS") ?? string.Empty).Trim();
        if (setting.Length == 0 || setting.Equals("all", StringComparison.OrdinalIgnoreCase)) return true;
        if (setting.Equals("none", StringComparison.OrdinalIgnoreCase) || setting == "0") return false;
        return setting.Split(',', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries)
            .Contains(aid, StringComparer.OrdinalIgnoreCase);
    }

    /// <summary>For a test: the setting of this async flow only (tests run in parallel and share the environment).</summary>
    internal static IDisposable Use(string setting)
    {
        string? before = Setting.Value;
        Setting.Value = setting;
        return new Restore(() => Setting.Value = before);
    }

    private sealed class Restore(Action restore) : IDisposable
    {
        public void Dispose() => restore();
    }
}
