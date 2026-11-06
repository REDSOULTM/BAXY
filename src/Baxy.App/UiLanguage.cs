using System.Globalization;

namespace Baxy.App;

/// <summary>
/// The language of BAXY's own words on screen and in its voice (Steam, 2026-11-04). The person's choice is «auto», «es»
/// or «en»: the view sends it (PUT /settings/language) and the field settings keep it for the next start
/// (<see cref="FieldSettings.Language"/>). «auto», or no choice yet, is Windows' display language, resolved here only
/// (<see cref="Resolve"/>): Spanish for Spanish, English for any other. Only what the person reads or hears follows it:
/// what the model reads (the catalog's groups, a conversation's titles, the internet log) stays as it was, in Spanish.
/// Words already shown keep theirs; the tray menu, built at each opening, takes the new one at its next. A projection
/// that says several words reads the language once (<see cref="IsEnglish"/>) and passes it down, so one chip or card is
/// never half in each.
/// </summary>
internal static class UiLanguage
{
    internal const string Auto = "auto";
    internal const string Spanish = "es";
    internal const string English = "en";

    private static string _choice = Auto;

    /// <summary>The language in use now: «es» or «en».</summary>
    internal static string Current => Resolve(Volatile.Read(ref _choice));

    internal static bool IsEnglish => Current == English;

    /// <summary>How dates and the order of words go in that language.</summary>
    internal static CultureInfo CultureOf(bool english) => CultureInfo.GetCultureInfo(english ? "en-US" : "es-ES");

    /// <summary>A choice the person can make: «auto», «es» or «en».</summary>
    internal static bool IsChoice(string? choice) => choice is Auto or Spanish or English;

    /// <summary>The language a choice stands for: «es» or «en» as chosen, Windows' display language for «auto» or none.</summary>
    internal static string Resolve(string? choice) =>
        choice is Spanish or English ? choice
        : CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == Spanish ? Spanish : English;

    /// <summary>Uses <paramref name="choice"/> from now on (null is «auto»); any other word changes nothing.</summary>
    internal static void Use(string? choice)
    {
        if (choice is null || IsChoice(choice))
        {
            Volatile.Write(ref _choice, choice ?? Auto);
        }
    }

    /// <summary>The words in the language in use: for a text said alone.</summary>
    internal static string Say(string spanish, string english) => Say(IsEnglish, spanish, english);

    /// <summary>The words in the language a projection read once.</summary>
    internal static string Say(bool inEnglish, string spanish, string english) => inEnglish ? english : spanish;
}
