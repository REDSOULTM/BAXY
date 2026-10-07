using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Which window a computer-use mission takes for its application while the application's process is unknown
/// (safety review 2026-10-07): the executable first, else the application named in the title's last segment as
/// whole words; never an editor, a terminal, a console or BAXY that the request did not name. Pure rules, nothing on
/// the desktop is read.
/// </summary>
[TestFixture]
public sealed class ComputerUseWindowIdentityTests
{
    [TestCase("SteamLocalAdapter.cs - BAXY Definitivo - Visual Studio Code", "Steam", false)]
    [TestCase("Steam - Bloc de notas", "Steam", false)]
    [TestCase("Steamworks", "Steam", false)]
    [TestCase("Steam", "Steam", true)]
    [TestCase("Ron92 - Discord", "Discord", true)]
    [TestCase("#general | BAXY - Discord", "Discord", true)]
    [TestCase("Nueva pestaña - Google Chrome", "Google Chrome", true)]
    [TestCase("Inicio - Personal - Microsoft​ Edge", "Microsoft Edge", true)]
    [TestCase("Calculadora", "Calculadora", true)]
    [TestCase("notas.txt - Bloc de notas", "Bloc de notas", true)]
    public void TheTitleNamesTheApplicationOnlyInItsLastSegmentAsWholeWords(string title, string application, bool names)
    {
        Assert.That(VisibleControlSurface.TitleNamesApplication(title, application), Is.EqualTo(names));
    }

    [TestCase("Spotify", "Spotify", true)]
    [TestCase("chrome", "Google Chrome", true)]
    [TestCase("EpicGamesLauncher", "Epic Games Launcher", true)]
    [TestCase("steamwebhelper", "Steam", false)]
    [TestCase("Code", "Steam", false)]
    public void TheExecutableIsTheApplicationByItsNameOrADistinctiveWord(string process, string application, bool matches)
    {
        Assert.That(VisibleControlSurface.ProcessIsApplication(process, application), Is.EqualTo(matches));
    }

    [TestCase("Code", "Steam", true)]
    [TestCase("Code.exe", "Steam", true)]
    [TestCase("devenv", "Steam", true)]
    [TestCase("WindowsTerminal", "Steam", true)]
    [TestCase("powershell", "Steam", true)]
    [TestCase("cmd", "Steam", true)]
    [TestCase("Baxy", "Steam", true)]
    [TestCase("baxy-core", "Steam", true)]
    [TestCase("Code", "Visual Studio Code", false)]
    [TestCase("WindowsTerminal", "Terminal", false)]
    [TestCase("steamwebhelper", "Steam", false)]
    public void AnEditorATerminalOrBaxyIsTheApplicationOnlyWhenNamed(string process, string application, bool protectedFrom)
    {
        Assert.That(VisibleControlSurface.ProtectedFrom(process, application), Is.EqualTo(protectedFrom));
    }
}
