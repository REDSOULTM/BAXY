using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 24, «un acto sin efecto no prueba nada» (pasada r23): un acto prueba un objetivo sólo con su efecto observado.
/// t-long-1: el Ctrl+V de un procedimiento salió ok 84 ms después de un app.open con robo de foco, la pestaña quedó en
/// «0 caracteres» y el átomo stepDone lo dio por cumplido. t-menu-4: un Enter con la vista idéntica (sameView) contó como
/// acto con efecto. v3-33: «sacá una captura de pantalla completa» se cerró con el ListItem «Pantalla completa» elegido y
/// sin pulsar «Nueva captura de pantalla». Las situaciones son las de la evidencia, recortadas a lo que se juzga.
/// </summary>
[TestFixture]
public sealed class CuV3R24UnActoSinEfectoTests
{
    private const string PasteCheck = "stepDone:input.key.press:ctrl_v|stepDone:input.visible.click:pegar";

    // t-long-1: the application opened (restoring its tabs), then the learned Ctrl+V; the look before the key was the
    // calculator's.
    private static JsonArray PasteSteps() => (JsonArray)JsonNode.Parse("""
        [{"step":7,"operation":"app.open","source":"procedure","appId":"Bloc de notas","ok":true,"changed":true},
         {"step":8,"operation":"input.key.press","source":"procedure","key":"ctrl_v","ok":true,"method":"keyboard"}]
        """)!;

    private static JsonObject Notepad(
        string document, string beforeTitle = "Calculadora", string? beforeDocument = null, string beforeProcess = "CalculatorApp")
    {
        var fields = new JsonArray();
        if (beforeDocument is not null)
        {
            fields.Add((JsonNode)new JsonObject { ["kind"] = "Document", ["name"] = "Editor de texto", ["value"] = beforeDocument });
        }

        return new JsonObject
        {
            ["window"] = new JsonObject
            {
                ["title"] = "Sin título - Bloc de notas",
                ["process"] = "notepad",
                ["foreground"] = true,
                ["focused"] = new JsonObject { ["kind"] = "Document", ["name"] = "Editor de texto", ["value"] = document },
            },
            ["controls"] = new JsonArray(
                new JsonObject { ["i"] = 0, ["kind"] = "TabItem", ["name"] = "Sin título", ["state"] = "selected" },
                new JsonObject { ["i"] = 1, ["kind"] = "Document", ["name"] = "Editor de texto", ["value"] = document },
                new JsonObject { ["i"] = 2, ["kind"] = "Text", ["name"] = $"{document.Length} caracteres" }),
            ["viewBeforeTyping"] = new JsonObject
            {
                ["8"] = new JsonObject
                {
                    ["text"] = new JsonArray(),
                    ["title"] = beforeTitle,
                    ["process"] = beforeProcess,
                    ["fields"] = fields,
                },
            },
        };
    }

    [Test]
    public void TLong1_APasteTheTabDoesNotShowNeverClosesTheSubgoal()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(PasteCheck, Notepad(string.Empty), PasteSteps(), out _), Is.False);
            // On the receipts alone (no look) the paste waits for the look after it.
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(PasteCheck, PasteSteps(), out _), Is.False);
            // The document already held the text before the key: nothing was put.
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                PasteCheck, Notepad("1024", "Sin título - Bloc de notas", "1024"), PasteSteps(), out _), Is.False);
            // A key the window answered with the same view put nothing either.
            JsonArray same = PasteSteps();
            same[1]!["sameView"] = true;
            same[1]!["sameText"] = true;
            Assert.That(ComputerUseSuccessCheck.Evaluate(PasteCheck, Notepad("1024"), same, out _), Is.False);
        });
    }

    // Contracase r15b/r18: the new tab's document holds «1024» after the Ctrl+V, the look before the key was of that
    // window, and the sub-goal closes.
    [Test]
    public void TLong1_Contracase_APasteTheDocumentShowsCloses()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                PasteCheck, Notepad("1024", "Sin título - Bloc de notas", string.Empty, "notepad"), PasteSteps(), out string? by), Is.True);
            Assert.That(by, Does.Contain("stepdone").IgnoreCase);
            // The same window by its process though an edit marked its title as modified.
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                PasteCheck, Notepad("1024", "*Sin título - Bloc de notas", string.Empty, "notepad"), PasteSteps(), out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                PasteCheck, Notepad("hola 1024", "Sin título - Bloc de notas", "hola "), PasteSteps(), out _), Is.True);
        });
    }

    // Revisión 1, hallazgo 3 («pestaña restaurada con texto»): the application opened on a restored tab already holding
    // «lista de compras», the look before the Ctrl+V was the calculator's and the key put nothing. A value that was
    // there when the window came up is no paste: the focused value proves it only against a look of the same window.
    [Test]
    public void Review1_ARestoredTabWithTextIsNoPaste()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(PasteCheck, Notepad("lista de compras"), PasteSteps(), out _), Is.False);
            // Nor does a value that only differs from another window's look.
            Assert.That(ComputerUseSuccessCheck.Evaluate(PasteCheck, Notepad("1024"), PasteSteps(), out _), Is.False);
            // Contracase: the same window before the key, its document changed by the paste.
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                PasteCheck, Notepad("lista de compras 1024", "Sin título - Bloc de notas", "lista de compras", "notepad"),
                PasteSteps(), out _), Is.True);
        });
    }

    // Contracase «copiá el resultado» on the calculator: a copy key closes on its own check, the clipboard never read,
    // though the window kept its signature (its effect is the clipboard, which no look shows).
    [Test]
    public void Contracase_ACopyKeyClosesOnItsOwnCheck()
    {
        const string copyCheck = "stepDone:input.key.press:ctrl_c|stepDone:input.visible.click:copiar";
        var steps = (JsonArray)JsonNode.Parse("""
            [{"step":1,"operation":"input.key.press","key":"ctrl_c","ok":true,"sameView":true}]
            """)!;
        var calculator = (JsonObject)JsonNode.Parse("""
            {"window":{"title":"Calculadora","process":"CalculatorApp"},"controls":[{"i":0,"kind":"Text","name":"La pantalla muestra 1024"}]}
            """)!;
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(copyCheck, steps, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(copyCheck, calculator, steps, out _), Is.True);
            // Estabilización R16: the act with an effect is the mind's reading (cu_evidence.acted_with_effect); the
            // App's own mark says a copy key is never «as it was».
            Assert.That(ComputerUseSuccessCheck.KeyLeftTheViewAsItWas((JsonObject)steps[0]!), Is.False);
        });
    }

    // t-menu-4: an Enter after which the view was identical is no act with an effect; one that changed the view is,
    // and Tab and the Enter after a query stay as they were.
    [Test]
    public void TMenu4_AKeyThatLeftTheViewAsItWasIsNoActWithAnEffect()
    {
        // Estabilización R16: whether such a key is an act with an effect is the mind's reading of the App's mark
        // (cu_evidence.acted_with_effect over key_left_the_view_as_it_was; Tab and the Enter after a query in
        // tests/test_cu_v3_r24_un_acto_sin_efecto.py); here the App's mark.
        JsonObject Key(string json) => (JsonObject)JsonNode.Parse(json)!;
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.KeyLeftTheViewAsItWas(
                Key("""{"operation":"input.key.press","key":"enter","ok":true,"sameView":true,"sameText":true}""")), Is.True);
            // A key the signature sees needs the signature alone.
            Assert.That(ComputerUseSuccessCheck.KeyLeftTheViewAsItWas(
                Key("""{"operation":"input.key.press","key":"escape","ok":true,"sameView":true}""")), Is.True);
            // Contracase: an Enter that sends a search and changes the view still counts.
            Assert.That(ComputerUseSuccessCheck.KeyLeftTheViewAsItWas(
                Key("""{"operation":"input.key.press","key":"enter","ok":true}""")), Is.False);
        });
    }

    // Revisión 3, bloqueante 1: a Ctrl+V on the person's open document, the look before the key of that same window.
    private static JsonArray KeySteps() => (JsonArray)JsonNode.Parse("""
        [{"step":3,"operation":"input.key.press","key":"ctrl_v","ok":true,"method":"keyboard"}]
        """)!;

    private static readonly string LongDocument = new('x', 120);

    private static JsonObject Window(string title, string process, JsonObject? focused, params JsonObject[] controls)
    {
        var list = new JsonArray();
        for (int i = 0; i < controls.Length; i++)
        {
            controls[i]["i"] = i;
            list.Add((JsonNode)controls[i]);
        }

        var window = new JsonObject { ["title"] = title, ["process"] = process, ["foreground"] = true };
        if (focused is not null)
        {
            window["focused"] = focused;
        }

        return new JsonObject { ["window"] = window, ["controls"] = list };
    }

    private static JsonObject Control(string kind, string name, string? value = null, string? state = null)
    {
        var control = new JsonObject { ["kind"] = kind, ["name"] = name };
        if (value is not null)
        {
            control["value"] = value;
        }

        if (state is not null)
        {
            control["state"] = state;
        }

        return control;
    }

    // The look after the key with the look before it recorded as the mission records it (ViewBeforeTyping, with the
    // signature), or as an older record without the signature.
    private static JsonObject After(JsonObject after, JsonObject before, bool signature = true)
    {
        JsonObject recorded = ComputerUseSuccessCheck.ViewBeforeTyping(before);
        if (!signature)
        {
            recorded.Remove("signature");
        }

        after["viewBeforeTyping"] = new JsonObject { ["3"] = recorded };
        return after;
    }

    // (A) a document past the worker's 120-character cut, pasted at its end: the cut value is the same, the title marked
    // as modified and the status bar's count changed. (B) the same with the title unchanged. (C) an editor that exposes
    // no value (TypedTextShows lets its keys stand) whose view changed. (D) a sheet's focused cell whose value became
    // «1024». Each closes on the paste key, with the signature recorded and without it.
    private static IEnumerable<(string Case, JsonObject Before, JsonObject After)> PastesTheSameWindowShows()
    {
        JsonObject Document(string title, int count) => Window(
            title, "notepad", Control("Document", "Editor de texto", LongDocument),
            Control("Document", "Editor de texto", LongDocument), Control("Text", $"{count} caracteres"));
        yield return ("A", Document("notas.txt - Bloc de notas", 500), Document("*notas.txt - Bloc de notas", 504));
        yield return ("B", Document("notas.txt - Bloc de notas", 500), Document("notas.txt - Bloc de notas", 504));

        JsonObject Editor(string sendState) => Window(
            "general - Chat", "chat", Control("Edit", "Mensaje"),
            Control("Edit", "Mensaje"), Control("Button", "Enviar", state: sendState));
        yield return ("C", Editor("disabled"), Editor("enabled"));

        JsonObject Sheet(string cell) => Window(
            "Libro1 - Hoja", "sheet", Control("DataItem", "B2", cell),
            Control("DataItem", "B1", "precio"), Control("DataItem", "B2", cell));
        yield return ("D", Sheet(string.Empty), Sheet("1024"));
    }

    [Test]
    public void Review3_APasteTheSameWindowShowsOnItsSignatureCloses()
    {
        Assert.Multiple(() =>
        {
            foreach ((string name, JsonObject before, JsonObject after) in PastesTheSameWindowShows())
            {
                foreach (bool signature in new[] { true, false })
                {
                    JsonObject view = After(after.DeepClone().AsObject(), before, signature);
                    Assert.That(ComputerUseSuccessCheck.PasteLanded((JsonObject)KeySteps()[0]!, view), Is.True, $"{name} {signature}");
                    Assert.That(ComputerUseSuccessCheck.Evaluate(PasteCheck, view, KeySteps(), out _), Is.True, $"{name} {signature}");
                }
            }
        });
    }

    // Contracases of review 3: the same window whose signature did not change put nothing (a later look, the step not
    // marked); a key the first look found with the same view put nothing; t-long-1, the look before the key another
    // window's, stays refused though everything changed; a focused value shown whole and unchanged put nothing there.
    [Test]
    public void Review3_Contracases_NoChangeOrAnotherWindowIsNoPaste()
    {
        Assert.Multiple(() =>
        {
            foreach ((string name, JsonObject before, JsonObject after) in PastesTheSameWindowShows())
            {
                Assert.That(ComputerUseSuccessCheck.Evaluate(
                    PasteCheck, After(before.DeepClone().AsObject(), before), KeySteps(), out _), Is.False, $"{name} unchanged");

                JsonArray same = KeySteps();
                same[0]!["sameView"] = true;
                // Review 4: the App's mark when the written text read stayed the same too (these windows read none).
                same[0]!["sameText"] = true;
                Assert.That(ComputerUseSuccessCheck.Evaluate(
                    PasteCheck, After(after.DeepClone().AsObject(), before), same, out _), Is.False, $"{name} sameView");

                JsonObject other = Window("Calculadora", "CalculatorApp", null, Control("Text", "La pantalla muestra 1024"));
                Assert.That(ComputerUseSuccessCheck.Evaluate(
                    PasteCheck, After(after.DeepClone().AsObject(), other), KeySteps(), out _), Is.False, $"{name} other window");
            }

            JsonObject Short(string count) => Window(
                "notas.txt - Bloc de notas", "notepad", Control("Document", "Editor de texto", "hola"),
                Control("Document", "Editor de texto", "hola"), Control("Text", count));
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                PasteCheck, After(Short("5 caracteres"), Short("4 caracteres")), KeySteps(), out _), Is.False, "whole value unchanged");
        });
    }

    // Revisión 4, bloqueante 1: the Terminal's frozen view (terminal_tras_ctrl_k: 14 controls, the console text no
    // control's value). The arrow that brings back the last command, the Enter that runs it and a Ctrl+V into the console
    // keep the view's signature, so the App marks them sameView, although the written text read changed.
    private static JsonObject TerminalView(params string[] console)
    {
        string path = Path.Combine(FindRepositoryRoot(), "tests", "data", "cu_v3_vistas_teclas.json");
        var view = (JsonObject)JsonNode.Parse(File.ReadAllText(path))!["terminal_tras_ctrl_k"]!["vista"]!.DeepClone();
        var lines = (JsonArray)view["text"]!["TL"]!;
        foreach (string line in console)
        {
            lines.Add((JsonNode?)JsonValue.Create(line));
        }

        return view;
    }

    private static string Text(JsonObject view) =>
        string.Join('\n', ComputerUseSuccessCheck.TextLines(view).Select(line => (string?)line));

    [Test]
    public void Review4_TheTerminalsEnterThatRanACommandIsAnActThoughTheSignatureKept()
    {
        JsonObject before = TerminalView();
        JsonObject recalled = TerminalView(@"PS C:\Users\usuario> ipconfig");
        JsonObject ran = TerminalView(@"PS C:\Users\usuario> ipconfig", "Configuracion IP de Windows", "Adaptador de Ethernet Ethernet:");
        var steps = (JsonArray)JsonNode.Parse("""
            [{"step":1,"operation":"app.open","appId":"Terminal","ok":true,"changed":true},
             {"step":2,"operation":"input.key.press","key":"arrow_up","ok":true,"method":"keyboard"}]
            """)!;
        // The mission's own marks, look by look: the arrow, then the Enter.
        var state = new JsonObject
        {
            ["lastSignature"] = ComputerUseMission.ViewSignature(before),
            ["lastSignatureText"] = Text(before),
        };
        ComputerUseMission.MarkSameView(state, steps, 1, ComputerUseMission.ViewSignature(recalled), false, Text(recalled));
        state["lastSignature"] = ComputerUseMission.ViewSignature(recalled);
        state["lastSignatureText"] = Text(recalled);
        steps.Add((JsonNode)JsonNode.Parse("""{"step":3,"operation":"input.key.press","key":"enter","ok":true,"method":"keyboard"}""")!);
        ComputerUseMission.MarkSameView(state, steps, 1, ComputerUseMission.ViewSignature(ran), false, Text(ran));
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.ViewSignature(ran), Is.EqualTo(ComputerUseMission.ViewSignature(before)));
            Assert.That((bool?)steps[1]!["sameView"], Is.True);
            Assert.That((bool?)steps[2]!["sameView"], Is.True);
            Assert.That(steps[2]!["sameText"], Is.Null);
            Assert.That(ComputerUseSuccessCheck.KeyLeftTheViewAsItWas((JsonObject)steps[1]!), Is.False);
            Assert.That(ComputerUseSuccessCheck.KeyLeftTheViewAsItWas((JsonObject)steps[2]!), Is.False);
            // Estabilización R16: so the mind's acted_with_effect counts them (test_review_4_the_terminal_command_an_
            // enter_ran_is_an_act_though_the_signature_kept, tests/test_cu_v3_r24_un_acto_sin_efecto.py).
        });

        // Contracase: an Enter after which the console read the same too did nothing a look sees, and the mark reaches
        // the mind. A caret or undo key is never «as it was», with or without the text.
        var still = (JsonArray)JsonNode.Parse("""
            [{"step":1,"operation":"input.key.press","key":"enter","ok":true,"method":"keyboard"}]
            """)!;
        var looked = new JsonObject { ["lastSignature"] = ComputerUseMission.ViewSignature(ran), ["lastSignatureText"] = Text(ran) };
        ComputerUseMission.MarkSameView(looked, still, 0, ComputerUseMission.ViewSignature(ran), false, Text(ran));
        Assert.Multiple(() =>
        {
            Assert.That((bool?)still[0]!["sameText"], Is.True);
            Assert.That((bool?)ComputerUseMission.HistoryForMind(still, 0)[0]!["sameText"], Is.True);
            Assert.That(ComputerUseSuccessCheck.KeyLeftTheViewAsItWas((JsonObject)still[0]!), Is.True);
            Assert.That(ComputerUseSuccessCheck.KeyLeftTheViewAsItWas((JsonObject)JsonNode.Parse(
                """{"operation":"input.key.press","key":"arrow_up","ok":true,"sameView":true,"sameText":true}""")!), Is.False);
            Assert.That(ComputerUseSuccessCheck.KeyLeftTheViewAsItWas((JsonObject)JsonNode.Parse(
                """{"operation":"input.key.press","key":"ctrl_z","ok":true,"sameView":true,"sameText":true}""")!), Is.False);
        });
    }

    // Revisión 4, bloqueante 1 (PasteLanded): a Ctrl+V into the Terminal's console keeps the signature (sameView) and the
    // pasted line shows in the written text read: the paste closes. Contracases: the console read the same, or the look
    // before the key another window's.
    [Test]
    public void Review4_APasteIntoTheTerminalsConsoleShowsOnTheWrittenText()
    {
        JsonObject before = TerminalView(@"PS C:\Users\usuario>");
        JsonObject after = TerminalView(@"PS C:\Users\usuario> ipconfig /all");
        JsonArray Pasted(bool sameText)
        {
            var steps = (JsonArray)JsonNode.Parse("""
                [{"step":3,"operation":"input.key.press","key":"ctrl_v","ok":true,"method":"keyboard","sameView":true}]
                """)!;
            if (sameText)
            {
                steps[0]!["sameText"] = true;
            }

            return steps;
        }

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.ViewSignature(after), Is.EqualTo(ComputerUseMission.ViewSignature(before)));
            JsonObject view = After(after.DeepClone().AsObject(), before);
            Assert.That(ComputerUseSuccessCheck.PasteLanded((JsonObject)Pasted(false)[0]!, view), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(PasteCheck, view, Pasted(false), out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.KeyLeftTheViewAsItWas((JsonObject)Pasted(false)[0]!), Is.False);
            // The console read the same: nothing was pasted.
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                PasteCheck, After(before.DeepClone().AsObject(), before), Pasted(true), out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                PasteCheck, After(before.DeepClone().AsObject(), before), Pasted(false), out _), Is.False);
            // Another window before the key stays refused.
            JsonObject other = Window("Calculadora", "CalculatorApp", null, Control("Text", "La pantalla muestra 1024"));
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                PasteCheck, After(after.DeepClone().AsObject(), other), Pasted(false), out _), Is.False);
        });
    }

    private static string FindRepositoryRoot()
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Baxy.slnx")))
        {
            directory = directory.Parent;
        }

        return directory?.FullName ?? throw new DirectoryNotFoundException("Baxy.slnx was not found.");
    }
}
