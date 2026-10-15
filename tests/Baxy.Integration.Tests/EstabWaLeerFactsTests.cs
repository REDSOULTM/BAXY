using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Encargo WA-LEER (war1-war3, wac1-wac3 imp-wa-leer on the notebook, compose_audit): the mission's facts carried the
/// first 20 of the chat's lines (every list of an observation is bounded at 20), the top of the window down to y≈0.32,
/// and «lo último que me escribió Abuela» was answered without the newest bubbles at the bottom. The lines a chat is read
/// from (observed.screen.chatLines) now travel whole within the App's 16 KiB operation message; every other list keeps
/// its bound. The geometry is that of the chat «Abuela» read on redpc (a bubble's text at x 0.8452, its time at 0.9205).
/// </summary>
[TestFixture]
public sealed class EstabWaLeerFactsTests
{
    private const string Mission = "mission.computer.use";

    [Test]
    public void AChatsLinesReachTheMindWholeAndInOrder()
    {
        // A tall window: past the 8 KiB every other observation has.
        JsonObject observation = Observation(Lines(150, "prueba BAXY imp"));
        string facts = OperationVisibleFacts.FromOutcome(Mission, Success(observation));
        JsonObject observed = ThroughTheApp(facts)["observed"]!.AsObject();
        JsonArray chatLines = observed["screen"]!["chatLines"]!.AsArray();
        Assert.Multiple(() =>
        {
            Assert.That(facts.Length, Is.GreaterThan(8_192));
            Assert.That(chatLines.Count, Is.EqualTo(150));
            Assert.That(JsonNode.DeepEquals(chatLines, observation["screen"]!["chatLines"]), Is.True);
            // Contracase: any other list of the same observation keeps the bound of 20.
            Assert.That(observed["screen"]!["lines"]!.AsArray().Count, Is.EqualTo(20));
            Assert.That(observed.ContainsKey("truncated"), Is.False);
        });
    }

    [Test]
    public void ContracaseAnObservationWithoutAChatKeepsItsBounds()
    {
        JsonObject observation = Observation(Lines(66, "prueba BAXY imp"));
        JsonNode lines = observation["screen"]!["chatLines"]!.DeepClone();
        observation["screen"]!.AsObject().Remove("chatLines");
        observation["screen"]!["rows"] = lines;
        string facts = OperationVisibleFacts.FromOutcome(Mission, Success(observation));
        Assert.Multiple(() =>
        {
            Assert.That(facts.Length, Is.LessThanOrEqualTo(8_192));
            Assert.That(JsonNode.Parse(facts)!["observed"]!["screen"]!["rows"]!.AsArray().Count, Is.EqualTo(20));
        });
    }

    [Test]
    public void AChatReadingOverTheBudgetIsProjectedAndStillParses()
    {
        JsonObject observation = Observation(Lines(OperationVisibleFacts.ChatLines, new string('a', 90)));
        JsonObject message = ThroughTheApp(OperationVisibleFacts.FromOutcome(Mission, Success(observation)));
        Assert.Multiple(() =>
        {
            Assert.That(message[OperationVisibleFacts.ObservedLimitKey]!.GetValue<string>(), Is.EqualTo("projected"));
            Assert.That(message["observed"]!["truncated"]!.GetValue<bool>(), Is.True);
        });
    }

    private static JsonObject Observation(JsonArray chatLines) => new()
    {
        ["goal"] = "ir a abuela; y responder: leé lo último que me escribió Abuela",
        ["application"] = "WhatsApp",
        ["reached"] = true,
        ["satisfiedBy"] = "page:abuela",
        ["screen"] = new JsonObject
        {
            ["title"] = "(1) WhatsApp",
            ["lines"] = new JsonArray([.. Enumerable.Range(0, 25).Select(index => (JsonNode?)JsonValue.Create($"línea {index}"))]),
            ["chatLines"] = chatLines,
        },
    };

    private static JsonArray Lines(int count, string text) =>
        new([.. Enumerable.Range(0, count).Select(index => (JsonNode?)new JsonObject
        {
            ["text"] = index % 2 == 0 ? text : $"{index / 60}:{index % 60:00}",
            ["x"] = index % 2 == 0 ? 0.8452 : 0.9205,
            ["y"] = Math.Round(0.1 + index * 0.0125, 4),
            ["w"] = 0.0712,
            ["h"] = 0.0164,
        })]);

    private static OperationOutcome Success(JsonObject observation)
    {
        using JsonDocument document = JsonDocument.Parse(observation.ToJsonString());
        return OperationOutcome.Success(document.RootElement.Clone());
    }

    private static JsonObject ThroughTheApp(string facts)
    {
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"), Guid.NewGuid().ToString("D"),
            OperationStatuses.Completed, facts, true, false, null, null);
        string message = OperationResponseProjection.Create(response, Mission).Message;
        Assert.That(message, Is.EqualTo(facts));
        return JsonNode.Parse(message)!.AsObject();
    }
}
