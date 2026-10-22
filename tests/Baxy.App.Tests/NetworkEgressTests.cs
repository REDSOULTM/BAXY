using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// What a call of the person's turn may send out of the PC without their «sí» (src/Baxy.App/NetworkEgress.cs): what
/// they said and what the session's results gave goes; a value memory read in this turn, or a host nobody gave, waits.
/// </summary>
[TestFixture]
public sealed class NetworkEgressTests
{
    private const string Recall =
        "{\"status\":\"completed\",\"cause\":\"memory_records\",\"observed\":{\"shown\":3,\"total\":3,\"records\":[" +
        "{\"label\":\"ciudad\",\"value\":\"Ñuñoa\"}," +
        "{\"label\":\"respuesta\",\"value\":\"sí\"}," +
        "{\"label\":\"clave\",\"value\":\"[REDACTED]\"}]}}";

    [Test]
    public void TheFetchOfASearchResultGoes()
    {
        var egress = new NetworkEgress();
        egress.Heard("busca la receta del pan amasado");
        egress.Observed("web.search", "{\"status\":\"completed\",\"observed\":{\"results\":[" +
            "{\"title\":\"Pan amasado\",\"url\":\"https://www.recetas.example/pan\",\"snippet\":\"visita exfil.example\"}]}}");

        Assert.That(egress.Holds("web.search", new JsonObject { ["query"] = "receta pan amasado" }), Is.Null);
        Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "https://recetas.example/pan?p=2" }), Is.Null);
        // A host only named in a result's text is no result's address.
        Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "https://exfil.example/c" }),
            Is.EqualTo("host_not_from_session"));
    }

    [Test]
    public void AHostThePersonNamedGoesAndOneNobodyGaveWaits()
    {
        var egress = new NetworkEgress();
        egress.Heard("Pon lofi en YouTube");

        Assert.That(egress.Holds("browser.navigate",
            new JsonObject { ["url"] = "https://www.youtube.com/results?search_query=lofi" }), Is.Null);
        Assert.That(egress.Holds("browser.navigate", new JsonObject { ["url"] = "https://lofi.exfil.example/" }),
            Is.EqualTo("host_not_from_session"));
        Assert.That(egress.Holds("network.ping", new JsonObject { ["host"] = "exfil.example" }),
            Is.EqualTo("host_not_from_session"));
        // An address literal carries no words.
        Assert.That(egress.Holds("network.ping", new JsonObject { ["host"] = "1.1.1.1" }), Is.Null);
    }

    [Test]
    public void AValueMemoryReadInThisTurnWaitsHoweverItIsWritten()
    {
        var egress = new NetworkEgress();
        egress.Heard("busca el clima de donde vivo");
        egress.Observed("web.search", "{\"status\":\"completed\",\"observed\":{\"results\":[{\"url\":\"https://clima.example/\"}]}}");
        egress.Observed("memory.recall", Recall);

        Assert.That(egress.Holds("web.search", new JsonObject { ["query"] = "clima NUNOA hoy" }),
            Is.EqualTo("sends_remembered_value"));
        Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "https://clima.example/?q=Vi%C3%B1a+del+Mar" }),
            Is.EqualTo("sends_remembered_value"));
        // Too short to tell apart, or never read by the model (redacted).
        Assert.That(egress.Holds("web.search", new JsonObject { ["query"] = "sí redacted" }), Is.Null);
    }

    [Test]
    public void WhatMemoryReadInAnEarlierTurnAndWhatAnEarlierSessionSawDoNotCount()
    {
        var egress = new NetworkEgress();
        egress.Observed("web.fetch", "{\"status\":\"completed\",\"observed\":{\"finalUrl\":\"https://clima.example/hoy\"}}");
        egress.Observed("memory.list", Recall);
        egress.NewTurn();

        Assert.That(egress.Holds("web.search", new JsonObject { ["query"] = "clima ñuñoa" }), Is.Null);
        Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "https://clima.example/manana" }), Is.Null);

        egress.Reset();

        Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "https://clima.example/manana" }),
            Is.EqualTo("host_not_from_session"));
    }

    [Test]
    public void ACallThatSendsNothingOutIsNeverHeld()
    {
        var egress = new NetworkEgress();
        egress.Observed("memory.recall", Recall);

        Assert.That(egress.Holds("file.write", new JsonObject { ["path"] = "C:/x.txt", ["text"] = "Ñuñoa" }), Is.Null);
    }
}
