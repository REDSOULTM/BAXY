using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class C03OcrObservationProjectionTests
{
    [TestCase("capture.screenshot")]
    [TestCase("capture.active.window")]
    public void CaptureSourceDigestAndWindowIdentityReachTheOcrEvidenceChain(string operation)
    {
        var source = new JsonObject
        {
            ["captureId"] = "capture_source",
            ["sha256"] = new string('a', 64),
            ["createdAtUtc"] = "2026-09-11T10:00:00Z",
            ["activeWindow"] = new JsonObject
            {
                ["windowHandle"] = 123,
                ["processId"] = 456,
                ["processCreatedAtUtc"] = "2026-09-11T09:00:00Z",
                ["captureBounds"] = new JsonObject { ["left"] = 12, ["width"] = 900 },
            },
        };
        JsonNode observed = JsonNode.Parse(Project(operation, source))!["observed"]!;
        Assert.That(JsonNode.DeepEquals(observed, source), Is.True);
    }

    [TestCase(2, 40, 160)]
    [TestCase(24, 2, 250)]
    public void DenseOcrSurvivesKernelAndAppWithoutLosingWordsRowsGeometryOrIdentity(
        int lineCount, int wordsPerLine, int wordLength)
    {
        JsonObject observation = Observation(lineCount, wordsPerLine, wordLength);
        string raw = observation.ToJsonString();
        Assert.That(raw.Length, Is.GreaterThan(16_384).And.LessThan(48_000));

        string message = Project("ocr.read", observation);
        JsonObject observed = JsonNode.Parse(message)!["observed"]!.AsObject();

        Assert.Multiple(() =>
        {
            Assert.That(message.Length, Is.GreaterThan(16_384).And.LessThanOrEqualTo(48_000));
            Assert.That(JsonNode.DeepEquals(observed["layout"], observation["layout"]), Is.True);
            Assert.That(JsonNode.DeepEquals(observed["activeWindow"], observation["activeWindow"]), Is.True);
            Assert.That(observed["sha256"]!.GetValue<string>(), Is.EqualTo(new string('a', 64)));
            Assert.That(observed["imageSha256"]!.GetValue<string>(), Is.EqualTo(new string('b', 64)));
            Assert.That(observed["recognizedAtUtc"]!.GetValue<string>(), Is.EqualTo("2026-09-11T10:00:00Z"));
            Assert.That(observed["imageWidth"]!.GetValue<int>(), Is.EqualTo(1920));
            Assert.That(observed["imageHeight"]!.GetValue<int>(), Is.EqualTo(1080));
            Assert.That(observed.ContainsKey("token"), Is.False);
        });
    }

    [Test]
    public void EscapedUnicodeDoesNotDiscardLayoutThatFitsTheSerializedMessage()
    {
        JsonObject observation = Observation(10, 25, 1);
        JsonArray lines = observation["layout"]!["lines"]!.AsArray();
        foreach (JsonNode? line in lines)
        {
            JsonArray words = line!["words"]!.AsArray();
            foreach (JsonNode? word in words) word!["text"] = "áéíóúÁÉÍÓÚñÑ";
            line["text"] = string.Join(" ", words.Select(word => word!["text"]!.GetValue<string>()));
        }
        observation["text"] = string.Join("\n", lines.Select(line => line!["text"]!.GetValue<string>()));
        var options = new JsonSerializerOptions { Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping };
        Assert.That(observation.ToJsonString().Length, Is.GreaterThan(48_000));
        Assert.That(observation.ToJsonString(options).Length, Is.LessThan(47_000));

        string message = Project("ocr.read", observation);
        JsonNode observed = JsonNode.Parse(message)!["observed"]!;
        Assert.Multiple(() =>
        {
            Assert.That(message.Length, Is.LessThanOrEqualTo(48_000));
            Assert.That(JsonNode.DeepEquals(observed["layout"], observation["layout"]), Is.True);
            Assert.That(observed["text"]!.GetValue<string>(), Is.EqualTo(observation["text"]!.GetValue<string>()));
        });
    }

    [Test]
    public void OversizedLayoutIsExplicitlyUnavailableWhileExistingTextAndFactsSurvive()
    {
        JsonObject observation = Observation(10, 80, 100);
        Assert.That(observation.ToJsonString().Length, Is.GreaterThan(48_000));

        string message = Project("ocr.read", observation);
        JsonNode observed = JsonNode.Parse(message)!["observed"]!;

        Assert.Multiple(() =>
        {
            Assert.That(message.Length, Is.LessThanOrEqualTo(48_000));
            Assert.That(observed["text"]!.GetValue<string>(), Is.EqualTo(observation["text"]!.GetValue<string>()));
            Assert.That(observed["lineCount"]!.GetValue<int>(), Is.EqualTo(10));
            Assert.That(observed["imageSha256"]!.GetValue<string>(), Is.EqualTo(new string('b', 64)));
            Assert.That(observed["layout"]!["available"]!.GetValue<bool>(), Is.False);
            Assert.That(observed["layout"]!["reason"]!.GetValue<string>(), Is.EqualTo("observation_size_limit"));
            Assert.That(observed["layout"]!.AsObject().ContainsKey("lines"), Is.False);
        });
    }

    [Test]
    public void EnvelopeBudgetAlsoOmitsWholeLayoutWithoutCuttingJson()
    {
        JsonObject observation = Observation(1, 1, 1);
        int padding = 47_970 - observation.ToJsonString().Length;
        observation["layout"]!["padding"] = new string('x', padding);
        Assert.That(observation.ToJsonString().Length, Is.InRange(47_970, 48_000));

        string message = Project("ocr.read", observation);
        JsonNode observed = JsonNode.Parse(message)!["observed"]!;

        Assert.That(observed["text"]!.GetValue<string>(), Is.EqualTo(observation["text"]!.GetValue<string>()));
        Assert.That(observed["layout"]!["available"]!.GetValue<bool>(), Is.False);
    }

    [Test]
    public void OversizedTextIsOmittedExplicitlyWithoutInventingOrTruncatingContent()
    {
        JsonObject observation = Observation(1, 1, 1);
        observation["text"] = new string('x', 49_000);

        JsonNode observed = JsonNode.Parse(Project("ocr.read", observation))!["observed"]!;

        Assert.That(observed["available"]!.GetValue<bool>(), Is.False);
        Assert.That(observed["reason"]!.GetValue<string>(), Is.EqualTo("observation_size_limit"));
        Assert.That(observed.AsObject().ContainsKey("text"), Is.False);
    }

    [TestCase(OperationStatuses.Completed, true, "success")]
    [TestCase(OperationStatuses.Failed, false, "failure")]
    [TestCase(OperationStatuses.Pending, false, "pending")]
    public void AppOversizedOcrMessagePreservesOutcomeAndExplicitlyOmitsObservation(
        string status, bool verified, string polarity)
    {
        string message = new JsonObject { ["observed"] = Observation(10, 80, 100) }.ToJsonString();
        using JsonDocument projected = JsonDocument.Parse(
            OperationResponseProjection.Create(Response(message) with
            {
                Status = status,
                Verified = verified,
            }, "ocr.read").Message);
        Assert.Multiple(() =>
        {
            Assert.That(projected.RootElement.GetProperty("status").GetString(), Is.EqualTo(status));
            Assert.That(projected.RootElement.GetProperty("verified").GetBoolean(), Is.EqualTo(verified));
            Assert.That(projected.RootElement.GetProperty("polarity").GetString(), Is.EqualTo(polarity));
            Assert.That(projected.RootElement.GetProperty("succeeded").GetBoolean(),
                Is.EqualTo(status == OperationStatuses.Completed));
            Assert.That(projected.RootElement.GetProperty("error").ValueKind, Is.EqualTo(JsonValueKind.Null));
            Assert.That(projected.RootElement.GetProperty("observed").GetProperty("available").GetBoolean(), Is.False);
            Assert.That(projected.RootElement.GetProperty("observed").GetProperty("reason").GetString(),
                Is.EqualTo("observation_size_limit"));
        });
    }

    [TestCase("note.list", 20, false)]
    [TestCase("system.process.list", 50, true)]
    public void OtherOperationsRetainTheirArrayDepthAndIdentitySanitization(
        string operation, int expectedRows, bool keepsProcessId)
    {
        var rows = new JsonArray();
        for (int index = 0; index < 55; index++) rows.Add(index);
        var observation = new JsonObject
        {
            ["rows"] = rows,
            ["processId"] = 123,
            ["sha256"] = "private_hash",
            ["nested"] = new JsonObject
            {
                ["a"] = new JsonObject
                {
                    ["b"] = new JsonObject
                    {
                        ["c"] = new JsonObject { ["tooDeep"] = "not projected" },
                    }
                }
            },
        };

        JsonObject observed = JsonNode.Parse(Project(operation, observation))!["observed"]!.AsObject();
        Assert.Multiple(() =>
        {
            Assert.That(observed["rows"]!.AsArray(), Has.Count.EqualTo(expectedRows));
            Assert.That(observed.ContainsKey("processId"), Is.EqualTo(keepsProcessId));
            Assert.That(observed.ContainsKey("sha256"), Is.False);
            Assert.That(observed["nested"]!["a"]!["b"]!["c"]!.AsObject(), Is.Empty);
        });
    }

    // SHELL2075 «ejecutá dir en el escritorio»: a bounded console result (8 KiB of
    // output and sixty lines) crosses 16 KiB of JSON; cutting it left the mind
    // without «seen» and the final said nothing of what came out.
    [Test]
    public void ABoundedShellResultKeepsItsObservationWhole()
    {
        var lines = new JsonArray();
        var text = new System.Text.StringBuilder();
        for (int line = 0; line < 60; line++)
        {
            string row = $"{line:D2}/09/2026  10:43         1.234.567 archivo-de-prueba-{line:D2}-con-un-nombre-deliberadamente-largo-como-los-que-deja-una-carpeta-de-trabajo-real.txt";
            lines.Add(row);
            text.Append(row).Append('\n');
        }
        var observation = new JsonObject
        {
            ["version"] = 1,
            ["command"] = "dir",
            ["cwd"] = "D:/Perfil/Escritorio",
            ["exitCode"] = 0,
            ["succeeded"] = true,
            ["stdout"] = text.ToString(),
            ["stderr"] = string.Empty,
            ["lineCount"] = lines.Count,
            ["lines"] = lines,
            ["truncated"] = false,
            ["authority"] = "shell_process_exit_and_captured_output",
        };

        string projected = Project("shell.command.run", observation);

        // Past the 8 KiB observed ceiling the facts used to arrive without «observed» at all.
        Assert.That(projected.Length, Is.GreaterThan(8_192), "the case only bites past the generic observed ceiling");
        using JsonDocument document = JsonDocument.Parse(projected);
        Assert.Multiple(() =>
        {
            Assert.That(document.RootElement.TryGetProperty("observed", out JsonElement observed), Is.True);
            // The generic array cap keeps twenty rows, well above the five the reply quotes.
            Assert.That(document.RootElement.GetProperty("observed").GetProperty("lines").GetArrayLength(), Is.GreaterThanOrEqualTo(5));
            Assert.That(document.RootElement.GetProperty("observed").GetProperty("lineCount").GetInt32(), Is.EqualTo(60));
            Assert.That(document.RootElement.GetProperty("observed").GetProperty("exitCode").GetInt32(), Is.EqualTo(0));
        });
    }

    private static string Project(string operation, JsonObject observation)
    {
        using JsonDocument document = JsonDocument.Parse(observation.ToJsonString());
        string facts = OperationVisibleFacts.FromOutcome(operation, OperationOutcome.Success(document.RootElement.Clone()));
        OperationResponse response = Response(facts) with { Result = document.RootElement.Clone() };
        byte[] wire = ProtocolJson.SerializeBoundedToUtf8Bytes(response, 1024 * 1024);
        OperationResponse restored = ProtocolJson.DeserializeResponse(wire);
        Assert.That(restored.Message, Is.EqualTo(facts));
        Assert.That(JsonElement.DeepEquals(restored.Result!.Value, document.RootElement), Is.True);
        return OperationResponseProjection.Create(restored, operation).Message;
    }

    private static OperationResponse Response(string message) => new(
        ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"), Guid.NewGuid().ToString("D"),
        OperationStatuses.Completed, message, true, false, null, null);

    private static JsonObject Observation(int lineCount, int wordsPerLine, int wordLength)
    {
        var lines = new JsonArray();
        for (int line = 0; line < lineCount; line++)
        {
            var words = new JsonArray();
            for (int word = 0; word < wordsPerLine; word++)
            {
                words.Add(new JsonObject
                {
                    ["text"] = new string('x', wordLength) + word,
                    ["boundingRect"] = new JsonObject
                    {
                        ["x"] = word * 11.5,
                        ["y"] = line * 15.5,
                        ["width"] = 10.5,
                        ["height"] = 14.5,
                    },
                });
            }
            lines.Add(new JsonObject { ["text"] = "Observed line " + line, ["words"] = words });
        }
        return new JsonObject
        {
            ["text"] = "Existing observed text remains available.",
            ["lineCount"] = lineCount,
            ["sha256"] = new string('a', 64),
            ["imageSha256"] = new string('b', 64),
            ["imageWidth"] = 1920,
            ["imageHeight"] = 1080,
            ["recognizedAtUtc"] = "2026-09-11T10:00:00Z",
            ["activeWindow"] = new JsonObject
            {
                ["windowHandle"] = 123,
                ["processId"] = 456,
                ["processCreatedAtUtc"] = "2026-09-11T09:00:00Z",
            },
            ["layout"] = new JsonObject { ["available"] = true, ["lines"] = lines },
            ["token"] = "must still be removed",
        };
    }
}
