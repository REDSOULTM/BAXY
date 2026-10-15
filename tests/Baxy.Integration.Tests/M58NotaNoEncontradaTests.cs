using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M58 (review of the official-window run v3d-final, F-p03-t1): «Actually, can you find the note called grocery?» read
/// the notes (one, «Llego tarde hoy») and the mind published «I cannot find a note called "grocery" in your active
/// notes; the only note visible is titled "Llego tarde hoy".». The shell rejected it as a reversed result and the turn
/// ended with no answer. That no listed note has the asked name is what the read found; a note the read lists is still
/// never denied.
/// </summary>
[TestFixture]
public sealed class M58NotaNoEncontradaTests
{
    private const string Asked = "Actually, can you find the note called grocery?";

    private static string NotesRead() => new JsonObject
    {
        ["kind"] = "operation",
        ["operation"] = "note.list",
        ["polarity"] = "success",
        ["verified"] = true,
        ["succeeded"] = true,
        ["observed"] = new JsonObject
        {
            ["notes"] = new JsonArray(new JsonObject
            {
                ["title"] = "«Llego tarde hoy»",
                ["createdAtUtc"] = "2026-09-29T02:11:32.5863282+00:00",
                ["updatedAtUtc"] = "2026-09-29T02:11:32.5863282+00:00",
                ["revision"] = 1,
                ["isTrashed"] = false,
            }),
            ["count"] = 1,
            ["totalCount"] = 1,
            ["scope"] = "active",
            ["limit"] = 50,
            ["offset"] = 0,
        },
    }.ToJsonString();

    [TestCase("I cannot find a note called \"grocery\" in your active notes; the only note visible is titled \"Llego tarde hoy\".")]
    [TestCase("I couldn't find a note named grocery; you have one note, \"Llego tarde hoy\".")]
    [TestCase("No encontré ninguna nota llamada «grocery»; la única que tienes es «Llego tarde hoy».")]
    public void ANoteTheReadDoesNotListIsSaidNotFound(string reply)
    {
        UserMessageDraft draft = UserMessagePolicy.Create(NotesRead(), UserMessageEvent.Status);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, Asked), Is.Null);
    }

    [TestCase("I cannot find a note called \"Llego tarde hoy\".")]
    [TestCase("I couldn't read your notes.")]
    public void ANoteTheReadListsOrTheReadItselfIsNeverDenied(string reply)
    {
        UserMessageDraft draft = UserMessagePolicy.Create(NotesRead(), UserMessageEvent.Status);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, Asked), Is.EqualTo("reversed_result"));
    }
}
