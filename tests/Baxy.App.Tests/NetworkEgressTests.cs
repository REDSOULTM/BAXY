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
        "{\"label\":\"ciudad\",\"value\":\"Viña del Mar\"}]}}";

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

    // Uso real 02-11: a site said with one letter changed, added or missing is the person's; one two letters away, or a
    // short name one letter away, is not.
    [TestCase("abre fackebook marketplace", "https://www.facebook.com/marketplace", null)]
    [TestCase("abre yutube y busca lofi", "https://www.youtube.com/results?search_query=lofi", null)]
    [TestCase("abre fakbok marketplace", "https://www.facebook.com/marketplace", "host_not_from_session")]
    [TestCase("abre bbx noticias", "https://www.bbc.co.uk/news", "host_not_from_session")]
    public void ASiteSaidWithOneLetterOffIsTheirs(string words, string url, string? held)
    {
        var egress = new NetworkEgress();
        egress.Heard(words);

        Assert.That(egress.Holds("browser.navigate", new JsonObject { ["url"] = url }), Is.EqualTo(held));
    }

    // Encargo 119 (F12): the title of an exact song goes out to the search as a query does; altered as it was copied, it
    // goes back once. One the person said, in that form or with another ending, goes.
    [Test]
    public void AnExactTitleWithNoneOfThePersonsWordsGoesBackOnce()
    {
        var egress = new NetworkEgress();
        egress.Heard("ponme a Quelentaro");
        var altered = new JsonObject { ["provider"] = "spotify", ["title"] = "Zarzalito Marino" };

        Assert.Multiple(() =>
        {
            Assert.That(egress.Unsaid("media.play.exact", altered)?.Code, Is.EqualTo("query_not_said"));
            Assert.That(egress.Unsaid("media.play.exact", altered), Is.Null);
            Assert.That(egress.Unsaid("media.play.exact", new JsonObject { ["provider"] = "spotify", ["title"] = "Quelentaro" }), Is.Null);
            Assert.That(egress.Unsaid("media.play.exact", new JsonObject { ["provider"] = "spotify", ["title"] = "Quelentaros" }), Is.Null);
        });
    }

    // A name altered as it was copied goes back with what they said in the call; a title they only described gets the words.
    [TestCase("ponme a Quelentaro", "Quilantero", "Quelentaro")]
    [TestCase("quiero oír a Trevángel", "Trébol Ángel", "Trevángel")]
    [TestCase("pon a Ocaranza", "Ocarina", "Ocaranza")]
    public void AnAlteredTitleGoesBackWithWhatThePersonSaidInTheCall(string words, string title, string said)
    {
        var egress = new NetworkEgress();
        egress.Heard(words);

        string? next = egress.Unsaid("media.play.exact", new JsonObject { ["provider"] = "spotify", ["title"] = title })?.Next;

        Assert.That(next, Does.StartWith("media_play_query {\"provider\":\"spotify\",\"query\":\"" + said + "\"}"));
        Assert.That(next, Does.Contain("they did not say «" + title + "»"));
    }

    [Test]
    public void ATitleOnlyDescribedGoesBackWithoutACallFilledIn()
    {
        var egress = new NetworkEgress();
        egress.Heard("pon la canción de la película Titanic");

        string? next = egress.Unsaid("media.play.exact", new JsonObject { ["provider"] = "spotify", ["title"] = "My Heart Will Go On" })?.Next;

        Assert.That(next, Does.StartWith("nothing ran: this search has none of the person's words"));
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

    // Ajuste c3, e2e E008: «año fundación ONU» for «busca en internet en qué año se fundó la ONU» was refused in every
    // run (its only word of 4 letters or more, «fundación», is not «fundó»). An acronym the query writes in capitals is
    // weighed: the person's when they said it, never one they did not; a short word in lower case is still not weighed.
    [Test]
    public void AnAcronymThePersonSaidIsTheirWord()
    {
        static NetworkEgress Hearing(string words)
        {
            var egress = new NetworkEgress();
            egress.Heard(words);
            return egress;
        }

        const string Asked = "busca en internet en qué año se fundó la ONU";

        Assert.Multiple(() =>
        {
            Assert.That(Hearing(Asked).Unsaid("web.search", new JsonObject
            {
                ["query"] = "año fundación ONU", ["source"] = "web",
            }), Is.Null);
            Assert.That(Hearing(Asked).Unsaid("web.search", new JsonObject { ["query"] = "fundación OEA" })?.Code,
                Is.EqualTo("query_not_said"));
            Assert.That(Hearing("uno de zentrovox").Unsaid("web.search", new JsonObject { ["query"] = "de Centro Box" })
                ?.Code, Is.EqualTo("query_not_said"));
        });
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
    // asked before it goes; in the next turn the channel is weighed again. Encargo 12: a sourced abbreviation («wasap»,
    // «guasap») is now said outright (ApplicationAliases), so the wordings here are ear-garbles the list leaves out.
    [TestCase("mándale a Ana por guatsap que ya salí", "whatsapp")]
    [TestCase("escríbele a Ana por wassap que llego tarde", "whatsapp")]
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

    // Banco de uso 2026-11-03 (U40): a window is named when a part of its title (between « - », « | », « — ») is words
    // the person said now or just before, in that order and whole; never a word inside another, nor a part under 4 letters.
    [Test]
    public void AWindowIsNamedByAPartOfItsTitleThePersonSaid()
    {
        var egress = new NetworkEgress();
        egress.Heard("escribe en la Sala Turquesa");
        egress.Heard("que llego tarde");
        (string Title, string? Process)[] windows =
        [
            ("Sala Turquesa | Charlina", "charlina"),
            ("Sala Azul - Charlina", "charlina"),
            ("Turquesas - Tienda", "tienda"),
            ("la", "otra"),
        ];

        Assert.That(egress.Named(windows).ToJsonString(),
            Is.EqualTo("[{\"title\":\"Sala Turquesa | Charlina\",\"process\":\"charlina\"}]"));
    }

    // Banco de uso 2026-11-03 (R11, R12): the chat named is a row of the list inside a window whose title names nothing
    // («Chat de prueba»). A row is named by its whole name, words of 4 letters or more in that order («Equipo Lunes 🌙»
    // by «a Equipo Lunes», never «Equipo Lunes y Martes» nor «Familia de prueba»); its window carries those rows alone.
    [Test]
    public void AWindowIsNamedByAVisibleRowOfItsListsThePersonSaid()
    {
        var egress = new NetworkEgress();
        egress.Heard("Déjale un mensaje a Equipo Lunes que diga: mañana no hay reunión.");
        Func<string, bool> names = egress.NamesRow();
        string[] rows = ["Equipo Lunes y Martes", "Familia de prueba", "Equipo Lunes 🌙", "Vecinos de prueba", "a"];
        VisibleRow[] read = [.. rows.Where(names).Select(static row => new VisibleRow("Chat de prueba", "ChatPrueba", row))];

        JsonArray named = egress.Named([("Chat de prueba", "ChatPrueba"), ("Notas", "notas")], read);
        Assert.Multiple(() =>
        {
            Assert.That(read.Select(static row => row.Name), Is.EqualTo(new[] { "Equipo Lunes 🌙" }));
            Assert.That(named.Select(static window => (string?)window?["title"]), Is.EqualTo(new[] { "Chat de prueba" }));
            Assert.That(named[0]?["rows"]?.AsArray().Select(static row => (string?)row),
                Is.EqualTo(new[] { "Equipo Lunes 🌙" }));
        });
    }

    private static JsonArray OpenSheet() =>
        [new JsonObject { ["title"] = "almacen - Excel", ["process"] = "EXCEL" }];

    // Encargo 115 (H2, T1, T3): a new file named after the window the person named, with the table meant for that window.
    [TestCase("file.write", "path", "libro_almacen.txt")]
    [TestCase("office.document.create", "title", "Almacen")]
    public void ANewFileNamedAfterTheWindowNamedIsRefusedOnce(string operation, string argument, string name)
    {
        var egress = new NetworkEgress();
        egress.Heard("En el libro almacen pon una tabla con tres filas");
        var call = new JsonObject { [argument] = name };

        var first = egress.Unsaid(operation, call, OpenSheet);
        var again = egress.Unsaid(operation, call, OpenSheet);

        Assert.Multiple(() =>
        {
            Assert.That(first?.Code, Is.EqualTo("new_file_named_after_window"));
            Assert.That(first?.Next, Does.Contain("input_visible_controls").And.Contain("«almacen - Excel»")
                .And.Contain("call it again exactly as before"));
            Assert.That(again, Is.Null);
        });
    }

    [TestCase("guarda en almacen.txt la lista", "almacen.txt")]
    [TestCase("en el libro almacen no toques nada y crea notas.txt", "notas.txt")]
    public void AFileThePersonNamedOrNamedOtherwiseRunsAsWritten(string words, string path)
    {
        var egress = new NetworkEgress();
        egress.Heard(words);

        Assert.That(egress.Unsaid("file.write", new JsonObject { ["path"] = path, ["text"] = "algo" }, OpenSheet), Is.Null);
    }

    [Test]
    public void AnAppendOrAReplacementIsNotANewFile()
    {
        var egress = new NetworkEgress();
        egress.Heard("en el libro almacen");

        Assert.Multiple(() =>
        {
            Assert.That(egress.Unsaid("file.write", new JsonObject { ["path"] = "almacen.log", ["text"] = "x", ["append"] = true }, OpenSheet), Is.Null);
            Assert.That(egress.Unsaid("file.write", new JsonObject { ["path"] = "almacen.log", ["text"] = "x", ["expectedSha256"] = new string('a', 64) }, OpenSheet), Is.Null);
        });
    }

    // A row a reader gave that the person's words do not name is compared again and left out; a window named by its title
    // and by a row is listed once, with the row.
    [Test]
    public void ARowNotNamedIsLeftOutAndAWindowIsListedOnce()
    {
        var egress = new NetworkEgress();
        egress.Heard("Manda al Grupo de prueba en la sala turquesa el mensaje: hoy llego tarde.");
        VisibleRow[] read =
        [
            new("Sala Turquesa - Charlina", "charlina", "Grupo de prueba"),
            new("Sala Turquesa - Charlina", "charlina", "Sala de prueba"),
            new("Otra", "otra", "Grupo de prueba"),
        ];

        Assert.That(egress.Named([("Sala Turquesa - Charlina", "charlina")], read).ToJsonString(), Is.EqualTo(
            "[{\"title\":\"Sala Turquesa - Charlina\",\"process\":\"charlina\",\"rows\":[\"Grupo de prueba\"]},"
            + "{\"title\":\"Otra\",\"process\":\"otra\",\"rows\":[\"Grupo de prueba\"]}]"));
    }

    // Banco uso-cf8d (U40, R13): a message refused for a channel not said, when windows the person named are open, says
    // the calls that reach each of them, its process filled in, in place of the question (measured: with the question
    // after them the model asked it 10 of 10); with none, the next is as before. Banco uso-93f1 (U40): told only to
    // write with input_text_type, the model typed with no field and the text went to the focused menu bar; the next says
    // the field goes by its index. Encargo 45 (R11): it leads with what their words name, and says the text to write.
    [Test]
    public void TheNextOfAChannelNotSaidSaysTheCallsThatReachTheWindowsNamed()
    {
        var egress = new NetworkEgress();
        egress.Heard("en la sala turquesa y en notas varias pon que llego tarde");
        var send = new JsonObject { ["channel"] = "whatsapp", ["recipient"] = "sala", ["text"] = "llego tarde" };
        (string Code, string Next)? plain = egress.Unsaid("message.send", send, static () => []);
        (string Code, string Next)? named = egress.Unsaid("message.draft", send, () => egress.Named(
            [("Sala Turquesa - Charlina", "charlina"), ("Notas varias", null), ("Otra cosa", "otra")]));

        string next = named?.Next ?? string.Empty;
        const string First = "input_visible_controls {\"application\":\"charlina\"} or {\"application\":\"Notas varias\"}";
        Assert.Multiple(() =>
        {
            Assert.That(plain?.Next, Does.StartWith("nothing ran: the person did not name whatsapp now nor just before; if "
                + "they spoke to someone there, answer them in words; if they want a message sent, ask them by which channel"));
            Assert.That(named?.Code, Is.EqualTo("channel_not_said"));
            Assert.That(next, Is.EqualTo("nothing ran: the person's words name the open window «Sala Turquesa - Charlina» "
                + "and the open window «Notas varias», and no channel: " + First + " reads each, then input_visible_click "
                + "and input_text_type with the index of its field write \"llego tarde\" in it"));
        });
    }

    // Encargo 58 (diagnóstico f11dcfa99, S03 6 of 6): «mándale por el chat de prueba al taller …» went to the owner's test
    // channel by a channel the person never said, with the window they named open. A test send is a message too: by a
    // channel not said it goes back once with the calls that reach the window; by the channel they said, it goes.
    [Test]
    public void ATestSendByAChannelNotSaidGoesBackWithTheWindowNamed()
    {
        var egress = new NetworkEgress();
        egress.Heard("mándale por el chat de prueba al taller inventado que llego a las siete");
        var test = new JsonObject
        {
            ["channel"] = "whatsapp", ["requestedRecipient"] = "taller inventado", ["text"] = "llego a las siete",
        };
        (string Code, string Next)? refused = egress.Unsaid("message.send.test", test,
            () => egress.Named([("Chat de prueba", "ChatPrueba")]));
        var said = new NetworkEgress();
        said.Heard("haz un envío de prueba por whatsapp al taller inventado: llego a las siete");

        Assert.Multiple(() =>
        {
            Assert.That(refused?.Code, Is.EqualTo("channel_not_said"));
            Assert.That(refused?.Next, Is.EqualTo("nothing ran: the person's words name the open window «Chat de prueba», "
                + "and no channel: input_visible_controls {\"application\":\"ChatPrueba\"} reads it, then "
                + "input_visible_click and input_text_type with the index of its field write \"llego a las siete\" in it; "
                + "if they named this channel in other words, call it again exactly as before: they are asked before it goes"));
            Assert.That(said.Unsaid("message.send.test", test, static () => []), Is.Null);
        });
    }

    private const string PageOfLinks = """
        {"status":"completed","verification":"output_only","observed":{"version":1,"title":"Lista de prueba",
        "text":"Lista de prueba","truncated":false,"links":["Rio Cobalto","Sierra de Papel (edicion larga)"],
        "browser":"Navegador Prueba"}}
        """;

    private const string StoreHasNoSuchGame = """
        {"status":"failed","error":"game_title_not_found","observed":{"appId":"Steam","place":"game","title":"Rio Cobalto"}}
        """;

    // Encargo 113 (banco de uso R06): a page was read and «ábreme la ficha de ese» went to the store's page by the title of
    // one of its links, and ended in «no está en la tienda». The failure says so, with the look at that page; said, not a
    // link, read long ago or another result, it stays as it was.
    [Test]
    public void AStorePageNotFoundByALinkOfThePageJustReadSaysSoWithTheLookAtThatPage()
    {
        NetworkEgress Heard(string words, bool read = true)
        {
            var egress = new NetworkEgress();
            egress.Heard("en esta lista cuál es la mejor");
            if (read)
            {
                egress.Observed("browser.page.read", PageOfLinks);
            }

            egress.Heard(words);
            return egress;
        }

        string Told(NetworkEgress egress, string operation = "game.store.page", string title = "Rio Cobalto",
            string observation = StoreHasNoSuchGame) =>
            egress.WithLinkOfPage(operation, new JsonObject { ["title"] = title }, observation);

        JsonNode? told = JsonNode.Parse(Told(Heard("ábreme la ficha de ese")));
        var longAgo = Heard("gracias");
        longAgo.Heard("ábreme la ficha de ese");
        const string found = """{"status":"completed","verification":"readback","observed":{"title":"Rio Cobalto"}}""";

        Assert.Multiple(() =>
        {
            Assert.That((string?)told?["error"], Is.EqualTo("game_title_not_found"));
            Assert.That((string?)told?["observed"]?["title"], Is.EqualTo("Rio Cobalto"));
            Assert.That((string?)told?["observed"]?["next"], Does.Contain(
                "input_visible_controls {\"application\":\"Navegador Prueba\"} reads the page open in Navegador Prueba"));
            Assert.That((string?)told?["observed"]?["next"], Does.Contain("\"Rio Cobalto\" is a link"));
            Assert.That((string?)JsonNode.Parse(Told(Heard("ábreme la ficha de ese"), title: "Sierra de Papel"))?["observed"]?["next"],
                Does.Contain("\"Sierra de Papel (edicion larga)\" is a link"), "a link that runs on");
            Assert.That(Told(Heard("ábremelo en steam")), Is.EqualTo(StoreHasNoSuchGame), "the store said");
            Assert.That(Told(Heard("ábreme la ficha de ese"), title: "Otro Titulo"), Is.EqualTo(StoreHasNoSuchGame), "not a link");
            Assert.That(Told(Heard("ábreme la ficha de ese", read: false)), Is.EqualTo(StoreHasNoSuchGame), "no page read");
            Assert.That(Told(longAgo), Is.EqualTo(StoreHasNoSuchGame), "read before the words just before");
            Assert.That(Told(Heard("ábreme la ficha de ese"), "game.launch"), Is.EqualTo(StoreHasNoSuchGame), "another call");
            Assert.That(Told(Heard("ábreme la ficha de ese"), observation: found), Is.EqualTo(found), "the store has it");
        });
    }

    // Banco de uso 2026-11-03 (S01, S05, S06): «en la página de streaming de prueba ponme …» went to a streaming service
    // and «en el chat de prueba …» to a chat client, with the window the person named open. A call whose closed value
    // is an application they did not say, while their words name open windows none of which is that application's,
    // goes back once with the call that reaches them first; said, or with that application's window named, it goes.
    [Test]
    public void AnApplicationNotSaidWithAnotherWindowNamedGoesBackOnceWithTheCallThatReachesIt()
    {
        var egress = new NetworkEgress();
        egress.Heard("ábreme el grupo de ajedrez en charla norte, sin escribir nada");
        var open = new JsonObject { ["client"] = "discord", ["name"] = "grupo de ajedrez" };
        Func<JsonArray> named = () => egress.Named([("Charla Norte", "CharlaNorte"), ("Otra cosa", "otra")]);

        (string Code, string Next)? refused = egress.Unsaid("client.channel.open", open, named);
        (string Code, string Next)? again = egress.Unsaid("client.channel.open", open, named);
        var unnamed = new NetworkEgress();
        unnamed.Heard("ábreme el grupo de ajedrez, sin escribir nada");
        (string Code, string Next)? none = unnamed.Unsaid("client.channel.open", open,
            () => unnamed.Named([("Charla Norte", "CharlaNorte")]));

        var said = new NetworkEgress();
        said.Heard("ábreme el grupo de ajedrez en discord");
        var itsOwn = new NetworkEgress();
        itsOwn.Heard("en la sala ajedrez abre el grupo de ajedrez");
        var streaming = new NetworkEgress();
        streaming.Heard("pon la serie Los Faroles en Disney+, porfa");

        Assert.Multiple(() =>
        {
            Assert.That(refused?.Code, Is.EqualTo("application_not_said"));
            Assert.That(refused?.Next, Is.EqualTo("input_visible_controls {\"application\":\"CharlaNorte\"} reads the open "
                + "window their words name («Charla Norte»), and input_visible_click acts on what it shows; this call ran "
                + "nothing: the person did not name discord now nor just before"));
            Assert.That(again, Is.Null);
            Assert.That(none, Is.Null);
            Assert.That(said.Unsaid("client.channel.open", open, () => said.Named([("Charla Norte", "CharlaNorte")])),
                Is.Null);
            Assert.That(itsOwn.Unsaid("client.channel.open", open,
                () => itsOwn.Named([("Sala Ajedrez - Discord", "Discord")])), Is.Null);
            Assert.That(streaming.Unsaid("streaming.play.named",
                new JsonObject { ["service"] = "disney_plus", ["title"] = "Los Faroles" },
                () => streaming.Named([("Disney+ - Perfil 1 - Microsoft Edge", "msedge")])), Is.Null);
        });
    }

    // Banco de uso 2026-11-03 (S07): «¿qué estado tengo puesto en el chat de prueba?» read the clipboard, failed, and the
    // model said nothing was copied. A failed call none of whose texts is in a window the person's words name says the
    // call that reaches those windows first; a call on that window, or none named, says nothing.
    [Test]
    public void AFailedCallOffTheWindowNamedSaysTheCallThatReachesIt()
    {
        var egress = new NetworkEgress();
        egress.Heard("¿qué saldo sale en billetera sur?");
        Func<JsonArray> named = () => egress.Named([("Billetera Sur", "BilleteraSur"), ("Otra cosa", "otra")]);

        string? onIt = NetworkEgress.Unreached(new JsonObject { ["application"] = "BilleteraSur" }, named);
        string? off = NetworkEgress.Unreached(new JsonObject { ["maxCharacters"] = 200 }, named);

        var unnamed = new NetworkEgress();
        unnamed.Heard("¿qué tengo copiado?");

        Assert.Multiple(() =>
        {
            Assert.That(onIt, Is.Null);
            Assert.That(off, Is.EqualTo("input_visible_controls {\"application\":\"BilleteraSur\"} reads the open window "
                + "their words name («Billetera Sur»), and input_visible_click acts on what it shows; this call is not "
                + "on them"));
            Assert.That(NetworkEgress.Unreached([], () => unnamed.Named([("Billetera Sur", "BilleteraSur")])), Is.Null);
        });
    }

    // Banco de uso 05-11 (U06): a browser whose tabs alone their words name is told, not gone to; said by its name (the title's
    // last word, in any of its forms) or its process, or a window named by itself, keeps the way. An empty title or process names
    // nothing: in a first turn, with no words before, an empty form would be «said».
    [TestCase("abre YouTube y busca pan", "Bandeja - Opera", "opera", true, true)]
    [TestCase("en mi Opera abre YouTube y busca pan", "Bandeja - Opera", "opera", true, false)]
    [TestCase("en mi Edge abre YouTube y busca pan", "Bandeja - Microsoft​ Edge", "msedge", true, false)]
    [TestCase("en el chrome abre YouTube", "Bandeja - Google Chrome", "chrome", true, false)]
    [TestCase("abre Google y busca pan", "Bandeja - Google Chrome", "chrome", true, true)]
    [TestCase("abre YouTube y busca pan", "", "", true, true)]
    [TestCase("abre YouTube y busca pan", "YouTube", "ChatPrueba", false, false)]
    public void ABrowserNamedOnlyByItsTabsIsToldNotGoneTo(string words, string title, string process, bool tab, bool told)
    {
        var egress = new NetworkEgress();
        egress.Heard(words);
        var window = new JsonObject { ["title"] = title, ["process"] = process };
        if (tab)
            window["tabs"] = new JsonArray(new JsonObject { ["title"] = "Mis videos - YouTube", ["shown"] = false });

        string? next = egress.BrowserUnsaid(new JsonArray(window));

        Assert.That(next, told ? Does.StartWith("this call failed").And.Contain("ask whether") : Is.Null);
    }

    // Encargo 65 (cosecha F2): a browser tab is named by a part of its page's title said whole, or by a word of 4 letters
    // or more of its first or last part (the site's name, «Page - Site» or «Site - Page») when that part has 2 words or
    // fewer; never by a word of a longer part (the page's own words) nor by a word inside another.
    [TestCase("abre en el Gmail lo último que me mandó Codeberg", "Recibidos (3) - ana@ejemplo.test - Gmail", true)]
    [TestCase("en el Drive búscame la planilla del asado", "Mi unidad - Google Drive", true)]
    [TestCase("en proton fíjate si me llegó algo", "Bandeja de entrada | rodrigo@ejemplo.test | Proton Mail", true)]
    [TestCase("en el calendar de google qué tengo el jueves", "Google Calendar - semana del 2 de noviembre", true)]
    [TestCase("en el whatsapp web dile que llego tipo ocho", "(2) WhatsApp", true)]
    [TestCase("cómo hacer una transferencia", "Cómo hacer pan amasado en casa - YouTube", false)]
    [TestCase("cómo hacer una transferencia", "Cómo hacer pan - YouTube", false)]
    [TestCase("abre en el Gmail mis mensajes", "Gmailers del sur - Foro", false)]
    [TestCase("qué tiempo hace mañana en Concepción", "Mi unidad - Google Drive", false)]
    public void ATabIsNamedByItsSitesNameOrAPartOfItsTitle(string words, string tab, bool named)
    {
        var egress = new NetworkEgress();
        egress.Heard(words);

        Assert.That(egress.NamesTab()(tab), Is.EqualTo(named));
    }

    // Encargo 65 (cosecha F2, uso real 03-11): email.latest.read read Outlook's newest mail with the person's webmail open
    // in a browser tab, and the model said there was no mail from the sender asked. A completed result of an application (its source)
    // that none of the windows and tabs the person named shows says the call that reaches them first, and that the result
    // is of that application alone; a tab not shown is clicked first. A window that shows the source, or none named, says
    // nothing.
    [Test]
    public void ACompletedResultOfAnotherApplicationSaysTheTabNamedAndTheCallThatReachesIt()
    {
        var egress = new NetworkEgress();
        egress.Heard("abre en el Gmail lo último que me mandó Codeberg");
        Func<string, bool> tabs = egress.NamesTab();
        VisibleRow[] read = [.. new[]
            {
                new VisibleRow("Runpod Billing - Opera", "opera", "Runpod Billing", Tab: true, Shown: true),
                new VisibleRow("Runpod Billing - Opera", "opera", "Recibidos (3) - ana@ejemplo.test - Gmail", Tab: true),
            }.Where(row => tabs(row.Name))];
        Func<JsonArray> named = () => egress.Named([("Runpod Billing - Opera", "opera")], read);

        string? elsewhere = NetworkEgress.Elsewhere("Outlook", named);
        var outlook = new NetworkEgress();
        outlook.Heard("en Outlook léeme el último correo");
        string? onIt = NetworkEgress.Elsewhere("Outlook", () => outlook.Named(
            [("Bandeja de entrada - ana@ejemplo.test - Outlook", "OUTLOOK")]));
        var unnamed = new NetworkEgress();
        unnamed.Heard("léeme mi último correo");

        Assert.Multiple(() =>
        {
            Assert.That(named().ToJsonString(), Is.EqualTo("[{\"title\":\"Runpod Billing - Opera\",\"process\":\"opera\","
                + "\"tabs\":[{\"title\":\"Recibidos (3) - ana@ejemplo.test - Gmail\",\"shown\":false}]}]"));
            Assert.That(elsewhere, Is.EqualTo("input_visible_controls {\"application\":\"opera\"} (its tab «Recibidos (3) - "
                + "ana@ejemplo.test - Gmail», not the one shown: input_visible_click on it in what it shows) reads the open window "
                + "their words name («Runpod Billing - Opera»), and input_visible_click acts on what it shows; this result "
                + "is of Outlook alone, not of them"));
            Assert.That(onIt, Is.Null);
            Assert.That(NetworkEgress.Elsewhere("Outlook", () => unnamed.Named(
                [("Recibidos - ana@ejemplo.test - Gmail - Opera", "opera")])), Is.Null);
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

    // Encargo 12 (caso real 03-11, «… por wsp» → BAXY preguntó «¿WhatsApp o Discord?»): a channel is said by one of its
    // non-ambiguous abbreviations as a whole word, the owner's one accepted help (ApplicationAliases); an ambiguous common
    // word («un disco» for Discord) is not that channel, so a message by it still waits.
    [Test]
    public void AChannelNamedByANonAmbiguousAbbreviationIsSaid()
    {
        var egress = new NetworkEgress();
        egress.Heard("mándale a Nadia que llego tarde por wsp");
        (string Code, string Next)? byAbbreviation = egress.Unsaid("message.draft",
            new JsonObject { ["channel"] = "whatsapp", ["recipient"] = "Nadia", ["text"] = "Llego tarde" });

        egress.Reset();
        egress.Heard("pon un disco mientras tanto");
        (string Code, string Next)? ambiguous = egress.Unsaid("message.draft",
            new JsonObject { ["channel"] = "discord", ["recipient"] = "Nadia", ["text"] = "Hola" });

        Assert.Multiple(() =>
        {
            Assert.That(byAbbreviation, Is.Null);
            Assert.That(ambiguous?.Code, Is.EqualTo("channel_not_said"));
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

    // Encargo 41 (U29): a web.search the engine refused leads with opening the same search in the person's browser; its
    // address is the failure's searchPageUrl, so that call goes unasked, while the same address before it is a host
    // nobody gave.
    [Test]
    public void TheSearchPageOfARefusedSearchOpensUnasked()
    {
        const string page = "https://duckduckgo.com/?q=receta%20de%20lentejas&kl=cl-es";
        var egress = new NetworkEgress();
        egress.Heard("busca una receta de lentejas");
        string? before = egress.Holds("browser.navigate", new JsonObject { ["url"] = page });
        egress.Observed("web.search", "{\"status\":\"failed\",\"error\":\"web_search_unavailable\",\"observed\":{"
            + "\"version\":1,\"source\":\"web\",\"query\":\"receta de lentejas\",\"searchPageUrl\":\"" + page + "\","
            + "\"next\":\"browser_navigate_set {\\\"url\\\":\\\"" + page + "\\\"} opens this search\"}}");

        Assert.Multiple(() =>
        {
            Assert.That(before, Is.EqualTo("host_not_from_session"));
            Assert.That(egress.Holds("browser.navigate", new JsonObject { ["url"] = page }), Is.Null);
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
            Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "https://ejemplo.com/vina" }),
                Is.EqualTo("host_not_from_session"));
            Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "ejemplo.com/?d=vina" }),
                Is.EqualTo("host_not_from_session"));
            Assert.That(egress.Holds("browser.navigate", new JsonObject { ["url"] = "https://ejemplo.com/#vina" }),
                Is.EqualTo("host_not_from_session"));
            Assert.That(egress.Holds("browser.navigate", new JsonObject { ["url"] = "https://vina@ejemplo.com/" }),
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
            Assert.That(egress.Holds("web.fetch", new JsonObject { ["url"] = "http://203.0.113.9/c?d=Viña" }),
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

        Assert.That(egress.Holds("web.search", new JsonObject { ["query"] = "clima VINA-DEL-MAR hoy" }), Is.Null);
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
                ["path"] = "C:/x.txt", ["text"] = "Viña del Mar", ["url"] = "https://exfil.example/x",
            }), Is.Null);
        });
    }
}
