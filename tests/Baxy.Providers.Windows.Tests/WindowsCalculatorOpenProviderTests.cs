using Baxy.Providers.Windows.Applications;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class WindowsCalculatorOpenProviderTests
{
    [Test]
    public async Task LaunchCompletesOnlyAfterIndependentVisibleForegroundInventory()
    {
        var platform = new FakePlatform();
        var provider = new WindowsCalculatorOpenProvider(platform);
        var request = new ApplicationOpenRequest(
            ApplicationIds.Calculator, Guid.NewGuid().ToString("D"), Foreground: true);

        ApplicationOpenResult result = await provider.OpenAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.True);
            Assert.That(result.Verified, Is.True);
            Assert.That(result.DisplayName, Is.EqualTo("Calculator"), "auditoría D9: the title read, not a literal");
            Assert.That(result.ProcessId, Is.EqualTo(52));
            Assert.That(result.WindowHandle, Is.EqualTo(91));
            Assert.That(platform.LaunchCount, Is.EqualTo(1));
            Assert.That(platform.FocusCount, Is.EqualTo(1));
            Assert.That(platform.InventoryCount, Is.GreaterThanOrEqualTo(3));
            Assert.That(platform.DelayCount, Is.Zero);
        });
    }

    // 2026-10-15: Windows keeps a prelaunched CalculatorApp suspended and shows that same process when it is opened; the
    // window it shows is the proof, not a new process.
    [Test]
    public async Task APrelaunchedProcessThatBecomesVisibleIsTheVerifiedOpening()
    {
        var platform = new FakePlatform { Prelaunched = true };
        var provider = new WindowsCalculatorOpenProvider(platform);
        var request = new ApplicationOpenRequest(
            ApplicationIds.Calculator, Guid.NewGuid().ToString("D"), Foreground: true);

        ApplicationOpenResult result = await provider.OpenAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.True);
            Assert.That(result.ProcessId, Is.EqualTo(52));
            Assert.That(platform.LaunchCount, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task ForegroundVerificationWaitsOnlyWhenTheImmediatePostreadHasNotConverged()
    {
        var platform = new FakePlatform { FocusRequiresDelay = true };
        var provider = new WindowsCalculatorOpenProvider(platform);
        var request = new ApplicationOpenRequest(
            ApplicationIds.Calculator, Guid.NewGuid().ToString("D"), Foreground: true);

        ApplicationOpenResult result = await provider.OpenAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.True);
            Assert.That(result.Verified, Is.True);
            Assert.That(platform.FocusCount, Is.EqualTo(1));
            Assert.That(platform.DelayCount, Is.EqualTo(1));
        });
    }

    // v3 point 0 (arreglo 4): without «foreground» nothing asks for the front; the packaged Calculator that Windows
    // activates by itself hands the front back to the person's window and the receipt counts it.
    [TestCase(false, false)]
    [TestCase(true, true)]
    public async Task AnOpeningNotAskedInFrontNeverAsksForItAndHandsBackWhatWindowsActivated(
        bool windowsActivates,
        bool handedBack)
    {
        var platform = new FakePlatform { PersonFront = 0x500, WindowsActivates = windowsActivates };
        var provider = new WindowsCalculatorOpenProvider(platform);
        var request = new ApplicationOpenRequest(ApplicationIds.Calculator, Guid.NewGuid().ToString("D"));

        ApplicationOpenResult result = await provider.OpenAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.True);
            Assert.That(platform.FocusCount, Is.Zero);
            Assert.That(result.WindowsActivation, Is.EqualTo(handedBack));
            Assert.That(result.FrontRestored, Is.EqualTo(handedBack));
            Assert.That(platform.HandedBack, Is.EqualTo(handedBack ? [(0x500L, 91L)] : Array.Empty<(long, long)>()));
        });
    }

    // cu-v3-foco-segunda: a hand-back Windows refused is said as such (the Calculator kept the front).
    [Test]
    public async Task AHandBackWindowsRefusedIsNotCountedAsRestored()
    {
        var platform = new FakePlatform { PersonFront = 0x500, WindowsActivates = true, HandBackHolds = false };
        var provider = new WindowsCalculatorOpenProvider(platform);
        var request = new ApplicationOpenRequest(ApplicationIds.Calculator, Guid.NewGuid().ToString("D"));

        ApplicationOpenResult result = await provider.OpenAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.True);
            Assert.That(result.WindowsActivation, Is.True);
            Assert.That(result.FrontRestored, Is.False);
            Assert.That(platform.HandedBack, Has.Count.EqualTo(1));
        });
    }

    // Review of r20b palanca 4, finding 1: the Calculator follows the rule of every path of app.open. Asked in front
    // while the person types in their own window, it is shown above it without the front, and said so only when read
    // back; from BAXY's chat (nobody working) it takes the front as before.
    [TestCase(true, true)]
    [TestCase(true, false)]
    [TestCase(false, true)]
    public async Task AskedInFrontWhileThePersonWorksElsewhereItIsShownWithoutTheirKeyboard(bool working, bool readBack)
    {
        var platform = new FakePlatform { PersonFront = 0x500, WorkingFront = working ? 0x500 : 0, ShowReadBack = readBack };
        var provider = new WindowsCalculatorOpenProvider(platform);
        var request = new ApplicationOpenRequest(ApplicationIds.Calculator, Guid.NewGuid().ToString("D"), Foreground: true);

        ApplicationOpenResult result = await provider.OpenAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.True);
            Assert.That(platform.FocusCount, Is.EqualTo(working ? 0 : 1));
            Assert.That(result.ShownWithoutFocus, Is.EqualTo(working && readBack));
            Assert.That(platform.RaisedAbove, Is.EqualTo(working ? [(91L, 0x500L)] : Array.Empty<(long, long)>()));
        });
    }

    // Finding 2: the packaged Calculator Windows activated at its start, asked in front while the person works in their
    // window: the front goes back to them.
    [Test]
    public async Task AFrontWindowsGaveItGoesBackToThePersonWorking()
    {
        var platform = new FakePlatform { PersonFront = 0x500, WorkingFront = 0x500, WindowsActivates = true };
        var provider = new WindowsCalculatorOpenProvider(platform);
        var request = new ApplicationOpenRequest(ApplicationIds.Calculator, Guid.NewGuid().ToString("D"), Foreground: true);

        ApplicationOpenResult result = await provider.OpenAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(platform.FocusCount, Is.Zero);
            Assert.That(result.WindowsActivation, Is.True);
            Assert.That(platform.HandedBack, Is.EqualTo(new[] { (0x500L, 91L) }));
            Assert.That(result.ShownWithoutFocus, Is.True);
        });
    }

    // Review 2 of r20b palanca 4: the Calculator Windows activated at its start, asked in front while the person works in
    // their window, and a hand-back Windows refused: it is above their window and holds their keyboard, so it is never
    // said shown without the focus. Counter-case: the hand-back holds, and it is.
    [TestCase(false)]
    [TestCase(true)]
    public async Task ARefusedHandBackIsNeverSaidShownWithoutTheFocus(bool holds)
    {
        var platform = new FakePlatform
        {
            PersonFront = 0x500,
            WorkingFront = 0x500,
            WindowsActivates = true,
            HandBackHolds = holds,
        };
        var provider = new WindowsCalculatorOpenProvider(platform);
        var request = new ApplicationOpenRequest(ApplicationIds.Calculator, Guid.NewGuid().ToString("D"), Foreground: true);

        ApplicationOpenResult result = await provider.OpenAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.True);
            Assert.That(platform.FocusCount, Is.Zero);
            Assert.That(result.WindowsActivation, Is.True);
            Assert.That(result.FrontRestored, Is.EqualTo(holds));
            Assert.That(result.ShownWithoutFocus, Is.EqualTo(holds));
        });
    }

    // The front read after the showing: the person's keyboard is left out of the opened application only when a window
    // is known in front and it is none of the opened application's.
    [TestCase(0x500L, true)]
    [TestCase(91L, false)]
    [TestCase(92L, false)]
    [TestCase(0L, false)]
    public void TheKeyboardIsLeftOutOnlyWhenTheFrontIsNotTheOpenedApplication(long front, bool leftOut) =>
        Assert.That(OpeningFront.KeyboardLeftOut(front, 91, window => window is 91 or 92), Is.EqualTo(leftOut));

    private sealed class FakePlatform : ICalculatorPlatform
    {
        public long PersonFront { get; init; }
        public long WorkingFront { get; init; }
        public bool ShowReadBack { get; init; } = true;
        public List<(long, long)> RaisedAbove { get; } = [];
        public long PersonWorkingIn(long window) => window != 0 && window == WorkingFront ? window : 0;
        public bool ShowAboveWithoutActivation(long window, long personWindow)
        {
            RaisedAbove.Add((window, personWindow));
            return ShowReadBack;
        }
        public bool WindowsActivates { get; init; }
        public List<(long, long)> HandedBack { get; } = [];
        // The Calculator holds the front once Windows activated it or it was asked for, until a hand-back that holds.
        public long ForegroundWindow() => _focused && !_handedBack ? 91 : PersonFront;
        public bool HandBackHolds { get; init; } = true;
        private bool _handedBack;
        public bool ReturnForeground(long previous, long opened)
        {
            HandedBack.Add((previous, opened));
            _handedBack = HandBackHolds;
            return HandBackHolds;
        }
        private bool _launched;
        private bool _focused;
        public bool FocusRequiresDelay { get; init; }
        public bool Prelaunched { get; init; }
        public int LaunchCount { get; private set; }
        public int FocusCount { get; private set; }
        public int InventoryCount { get; private set; }
        public int DelayCount { get; private set; }
        public IReadOnlyList<CalculatorSnapshot> Inventory()
        {
            InventoryCount++;
            return _launched
                ? [new CalculatorSnapshot(52, 638_880_000_000_000_000, 91, true, _focused)]
                : Prelaunched ? [new CalculatorSnapshot(52, 638_880_000_000_000_000, 0, false, false)] : [];
        }
        public bool Launch() { LaunchCount++; _launched = true; _focused = WindowsActivates; return true; }
        public string WindowTitle(long windowHandle) => windowHandle == 91 ? "Calculator" : string.Empty;
        public void RequestForeground(long windowHandle)
        {
            Assert.That(windowHandle, Is.EqualTo(91));
            FocusCount++;
            if (!FocusRequiresDelay) _focused = true;
        }
        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            DelayCount++;
            _focused = true;
            return ValueTask.CompletedTask;
        }
    }
}
