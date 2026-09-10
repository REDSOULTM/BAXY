using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class ObservedWindowVocabularyTests
{
    private static readonly string[] Names =
        ["Qwen", "Qwen3 - Research", "Router notes", "Core designs", "Tool atlas", "router_notes.txt - Editor"];

    private static string Source(string name) => new JsonObject
    {
        ["kind"] = "operation",
        ["operation"] = "window.active",
        ["polarity"] = "success",
        ["verified"] = true,
        ["succeeded"] = true,
        ["observed"] = new JsonObject
        {
            ["count"] = 1,
            ["windows"] = new JsonArray(new JsonObject
            {
                ["title"] = name,
                ["processName"] = "Editor",
                ["foreground"] = true,
            }),
        },
    }.ToJsonString();

    [TestCaseSource(nameof(Names))]
    public async Task VerifiedNameSurvivesBothShellChecksWithoutRecovery(string name)
    {
        foreach ((string request, string reply) in new[]
        {
            ("Which window is active?", $"The window \"{name}\" is active."),
            ("¿Qué ventana tiene el foco?", $"La ventana \"{name}\" tiene foco."),
        })
        {
            var draft = new UserMessageDraft(Source(name), "status", null);
            int calls = 0;
            ModelMessageCompositionOutcome outcome = await ModelMessageComposer.ComposeAsync(
                draft, request, ModelMessageComposer.CreateFacts(draft), (_, _, _, _, _) =>
                {
                    calls++;
                    return Task.FromResult<MindComposedMessage?>(new(reply));
                }, false, true, CancellationToken.None);
            Assert.That(outcome.Text, Is.EqualTo(reply));
            Assert.That(calls, Is.EqualTo(1));
        }
    }

    [TestCaseSource(nameof(Names))]
    public void ExemptionDoesNotEscapeTheExactName(string name)
    {
        var draft = new UserMessageDraft(Source(name), "status", null);
        string reply = $"The window \"{name}\" is active.";
        foreach (string suffix in new[] { " The router chose it.", " The core confirmed it.", " window.active." })
        {
            Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply + suffix, draft,
                "Which window is active?"), Is.Not.Null);
        }
    }

    [TestCase("verified", "false")]
    [TestCase("succeeded", "false")]
    [TestCase("polarity", "\"failure\"")]
    [TestCase("operation", "\"system.status\"")]
    public void ObservationMustRetainItsSuccessfulWindowProvenance(string key, string value)
    {
        JsonObject source = JsonNode.Parse(Source("Router notes"))!.AsObject();
        source[key] = JsonNode.Parse(value);
        var draft = new UserMessageDraft(source.ToJsonString(), "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(
            "The window \"Router notes\" is active.", draft, "Which window is active?"),
            Is.EqualTo("unsafe_language"));
    }

    [Test]
    public void DifferentNameAndUnobservedRootTitleAreNotExemptions()
    {
        foreach (string source in new[] { Source("Router plans"), """{"kind":"operation","title":"Router notes","verified":true,"succeeded":true} """ })
        {
            var draft = new UserMessageDraft(source, "status", null);
            Assert.That(UserMessagePolicy.ModelResponseRejectionReason(
                "The window \"Router notes\" is active.", draft, "Which window is active?"),
                Is.EqualTo("unsafe_language"));
        }
    }

    [Test]
    public void SuccessfulMissionStepRetainsItsLiteralProvenance()
    {
        var draft = new UserMessageDraft(MissionNarration.CreateCompletionMessage([Source("Router notes")]), "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(
            "The window \"Router notes\" is active.", draft, "Which window is active?"), Is.Null);
    }

    [TestCase("Router notesX")]
    [TestCase("XRouter notes")]
    public void PartialIdentityDoesNotExemptADifferentCompleteToken(string name)
    {
        var draft = new UserMessageDraft(Source("Router notes"), "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(
            $"The window \"{name}\" is active.", draft, "Which window is active?"),
            Is.EqualTo("unsafe_language"));
    }

    [Test]
    public void MaskingDoesNotChangeThePublicLengthLimit()
    {
        string name = "Router " + new string('a', 2200);
        var draft = new UserMessageDraft(Source(name), "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(
            $"The window \"{name}\" is active. \"{name}\".", draft, "Which window is active?"),
            Is.EqualTo("unsafe_language"));
    }

    [TestCase("Atlas", "Atlas.route")]
    [TestCase("Core", "Core.schema")]
    [TestCase("Core", "internal.Core")]
    [TestCase("Router notes", "Router notes-extra")]
    [TestCase("Router notes", "extra-Router notes")]
    [TestCase("Core", "Core_schema")]
    [TestCase("Core", "internal_Core")]
    public void KnownNameCannotHideALongerIdentifier(string name, string compound)
    {
        var draft = new UserMessageDraft(Source(name), "status", null);
        Assert.That(ObservedResponseLiterals.WithoutWindowNames(
            $"The window \"{name}\" is active. {compound}.", Source(name)),
            Is.EqualTo($"The window \"\uFFFC\" is active. {compound}."));
        // Exercise the existing lowercase code veto independently from the
        // uppercase compound-preservation assertion above.
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(
            $"The window \"{name}\" is active. {compound.ToLowerInvariant()}.", draft, "Which window is active?"),
            Is.Not.Null);
    }

    [TestCase(".")]
    [TestCase(",")]
    [TestCase(":")]
    [TestCase(";")]
    [TestCase("!")]
    [TestCase("?")]
    [TestCase(")")]
    [TestCase("\"")]
    public void SentencePunctuationDoesNotChangeAnObservedName(string punctuation)
    {
        Assert.That(ObservedResponseLiterals.WithoutWindowNames(
            $"Router notes{punctuation}", Source("Router notes")), Is.EqualTo($"\uFFFC{punctuation}"));
    }
}
