using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class C03NaturalContextPhraseTests
{
    private static UserMessageDraft ObservedProcesses() => new(new JsonObject
    {
        ["kind"] = "operation",
        ["operation"] = "system.process.list",
        ["polarity"] = "success",
        ["verified"] = true,
        ["succeeded"] = true,
        ["observed"] = new JsonObject
        {
            ["observedProcessCount"] = 20,
            ["returnedProcessCount"] = 1,
            ["observationScope"] = "accessible_processes",
            ["processes"] = new JsonArray(new JsonObject
            {
                ["processId"] = 731,
                ["name"] = "Editor",
            }),
        },
    }.ToJsonString(), "status", null);

    [TestCase("I observed 20 accessible processes in the current context; the total for the whole PC remains unknown.")]
    [TestCase("Within the current context, 20 accessible processes were observed. This observation does not establish a complete PC count.")]
    [TestCase("The count is 20 observed processes accessible in the CURRENT CONTEXT, with one entry returned; the whole PC total remains unknown.")]
    [TestCase("Observé 20 procesos accesibles en el current context; el total de todo el PC sigue sin determinarse.")]
    public void NaturalContextCanDescribeALimitedObservedCount(string reply)
    {
        // The observation is deliberately broader than the returned list and
        // does not establish completeness outside its accessible scope.
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(
            reply, ObservedProcesses(), "Count the running processes."), Is.Null);
    }

    [TestCase(" system.process.list.", "internal_code")]
    [TestCase(" request_failed.", "internal_code")]
    [TestCase(" <think>Choose a response.</think>", "internal_code")]
    [TestCase(" The previous draft was accepted.", "internal_code")]
    [TestCase(" status: success.", "internal_code")]
    [TestCase(" The core confirmed it.", "unsafe_language")]
    public void NaturalContextDoesNotPermitInternalCodesOrDetails(string suffix, string expectedReason)
    {
        const string reply = "I observed 20 accessible processes in the current context; the total for the whole PC remains unknown.";
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(
            reply + suffix, ObservedProcesses(), "Count the running processes."), Is.EqualTo(expectedReason));
    }
}
