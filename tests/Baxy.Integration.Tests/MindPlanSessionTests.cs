using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class MindPlanSessionTests
{
    [TestCase(false, false)]
    [TestCase(true, false)]
    [TestCase(false, true)]
    [TestCase(true, true)]
    public void SupersedingConfirmationResolvesDurableIdentityOnlyBeforeAnyPossibleEffect(
        bool reconciliationRequired, bool uncertainEffect)
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-supersede-confirmation-" + Guid.NewGuid());
        Directory.CreateDirectory(root);
        try
        {
            var session = new MindPlanSession(new MindPlanSession.Host
            {
                Core = static () => throw new AssertionException("Superseding cannot execute Core."),
                Mind = static () => throw new AssertionException("Superseding cannot execute the mind."),
                Publish = static (_, _) => throw new AssertionException("Superseding does not claim an effect."),
                SetStatus = static _ => { },
                TryMarkResolved = static (_, _) => true,
            });
            var store = new DurablePlanStore(Path.Combine(root, "plan.bin"), Path.Combine(root, "plan.key"));
            session.UseStore(store);
            string outbox = Path.Combine(root, "outbox.bin");
            var registry = new RetryableOperationRegistry(outbox);
            var arguments = new JsonObject { ["appId"] = "windows.notepad" };
            PreparedOperation prepared = registry.GetOrAdd(new RoutedOperation("app.open", arguments));
            var execution = new PendingMindPlanExecution("abre notepad",
                [new MindPlanStep("open", "app.open", "Abre notepad.", [], "literal", arguments)])
            {
                PendingOperation = prepared,
                PendingEffectMayHaveOccurred = uncertainEffect,
            };
            var response = new OperationResponse(
                ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"),
                prepared.MissionId, prepared.InvocationId, OperationStatuses.Pending,
                "Confirmación requerida.", false, false,
                JsonSerializer.SerializeToElement(new
                {
                    version = 1,
                    token = Convert.ToBase64String(new byte[32]).TrimEnd('='),
                    expiresAtUtc = DateTimeOffset.UtcNow.AddMinutes(2)
                        .ToString("O", System.Globalization.CultureInfo.InvariantCulture),
                    reconciliationRequired,
                }), "confirmation_required");
            Assert.That(PendingOperationConfirmation.TryCreate(
                response, prepared, TimeProvider.System, out PendingOperationConfirmation? confirmation), Is.True);
            execution.RequireConfirmation(confirmation!);
            session.Begin(execution);

            bool canSupersede = !reconciliationRequired && !uncertainEffect;
            Assert.That(session.TrySupersedeUnstartedConfirmation(registry), Is.EqualTo(canSupersede));
            Assert.That(session.HasPending, Is.EqualTo(!canSupersede));
            if (canSupersede)
            {
                Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
                Assert.That(store.Load(registry), Is.Null);
            }
            else
            {
                Assert.That(session.Current, Is.SameAs(execution));
                Assert.That(session.Current!.Confirmation, Is.SameAs(confirmation));
                Assert.That(new DurableRetryStore(outbox).Load().Single().InvocationId, Is.EqualTo(prepared.InvocationId));
                Assert.That(store.Load(registry)!.PendingOperation!.InvocationId, Is.EqualTo(prepared.InvocationId));
            }
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [TestCase(false, "cancelar")]
    [TestCase(true, "cancelar")]
    [TestCase(true, "cierra la calculadora")]
    public async Task PendingRepliesPreserveUncertainEffects(bool uncertain, string text)
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
                ])
            { PendingEffectMayHaveOccurred = uncertain };
            session.Begin(execution);
            var registry = new RetryableOperationRegistry(Path.Combine(root, "outbox.bin"));

            await session.HandlePendingAsync(text, registry, CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(session.HasPending, Is.EqualTo(uncertain));
                Assert.That(published, Has.Count.EqualTo(1));
                if (uncertain)
                {
                    var facts = JsonNode.Parse(published[0].Body)!;
                    Assert.That((string?)facts["polarity"], Is.EqualTo("failure"));
                    Assert.That((bool?)facts["effectUncertain"], Is.True);
                    Assert.That((bool?)facts["pending"], Is.True);
                    Assert.That((bool?)facts["canRepeat"], Is.False);
                    Assert.That((bool?)facts["evidenceRetained"], Is.True);
                    Assert.That((string?)facts["pendingRequest"], Is.EqualTo("abre notepad"));
                    Assert.That(published[0].Event?.Type, Is.EqualTo(UserMessageEventType.Error));
                }
                else
                {
                    var facts = JsonNode.Parse(published[0].Body)!;
                    Assert.That((string?)facts["cause"], Is.EqualTo("remaining_steps_cancelled"));
                    Assert.That((string?)facts["cancelledRequest"], Is.EqualTo("abre notepad"));
                    Assert.That((string?)facts["cancelledAction"]?["operation"], Is.EqualTo("app.open"));
                    Assert.That(facts["pendingAction"], Is.Null);
                }
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

    // 2026-09-21: a message.send.test left awaiting confirmation the evening before was restored at the next
    // start and re-prompted at every new request; the «sí» meant for the new request confirmed the stale one.
    // A restored plan whose pending step never ran is dropped (outbox and store cleared) and announced as
    // cancelled; a step whose effect may have occurred is still restored for its truthful recovery prompt.
    [TestCase(false)]
    [TestCase(true)]
    public void RestoringAPreviousSessionPlanDropsANeverRunStepAndKeepsAnUncertainOne(bool uncertainEffect)
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-restore-stale-plan-" + Guid.NewGuid());
        Directory.CreateDirectory(root);
        try
        {
            var store = new DurablePlanStore(Path.Combine(root, "plan.bin"), Path.Combine(root, "plan.key"));
            string outbox = Path.Combine(root, "outbox.bin");
            var registry = new RetryableOperationRegistry(outbox);
            var arguments = new JsonObject { ["channel"] = "whatsapp", ["requestedRecipient"] = "amor", ["text"] = "la amo" };
            PreparedOperation prepared = registry.GetOrAdd(new RoutedOperation("message.send.test", arguments));
            var execution = new PendingMindPlanExecution("escribile a amor en WhatsApp que la amo",
                [new MindPlanStep("send", "message.send.test", "Envía el mensaje.", [], "literal", arguments)])
            {
                PendingOperation = prepared,
                PendingEffectMayHaveOccurred = uncertainEffect,
            };
            store.Save(execution);

            var session = new MindPlanSession(new MindPlanSession.Host
            {
                Core = static () => throw new AssertionException("Restoring cannot execute Core."),
                Mind = static () => throw new AssertionException("Restoring cannot execute the mind."),
                Publish = static (_, _) => throw new AssertionException("Restoring does not publish."),
                SetStatus = static _ => { },
                TryMarkResolved = static (_, _) => true,
            });
            session.UseStore(store);
            var restoredRegistry = new RetryableOperationRegistry(outbox);
            session.TryRestore(restoredRegistry);

            if (uncertainEffect)
            {
                Assert.That(session.HasPending, Is.True);
                Assert.That(session.DroppedRestoredPlan, Is.Null);
                Assert.That(new DurableRetryStore(outbox).Load().Single().InvocationId, Is.EqualTo(prepared.InvocationId));
            }
            else
            {
                Assert.That(session.HasPending, Is.False);
                Assert.That(session.DroppedRestoredPlan!.Objective, Is.EqualTo("escribile a amor en WhatsApp que la amo"));
                Assert.That(new DurableRetryStore(outbox).Load(), Is.Empty);
                Assert.That(store.Load(restoredRegistry), Is.Null);
            }
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }
}
