using Baxy.Contracts;

namespace Baxy.Providers.Windows.Infrastructure;

/// <summary>
/// ING6 (owner's decision of 2026-11-13: the language is a setting, and choosing it puts all the model reads in it): the
/// language of BAXY's own words in what this process writes for the model: the sky and the weekday of the weather, the
/// reason a look was left without its tree, the mark of a minimized window, the question asked of a capture, a reading's
/// unit. The App resolves the setting (Baxy.App.UiLanguage) and says it with each request
/// (<see cref="OperationRequest.Language"/>); the core takes it before it runs the request (Baxy.Core.CoreRequest), one
/// request at a time, so a change of the setting is followed at the next call with no restart. A request that names none
/// is in Spanish, with every word as it was before the setting reached here. What the PC gives (a window's title, a
/// control's name, a text on screen, a file's name) is no language's and stays as read.
/// </summary>
public static class ModelLanguage
{
    private static volatile bool _english;

    public static bool IsEnglish => _english;

    /// <summary>Uses <paramref name="language"/> from now on: English for <see cref="ProtocolLanguages.English"/>,
    /// Spanish for any other or none.</summary>
    public static void Use(string? language) => _english = language == ProtocolLanguages.English;

    /// <summary>The words in the language in use.</summary>
    public static string Say(string spanish, string english) => _english ? english : spanish;
}
