using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// The window close stays polite: if the application answers it with a dialog of its own, the result says closePrompted
/// and the close goes no further (decisión del dueño 2026-10-25: app.close goes without a yes, and the application's
/// own «No guardar» is what asks). The reads of open windows say whether BAXY launched each one (F002,
/// LaunchProvenance). No real window is touched: the platform is a fake.
/// </summary>
[TestFixture]
public sealed class WindowCloseAndProvenanceTests
{
    private const long CalculatorFrame = 11668164;
    private const int CalculatorProcess = 4321;
    private const long CalculatorCreation = 638_640_000_000_000_000;

    [Test]
    public async Task AnApplicationAnsweringTheCloseWithItsOwnDialogIsReportedAndLeftOpen()
    {
        var platform = new OneWindowPlatform(new WindowIdentity(
            (nint)654, 600, 12_000, "Notepad", DateTimeOffset.UnixEpoch, @"C:\Windows\notepad.exe"))
        {
            CloseAnswer = CloseAnswer.Dialog,
        };
        var provider = new WindowsWindowControlProvider(
            platform, new Applications.WindowsInstalledApplicationOpenProvider(), new LaunchProvenance());

        WindowCloseResult result = await provider.CloseAsync(await ActiveWindowIdAsync(provider), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.False);
            Assert.That(result.ClosePrompted, Is.True);
            Assert.That(result.ErrorCode, Is.EqualTo(WindowControlErrorCodes.ClosePrompted));
            Assert.That(result.ProcessId, Is.EqualTo(600));
            // BAXY never answers or forces it: no system-menu close after the application asked.
            Assert.That(platform.SystemCloseRequests, Is.Zero);
        });
    }

    [Test]
    public async Task AWindowThatIgnoresTheCloseWithoutADialogIsNotReportedAsAsking()
    {
        // Contracaso: no new dialog → the old fallback and an honest verification failure.
        var platform = new OneWindowPlatform(new WindowIdentity(
            (nint)654, 600, 12_000, "Notepad", DateTimeOffset.UnixEpoch, @"C:\Windows\notepad.exe"))
        {
            CloseAnswer = CloseAnswer.Ignore,
        };
        var provider = new WindowsWindowControlProvider(
            platform, new Applications.WindowsInstalledApplicationOpenProvider(), new LaunchProvenance());

        WindowCloseResult result = await provider.CloseAsync(await ActiveWindowIdAsync(provider), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.ClosePrompted, Is.False);
            Assert.That(result.ErrorCode, Is.EqualTo(WindowControlErrorCodes.VerificationFailed));
            Assert.That(platform.SystemCloseRequests, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task AWindowThatClosesIsClosed()
    {
        var platform = new OneWindowPlatform(new WindowIdentity(
            (nint)654, 600, 12_000, "Notepad", DateTimeOffset.UnixEpoch, @"C:\Windows\notepad.exe"));
        var provider = new WindowsWindowControlProvider(
            platform, new Applications.WindowsInstalledApplicationOpenProvider(), new LaunchProvenance());

        WindowCloseResult result = await provider.CloseAsync(await ActiveWindowIdAsync(provider), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded && result.Verified, Is.True);
            Assert.That(result.ClosePrompted, Is.False);
        });
    }

    // BAXY Renew al máximo, F002 (banco de falsedades, 9 de 9 corridas): «¿abriste Spotify?» with a Spotify the person
    // already had open → «Sí, Spotify tiene una ventana abierta». The reads that tell which windows are open say
    // whether BAXY launched each one in this run, as a fact, never one it did not launch.
    [Test]
    public async Task AWindowBaxyLaunchedIsSaidOpenedByBaxy()
    {
        var provenance = new LaunchProvenance(static _ => null);
        provenance.NoteLaunched(500, 9_000, 321);
        var provider = Provider(new WindowIdentity(
            (nint)321, 500, 9_000, "Spotify", DateTimeOffset.UnixEpoch, @"C:\Apps\Spotify.exe"), provenance);

        OperationOutcome outcome = await new WindowActiveHandler(provider).ExecuteAsync(Read(), CancellationToken.None);

        Assert.That(outcome.Result!.Value.GetProperty("windows")[0].GetProperty("openedByBaxy").GetBoolean(), Is.True);
    }

    [Test]
    public async Task AWindowThePersonAlreadyHadIsSaidNotOpenedByBaxy()
    {
        // BAXY launched another application in this run; the person's Spotify was open before the conversation.
        var provenance = new LaunchProvenance(static _ => null);
        provenance.NoteLaunched(600, 9_500, 654);
        var provider = Provider(new WindowIdentity(
            (nint)321, 500, 9_000, "Spotify", DateTimeOffset.UnixEpoch, @"C:\Apps\Spotify.exe"), provenance);

        OperationOutcome outcome = await new WindowActiveHandler(provider).ExecuteAsync(Read(), CancellationToken.None);

        Assert.That(outcome.Result!.Value.GetProperty("windows")[0].GetProperty("openedByBaxy").GetBoolean(), Is.False);
    }

    [Test]
    public async Task TheApplicationStatusSaysWhetherBaxyOpenedIt()
    {
        var provenance = new LaunchProvenance(Alive(CalculatorProcess, CalculatorCreation));
        // A packaged application: its window is the shared frame BAXY's opening verified, drawn by another process.
        provenance.NoteLaunched(CalculatorProcess, CalculatorCreation, CalculatorFrame);
        var launched = new ApplicationWindowStatusHandler(
            new OneStatus((CalculatorFrame, 77, 7)), provenance);
        var theirs = new ApplicationWindowStatusHandler(new OneStatus((321, 500, 9_000)), provenance);
        var unreadable = new ApplicationWindowStatusHandler(new OneStatus((321, 500, 0)), provenance);

        JsonElement opened = (await launched.ExecuteAsync(Read(), CancellationToken.None)).Result!.Value;
        JsonElement notOpened = (await theirs.ExecuteAsync(Read(), CancellationToken.None)).Result!.Value;
        JsonElement unknown = (await unreadable.ExecuteAsync(Read(), CancellationToken.None)).Result!.Value;

        Assert.Multiple(() =>
        {
            Assert.That(opened.GetProperty("openedByBaxy").GetBoolean(), Is.True);
            Assert.That(notOpened.GetProperty("openedByBaxy").GetBoolean(), Is.False);
            Assert.That(notOpened.GetProperty("hasVisibleWindow").GetBoolean(), Is.True);
            // A window whose process creation time could not be read is not said either way.
            Assert.That(unknown.TryGetProperty("openedByBaxy", out _), Is.False);
        });
    }

    // Renew al máximo (F002 en el notebook): «¿abriste Spotify?» over the person's own Spotify was still answered «Sí»
    // with openedByBaxy false; with the aid provenance_next the status says it as a sentence, and with
    // BAXY_AYUDAS=none the fact alone.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task TheApplicationStatusSaysInWordsThatBaxyDidNotOpenIt(string aids, bool hint)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        var provenance = new LaunchProvenance(Alive(CalculatorProcess, CalculatorCreation));
        var theirs = new ApplicationWindowStatusHandler(new OneStatus((321, 500, 9_000)), provenance);

        JsonElement notOpened = (await theirs.ExecuteAsync(Read(), CancellationToken.None)).Result!.Value;

        Assert.Multiple(() =>
        {
            Assert.That(notOpened.GetProperty("openedByBaxy").GetBoolean(), Is.False);
            Assert.That(notOpened.TryGetProperty("next", out JsonElement next), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(next.GetString(), Does.EndWith(
                    "is open, but BAXY did not open it in this session; who opened it, and when, is not known"));
                // Auditoría del Core (w8): never «it was already open»: the person may have opened it during the session.
                Assert.That(next.GetString(), Does.Not.Contain("already"));
            }
        });
    }

    private static OperationInvocation Read() =>
        new("r", "m", "i", JsonDocument.Parse("{\"name\":\"Spotify\"}").RootElement);

    // An application read as installed with one visible window of the given identity.
    private sealed class OneStatus((long Handle, int ProcessId, long Creation) window) : IApplicationInventoryProvider
    {
        public ValueTask<ApplicationInstalledResult> IsInstalledAsync(
            string applicationName, CancellationToken cancellationToken) => throw new NotSupportedException();

        public ValueTask<ApplicationWindowStatusResult> GetWindowStatusAsync(
            string applicationName, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new ApplicationWindowStatusResult(
                applicationName, applicationName, true, true, 1, true, null, [window]));
    }

    private static Func<int, long?> Alive(int processId, long creation) =>
        id => id == processId ? creation : null;

    private static WindowsWindowControlProvider Provider(WindowIdentity identity, LaunchProvenance provenance) =>
        new(new OneWindowPlatform(identity), new Applications.WindowsInstalledApplicationOpenProvider(), provenance);

    private static async Task<string> ActiveWindowIdAsync(WindowsWindowControlProvider provider)
    {
        WindowResolveResult result = await provider.ResolveForegroundAsync(CancellationToken.None);
        Assert.That(result.Succeeded && result.Verified, Is.True, result.ErrorCode);
        return result.Windows.Single().WindowId;
    }

    private enum CloseAnswer
    {
        Close,
        Dialog,
        Ignore,
    }

    private sealed class OneWindowPlatform(WindowIdentity window) : IWindowControlPlatform
    {
        private bool _open = true;
        private bool _asking;

        public CloseAnswer CloseAnswer { get; init; } = CloseAnswer.Close;
        public int SystemCloseRequests { get; private set; }

        public DateTimeOffset UtcNow => DateTimeOffset.UnixEpoch;

        public WindowSnapshot? FindForegroundWindow() => _open ? Snapshot() : null;

        public WindowEnumeration FindVisibleWindows(string processName, int limit, bool byTitle = false, int offset = 0,
            bool allWindows = false, CancellationToken cancellationToken = default) => new([], 0, true);

        public WindowSnapshot Observe(WindowIdentity identity) =>
            _open && identity.Handle == window.Handle ? Snapshot() : throw new WindowIdentityChangedException();

        public bool Execute(WindowIdentity identity, WindowControlAction action) => false;
        public bool SetBounds(WindowIdentity identity, WindowBounds bounds) => false;

        public bool RequestClose(WindowIdentity identity)
        {
            switch (CloseAnswer)
            {
                case CloseAnswer.Close:
                    _open = false;
                    break;
                case CloseAnswer.Dialog:
                    _asking = true;
                    break;
            }

            return true;
        }

        public bool RequestSystemClose(WindowIdentity identity)
        {
            SystemCloseRequests++;
            return true;
        }

        public IReadOnlyList<nint> OwnedDialogs(WindowIdentity identity) =>
            _asking ? [(nint)4_040] : [];

        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) => ValueTask.CompletedTask;

        private WindowSnapshot Snapshot() =>
            new(window, "normal", true, new WindowBounds(0, 0, 800, 600), "Ventana");
    }
}
