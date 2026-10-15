using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 24b (banco r23 c6): «prueba BAXY C6» was typed at the caret into Discord's search («Buscar .wolfsoultm.4191»)
/// while «Mensaje @Ron92» stayed empty; «stepDone:input.text.type» passed on the text in any field and the Enter on the
/// search passed «enviar». The typing receipt now says «intoSearch» and «otherField», a free text has its own marker
/// («stepDone:input.text.type:written») and sending reads the message sent («sent:»). Twins of
/// tests/test_cu_v3_r24b_texto_en_buscador.py.
/// </summary>
[TestFixture]
public sealed class ComputerUseR24bTextInSearchTests
{
    private const string Text = "prueba BAXY C6";

    private static JsonObject C6(string searchValue, string composerValue) => (JsonObject)JsonNode.Parse($$$"""
        {"window": {"title": "@Ron92 - Discord", "process": "Discord",
                    "focused": {"i": 19, "kind": "ComboBox", "name": "Buscar .wolfsoultm.4191", "value": "{{{searchValue}}}"}},
         "controls": [
           {"i": 0, "kind": "Document", "name": "@Ron92", "state": "readonly", "value": "https://discord.com/channels/@me/1"},
           {"i": 19, "kind": "ComboBox", "name": "Buscar .wolfsoultm.4191", "state": "collapsed focused", "value": "{{{searchValue}}}"},
           {"i": 20, "kind": "Edit", "name": "Mensaje @Ron92", "value": "{{{composerValue}}}"}]}
        """)!;

    private static JsonObject Typed(JsonObject view)
    {
        var record = new JsonObject { ["step"] = 2, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = Text };
        ComputerUseMission.NoteWhereTheTextGoes(record, new JsonObject { ["text"] = Text }, view);
        return record;
    }

    [Test]
    public void TheReceiptSaysTheTextWentIntoTheSearchBesideAMessageBox()
    {
        JsonObject record = Typed(C6("", ""));
        Assert.Multiple(() =>
        {
            Assert.That((bool?)record["atCaret"], Is.True);
            Assert.That((bool?)record["intoSearch"], Is.True);
            Assert.That((bool?)record["otherField"], Is.True);
        });
    }

    [Test]
    public void ALauncherWhoseOnlyFieldIsItsSearchHasNoOtherField()
    {
        var launcher = (JsonObject)JsonNode.Parse("""
            {"window": {"title": "Inicio", "focused": {"i": 0, "kind": "Edit", "name": "Buscar", "value": ""}},
             "controls": [{"i": 0, "kind": "Edit", "name": "Buscar", "state": "focused", "value": ""},
                          {"i": 1, "kind": "ListItem", "name": "Bloc de notas"}]}
            """)!;
        var record = new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "notepad" };
        ComputerUseMission.NoteWhereTheTextGoes(record, new JsonObject { ["text"] = "notepad" }, launcher);
        var after = (JsonObject)launcher.DeepClone();
        after["window"]!["focused"]!["value"] = "notepad";
        after["controls"]![0]!["value"] = "notepad";
        Assert.Multiple(() =>
        {
            Assert.That((bool?)record["intoSearch"], Is.True);
            Assert.That((bool?)record["otherField"], Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                "stepDone:input.text.type:written", after, new JsonArray { record }, out _), Is.True);
        });
    }

    [Test]
    public void NotepadsDocumentIsNoSearch()
    {
        var notepad = (JsonObject)JsonNode.Parse("""
            {"window": {"title": "Sin título: Bloc de notas", "focused": {"i": 0, "kind": "Document", "name": "Editor de texto", "value": ""}},
             "controls": [{"i": 0, "kind": "Document", "name": "Editor de texto", "state": "focused", "value": ""},
                          {"i": 1, "kind": "Edit", "name": "Buscar", "value": ""}]}
            """)!;
        var record = new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "hola" };
        ComputerUseMission.NoteWhereTheTextGoes(record, new JsonObject { ["text"] = "hola" }, notepad);
        Assert.That(record.ContainsKey("intoSearch"), Is.False);
    }

    [Test]
    public void AFreeTextInTheSearchIsNotWrittenThoughASearchStillCountsIt()
    {
        JsonObject record = Typed(C6("", ""));
        JsonObject after = C6(Text, "");
        var steps = new JsonArray { record };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type:written", after, steps, out _), Is.False);
            // Counter-case: the plain atom (a search's own typing, a field said) still reads the text on screen.
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", after, steps, out _), Is.True);
            // The marker is no text to look for: typed into the message box, the written atom holds.
            var intoBox = new JsonObject { ["step"] = 2, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = Text, ["atCaret"] = true };
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                "stepDone:input.text.type:written", C6("", Text), new JsonArray { intoBox }, out _), Is.True);
            // A written atom is judged on screen, never on receipts alone.
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("stepDone:input.text.type:written", steps, out _), Is.False);
        });
    }

    private static JsonArray Enter() => new()
    {
        new JsonObject { ["step"] = 4, ["operation"] = "input.key.press", ["ok"] = true, ["key"] = "enter", ["target"] = "message_composer" },
    };

    private static JsonObject BeforeEnter(JsonObject before) =>
        new() { ["4"] = ComputerUseSuccessCheck.ViewBeforeTyping(before) };

    [Test]
    public void AnEnterOnTheSearchThatKeepsTheTextSendsNothing()
    {
        JsonObject after = C6(Text, "");
        after["viewBeforeEnter"] = BeforeEnter(C6(Text, ""));
        const string check = "stepDone:input.key.press:enter&sent:" + Text;
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Sent(Text, after, Enter()), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, after, Enter(), out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(check, Enter(), out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.ExactCheckContradicts(check, after, Enter()), Is.True);
        });
    }

    [Test]
    public void TheMessageBoxEmptiedOrTheMessageShownIsSent()
    {
        JsonObject emptied = C6("", "");
        emptied["viewBeforeEnter"] = BeforeEnter(C6("", Text));
        JsonObject listed = (JsonObject)JsonNode.Parse("""
            {"window": {"title": "@Ron92 - Discord", "focused": {"kind": "Document", "name": "Enviar mensaje a @Ron92"}},
             "controls": [], "text": {"main": ["ayer a las 6:45", "prueba BAXY C6"]}}
            """)!;
        var unreadBox = (JsonObject)JsonNode.Parse("""{"controls": [], "text": {"main": ["ayer a las 6:45"]}}""")!;
        listed["viewBeforeEnter"] = BeforeEnter(unreadBox);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Sent(Text, emptied, Enter()), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.key.press:enter&sent:" + Text, emptied, Enter(), out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Sent(Text, listed, Enter()), Is.True);
            // Shown no more times than before, with nothing else read: not sent.
            var same = (JsonObject)unreadBox.DeepClone();
            same["viewBeforeEnter"] = BeforeEnter(unreadBox);
            Assert.That(ComputerUseSuccessCheck.Sent(Text, same, Enter()), Is.False);
        });
    }

    [Test]
    public void AnEditorWithNoValueAndNoTextLeavesTheEnterAsItsReceipt()
    {
        var blind = (JsonObject)JsonNode.Parse("""
            {"window": {"title": "Discord", "focused": {"kind": "Document", "name": "Enviar mensaje a @Ron92"}}, "controls": [], "text": {}}
            """)!;
        blind["viewBeforeEnter"] = BeforeEnter(blind);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Sent(Text, blind, Enter()), Is.True);
            // No Enter at all is never a message sent.
            Assert.That(ComputerUseSuccessCheck.Sent(Text, blind, new JsonArray()), Is.False);
        });
    }

    [Test]
    public void TheMindIsToldWhereTheLastTextWent()
    {
        var steps = new JsonArray { Typed(C6("", "")), Enter()[0]!.DeepClone() };
        JsonObject judged = ComputerUseMission.ForTheJudge(new JsonObject(), new JsonObject(), null, C6(Text, ""), steps);
        Assert.Multiple(() =>
        {
            Assert.That((string?)judged["lastTyped"]?["text"], Is.EqualTo(Text));
            Assert.That((bool?)judged["lastTyped"]?["atCaret"], Is.True);
            Assert.That((bool?)judged["lastTyped"]?["intoSearch"], Is.True);
            Assert.That(ComputerUseMission.ForTheJudge(new JsonObject(), new JsonObject(), null, C6("", ""), new JsonArray())
                .ContainsKey("lastTyped"), Is.False);
        });
    }

    // ------------------------------------------------------------------------------------------ revisión 1 (B1, B2, B3)
    private static JsonObject Chat(string searchValue, string composerValue) => (JsonObject)JsonNode.Parse($$$"""
        {"window": {"title": "@Ron92 - Discord", "process": "Discord",
                    "focused": {"i": 20, "kind": "Edit", "name": "Mensaje @Ron92", "value": "{{{composerValue}}}"}},
         "controls": [
           {"i": 0, "kind": "Document", "name": "@Ron92", "state": "readonly", "value": "https://discord.com/channels/@me/1"},
           {"i": 19, "kind": "ComboBox", "name": "Buscar .wolfsoultm.4191", "state": "collapsed", "value": "{{{searchValue}}}"},
           {"i": 20, "kind": "Edit", "name": "Mensaje @Ron92", "state": "focused", "value": "{{{composerValue}}}"}]}
        """)!;

    private static JsonArray TypedOn(JsonObject typedOn)
    {
        var typing = new JsonObject { ["step"] = 3, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = Text };
        ComputerUseMission.NoteWhereTheTextGoes(typing, new JsonObject { ["text"] = Text }, typedOn);
        return new JsonArray { typing };
    }

    [Test]
    public void B1_TheMessageBoxEmptiedIsSentWhateverADirtySearchStillHolds()
    {
        // A cut burst left «prueba BAXY C6» in the search; BAXY typed it in the message box and the Enter emptied it.
        JsonObject typedOn = Chat(Text, "");
        JsonObject before = Chat(Text, Text);
        JsonObject after = Chat(Text, "");
        after["viewBeforeEnter"] = new JsonObject { ["4"] = ComputerUseSuccessCheck.ViewBeforeEnter(before, TypedOn(typedOn)) };
        const string check = "stepDone:input.key.press:enter&sent:" + Text;
        Assert.Multiple(() =>
        {
            Assert.That((string?)after["viewBeforeEnter"]!["4"]!["into"], Is.EqualTo("Mensaje @Ron92"));
            Assert.That(ComputerUseSuccessCheck.Sent(Text, after, Enter()), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, after, Enter(), out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.ExactCheckContradicts(check, after, Enter()), Is.False);
        });
    }

    [Test]
    public void B1_TheTextStaysOnlyInTheFieldThatTookIt()
    {
        // The message box shows no value (an editor that hides it): the dirty search still holding the text says nothing
        // about the Enter, which stands as its receipt.
        JsonObject hidden = Chat(Text, "");
        ((JsonObject)hidden["controls"]![2]!).Remove("value");
        ((JsonObject)hidden["window"]!["focused"]!).Remove("value");
        JsonObject after = (JsonObject)hidden.DeepClone();
        after["viewBeforeEnter"] = new JsonObject { ["4"] = ComputerUseSuccessCheck.ViewBeforeEnter(hidden, TypedOn(hidden)) };
        // Counter-case (c6): the text was typed into the search, which keeps it after the Enter: nothing sent.
        JsonObject kept = C6(Text, "");
        kept["viewBeforeEnter"] = new JsonObject { ["4"] = ComputerUseSuccessCheck.ViewBeforeEnter(C6(Text, ""), TypedOn(C6("", ""))) };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Sent(Text, after, Enter()), Is.True);
            Assert.That((string?)kept["viewBeforeEnter"]!["4"]!["into"], Is.EqualTo("Buscar .wolfsoultm.4191"));
            Assert.That(ComputerUseSuccessCheck.Sent(Text, kept, Enter()), Is.False);
            Assert.That(ComputerUseSuccessCheck.ExactCheckContradicts("stepDone:input.key.press:enter&sent:" + Text, kept, Enter()), Is.True);
        });
    }

    private static JsonObject Ocr(params string[] lines)
    {
        var view = (JsonObject)JsonNode.Parse("""
            {"window": {"title": "WhatsApp", "process": "WhatsApp", "focused": {"kind": "Pane", "name": "WhatsApp"}},
             "controls": [{"i": 0, "kind": "Pane", "name": "WhatsApp"}], "text": {}}
            """)!;
        var zone = new JsonArray();
        foreach (string line in lines)
        {
            zone.Add(line);
        }

        view["text"]!["main"] = zone;
        return view;
    }

    [Test]
    public void B2_ReadOnlyByOcrTheTextMovedFromTheBoxToABubbleIsNoContradiction()
    {
        // wa-1: before the Enter the reading saw the text in the box; after, in the bubble with its hour, and the box
        // back to its placeholder. Shown no more times, but the look changed: the Enter stands as its receipt.
        const string hola = "hola que tal";
        JsonObject before = Ocr("Juanito", "en línea", "ayer", hola);
        JsonObject after = Ocr("Juanito", "en línea", "ayer", hola + " 21:43", "Escribe un mensaje");
        after["viewBeforeEnter"] = new JsonObject { ["4"] = ComputerUseSuccessCheck.ViewBeforeEnter(before, new JsonArray()) };
        const string check = "stepDone:input.key.press:enter&sent:" + hola;
        // Counter-case: the Enter left the look as it was (the text still where it was typed): nothing sent.
        JsonObject unchanged = Ocr("Juanito", "en línea", "ayer", hola);
        unchanged["viewBeforeEnter"] = new JsonObject { ["4"] = ComputerUseSuccessCheck.ViewBeforeEnter(before, new JsonArray()) };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Sent(hola, after, Enter()), Is.True);
            Assert.That(ComputerUseSuccessCheck.ExactCheckContradicts(check, after, Enter()), Is.False);
            Assert.That(ComputerUseSuccessCheck.Sent(hola, unchanged, Enter()), Is.False);
            Assert.That(ComputerUseSuccessCheck.ExactCheckContradicts(check, unchanged, Enter()), Is.True);
        });
    }

    [Test]
    public void B3_ADocumentTitledWithASearchWordIsNoSearch()
    {
        foreach (string document in new[] { "Búsqueda de empleo", "Ir a la playa", "Search notes" })
        {
            var word = (JsonObject)JsonNode.Parse($$$"""
                {"window": {"title": "{{{document}}} - Word", "focused": {"i": 50, "kind": "Document", "name": "{{{document}}}", "value": ""}},
                 "controls": [{"i": 3, "kind": "Edit", "name": "Buscar en documento", "value": ""},
                              {"i": 50, "kind": "Document", "name": "{{{document}}}", "state": "focused", "value": ""},
                              {"i": 51, "kind": "Edit", "name": "Encabezado", "value": ""}]}
                """)!;
            var record = new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "hola mundo" };
            ComputerUseMission.NoteWhereTheTextGoes(record, new JsonObject { ["text"] = "hola mundo" }, word);
            Assert.That(record.ContainsKey("intoSearch"), Is.False, document);
            Assert.That(ComputerUseMission.SearchField((JsonObject)word["controls"]![1]!, word), Is.False, document);
        }

        // Counter-cases: a small Document whose whole name is a search label, and an Edit with a search word, are
        // searches; a large Document so labelled is the person's page.
        var labelled = (JsonObject)JsonNode.Parse("""
            {"window": {"rect": {"x": 0, "y": 0, "w": 1000, "h": 800}},
             "controls": [{"i": 1, "kind": "Document", "name": "Buscar:", "rect": {"x": 0, "y": 0, "w": 200, "h": 24}},
                          {"i": 2, "kind": "Document", "name": "Search", "rect": {"x": 0, "y": 40, "w": 1000, "h": 700}},
                          {"i": 3, "kind": "Edit", "name": "Buscar en documento"}]}
            """)!;
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.SearchField((JsonObject)labelled["controls"]![0]!, labelled), Is.True);
            Assert.That(ComputerUseMission.SearchField((JsonObject)labelled["controls"]![1]!, labelled), Is.False);
            Assert.That(ComputerUseMission.SearchField((JsonObject)labelled["controls"]![2]!, labelled), Is.True);
            Assert.That(OperationFloor.SearchLabelName("busqueda de empleo"), Is.False);
            Assert.That(OperationFloor.SearchLabelName("buscar"), Is.True);
        });
    }

    // ------------------------------------------------------------------------------------------ revisión 2 (B1, B2, B3)
    private static JsonObject Box(string name, string boxValue, string searchName, string searchValue, bool keyboardInBox)
    {
        var searchField = new JsonObject
        {
            ["i"] = 19,
            ["kind"] = "Edit",
            ["name"] = searchName,
            ["state"] = keyboardInBox ? "" : "focused",
            ["value"] = searchValue,
        };
        var boxField = new JsonObject
        {
            ["i"] = 20,
            ["kind"] = "Edit",
            ["name"] = name,
            ["state"] = keyboardInBox ? "focused" : "",
            ["value"] = boxValue,
        };
        JsonObject focused = (JsonObject)(keyboardInBox ? boxField : searchField).DeepClone();
        focused.Remove("state");
        return new JsonObject
        {
            ["window"] = new JsonObject { ["title"] = "Chat", ["process"] = "Chat", ["focused"] = focused },
            ["controls"] = new JsonArray { searchField, boxField },
        };
    }

    [Test]
    public void R2B1_AMessageBoxNamedForASearchLikeRecipientIsNoSearch()
    {
        foreach (string name in new[]
            { "Enviar mensaje a #búsqueda-de-equipo", "Message #job-search", "Message #find-a-duo", "Enviar mensaje a #filtros", "Mensaje @Buscador99" })
        {
            JsonObject view = Box(name, "", "Buscar .wolfsoultm.4191", "", keyboardInBox: true);
            var record = new JsonObject { ["step"] = 3, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "hola" };
            ComputerUseMission.NoteWhereTheTextGoes(record, new JsonObject { ["text"] = "hola" }, view);
            Assert.Multiple(() =>
            {
                Assert.That(record.ContainsKey("intoSearch"), Is.False, name);
                Assert.That(ComputerUseMission.SearchField((JsonObject)view["controls"]![1]!, view), Is.False, name);
                Assert.That(OperationFloor.SearchFieldName(ComputerUseSuccessCheck.Fold(name)), Is.False, name);
            });
        }

        // Counter-cases: a search that says «chat» is still the search, and so is a search word outside a recipient.
        JsonObject whatsapp = Box("Escribe un mensaje", "", "Buscar o empezar un chat nuevo", "", keyboardInBox: false);
        var intoSearch = new JsonObject { ["step"] = 3, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "hola" };
        ComputerUseMission.NoteWhereTheTextGoes(intoSearch, new JsonObject { ["text"] = "hola" }, whatsapp);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)intoSearch["intoSearch"], Is.True);
            Assert.That((bool?)intoSearch["otherField"], Is.True);
            Assert.That(OperationFloor.SearchFieldName("buscar o empezar un chat nuevo"), Is.True);
            Assert.That(OperationFloor.SearchFieldName("search messages in #general"), Is.True);
            Assert.That(OperationFloor.SearchFieldName("buscar .wolfsoultm.4191"), Is.True);
        });
    }

    [Test]
    public void R2B2_TheTextComparedIsTheOneTypedNotThePlaceOfThePhrase()
    {
        // «en WhatsApp escribí hola en la caja de mensaje y mandalo»: the act typed «hola»; the atom says the phrase.
        const string box = "Escribe un mensaje";
        const string search = "Buscar o empezar un chat nuevo";
        var typing = new JsonObject { ["step"] = 3, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "hola" };
        ComputerUseMission.NoteWhereTheTextGoes(typing, new JsonObject { ["text"] = "hola" }, Box(box, "", search, "", keyboardInBox: true));
        var typed = new JsonArray { typing };
        JsonObject sent = Box(box, "", search, "", keyboardInBox: true);
        sent["text"] = new JsonObject { ["main"] = new JsonArray("hola 21:43") };
        sent["viewBeforeEnter"] = new JsonObject { ["4"] = ComputerUseSuccessCheck.ViewBeforeEnter(Box(box, "hola", search, "", keyboardInBox: true), typed) };
        JsonObject kept = Box(box, "hola", search, "", keyboardInBox: true);
        kept["viewBeforeEnter"] = sent["viewBeforeEnter"]!.DeepClone();
        foreach (string phrase in new[] { "hola en la caja de mensaje", "hola en el cuadro de mensaje", "hola en el chat" })
        {
            string check = "stepDone:input.key.press:enter&sent:" + phrase;
            Assert.Multiple(() =>
            {
                Assert.That(ComputerUseSuccessCheck.Sent(phrase, sent, Enter()), Is.True, phrase);
                Assert.That(ComputerUseSuccessCheck.Evaluate(check, sent, Enter(), out _), Is.True, phrase);
                Assert.That(ComputerUseSuccessCheck.ExactCheckContradicts(check, sent, Enter()), Is.False, phrase);
                // Counter-case: the box still holds what was typed: not sent.
                Assert.That(ComputerUseSuccessCheck.Sent(phrase, kept, Enter()), Is.False, phrase);
            });
        }
    }

    [Test]
    public void R2B3_OnlyTheFieldThatTookTheTextOrAMessageBoxEmptiedIsASend()
    {
        // (a) Dirty base: a cut burst left the text in the search; BAXY typed it in «Mensaje @Ron92». The Enter emptied the
        // search, never the box: the text stayed where it was typed, nothing was sent.
        JsonObject typedOn = Chat(Text, "");
        JsonObject dirty = Chat("", Text);
        dirty["viewBeforeEnter"] = new JsonObject { ["4"] = ComputerUseSuccessCheck.ViewBeforeEnter(Chat(Text, Text), TypedOn(typedOn)) };
        // (b) The text went into the search «Buscar o empezar un chat nuevo»; the Enter emptied it opening its first
        // result: no message was sent.
        const string box = "Escribe un mensaje";
        const string search = "Buscar o empezar un chat nuevo";
        var typing = new JsonObject { ["step"] = 3, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "hola" };
        ComputerUseMission.NoteWhereTheTextGoes(typing, new JsonObject { ["text"] = "hola" }, Box(box, "", search, "", keyboardInBox: false));
        JsonObject opened = Box(box, "", search, "", keyboardInBox: true);
        opened["text"] = new JsonObject { ["main"] = new JsonArray("Juanito", "hola, ¿vienes?") };
        opened["viewBeforeEnter"] = new JsonObject
        {
            ["4"] = ComputerUseSuccessCheck.ViewBeforeEnter(Box(box, "", search, "hola", keyboardInBox: false), new JsonArray { typing }),
        };
        // Counter-case: the message box that took the text emptied, the dirty search still holding it: sent.
        JsonObject emptied = Chat(Text, "");
        emptied["viewBeforeEnter"] = new JsonObject { ["4"] = ComputerUseSuccessCheck.ViewBeforeEnter(Chat(Text, Text), TypedOn(typedOn)) };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Sent(Text, dirty, Enter()), Is.False);
            Assert.That(ComputerUseSuccessCheck.ExactCheckContradicts("stepDone:input.key.press:enter&sent:" + Text, dirty, Enter()), Is.True);
            Assert.That((bool?)opened["viewBeforeEnter"]!["4"]!["intoSearch"], Is.True);
            Assert.That(ComputerUseSuccessCheck.Sent("hola", opened, Enter()), Is.False);
            Assert.That(ComputerUseSuccessCheck.Sent(Text, emptied, Enter()), Is.True);
        });
    }
}
