using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Which window a computer-use mission takes for its application while the application's process is unknown
/// (safety review 2026-10-07): the executable first, else the application named in the title's last segment as
/// whole words; never an editor, a terminal, a console or BAXY that the request did not name. Pure rules; the last
/// test only reads the list of windows, nothing on the desktop is touched.
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

    // A process's window is one a person can see: never a cloaked or untitled frame it also holds (the shell's
    // explorer.exe holds one larger than its folder windows; taking it made every look bound to the process wait out
    // its retries, ≈1.8 s each). Pure rule over synthetic window records.
    [Test]
    public void AProcessWindowIsNeverALargerFrameWithoutAUsableSurface()
    {
        VisibleControlSurface.TopLevelWindow[] windows =
        [
            new(10, 7, Usable: false, Area: 3_000_000),
            new(11, 7, Usable: true, Area: 800_000),
            new(12, 9, Usable: true, Area: 5_000_000),
        ];
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.ChooseProcessWindow(windows, 7, front: 0), Is.EqualTo((nint)11));
            Assert.That(VisibleControlSurface.ChooseProcessWindow(windows, 7, front: 10), Is.EqualTo((nint)11),
                "a front window without a surface gives way to the usable one");
            Assert.That(VisibleControlSurface.ChooseProcessWindow(windows, 8, front: 0), Is.EqualTo((nint)0));
        });
    }

    // File Explorer with two folder windows open: the one the person brought to the front is the one, even when the
    // other is larger; another process's window in front does not count.
    [Test]
    public void TheProcessWindowInFrontIsTakenOverALargerOne()
    {
        VisibleControlSurface.TopLevelWindow[] windows =
        [
            new(20, 4, Usable: true, Area: 2_000_000),
            new(21, 4, Usable: true, Area: 600_000),
            new(22, 5, Usable: true, Area: 900_000),
        ];
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.ChooseProcessWindow(windows, 4, front: 21), Is.EqualTo((nint)21));
            Assert.That(VisibleControlSurface.ChooseProcessWindow(windows, 4, front: 22), Is.EqualTo((nint)20));
            Assert.That(VisibleControlSurface.ChooseProcessWindow(windows, 4, front: 0), Is.EqualTo((nint)20));
        });
    }
}
