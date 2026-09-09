using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class WindowsOperatingSystemProbeTests
{
    [TestCase("Microsoft Windows 11 Pro", "10.0.26100", 1, 26100, true)]
    [TestCase("Microsoft Windows 10 Enterprise", "10.0.19045", 1, 19045, true)]
    [TestCase("Microsoft Windows Server 2022 Standard", "10.0.20348", 2, 20348, false)]
    [TestCase("Microsoft Windows Server 2025 Standard", "10.0.26100", 3, 26100, false)]
    [TestCase("  Windows de evaluación  ", "10.0.26100", 1, 26100, true)]
    public async Task ReadsTheObservedCaptionWithoutGuessingAReleaseFromNtVersion(
        string caption, string version, int productType, int build, bool workstation)
    {
        var runner = new StubRunner
        {
            Output = $$"""{"Caption":"{{caption}}","Version":"{{version}}","ProductType":{{productType}}} """,
        };
        var provider = new WindowsSystemStatusProvider(
            new WindowsSystemStatusProbe(runner), TimeSpan.FromMilliseconds(10));

        SystemStatusSnapshot result = await provider.GetStatusAsync(
            SystemStatusScope.OperatingSystem, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Failures, Is.Empty);
            Assert.That(result.OperatingSystem!.Caption, Is.EqualTo(caption.Trim()));
            Assert.That(result.OperatingSystem.MajorVersion, Is.EqualTo(10));
            Assert.That(result.OperatingSystem.BuildNumber, Is.EqualTo(build));
            Assert.That(result.OperatingSystem.IsWorkstation, Is.EqualTo(workstation));
            Assert.That(runner.Executable, Is.EqualTo("powershell.exe"));
            Assert.That(runner.Arguments, Does.Contain("-NonInteractive"));
            Assert.That(runner.Arguments![^1], Does.Contain("-Property Caption,Version,ProductType"));
            Assert.That(runner.Timeout, Is.EqualTo(TimeSpan.FromSeconds(5)));
        });
    }

    [TestCase("not json")]
    [TestCase("[]")]
    [TestCase("null")]
    [TestCase("{}")]
    [TestCase("{\"Caption\":null,\"Version\":\"10.0.26100\",\"ProductType\":1}")]
    [TestCase("{\"Caption\":\"Windows\",\"Version\":\"invalid\",\"ProductType\":1}")]
    [TestCase("{\"Caption\":\"Windows\",\"Version\":\"10.0.26100\",\"ProductType\":4}")]
    [TestCase("{\"Caption\":\"Windows\",\"Version\":\"10.0.26100\",\"ProductType\":\"1\"}")]
    [TestCase("{\"Caption\":\"\",\"Version\":\"10.0.26100\",\"ProductType\":1}")]
    [TestCase("{\"Caption\":\"Windows\\n11\",\"Version\":\"10.0.26100\",\"ProductType\":1}")]
    [TestCase("{\"Caption\":\"Windows\",\"Version\":\"10.0\",\"ProductType\":1}")]
    public async Task InvalidObservationCannotBecomeAVerifiedOperatingSystem(string output)
    {
        var provider = new WindowsSystemStatusProvider(
            new WindowsSystemStatusProbe(new StubRunner { Output = output }),
            TimeSpan.FromMilliseconds(10));

        SystemStatusSnapshot result = await provider.GetStatusAsync(
            SystemStatusScope.OperatingSystem, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.OperatingSystem, Is.Null);
            Assert.That(result.Failures, Has.Count.EqualTo(1));
            Assert.That(result.Failures[0].Scope, Is.EqualTo(SystemStatusScope.OperatingSystem));
        });
    }

    [TestCase(false)]
    [TestCase(true)]
    public async Task CimFailureIsSanitizedAndDoesNotDiscardOtherScopes(bool timeout)
    {
        var runner = new StubRunner
        {
            ExitCode = 1,
            Exception = timeout ? new TimeoutException("private process detail") : null,
        };
        var provider = new WindowsSystemStatusProvider(
            new WindowsSystemStatusProbe(runner), TimeSpan.FromMilliseconds(10));

        SystemStatusSnapshot result = await provider.GetStatusAsync(
            SystemStatusScope.OperatingSystem | SystemStatusScope.Uptime, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.OperatingSystem, Is.Null);
            Assert.That(result.UptimeSeconds, Is.Not.Null);
            Assert.That(result.Failures, Is.EqualTo(new[]
            {
                new SystemStatusFailure(SystemStatusScope.OperatingSystem, SystemStatusErrorCodes.MeasurementFailed),
            }));
        });
    }

    [Test]
    public async Task CancellationReachesTheRunningCimRead()
    {
        using var cancellation = new CancellationTokenSource();
        var started = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var runner = new StubRunner
        {
            Wait = async token =>
            {
                started.SetResult();
                await Task.Delay(Timeout.Infinite, token);
            },
        };
        var provider = new WindowsSystemStatusProvider(
            new WindowsSystemStatusProbe(runner), TimeSpan.FromMilliseconds(10));
        Task<SystemStatusSnapshot> pending = provider.GetStatusAsync(
            SystemStatusScope.OperatingSystem, cancellation.Token).AsTask();
        await started.Task.WaitAsync(TimeSpan.FromSeconds(5));
        cancellation.Cancel();

        Assert.ThrowsAsync<TaskCanceledException>(async () => await pending);
        Assert.That(runner.Token, Is.EqualTo(cancellation.Token));
    }

    private sealed class StubRunner : IExternalProcessRunner
    {
        public string Output { get; init; } = "";
        public int ExitCode { get; init; }
        public Exception? Exception { get; init; }
        public Func<CancellationToken, Task>? Wait { get; init; }
        public string? Executable { get; private set; }
        public IReadOnlyList<string>? Arguments { get; private set; }
        public TimeSpan Timeout { get; private set; }
        public CancellationToken Token { get; private set; }

        public async ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments,
            TimeSpan timeout, CancellationToken cancellationToken)
        {
            Executable = executable;
            Arguments = arguments;
            Timeout = timeout;
            Token = cancellationToken;
            if (Exception is not null)
            {
                throw Exception;
            }
            if (Wait is not null)
            {
                await Wait(cancellationToken);
            }
            return new ExternalProcessResult(ExitCode, Output, "private process detail");
        }
    }
}
