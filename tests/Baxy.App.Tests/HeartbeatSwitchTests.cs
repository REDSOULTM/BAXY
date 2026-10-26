using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>Owner, 2026-10-22: the heartbeat stays off unless BAXY_RENEW_HEARTBEAT=1 asks for it.</summary>
[TestFixture]
[NonParallelizable]
public sealed class HeartbeatSwitchTests
{
    [TestCase(null, false)]
    [TestCase("0", false)]
    [TestCase("", false)]
    [TestCase("1", true)]
    public void TheHeartbeatBeatsOnlyWhenItIsAskedFor(string? value, bool enabled)
    {
        string? before = Environment.GetEnvironmentVariable("BAXY_RENEW_HEARTBEAT");
        try
        {
            Environment.SetEnvironmentVariable("BAXY_RENEW_HEARTBEAT", value);
            Assert.That(Heartbeat.Enabled, Is.EqualTo(enabled));
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_RENEW_HEARTBEAT", before);
        }
    }
}
