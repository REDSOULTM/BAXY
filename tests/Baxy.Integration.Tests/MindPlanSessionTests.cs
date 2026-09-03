using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class MindPlanSessionTests
{
    [Test]
    public async Task CancelWithoutAnUncertainEffectClearsThePendingPlan()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-plan-session-" + Guid.NewGuid());
        Directory.CreateDirectory(root);
        try
        {
            var published = new List<(string Body, UserMessageEvent? Event)>();
            var session = new MindPlanSession(
                new MindPlanSession.Host
                {
                    Core = static () => null,
                    Mind = static () => null,
                    Publish = (body, messageEvent) => published.Add((body, messageEvent)),
                    SetStatus = static _ => { },
                    TryMarkResolved = static (_, _) => true,
                });
            session.UseStore(
                new DurablePlanStore(
                    Path.Combine(root, "planner-state.v1.bin"),
                    Path.Combine(root, "planner-state.v1.key")));
            var execution = new PendingMindPlanExecution(
                "abre notepad",
                [
                    new MindPlanStep(
                        "open",
                        "app.open",
                        "Abre notepad.",
                        [],
                        "literal",
                        new JsonObject { ["appId"] = "windows.notepad" }),
                ]);
            session.Begin(execution);
            var registry = new RetryableOperationRegistry(Path.Combine(root, "outbox.bin"));

            await session.HandlePendingAsync("cancelar", registry, CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(session.HasPending, Is.False);
                Assert.That(published, Has.Count.EqualTo(1));
                Assert.That(
                    published[0].Body,
                    Is.EqualTo(TurnVisibleFacts.Status("remaining_steps_cancelled")));
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [Test]
    public async Task UnrecognizedReplyAsksToContinueOrCancelWithoutTouchingCore()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-plan-prompt-" + Guid.NewGuid());
        Directory.CreateDirectory(root);
        try
        {
            var published = new List<string>();
            var session = new MindPlanSession(
                new MindPlanSession.Host
                {
                    Core = static () => throw new AssertionException("Core must not run."),
                    Mind = static () => throw new AssertionException("Mind must not run."),
                    Publish = (body, _) => published.Add(body),
                    SetStatus = static _ => { },
                    TryMarkResolved = static (_, _) => true,
                });
            session.UseStore(
                new DurablePlanStore(
                    Path.Combine(root, "planner-state.v1.bin"),
                    Path.Combine(root, "planner-state.v1.key")));
            session.Begin(
                new PendingMindPlanExecution(
                    "abre notepad",
                    [
                        new MindPlanStep(
                            "open",
                            "app.open",
                            "Abre notepad.",
                            [],
                            "literal",
                            new JsonObject { ["appId"] = "windows.notepad" }),
                    ]));
            var registry = new RetryableOperationRegistry(Path.Combine(root, "outbox.bin"));

            await session.HandlePendingAsync("tal vez", registry, CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(session.HasPending, Is.True);
                Assert.That(published, Has.Count.EqualTo(1));
                Assert.That(published[0], Does.Contain("continuar"));
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }
}
