using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M54: the shell lets through the finals the mind now writes for the independent review of v3b-final (the official
/// window run, development set): the output volume already at its maximum and muted (F-w02-t4, F-w11-t3), said
/// plainly with an offer to unmute, and the car parks OpenStreetMap returned near the asked street (F-p06-t3), told by
/// their streets instead of «no lo encontré».
/// </summary>
[TestFixture]
public sealed class M54LecturasVerificadasTests
{
    [TestCase("El volumen ya está al máximo, pero en silencio. ¿Lo activo?")]
    [TestCase("El volumen ya estaba al máximo, pero está silenciado. ¿Quieres que lo active?")]
    public void TheVolumeAlreadyAtItsMaximumAndMutedIsTheFailureSaid(string reply)
    {
        string step = TurnVisibleFacts.Failure("mission_failed", new JsonObject
        {
            ["stepCount"] = 0,
            ["steps"] = new JsonArray(),
            ["reason"] = new JsonObject
            {
                ["kind"] = "operation",
                ["operation"] = "audio.volume.adjust",
                ["polarity"] = "failure",
                ["verified"] = false,
                ["succeeded"] = false,
                ["error"] = "volume_already_at_maximum_muted",
            },
        });
        UserMessageDraft draft = UserMessagePolicy.Create(
            step, UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "súbele harto a la música"), Is.Null);
    }

    [TestCase("Encontré: Calle de Campoamor, Calle del Conde de Xiquena y Parking Escuelas Pías de San Antón (Calle de Santa Brígida).")]
    [TestCase("Hay aparcamiento en la calle de Campoamor y en la calle del Conde de Xiquena.")]
    public void ThePlacesReadNearTheAskedStreetAreTheAnswer(string reply)
    {
        string facts = new JsonObject
        {
            ["kind"] = "operation",
            ["operation"] = "web.search",
            ["polarity"] = "success",
            ["verified"] = true,
            ["succeeded"] = true,
            ["observed"] = new JsonObject
            {
                ["version"] = 1,
                ["query"] = "aparcamiento en la calle Génova en Madrid",
                ["count"] = 3,
                ["results"] = new JsonArray(
                    Place("parking", "https://www.openstreetmap.org/way/1550539478",
                        "Calle de Campoamor, Chueca, Justicia, Centro, Madrid, Comunidad de Madrid, 28004, España"),
                    Place("parking", "https://www.openstreetmap.org/way/1547417618",
                        "Calle del Conde de Xiquena, Chueca, Justicia, Centro, Madrid, Comunidad de Madrid, 28004, España"),
                    Place("Parking Escuelas Pías de San Antón", "https://www.openstreetmap.org/node/13167699221",
                        "Parking Escuelas Pías de San Antón, Calle de Santa Brígida, Chueca, Justicia, Centro, Madrid, "
                        + "Comunidad de Madrid, 28004, España")),
                ["authority"] = "openstreetmap_nominatim",
            },
        }.ToJsonString();
        UserMessageDraft draft = UserMessagePolicy.Create(facts, UserMessageEvent.Status);
        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "Mejor en calle Génova"), Is.Null);
    }

    private static JsonObject Place(string title, string url, string snippet) => new()
    {
        ["title"] = title,
        ["url"] = url,
        ["snippet"] = snippet,
    };
}
