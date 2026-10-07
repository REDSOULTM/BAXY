using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Live 2026-10-07 (cu-universal v2 bench, cu-r8): when the mind returned no final for a computer-use mission, the App's
/// floor said «Lo hice en la aplicación «Reloj»; hay 2: «Reloj mundial».» or «No pude hacerlo en la aplicación
/// «Configuración».». It now says what the mind's floor says, from the same data (operation_floor.v1.json
/// «computerUse»): the place reached, or what was not reached and the typed cause. The fixture
/// (tests/data/cu_floor_twins.json) is written by the mind and read back by tests/test_cu_r8_voz_final.py too.
/// </summary>
[TestFixture]
public sealed class ComputerUseFloorTests
{
    private static IEnumerable<TestCaseData> TwinCases()
    {
        var fixture = (JsonObject)JsonNode.Parse(File.ReadAllText(Path.Combine(
            FindRepositoryRoot(), "tests", "data", "cu_floor_twins.json")))!;
        foreach (JsonNode? row in (JsonArray)fixture["cases"]!)
        {
            string id = (string)row!["id"]!;
            yield return new TestCaseData(row["situation"]!.ToJsonString(), false, (string)row["es"]!)
                .SetName($"ComputerUseTwin({id},es)");
            yield return new TestCaseData(row["situation"]!.ToJsonString(), true, (string)row["en"]!)
                .SetName($"ComputerUseTwin({id},en)");
        }
    }

    [TestCaseSource(nameof(TwinCases))]
    public void TheAppSaysWhatTheMindSays(string situation, bool english, string expected)
    {
        var source = (JsonObject)JsonNode.Parse(situation)!;
        Assert.That(OperationFloor.Final(source, english), Is.EqualTo(expected));

        // And it is what the App publishes when the mind answered nothing.
        bool done = source["verified"] is JsonValue verified && verified.GetValue<bool>()
            && source["succeeded"] is JsonValue succeeded && succeeded.GetValue<bool>();
        var draft = new UserMessageDraft(situation, done || (string?)source["cause"] == "mission_completed"
            ? "status" : "error", null);
        string request = english ? "in the clock go to world clock" : "en el reloj andá a reloj mundial";
        Assert.That(
            ModelMessageComposer.DeterministicFinal(draft, request, ModelMessageComposer.CreateFacts(draft), string.Empty),
            Is.EqualTo(expected),
            () => $"refused: {UserMessagePolicy.ModelResponseRejectionReason(expected, draft, request)}");
    }

    [Test]
    public void AMissionWithAQuestionLeavesTheAnswerToTheMind()
    {
        var source = (JsonObject)JsonNode.Parse(
            """{"kind":"operation","operation":"mission.computer.use","polarity":"success","verified":true,"succeeded":true,"observed":{"goal":"ir a personalización; y responder: el modo es claro u oscuro","application":"Configuración","reached":true,"steps":[]}}""")!;
        Assert.That(OperationFloor.Final(source, english: false), Does.Not.StartWith("Listo, estoy en"));
    }

    private static string FindRepositoryRoot()
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Baxy.slnx")))
        {
            directory = directory.Parent;
        }

        return directory?.FullName ?? throw new DirectoryNotFoundException("Baxy.slnx was not found.");
    }
}
