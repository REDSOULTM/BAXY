using System.IO;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The guard oracle of the decision benches (tests/Baxy.GuardOracle) answers a call as the App's guards would: refused
/// with the observation the model reads, or the call as it would run.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class GuardOracleTests
{
    private const string Draft = """{"call": "message.draft", "arguments": {"channel": "whatsapp", "recipient": "Pedro", "text": "Hola"}}""";

    [Test]
    public void AMessageByAChannelThePersonDidNotNameIsRefusedAsTheModelWouldReadIt()
    {
        var oracle = new GuardOracle.GuardOracle();

        string heard = oracle.Answer("""{"heard": "saluda a Pedro que está aquí", "answering": false}""");
        JsonNode answer = JsonNode.Parse(oracle.Answer(Draft))!;
        JsonNode refused = JsonNode.Parse((string)answer["refused"]!)!;

        Assert.Multiple(() =>
        {
            Assert.That(heard, Is.EqualTo("{}"));
            Assert.That((string?)refused["status"], Is.EqualTo("rejected"));
            Assert.That((string?)refused["error"], Is.EqualTo("channel_not_said"));
            Assert.That((string?)refused["next"], Does.StartWith("nothing ran"));
        });
    }

    [Test]
    public void AMessageByTheChannelThePersonNamedGoesAsWritten()
    {
        var oracle = new GuardOracle.GuardOracle();

        oracle.Answer("""{"heard": "mándale a Pedro por whatsapp que ya voy"}""");
        JsonNode answer = JsonNode.Parse(oracle.Answer(Draft))!;

        Assert.Multiple(() =>
        {
            Assert.That(answer["refused"], Is.Null);
            Assert.That((string?)answer["operation"], Is.EqualTo("message.draft"));
            Assert.That((string?)answer["arguments"]!["channel"], Is.EqualTo("whatsapp"));
            Assert.That(answer["note"], Is.Null);
        });
    }

    [Test]
    public void AGameTheyDidNotNameGoesHeldForTheirYesWithItsCause()
    {
        var oracle = new GuardOracle.GuardOracle();

        oracle.Answer("""{"heard": "pon algo para jugar"}""");
        JsonNode answer = JsonNode.Parse(oracle.Answer("""{"call": "game.launch", "arguments": {"title": "Rocket League"}}"""))!;

        Assert.Multiple(() =>
        {
            Assert.That((string?)answer["operation"], Is.EqualTo("game.launch"));
            Assert.That((string?)answer["held"], Is.EqualTo("game_title_not_said"));
        });
    }

    [Test]
    public void AResultComesBackAsTheModelReadsItAndACallThatGoesUnheldSaysSo()
    {
        var oracle = new GuardOracle.GuardOracle();

        oracle.Answer("""{"heard": "mándale a Pedro por whatsapp que ya voy"}""");
        JsonNode answer = JsonNode.Parse(oracle.Answer(Draft))!;
        JsonNode ran = JsonNode.Parse(oracle.Answer(
            """{"ran": "message.draft", "arguments": {}, "observation": "{\"status\":\"completed\"}"}"""))!;

        Assert.Multiple(() =>
        {
            Assert.That(answer["held"], Is.Null);
            Assert.That((string?)JsonNode.Parse((string)ran["observation"]!)!["status"], Is.EqualTo("completed"));
        });
    }

    [Test]
    public void AnOperationNoCatalogHasIsRefusedAsUnknown()
    {
        JsonNode answer = JsonNode.Parse(new GuardOracle.GuardOracle().Answer("""{"call": "nada.inventado", "arguments": {}}"""))!;

        Assert.That((string?)JsonNode.Parse((string)answer["refused"]!)!["error"], Is.EqualTo("unknown_operation"));
    }

    [Test]
    public void AWriteThatLeavesOutTheFolderNamedIsRefusedBySaidFolders()
    {
        string home = Path.Combine(Path.GetTempPath(), "baxy-oracle-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path.Combine(home, "banco-local"));
        try
        {
            var oracle = new GuardOracle.GuardOracle(label => label == "home" ? home : null);
            var heard = new JsonObject
            {
                ["heard"] = $@"guarda en {home}\banco-local un archivo recados.txt que diga: comprar pan",
            };
            oracle.Answer(heard.ToJsonString());

            JsonNode answer = JsonNode.Parse(oracle.Answer(
                """{"call": "file.write", "arguments": {"path": "recados.txt", "text": "comprar pan"}}"""))!;

            Assert.That((string?)JsonNode.Parse((string)answer["refused"]!)!["error"], Is.EqualTo("said_folder_left_out"));
        }
        finally
        {
            Directory.Delete(home, recursive: true);
        }
    }
}
