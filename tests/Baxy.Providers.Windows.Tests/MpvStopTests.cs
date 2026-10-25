using System.ComponentModel;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Revisión nb-q-apps2: ending the local player or yt-dlp is best effort; what Process.Kill throws when Windows refuses
/// (Win32Exception) or ends the tree partway (AggregateException) never escapes. Nothing real is ended.
/// </summary>
[TestFixture]
public sealed class MpvStopTests
{
    private static IEnumerable<Exception> KillFailures()
    {
        yield return new InvalidOperationException("already exited");
        yield return new Win32Exception(5);
        yield return new AggregateException(new Win32Exception(5));
    }

    [TestCaseSource(nameof(KillFailures))]
    public void AKillWindowsRefusesIsSwallowed(Exception failure)
    {
        Assert.DoesNotThrow(() => YouTubeMpvAdapter.TryStop(() => throw failure));
    }
}
