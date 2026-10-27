using System.IO;
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

    // Feria 2026-10-27: a creator's name the person said was searched as another one that sounds alike, and the video of
    // someone else played. A search with none of their words goes back to the model once; the same call again goes.
    [Test]
    public void ASearchWithNoneOfThePersonsWordsGoesBackOnce()
    {
        var egress = new NetworkEgress();
        egress.Heard("ponme un video en el navegador");
        egress.Heard("uno de zentrovox");
        var renamed = new JsonObject { ["query"] = "Centro Box" };

        Assert.Multiple(() =>
        {
            Assert.That(egress.Unsaid("media.play.youtube", renamed)?.Code, Is.EqualTo("query_not_said"));
            Assert.That(egress.Unsaid("media.play.youtube", renamed), Is.Null);
            Assert.That(egress.Unsaid("web.search", new JsonObject { ["query"] = "Centro Box", ["source"] = "news" })
                ?.Code, Is.EqualTo("query_not_said"));
        });
    }

    // Their words with other endings, run together or spelled otherwise by the ear, a source that searches
    // its typed fields and not the query, and a call that sends nothing out are not refused.
    [TestCase("zentrovox", "videos de zentrovox")]
    [TestCase("zentro vox", "zentrovox")]
    [TestCase("busca la receta del pan amasado", "recetas pan amasado")]
    [TestCase("¿la comuna tiene alcaldeza?", "alcaldesa comuna")]
    public void ASearchThatSharesTheirWordsGoes(string words, string query)
    {
        var egress = new NetworkEgress();
        egress.Heard(words);

        Assert.That(egress.Unsaid("web.search", new JsonObject { ["query"] = query }), Is.Null);
    }

    [Test]
    public void OnlyTheTextASearchSendsIsWeighed()
    {
        var egress = new NetworkEgress();
        egress.Heard("¿cuántos pesos son cien dólares?");

        Assert.Multiple(() =>
        {
            Assert.That(egress.Unsaid("web.search", new JsonObject
            {
                ["query"] = "exchange rate", ["source"] = "currency", ["from"] = "USD", ["to"] = "CLP", ["amount"] = 100,
            }), Is.Null);
            Assert.That(egress.Unsaid("note.search", new JsonObject { ["query"] = "presupuesto mensual" }), Is.Null);
        });
    }

    // Feria 2026-10-27: a greeting asked for someone in the room opened a messaging client with a draft. A draft goes
    // only by a channel the person named now or just before (the answer to the model's question keeps what it asked);
    // when the turn that refused a message ended with the model's question, a draft or a send by that channel goes in the
    // turn right after it (their «sí» to «¿le escribo por …?»), and that channel counts as said in that turn and the next.
    [Test]
    public void AMessageGoesOnlyByAChannelThePersonNamed()
    {
        var egress = new NetworkEgress();
        var draft = new JsonObject { ["channel"] = "whatsapp", ["recipient"] = "Nadia", ["text"] = "Hola" };
        egress.Heard("saluda a Nadia");
        (string Code, string Next)? greeted = egress.Unsaid("message.draft", draft);
        (string Code, string Next)? again = egress.Unsaid("message.draft", draft);
        egress.Heard("Nadia, ¿cómo estás?");
        (string Code, string Next)? unasked = egress.Unsaid("message.draft", draft);
        egress.Asked();
        egress.Heard("sí");
        (string Code, string Next)? yes = egress.Unsaid("message.send", draft);
        egress.Heard("la que vive en Temuco");
        (string Code, string Next)? clarified = egress.Unsaid("message.send", new JsonObject
        {
            ["channel"] = "whatsapp", ["recipient"] = "Nadia Temuco", ["text"] = "Hola",
        });
        egress.Heard("escríbele a Nadia por Whats App");
        egress.Heard("que paso a buscarla");

        Assert.Multiple(() =>
        {
            Assert.That(greeted?.Code, Is.EqualTo("channel_not_said"));
            Assert.That(greeted?.Next, Does.Contain("answer them in words"));
            Assert.That(greeted?.Next, Does.Not.Contain("call it again"));
            Assert.That(again?.Code, Is.EqualTo("channel_not_said"));
            Assert.That(unasked?.Code, Is.EqualTo("channel_not_said"));
            Assert.That(yes, Is.Null);
            Assert.That(clarified, Is.Null);
            Assert.That(egress.Unsaid("message.send", draft), Is.Null);
            Assert.That(egress.Unsaid("message.send.test", draft), Is.Null);
        });
    }

    // Revisión de privacidad 2026-10-27: a message asked for clearly, its channel written otherwise by the ear, came back
    // for the whole turn and ended in a question. The first message.send by a channel not said goes back with what to do
    // next; by that channel again in that turn it goes, to that recipient or another wording of it, since the person is
    // asked before it goes; in the next turn the channel is weighed again.
    [TestCase("mándale a Ana por guasap que ya salí", "whatsapp")]
    [TestCase("escríbele a Ana por wasap que llego tarde", "whatsapp")]
    public void AMessageByAChannelSaidInOtherWordsGoesWhenCalledAgain(string words, string channel)
    {
        var egress = new NetworkEgress();
        egress.Heard(words);
        (string Code, string Next)? first = egress.Unsaid("message.send", new JsonObject
        {
            ["channel"] = channel, ["recipient"] = "Ana", ["text"] = "Llego tarde",
        });
        (string Code, string Next)? second = egress.Unsaid("message.send", new JsonObject
        {
            ["channel"] = channel, ["recipient"] = "Ana", ["text"] = "Llego tarde",
        });
        (string Code, string Next)? reworded = egress.Unsaid("message.send", new JsonObject
        {
            ["channel"] = channel, ["recipient"] = "Ana María", ["text"] = "Llego tarde",
        });
        egress.Heard("saluda a Nadia");
        var greeting = new JsonObject { ["channel"] = channel, ["recipient"] = "Nadia", ["text"] = "Hola" };
        (string Code, string Next)? greeted = egress.Unsaid("message.send", greeting);
        egress.Heard("Nadia, pasa");
        (string Code, string Next)? drafted = egress.Unsaid("message.draft", greeting);
        (string Code, string Next)? sentAfterDraft = egress.Unsaid("message.send", greeting);

        Assert.Multiple(() =>
        {
            Assert.That(first?.Code, Is.EqualTo("channel_not_said"));
            Assert.That(first?.Next, Does.Contain("ask them by which channel"));
            Assert.That(first?.Next, Does.Contain("call it again exactly as before"));
            Assert.That(second, Is.Null);
            Assert.That(reworded, Is.Null);
            Assert.That(greeted?.Code, Is.EqualTo("channel_not_said"));
            Assert.That(drafted?.Code, Is.EqualTo("channel_not_said"));
            Assert.That(sentAfterDraft?.Code, Is.EqualTo("channel_not_said"));
        });
    }

    // Revisión de privacidad 2026-10-27: the answer to the model's question releases the message even when the model
    // words the recipient otherwise when it calls again.
    [Test]
    public void TheAnswerReleasesTheMessageWhateverTheRecipientsWording()
    {
        var egress = new NetworkEgress();
        egress.Heard("escríbele a Nadia que llego a las ocho");
        (string Code, string Next)? refused = egress.Unsaid("message.send", new JsonObject
        {
            ["channel"] = "whatsapp", ["recipient"] = "Nadia", ["text"] = "Llego a las ocho",
        });
        egress.Asked();
        egress.Heard("sí");

        Assert.Multiple(() =>
        {
            Assert.That(refused?.Code, Is.EqualTo("channel_not_said"));
            Assert.That(egress.Unsaid("message.send", new JsonObject
            {
                ["channel"] = "whatsapp", ["recipient"] = "Nadia Temuco", ["text"] = "Llego a las ocho",
            }), Is.Null);
        });
    }

    // A search may take its words from what a result or memory gave in a short text («pon un video de él» after a result
    // named him), never from a page's text nor from BAXY's own fields; the person's «sí» to a waiting call keeps the words
    // they said before it.
    [Test]
    public void WhatResultsGaveAndTheWordsBeforeAnAnswerStillCount()
    {
        var egress = new NetworkEgress();
        egress.Heard("¿quién ganó el torneo de ajedrez de este año?");
        egress.Observed("web.search", "{\"status\":\"completed\",\"observed\":{\"results\":[" +
            "{\"title\":\"Gana Ilvaro Kastañeda\",\"url\":\"https://ajedrez.example/a\"}]}}");
        egress.Heard("ponme un video de él");
        egress.Observed("memory.recall", "{\"status\":\"completed\",\"observed\":{\"records\":[" +
            "{\"label\":\"cancion favorita\",\"value\":\"Brisa de Tolhuaca\"}]}}");
        egress.Observed("web.fetch", "{\"status\":\"rejected\",\"next\":\"call it again exactly\",\"observed\":{\"text\":\""
            + new string('x', 120) + " Pehuenquelo\"}}");
        egress.Heard("mándale por whatsapp a Nadia que llego a las ocho");
        egress.Heard("y que lleve pan");
        egress.Heard("sí", answering: true);

        Assert.Multiple(() =>
        {
            Assert.That(egress.Unsaid("media.play.youtube", new JsonObject { ["query"] = "Ilvaro Kastañeda" }), Is.Null);
            Assert.That(egress.Unsaid("media.play.youtube", new JsonObject { ["query"] = "Brisa de Tolhuaca" }), Is.Null);
            Assert.That(egress.Unsaid("web.search", new JsonObject { ["query"] = "Pehuenquelo" })?.Code,
                Is.EqualTo("query_not_said"));
            Assert.That(egress.Unsaid("web.search", new JsonObject { ["query"] = "exactamente" })?.Code,
                Is.EqualTo("query_not_said"));
            Assert.That(egress.Unsaid("message.send", new JsonObject
            {
                ["channel"] = "whatsapp", ["recipient"] = "Nadia", ["text"] = "Llego a las ocho",
            }), Is.Null);
        });
    }

    // Sentences an agent wrote without seeing the check (Data/said-arguments.heldout.v1.json): what goes back and what goes.
    [TestCaseSource(nameof(HeldOut))]
    public void HeldOutSentences(string check, string[] said, string argument, bool back)
    {
        var egress = new NetworkEgress();
        foreach (string words in said)
        {
            egress.Heard(words);
        }

        (string Code, string Next)? unsaid = check == "A"
            ? egress.Unsaid("web.search", new JsonObject { ["query"] = argument })
            : egress.Unsaid("message.send", new JsonObject { ["channel"] = argument, ["recipient"] = "x", ["text"] = "y" });
        Assert.That(unsaid?.Code, back ? Is.EqualTo(check == "A" ? "query_not_said" : "channel_not_said") : Is.Null);
    }

    private static IEnumerable<TestCaseData> HeldOut()
    {
        string path = Path.Combine(TestContext.CurrentContext.TestDirectory, "Data", "said-arguments.heldout.v1.json");
        JsonNode data = JsonNode.Parse(File.ReadAllText(path))!;
        foreach ((string check, string field) in new[] { ("A", "consulta"), ("B", "canal") })
        {
            foreach ((string kind, bool back) in new[] { ("positivas", true), ("negativas", false) })
            {
                JsonArray items = data[check]![kind]!.AsArray();
                for (int index = 0; index < items.Count; index++)
                {
                    string[] said = [.. items[index]!["dicho"]!.AsArray().Select(static words => (string)words!)];
                    yield return new TestCaseData(check, said, (string)items[index]![field]!, back)
                        .SetName($"HeldOut {check} {kind} {index + 1}");
                }
            }
        }
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
