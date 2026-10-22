using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class WindowsWindowControlProviderTests
{
    [Test]
    public async Task ForegroundResolveReturnsOnlyVerifiedActiveWindow()
    {
        var platform = new FakePlatform { Foreground = true };
        var provider = new WindowsWindowControlProvider(platform);

        WindowResolveResult result = await provider.ResolveForegroundAsync(
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.True);
            Assert.That(result.Verified, Is.True);
            Assert.That(result.Windows, Has.Count.EqualTo(1));
            Assert.That(result.Windows[0].ProcessName, Is.EqualTo("notepad"));
            Assert.That(result.Windows[0].Foreground, Is.True);
            Assert.That(result.Windows[0].WindowId, Does.Match("^win_[0-9a-f]{32}$"));
        });
    }

    [Test]
    public async Task ResolveIssuesOpaqueIdAndActionConsumesThenRefreshesIt()
    {
        var platform = new FakePlatform();
        var provider = new WindowsWindowControlProvider(platform);

        WindowResolveResult resolved = await provider.ResolveAsync(
            "notepad.exe", 10, CancellationToken.None);
        string firstId = resolved.Windows.Single().WindowId;
        WindowActionResult focused = await provider.ExecuteAsync(
            firstId, WindowControlAction.Focus, CancellationToken.None);
        WindowActionResult replayed = await provider.ExecuteAsync(
            firstId, WindowControlAction.Focus, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(resolved.Succeeded, Is.True);
            Assert.That(resolved.Verified, Is.True);
            Assert.That(firstId, Does.Match("^win_[0-9a-f]{32}$"));
            Assert.That(focused.Succeeded, Is.True);
            Assert.That(focused.Verified, Is.True);
            Assert.That(focused.Window!.Foreground, Is.True);
            Assert.That(focused.Window.WindowId, Is.Not.EqualTo(firstId));
            Assert.That(replayed.Succeeded, Is.False);
            Assert.That(replayed.ErrorCode,
                Is.EqualTo(WindowControlErrorCodes.InvalidOrExpiredWindowId));
        });
    }

    [Test]
    public async Task ChangedIdentityFailsClosedBeforeDispatch()
    {
        var platform = new FakePlatform();
        var provider = new WindowsWindowControlProvider(platform);
        WindowResolveResult resolved = await provider.ResolveAsync(
            "notepad", 10, CancellationToken.None);
        platform.IdentityChanged = true;

        WindowActionResult result = await provider.ExecuteAsync(
            resolved.Windows.Single().WindowId,
            WindowControlAction.Minimize,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.False);
            Assert.That(result.ErrorCode,
                Is.EqualTo(WindowControlErrorCodes.WindowIdentityChanged));
            Assert.That(platform.ExecuteCalls, Is.Zero);
        });
    }

    [Test]
    public async Task CloseConsumesHandleAndSucceedsOnlyAfterIndependentAbsenceProbe()
    {
        var platform = new FakePlatform();
        var provider = new WindowsWindowControlProvider(platform);
        WindowResolveResult resolved = await provider.ResolveAsync("notepad", 10, CancellationToken.None);

        WindowCloseResult closed = await provider.CloseAsync(
            resolved.Windows.Single().WindowId, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(closed.Succeeded, Is.True);
            Assert.That(closed.Verified, Is.True);
            Assert.That(closed.ProcessId, Is.EqualTo(42));
            Assert.That(platform.CloseCalls, Is.EqualTo(1));
            Assert.That(platform.SystemCloseCalls, Is.Zero);
        });
    }

    // Auditoría D7: a window gone before BAXY's close reached it is «alreadyGone», and one that went invisible instead
    // of closing (an application that hides in the notification area) is «hidden»: neither is «closed».
    // FT/proveedores goal (review of receipts): a browser hides its window first and destroys it a moment later: closed.
    [Test]
    public async Task AWindowHiddenAndThenDestroyedIsClosed()
    {
        var platform = new FakePlatform { CloseHides = true, HiddenReads = 3 };
        var provider = new WindowsWindowControlProvider(platform);
        WindowResolveResult resolved = await provider.ResolveAsync("notepad", 10, CancellationToken.None);

        WindowCloseResult result = await provider.CloseAsync(resolved.Windows.Single().WindowId, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.True);
            Assert.That(result.Outcome, Is.EqualTo(WindowCloseOutcomes.Closed));
        });
    }

    [TestCase(false, WindowCloseOutcomes.Closed)]
    [TestCase(true, WindowCloseOutcomes.Hidden)]
    public async Task ACloseSaysWhetherTheWindowClosedOrOnlyHid(bool hides, string outcome)
    {
        var platform = new FakePlatform { CloseHides = hides };
        var provider = new WindowsWindowControlProvider(platform);
        WindowResolveResult resolved = await provider.ResolveAsync("notepad", 10, CancellationToken.None);

        WindowCloseResult result = await provider.CloseAsync(resolved.Windows.Single().WindowId, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.True);
            Assert.That(result.Outcome, Is.EqualTo(outcome));
        });
    }

    [Test]
    public async Task AWindowGoneBeforeTheCloseIsAlreadyGoneNeverClosedByBaxy()
    {
        var platform = new FakePlatform { GoneAtClose = true };
        var provider = new WindowsWindowControlProvider(platform);
        WindowResolveResult resolved = await provider.ResolveAsync("notepad", 10, CancellationToken.None);

        WindowCloseResult result = await provider.CloseAsync(resolved.Windows.Single().WindowId, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.True);
            Assert.That(result.Outcome, Is.EqualTo(WindowCloseOutcomes.AlreadyGone));
        });
    }

    // FT/proveedores goal (review of receipts): a frame already gone when its close comes (it ended with the first frame
    // of the same application) is already gone, never a failure and never closed by BAXY; no close is sent to it.
    [Test]
    public async Task AWindowGoneBeforeItsCloseIsReadIsAlreadyGone()
    {
        var platform = new FakePlatform();
        var provider = new WindowsWindowControlProvider(platform);
        WindowResolveResult resolved = await provider.ResolveAsync("notepad", 10, CancellationToken.None);
        platform.IdentityChanged = true;

        WindowCloseResult result = await provider.CloseAsync(resolved.Windows.Single().WindowId, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.True, result.ErrorCode);
            Assert.That(result.Verified, Is.True);
            Assert.That(result.Outcome, Is.EqualTo(WindowCloseOutcomes.AlreadyGone));
            Assert.That(platform.CloseCalls, Is.Zero);
        });
    }

    [TestCase(true)]
    [TestCase(false)]
    public async Task CloseFallsBackToVerifiedSystemCommandForHostedOrUiAccessWindows(
        bool primaryAccepted)
    {
        var platform = new FakePlatform
        {
            PrimaryCloseAccepted = primaryAccepted,
            PrimaryCloseCloses = false,
            SystemCloseAccepted = true,
            SystemCloseCloses = true,
        };
        var provider = new WindowsWindowControlProvider(platform);
        WindowResolveResult resolved = await provider.ResolveAsync(
            "notepad", 10, CancellationToken.None);

        WindowCloseResult result = await provider.CloseAsync(
            resolved.Windows.Single().WindowId, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.True);
            Assert.That(result.Verified, Is.True);
            Assert.That(platform.CloseCalls, Is.EqualTo(1));
            Assert.That(platform.SystemCloseCalls, Is.EqualTo(1));
            Assert.That(platform.Closed, Is.True);
        });
    }

    [TestCase(WindowControlAction.Minimize, "minimized", false)]
    [TestCase(WindowControlAction.Maximize, "maximized", false)]
    [TestCase(WindowControlAction.Restore, "normal", false)]
    public async Task WindowStateActionsWaitForObservableConvergence(
        WindowControlAction action,
        string expectedState,
        bool expectedForeground)
    {
        var platform = new FakePlatform
        {
            ActionConvergenceDelayCount = 3,
            Foreground = action == WindowControlAction.Minimize,
        };
        if (action == WindowControlAction.Restore)
        {
            platform.SetInitialState("maximized");
        }
        var provider = new WindowsWindowControlProvider(platform);
        WindowResolveResult resolved = await provider.ResolveAsync(
            "notepad", 10, CancellationToken.None);

        WindowActionResult result = await provider.ExecuteAsync(
            resolved.Windows.Single().WindowId, action, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.True);
            Assert.That(result.Verified, Is.True);
            Assert.That(result.Window?.State, Is.EqualTo(expectedState));
            Assert.That(result.Window?.Foreground, Is.EqualTo(expectedForeground));
            Assert.That(platform.DelayCalls, Is.EqualTo(3));
            Assert.That(platform.ExecuteCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task MoveAndResizePreserveUnchangedDimensionsAndVerifyExactBounds()
    {
        var platform = new FakePlatform();
        var provider = new WindowsWindowControlProvider(platform);
        WindowResolveResult first = await provider.ResolveAsync("notepad", 10, CancellationToken.None);
        WindowActionResult moved = await provider.SetBoundsAsync(
            first.Windows.Single().WindowId, 20, 30, null, null, CancellationToken.None);
        WindowActionResult resized = await provider.SetBoundsAsync(
            moved.Window!.WindowId, null, null, 800, 600, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(moved.Succeeded, Is.True);
            Assert.That((moved.Window.X, moved.Window.Y), Is.EqualTo((20, 30)));
            Assert.That((moved.Window.Width, moved.Window.Height), Is.EqualTo((640, 480)));
            Assert.That((resized.Window!.X, resized.Window.Y), Is.EqualTo((20, 30)));
            Assert.That((resized.Window.Width, resized.Window.Height), Is.EqualTo((800, 600)));
            Assert.That(platform.SetBoundsCalls, Is.EqualTo(2));
        });
    }

    // Round A: a close Windows took with the window still there came back as a clean verification failure, as if the
    // application never got it. It says the close may still act; a close Windows refused changed nothing.
    [TestCase(true, WindowControlErrorCodes.VerificationFailed, true)]
    [TestCase(false, WindowControlErrorCodes.ActionFailed, false)]
    public async Task ACloseWindowsTookWithTheWindowStillThereMayStillAct(
        bool accepted, string errorCode, bool effectMayHaveOccurred)
    {
        var platform = new FakePlatform
        {
            PrimaryCloseAccepted = accepted,
            PrimaryCloseCloses = false,
            SystemCloseAccepted = false,
        };
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        OperationOutcome outcome = await Run(new AppCloseHandler(provider), new { windowId });

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(errorCode));
            Assert.That(outcome.EffectMayHaveOccurred, Is.EqualTo(effectMayHaveOccurred));
        });
    }

    // A state that never converges after the command was sent, and a focus refused after restoring a minimized window,
    // may have changed the window; a maximize Windows refused did not.
    [TestCase(WindowControlAction.Minimize, "normal", true, WindowControlErrorCodes.VerificationFailed, true)]
    [TestCase(WindowControlAction.Focus, "minimized", false, WindowControlErrorCodes.ActionFailed, true)]
    [TestCase(WindowControlAction.Maximize, "normal", false, WindowControlErrorCodes.ActionFailed, false)]
    public async Task AWindowActionSaysWhetherItMayHaveChangedTheWindow(
        WindowControlAction action, string initialState, bool accepted, string errorCode, bool effectMayHaveOccurred)
    {
        var platform = new FakePlatform { ExecuteAccepted = accepted, ActionConvergenceDelayCount = accepted ? 1000 : 0 };
        platform.SetInitialState(initialState);
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        OperationOutcome outcome = await Run(
            new WindowActionHandler("window." + action.ToString().ToLowerInvariant(), action, provider), new { windowId });

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(errorCode));
            Assert.That(outcome.EffectMayHaveOccurred, Is.EqualTo(effectMayHaveOccurred));
        });
    }

    // Renew al máximo (8.3): a minimize that never converged, and a focus refused after restoring a minimized window,
    // failed with nothing of the window; the state one read found after is said, with whether it is the one asked.
    [TestCase(WindowControlAction.Minimize, "normal", true, "normal")]
    [TestCase(WindowControlAction.Focus, "minimized", false, "minimized")]
    public async Task AnAmbiguousWindowActionSaysTheStateReadAfter(
        WindowControlAction action, string initialState, bool accepted, string stateAfter)
    {
        var platform = new FakePlatform { ExecuteAccepted = accepted, ActionConvergenceDelayCount = accepted ? 1000 : 0 };
        platform.SetInitialState(initialState);
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        WindowActionResult result = await provider.ExecuteAsync(windowId, action, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.False);
            Assert.That(result.EffectMayHaveOccurred, Is.True);
            Assert.That(result.StateAfter?.Present, Is.True);
            Assert.That(result.StateAfter?.State, Is.EqualTo(stateAfter));
            Assert.That(result.StateAfter?.Foreground, Is.False);
            Assert.That(result.StateAfter?.RequestedStateReached, Is.False);
        });
    }

    // Renew al máximo (8.3): a move Windows took and the window did not: the bounds read after are said.
    [Test]
    public async Task AMoveTheWindowDidNotTakeSaysTheBoundsReadAfter()
    {
        var platform = new FakePlatform { SetBoundsIgnored = true };
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        WindowActionResult result = await provider.SetBoundsAsync(windowId, 20, 30, null, null, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.ErrorCode, Is.EqualTo(WindowControlErrorCodes.VerificationFailed));
            Assert.That(result.EffectMayHaveOccurred, Is.True);
            Assert.That((result.StateAfter?.X, result.StateAfter?.Y), Is.EqualTo(((int?)0, (int?)0)));
            Assert.That(result.StateAfter?.RequestedStateReached, Is.False);
        });
    }

    // Renew al máximo (8.3): a close Windows took with the window still there says it is there, read once more; a
    // window gone by that read is said gone, the failure kept.
    [TestCase(false, true, false)]
    [TestCase(true, false, true)]
    public async Task ACloseWindowsTookSaysWhetherTheWindowIsStillThere(bool goneAtLastRead, bool present, bool reached)
    {
        static FakePlatform Stubborn() => new()
        {
            PrimaryCloseAccepted = true,
            PrimaryCloseCloses = false,
            SystemCloseAccepted = true,
            SystemCloseCloses = false,
        };
        // How many reads a close of that window makes, counted on a twin: the window is gone at the last of them.
        FakePlatform twin = Stubborn();
        var twinProvider = new WindowsWindowControlProvider(twin);
        string twinId = (await twinProvider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;
        int readsBefore = twin.ObserveCalls;
        _ = await twinProvider.CloseAsync(twinId, CancellationToken.None);
        int closeReads = twin.ObserveCalls - readsBefore;

        FakePlatform platform = Stubborn();
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;
        platform.GoneAfterObservations = goneAtLastRead ? platform.ObserveCalls + closeReads : -1;

        WindowCloseResult result = await provider.CloseAsync(windowId, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.ErrorCode, Is.EqualTo(WindowControlErrorCodes.VerificationFailed));
            Assert.That(result.EffectMayHaveOccurred, Is.True);
            Assert.That(result.StateAfter?.Present, Is.EqualTo(present));
            Assert.That(result.StateAfter?.RequestedStateReached, Is.EqualTo(reached));
        });
    }

    // Renew al máximo (8.3, Core): the handlers dropped the state read after an ambiguous failure, so the mind
    // only heard «could not». The failure keeps its code and uncertainty and carries stateAfter; a maximize
    // Windows refused changed nothing and says nothing more.
    [TestCase(WindowControlAction.Minimize, true, "normal")]
    [TestCase(WindowControlAction.Maximize, false, null)]
    public async Task AWindowActionFailureCarriesTheStateReadAfter(
        WindowControlAction action, bool accepted, string? stateAfter)
    {
        var platform = new FakePlatform
        {
            ExecuteAccepted = accepted,
            ActionConvergenceDelayCount = accepted ? 1000 : 0,
        };
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None))
            .Windows.Single().WindowId;

        string operation = "window." + action.ToString().ToLowerInvariant();
        OperationOutcome outcome = await Run(new WindowActionHandler(operation, action, provider), new { windowId });

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.EffectMayHaveOccurred, Is.EqualTo(accepted));
            if (stateAfter is null)
            {
                Assert.That(outcome.Result, Is.Null);
                return;
            }

            JsonElement state = outcome.Result!.Value.GetProperty("stateAfter");
            Assert.That(state.GetProperty("present").GetBoolean(), Is.True);
            Assert.That(state.GetProperty("hidden").GetBoolean(), Is.False);
            Assert.That(state.GetProperty("state").GetString(), Is.EqualTo(stateAfter));
            Assert.That(state.GetProperty("foreground").GetBoolean(), Is.False);
            Assert.That(state.GetProperty("width").GetInt32(), Is.EqualTo(640));
            Assert.That(state.GetProperty("requestedStateReached").GetBoolean(), Is.False);
            Assert.That(state.GetProperty("authority").GetString(), Is.EqualTo("windows_window_identity_postread"));
        });
    }

    // Renew al máximo (8.3, Core): a move Windows took and the window did not keeps the bounds read after.
    [Test]
    public async Task AMoveFailureCarriesTheBoundsReadAfter()
    {
        var platform = new FakePlatform { SetBoundsIgnored = true };
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None))
            .Windows.Single().WindowId;

        OperationOutcome outcome = await Run(
            new WindowBoundsHandler("window.move", provider), new { windowId, x = 20, y = 30 });

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(WindowControlErrorCodes.VerificationFailed));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            JsonElement state = outcome.Result!.Value.GetProperty("stateAfter");
            Assert.That((state.GetProperty("x").GetInt32(), state.GetProperty("y").GetInt32()), Is.EqualTo((0, 0)));
            Assert.That(state.GetProperty("requestedStateReached").GetBoolean(), Is.False);
        });
    }

    // Renew al máximo (8.3, Core): a close Windows took with the window still there says it is still there.
    [Test]
    public async Task ACloseFailureCarriesWhetherTheWindowIsStillThere()
    {
        var platform = new FakePlatform
        {
            PrimaryCloseAccepted = true,
            PrimaryCloseCloses = false,
            SystemCloseAccepted = true,
            SystemCloseCloses = false,
        };
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None))
            .Windows.Single().WindowId;

        OperationOutcome outcome = await Run(new AppCloseHandler(provider), new { windowId });

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(WindowControlErrorCodes.VerificationFailed));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            JsonElement state = outcome.Result!.Value.GetProperty("stateAfter");
            Assert.That(state.GetProperty("present").GetBoolean(), Is.True);
            Assert.That(state.GetProperty("requestedStateReached").GetBoolean(), Is.False);
        });
    }

    // A maximized window is restored before it is placed; a placement Windows then refused leaves it restored.
    [TestCase("maximized", true)]
    [TestCase("normal", false)]
    public async Task ASnapRefusedAfterTheRestoreSaysTheWindowMayHaveChanged(string initialState, bool effectMayHaveOccurred)
    {
        var platform = new FakePlatform { SetBoundsAccepted = false, WorkAreaBounds = new WindowBounds(0, 0, 1536, 816) };
        platform.SetInitialState(initialState);
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        OperationOutcome outcome = await Run(new WindowSnapHandler(provider), new { windowId, side = "left" });

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo(WindowControlErrorCodes.ActionFailed));
            Assert.That(outcome.EffectMayHaveOccurred, Is.EqualTo(effectMayHaveOccurred));
        });
    }

    // Renew al máximo (auditoría de flujos): Windows brings a window minimized from maximized back maximized
    // (WPF_RESTORETOMAXIMIZED): «restaura el chrome» then failed verification, and «ponlo a la izquierda» said the window
    // takes no size (window_size_not_taken). The restore is asked once more and the window ends at its normal size.
    [TestCase(false)]
    [TestCase(true)]
    public async Task AWindowMinimizedFromMaximizedIsRestoredToItsNormalSize(bool snap)
    {
        var platform = new FakePlatform { RestoresToMaximized = true, WorkAreaBounds = new WindowBounds(0, 0, 1536, 816) };
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;
        windowId = (await provider.ExecuteAsync(windowId, WindowControlAction.Maximize, CancellationToken.None)).Window!.WindowId;
        windowId = (await provider.ExecuteAsync(windowId, WindowControlAction.Minimize, CancellationToken.None)).Window!.WindowId;

        WindowActionResult result = snap
            ? await provider.SnapAsync(windowId, "left", CancellationToken.None)
            : await provider.ExecuteAsync(windowId, WindowControlAction.Restore, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded && result.Verified, Is.True, result.ErrorCode);
            Assert.That(result.Window?.State, Is.EqualTo("normal"));
        });
    }

    // Round A: «cerrame todo» keeps only BAXY's own windows open; the receipt said «editorKeptOpen» of them.
    [Test]
    public async Task CloseAllSaysItKeptBaxysOwnWindowsAndNeverAnEditor()
    {
        var platform = new FakePlatform
        {
            Desktop =
            [
                new WindowSnapshot(
                    new WindowIdentity((nint)0x99, 7, 638_880_000_000_000_000, "Baxy", DateTimeOffset.UnixEpoch),
                    "normal", true, new WindowBounds(0, 0, 400, 600)),
            ],
        };

        OperationOutcome outcome = await Run(new WindowCloseAllHandler(new WindowsWindowControlProvider(platform)), new { });

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.GetProperty("keptOpen").GetInt32(), Is.EqualTo(1));
            Assert.That(outcome.Result!.Value.GetProperty("keptProcesses")[0].GetString(), Is.EqualTo("Baxy"));
            Assert.That(outcome.Result!.Value.TryGetProperty("editorKeptOpen", out _), Is.False);
        });
    }

    private static ValueTask<OperationOutcome> Run(IOperationHandler handler, object arguments) =>
        handler.ExecuteAsync(
            new OperationInvocation("request", "mission", "invocation", JsonSerializer.SerializeToElement(arguments)),
            CancellationToken.None);

    [TestCase("")]
    [TestCase("C:\\Windows\\notepad.exe")]
    [TestCase("notepad:evil")]
    public async Task ResolveRejectsUnboundedOrPathLikeSelectors(string selector)
    {
        var provider = new WindowsWindowControlProvider(new FakePlatform());

        WindowResolveResult result = await provider.ResolveAsync(
            selector, 10, CancellationToken.None);

        Assert.That(result.ErrorCode, Is.EqualTo(WindowControlErrorCodes.InvalidSelector));
    }

    private sealed class FakePlatform : IWindowControlPlatform
    {
        private readonly WindowIdentity _identity = new(
            (nint)0x1234, 42, 638_880_000_000_000_000, "notepad", DateTimeOffset.UnixEpoch);
        private string _state = "normal";
        private bool _foreground;
        private WindowBounds _bounds = new(0, 0, 640, 480);

        public DateTimeOffset UtcNow { get; set; } =
            new(2026, 7, 16, 0, 0, 0, TimeSpan.Zero);
        public bool IdentityChanged { get; set; }
        public int ExecuteCalls { get; private set; }
        public int CloseCalls { get; private set; }
        public int SystemCloseCalls { get; private set; }
        public bool Closed { get; private set; }
        public int SetBoundsCalls { get; private set; }
        public int DelayCalls { get; private set; }
        public int ActionConvergenceDelayCount { get; set; }
        public bool PrimaryCloseAccepted { get; set; } = true;
        public bool PrimaryCloseCloses { get; set; } = true;
        public bool SystemCloseAccepted { get; set; }
        public bool SystemCloseCloses { get; set; }
        public bool ExecuteAccepted { get; set; } = true;
        public bool SetBoundsAccepted { get; set; } = true;
        // Renew al máximo (8.3): Windows takes the placement and the window keeps its bounds.
        public bool SetBoundsIgnored { get; set; }
        // Renew al máximo (8.3): the read from which the window is gone (-1: never), and the reads so far.
        public int GoneAfterObservations { get; set; } = -1;
        public int ObserveCalls { get; private set; }
        // As Windows: a window minimized from maximized comes back maximized from its first restore.
        public bool RestoresToMaximized { get; set; }
        private bool _minimizedFromMaximized;
        public WindowBounds? WorkAreaBounds { get; set; }
        public IReadOnlyList<WindowSnapshot> Desktop { get; set; } = [];
        private WindowControlAction? _pendingAction;
        public bool Foreground
        {
            get => _foreground;
            set => _foreground = value;
        }

        public WindowSnapshot? FindForegroundWindow() => _foreground
            ? new WindowSnapshot(_identity, _state, true, _bounds)
            : null;

        public WindowEnumeration FindVisibleWindows(string processName, int limit,
            bool byTitle = false, int offset = 0, bool allWindows = false,
            CancellationToken cancellationToken = default)
        {
            Assert.That(processName, Is.EqualTo("notepad").IgnoreCase);
            Assert.That(limit, Is.EqualTo(10));
            Assert.That(offset, Is.Zero);
            Assert.That(allWindows, Is.False);
            cancellationToken.ThrowIfCancellationRequested();
            return new WindowEnumeration([new WindowSnapshot(_identity, _state, _foreground, _bounds)], 1, true);
        }

        // Auditoría D7: the close hides the window instead (it still exists, invisible), or the window is gone when
        // the close would reach it.
        public bool CloseHides { get; set; }
        public bool GoneAtClose { get; set; }
        // How many reads see the closed window hidden before it is gone (a browser hiding it first); -1: it stays hidden.
        public int HiddenReads { get; set; } = -1;
        private int _hiddenSeen;

        public WindowSnapshot Observe(WindowIdentity identity)
        {
            if (++ObserveCalls >= GoneAfterObservations && GoneAfterObservations >= 0)
                throw new WindowIdentityChangedException();
            if (Closed && CloseHides && (HiddenReads < 0 || _hiddenSeen++ < HiddenReads))
                throw new WindowIdentityChangedException(hidden: true);
            if (IdentityChanged || Closed) throw new WindowIdentityChangedException();
            Assert.That(identity.Handle, Is.EqualTo(_identity.Handle));
            Assert.That(identity.ProcessCreationTimeUtcTicks,
                Is.EqualTo(_identity.ProcessCreationTimeUtcTicks));
            return new WindowSnapshot(identity, _state, _foreground, _bounds);
        }

        public bool Execute(WindowIdentity identity, WindowControlAction action)
        {
            ExecuteCalls++;
            _ = Observe(identity);
            if (!ExecuteAccepted)
                return false;
            if (ActionConvergenceDelayCount > 0)
            {
                _pendingAction = action;
                return true;
            }

            ApplyAction(action);
            return true;
        }

        private void ApplyAction(WindowControlAction action)
        {
            switch (action)
            {
                case WindowControlAction.Focus:
                    _foreground = true;
                    _state = "normal";
                    break;
                case WindowControlAction.Minimize:
                    _minimizedFromMaximized = RestoresToMaximized && _state == "maximized";
                    _foreground = false;
                    _state = "minimized";
                    break;
                case WindowControlAction.Maximize:
                    _state = "maximized";
                    break;
                case WindowControlAction.Restore:
                    _state = _state == "minimized" && _minimizedFromMaximized ? "maximized" : "normal";
                    _minimizedFromMaximized = false;
                    break;
            }
        }

        public bool RequestClose(WindowIdentity identity)
        {
            CloseCalls++;
            if (GoneAtClose) throw new WindowIdentityChangedException();
            _ = Observe(identity);
            if (PrimaryCloseCloses)
            {
                Closed = true;
            }
            return PrimaryCloseAccepted;
        }

        public bool RequestSystemClose(WindowIdentity identity)
        {
            SystemCloseCalls++;
            _ = Observe(identity);
            if (SystemCloseCloses)
            {
                Closed = true;
            }
            return SystemCloseAccepted;
        }

        public bool SetBounds(WindowIdentity identity, WindowBounds bounds)
        {
            SetBoundsCalls++;
            _ = Observe(identity);
            if (!SetBoundsAccepted)
                return false;
            if (!SetBoundsIgnored)
                _bounds = bounds;
            return true;
        }

        public WindowBounds? WorkArea(WindowIdentity identity) => WorkAreaBounds;

        public IReadOnlyList<WindowSnapshot> DesktopWindows() => Desktop;

        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            DelayCalls++;
            if (_pendingAction is { } action
                && DelayCalls >= ActionConvergenceDelayCount)
            {
                _pendingAction = null;
                ApplyAction(action);
            }
            return ValueTask.CompletedTask;
        }

        public void SetInitialState(string state) => _state = state;
    }
}
