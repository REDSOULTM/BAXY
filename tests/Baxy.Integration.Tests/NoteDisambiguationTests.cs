using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Core.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed partial class NoteDisambiguationTests
{
    [TestCase("1", 1)]
    [TestCase("la opción 2", 2)]
    [TestCase("choose la 3", 3)]
    [TestCase("I choose 4", 4)]
    [TestCase("la primera", 1)]
    [TestCase("elige the second", 2)]
    [TestCase("the third one", 3)]
    [TestCase("el primero", 1)]
    [TestCase("elige el tercero", 3)]
    public void ContextualParserAcceptsAnchoredSpanishEnglishAndSpanglishSelections(
        string text,
        int expectedNumber)
    {
        NoteChoiceReply reply = NoteChoiceReplyParser.Parse(text);

        Assert.Multiple(() =>
        {
            Assert.That(reply.Kind, Is.EqualTo(NoteChoiceReplyKind.Select));
            Assert.That(reply.Number, Is.EqualTo(expectedNumber));
        });
    }

    [TestCase("0")]
    [TestCase("513")]
    [TestCase("1 o 2")]
    [TestCase("1 and 2")]
    [TestCase("-1")]
    [TestCase("1.5")]
    [TestCase("1 y bórrala")]
    [TestCase("both")]
    [TestCase("¿Quién eres?")]
    [TestCase("Who are you?")]
    public void ContextualParserRejectsBulkOrMalformedSelections(string text)
    {
        Assert.That(
            NoteChoiceReplyParser.Parse(text).Kind,
            Is.EqualTo(NoteChoiceReplyKind.Invalid));
    }

    [Test]
    public void BareNumberNeverBecomesANaturalOperationWithoutChoiceContext()
    {
        Assert.That(NaturalNoteRequestParser.TryParse("2", out RoutedOperation? routed), Is.False);
        Assert.That(routed, Is.Null);
    }

    [Test]
    public void ContextualParserRejectsInvalidUtf16WithoutThrowing()
    {
        Assert.That(
            NoteChoiceReplyParser.Parse("1\uD800").Kind,
            Is.EqualTo(NoteChoiceReplyKind.Invalid));
    }

    [Test]
    public void PromptPagesCandidatesWithoutExposingIdentifiersOrJson()
    {
        (OperationResponse response, RoutedOperation routed, Guid[] ids) = CreateAmbiguity(7);

        bool parsed = PendingNoteChoice.TryCreate(response, routed, out PendingNoteChoice? choice);
        Assert.That(parsed, Is.True);
        Assert.That(choice, Is.Not.Null);
        string firstPage = choice!.CreatePrompt();

        Assert.Multiple(() =>
        {
            Assert.That(firstPage.TrimStart(), Does.StartWith("{"));
            Assert.That(firstPage, Does.Contain("\"n\":1"));
            Assert.That(firstPage, Does.Contain("\"n\":5"));
            Assert.That(firstPage, Does.Not.Contain("\"n\":6"));
            Assert.That(firstPage, Does.Contain("\"hasNext\":true"));
            Assert.That(firstPage, Does.Not.Contain("Encontré"));
            Assert.That(ids.All(id => !firstPage.Contains(id.ToString("D"), StringComparison.Ordinal)), Is.True);
        });

        Assert.That(choice.MoveNext(), Is.True);
        string secondPage = choice.CreatePrompt();
        Assert.Multiple(() =>
        {
            Assert.That(secondPage, Does.Contain("\"n\":6"));
            Assert.That(secondPage, Does.Contain("\"n\":7"));
            Assert.That(secondPage, Does.Contain("\"trashed\":true"));
            Assert.That(secondPage, Does.Contain("\"hasPrevious\":true"));
            Assert.That(choice.TrySelect(1, out _), Is.False);
            Assert.That(choice.TrySelect(6, out NoteChoiceCandidate? selected), Is.True);
            Assert.That(selected?.NoteId, Is.EqualTo(ids[5]));
        });
    }

    [Test]
    public void PaginationReachesAndSelectsTheFiveHundredTwelfthCandidate()
    {
        (OperationResponse response, RoutedOperation routed, Guid[] ids) =
            CreateAmbiguity(PendingNoteChoice.MaximumCandidates);
        Assert.That(PendingNoteChoice.TryCreate(response, routed, out PendingNoteChoice? choice), Is.True);

        int pageMoves = 0;
        while (choice!.MoveNext())
        {
            pageMoves++;
        }

        string lastPage = choice.CreatePrompt();
        Assert.Multiple(() =>
        {
            Assert.That(pageMoves, Is.EqualTo(102));
            Assert.That(choice.FirstVisibleNumber, Is.EqualTo(511));
            Assert.That(choice.LastVisibleNumber, Is.EqualTo(512));
            Assert.That(choice.TrySelect(512, out NoteChoiceCandidate? selected), Is.True);
            Assert.That(selected?.NoteId, Is.EqualTo(ids[511]));
            Assert.That(lastPage, Does.Contain("\"n\":512"));
            Assert.That(UuidLikeText().IsMatch(lastPage), Is.False);
        });
    }

    [Test]
    public void MalformedOrReorderedAmbiguityFailsClosed()
    {
        (OperationResponse valid, RoutedOperation routed, _) = CreateAmbiguity(2);
        JsonObject result = JsonNode.Parse(valid.Result!.Value.GetRawText())!.AsObject();
        JsonArray candidates = result["candidates"]!.AsArray();
        candidates[1]!["updatedAtUtc"] = candidates[0]!["updatedAtUtc"]!.GetValue<string>();
        candidates[1]!["noteId"] = "00000000-0000-0000-0000-000000000001";
        candidates[0]!["noteId"] = "ffffffff-ffff-ffff-ffff-ffffffffffff";
        OperationResponse reordered = valid with { Result = Serialize(result) };

        Assert.That(
            PendingNoteChoice.TryCreate(reordered, routed, out PendingNoteChoice? choice),
            Is.False);
        Assert.That(choice, Is.Null);
    }

    [Test]
    public void SelectedSnapshotIsPersistedAndRecoveredWithoutReinterpretingOrdinal()
    {
        string root = Path.Combine(
            Path.GetTempPath(),
            "baxy-note-choice-tests",
            Guid.NewGuid().ToString("N"));
        string outbox = Path.Combine(root, "shell", "retry-outbox.v1.json");
        try
        {
            (OperationResponse response, RoutedOperation original, Guid[] ids) = CreateAmbiguity(2);
            Assert.That(PendingNoteChoice.TryCreate(response, original, out PendingNoteChoice? choice), Is.True);
            Assert.That(choice!.TrySelect(2, out NoteChoiceCandidate? selected), Is.True);
            RoutedOperation selectedRoute = choice.CreateSelectedRoute(selected!);
            var firstRegistry = new RetryableOperationRegistry(outbox);
            PreparedOperation first = firstRegistry.GetOrAdd(selectedRoute);

            var restartedRegistry = new RetryableOperationRegistry(outbox);
            PreparedOperation recovered = restartedRegistry.SnapshotPendingOperations().Single();
            bool recoveredChoice = PendingSelectedNote.TryCreate(
                recovered,
                selectedNumber: null,
                out PendingSelectedNote? pending);

            Assert.Multiple(() =>
            {
                Assert.That(recoveredChoice, Is.True);
                Assert.That(pending, Is.Not.Null);
                Assert.That(recovered.InvocationId, Is.EqualTo(first.InvocationId));
                Assert.That(recovered.MissionId, Is.EqualTo(first.MissionId));
                Assert.That(
                    recovered.Arguments.GetProperty("noteId").GetString(),
                    Is.EqualTo(ids[1].ToString("D")));
                Assert.That(pending!.CreateRecoveryPrompt(), Does.Not.Contain(ids[1].ToString("D")));
                Assert.That(pending.CreateRecoveryPrompt(), Does.Contain("no volveré a interpretar el número"));
            });
        }
        finally
        {
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    [Test]
    public void MaximumAdversarialAmbiguityFitsTheIpcAndJournalBudgets()
    {
        DateTimeOffset timestamp = new(2026, 7, 15, 12, 0, 0, TimeSpan.Zero);
        NoteAmbiguityCandidateResult[] candidates = Enumerable
            .Range(0, PendingNoteChoice.MaximumCandidates)
            .Select(index => new NoteAmbiguityCandidateResult(
                Guid.NewGuid().ToString("D"),
                new string('<', 128),
                timestamp,
                timestamp,
                index + 1L,
                index % 2 == 0))
            .ToArray();
        JsonElement result = JsonSerializer.SerializeToElement(
            new NoteAmbiguityResult(candidates),
            CoreJsonContext.Default.NoteAmbiguityResult);
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            OperationStatuses.Failed,
            "Encontré duplicados; no hice cambios.",
            false,
            false,
            result,
            "note_ambiguous");

        byte[] wire = ProtocolJson.SerializeToUtf8Bytes(response);

        Assert.Multiple(() =>
        {
            Assert.That(wire.Length, Is.LessThan(CoreProcessClient.MaximumProtocolLineLength));
            Assert.That(
                wire.Length,
                Is.LessThan(700_000),
                "El margen también debe caber holgadamente en la reserva de completion de 2 MiB.");
        });
    }

    private static (OperationResponse Response, RoutedOperation Routed, Guid[] Ids) CreateAmbiguity(
        int count)
    {
        DateTimeOffset latest = new(2026, 7, 15, 12, 0, 0, TimeSpan.Zero);
        var candidates = new JsonArray();
        var ids = new Guid[count];
        for (int index = 0; index < count; index++)
        {
            ids[index] = Guid.Parse($"00000000-0000-0000-0000-{index + 1:000000000000}");
            DateTimeOffset timestamp = latest.AddMinutes(-index);
            candidates.Add(new JsonObject
            {
                ["noteId"] = ids[index].ToString("D"),
                ["contentPreview"] = $"contenido {index + 1}",
                ["createdAtUtc"] = timestamp.AddDays(-1),
                ["updatedAtUtc"] = timestamp,
                ["revision"] = index + 1,
                ["isTrashed"] = index % 2 == 1,
            });
        }

        var result = new JsonObject { ["candidates"] = candidates };
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            OperationStatuses.Failed,
            "Encontré duplicados; no hice cambios.",
            false,
            false,
            Serialize(result),
            "note_ambiguous");
        var routed = new RoutedOperation(
            "note.trash",
            new JsonObject { ["title"] = "Compras" });
        return (response, routed, ids);
    }

    private static JsonElement Serialize(JsonNode node) =>
        JsonSerializer.SerializeToElement(node).Clone();

    [GeneratedRegex(
        "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex UuidLikeText();
}
