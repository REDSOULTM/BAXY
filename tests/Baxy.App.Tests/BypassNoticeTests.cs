using System.Reflection;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The conversation's «Bypass · … sin preguntar» line (FieldProductChannel.OnStepCompleted): it says that a call
/// normal mode would have asked about ran without asking, as its step ended: «hecho» only for an effect read back.
/// </summary>
[TestFixture]
public sealed class BypassNoticeTests
{
    private const string Operation = "system.recyclebin.empty";

    [Test]
    public async Task AFailedCallIsNotSaid()
    {
        IReadOnlyList<JsonObject> lines = await LinesAfterAsync(Step(OperationStatuses.Failed, verified: false, "{}"));

        Assert.That(lines.Select(static l => (string?)l["text"]), Has.None.StartsWith("Bypass"));
    }

    [TestCase(false, "{}")]
    [TestCase(true, "{\"verification\":\"none\"}")]
    public async Task ACompletionThatWasNotVerifiedIsNotSaidDone(bool verified, string observation)
    {
        IReadOnlyList<JsonObject> lines = await LinesAfterAsync(Step(OperationStatuses.Completed, verified, observation));

        Assert.That(lines.Select(static l => (string?)l["text"]),
            Has.One.StartsWith("Bypass · sin preguntar, puede haber corrido: "));
    }

    [TestCase("readback", "Bypass · hecho sin preguntar: ")]
    [TestCase("unchanged", "Bypass · sin preguntar, ya estaba así: ")]
    [TestCase("delivered_only", "Bypass · enviado sin preguntar, sin comprobar: ")]
    public async Task ACompletedCallIsSaidAsItWasVerified(string verification, string said)
    {
        IReadOnlyList<JsonObject> lines = await LinesAfterAsync(Step(OperationStatuses.Completed, verified: true,
            "{\"status\":\"completed\",\"verification\":\"" + verification + "\"}"));

        Assert.That(lines.Select(static l => (string?)l["text"]), Has.One.StartsWith(said));
    }

    // Uso real 2026-11-02: a send the person said «sí» to failed after reaching its provider, and the line said it ran
    // «sin preguntar, puede haber corrido». It was asked: no Bypass line, whatever it ended in.
    [TestCase(OperationStatuses.Completed, true, "{\"status\":\"completed\",\"verification\":\"readback\"}")]
    [TestCase(OperationStatuses.Completed, false, "{}")]
    public async Task ACallThePersonSaidYesToIsNeverSaidUnasked(string status, bool verified, string observation)
    {
        IReadOnlyList<JsonObject> lines = await LinesAfterAsync(Step(status, verified, observation) with { Asked = true });

        Assert.That(lines.Select(static l => (string?)l["text"]), Has.None.StartsWith("Bypass"));
    }

    private static NativeTurnStep Step(string status, bool verified, string observation) =>
        new(Operation, new JsonObject(), status, verified, status == OperationStatuses.Failed ? "provider_failed" : null,
            12, observation, "c1", Sent: true);

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
