using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// APP2 (VIVO14, reparo 1): with BAXY open, the installer opened by hand showed the agreement, took «La acepto» and
/// «Instalarme», and only then said «Ya estoy abierto en este PC. Ciérrame y vuelve a intentarlo», and exited with 0,
/// which a script reads as installed. An open BAXY is told first, the window offers to close it, and a window that
/// closes without having finished exits with something other than 0.
/// </summary>
[TestFixture]
internal sealed class OpenBaxyTests
{
    [Test]
    public void An_open_baxy_is_told_before_the_agreement_and_the_greeting()
    {
        string First(bool uninstalling, bool updating, bool baxyOpen, bool asksAgreement) =>
            MainWindow.FirstScreen(uninstalling, updating, baxyOpen, asksAgreement, "uninstall", "open", "agreement", "greeting");

        Assert.Multiple(() =>
        {
            Assert.That(First(uninstalling: false, updating: false, baxyOpen: true, asksAgreement: true), Is.EqualTo("open"));
            Assert.That(First(uninstalling: false, updating: false, baxyOpen: true, asksAgreement: false), Is.EqualTo("open"));
            Assert.That(First(uninstalling: false, updating: false, baxyOpen: false, asksAgreement: true), Is.EqualTo("agreement"));
            Assert.That(First(uninstalling: false, updating: false, baxyOpen: false, asksAgreement: false), Is.EqualTo("greeting"));
            Assert.That(First(uninstalling: false, updating: true, baxyOpen: true, asksAgreement: true), Is.EqualTo("agreement"),
                "--update: the BAXY that started it closes itself for it");
            Assert.That(First(uninstalling: true, updating: false, baxyOpen: true, asksAgreement: false), Is.EqualTo("uninstall"));
        });
    }

    // «Cerrarme y seguir» asks BAXY to exit as its own «Salir» does (the App's exit event, BaxyExitHandler); with no BAXY
    // listening there is nobody to ask.
    [Test]
    public void Closing_baxy_signals_its_exit_event()
    {
        string name = @"Local\BAXY.Installer.Tests.Exit." + Guid.NewGuid().ToString("N");
        Assert.That(MainWindow.AskBaxyToExit(name), Is.False, "no BAXY listening");

        using EventWaitHandle exit = new(false, EventResetMode.AutoReset, name);
        Assert.Multiple(() =>
        {
            Assert.That(MainWindow.AskBaxyToExit(name), Is.True);
            Assert.That(exit.WaitOne(0), Is.True, "BAXY heard it");
        });
    }

    // REM1 (REV12 A-2): the exit event is one for every copy of BAXY. «Cerrarme y seguir» closed whichever was open, from any
    // folder, and opened this folder's. It asks only when the BAXY running is this folder's.
    [Test]
    public void Close_me_asks_only_the_baxy_of_this_folder()
    {
        Assert.Multiple(() =>
        {
            Assert.That(MainWindow.MayAskToExit(runningHere: 1, runningElsewhere: false), Is.True);
            Assert.That(MainWindow.MayAskToExit(runningHere: 0, runningElsewhere: true), Is.False, "another folder's BAXY stays");
            Assert.That(MainWindow.MayAskToExit(runningHere: 1, runningElsewhere: true), Is.False, "the event could reach the other");
            Assert.That(MainWindow.MayAskToExit(runningHere: 0, runningElsewhere: false), Is.False);
        });
    }

    // REM1 (REV12 A-2): which BAXY runs is told by PID and the path of its exe. This test's own process stands in for one.
    [Test]
    public void A_running_exe_is_told_by_its_folder()
    {
        string running = Environment.ProcessPath!;
        string sameNameElsewhere = Path.Combine(Path.GetTempPath(), "BAXY-App-other", "app", Path.GetFileName(running));
        Assert.Multiple(() =>
        {
            Assert.That(RunningBaxy.From(running), Does.Contain(Environment.ProcessId));
            Assert.That(RunningBaxy.From(sameNameElsewhere), Does.Not.Contain(Environment.ProcessId));
            Assert.That(RunningBaxy.AnyElsewhere(sameNameElsewhere), Is.True);
            Assert.That(RunningBaxy.AnyAlive([Environment.ProcessId]), Is.True);
        });
    }

    [Test]
    public void The_window_exits_with_zero_only_when_it_finished()
    {
        Assert.Multiple(() =>
        {
            Assert.That(MainWindow.ExitCode(finished: null), Is.EqualTo(Program.Failure), "closed before finishing: BAXY open, a failure, cancelled");
            Assert.That(MainWindow.ExitCode(finished: 0), Is.Zero, "installed or uninstalled");
            Assert.That(MainWindow.ExitCode(finished: QuietInstall.NotRegistered), Is.EqualTo(QuietInstall.NotRegistered));
        });
    }

    [TestCase("es", "Con ventana, lo mismo")]
    [TestCase("en", "With a window, the same")]
    public void The_help_says_the_window_exits_as_quiet_does(string language, string said) =>
        Assert.That(CommandLine.HelpText(language, @"C:\Users\someone\AppData\Local\Programs\BAXY-App"), Does.Contain(said));
}
