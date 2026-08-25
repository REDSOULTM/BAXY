using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class Goal06VisibleVoiceTests
{
    [Test]
    public void NarrationEmitsStructuredFactsNotSpanishProse()
    {
        string success = ProductOperationNarrator.Instance.Narrate(
            "app.open",
            OperationOutcome.Success());
        string failure = ProductOperationNarrator.Instance.Narrate(
            "app.open",
            OperationOutcome.Failure("app_not_found"));

        Assert.Multiple(() =>
        {
            Assert.That(UserMessagePolicy.IsStructuredFacts(success), Is.True);
            Assert.That(UserMessagePolicy.IsStructuredFacts(failure), Is.True);
            Assert.That(success, Does.Contain("\"polarity\":\"success\""));
            Assert.That(failure, Does.Contain("\"polarity\":\"failure\""));
            Assert.That(success, Does.Not.Contain("Listo"));
            Assert.That(failure, Does.Not.Contain("No pude"));
        });
    }

    [Test]
    public void OversizedObservedPayloadIsOmittedBeforeTheWireContract()
    {
        JsonElement result = JsonSerializer.SerializeToElement(new
        {
            values = Enumerable.Repeat(new string('x', 200), 40).ToArray(),
        });

        string facts = ProductOperationNarrator.Instance.Narrate(
            "note.list",
            OperationOutcome.Success(result));
        using JsonDocument document = JsonDocument.Parse(facts);

        Assert.Multiple(() =>
        {
            Assert.That(facts.Length, Is.LessThanOrEqualTo(4_096));
            Assert.That(document.RootElement.TryGetProperty("observed", out _), Is.False);
            Assert.That(document.RootElement.GetProperty("polarity").GetString(), Is.EqualTo("success"));
        });
    }

    [Test]
    public void DuplicateObservedPropertiesCannotCrashTheNarrationBoundary()
    {
        using JsonDocument duplicate = JsonDocument.Parse("{\"version\":1,\"version\":2}");

        string facts = ProductOperationNarrator.Instance.Narrate(
            "reminder.create",
            OperationOutcome.Success(duplicate.RootElement.Clone()));
        using JsonDocument document = JsonDocument.Parse(facts);

        Assert.Multiple(() =>
        {
            Assert.That(document.RootElement.TryGetProperty("observed", out _), Is.False);
            Assert.That(document.RootElement.GetProperty("polarity").GetString(), Is.EqualTo("success"));
        });
    }

    [Test]
    public async Task ComposerPublishesInjectedProseForVerifiedSuccessAndUglyPaths()
    {
        var cases = new (string User, string Intent, string Source, string Authored)[]
        {
            (
                "abre Spotify",
                "status",
                OperationVisibleFacts.FromOutcome("app.open", OperationOutcome.Success()),
                "Listo, Spotify está abierto y sonando."),
            (
                "abre Spotify",
                "error",
                TurnVisibleFacts.Failure("provider_down"),
                "No pude: Spotify no responde."),
            (
                "haz algo raro",
                "error",
                TurnVisibleFacts.Failure("out_of_catalog"),
                "No pude: eso no lo hago."),
            (
                "hello",
                "welcome",
                TurnVisibleFacts.Welcome(),
                "Hola, estoy listo."),
        };

        foreach ((string user, string intent, string source, string authored) in cases)
        {
            UserMessageEvent messageEvent = intent switch
            {
                "welcome" => UserMessageEvent.Welcome,
                "error" => UserMessageEvent.Error(UserMessageDiagnosticCodes.LocalService),
                _ => UserMessageEvent.Status,
            };
            UserMessageDraft draft = UserMessagePolicy.Create(source, messageEvent);
            JsonObject facts = ModelMessageComposer.CreateFacts(draft);
            ModelMessageCompositionOutcome outcome = await ModelMessageComposer.ComposeAsync(
                draft,
                user,
                facts,
                (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(
                    new MindComposedMessage(authored)),
                cpuFallback: false,
                allowRecovery: true,
                CancellationToken.None);

            Assert.That(outcome.Text, Is.EqualTo(authored), user);
            Assert.That(outcome.Text, Is.Not.EqualTo(source), user);
            Assert.That(
                outcome.Text,
                Does.Not.Contain("un momento").IgnoreCase,
                user);
            Assert.That(
                UserMessagePolicy.IsStructuredFacts(outcome.Text!),
                Is.False,
                user);
        }
    }

    [Test]
    public void RecoveryDraftIsFactsNeverShownAsTheVisibleReply()
    {
        UserMessageDraft recovery = ModelMessageComposer.CreateRecoveryDraft();
        Assert.That(UserMessagePolicy.IsStructuredFacts(recovery.Source), Is.True);
        Assert.That(recovery.Source, Does.Not.Contain("No pude presentar"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(recovery.Source, recovery),
            Is.EqualTo("structured_facts_not_prose"));
    }

    [Test]
    public void ProgressStagesCarryNoVisibleProse()
    {
        foreach (string stage in FieldBridgeContract.ProgressStages)
        {
            Assert.That(FieldBridgeContract.Create(stage).Label, Is.Null, stage);
        }
    }

    [Test]
    public void PolicyRejectsInternalCodesAndSuccessOpenersOnFailure()
    {
        UserMessageDraft draft = UserMessagePolicy.Create(
            TurnVisibleFacts.Failure("timeout"),
            UserMessageEvent.Error(UserMessageDiagnosticCodes.Timeout));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "No pude: provider_down",
                draft),
            Is.EqualTo("internal_code"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "Listo, Chrome no respondió.",
                draft),
            Is.EqualTo("reversed_result"));
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "No pude: se agotó el tiempo.",
                draft),
            Is.Null);
    }
}
