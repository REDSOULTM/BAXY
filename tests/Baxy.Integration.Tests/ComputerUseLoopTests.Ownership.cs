using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 24, lo que la misión creó es suyo (pasada r23: v3-11 t1, v3-34, v3-35, t-form-2). Ownership follows what the
/// mission created and verified, document by document; a field is never an order; a window whose opening restored the
/// person's content is not the mission's.
/// </summary>
public sealed partial class ComputerUseLoopTests
{
    private const string NewPageRequest = "en onenote crea una pagina nueva y escribe comprar pan";

    private static JsonObject NotesPage(string title, long hwnd = 3003)
    {
        JsonObject view = Window(title, "ONENOTE", 70, true,
            [Control(0, "Button", "Agregar página"), Control(1, "ListItem", "Lista del super"),
             Control(2, "ListItem", "Recetas"), Control(3, "Document", "Página")]);
        view["window"]!["rect"] = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 1600, ["h"] = 900 };
        return Tied(view, hwnd, 4004);
    }

    // OneNote already open on the person's «Lista del super» (not started by the mission, another window of its
    // process): the mission is tied to it and owns nothing of it.
    private static (JsonObject State, JsonArray Steps) TiedToTheOwnersPage()
    {
        var state = new JsonObject { ["objective"] = NewPageRequest, ["application"] = "OneNote" };
        var steps = new JsonArray();
        state["steps"] = steps;
        JsonObject first = NotesPage("Lista del super - OneNote");
        ComputerUseMission.AdoptWindow(state, "OneNote", first);
        ComputerUseMissionWindow.Tie(state, "OneNote", first, ofTheApplication: true, steps);
        return (state, steps);
    }

    private static JsonObject Click(int step, string label, string titleBefore) => new()
    {
        ["step"] = step,
        ["operation"] = "input.visible.click",
        ["label"] = label,
        ["ok"] = true,
        ["titleBefore"] = titleBefore,
    };

    [Test]
    public void V311APageTheMissionCreatedIsItsOwnWhileTheWindowShowsIt()
    {
        (JsonObject state, JsonArray steps) = TiedToTheOwnersPage();
        JsonObject untitled = NotesPage("Sin título - OneNote");
        var text = new JsonObject { ["text"] = "comprar pan" };
        Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.text.type", text, untitled, state), Is.True,
            "before the click nothing of the window is the mission's");

        steps.Add(Click(1, "Agregar página", "Lista del super - OneNote"));
        ComputerUseMissionWindow.NoteCreatedDocument(state, untitled, steps);
        Assert.Multiple(() =>
        {
            Assert.That((string?)steps[0]!["createdDocument"], Is.EqualTo("Sin título"));
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.text.type", text, untitled, state), Is.False);
            Assert.That(ComputerUseMission.BindToMissionWindow("input.text.type", text, untitled, state, "OneNote"), Is.True);
        });

        // Contracase: navigating from the created page to one that was there drops the exemption.
        JsonObject existing = NotesPage("Lista del super - OneNote");
        Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.text.type", text, existing, state), Is.True);
    }

    [Test]
    public void V311ASelectedExistingPageIsNeverTheMissions()
    {
        // Contracase: a mission that only selected an existing page and then types is still refused.
        (JsonObject state, JsonArray steps) = TiedToTheOwnersPage();
        JsonObject recipes = NotesPage("Recetas - OneNote");
        steps.Add(Click(1, "Recetas", "Lista del super - OneNote"));
        ComputerUseMissionWindow.NoteCreatedDocument(state, recipes, steps);
        Assert.That(state["createdDocuments"], Is.Null);
        Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.text.type", new JsonObject { ["text"] = "pan" }, recipes, state),
            Is.True);

        // An existing untitled page chosen by its own name, and an untitled title the window already showed when the
        // mission took it, are no creation either.
        (JsonObject chosenState, JsonArray chosenSteps) = TiedToTheOwnersPage();
        JsonObject untitled = NotesPage("Sin título - OneNote");
        chosenSteps.Add(Click(1, "Sin título", "Lista del super - OneNote"));
        chosenSteps[0]!["broughtNew"] = true;
        ComputerUseMissionWindow.NoteCreatedDocument(chosenState, untitled, chosenSteps);
        Assert.That(chosenState["createdDocuments"], Is.Null, "the click named the page");

        var shownState = new JsonObject { ["objective"] = NewPageRequest, ["application"] = "OneNote" };
        var shownSteps = new JsonArray();
        ComputerUseMissionWindow.Tie(shownState, "OneNote", NotesPage("Sin título - OneNote"), ofTheApplication: true, shownSteps);
        shownSteps.Add(Click(1, "Agregar página", "Sin título - OneNote"));
        ComputerUseMissionWindow.NoteCreatedDocument(shownState, untitled, shownSteps);
        Assert.That(shownState["createdDocuments"], Is.Null, "the first look already showed it");
    }

    private const string ReplaceRequest = "reemplazá casa por hogar en el bloc de notas";

    private static JsonObject NotepadWithReplace(string title)
    {
        var document = Control(0, "Document", "Editor de texto", "", "la casa roja, la casa azul, mi casa es tu casa");
        JsonObject view = Window(title, "Notepad", 80, true,
            [document, Control(1, "Edit", "Buscar"), Control(2, "Edit", "Reemplazar"),
             Control(3, "Button", "Reemplazar"), Control(4, "Button", "Reemplazar todo"), Control(5, "TabItem", "pendientes")]);
        view["window"]!["rect"] = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 1200, ["h"] = 800 };
        return Tied(view, 5005, 5006);
    }

    private static JsonObject NotepadTied(string objective, JsonObject view)
    {
        var state = new JsonObject { ["objective"] = objective, ["application"] = "Bloc de notas" };
        ComputerUseMissionWindow.Tie(state, "Bloc de notas", view, ofTheApplication: true, []);
        return state;
    }

    [Test]
    public void TForm2AFieldIsNeverAnOrderAndTheRequestedReplaceGoesOnTheTiedDocument()
    {
        JsonObject view = NotepadWithReplace("pendientes - Bloc de notas");
        JsonObject state = NotepadTied(ReplaceRequest, view);
        Assert.Multiple(() =>
        {
            Assert.That(state["created"], Is.Null);
            Assert.That(state["named"], Is.Null);
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.visible.click", new JsonObject { ["label"] = "Reemplazar", ["index"] = 2 }, view, state),
                Is.False, "the «Reemplazar» field");
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.visible.click", new JsonObject { ["label"] = "Reemplazar todo", ["index"] = 4 }, view, state),
                Is.False, "the replace the request names");
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.visible.click", new JsonObject { ["label"] = "Reemplazar", ["index"] = 3 }, view, state),
                Is.False, "the «Reemplazar» button, a replace the request names");
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.visible.click", new JsonObject { ["label"] = "Pegar" }, view, state),
                Is.True, "a class the request does not name");
        });
    }

    [Test]
    public void TForm2ASearchNeverReplacesAndAnotherTabIsNotTheTiedDocument()
    {
        // Contracase: «buscá» names no replace.
        JsonObject view = NotepadWithReplace("pendientes - Bloc de notas");
        JsonObject searching = NotepadTied("en el bloc de notas buscá «casa»", view);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.visible.click", new JsonObject { ["label"] = "Reemplazar todo" }, view, searching),
                Is.True);
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.visible.click", new JsonObject { ["label"] = "Reemplazar" }, view, searching),
                Is.False, "a field is still no order");
        });

        // Contracase: another tab than the one shown when the mission took the window.
        JsonObject replacing = NotepadTied(ReplaceRequest, view);
        JsonObject otherTab = NotepadWithReplace("diario - Bloc de notas");
        Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.visible.click", new JsonObject { ["label"] = "Reemplazar todo" }, otherTab, replacing),
            Is.True);
    }

    private static JsonArray Opened() =>
        new(new JsonObject { ["step"] = 1, ["operation"] = "app.open", ["appId"] = "x", ["ok"] = true });

    private static JsonObject NoteWindow(string? value, string title = "Notas")
    {
        var editor = Control(3, "Edit", "Editor de notas", "focused", value);
        editor["rect"] = new JsonObject { ["x"] = 0, ["y"] = 40, ["w"] = 400, ["h"] = 360 };
        JsonObject view = Window(title, "Notes", 90, true, [Control(0, "Button", "Nueva nota"), editor]);
        view["window"]!["rect"] = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 400, ["h"] = 400 };
        return Tied(view, 7007);
    }

    [Test]
    public void V334AnOpeningThatRestoredThePersonsContentIsNotTheMissions()
    {
        JsonObject restored = NoteWindow("baxy prueba");
        var state = new JsonObject { ["objective"] = "abre notas y crea una nota que diga llamar al dentista", ["application"] = "Notas" };
        ComputerUseMissionWindow.Tie(state, "Notas", restored, ofTheApplication: true, Opened());
        var text = new JsonObject { ["text"] = "llamar al dentista" };
        Assert.Multiple(() =>
        {
            Assert.That(state["created"], Is.Null);
            Assert.That(state["sole"], Is.Null, "restored is never sole");
            Assert.That(ComputerUseMissionWindow.Restored(state, restored), Is.True);
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.text.type", text, restored, state), Is.True);
            Assert.That(ComputerUseMission.ForeignDocumentCause("input.text.type", text, restored: true),
                Is.EqualTo("computer_use_document_restored"));
        });
    }

    // r26: the mind's «escribir» names the one field by its label (no click first, the editor without the keyboard
    // behind the person's window). The label is resolved to that field of this view, and the same guard holds: the
    // person's content an opening restored takes no text; the new, empty window of the mission takes it by its index.
    [Test]
    public void R26ATextNamedForTheEditorWithoutTheKeyboardGoesToItsIndexAndNeverToRestoredContent()
    {
        static JsonObject Behind(JsonObject view)
        {
            view["window"]!["foreground"] = false;
            ((JsonObject)view["controls"]![1]!)["state"] = string.Empty;
            return view;
        }

        JsonObject restored = Behind(NoteWindow("baxy prueba"));
        var theirs = new JsonObject { ["objective"] = "abre notas y escribe hola", ["application"] = "Notas" };
        ComputerUseMissionWindow.Tie(theirs, "Notas", restored, ofTheApplication: true, Opened());
        JsonObject empty = Behind(NoteWindow(string.Empty));
        var mine = new JsonObject { ["objective"] = "abre notas y escribe hola", ["application"] = "Notas" };
        ComputerUseMissionWindow.Tie(mine, "Notas", empty, ofTheApplication: true, Opened());
        var refused = new JsonObject { ["text"] = "hola", ["field"] = "Editor de notas" };
        var typed = new JsonObject { ["text"] = "hola", ["field"] = "Editor de notas" };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.BindToMissionWindow("input.text.type", refused, restored, theirs, "Notas"), Is.False);
            Assert.That(ComputerUseMission.BindToMissionWindow("input.text.type", typed, empty, mine, "Notas"), Is.True);
            Assert.That((int?)typed["index"], Is.EqualTo(3), "the field the label names, never the window's focus");
            Assert.That((long?)typed["window"], Is.EqualTo(7007));
        });
    }

    [TestCase(null)]
    [TestCase("")]
    [TestCase("Haga clic para agregar texto")]
    public void V334AnOpeningOfAnEmptyOrPlaceholderDocumentIsStillCreated(string? value)
    {
        // Contracase: «abre el bloc de notas y escribe hola» with a new, empty window: created and sole, it writes.
        JsonObject empty = NoteWindow(value);
        var state = new JsonObject { ["objective"] = "abre notas y escribe hola", ["application"] = "Notas" };
        ComputerUseMissionWindow.Tie(state, "Notas", empty, ofTheApplication: true, Opened());
        Assert.Multiple(() =>
        {
            Assert.That(state["restored"], Is.Null);
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.text.type", new JsonObject { ["text"] = "hola" }, empty, state), Is.False);
        });
    }

    [Test]
    public void V334AFileTheMissionOpenedIsStillItsEvenWithText()
    {
        // A file the mission opened shows its content by design: file.open keeps it created.
        JsonObject file = NoteWindow("contenido del archivo", "informe.txt - Notas");
        var state = new JsonObject { ["objective"] = "abre informe y escribe hola", ["application"] = "Notas" };
        var steps = new JsonArray(new JsonObject { ["step"] = 1, ["operation"] = "file.open", ["name"] = "informe.txt", ["ok"] = true });
        ComputerUseMissionWindow.Tie(state, "Notas", file, ofTheApplication: true, steps);
        Assert.That(state["restored"], Is.Null);
    }

    // Revisión 1 de r24 (B1): the page of a web application (WebView2, Electron, CEF, a browser) is a read-only Document
    // whose value is its address; an opening that shows it restored no text of the person's.
    private static JsonObject WebApplication(string documentState, string value)
    {
        var page = Control(1, "Document", "Mensajes", documentState, value);
        page["rect"] = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 1200, ["h"] = 800 };
        JsonObject view = Window("(5) Mensajes", "Mensajes", 91, true, [Control(0, "TabItem", "Todos", "selected focused"), page]);
        view["window"]!["rect"] = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 1200, ["h"] = 800 };
        return Tied(view, 9009);
    }

    [TestCase("readonly", "https://web.mensajes.example/")]
    [TestCase("", "https://web.mensajes.example/")]
    [TestCase("readonly", "Hola, ¿cómo estás?")]
    public void R24B1AWebApplicationTheMissionOpenedIsStillCreated(string documentState, string value)
    {
        JsonObject view = WebApplication(documentState, value);
        var state = new JsonObject { ["objective"] = "abre mensajes y escribe hola", ["application"] = "Mensajes" };
        ComputerUseMissionWindow.Tie(state, "Mensajes", view, ofTheApplication: true, Opened());
        Assert.Multiple(() =>
        {
            Assert.That(state["restored"], Is.Null);
            Assert.That(ComputerUseMissionWindow.Restored(state, view), Is.False);
            Assert.That(state["created"]?.ToJsonString(), Is.EqualTo("[9009]"));
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.text.type", new JsonObject { ["text"] = "hola" }, view, state),
                Is.False);
        });
    }

    [Test]
    public void R24B1AnEditableDocumentWithTextIsStillRestored()
    {
        // Contracase: a document that takes text and shows text (not an address) restored the person's work.
        JsonObject view = WebApplication("", "lista de la compra: pan, leche");
        var state = new JsonObject { ["objective"] = "abre mensajes y escribe hola", ["application"] = "Mensajes" };
        ComputerUseMissionWindow.Tie(state, "Mensajes", view, ofTheApplication: true, Opened());
        Assert.Multiple(() =>
        {
            Assert.That(state["created"], Is.Null);
            Assert.That(ComputerUseMissionWindow.Restored(state, view), Is.True);
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.text.type", new JsonObject { ["text"] = "hola" }, view, state),
                Is.True);
        });
    }

    // Revisión 1 de r24 (B2): OneNote on the person's «Lista del super», its page list showing the person's own
    // «Sin título» (or not), and a section tab «Trabajo».
    private static JsonObject NotesWithSections(string title, bool listsUntitled)
    {
        var controls = new JsonArray(Control(0, "Button", "Agregar página"), Control(1, "TabItem", "Trabajo"),
            Control(2, "ListItem", "Lista del super"), Control(3, "Document", "Página"));
        if (listsUntitled)
            controls.Add(Control(4, "ListItem", "Sin título"));
        JsonObject view = Window(title, "ONENOTE", 70, true, controls);
        view["window"]!["rect"] = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 1600, ["h"] = 900 };
        return Tied(view, 3003, 4004);
    }

    private static (JsonObject State, JsonArray Steps) TiedToSections(bool listsUntitled)
    {
        var state = new JsonObject { ["objective"] = NewPageRequest, ["application"] = "OneNote" };
        var steps = new JsonArray();
        state["steps"] = steps;
        JsonObject first = NotesWithSections("Lista del super - OneNote", listsUntitled);
        ComputerUseMission.AdoptWindow(state, "OneNote", first);
        ComputerUseMissionWindow.Tie(state, "OneNote", first, ofTheApplication: true, steps);
        return (state, steps);
    }

    [TestCase(true)]
    [TestCase(false)]
    public void R24B2ASectionClickLandingOnAnExistingUntitledPageCreatedNothing(bool listsUntitled)
    {
        (JsonObject state, JsonArray steps) = TiedToSections(listsUntitled);
        steps.Add(Click(1, "Trabajo", "Lista del super - OneNote"));
        steps[0]!["broughtNew"] = true;
        JsonObject landed = NotesWithSections("Sin título - OneNote", listsUntitled: true);
        ComputerUseMissionWindow.NoteCreatedDocument(state, landed, steps);
        Assert.Multiple(() =>
        {
            Assert.That(state["createdDocuments"], Is.Null);
            Assert.That(steps[0]!["createdDocument"], Is.Null, "the final may not say it created that page");
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.text.type", new JsonObject { ["text"] = "pan" }, landed, state),
                Is.True);
        });
    }

    [Test]
    public void R24B2AnUntitledPageAnEarlierLookListedIsNeverCreated()
    {
        // Even a creating command proves nothing of a page the look the mission tied on already listed (twin of
        // _created_by_diff over firstLook); nor of one the sub-goal's first look or the look before a click showed.
        (JsonObject state, JsonArray steps) = TiedToSections(listsUntitled: true);
        steps.Add(Click(1, "Agregar página", "Lista del super - OneNote"));
        JsonObject untitled = NotesWithSections("Sin título - OneNote", listsUntitled: true);
        ComputerUseMissionWindow.NoteCreatedDocument(state, untitled, steps);
        Assert.That(state["createdDocuments"], Is.Null, "the look the mission tied on");

        (JsonObject firstLookState, JsonArray firstLookSteps) = TiedToSections(listsUntitled: false);
        firstLookState["subgoalFirstText"] = "lista del super - onenote\nsin titulo\n";
        firstLookSteps.Add(Click(1, "Agregar página", "Lista del super - OneNote"));
        ComputerUseMissionWindow.NoteCreatedDocument(firstLookState, untitled, firstLookSteps);
        Assert.That(firstLookState["createdDocuments"], Is.Null, "the sub-goal's first look");

        (JsonObject beforeState, JsonArray beforeSteps) = TiedToSections(listsUntitled: false);
        beforeSteps.Add(Click(1, "Agregar página", "Lista del super - OneNote"));
        JsonObject withBefore = NotesWithSections("Sin título - OneNote", listsUntitled: true);
        withBefore["controlsBeforeClick"] = new JsonObject { ["1"] = new JsonArray("agregar pagina", "sin titulo") };
        ComputerUseMissionWindow.NoteCreatedDocument(beforeState, withBefore, beforeSteps);
        Assert.That(beforeState["createdDocuments"], Is.Null, "the look before the click");

        // Contracase: a command that brought new controls and a page no look showed is the mission's.
        (JsonObject newState, JsonArray newSteps) = TiedToSections(listsUntitled: false);
        newSteps.Add(Click(1, "+", "Lista del super - OneNote"));
        newSteps[0]!["broughtNew"] = true;
        JsonObject made = NotesWithSections("Sin título - OneNote", listsUntitled: true);
        ((JsonArray)made["controls"]!).Add(Control(5, "Button", "+"));
        ComputerUseMissionWindow.NoteCreatedDocument(newState, made, newSteps);
        Assert.That((string?)newSteps[0]!["createdDocument"], Is.EqualTo("Sin título"));
    }

    // Revisión 1 de r24 (B3): the class the request names is its verb, never a noun of the same root.
    private static JsonObject NotepadWithCommands()
    {
        var document = Control(0, "Document", "Editor de texto", "", "la casa roja, la casa azul");
        JsonObject view = Window("pendientes - Bloc de notas", "Notepad", 80, true,
            [document, Control(1, "Button", "Eliminar"), Control(2, "Button", "Pegar"), Control(3, "Button", "Cortar"),
             Control(4, "Button", "Deshacer"), Control(5, "Button", "Seleccionar todo"), Control(6, "Button", "Reemplazar todo")]);
        view["window"]!["rect"] = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 1200, ["h"] = 800 };
        return Tied(view, 5005, 5006);
    }

    [TestCase("Eliminar", "en el bloc de notas borrá la segunda línea", "en el bloc de notas escribe un borrador de la carta")]
    [TestCase("Eliminar", "en el bloc de notas eliminalo", "en el bloc de notas anota la eliminatoria del sábado")]
    [TestCase("Eliminar", "en el bloc de notas borrando lo de ayer", "en el bloc de notas abre Borradores")]
    [TestCase("Pegar", "en el bloc de notas pegá el texto", "en el bloc de notas escribe pegatina roja")]
    [TestCase("Cortar", "en el bloc de notas cortá la última frase", "en el bloc de notas escribe que el corte de luz es a las cinco")]
    [TestCase("Cortar", "en el bloc de notas cortar la frase", "en el bloc de notas escribe pregúntale a Cortana")]
    [TestCase("Deshacer", "en el bloc de notas deshacé lo último", "en el bloc de notas escribe lo deshecho")]
    [TestCase("Seleccionar todo", "en el bloc de notas seleccioná todo", "en el bloc de notas escribe el seleccionador todo lo ve")]
    [TestCase("Reemplazar todo", "en el bloc de notas reemplazá casa por hogar", "en el bloc de notas escribe el reemplazo de Juan")]
    public void R24B3TheRequestNamesAClassByItsVerbNeverByANoun(string label, string verb, string noun)
    {
        JsonObject view = NotepadWithCommands();
        var click = new JsonObject { ["label"] = label };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.visible.click", click, view, NotepadTied(verb, view)),
                Is.False, verb);
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.visible.click", click, view, NotepadTied(noun, view)),
                Is.True, noun);
        });
    }

    // Revisión 3 de r24 (B2): Notepad tied on the person's «pendientes», with its commands as MenuItems (picked by index,
    // the probe's shape) in Spanish and English.
    private static JsonObject NotepadWithMenu(string application)
    {
        var document = Control(0, "Document", "Editor de texto", "", "la casa roja, la casa azul");
        JsonObject view = Window($"pendientes - {application}", "Notepad", 80, true,
            [document, Control(1, "MenuItem", "Cortar"), Control(2, "MenuItem", "Pegar"), Control(3, "MenuItem", "Eliminar"),
             Control(4, "MenuItem", "Cut"), Control(5, "MenuItem", "Paste"), Control(6, "MenuItem", "Delete"), Control(7, "MenuItem", "Clear all")]);
        view["window"]!["rect"] = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 1200, ["h"] = 800 };
        return Tied(view, 5005, 5006);
    }

    private static bool RefusedOnPendientes(string application, int index, string label, string objective)
    {
        JsonObject view = NotepadWithMenu(application);
        var state = new JsonObject { ["objective"] = objective, ["application"] = application };
        ComputerUseMissionWindow.Tie(state, application, view, ofTheApplication: true, []);
        return ComputerUseMissionWindow.ForeignDocumentAct("input.visible.click", new JsonObject { ["label"] = label, ["index"] = index }, view, state);
    }

    // An adjective or a noun spelled as the class's verb names no order: the probe's three requests and the homographs.
    [TestCase("Bloc de notas", 1, "Cortar", "escribe una nota corta en el bloc de notas")]
    [TestCase("Notepad", 6, "Delete", "write a clear note in notepad")]
    [TestCase("Notepad", 7, "Clear all", "write a clear note in notepad")]
    [TestCase("Bloc de notas", 2, "Pegar", "anota en el bloc de notas que manana hay pega")]
    [TestCase("Bloc de notas", 2, "Pegar", "en el bloc de notas escribe que la pega empieza a las nueve")]
    [TestCase("Notepad", 5, "Paste", "in notepad write that we need tomato paste")]
    [TestCase("Notepad", 4, "Cut", "in notepad write down the hair cut appointment")]
    [TestCase("Notepad", 4, "Cut", "write in notepad that the cut was clean")]
    public void R24R3B2AnAdjectiveOrANounOfTheVerbsSpellingOpensNoClass(string application, int index, string label, string objective) =>
        Assert.That(RefusedOnPendientes(application, index, label, objective), Is.True, objective);

    // Contracases: the same words where an order stands (the start, after a link, a courtesy or a modal, after the
    // place named by the tied window's application or title, after a comma).
    [TestCase("Bloc de notas", 1, "Cortar", "en el bloc de notas, corta la última frase")]
    [TestCase("Bloc de notas", 1, "Cortar", "en el bloc de notas corta la última frase")]
    [TestCase("Notepad", 7, "Clear all", "clear the note in notepad")]
    [TestCase("Notepad", 6, "Delete", "please delete the last line in notepad")]
    [TestCase("Bloc de notas", 2, "Pegar", "abre el bloc de notas y pega el texto")]
    [TestCase("Bloc de notas", 2, "Pegar", "podés pegar el texto en el bloc de notas")]
    [TestCase("Notepad", 5, "Paste", "in notepad paste the text")]
    [TestCase("Notepad", 4, "Cut", "in the notepad cut the last line")]
    [TestCase("Bloc de notas", 3, "Eliminar", "en pendientes eliminá la segunda línea")]
    public void R24R3B2TheVerbWhereAnOrderStandsStillOpensItsClass(string application, int index, string label, string objective) =>
        Assert.That(RefusedOnPendientes(application, index, label, objective), Is.False, objective);

    // Revisión 2 de r24 (B1, pasada r23 v3-11): OneNote's page list shows the person's own «Sin título» pages (seven in
    // the real look), a section tab «Trabajo» and the page's body. Revisión 3 (B1): as the provider gives them, one
    // ListItem «Sin título» whose «repeated» counts the others (DesktopUiaWorker joins each kind and name).
    private static JsonObject NotesListing(string title, int untitled)
    {
        var controls = new JsonArray(Control(0, "Button", "Agregar página"), Control(1, "TabItem", "Trabajo"),
            Control(2, "ListItem", "Lista del super"), Control(3, "Document", "Página"));
        if (untitled > 0)
        {
            JsonObject pages = Control(4, "ListItem", "Sin título");
            pages["repeated"] = untitled - 1;
            controls.Add(pages);
        }

        JsonObject view = Window(title, "ONENOTE", 70, true, controls);
        view["window"]!["rect"] = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 1600, ["h"] = 900 };
        return Tied(view, 3003, 4004);
    }

    // Tied to the person's «Lista del super» listing seven «Sin título»; the look before click 1 recorded as the
    // mission records it (controlsBeforeClick of that step), then the click and the look after it.
    private static (JsonObject State, JsonArray Steps, JsonObject After) ClickedOnListing(
        string label, string? kind, int untitledAfter)
    {
        var state = new JsonObject { ["objective"] = NewPageRequest, ["application"] = "OneNote" };
        var steps = new JsonArray();
        state["steps"] = steps;
        JsonObject first = NotesListing("Lista del super - OneNote", 7);
        ComputerUseMission.AdoptWindow(state, "OneNote", first);
        ComputerUseMissionWindow.Tie(state, "OneNote", first, ofTheApplication: true, steps);
        state["subgoalFirstText"] = ComputerUseSuccessCheck.LookText(first);
        ComputerUseMission.RecordControlsBeforeClick(state, first, 1);
        JsonObject click = Click(1, label, "Lista del super - OneNote");
        if (kind is not null)
            click["kind"] = kind;
        steps.Add(click);
        JsonObject after = NotesListing("Sin título - OneNote", untitledAfter);
        ComputerUseMissionWindow.NoteCreatedDocument(state, after, steps);
        return (state, steps, after);
    }

    [Test]
    public void R24R2B1OneMoreUntitledPageAfterACommandIsTheMissions()
    {
        (JsonObject state, JsonArray steps, JsonObject after) = ClickedOnListing("Agregar página", "Button", untitledAfter: 8);
        Assert.Multiple(() =>
        {
            Assert.That((string?)steps[0]!["createdDocument"], Is.EqualTo("Sin título"));
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.text.type", new JsonObject { ["text"] = "comprar pan" }, after, state),
                Is.False);
        });

        // The kind known from the view alone (no receipt) is the same command.
        (_, JsonArray byView, _) = ClickedOnListing("Agregar página", null, untitledAfter: 8);
        Assert.That((string?)byView[0]!["createdDocument"], Is.EqualTo("Sin título"));
    }

    [Test]
    public void R24R3B1TheLookBeforeTheClickKeepsTheCountsTheProviderFolded()
    {
        // The real v3-11 look: one ListItem «Sin título» with repeated 6 (seven pages), names listing it once.
        JsonObject first = NotesListing("Lista del super - OneNote", 7);
        var state = new JsonObject();
        ComputerUseMission.RecordControlsBeforeClick(state, first, 1);
        Assert.Multiple(() =>
        {
            Assert.That(((JsonArray)state["controlsBeforeClick"]!["1"]!).Count(name => (string?)name == "sin titulo"), Is.EqualTo(1));
            Assert.That((int?)state["countsBeforeClick"]!["1"]!["sin titulo"], Is.EqualTo(7));
            Assert.That(state["countsBeforeClick"]!["1"]!["trabajo"], Is.Null, "a name of one control needs no count");
        });

        // Contracase: the same seven pages after the command (repeated 6 before and after) prove nothing, though the
        // names list «sin titulo» once before and the view seven after.
        (JsonObject seven, JsonArray sevenSteps, _) = ClickedOnListing("Agregar página", "Button", untitledAfter: 7);
        Assert.That(seven["createdDocuments"], Is.Null, "repeated 6 before and after: the same seven pages");
        Assert.That(sevenSteps[0]!["createdDocument"], Is.Null);
    }

    [Test]
    public void R24R2B1TheSameCountOrAClickThatChoosesProvesNothing()
    {
        // Contracase: the same number of «Sin título» after the command.
        (JsonObject same, JsonArray sameSteps, JsonObject sameAfter) = ClickedOnListing("Agregar página", "Button", untitledAfter: 7);
        Assert.Multiple(() =>
        {
            Assert.That(same["createdDocuments"], Is.Null);
            Assert.That(sameSteps[0]!["createdDocument"], Is.Null);
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.text.type", new JsonObject { ["text"] = "pan" }, sameAfter, same),
                Is.True);
        });

        // Contracase: one more after a click on a row (no command), even one whose label creates.
        (JsonObject row, JsonArray rowSteps, _) = ClickedOnListing("Nueva página", "ListItem", untitledAfter: 8);
        Assert.Multiple(() =>
        {
            Assert.That(row["createdDocuments"], Is.Null);
            Assert.That(rowSteps[0]!["createdDocument"], Is.Null);
        });
    }

    [Test]
    public void R24R2B3AClickThatChoosesOrNavigatesRetiresTheCreatedDocument()
    {
        // Sonda B: after «Agregar página» the section «Trabajo» lands on a page of the person's also titled «Sin título».
        (JsonObject state, JsonArray steps, JsonObject created) = ClickedOnListing("Agregar página", "Button", untitledAfter: 8);
        Assert.That((string?)state["createdDocuments"]?["3003"], Is.EqualTo("sin titulo"));
        var text = new JsonObject { ["text"] = "comprar pan" };

        // Contracase: a click on the created page's body keeps it the mission's.
        steps.Add(new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Página", ["kind"] = "Document", ["ok"] = true });
        ComputerUseMissionWindow.NoteCreatedDocument(state, created, steps);
        Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.text.type", text, created, state), Is.False);

        steps.Add(new JsonObject { ["step"] = 3, ["operation"] = "input.visible.click", ["label"] = "Trabajo", ["kind"] = "TabItem", ["ok"] = true });
        JsonObject persons = NotesListing("Sin título - OneNote", 8);
        ComputerUseMissionWindow.NoteCreatedDocument(state, persons, steps);
        Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.text.type", text, persons, state), Is.True,
            "after changing section the page shown may be the person's");

        // And the row «Sin título» (the first of that name, an old page): the same.
        (JsonObject rowState, JsonArray rowSteps, JsonObject rowView) = ClickedOnListing("Agregar página", "Button", untitledAfter: 8);
        rowSteps.Add(new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Sin título", ["ok"] = true });
        ComputerUseMissionWindow.NoteCreatedDocument(rowState, rowView, rowSteps);
        Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.text.type", text, rowView, rowState), Is.True);
    }

    // Revisión 2 de r24 (B2, sonda A): Notepad's only window, showing «diario» and listing the tab «pendientes».
    private static JsonObject NotepadOnDiary()
    {
        var document = Control(0, "Document", "Editor de texto", "", "la casa roja, la casa azul");
        JsonObject view = Window("diario - Bloc de notas", "Notepad", 80, true,
            [document, Control(1, "Edit", "Buscar"), Control(2, "Edit", "Reemplazar"), Control(3, "Button", "Reemplazar"),
             Control(4, "TabItem", "diario", "selected"), Control(5, "Button", "Reemplazar todo"), Control(6, "TabItem", "pendientes")]);
        view["window"]!["rect"] = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 1200, ["h"] = 800 };
        return Tied(view, 5005);
    }

    [Test]
    public void R24R2B2ARequestThatNamesAnotherTabNeverReplacesOnTheTiedOne()
    {
        JsonObject view = NotepadOnDiary();
        var replaceAll = new JsonObject { ["label"] = "Reemplazar todo", ["index"] = 5 };
        JsonObject other = NotepadTied("en el bloc de notas reemplazá casa por hogar en la pestaña pendientes", view);
        Assert.Multiple(() =>
        {
            Assert.That(other["sole"]?.ToJsonString(), Is.EqualTo("[5005]"));
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.visible.click", replaceAll, view, other), Is.True,
                "the request names «pendientes», not the «diario» shown");
            // Contracase (t-form-2): the request names no other document; nor does one that names the tab shown.
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.visible.click", replaceAll, view, NotepadTied(ReplaceRequest, view)),
                Is.False);
            Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.visible.click", replaceAll, view,
                NotepadTied("en el bloc de notas reemplazá casa por hogar en la pestaña diario", view)), Is.False);
        });
    }

    [Test]
    public void R24R2B4TheCauseNeverDeniesWhatAnEarlierRequestDid()
    {
        // Sonda D (v3-35 t2, «ponle: pagar la luz»): no opening in this mission, the empty note an earlier turn created
        // and another window. Refused (the person's document stays refused), and the cause speaks of this request only.
        JsonObject note = NoteWindow(string.Empty);
        note["window"]!["others"] = new JsonArray(7008);
        var state = new JsonObject { ["objective"] = "ponle: pagar la luz", ["application"] = "Notas" };
        ComputerUseMissionWindow.Tie(state, "Notas", note, ofTheApplication: true, []);
        var text = new JsonObject { ["text"] = "pagar la luz" };
        Assert.That(ComputerUseMissionWindow.ForeignDocumentAct("input.text.type", text, note, state), Is.True);
        string cause = ComputerUseMission.ForeignDocumentCause("input.text.type", text, ComputerUseMissionWindow.Restored(state, note));
        Assert.That(cause, Is.EqualTo("computer_use_document_not_named"));
        foreach (bool english in new[] { false, true })
        {
            string? final = OperationFloor.Final(new JsonObject
            {
                ["kind"] = "operation",
                ["operation"] = "mission.computer.use",
                ["polarity"] = "failure",
                ["verified"] = false,
                ["succeeded"] = false,
                ["error"] = cause,
                ["observed"] = new JsonObject
                {
                    ["goal"] = "ponle: pagar la luz",
                    ["application"] = "Notas",
                    ["reached"] = false,
                    ["steps"] = new JsonArray(),
                    ["stoppedBy"] = cause,
                },
            }, english);
            Assert.That(final, Does.Contain(english ? "in this request" : "en este pedido"));
            Assert.That(final, Does.Not.Contain(english ? "I neither opened nor created that document and" : "ni lo creé yo"));
        }
    }
}
