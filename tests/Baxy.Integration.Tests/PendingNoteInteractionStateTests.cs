using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class PendingNoteInteractionStateTests
{
    [Test]
    public void ChoicePromotionDropsTheOldChoiceAndPreservesPreparedIdentity()
    {
        (PendingNoteChoice choice, PreparedOperation source) = CreateChoice();
        var state = new PendingNoteInteractionState();
        state.BeginChoice(choice, source);
        var awaiting = (PendingNoteInteraction.AwaitingChoice)state.Current!;
        PreparedOperation selectedPrepared = CreateSelectedOperation();
        var selected = new PendingSelectedNote(
            selectedPrepared,
            "Compras",
            1,
            false,
            2);

        state.PromoteToSelection(awaiting, selected);

        var current = (PendingNoteInteraction.ReconcilingSelection)state.Current!;
        Assert.Multiple(() =>
        {
            Assert.That(current.Pending, Is.SameAs(selected));
            Assert.That(current.Pending.Prepared, Is.SameAs(selectedPrepared));
            Assert.That(state.Current, Is.Not.TypeOf<PendingNoteInteraction.AwaitingChoice>());
        });
    }

    [Test]
    public void ResolvedSelectionClearsOnlyForTheExactPreparedInstance()
    {
        PreparedOperation prepared = CreateSelectedOperation();
        PreparedOperation equivalent = CreateSelectedOperation();
        var selected = new PendingSelectedNote(prepared, "Compras", 1, false, 1);
        var state = new PendingNoteInteractionState();
        state.RestoreSelection(selected);

        Assert.Multiple(() =>
        {
            Assert.That(equivalent.IdentityKey, Is.EqualTo(prepared.IdentityKey));
            Assert.That(state.TryClearResolved(equivalent), Is.False);
            Assert.That(state.Current, Is.TypeOf<PendingNoteInteraction.ReconcilingSelection>());
        });

        Assert.Multiple(() =>
        {
            Assert.That(state.TryClearResolved(prepared), Is.True);
            Assert.That(state.Current, Is.Null);
        });
    }

    [Test]
    public void ResolvedTitleClearsOnlyForTheExactPreparedInstance()
    {
        PreparedOperation prepared = PreparedOperation.Create(
            "note.read",
            new JsonObject { ["title"] = "Compras" });
        PreparedOperation equivalent = PreparedOperation.Create(
            "note.read",
            new JsonObject { ["title"] = "Compras" });
        var state = new PendingNoteInteractionState();
        state.RestoreTitle(new PendingTitleNote(prepared, "Compras"));

        Assert.Multiple(() =>
        {
            Assert.That(equivalent.IdentityKey, Is.EqualTo(prepared.IdentityKey));
            Assert.That(state.TryClearResolved(equivalent), Is.False);
            Assert.That(state.Current, Is.TypeOf<PendingNoteInteraction.ReconcilingTitle>());
        });

        Assert.Multiple(() =>
        {
            Assert.That(state.TryClearResolved(prepared), Is.True);
            Assert.That(state.Current, Is.Null);
        });
    }

    [Test]
    public void AmbiguityReplacesTitleReconciliationAsOneClosedState()
    {
        PreparedOperation titlePrepared = PreparedOperation.Create(
            "note.trash",
            new JsonObject { ["title"] = "Compras" });
        var title = new PendingTitleNote(titlePrepared, "Compras");
        (PendingNoteChoice choice, PreparedOperation source) = CreateChoice();
        var state = new PendingNoteInteractionState();
        state.RestoreTitle(title);

        state.BeginChoice(choice, source);

        var current = (PendingNoteInteraction.AwaitingChoice)state.Current!;
        Assert.Multiple(() =>
        {
            Assert.That(current.Choice, Is.SameAs(choice));
            Assert.That(current.Source, Is.SameAs(source));
            Assert.That(state.Current, Is.Not.TypeOf<PendingNoteInteraction.ReconcilingTitle>());
        });
    }

    private static (PendingNoteChoice Choice, PreparedOperation Source) CreateChoice()
    {
        var candidates = new JsonArray
        {
            CreateCandidate("00000000-0000-0000-0000-000000000001", 2),
            CreateCandidate("00000000-0000-0000-0000-000000000002", 1),
        };
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            OperationStatuses.Failed,
            "Encontré duplicados; no hice cambios.",
            false,
            false,
            System.Text.Json.JsonSerializer.SerializeToElement(
                new JsonObject { ["candidates"] = candidates }),
            "note_ambiguous");
        var routed = new RoutedOperation(
            "note.trash",
            new JsonObject { ["title"] = "Compras" });
        Assert.That(
            PendingNoteChoice.TryCreate(response, routed, out PendingNoteChoice? choice),
            Is.True);
        return (choice!, PreparedOperation.Create(routed.Name, routed.Arguments));
    }

    private static JsonObject CreateCandidate(string noteId, int minute) => new()
    {
        ["noteId"] = noteId,
        ["contentPreview"] = $"contenido {minute}",
        ["createdAtUtc"] = new DateTimeOffset(2026, 7, 15, 11, minute, 0, TimeSpan.Zero),
        ["updatedAtUtc"] = new DateTimeOffset(2026, 7, 15, 12, minute, 0, TimeSpan.Zero),
        ["revision"] = minute,
        ["isTrashed"] = false,
    };

    private static PreparedOperation CreateSelectedOperation() => PreparedOperation.Create(
        "note.trash",
        new JsonObject
        {
            ["noteId"] = "00000000-0000-0000-0000-000000000001",
            ["expectedTitle"] = "Compras",
            ["expectedRevision"] = 1,
            ["expectedIsTrashed"] = false,
        });
}
