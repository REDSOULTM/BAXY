using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// system.status scopes «firewall» and «updates» (auditoría de los pedidos reales, 2026-10-17): read through Windows
/// PowerShell, checked before anything is said, and nothing is said when the read did not come back whole.
/// </summary>
[TestFixture]
public sealed class SecurityStatusTests
{
    private static Task<SecurityStatusReading> Read(string scope, string output, int exitCode = 0) =>
        new WindowsSecurityStatusProvider(new ScriptedRunner(output, exitCode))
            .ReadAsync(scope, CancellationToken.None).AsTask();

    [Test]
    public async Task FirewallReportsEachProfileWhetherAllAreOnAndTheConnectedOnes()
    {
        SecurityStatusReading reading = await Read("firewall",
            """{"ok":true,"profiles":[{"name":"Domain","enabled":true},{"name":"Private","enabled":true},{"name":"Public","enabled":false}],"connected":"Private"}""");

        JsonElement result = reading.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(reading.ErrorCode, Is.Null);
            Assert.That(result.GetProperty("profiles").GetArrayLength(), Is.EqualTo(3));
            Assert.That(result.GetProperty("profiles")[2].GetProperty("enabled").GetBoolean(), Is.False);
            Assert.That(result.GetProperty("allEnabled").GetBoolean(), Is.False);
            Assert.That(result.GetProperty("connectedProfiles")[0].GetString(), Is.EqualTo("Private"));
            Assert.That(result.GetProperty("authority").GetString(), Is.EqualTo("windows_netsecurity_activestore_read"));
        });
    }

    [Test]
    public async Task OneProfileWrittenAsAnObjectIsStillRead()
    {
        SecurityStatusReading reading = await Read("firewall",
            """{"ok":true,"profiles":{"name":"Public","enabled":true},"connected":[]}""");

        Assert.Multiple(() =>
        {
            Assert.That(reading.Result!.Value.GetProperty("profiles").GetArrayLength(), Is.EqualTo(1));
            Assert.That(reading.Result!.Value.GetProperty("allEnabled").GetBoolean(), Is.True);
        });
    }

    [TestCase("firewall", "{\"ok\":false}", 0, "firewall_status_not_read")]
    [TestCase("firewall", "{\"ok\":true,\"profiles\":[]}", 0, "firewall_status_not_read")]
    [TestCase("firewall", "{\"ok\":true,\"profiles\":[{\"name\":\"Public\",\"enabled\":\"True\"}]}", 0, "firewall_status_not_read")]
    [TestCase("updates", "not json", 0, "update_status_not_read")]
    [TestCase("updates", "{\"ok\":true,\"reboot\":false,\"pending\":2}", 1, "update_status_not_read")]
    [TestCase("updates", "{\"ok\":true,\"reboot\":false}", 0, "update_status_not_read")]
    public async Task ReadThatDidNotComeBackWholeSaysNothing(string scope, string output, int exitCode, string code)
    {
        SecurityStatusReading reading = await Read(scope, output, exitCode);

        Assert.Multiple(() =>
        {
            Assert.That(reading.Result, Is.Null);
            Assert.That(reading.ErrorCode, Is.EqualTo(code));
        });
    }

    [Test]
    public async Task UpdatesSayTheCountTheRestartAndOnlyTheFirstTenTitlesFromTheLastSearch()
    {
        string titles = string.Join(",", Enumerable.Range(1, 12).Select(n => $"\"Update {n}\""));
        SecurityStatusReading reading = await Read("updates",
            $$"""{"ok":true,"reboot":true,"pending":12,"titles":[{{titles}}],"lastSearchUtc":"2026-10-17T12:17:26.0000000Z"}""");

        JsonElement result = reading.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("rebootRequired").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("pendingCount").GetInt32(), Is.EqualTo(12));
            Assert.That(result.GetProperty("shownCount").GetInt32(), Is.EqualTo(10));
            Assert.That(result.GetProperty("titles").GetArrayLength(), Is.EqualTo(10));
            Assert.That(result.GetProperty("searchedOnline").GetBoolean(), Is.False);
            Assert.That(result.GetProperty("lastSearchUtc").GetString(), Is.EqualTo("2026-10-17T12:17:26Z"));
        });
    }

    [Test]
    public async Task StatusRoutesFirewallAndUpdatesToTheSecurityReadAndKeepsItsCode()
    {
        var security = new FixedSecurity(new SecurityStatusReading(null, "update_status_not_read"));
        var handler = new SystemStatusHandler(new UnusedSystem(), new UnusedGpu(), security);

        OperationOutcome outcome = await handler.ExecuteAsync(
            new OperationInvocation("r", "m", "i", JsonDocument.Parse("{\"scope\":\"updates\"}").RootElement),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(security.Scopes, Is.EqualTo(new[] { "updates" }));
            Assert.That(outcome.ErrorCode, Is.EqualTo("update_status_not_read"));
        });
    }

    private sealed class ScriptedRunner(string output, int exitCode) : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new ExternalProcessResult(exitCode, output, string.Empty));
    }

    private sealed class FixedSecurity(SecurityStatusReading reading) : ISecurityStatusProvider
    {
        internal List<string> Scopes { get; } = [];

        public ValueTask<SecurityStatusReading> ReadAsync(string scope, CancellationToken cancellationToken)
        {
            Scopes.Add(scope);
            return ValueTask.FromResult(reading);
        }
    }

    private sealed class UnusedSystem : ISystemStatusProvider
    {
        public ValueTask<SystemStatusSnapshot> GetStatusAsync(SystemStatusScope scope, CancellationToken cancellationToken) =>
            throw new AssertionException("system measurements are not read for a security scope");
    }

    private sealed class UnusedGpu : IGpuStatusProvider
    {
        public ValueTask<GpuStatusSnapshot> GetStatusAsync(GpuStatusScope scope, CancellationToken cancellationToken) =>
            throw new AssertionException("the GPU is not read for a security scope");
    }
}
