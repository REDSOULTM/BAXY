namespace Baxy.App;

/// <summary>
/// ING5 (owner's decision of 2026-11-13: the language is a setting, and choosing it puts all the model reads in it): the
/// language the running mind was configured with (MindSidecarClient.ConfiguredLanguage), against the one chosen now
/// (<see cref="UiLanguage.Current"/>). The mind takes its language with its catalog and writes its prompt prefix in it,
/// so another language relaunches it as other texts or another tool profile do (MainWindowViewModel.LanguageChanged),
/// and its prefix is read once in that language.
/// </summary>
internal sealed class MindLanguage
{
    // «es» or «en»; null until a mind came up (with none, a change waits for the next start and asks for no relaunch).
    private string? _applied;

    /// <summary>A mind came up configured in <paramref name="language"/>.</summary>
    internal void Started(string? language) => Volatile.Write(ref _applied, language);

    /// <summary>Whether a mind came up and the language chosen now is not the one it was configured in. «auto» that
    /// stands for the same language as the choice before is no change.</summary>
    internal bool NeedsSwitch =>
        Volatile.Read(ref _applied) is { } applied && !string.Equals(applied, UiLanguage.Current, StringComparison.Ordinal);
}
