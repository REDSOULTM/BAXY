namespace Baxy.Providers.Windows.Infrastructure;

/// <summary>
/// The aids of the «ayudas al modelo» goal (2026-10-19): facts added to what a tool's result tells the model, never a
/// choice of tool, an argument, a run or a reply. <c>BAXY_AYUDAS</c> says which are on: unset, empty or «all», every
/// one; «none» (or «0»), none, and the product reads as it did before them; otherwise the comma-separated ids that are
/// on. The mind reads the same variable for its own aids (src/baxy_mind/mind.py, <c>_aid_on</c>).
/// </summary>
public static class ModelAids
{
    /// <summary>E011: a calculator.expression.evaluate with no Calculator window says app_open can start it.</summary>
    public const string CalculatorNext = "calculator_next";

    /// <summary>Accessible mode: system.settings.set says what the mode changes and which modes do not exist yet.</summary>
    public const string AccessibleScope = "accessible_scope";

    /// <summary>BAXY Renew cu (C14): audio.microphone.mute says it is Windows' switch, not an application's own mute.</summary>
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

    /// <summary>Renew al máximo (F002): window.application.status says as a sentence whether BAXY opened the window.</summary>
    public const string ProvenanceNext = "provenance_next";

    /// <summary>Renew al máximo (w5, F004): a text typed with no window named says, as a sentence, the one window it went into.</summary>
    public const string TypedTargetNext = "typed_target_next";

    /// <summary>Renew al máximo (w5): an act stopped by the person's input says why it stopped and how the window is seen.</summary>
    public const string InterruptedNext = "interrupted_next";

    /// <summary>
    /// Auditoría de falsedades (F001): an invalid_or_expired_window_id says the id is used up, nothing was done to the
    /// window and nothing was read of it.
    /// </summary>
    public const string WindowIdSpent = "window_id_spent";

    /// <summary>Renew al máximo (w5, E024): an append refused for a missing file says where one of that name is.</summary>
    public const string AppendElsewhere = "append_elsewhere";

    /// <summary>Renew al máximo (w5, E020): a look at BAXY's working folder says it is BAXY's, and one that found nothing that the person's folders were not looked at.</summary>
    public const string WorkFolderScope = "work_folder_scope";

    /// <summary>
    /// Renew al máximo (w6, rutas): a file call that leaves out the folder the person named in this turn is routed there
    /// (a read) or refused before any effect with the call that names it (anything else) (Baxy.App.SaidFolders).
    /// </summary>
    public const string SaidFolder = "said_folder";

    /// <summary>
    /// Holdout v4 (en vivo: «Biblioteca» pressed 7 times in Steam, each visible_button_postread_unchanged, 50 s): the
    /// same click seen unchanged a second time in a row says so, and the places its application opens straight at.
    /// </summary>
    public const string RepeatedUnchangedNext = "repeated_unchanged_next";

    /// <summary>
    /// Renew al máximo (w8, falsedades F019): a look at a window drawn without controls (Steam's library, read only by
    /// OCR) says its text is the screen's words, pressed by label, and that a word missing from the controls is not absent.
    /// </summary>
    public const string DrawnTextNext = "drawn_text_next";

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
