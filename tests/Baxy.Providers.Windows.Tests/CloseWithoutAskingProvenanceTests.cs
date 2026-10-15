using System.Buffers.Binary;
using BaxyInputMark = Baxy.Providers.Windows.External.BaxyInputMark;
using WindowsUserInputPause = Baxy.Providers.Windows.External.WindowsUserInputPause;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// v3 r22 uso real, «cerrar sin confirmar lo que no pierde nada» (pasada r18):
/// t3-c18 t4 «ya ciérrala» sobre la Calculadora que BAXY había abierto en esa conversación (app.open
/// alreadyRunning=false, ventana 11668164, el marco de ApplicationFrameHost) y en la que sólo hizo clics → pidió
/// confirmación; t4-c03 t4 «ya cierra discord» → pidió confirmación y no se cerró. A window of a process BAXY launched
/// and never wrote into, or of an application whose content lives in the account, holds nothing of the person. The
/// close stays polite; if the application answers it with a dialog of its own, the result says closePrompted and the
/// close goes no further. No real window is touched: the platform is a fake.
/// </summary>
[TestFixture]
public sealed class CloseWithoutAskingProvenanceTests
{
    private const string FrameHost = @"C:\Windows\System32\ApplicationFrameHost.exe";
    private const long CalculatorFrame = 11668164;
    private const int CalculatorProcess = 4321;
    private const long CalculatorCreation = 638_640_000_000_000_000;

    [Test]
    public async Task TheCalculatorBaxyOpenedAndOnlyClickedClosesWithoutAsking()
    {
        // Evidence t3-c18: app.open windows.calculator → alreadyRunning false, windowHandle 11668164; the window that
        // closes is the shared frame (ApplicationFrameHost.exe), not the launched process.
        var provenance = new LaunchProvenance(Alive(CalculatorProcess, CalculatorCreation), Watching());
        provenance.NoteLaunched(CalculatorProcess, CalculatorCreation, CalculatorFrame);
        var platform = new OneWindowPlatform(new WindowIdentity(
            (nint)CalculatorFrame, 77, 7, "ApplicationFrameHost", DateTimeOffset.UnixEpoch, FrameHost));
        var provider = new WindowsWindowControlProvider(
            platform, new Applications.WindowsInstalledApplicationOpenProvider(), provenance);

        string windowId = await ActiveWindowIdAsync(provider);

        Assert.That(provider.HoldsNoDocument(windowId), Is.True);
    }

    [Test]
    public async Task AClassicWindowOfTheLaunchedProcessClosesWithoutAsking()
    {
        var provenance = new LaunchProvenance(static _ => null, Watching());
        provenance.NoteLaunched(500, 9_000, 321);
        var provider = Provider(new WindowIdentity(
            (nint)321, 500, 9_000, "mspaint", DateTimeOffset.UnixEpoch, @"C:\Windows\System32\mspaint.exe"), provenance);

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.True);
    }

    [Test]
    public async Task AnotherWindowOfTheLaunchedProcessStillAsks()
    {
        // v3 r22 revisión (bloqueante 2, sonda: ventana 888 de un proceso anotado con la ventana 777): BAXY opened the
        // browser in the morning, the person opened another window of it (Ctrl+N) and filled a form there. Only the
        // window the opening verified is BAXY's; the person's window of the same process keeps asking.
        var provenance = new LaunchProvenance(static _ => null, Watching());
        provenance.NoteLaunched(5150, 20_000, 777);
        var provider = Provider(new WindowIdentity(
            (nint)888, 5150, 20_000, "browser", DateTimeOffset.UnixEpoch, @"C:\Apps\browser.exe"), provenance);

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.False);
    }

    [Test]
    public async Task TheVerifiedWindowOfTheLaunchedProcessClosesWithoutAsking()
    {
        // Contracaso of the one above: the very window the opening verified, same process and creation time.
        var provenance = new LaunchProvenance(static _ => null, Watching());
        provenance.NoteLaunched(5150, 20_000, 777);
        var provider = Provider(new WindowIdentity(
            (nint)777, 5150, 20_000, "browser", DateTimeOffset.UnixEpoch, @"C:\Apps\browser.exe"), provenance);

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.True);
    }

    [Test]
    public async Task TheVerifiedWindowThePersonTypedIntoStillAsks()
    {
        // v3 r22 revisión 2 (bloqueante, contraparte exacta de AnotherWindowOfTheLaunchedProcessStillAsks): BAXY opened
        // the browser in the morning (process 5150, window 777) and in the afternoon the person filled a long form in
        // that same window 777. Their own keys reached it: it holds their work and the close asks.
        long now = 1;
        var personInput = new PersonInputLedger(static () => true, static () => true, () => now);
        personInput.EnsureWatching();
        var provenance = new LaunchProvenance(static _ => null, personInput);
        provenance.NoteLaunched(5150, 20_000, 777);
        now = 900_000;
        personInput.Record(777, 777);
        var provider = Provider(new WindowIdentity(
            (nint)777, 5150, 20_000, "browser", DateTimeOffset.UnixEpoch, @"C:\Apps\browser.exe"), provenance);

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.False);
    }

    [Test]
    public void ADialogOfTheVerifiedWindowThePersonTypedIntoStillAsks()
    {
        // The person typed into a dialog the launched window owns (its root owner is the window): the window is theirs.
        long now = 1;
        var personInput = new PersonInputLedger(static () => true, static () => true, () => now);
        personInput.EnsureWatching();
        var provenance = new LaunchProvenance(static _ => null, personInput);
        provenance.NoteLaunched(5150, 20_000, 777);
        now = 900_000;
        personInput.Record(4_040, 777);

        Assert.That(provenance.LaunchedAndUnwritten(777, 5150, 20_000), Is.False);
    }

    [Test]
    public async Task TheCalculatorClosesWithoutAskingWhenThePersonOnlyTypedInBaxysWindow()
    {
        // Par del de arriba (t3-c18): the person only spoke, or typed in BAXY's own window (555); none of their input
        // reached the Calculator BAXY opened, so it still closes without asking.
        long now = 1;
        var personInput = new PersonInputLedger(static () => true, static () => true, () => now);
        personInput.EnsureWatching();
        var provenance = new LaunchProvenance(Alive(CalculatorProcess, CalculatorCreation), personInput);
        provenance.NoteLaunched(CalculatorProcess, CalculatorCreation, CalculatorFrame);
        now = CalculatorCreation + TimeSpan.TicksPerMinute;
        personInput.Record(555, 555);
        var provider = Provider(new WindowIdentity(
            (nint)CalculatorFrame, 77, 7, "ApplicationFrameHost", DateTimeOffset.UnixEpoch, FrameHost), provenance);

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.True);
    }

    [Test]
    public void TheLaunchedWindowAsksWhenThePersonsInputCannotBeRead()
    {
        // Fail-closed: the detector could not start, the watch began after the launch, the detector no longer accounts
        // for the system's last input, or the window's record was dropped to keep the bound.
        var notInstalled = new PersonInputLedger(static () => false, static () => true, static () => 1);
        notInstalled.EnsureWatching();
        var late = new PersonInputLedger(static () => true, static () => true, static () => 30_000_000);
        late.EnsureWatching();
        var lost = new PersonInputLedger(static () => true, static () => false, static () => 1);
        lost.EnsureWatching();
        long now = 1;
        var dropped = new PersonInputLedger(static () => true, static () => true, () => now);
        dropped.EnsureWatching();
        now = 30_000_000;
        for (int window = 1; window <= 513; window++)
        {
            dropped.Record(10_000 + window, 0);
        }

        Assert.Multiple(() =>
        {
            foreach (PersonInputLedger witness in new[] { notInstalled, late, lost, dropped })
            {
                var provenance = new LaunchProvenance(static _ => null, witness);
                provenance.NoteLaunched(5150, 20_000_000, 777);
                Assert.That(provenance.LaunchedAndUnwritten(777, 5150, 20_000_000), Is.False);
            }
        });
    }

    [Test]
    public void TheWindowsWitnessInstallsWithoutTouchingAnything()
    {
        // The real witness only looks: starting it clicks nothing, and a window no input reached is never touched.
        WindowsPersonInputWitness.Shared.EnsureWatching();
        long since = DateTime.UtcNow.Ticks + TimeSpan.TicksPerSecond;

        Assert.That(WindowsPersonInputWitness.Shared.ReachedSince(long.MaxValue, since),
            Is.Not.EqualTo(PersonInputVerdict.Touched));
    }

    [Test]
    public void InjectedInputWithoutBaxysMarkIsThePersonsAndTheWindowStillAsks()
    {
        // v3 r22 revisión 3 (bloqueante 1): BAXY opened the browser (window 777) and the person filled a form in it
        // through Synergy, an on-screen keyboard or a remote desktop: their keys and clicks arrive injected (no device)
        // and without BAXY's mark. They are the person's: the window is touched and «cierra el navegador» asks.
        long now = 1;
        var personInput = new PersonInputLedger(static () => true, static () => true, () => now);
        personInput.EnsureWatching();
        var provenance = new LaunchProvenance(static _ => null, personInput);
        provenance.NoteLaunched(5150, 20_000, 777);
        now = 900_000;

        nint typed = WindowsUserInputPause.PersonReachedWindow(InjectedKey(0x41, extra: 0), Header, front: 777, pointed: 0);
        nint clicked = WindowsUserInputPause.PersonReachedWindow(InjectedClick(extra: 0x1234), Header, front: 555, pointed: 777);
        personInput.Record(typed, typed);

        Assert.Multiple(() =>
        {
            Assert.That(typed, Is.EqualTo((nint)777), "an injected key without the mark reaches the window in front");
            Assert.That(clicked, Is.EqualTo((nint)777), "an injected click without the mark reaches the window under it");
            Assert.That(personInput.ReachedSince(777, 20_000), Is.EqualTo(PersonInputVerdict.Touched));
            Assert.That(provenance.LaunchedAndUnwritten(777, 5150, 20_000), Is.False);
        });
    }

    [Test]
    public void OnlyBaxysMarkedInputLeavesTheLaunchedWindowUntouched()
    {
        // Par del de arriba: BAXY's own marked key and click into window 777 are not the person's; a bare move of the
        // person reaches no content. The launched window stays untouched and closes without asking.
        long now = 1;
        var personInput = new PersonInputLedger(static () => true, static () => true, () => now);
        personInput.EnsureWatching();
        var provenance = new LaunchProvenance(static _ => null, personInput);
        provenance.NoteLaunched(5150, 20_000, 777);
        now = 900_000;

        foreach (byte[] record in new[] { InjectedKey(0x41, BaxyInputMark.Value), InjectedClick(BaxyInputMark.Value), BareMove() })
        {
            nint reached = WindowsUserInputPause.PersonReachedWindow(record, Header, front: 777, pointed: 777);
            Assert.That(reached, Is.EqualTo((nint)0));
            personInput.Record(reached, reached);
        }

        Assert.That(provenance.LaunchedAndUnwritten(777, 5150, 20_000), Is.True);
    }

    [Test]
    public void InputTheWitnessRecordsWhileTellingItIsLiveMakesTheWindowTouched()
    {
        // The detector's self-check runs when liveness is asked and may record input it had missed (VK_PACKET typing
        // of an on-screen keyboard) on the window in front: that record must count in the same read.
        long now = 1;
        PersonInputLedger? personInput = null;
        personInput = new PersonInputLedger(static () => true, () =>
        {
            personInput!.Record(777, 777);
            return true;
        }, () => now);
        personInput.EnsureWatching();
        now = 900_000;

        Assert.That(personInput.ReachedSince(777, 20_000), Is.EqualTo(PersonInputVerdict.Touched));
    }

    [Test]
    public void NothingOfBaxySitsInThePersonsInputPath()
    {
        // v3 r22 revisión 3 (bloqueante 2): the witness reads the passive Raw Input detector. No low-level keyboard or
        // mouse hook anywhere in src/ (each would make every key and move of the person wait on BAXY).
        string separator = Path.DirectorySeparatorChar.ToString();
        var offenders = Directory.EnumerateFiles(Path.Combine(RepositoryRoot(), "src"), "*.*", SearchOption.AllDirectories)
            .Where(static path => path.EndsWith(".cs", StringComparison.Ordinal) || path.EndsWith(".ps1", StringComparison.Ordinal))
            .Where(path => !path.Contains(separator + "bin" + separator, StringComparison.Ordinal)
                && !path.Contains(separator + "obj" + separator, StringComparison.Ordinal))
            .Where(static path => File.ReadAllText(path).Contains("SetWindowsHookEx", StringComparison.Ordinal))
            .ToList();

        Assert.That(offenders, Is.Empty);
    }

    [Test]
    public void AWindowRecordDroppedBeforeTheLaunchDoesNotMakeItUnknown()
    {
        // Contracaso of the bound: records dropped from before the launch say nothing of the launched window.
        long now = 1;
        var witness = new PersonInputLedger(static () => true, static () => true, () => now);
        witness.EnsureWatching();
        now = 10;
        for (int window = 1; window <= 513; window++)
        {
            witness.Record(10_000 + window, 0);
        }

        var provenance = new LaunchProvenance(static _ => null, witness);
        provenance.NoteLaunched(5150, 20_000_000, 777);

        Assert.That(provenance.LaunchedAndUnwritten(777, 5150, 20_000_000), Is.True);
    }

    [Test]
    public async Task AnAccountBackedApplicationCapturingTheMicrophoneStillAsks()
    {
        // v3 r22 revisión (bloqueante 3, «cierra Teams» en plena reunión): an application in a call captures the
        // microphone; closing its window may leave the call, which opening it again does not bring back.
        var platform = new OneWindowPlatform(Discord()) { CapturingMicrophone = true };
        var provider = new WindowsWindowControlProvider(
            platform, new Applications.WindowsInstalledApplicationOpenProvider(), new LaunchProvenance());

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.False);
    }

    [Test]
    public async Task AWindowBaxyLaunchedThatCapturesTheMicrophoneStillAsks()
    {
        var provenance = new LaunchProvenance(static _ => null, Watching());
        provenance.NoteLaunched(500, 9_000, 321);
        var platform = new OneWindowPlatform(new WindowIdentity(
            (nint)321, 500, 9_000, "recorder", DateTimeOffset.UnixEpoch, @"C:\Apps\recorder.exe"))
        {
            CapturingMicrophone = true,
        };
        var provider = new WindowsWindowControlProvider(
            platform, new Applications.WindowsInstalledApplicationOpenProvider(), provenance);

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.False);
    }

    [Test]
    public async Task AnAccountBackedApplicationNotCapturingTheMicrophoneClosesWithoutAsking()
    {
        // Contracaso: the same application with no call in progress.
        var platform = new OneWindowPlatform(Discord()) { CapturingMicrophone = false };
        var provider = new WindowsWindowControlProvider(
            platform, new Applications.WindowsInstalledApplicationOpenProvider(), new LaunchProvenance());

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.True);
    }

    [Test]
    public async Task ACalculatorThePersonAlreadyHadOpenStillAsks()
    {
        // Contracaso: app.open found it running (alreadyRunning=true), so nothing was noted.
        var provenance = new LaunchProvenance(Alive(CalculatorProcess, CalculatorCreation), Watching());
        var provider = Provider(new WindowIdentity(
            (nint)CalculatorFrame, 77, 7, "ApplicationFrameHost", DateTimeOffset.UnixEpoch, FrameHost), provenance);

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.False);
    }

    [Test]
    public async Task AWindowBaxyOpenedAndWroteIntoStillAsks()
    {
        // Contracaso: Notepad (or Word, or Paint) opened by BAXY and then typed into keeps asking.
        var provenance = new LaunchProvenance(static _ => null, Watching());
        provenance.NoteLaunched(600, 12_000, 654);
        provenance.NoteWritten();
        var provider = Provider(new WindowIdentity(
            (nint)654, 600, 12_000, "Notepad", DateTimeOffset.UnixEpoch, @"C:\Windows\notepad.exe"), provenance);

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.False);
    }

    [Test]
    public async Task AnApplicationLaunchedAfterTheWritingStaysUnwritten()
    {
        var provenance = new LaunchProvenance(static _ => null, Watching());
        provenance.NoteLaunched(600, 12_000, 654);
        provenance.NoteWritten();
        provenance.NoteLaunched(700, 13_000, 765);
        var provider = Provider(new WindowIdentity(
            (nint)765, 700, 13_000, "mspaint", DateTimeOffset.UnixEpoch, @"C:\Windows\System32\mspaint.exe"), provenance);

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.True);
    }

    [Test]
    public async Task ARecycledProcessIdDoesNotInheritTheProvenance()
    {
        // Contracaso: same id, another creation time (the launched process ended and the id was given again).
        var provenance = new LaunchProvenance(static _ => null, Watching());
        provenance.NoteLaunched(500, 9_000, 321);
        var provider = Provider(new WindowIdentity(
            (nint)321, 500, 9_001, "WINWORD", DateTimeOffset.UnixEpoch, @"C:\Office\WINWORD.EXE"), provenance);

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.False);
    }

    [Test]
    public async Task AFrameWhoseLaunchedProcessIsGoneDoesNotInheritTheProvenance()
    {
        // Contracaso: the frame handle matches, but the launched process is no longer the one launched.
        var provenance = new LaunchProvenance(Alive(CalculatorProcess, CalculatorCreation + 1), Watching());
        provenance.NoteLaunched(CalculatorProcess, CalculatorCreation, CalculatorFrame);
        var provider = Provider(new WindowIdentity(
            (nint)CalculatorFrame, 77, 7, "ApplicationFrameHost", DateTimeOffset.UnixEpoch, FrameHost), provenance);

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.False);
    }

    [Test]
    public async Task FileExplorerNeverClosesWithoutAskingEvenWhenBaxyLaunchedIt()
    {
        var provenance = new LaunchProvenance(static _ => null, Watching());
        provenance.NoteLaunched(800, 14_000, 888);
        var provider = Provider(new WindowIdentity(
            (nint)888, 800, 14_000, "explorer", DateTimeOffset.UnixEpoch, @"C:\Windows\explorer.exe"), provenance);

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.False);
    }

    [Test]
    public async Task AnAccountBackedApplicationClosesWithoutAskingEvenAfterBaxyWroteIntoIt()
    {
        // Evidence t4-c03: Discord was opened (t1) and a message typed to Ron92 (t2) before «ya cierra discord» (t4).
        var provenance = new LaunchProvenance(static _ => null, Watching());
        provenance.NoteLaunched(900, 15_000, 999);
        provenance.NoteWritten();
        var provider = Provider(new WindowIdentity(
            (nint)999, 900, 15_000, "Discord", DateTimeOffset.UnixEpoch,
            @"C:\Users\person\AppData\Local\Discord\app-1.0.9200\Discord.exe"), provenance);

        Assert.That(provider.HoldsNoDocument(await ActiveWindowIdAsync(provider)), Is.True);
    }

    [Test]
    public async Task AnApplicationAnsweringTheCloseWithItsOwnDialogIsReportedAndLeftAsking()
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

    private static WindowIdentity Discord() => new(
        (nint)999, 900, 15_000, "Discord", DateTimeOffset.UnixEpoch,
        @"C:\Users\person\AppData\Local\Discord\app-1.0.9200\Discord.exe");

    // The person's input watched since long before the case and none of it reached the launched window.
    private static PersonInputLedger Watching()
    {
        var ledger = new PersonInputLedger(static () => true, static () => true, static () => 1);
        ledger.EnsureWatching();
        return ledger;
    }

    private static readonly int Header = 8 + 2 * IntPtr.Size;

    // A keyboard Raw Input record with no device (injected) and the given extra information.
    private static byte[] InjectedKey(ushort virtualKey, uint extra)
    {
        var record = new byte[Header + 24];
        BinaryPrimitives.WriteUInt32LittleEndian(record, 1);
        BinaryPrimitives.WriteUInt16LittleEndian(record.AsSpan(Header + 6), virtualKey);
        BinaryPrimitives.WriteUInt32LittleEndian(record.AsSpan(Header + 12), extra);
        return record;
    }

    // A mouse Raw Input record with no device (injected), the left button going down and the given extra information.
    private static byte[] InjectedClick(uint extra)
    {
        var record = new byte[Header + 24];
        BinaryPrimitives.WriteUInt32LittleEndian(record, 0);
        BinaryPrimitives.WriteUInt16LittleEndian(record.AsSpan(Header + 4), 0x0001);
        BinaryPrimitives.WriteUInt32LittleEndian(record.AsSpan(Header + 20), extra);
        return record;
    }

    private static byte[] BareMove() => new byte[Header + 24];

    private static string RepositoryRoot()
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Baxy.slnx")))
            directory = directory.Parent;
        return directory?.FullName ?? throw new DirectoryNotFoundException("Baxy.slnx was not found.");
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
        public bool CapturingMicrophone { get; init; }
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

        public bool CapturesMicrophone(WindowIdentity identity) => CapturingMicrophone;

        public IReadOnlyList<nint> OwnedDialogs(WindowIdentity identity) =>
            _asking ? [(nint)4_040] : [];

        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken) => ValueTask.CompletedTask;

        private WindowSnapshot Snapshot() =>
            new(window, "normal", true, new WindowBounds(0, 0, 800, 600), "Ventana");
    }
}
