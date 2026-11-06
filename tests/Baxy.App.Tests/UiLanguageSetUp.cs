using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Steam (2026-11-04): BAXY's own words follow the interface's language, Windows' until the view chooses one
/// (UiLanguage). The App's tests read its Spanish words, so around the whole assembly they run in Spanish whatever the
/// language of the Windows that runs them; a test about English sets it itself and gives Spanish back (UiLanguageTests).
/// </summary>
[SetUpFixture]
public sealed class UiLanguageSetUp
{
    [OneTimeSetUp]
    public void InSpanish() => UiLanguage.Use(UiLanguage.Spanish);

    [OneTimeTearDown]
    public void AsWindowsSays() => UiLanguage.Use(null);
}
