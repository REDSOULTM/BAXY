using System.Reflection;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The conversation's «Bypass · hecho sin preguntar» line (FieldProductChannel.OnStepCompleted): it says that a call
/// normal mode would have asked about was done, so it appears only for one that completed and was verified.
/// </summary>
[TestFixture]
public sealed class BypassNoticeTests
{
    private const string Operation = "system.recyclebin.empty";

    [TestCase(OperationStatuses.Failed, false)]
    [TestCase(OperationStatuses.Completed, false)]
    public async Task ACallThatWasNotDoneAndVerifiedIsNotSaidDone(string status, bool verified)
    {
        IReadOnlyList<JsonObject> lines = await LinesAfterAsync(Step(status, verified));

        Assert.That(lines.Select(static l => (string?)l["text"]), Has.None.StartsWith("Bypass"));
    }

    [Test]
    public async Task ACallDoneAndVerifiedIsSaidDoneWithoutAsking()
    {
        IReadOnlyList<JsonObject> lines = await LinesAfterAsync(Step(OperationStatuses.Completed, verified: true));

        Assert.That(lines.Select(static l => (string?)l["text"]), Has.One.StartsWith("Bypass · hecho sin preguntar: "));
    }

    private static NativeTurnStep Step(string status, bool verified) =>
        new(Operation, new JsonObject(), status, verified, status == OperationStatuses.Failed ? "provider_failed" : null,
            12, "{}", "c1", Sent: true);

    // The shell's lines the view got after the call ended in bypass mode, as the turn loop reports it.
    private static async Task<IReadOnlyList<JsonObject>> LinesAfterAsync(NativeTurnStep step)
    {
        using var fake = new FakeMind();
        ConfirmationModeStore.Write(MemoryOperationProtector.ResolveDataRoot(), ConfirmationMode.Bypass);
        Assert.That(FieldStepProjection.NormalModeAsks(Operation, new JsonObject()), Is.True);
        var viewModel = new MainWindowViewModel();
        await using (viewModel)
        await using (var view = new ChannelHarness(viewModel))
        {
            const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
            object loop = typeof(MainWindowViewModel).GetField("_loop", Private)!.GetValue(viewModel)!;
            var host = (NativeTurnLoop.Host)typeof(NativeTurnLoop).GetField("_host", Private)!.GetValue(loop)!;
            host.StepCompleted!(step);
            return [.. view.Sink.Items.Where(static i => (string?)i["who"] == "sys")];
        }
    }
}
