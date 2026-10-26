using System.ComponentModel;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// PC-F8 cierre (identidad: «sólo se confirma lo destructivo o peligroso»): closing an application with nothing unsaved
/// that BAXY did not open (Paint with a blank canvas, an editor with its file saved) asked for the yes all the same.
/// A window whose own reading shows no changes holds nothing of the person: its title carries no unsaved mark, it is
/// not a console or a terminal, it is not in a call and it shows no dialog. Any reading that fails, or that cannot
/// tell, keeps the yes. No real window is touched: the platform is a fake.
/// </summary>
[TestFixture]
public sealed class CloseWithoutChangesTests
{
    private const string PaintPath =
        @"C:\Program Files\WindowsApps\Microsoft.Paint_11.2409.29.0_x64__8wekyb3d8bbwe\PaintApp\mspaint.exe";
    private const string NotepadPath =
        @"C:\Program Files\WindowsApps\Microsoft.WindowsNotepad_11.2409.9.0_x64__8wekyb3d8bbwe\Notepad\Notepad.exe";

    [TestCase("Sin título - Paint")]
    [TestCase("nota.txt - Bloc de notas")]
    public async Task AWindowWhoseTitleShowsNoChangesClosesWithoutAsking(string title)
    {
        var provider = Provider(new FakePlatform(Window(title)) { Title = title });

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.True);
    }

    [TestCase("*Sin título - Paint")]
    [TestCase("*nota.txt - Bloc de notas")]
    [TestCase("nota.txt* - Bloc de notas")]
    [TestCase("nota.txt - Bloc de notas*")]
    [TestCase("● nota.txt - Editor")]
    [TestCase("nota.txt (Sin guardar) - Editor")]
    [TestCase("nota.txt [Unsaved] - Editor")]
    [TestCase("nota.txt [Modified] - Editor")]
    public async Task AWindowWhoseTitleMarksUnsavedChangesStillAsks(string title)
    {
        var provider = Provider(new FakePlatform(Window(title)) { Title = title });

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.False);
    }

    [Test]
    public async Task AConsoleStillAsks()
    {
        // Its window class says console (conhost, a terminal): whatever runs in it ends with the window.
        var provider = Provider(new FakePlatform(new WindowIdentity(
            (nint)321, 500, 9_000, "cmd", DateTimeOffset.UnixEpoch, @"C:\Windows\System32\cmd.exe"))
        {
            Title = "Símbolo del sistema",
            Console = true,
        });

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.False);
    }

    [Test]
    public async Task ATerminalOrAnEditorThatHostsOneStillAsksWhateverItsClass()
    {
        // The processes where Enter runs what was typed (VisibleControlSurface.RunsWhatIsTyped) keep the yes too.
        var provider = Provider(new FakePlatform(new WindowIdentity(
            (nint)321, 500, 9_000, "WindowsTerminal", DateTimeOffset.UnixEpoch, @"C:\Apps\WindowsTerminal.exe"))
        {
            Title = "PowerShell",
        });

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.False);
    }

    [Test]
    public async Task AWindowShowingADialogStillAsks()
    {
        // A dialog of its own is open (a copy in progress, a question): closing may cancel it.
        const string title = "nota.txt - Bloc de notas";
        var provider = Provider(new FakePlatform(Window(title)) { Title = title, Dialogs = [(nint)4_040] });

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.False);
    }

    [Test]
    public async Task AWindowInACallStillAsks()
    {
        const string title = "Sin título - Paint";
        var provider = Provider(new FakePlatform(Window(title)) { Title = title, CapturingMicrophone = true });

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.False);
    }

    [TestCase(Failure.Title)]
    [TestCase(Failure.EmptyTitle)]
    [TestCase(Failure.Console)]
    [TestCase(Failure.Dialogs)]
    [TestCase(Failure.ConsoleUnknown)]
    public async Task AReadingThatFailsStillAsks(Failure failure)
    {
        const string title = "Sin título - Paint";
        var platform = new FakePlatform(Window(title)) { Title = title };
        var provider = Provider(platform);
        string windowId = await ActiveWindowIdAsync(provider);
        platform.Fails = failure;

        Assert.That(provider.HoldsNoDocument(windowId), Is.False);
    }

    [Test]
    public void APlatformThatCannotTellAConsoleSaysItIsOne()
    {
        IWindowControlPlatform silent = new SilentPlatform();

        Assert.That(silent.ShowsConsole(Window("Sin título - Paint")), Is.True);
    }

    public enum Failure
    {
        None,
        Title,
        EmptyTitle,
        Console,
        Dialogs,
        ConsoleUnknown,
    }

    private static WindowIdentity Window(string title) => title.Contains("Paint", StringComparison.Ordinal)
        ? new WindowIdentity((nint)321, 500, 9_000, "mspaint", DateTimeOffset.UnixEpoch, PaintPath)
        : new WindowIdentity((nint)654, 600, 12_000, "Notepad", DateTimeOffset.UnixEpoch, NotepadPath);

    private static WindowsWindowControlProvider Provider(FakePlatform platform) =>
        new(platform, new Applications.WindowsInstalledApplicationOpenProvider(), new LaunchProvenance());

    private static async Task<string> ActiveWindowIdAsync(WindowsWindowControlProvider provider)
    {
        WindowResolveResult result = await provider.ResolveForegroundAsync(CancellationToken.None);
        Assert.That(result.Succeeded && result.Verified, Is.True, result.ErrorCode);
        return result.Windows.Single().WindowId;
    }

    private sealed class FakePlatform(WindowIdentity window) : IWindowControlPlatform
    {
        public string Title { get; init; } = string.Empty;
        public bool Console { get; init; }
        public bool CapturingMicrophone { get; init; }
        public IReadOnlyList<nint> Dialogs { get; init; } = [];
        public Failure Fails { get; set; }

        public DateTimeOffset UtcNow => DateTimeOffset.UnixEpoch;

        public WindowSnapshot? FindForegroundWindow() => Snapshot(Title);

        public WindowEnumeration FindVisibleWindows(string processName, int limit, bool byTitle = false, int offset = 0,
            bool allWindows = false, CancellationToken cancellationToken = default) => new([], 0, true);

        public WindowSnapshot Observe(WindowIdentity identity) => Fails switch
        {
            Failure.Title => throw new Win32Exception(5),
            Failure.EmptyTitle => Snapshot(string.Empty),
            _ => identity.Handle == window.Handle ? Snapshot(Title) : throw new WindowIdentityChangedException(),
        };

        public bool ShowsConsole(WindowIdentity identity) => Fails switch
        {
            Failure.Console => throw new InvalidOperationException("class unreadable"),
            Failure.ConsoleUnknown => true,
            _ => Console,
        };

        public IReadOnlyList<nint> OwnedDialogs(WindowIdentity identity) =>
            Fails == Failure.Dialogs ? throw new InvalidOperationException("not enumerated") : Dialogs;

        public bool CapturesMicrophone(WindowIdentity identity) => CapturingMicrophone;

        public bool Execute(WindowIdentity identity, WindowControlAction action) => false;
        public bool SetBounds(WindowIdentity identity, WindowBounds bounds) => false;
        public bool RequestClose(WindowIdentity identity) => false;
        public bool RequestSystemClose(WindowIdentity identity) => false;
        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) => ValueTask.CompletedTask;

        private WindowSnapshot Snapshot(string title) =>
            new(window, "normal", true, new WindowBounds(0, 0, 800, 600), title);
    }

    // A platform that implements nothing beyond what every platform must.
    private sealed class SilentPlatform : IWindowControlPlatform
    {
        public DateTimeOffset UtcNow => DateTimeOffset.UnixEpoch;
        public WindowSnapshot? FindForegroundWindow() => null;
        public WindowEnumeration FindVisibleWindows(string processName, int limit, bool byTitle = false, int offset = 0,
            bool allWindows = false, CancellationToken cancellationToken = default) => new([], 0, true);
        public WindowSnapshot Observe(WindowIdentity identity) => throw new WindowIdentityChangedException();
        public bool Execute(WindowIdentity identity, WindowControlAction action) => false;
        public bool SetBounds(WindowIdentity identity, WindowBounds bounds) => false;
        public bool RequestClose(WindowIdentity identity) => false;
        public bool RequestSystemClose(WindowIdentity identity) => false;
        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) => ValueTask.CompletedTask;
    }
}
