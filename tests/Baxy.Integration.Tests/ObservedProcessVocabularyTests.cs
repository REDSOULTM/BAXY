using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class ObservedProcessVocabularyTests
{
    private static string Source(string name = "baxy-core") => new JsonObject
    {
        ["kind"] = "operation",
        ["operation"] = "system.process.list",
        ["polarity"] = "success",
        ["verified"] = true,
        ["succeeded"] = true,
        ["observed"] = new JsonObject
        {
            ["sort"] = "cpu",
            ["observedProcessCount"] = 20,
            ["returnedProcessCount"] = 1,
            ["observationScope"] = "accessible_processes",
            ["processes"] = new JsonArray(new JsonObject
            {
                ["processId"] = 731,
                ["name"] = name,
                ["cpuUsagePercent"] = 4.5,
                ["sampleDurationSeconds"] = 0.2,
            }),
        },
    }.ToJsonString();

    [TestCase("baxy-core")]
    [TestCase("gpu_router")]
    [TestCase("Qwen Worker")]
    public async Task VerifiedProcessNameSurvivesShellChecksInOneCall(string name)
    {
        foreach ((string question, string answer) in new[]
        {
            ("¿Qué proceso usa más CPU?", $"El proceso {name} usa el 4,5 % de CPU."),
            ("Which process uses the most CPU?", $"The process {name} uses 4.5% CPU."),
        })
        {
            var draft = new UserMessageDraft(Source(name), "status", null);
            int calls = 0;
            ModelMessageCompositionOutcome outcome = await ModelMessageComposer.ComposeAsync(
                draft, question, ModelMessageComposer.CreateFacts(draft), (_, _, _, _, _) =>
                {
                    calls++;
                    return Task.FromResult<MindComposedMessage?>(new(answer));
                }, false, true, CancellationToken.None);
            Assert.That(outcome.Text, Is.EqualTo(answer));
            Assert.That(calls, Is.EqualTo(1));
        }
    }

    [TestCase(" The core chose it.")]
    [TestCase(" The router confirmed it.")]
    [TestCase(" system.process.list.")]
    [TestCase(" baxy-core.worker.")]
    [TestCase(" internal.baxy-core.")]
    [TestCase(" baxy-core_extra.")]
    public void ExemptionDoesNotEscapeTheObservedName(string suffix)
    {
        var draft = new UserMessageDraft(Source(), "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(
            "The process baxy-core uses 4.5% CPU." + suffix, draft,
            "Which process uses the most CPU?"), Is.Not.Null);
    }

    [TestCase("verified", "false")]
    [TestCase("succeeded", "false")]
    [TestCase("polarity", "\"failure\"")]
    [TestCase("operation", "\"system.status\"")]
    public void ProcessNameRequiresSuccessfulVerifiedProvenance(string field, string value)
    {
        JsonObject source = JsonNode.Parse(Source())!.AsObject();
        source[field] = JsonNode.Parse(value);
        var draft = new UserMessageDraft(source.ToJsonString(), "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(
            "The process baxy-core uses 4.5% CPU.", draft,
            "Which process uses the most CPU?"), Is.EqualTo("unsafe_language"));
    }

    [Test]
    public void MissionStepKeepsItsOwnProcessProvenance()
    {
        var draft = new UserMessageDraft(MissionNarration.CreateCompletionMessage([Source()]), "status", null);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(
            "The process baxy-core uses 4.5% CPU.", draft,
            "Which process uses the most CPU?"), Is.Null);
    }
}
