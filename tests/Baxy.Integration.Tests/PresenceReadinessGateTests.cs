using System.Diagnostics;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class PresenceReadinessGateTests
{
    [Test]
    public void TurnIsRejectedUntilInputIsEnabled()
    {
        Assert.That(
            FieldBridgeContract.TryAcceptTurn(
                isInputEnabled: false,
                "abre notepad",
                out string error,
                out int status),
            Is.False);
        Assert.That(error, Is.EqualTo(FieldBridgeContract.AgentNotReadyError));
        Assert.That(status, Is.EqualTo(FieldBridgeContract.AgentNotReadyStatus));
    }

    [Test]
    public void ReadyTurnWithEmptyTextIsRejectedWithoutStartingAMission()
    {
        Assert.That(
            FieldBridgeContract.TryAcceptTurn(true, "  ", out string error, out int status),
            Is.False);
        Assert.That(error, Is.EqualTo("invalid_text"));
        Assert.That(status, Is.EqualTo(400));
    }

    [Test]
    public void ReadyTurnWithTextIsAcceptedByTheShippedGate()
    {
        Assert.That(
            FieldBridgeContract.TryAcceptTurn(true, "abre notepad", out string error, out int status),
            Is.True);
        Assert.That(error, Is.Empty);
        Assert.That(status, Is.EqualTo(200));
    }

    [Test]
    public void VoiceControlIsRejectedUntilTheShellIsReady()
    {
        Assert.That(
            FieldBridgeContract.TryAcceptVoiceControl(false, out string error, out int status),
            Is.False);
        Assert.That(error, Is.EqualTo(FieldBridgeContract.AgentNotReadyError));
        Assert.That(status, Is.EqualTo(409));
        Assert.That(
            FieldBridgeContract.TryAcceptVoiceControl(true, out error, out status),
            Is.True);
        Assert.That(error, Is.Empty);
        Assert.That(status, Is.EqualTo(200));
    }

    [Test]
    public async Task SubmitAsyncDoesNotAcceptATurnBeforeReady()
    {
        await using var viewModel = new MainWindowViewModel();
        viewModel.Draft = "abre notepad";

        Assert.That(viewModel.IsReady, Is.False);
        Assert.That(viewModel.IsInputEnabled, Is.False);
        Assert.That(viewModel.CanSend, Is.False);

        await viewModel.SubmitAsync(CancellationToken.None);

        Assert.That(viewModel.Messages, Is.Empty);
        Assert.That(viewModel.Draft, Is.EqualTo("abre notepad"));
        Assert.That(viewModel.HasStartupError, Is.False);
    }

    [Test]
    public async Task DeadChildProcessReachesABoundedHonestFailure()
    {
        string cmd = Path.Combine(Environment.SystemDirectory, "cmd.exe");
        Assert.That(File.Exists(cmd), Is.True);
        await using var client = new CoreProcessClient(cmd, ["/c", "exit", "1"]);
        var watch = Stopwatch.StartNew();
        Exception? failure = null;

        try
        {
            await client.StartAsync(TimeSpan.FromMilliseconds(800), CancellationToken.None);
        }
        catch (Exception exception)
        {
            failure = exception;
        }

        watch.Stop();
        Assert.That(failure, Is.Not.Null);
        Assert.That(
            MainWindowViewModel.IsExpectedStartupFailure(failure!),
            Is.True);
        Assert.That(client.IsReady, Is.False);
        Assert.That(watch.Elapsed, Is.LessThan(TimeSpan.FromSeconds(4)));
    }

    [Test]
    public void BridgeSourceUsesTheSharedReadyGate()
    {
        string bridge = File.ReadAllText(RepositoryPath("src", "Baxy.App", "FieldUiBridge.cs"));
        string contract = File.ReadAllText(RepositoryPath("src", "Baxy.App", "FieldBridgeContract.cs"));
        Assert.That(bridge, Does.Contain("FieldBridgeContract.TryAcceptTurn"));
        Assert.That(bridge, Does.Contain("FieldBridgeContract.TryAcceptVoiceControl"));
        Assert.That(contract, Does.Contain("AgentNotReadyError = \"agent_not_ready\""));
    }

    private static string RepositoryPath(params string[] path)
    {
        DirectoryInfo? current = new(TestContext.CurrentContext.TestDirectory);
        while (current is not null && !File.Exists(Path.Combine(current.FullName, "Baxy.slnx")))
        {
            current = current.Parent;
        }

        if (current is null)
        {
            throw new AssertionException("Could not locate the BAXY repository root.");
        }

        return path.Aggregate(current.FullName, Path.Combine);
    }
}
