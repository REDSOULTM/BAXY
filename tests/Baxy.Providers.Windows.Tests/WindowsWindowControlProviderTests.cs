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

    // Uso-108 (hondo 13, measured across the integrity boundary): a placement Windows refused says why for a window of an
    // administrator's process; a focus crosses it, so its refusal is another one.
    [TestCase(WindowControlAction.Maximize, true, WindowControlErrorCodes.WindowElevated)]
    [TestCase(WindowControlAction.Minimize, true, WindowControlErrorCodes.WindowElevated)]
    [TestCase(WindowControlAction.Maximize, false, WindowControlErrorCodes.ActionFailed)]
    [TestCase(WindowControlAction.Focus, true, WindowControlErrorCodes.ActionFailed)]
    public async Task APlacementRefusedSaysItIsAnElevatedWindowOnlyWhenItIs(WindowControlAction action, bool elevated, string code)
    {
        var platform = new FakePlatform { ExecuteAccepted = false, ElevatedProcess = elevated };
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        WindowActionResult result = await provider.ExecuteAsync(windowId, action, CancellationToken.None);

        Assert.That(result.ErrorCode, Is.EqualTo(code));
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

    // uso-108 A9: a window whose thread does not answer is told so, with nothing sent to it and no effect in doubt.
    [Test]
    public async Task NothingIsSentToAWindowThatDoesNotRespond()
    {
        var platform = new FakePlatform { Hung = true, WorkAreaBounds = new WindowBounds(0, 0, 1000, 800) };
        var provider = new WindowsWindowControlProvider(platform);
        async Task<string> Id() =>
            (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        WindowActionResult moved = await provider.SetBoundsAsync(await Id(), 20, 30, null, null, CancellationToken.None);
        WindowActionResult resized = await provider.SetBoundsAsync(await Id(), null, null, 800, 600, CancellationToken.None);
        WindowActionResult minimized = await provider.ExecuteAsync(await Id(), WindowControlAction.Minimize, CancellationToken.None);
        WindowActionResult snapped = await provider.SnapAsync(await Id(), "left", CancellationToken.None);
        WindowCloseResult closed = await provider.CloseAsync(await Id(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            foreach (WindowActionResult result in new[] { moved, resized, minimized, snapped })
            {
                Assert.That(result.ErrorCode, Is.EqualTo("window_not_responding"));
                Assert.That(result.EffectMayHaveOccurred, Is.False);
                Assert.That(result.StateAfter, Is.Null);
            }

            Assert.That(closed.ErrorCode, Is.EqualTo("window_not_responding"));
            Assert.That(closed.EffectMayHaveOccurred, Is.False);
            Assert.That(platform.SetBoundsCalls, Is.Zero);
            Assert.That(platform.ExecuteCalls, Is.Zero);
            Assert.That(platform.CloseCalls, Is.Zero);
            Assert.That(platform.SystemCloseCalls, Is.Zero);
        });
    }

    // uso-108 A13: the request is posted, so the read right after it may find the window where it was.
    [Test]
    public async Task AMoveThatLandsAfterSomeReadsIsConfirmed()
    {
        var old = new WindowBounds(0, 0, 640, 480);
        var platform = new FakePlatform { ReadsAfterMove = new Queue<WindowBounds>([old, old]) };
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        WindowActionResult result = await provider.SetBoundsAsync(windowId, 20, 30, null, null, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded && result.Verified, Is.True);
            Assert.That((result.Window!.X, result.Window.Y), Is.EqualTo((20, 30)));
            Assert.That(platform.DelayCalls, Is.EqualTo(2));
        });
    }

    // uso-108 A13 (agent-desktop window_op.rs:15): a window that adjusts its own size settles near what was asked, and the
    // result carries where it really is. Its first read alone proves nothing: it may still be on its way.
    [Test]
    public async Task AWindowThatSettlesNearTheSizeAskedIsWhereItWasAskedToGo()
    {
        var settled = new WindowBounds(0, 0, 797, 594);
        var platform = new FakePlatform { ReadsAfterMove = new Queue<WindowBounds>(Enumerable.Repeat(settled, 5)) };
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        WindowActionResult result = await provider.SetBoundsAsync(windowId, null, null, 800, 600, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded && result.Verified, Is.True);
            Assert.That((result.Window!.Width, result.Window.Height), Is.EqualTo((797, 594)));
            Assert.That(platform.DelayCalls, Is.EqualTo(1));
        });
    }

    // Review of uso-108: a move of a few pixels, the window read twice where it started: near what was asked and never moved.
    [Test]
    public async Task AMoveOfAFewPixelsThatDidNotHappenIsNotConfirmed()
    {
        var old = new WindowBounds(0, 0, 640, 480);
        var platform = new FakePlatform { ReadsAfterMove = new Queue<WindowBounds>(Enumerable.Repeat(old, 100)) };
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        WindowActionResult result = await provider.SetBoundsAsync(windowId, 5, 5, null, null, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.ErrorCode, Is.EqualTo(WindowControlErrorCodes.VerificationFailed));
            Assert.That(result.EffectMayHaveOccurred, Is.True);
            Assert.That((result.StateAfter?.X, result.StateAfter?.Y), Is.EqualTo(((int?)0, (int?)0)));
        });
    }

    // Control: the same few pixels, the window having moved and settled near them.
    [Test]
    public async Task AMoveOfAFewPixelsThatSettledNearThemIsConfirmed()
    {
        var settled = new WindowBounds(3, 4, 640, 480);
        var platform = new FakePlatform { ReadsAfterMove = new Queue<WindowBounds>(Enumerable.Repeat(settled, 5)) };
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        WindowActionResult result = await provider.SetBoundsAsync(windowId, 5, 5, null, null, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded && result.Verified, Is.True);
            Assert.That((result.Window!.X, result.Window.Y), Is.EqualTo((3, 4)));
        });
    }

    // Review of uso-108: on a half, what counts is being on it: a window that rounds its size (a terminal) is already there,
    // under the tolerance, and asked again stays where it is: it is on the half, in a moment, and that is said with its bounds.
    [Test]
    public async Task AWindowAlreadyOnTheHalfWithinTheToleranceIsThere()
    {
        var old = new WindowBounds(0, 0, 640, 480);
        var platform = new FakePlatform
        {
            WorkAreaBounds = new WindowBounds(0, 0, 1286, 484),
            ReadsAfterMove = new Queue<WindowBounds>(Enumerable.Repeat(old, 100)),
        };
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        WindowActionResult result = await provider.SnapAsync(windowId, "left", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded && result.Verified, Is.True);
            Assert.That((result.Window!.Width, result.Window.Height), Is.EqualTo((640, 480)));
            Assert.That(platform.DelayCalls, Is.LessThan(8), "not the whole wait");
        });
    }

    // Control: near the half at first and on its way: it is the arrival that is said.
    [Test]
    public async Task AWindowNearTheHalfThatMovesEndsOnTheHalf()
    {
        var old = new WindowBounds(0, 0, 640, 480);
        var platform = new FakePlatform
        {
            WorkAreaBounds = new WindowBounds(0, 0, 1286, 484),
            ReadsAfterMove = new Queue<WindowBounds>([old, old]),
        };
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        WindowActionResult result = await provider.SnapAsync(windowId, "left", CancellationToken.None);

        Assert.That((result.Window!.Width, result.Window.Height), Is.EqualTo((643, 484)));
    }

    // Control: far from the half and not moving is no placement.
    [Test]
    public async Task AWindowFarFromTheHalfThatDoesNotMoveIsNotConfirmed()
    {
        var old = new WindowBounds(0, 0, 640, 480);
        var platform = new FakePlatform
        {
            WorkAreaBounds = new WindowBounds(0, 0, 1000, 800),
            ReadsAfterMove = new Queue<WindowBounds>(Enumerable.Repeat(old, 100)),
        };
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        WindowActionResult result = await provider.SnapAsync(windowId, "left", CancellationToken.None);

        Assert.That(result.ErrorCode, Is.EqualTo(WindowControlErrorCodes.VerificationFailed));
    }

    // Control: a window still moving near the bounds is read until it arrives, and it is the arrival that is said.
    [Test]
    public async Task AWindowStillMovingNearTheBoundsIsReadUntilItArrives()
    {
        var platform = new FakePlatform
        {
            ReadsAfterMove = new Queue<WindowBounds>([new WindowBounds(14, 30, 640, 480), new WindowBounds(17, 30, 640, 480)]),
        };
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        WindowActionResult result = await provider.SetBoundsAsync(windowId, 20, 30, null, null, CancellationToken.None);

        Assert.That((result.Window!.X, result.Window.Y), Is.EqualTo((20, 30)));
    }

    // Control: settled farther than the tolerance is not where it was asked to go: the failure stands, with where it is.
    [Test]
    public async Task AWindowThatSettlesFarFromTheSizeAskedStaysUnconfirmed()
    {
        var settled = new WindowBounds(0, 0, 780, 580);
        var platform = new FakePlatform
        {
            ReadsAfterMove = new Queue<WindowBounds>(Enumerable.Repeat(settled, 100)),
        };
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        WindowActionResult result = await provider.SetBoundsAsync(windowId, null, null, 800, 600, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.ErrorCode, Is.EqualTo(WindowControlErrorCodes.VerificationFailed));
            Assert.That(result.EffectMayHaveOccurred, Is.True);
            Assert.That((result.StateAfter?.Width, result.StateAfter?.Height), Is.EqualTo(((int?)780, (int?)580)));
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

    // Auditoría del Core (w8): a maximize, minimize or restore already as asked said a bare changed:false (read as «no
    // pude», C13), while a move, a resize or a snap said the next too; now every window action says it.
    [TestCase(WindowControlAction.Maximize, "maximized")]
    [TestCase(WindowControlAction.Minimize, "minimized")]
    [TestCase(WindowControlAction.Restore, "normal")]
    public async Task AWindowActionAlreadyAsAskedSaysThisCallChangedNothing(WindowControlAction action, string state)
    {
        var platform = new FakePlatform();
        platform.SetInitialState(state);
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        OperationOutcome outcome = await Run(
            new WindowActionHandler("window." + action.ToString().ToLowerInvariant(), action, provider), new { windowId });

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.GetProperty("changed").GetBoolean(), Is.False);
            Assert.That(outcome.Result!.Value.GetProperty("next").GetString(), Is.EqualTo(WindowControlResultJson.UnchangedNext));
            Assert.That(outcome.Result!.Value.GetProperty("window").GetProperty("state").GetString(), Is.EqualTo(state));
            Assert.That(platform.ExecuteCalls, Is.Zero);
        });
    }

    // Contracase: an action that changed the window says neither.
    [Test]
    public async Task AWindowActionThatChangedTheWindowSaysNoUnchangedNext()
    {
        var platform = new FakePlatform();
        platform.SetInitialState("normal");
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        OperationOutcome outcome = await Run(
            new WindowActionHandler("window.maximize", WindowControlAction.Maximize, provider), new { windowId });

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.TryGetProperty("changed", out _), Is.False);
            Assert.That(outcome.Result!.Value.TryGetProperty("next", out _), Is.False);
        });
    }

    // Auditoría de falsedades: a window already where it was asked to go is told as its state before the call, never as
    // «done» by this call («¿ya lo moviste?»).
    [Test]
    public async Task AWindowAlreadyAsAskedSaysThisCallChangedNothing()
    {
        var platform = new FakePlatform();
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        OperationOutcome outcome = await Run(new WindowBoundsHandler("window.move", provider), new { windowId, x = 0, y = 0 });

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.GetProperty("changed").GetBoolean(), Is.False);
            string next = outcome.Result!.Value.GetProperty("next").GetString()!;
            Assert.That(next, Is.EqualTo(WindowControlResultJson.UnchangedNext));
            Assert.That(next, Does.Not.Contain("done"));
            Assert.That(platform.SetBoundsCalls, Is.Zero);
        });
    }

    // Auditoría de falsedades (F001): a windowId used up by an earlier action says the window was neither touched nor
    // read (BAXY told «la ventana se cerró» with Steam still open); the code stays, and with the aid off it is bare.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task AUsedUpWindowIdSaysTheWindowWasNotTouchedNorRead(string aids, bool told)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        var provider = new WindowsWindowControlProvider(new FakePlatform());
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;
        var focus = new WindowActionHandler("window.focus", WindowControlAction.Focus, provider);

        OperationOutcome first = await Run(focus, new { windowId });
        OperationOutcome again = await Run(focus, new { windowId });
        OperationOutcome snapped = await Run(new WindowSnapHandler(provider), new { windowId, side = "left" });

        Assert.Multiple(() =>
        {
            Assert.That(first.Succeeded, Is.True, first.ErrorCode);
            foreach (OperationOutcome spent in new[] { again, snapped })
            {
                Assert.That(spent.ErrorCode, Is.EqualTo(WindowControlErrorCodes.InvalidOrExpiredWindowId));
                Assert.That(spent.EffectMayHaveOccurred, Is.False);
                if (told)
                    Assert.That(spent.Result!.Value.GetProperty("next").GetString(),
                        Is.EqualTo(WindowControlResultJson.SpentWindowIdNext));
                else
                    Assert.That(spent.Result, Is.Null);
            }
        });
    }

    // Banco de entorno del NB (U43 3 of 3, R01, U44): window.focus {windowId: "264146"}, the number a look gives Word's
    // window, failed every time with a next that said the id was used up. A number that is a window open now leads with
    // the window_resolve call by that window's process; a number that is no window, and an id of another shape, keep the
    // used-up next; with the aid off, the old next.
    [TestCase("all", "264146", true, "window_resolve {\"process\":\"WINWORD\"} gives the windowId of each window of WINWORD")]
    [TestCase("all", "999", false, null)]
    [TestCase("all", "win_nope", false, null)]
    [TestCase("window_id_spent", "264146", true, null)]
    public async Task AWindowNumberGivenAsAWindowIdLeadsWithTheCallThatGivesItsWindowId(
        string aids, string windowId, bool open, string? numbered)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        var platform = new FakePlatform();
        if (open)
            platform.WindowProcesses[(nint)264146] = "WINWORD";
        var provider = new WindowsWindowControlProvider(platform);

        OperationOutcome focus = await Run(
            new WindowActionHandler("window.focus", WindowControlAction.Focus, provider), new { windowId });
        OperationOutcome snap = await Run(new WindowSnapHandler(provider), new { windowId, side = "left" });

        Assert.Multiple(() =>
        {
            foreach (OperationOutcome failed in new[] { focus, snap })
            {
                Assert.That(failed.ErrorCode, Is.EqualTo(WindowControlErrorCodes.InvalidOrExpiredWindowId));
                Assert.That(failed.EffectMayHaveOccurred, Is.False);
                string next = failed.Result!.Value.GetProperty("next").GetString()!;
                if (numbered is null)
                    Assert.That(next, Does.StartWith("nothing was done to the window: this windowId cannot be used"));
                else
                    Assert.That(next, Does.StartWith(numbered));
            }
            Assert.That(platform.ExecuteCalls, Is.Zero);
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

    // Auditoría del Core (w8): a snap Windows took and the window did not failed with nothing of the window, while move,
    // resize and the state actions said the window read after; now it says it too, with whether it is on the half.
    [Test]
    public async Task ASnapTheWindowDidNotTakeCarriesTheWindowReadAfter()
    {
        var platform = new FakePlatform { SetBoundsIgnored = true, WorkAreaBounds = new WindowBounds(0, 0, 1536, 816) };
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        OperationOutcome outcome = await Run(new WindowSnapHandler(provider), new { windowId, side = "left" });

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            JsonElement state = outcome.Result!.Value.GetProperty("stateAfter");
            Assert.That(state.GetProperty("present").GetBoolean(), Is.True);
            Assert.That(state.GetProperty("state").GetString(), Is.EqualTo("normal"));
            Assert.That(state.GetProperty("width").GetInt32(), Is.Not.EqualTo(768));
            Assert.That(state.GetProperty("requestedStateReached").GetBoolean(), Is.False);
            Assert.That(state.GetProperty("authority").GetString(), Is.EqualTo("windows_window_identity_postread"));
        });
    }

    // Contracase: a snap refused before anything reached the window says no state after.
    [Test]
    public async Task ASnapRefusedBeforeAnyEffectCarriesNoStateAfter()
    {
        var platform = new FakePlatform { SetBoundsAccepted = false, WorkAreaBounds = new WindowBounds(0, 0, 1536, 816) };
        var provider = new WindowsWindowControlProvider(platform);
        string windowId = (await provider.ResolveAsync("notepad", 10, CancellationToken.None)).Windows.Single().WindowId;

        WindowActionResult result = await provider.SnapAsync(windowId, "left", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.EffectMayHaveOccurred, Is.False);
            Assert.That(result.StateAfter, Is.Null);
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

    // Renew al máximo: a protected window (here a terminal) is never asked to close and stays open, yet the receipt
    // said allClosed true beside it. BAXY's own window kept open still lets «all» stand.
    [TestCase("WindowsTerminal", false)]
    [TestCase("Baxy", true)]
    public async Task CloseAllNeverSaysAllClosedWithAProtectedWindowOpen(string process, bool allClosed)
    {
        var platform = new FakePlatform
        {
            Desktop =
            [
                new WindowSnapshot(
                    new WindowIdentity((nint)0x99, 7, 638_880_000_000_000_000, process, DateTimeOffset.UnixEpoch),
                    "normal", true, new WindowBounds(0, 0, 400, 600)),
            ],
        };

        var handler = new WindowCloseAllHandler(new WindowsWindowControlProvider(platform));
        OperationOutcome outcome = await Run(handler, new { });

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.GetProperty("remainingVisible").GetInt32(), Is.Zero);
            Assert.That(outcome.Result!.Value.GetProperty("allClosed").GetBoolean(), Is.EqualTo(allClosed));
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
        // Banco de entorno del NB: the visible top-level windows by handle, with their process (a look's numbers).
        public Dictionary<nint, string> WindowProcesses { get; } = [];
        public string? ProcessOfWindow(nint window) => WindowProcesses.GetValueOrDefault(window);
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
        public bool ElevatedProcess { get; init; }
        public bool RunsElevatedAboveUs(WindowIdentity identity) => ElevatedProcess;
        public bool SetBoundsAccepted { get; set; } = true;
        // Renew al máximo (8.3): Windows takes the placement and the window keeps its bounds.
        public bool SetBoundsIgnored { get; set; }
        // uso-108: the window does not answer messages; and what the reads after a move find, each in turn.
        public bool Hung { get; set; }
        public bool NotResponding(WindowIdentity identity, CancellationToken cancellationToken) => Hung;
        public Queue<WindowBounds>? ReadsAfterMove { get; set; }
        private bool _moved;
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
            if (_moved && ReadsAfterMove is { Count: > 0 } reads)
                return new WindowSnapshot(identity, _state, _foreground, reads.Dequeue());
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
            _moved = true;
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
