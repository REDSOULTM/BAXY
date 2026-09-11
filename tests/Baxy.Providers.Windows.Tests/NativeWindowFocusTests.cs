using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class NativeWindowFocusTests
{
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
