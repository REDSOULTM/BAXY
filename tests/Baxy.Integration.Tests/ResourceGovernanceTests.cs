using System.Text.Json.Nodes;

using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class ResourceGovernanceTests
{
    [Test]
    public async Task PendingCompositionStopsAtTheAutomaticAttemptCeiling()
    {
        await using var mind = new MindSidecarClient();
        int compositions = 0;
        int terminalFailures = 0;
        var terminal = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var queue = new PendingModelMessageQueue(
            _ => Task.FromResult<MindSidecarClient?>(mind),
            (_, _) => Task.CompletedTask,
            _ => Task.CompletedTask,
            _ =>
            {
                terminalFailures++;
                terminal.TrySetResult();
                return Task.CompletedTask;
            },
            () => { },
            (_, _, _) =>
            {
                compositions++;
                return Task.FromResult(
                    new ModelMessageCompositionOutcome(
                        null,
                        "composer_request_failed",
                        UsedRecovery: false));
            });
        UserMessageDraft draft = UserMessagePolicy.Create(
            "¿Quieres continuar?",
            UserMessageEvent.Confirmation);
        var pending = new PendingModelMessage(
            draft,
            "continúa",
            new JsonObject(),
            "resource-governance")
        {
            Attempts = PendingModelMessageQueue.MaximumCompositionAttempts - 1,
        };

        queue.Enqueue(pending, CancellationToken.None);
        await terminal.Task.WaitAsync(TimeSpan.FromSeconds(5));

        Assert.Multiple(
            () =>
            {
                Assert.That(compositions, Is.EqualTo(1));
                Assert.That(terminalFailures, Is.EqualTo(1));
                Assert.That(queue.Count, Is.Zero);
                Assert.That(
                    pending.Attempts,
                    Is.EqualTo(PendingModelMessageQueue.MaximumCompositionAttempts));
            });
        await queue.CloseAsync();
    }
}
