using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Goal v3 point 2, the shell side of the new types of task (cu-v3 r2 diag_tipos §2.B): a form's text goes to the
/// field its label names in this view (or nowhere), and a click that confirms writing over an existing file is marked
/// for RiskPolicy from the view it was decided on.
/// </summary>
[TestFixture]
public sealed class ComputerUseTiposTests
{
    private static JsonObject View(string json) => (JsonObject)JsonNode.Parse(json)!;

    private static readonly string ResizeDialog = """
        {
          "window": {"title": "Cambiar tamaño", "process": "x", "processId": 55, "hwnd": 8, "requested": true,
                     "focused": {"kind": "Edit", "name": "Horizontal", "i": 1}},
          "controls": [
            {"i": 0, "kind": "RadioButton", "name": "Porcentaje", "state": ""},
            {"i": 1, "kind": "Edit", "name": "Horizontal", "state": "focused", "value": "1366"},
            {"i": 2, "kind": "Edit", "name": "Vertical:", "state": "", "value": "768"},
            {"i": 3, "kind": "ComboBox", "name": "Fuente", "state": "", "value": "Calibri"},
            {"i": 4, "kind": "Edit", "name": "Clave", "state": "password"},
            {"i": 5, "kind": "Button", "name": "Aceptar", "state": ""}
          ]
        }
        """;

    // «poner vertical en 600»: the field the label names, not the focused one; a trailing colon of the label is the
    // label's. A combo box takes it too.
    [TestCase("Vertical", 2)]
    [TestCase("vertical", 2)]
    // The label as the view writes it (the mind may send the control's name with its colon): both sides fold alike.
    [TestCase("Vertical:", 2)]
    [TestCase("Vertical :", 2)]
    [TestCase("Fuente:", 3)]
    [TestCase("Horizontal", 1)]
    [TestCase("Fuente", 3)]
    public void ATextThatNamesItsFieldGoesToThatField(string label, int expected)
    {
        var arguments = new JsonObject { ["text"] = "600", ["field"] = label, ["replace"] = true };

        bool bound = ComputerUseMission.BindToMissionWindow("input.text.type", arguments, View(ResizeDialog), new JsonObject(), null);

        Assert.Multiple(() =>
        {
            Assert.That(bound, Is.True);
            Assert.That((int?)arguments["index"], Is.EqualTo(expected));
            Assert.That((long?)arguments["window"], Is.EqualTo(8));
        });
    }

    // Integration of round 2 (tipos-lectura + tipos-uia): two fields of one name (Paint's size group and skew group both
    // say «Horizontal») take the first in the view's reading order, the field the mind's «poner ancho en 800» names;
    // never left without a field nor to the focus. Counter-case: the other order gives the other field.
    [TestCase(10, 20, 10)]
    [TestCase(20, 10, 20)]
    public void TwoFieldsOfOneNameTakeTheFirstInReadingOrder(int first, int second, int expected)
    {
        JsonObject view = View($$"""
            {"window": {"title": "Cambiar tamaño", "process": "mspaint", "processId": 5, "hwnd": 8, "requested": true},
             "controls": [
               {"i": {{first}}, "kind": "Edit", "name": "Horizontal", "state": "", "value": "100"},
               {"i": {{second}}, "kind": "Edit", "name": "Horizontal", "state": "", "value": "0"}
             ]}
            """);
        var arguments = new JsonObject { ["text"] = "800", ["field"] = "Horizontal", ["replace"] = true };

        Assert.That(ComputerUseMission.BindToMissionWindow("input.text.type", arguments, view, new JsonObject(), null), Is.True);
        Assert.That((int?)arguments["index"], Is.EqualTo(expected));
    }

    // Contract «Seguridad v2»: a window the view marks as a developer's or BAXY's own (VS Code, a terminal, BAXY, told
    // by its process) takes no key, text, click, scroll or drag, also when the mission names no application and works
    // on the window in front. Counter-case: the same act on an unmarked window in front is bound to it when the person
    // named that window as the destination (frontWindow, integración ronda 5).
    [TestCase("input.text.type")]
    [TestCase("input.key.press")]
    [TestCase("input.visible.click")]
    [TestCase("input.scroll")]
    public void AProtectedWindowInFrontTakesNoActEvenWithNoApplicationNamed(string operation)
    {
        JsonObject Editor(bool marked) => View($$$"""
            {"window": {"title": "ComputerUseMission.cs - BAXY - Visual Studio Code", "process": "Code", "processId": 77,
                        "hwnd": 999, "requested": false{{{(marked ? ", \"protected\": true" : string.Empty)}}},
                        "focused": {"kind": "Document", "name": "editor", "i": 0}},
             "controls": [{"i": 0, "kind": "Document", "name": "editor", "state": "focused"}]}
            """);
        var arguments = new JsonObject { ["text"] = "baxy-x.txt", ["key"] = "ctrl_s", ["label"] = "editor" };

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.BindToMissionWindow(operation, arguments, Editor(true), new JsonObject { ["frontWindow"] = true }, null), Is.False);
            Assert.That(arguments["window"], Is.Null);
            Assert.That(ComputerUseMission.ProtectedWindow(Editor(true)), Is.True);
            // Goal v3 destino, extended by the round-5 integration: with no application resolved no act goes to the
            // window in front (the person's) unless the person named it; then an unmarked one takes it.
            Assert.That(ComputerUseMission.BindToMissionWindow(operation, arguments, Editor(false), new JsonObject(), null), Is.False);
            Assert.That(arguments["window"], Is.Null);
            Assert.That(ComputerUseMission.BindToMissionWindow(operation, arguments, Editor(false), new JsonObject { ["frontWindow"] = true }, null), Is.True);
            Assert.That((long?)arguments["window"], Is.EqualTo(999));
        });
    }

    // Contracases: a label no field of the view carries, a password field, or a button never falls back to the focused
    // field; the provider then refuses the text (input_field_not_found). Without a label the focused field still takes it.
    [TestCase("Ancho")]
    [TestCase("Clave")]
    [TestCase("Aceptar")]
    public void ANamedFieldThisViewDoesNotHaveIsNoField(string label)
    {
        var arguments = new JsonObject { ["text"] = "600", ["field"] = label };

        _ = ComputerUseMission.BindToMissionWindow("input.text.type", arguments, View(ResizeDialog), new JsonObject(), null);

        Assert.That(arguments["index"], Is.Null);
    }

    // Guardar como: the file name box is a combo box labelled «Nombre de archivo:» on screen; the label the mind sends
    // for it, with or without the colon, reaches it, and «Tipo:» (another combo box) is not it.
    [TestCase("Nombre de archivo:", 1)]
    [TestCase("Nombre de archivo", 1)]
    [TestCase("nombre de archivo", 1)]
    [TestCase("Tipo:", 2)]
    public void TheSaveAsFileNameBoxTakesTheLabelWithItsColon(string label, int expected)
    {
        JsonObject view = View("""
            {
              "window": {"title": "Guardar como", "process": "x", "processId": 55, "hwnd": 8, "requested": true},
              "controls": [
                {"i": 0, "kind": "Button", "name": "Guardar", "state": ""},
                {"i": 1, "kind": "ComboBox", "name": "Nombre de archivo:", "state": "", "value": "*.txt"},
                {"i": 2, "kind": "ComboBox", "name": "Tipo:", "state": "", "value": "Documentos de texto"}
              ]
            }
            """);
        var arguments = new JsonObject { ["text"] = "notas.txt", ["field"] = label, ["replace"] = true };

        _ = ComputerUseMission.BindToMissionWindow("input.text.type", arguments, view, new JsonObject(), null);

        Assert.That((int?)arguments["index"], Is.EqualTo(expected));
    }

    // Contracase: the colon is trimmed, not any word: «Nombre» alone names no field of the view.
    [Test]
    public void ALabelThatIsOnlyPartOfTheFieldNameIsNoField()
    {
        JsonObject view = View("""
            {"window": {"hwnd": 8, "requested": true},
             "controls": [{"i": 1, "kind": "ComboBox", "name": "Nombre de archivo:", "state": ""}]}
            """);
        var arguments = new JsonObject { ["text"] = "notas.txt", ["field"] = "Nombre:" };

        _ = ComputerUseMission.BindToMissionWindow("input.text.type", arguments, view, new JsonObject(), null);

        Assert.That(arguments["index"], Is.Null);
    }

    [Test]
    public void WithoutALabelTheFocusedFieldTakesTheText()
    {
        var arguments = new JsonObject { ["text"] = "600" };

        _ = ComputerUseMission.BindToMissionWindow("input.text.type", arguments, View(ResizeDialog), new JsonObject(), null);

        Assert.That((int?)arguments["index"], Is.EqualTo(1));
    }

    private static JsonObject Dialog(string message, params string[] buttons)
    {
        var controls = new JsonArray { new JsonObject { ["i"] = 0, ["kind"] = "Text", ["name"] = message } };
        for (int k = 0; k < buttons.Length; k++)
            controls.Add(new JsonObject { ["i"] = k + 1, ["kind"] = "Button", ["name"] = buttons[k] });
        return new JsonObject
        {
            ["window"] = new JsonObject { ["title"] = "Confirmar Guardar como", ["processId"] = 55, ["hwnd"] = 8L, ["requested"] = true },
            ["controls"] = controls,
        };
    }

    // «notas.txt ya existe. ¿Desea reemplazarlo?» → «Sí»: the click is marked as writing over the file.
    [TestCase("notas.txt ya existe.\n¿Desea reemplazarlo?", "Sí", true)]
    [TestCase("notes.txt already exists. Do you want to replace it?", "Yes", true)]
    [TestCase("El archivo ya existe en el destino", "Reemplazar el archivo", true)]
    // The file Explorer's copy/move conflict: a longer confirming button, and a warning worded «ya tiene un archivo».
    [TestCase("El destino ya tiene un archivo denominado «a.txt»", "Reemplazar el archivo en el destino", true)]
    [TestCase("The destination already has a file named \"a.txt\"", "Replace the file in the destination", true)]
    [TestCase("El destino ya tiene un archivo denominado «a.txt»", "Sí, reemplazar", true)]
    [TestCase("notas.txt ya existe.\n¿Desea reemplazarlo?", "Reemplazar archivo", true)]
    // Contracases: skipping the file on the same conflict, and a long sentence that starts with «Sí» is no button.
    [TestCase("El destino ya tiene un archivo denominado «a.txt»", "Omitir este archivo", false)]
    [TestCase("El destino ya tiene un archivo denominado «a.txt»", "Sí, quiero ver la información de los dos archivos antes", false)]
    // Contracases: «No» on the same dialog; a «Sí» with no overwrite warning; the Replace dialog's «Reemplazar todo».
    [TestCase("notas.txt ya existe.\n¿Desea reemplazarlo?", "No", false)]
    [TestCase("¿Desea guardar los cambios de Sin título?", "Sí", false)]
    [TestCase("Buscar: casa", "Reemplazar todo", false)]
    public void AClickThatWritesOverAFileIsMarkedFromItsView(string message, string label, bool overwrite)
    {
        JsonObject view = Dialog(message, "Sí", "No", "Yes", "Reemplazar el archivo", "Reemplazar todo", label);
        var arguments = new JsonObject { ["label"] = label };

        _ = ComputerUseMission.BindToMissionWindow("input.visible.click", arguments, view, new JsonObject(), null);

        Assert.That((string?)arguments["consequence"], Is.EqualTo(overwrite ? "overwrite" : null));
    }

    // The mark is the view's, never the step's: a learned or model step that carried one is read again.
    [Test]
    public void AConsequenceTheStepBroughtIsReadAgainFromTheView()
    {
        var arguments = new JsonObject { ["label"] = "Sí", ["consequence"] = "overwrite" };

        _ = ComputerUseMission.BindToMissionWindow(
            "input.visible.click", arguments, Dialog("¿Desea guardar los cambios?", "Sí"), new JsonObject(), null);

        Assert.That(arguments["consequence"], Is.Null);
    }

    // The overwrite warning may be written on screen (the view's text zones) instead of a text control.
    [Test]
    public void TheWarningMayBeWrittenTextOfTheView()
    {
        JsonObject view = Dialog("Confirmar", "Sí");
        view["text"] = new JsonObject { ["center"] = new JsonArray("Informe.docx ya existe.", "¿Desea reemplazarlo?") };
        var arguments = new JsonObject { ["label"] = "Sí" };

        _ = ComputerUseMission.BindToMissionWindow("input.visible.click", arguments, view, new JsonObject(), null);

        Assert.That((string?)arguments["consequence"], Is.EqualTo("overwrite"));
    }

    private static JsonObject Focused(JsonObject view, string? name)
    {
        if (name is not null)
            ((JsonObject)view["window"]!)["focused"] = new JsonObject { ["kind"] = "Button", ["name"] = name, ["i"] = 1 };
        return view;
    }

    // Enter or Space on the focused «Sí» of the overwrite warning writes over the file as the click does: marked. With
    // no focus reported, a view that warns and has a confirming button is marked (the key may land on it).
    [TestCase("notas.txt ya existe.\n¿Desea reemplazarlo?", "Sí", "enter", true)]
    [TestCase("notas.txt ya existe.\n¿Desea reemplazarlo?", "Sí", "space", true)]
    [TestCase("The destination already has a file named \"a.txt\"", "Replace the file in the destination", "enter", true)]
    [TestCase("notas.txt ya existe.\n¿Desea reemplazarlo?", null, "enter", true)]
    // Contracases: the focused «No»; Tab only moves the focus; a «Sí» with no overwrite warning.
    [TestCase("notas.txt ya existe.\n¿Desea reemplazarlo?", "No", "enter", false)]
    [TestCase("notas.txt ya existe.\n¿Desea reemplazarlo?", "Sí", "tab", false)]
    [TestCase("¿Desea guardar los cambios de Sin título?", "Sí", "enter", false)]
    public void AKeyOnTheFocusedConfirmingButtonIsMarkedFromItsView(string message, string? focused, string key, bool overwrite)
    {
        JsonObject view = Focused(Dialog(message, "Sí", "No", "Replace the file in the destination"), focused);
        var arguments = new JsonObject { ["key"] = key };

        _ = ComputerUseMission.BindToMissionWindow("input.key.press", arguments, view, new JsonObject(), null);

        Assert.That((string?)arguments["consequence"], Is.EqualTo(overwrite ? "overwrite" : null));
    }

    // Contracase: with no focus reported, a warning view whose only buttons decline is not marked; a key's mark the
    // step brought is read again from the view.
    [Test]
    public void AKeyWithNoConfirmingButtonOnTheViewIsNotMarked()
    {
        var arguments = new JsonObject { ["key"] = "enter", ["consequence"] = "overwrite" };

        _ = ComputerUseMission.BindToMissionWindow(
            "input.key.press", arguments, Dialog("notas.txt ya existe.\n¿Desea reemplazarlo?", "No", "Cancelar"), new JsonObject(), null);

        Assert.That(arguments["consequence"], Is.Null);
    }
}
