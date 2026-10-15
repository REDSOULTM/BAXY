using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 21, destino por contenido (pasada r18: t-file-1, t-file-3, t-menu-4, t-form-4, t-drag-2). A mission that names
/// no application looked only at the window in front, the simulated person's «BAXY usuario simulado», and the window that
/// held what the request named (the unsaved Bloc de notas, Paint with its «Imagen» and «Girar», Word with «Fuente:», the
/// PowerPoint thumbnails) was never looked at. The desktop's windows are simulated here as the provider lists them
/// (<c>candidateWindows</c>), with control names taken from the views of the same lote; no UIA is touched.
/// </summary>
[TestFixture]
public sealed class ComputerUseDestinationTests
{
    private const long Recent = ComputerUseMissionWindow.PersonRecentMs;

    // The harness's simulated person: a python window in front, a Document they type in (Raw Input never sees it).
    private static JsonObject Person(bool foreground = true, long? personAgo = null) => Window(
        1, 900, "python", "BAXY usuario simulado", foreground, personAgo,
        ("Document", "el usuario escribe aquí"), ("Button", "Minimizar"), ("Button", "Maximizar"), ("Button", "Cerrar"),
        ("TitleBar", "BAXY usuario simulado"));

    private static JsonObject PowerOptions() => Window(
        2, 901, "explorer", "Opciones de energía", false, null,
        ("Hyperlink", "Elegir el comportamiento de los botones de inicio/apagado"), ("RadioButton", "Equilibrado"),
        ("Button", "Cerrar"));

    private static JsonObject Notepad(string title = "*prueba de guardado v3 - Bloc de notas", bool foreground = false, long? personAgo = null) =>
        Window(3, 902, "Notepad", title, foreground, personAgo,
            ("MenuItem", "Archivo"), ("MenuItem", "Editar"), ("MenuItem", "Ver"), ("Document", "Editor de texto"),
            ("Button", "Cerrar"));

    private static JsonObject Paint(long hwnd = 4, string title = "lienzo-1000x700-trazo - Paint") => Window(
        hwnd, 903 + (int)hwnd, "mspaint", title, false, null,
        ("MenuItem", "Archivo"), ("MenuItem", "Editar"), ("MenuItem", "Ver"), ("Text", "Imagen"),
        ("Button", "Seleccionar"), ("Button", "Recortar"), ("Button", "Cambiar tamaño e inclinar"), ("Button", "Girar"),
        ("Text", "800 × 400px"));

    // Word with text selected in its document (the provider read a non-empty selected range: «selection»).
    private static JsonObject Word(bool selection = true)
    {
        JsonObject word = Window(
            5, 904, "WINWORD", "Informe semanal - Word", false, null,
            ("TabItem", "Archivo"), ("TabItem", "Inicio"), ("TabItem", "Insertar"), ("Button", "Imágenes"),
            ("ComboBox", "Fuente:"), ("ComboBox", "Tamaño de fuente:"), ("Button", "Cursiva"), ("Document", "Informe semanal"));
        if (selection)
            word["selection"] = true;
        return word;
    }

    private static JsonObject PowerPoint() => Window(
        6, 905, "POWERPNT", "presentacion-v3 - PowerPoint", false, null,
        ("TabItem", "Archivo"), ("TabItem", "Inicio"), ("MenuItem", "Diapositivas"), ("Thumb", "Miniatura"),
        ("ListItem", "Uno"), ("ListItem", "Dos"), ("ListItem", "Tres"));

    private static JsonObject Editor() => Window(
        7, 906, "Code", "● ComputerUseMission.cs - BAXY - Visual Studio Code", false, null,
        ("MenuItem", "Archivo"), ("MenuItem", "Imagen"), ("Document", "editor"));

    private static JsonObject Terminal() => Window(
        8, 907, "WindowsTerminal", "PowerShell", false, null, ("Document", "Fuente"), ("TabItem", "Imagen"));

    [Test]
    public void Revision2B1WithoutRawInputTheWindowInFrontIsThePersonsWhileTheirInputIsRecent()
    {
        // No window of the person is known (no «personInputAgoMs»); the session's last input came 300 ms ago. The only
        // window that shows «Imagen» and «Girar» is the one in front: it is the person's, never bound.
        var referent = new ComputerUseDestination.Referent(["imagen", "girar"], Selection: false);
        JsonObject front = Paint();
        front["foreground"] = true;

        var choice = ComputerUseDestination.Choose(referent, [front, PowerOptions()], frontWindow: false, Recent, personInputUnknownAgoMs: 300);

        Assert.That(choice.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.PersonsWindow));
        Assert.That(choice.Window, Is.Null);
    }

    [Test]
    public void Revision2B1ContracasesAnOldInputOrAWindowBehindIsStillBound()
    {
        var referent = new ComputerUseDestination.Referent(["imagen", "girar"], Selection: false);
        JsonObject front = Paint();
        front["foreground"] = true;

        // The session's last input is older than a moment: the window in front is weighed as before.
        var old = ComputerUseDestination.Choose(referent, [front, PowerOptions()], frontWindow: false, Recent, personInputUnknownAgoMs: Recent + 1);
        Assert.That(old.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));

        // Recent input, but the window that shows it is behind (only the window in front may have taken that input).
        var behind = ComputerUseDestination.Choose(referent, [Person(), Paint()], frontWindow: false, Recent, personInputUnknownAgoMs: 300);
        Assert.That(behind.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
        Assert.That((string?)behind.Window!["process"], Is.EqualTo("mspaint"));
    }

    [Test]
    public void TMenu4TheWindowShowingBothPiecesOfTheMenuRouteWinsOverOneShowingOne()
    {
        // Word shows «Imágenes» (one piece, as a plural); Paint shows «Imagen» and «Girar».
        var referent = new ComputerUseDestination.Referent(["imagen", "girar"], Selection: false);

        var choice = ComputerUseDestination.Choose(referent, [Person(), PowerOptions(), Word(), Paint()], frontWindow: false, Recent);

        Assert.That(choice.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
        Assert.That((string?)choice.Window!["process"], Is.EqualTo("mspaint"));
    }

    [Test]
    public void TForm4WordWithTheFontBoxAndADocumentIsTheDestination()
    {
        var referent = new ComputerUseDestination.Referent(["fuente"], Selection: true);

        var choice = ComputerUseDestination.Choose(referent, [Person(), Paint(), Word()], frontWindow: false, Recent);

        Assert.That(choice.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
        Assert.That((string?)choice.Window!["process"], Is.EqualTo("WINWORD"));
    }

    [Test]
    public void TDrag2ThePresentationWithItsThumbnailsIsTheDestination()
    {
        var referent = new ComputerUseDestination.Referent(["miniaturas", "tres"], Selection: false);

        var choice = ComputerUseDestination.Choose(referent, [Person(), Word(), PowerPoint()], frontWindow: false, Recent);

        Assert.That(choice.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
        Assert.That((string?)choice.Window!["process"], Is.EqualTo("POWERPNT"));
    }

    [Test]
    public void ContracaseThePersonsNotepadInFrontIsUsedWhenTheyPointAtIt()
    {
        // The person works in the Bloc de notas (in front, their input went there) and says «en esta ventana, desde el
        // menú Archivo …».
        var referent = new ComputerUseDestination.Referent(["archivo"], Selection: false);
        JsonObject front = Notepad(foreground: true, personAgo: 400);

        var choice = ComputerUseDestination.Choose(referent, [front, Paint()], frontWindow: true, Recent);

        Assert.That(choice.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Front));
        Assert.That((string?)choice.Window!["process"], Is.EqualTo("Notepad"));
    }

    [Test]
    public void ContracaseTwoImageEditorsAreAskedAboutNeverTheFirstInZOrder()
    {
        var referent = new ComputerUseDestination.Referent(["imagen", "girar"], Selection: false);

        var choice = ComputerUseDestination.Choose(
            referent, [Paint(4, "uno.png - Paint"), Paint(9, "dos.png - Paint")], frontWindow: false, Recent);

        Assert.That(choice.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Ambiguous));
        Assert.That(choice.Window, Is.Null);
        Assert.That(choice.Titles, Is.EqualTo(new[] { "uno.png - Paint", "dos.png - Paint" }));
    }

    [Test]
    public void ContracaseThePersonsWindowIsNeverTheDestinationWhenTheyDidNotPointAtIt()
    {
        // The person types in their own Bloc de notas (their input went there a moment ago): it fits, and is not taken.
        var referent = new ComputerUseDestination.Referent(["archivo"], Selection: false);

        var choice = ComputerUseDestination.Choose(
            referent, [Notepad(foreground: true, personAgo: 300), Person()], frontWindow: false, Recent);

        // Revision 1 (B3): said as the person's window, never as «no window shows it».
        Assert.That(choice.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.PersonsWindow));
        Assert.That(choice.Window, Is.Null);
    }

    [Test]
    public void ContracaseTheEditorTheTerminalAndBaxyAreNeverCandidates()
    {
        // They fit by words (a modified title, «Archivo», «Imagen», «Fuente») and are marked protected by their process.
        var referent = new ComputerUseDestination.Referent(["imagen", "fuente"], Selection: false);
        JsonObject baxy = Window(10, 908, "Baxy", "*BAXY", false, null, ("MenuItem", "Archivo"), ("Text", "Imagen"));
        baxy["protected"] = true;

        // Revision 2 (B2): a request pointing at the window in front weighs nothing, so the request here points at none.
        var choice = ComputerUseDestination.Choose(referent, [Editor(), Terminal(), baxy], frontWindow: false, Recent);

        Assert.That(choice.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.NotFound));
    }

    [Test]
    public void ContracaseAMenuNoWindowShowsBindsNothing()
    {
        var referent = new ComputerUseDestination.Referent(["capas"], Selection: false);

        var choice = ComputerUseDestination.Choose(referent, [Person(), PowerOptions(), Paint(), Word()], frontWindow: false, Recent);

        Assert.That(choice.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.NotFound));
        Assert.That(choice.Titles, Is.Empty);
    }

    [Test]
    public void ContracaseARequestWithoutReferentCarriesNone()
    {
        // «hacé clic en Aceptar»: the mind sends no referent; the mission behaves as before (it asks for the window).
        Assert.That(ComputerUseDestination.ReferentOf(new JsonObject { ["goal"] = "hacé clic en Aceptar" }), Is.Null);
        Assert.That(ComputerUseDestination.ReferentOf(new JsonObject
        {
            ["goal"] = "x",
            ["referentLabels"] = new JsonArray(),
            ["referentSelection"] = false,
        }), Is.Null);
        ComputerUseDestination.Referent? read = ComputerUseDestination.ReferentOf(new JsonObject
        {
            ["referentLabels"] = new JsonArray("Imagen", "girar", "imagen"),
        });
        Assert.That(read!.Labels, Is.EqualTo(new[] { "imagen", "girar" }));
    }

    [Test]
    public void TheBoundWindowTiesTheMissionToAWindowOfItsProcessNotToADocumentItNames()
    {
        var state = new JsonObject { ["frontWindow"] = true };
        ComputerUseDestination.Bind(state, Notepad(), stepCount: 0);

        Assert.That(ComputerUseMissionWindow.Tied(state), Is.True);
        Assert.That((int?)state["processId"], Is.EqualTo(902));
        // Revision 3 of r21 (B1): the window is the mission's, never a document the request names.
        Assert.That(state["named"], Is.Null);

        // The next look names the window, and the view of it (requested) lets the mission act there.
        var look = new JsonObject { ["limit"] = 60 };
        ComputerUseMissionWindow.AddLookArguments(state, look);
        Assert.That(look["windows"]!.ToJsonString(), Is.EqualTo("[3]"));
        var view = new JsonObject { ["window"] = new JsonObject { ["hwnd"] = 3L, ["requested"] = true, ["title"] = "x" } };
        Assert.That(ComputerUseMission.NoApplicationActs("input.text.type", null, state, view["window"] as JsonObject), Is.False);
    }

    [Test]
    public void TheMissionStateKeepsTheReferentOnlyWithoutApplication()
    {
        JsonObject arguments = new()
        {
            ["goal"] = "Gira la imagen 90 grados a la derecha desde el menú Imagen > Girar",
            ["referentLabels"] = new JsonArray("imagen", "girar"),
        };
        ComputerUseDestination.Referent referent = ComputerUseDestination.ReferentOf(arguments)!;
        JsonObject kept = ComputerUseDestination.ToState(referent);

        Assert.That(ComputerUseDestination.FromState(new JsonObject { ["referent"] = kept })!.Labels, Is.EqualTo(new[] { "imagen", "girar" }));
        Assert.That(ComputerUseDestination.FromState(new JsonObject()), Is.Null);
    }

    [Test]
    public void TheLookForCandidatesAndTheMissionReferentPassTheCatalogSchemas()
    {
        OperationArgumentsSchema look = ProductCatalog.GetRequired("input.visible.controls").ArgumentsSchema;
        OperationArgumentsSchema mission = ProductCatalog.GetRequired("mission.computer.use").ArgumentsSchema;

        Assert.That(Valid(look, new JsonObject { ["candidates"] = true, ["limit"] = 60 }), Is.True);
        Assert.That(Valid(mission, new JsonObject
        {
            ["goal"] = "Ponme el texto seleccionado en Arial, desde el cuadro de diálogo de Fuente",
            ["referentLabels"] = new JsonArray("fuente"),
            ["referentSelection"] = true,
        }), Is.True);
        // Estabilización L: «guardá esto» with no window named is asked about by the mind, never a referent of the
        // engine: the save referent is no argument any more.
        Assert.That(Valid(mission, new JsonObject { ["goal"] = "guardá esto como baxy-nota1.txt", ["referentUnsaved"] = true }),
            Is.False);
        // Counter-cases: an undeclared argument, and a blank label.
        Assert.That(Valid(look, new JsonObject { ["candidatez"] = true }), Is.False);
        Assert.That(Valid(mission, new JsonObject { ["goal"] = "x", ["referentLabels"] = new JsonArray(" ") }), Is.False);
    }

    [Test]
    public void TheFinalOfAnAmbiguousDestinationNamesTheWindowsAndAsks()
    {
        var source = (JsonObject)JsonNode.Parse(
            """{"kind":"operation","operation":"mission.computer.use","polarity":"failure","verified":true,"succeeded":false,"observed":{"goal":"gira la imagen desde el menú Imagen > Girar","reached":false,"steps":[],"stoppedBy":"computer_use_destination_ambiguous","destinationCandidates":["uno.png - Paint","dos.png - Paint"]}}""")!;

        string? final = OperationFloor.Final(source, english: false);

        Assert.That(final, Does.Contain("«uno.png - Paint»").And.Contain("«dos.png - Paint»"));
        Assert.That(final, Does.Contain("decime en cuál"));
    }

    [Test]
    public void Revision1B2ASelectionIsTheOneReadNeverADocumentBeingThere()
    {
        // (a) The selection is in an image editor (no text pattern to read it); the Bloc de notas has a document and
        // nothing selected: nothing is bound in its place.
        var referent = new ComputerUseDestination.Referent([], Selection: true);

        var none = ComputerUseDestination.Choose(referent, [Paint(), Notepad()], frontWindow: false, Recent);

        Assert.That(none.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.NotFound));

        // (b) Word with text selected beside a browser whose address bar is an Edit: Word alone has a selection.
        JsonObject browser = Window(
            12, 911, "msedge", "Noticias - Microsoft Edge", false, null,
            ("Edit", "Barra de direcciones y de búsqueda"), ("Document", "Noticias"));

        var word = ComputerUseDestination.Choose(referent, [browser, Word()], frontWindow: false, Recent);

        Assert.That(word.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
        Assert.That((string?)word.Window!["process"], Is.EqualTo("WINWORD"));
    }

    [Test]
    public void Revision1B2ContracaseTheWindowWithASelectionReadIsBound()
    {
        var referent = new ComputerUseDestination.Referent([], Selection: true);
        JsonObject notepad = Notepad();
        notepad["selection"] = true;

        var choice = ComputerUseDestination.Choose(referent, [Paint(), Word(selection: false), notepad], frontWindow: false, Recent);

        Assert.That(choice.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
        Assert.That((string?)choice.Window!["process"], Is.EqualTo("Notepad"));
    }

    [Test]
    public void Revision1B3ThePersonsWindowShowingItIsSaidAsSuchNeverAsNoWindowShowsIt()
    {
        // The person clicked Paint 1,5 s ago and says by voice «girá la imagen desde el menú Imagen > Girar».
        var referent = new ComputerUseDestination.Referent(["imagen", "girar"], Selection: false);
        JsonObject paint = Paint();
        paint["foreground"] = true;
        paint["personInputAgoMs"] = 1500L;

        var choice = ComputerUseDestination.Choose(referent, [paint, PowerOptions(), Word()], frontWindow: false, Recent);

        Assert.That(choice.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.PersonsWindow));
        Assert.That(choice.Window, Is.Null);
    }

    [Test]
    public void Revision1B3ContracasesThePointedWindowIsTheFrontAndABetterWindowIsStillBound()
    {
        var referent = new ComputerUseDestination.Referent(["imagen", "girar"], Selection: false);
        JsonObject paint = Paint();
        paint["foreground"] = true;
        paint["personInputAgoMs"] = 1500L;

        // «en esta ventana girá la imagen…»: the person points at it.
        var pointed = ComputerUseDestination.Choose(referent, [paint, Word()], frontWindow: true, Recent);
        Assert.That(pointed.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Front));

        // The person's window shows one piece («Imagen»), another window both: that one is clearly ahead.
        JsonObject persons = Window(13, 912, "Photos", "Fotos", true, 900, ("MenuItem", "Imagen"));
        var other = ComputerUseDestination.Choose(referent, [persons, Paint()], frontWindow: false, Recent);
        Assert.That(other.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
        Assert.That((string?)other.Window!["process"], Is.EqualTo("mspaint"));
    }

    [Test]
    public void Revision1B4AWindowNotReadInTimeIsNeverWeighed()
    {
        // The provider ran out of budget before Paint: its listing carries no tree and is marked unread.
        var referent = new ComputerUseDestination.Referent(["imagen", "girar"], Selection: false);
        JsonObject unread = Paint();
        unread["unread"] = true;

        var choice = ComputerUseDestination.Choose(referent, [Person(), unread], frontWindow: false, Recent);

        Assert.That(choice.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.NotFound));
    }

    [Test]
    public void Revision1B3TheFinalsOfTheDestinationSayOnlyWhatWasLookedAt()
    {
        foreach (string code in new[] { "computer_use_destination_not_found", "computer_use_destination_persons_window", "computer_use_destination_unlisted" })
        {
            var source = (JsonObject)JsonNode.Parse(
                $$$"""{"kind":"operation","operation":"mission.computer.use","polarity":"failure","verified":true,"succeeded":false,"observed":{"goal":"gira la imagen desde el menú Imagen > Girar","reached":false,"steps":[],"stoppedBy":"{{{code}}}"}}""")!;

            string? final = OperationFloor.Final(source, english: false);

            Assert.That(final, Is.Not.Null.And.Not.Contain("ninguna ventana abierta muestra"), code);
        }
    }

    private static bool Valid(OperationArgumentsSchema schema, JsonObject arguments)
    {
        using JsonDocument document = JsonDocument.Parse(arguments.ToJsonString());
        return OperationArgumentValidator.IsValid(document.RootElement, schema);
    }

    private static JsonObject Window(
        long hwnd, int processId, string process, string title, bool foreground, long? personAgo,
        params (string Kind, string Name)[] controls)
    {
        var window = new JsonObject
        {
            ["hwnd"] = hwnd,
            ["processId"] = processId,
            ["process"] = process,
            ["title"] = title,
            ["foreground"] = foreground,
            ["controls"] = new JsonArray([.. controls.Select(control => (JsonNode?)new JsonObject
            {
                ["kind"] = control.Kind,
                ["name"] = control.Name,
            })]),
        };
        if (personAgo is long ago)
            window["personInputAgoMs"] = ago;
        if (process is "Code" or "WindowsTerminal")
            window["protected"] = true;
        return window;
    }
}
