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
