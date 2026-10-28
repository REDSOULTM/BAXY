using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class NativeWindowFocusTests
{
    // Renew al máximo (w8): a window whose own dialog (or the dialog's own) holds the front is in front; another
    // window, or one that only shares a process, is not.
    [TestCase(10L, true)]
    [TestCase(11L, true)]
    [TestCase(12L, true)]
    [TestCase(20L, false)]
    [TestCase(0L, false)]
    public void AWindowWhoseOwnDialogHoldsTheFrontHoldsIt(long foreground, bool holds)
    {
        var owners = new Dictionary<nint, nint> { [11] = 10, [12] = 11, [20] = 30 };
        Assert.That(Win32WindowControlPlatform.HoldsTheFront(
            10, (nint)foreground, window => owners.TryGetValue(window, out nint owner) ? owner : 0), Is.EqualTo(holds));
    }

    // C37 (NB-R6, R6N2p3): resolving a process listed an application's untitled floating bar (owned, 437×23) first,
    // and window.snap moved it instead of the document window. An owned window without a title is not one of the
    // process's windows; an owned dialog with a title and an unowned window are.
    [TestCase(11L, "", false)]
    [TestCase(11L, "   ", false)]
    [TestCase(12L, "Guardar como", true)]
    [TestCase(10L, "", true)]
    [TestCase(10L, "c13 - Word", true)]
    public void AnOwnedWindowWithoutATitleIsNotListedForItsProcess(long window, string title, bool listed)
    {
        var owners = new Dictionary<nint, nint> { [11] = 10, [12] = 10 };
        Assert.That(Win32WindowControlPlatform.ListedForProcess(
            (nint)window, handle => owners.TryGetValue(handle, out nint owner) ? owner : 0, _ => title),
            Is.EqualTo(listed));
    }

    [TestCase("normal")]
    [TestCase("maximized")]
    public void VisibleWindowFocusDoesNotChangeShowState(string state)
    {
        var calls = new List<string>();

        bool result = Focus(state, calls, showResult: false, foregroundResult: true);

        Assert.Multiple(() =>
        {
            Assert.That(result, Is.True);
            Assert.That(calls, Is.EqualTo(new[] { "focus" }));
        });
    }

    [Test]
    public void MinimizedWindowRestoresBeforeRequestingFocus()
    {
        var calls = new List<string>();

        bool result = Focus("minimized", calls, showResult: true, foregroundResult: true);

        Assert.Multiple(() =>
        {
            Assert.That(result, Is.True);
            Assert.That(calls, Is.EqualTo(new[] { "show:9", "focus" }));
        });
    }

    [Test]
    public void FailedRestoreDoesNotRequestFocus()
    {
        var calls = new List<string>();

        bool result = Focus("minimized", calls, showResult: false, foregroundResult: true);

        Assert.Multiple(() =>
        {
            Assert.That(result, Is.False);
            Assert.That(calls, Is.EqualTo(new[] { "show:9" }));
        });
    }

    [TestCase("normal")]
    [TestCase("maximized")]
    [TestCase("minimized")]
    public void FailedForegroundRequestDoesNotReportSuccess(string state)
    {
        var calls = new List<string>();

        bool result = Focus(state, calls, showResult: true, foregroundResult: false);

        Assert.Multiple(() =>
        {
            Assert.That(result, Is.False);
            Assert.That(calls, Is.EqualTo(state == "minimized"
                ? new[] { "show:9", "focus" }
                : new[] { "focus" }));
        });
    }

    // Ronda B: a window act asked for moves the front on purpose, so the guard of an app.open started before it stops
    // instead of handing the front back to the window that had it (it undid a window.focus asked within its 3 s).
    [TestCase(WindowControlAction.Focus, "focus")]
    [TestCase(WindowControlAction.Minimize, "show:6")]
    [TestCase(WindowControlAction.Maximize, "show:3")]
    [TestCase(WindowControlAction.Restore, "show:9")]
    public void ARequestedWindowActStopsTheGuardOfAnOpening(WindowControlAction action, string call)
    {
        var calls = new List<string>();
        var identity = new WindowIdentity((nint)0x1234, 42, 123, "example", DateTimeOffset.UnixEpoch);
        var snapshot = new WindowSnapshot(identity, "normal", false, new WindowBounds(0, 0, 800, 600));
        ForegroundHandBack.GuardStamp guard = ForegroundHandBack.Stamp();

        bool result = Win32WindowControlPlatform.Act(snapshot, action,
            (_, command) =>
            {
                calls.Add($"show:{command}");
                return true;
            },
            _ =>
            {
                calls.Add("focus");
                return true;
            });

        Assert.Multiple(() =>
        {
            Assert.That(result, Is.True);
            Assert.That(calls, Is.EqualTo(new[] { call }));
            Assert.That(ForegroundHandBack.Interrupted(guard), Is.True);
        });
    }

    private static bool Focus(string state, List<string> calls, bool showResult, bool foregroundResult)
    {
        var identity = new WindowIdentity((nint)0x1234, 42, 123, "example", DateTimeOffset.UnixEpoch);
        var snapshot = new WindowSnapshot(identity, state, false, new WindowBounds(0, 0, 800, 600));
        return Win32WindowControlPlatform.ExecuteFocus(snapshot,
            (handle, command) =>
            {
                Assert.That(handle, Is.EqualTo(identity.Handle));
                calls.Add($"show:{command}");
                return showResult;
            },
            handle =>
            {
                Assert.That(handle, Is.EqualTo(identity.Handle));
                calls.Add("focus");
                return foregroundResult;
            });
    }
}
