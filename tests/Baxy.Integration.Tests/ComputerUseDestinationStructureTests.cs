using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 24, destino por estructura y nunca por contenido (pasada r23: t-drag-2, t-file-3, t-form-4). A window is the
/// mission's destination by what the request's structure names (a menu, a panel, a tab, a dialog already open, a
/// selection, a document that can save), never by a word of its content: «Spotify Premium» was bound for «la diapositiva
/// «Tres»» because a song of its list was called «Tres». The desktop's windows are simulated as the provider lists them.
/// </summary>
[TestFixture]
public sealed class ComputerUseDestinationStructureTests
{
    private const long Recent = ComputerUseMissionWindow.PersonRecentMs;

    private static JsonObject Person() => Window(
        1, 900, "python", "BAXY usuario simulado", true, 300, ("Document", "el usuario escribe aquí"), ("Button", "Cerrar"));

    // A music player whose list holds a song called «Tres» (r23 t-drag-2: bound.candidates.8 on «Spotify Premium»).
    private static JsonObject Player() => Window(
        2, 901, "Spotify", "Spotify Premium", false, null,
        ("Edit", "Address and search bar"), ("Button", "Reproducir"), ("ListItem", "Tres"), ("ListItem", "Dos"));

    private static JsonObject PowerPoint() => Window(
        6, 905, "POWERPNT", "presentacion-v3 - PowerPoint", false, null,
        ("TabItem", "Archivo"), ("TabItem", "Inicio"), ("Thumb", "Miniatura"), ("ListItem", "Uno"), ("ListItem", "Tres"));

    private static JsonObject Paint(long hwnd = 4, string title = "lienzo - Paint", bool foreground = false) => Window(
        hwnd, 903 + (int)hwnd, "mspaint", title, foreground, null,
        ("MenuItem", "Archivo"), ("Text", "Imagen"), ("Button", "Girar"), ("Button", "Guardar"));

    // A page that mentions «girar» and «imagen» in its content only. Revision 2 (B2): as a real browser lists it, its
    // frame shows the page's tab (named as the document in the title) and another page's tab beside it. Revision 3
    // (B1): what hangs from its Document carries the provider's content mark, its text a Text control.
    private static JsonObject Page(string title = "Cómo girar una imagen - Microsoft Edge") => Content(Window(
        12, 911, "msedge", title, false, null,
        ("TabItem", "Cómo girar una imagen"), ("TabItem", "Miniaturas de YouTube: guía"), ("Button", "Nueva pestaña"),
        ("Edit", "Barra de direcciones y de búsqueda"),
        ("Document", "Cómo girar una imagen"), ("Hyperlink", "Girar"), ("Hyperlink", "Imagen"),
        ("Text", "Abrí el menú Imagen y elegí Girar")), 5, 6, 7);

    // Revision 2 (B2): a page whose own tab, the one in front, is named with the words of a panel and of a slide.
    // Revision 3 (B1): its text, read inside the Document, carries the provider's content mark.
    private static JsonObject ThumbnailsPage() => Content(Window(
        13, 912, "msedge", "Miniaturas de YouTube: guía - Microsoft Edge", false, null,
        ("TabItem", "Miniaturas de YouTube: guía"), ("Button", "Nueva pestaña"),
        ("Document", "Miniaturas de YouTube: guía"), ("Text", "El panel de miniaturas muestra cada diapositiva"),
        ("Text", "Tres")), 3, 4);

    // Revision 3 (B1): a page as a real browser lists it with a single tab of its own (no tab strip naming it): the
    // frame's back button and address bar, the Document, and the page's text read inside it (content), never links.
    private static JsonObject ProbePage(long hwnd, string title, params (string Kind, string Name)[] text)
    {
        (string Kind, string Name)[] frame =
            [("Button", "Atrás"), ("Edit", "Barra de direcciones y de búsqueda"), ("Document", title.Split(" - ")[0])];
        JsonObject page = Window(hwnd, 930 + (int)hwnd, "msedge", title, false, null, [.. frame, .. text]);
        return Content(page, [.. Enumerable.Range(frame.Length, text.Length)]);
    }

    private static JsonObject Word(bool selection) => Window(
        5, 904, "WINWORD", "Informe semanal - Word", false, null,
        ("TabItem", "Archivo"), ("TabItem", "Inicio"), ("ComboBox", "Tamaño de fuente:"), ("Document", "Informe semanal"),
        ("Button", "Guardar"))
        .WithSelection(selection);

    [Test]
    public void TDrag2AQuotedNameIsContentAndNeverMakesAWindowFit()
    {
        var referent = new ComputerUseDestination.Referent(["miniaturas"], Selection: false, Items: ["tres"]);

        var bound = ComputerUseDestination.Choose(referent, [Person(), Player(), PowerPoint()], frontWindow: false, Recent);
        var alone = ComputerUseDestination.Choose(referent, [Person(), Player()], frontWindow: false, Recent);

        Assert.Multiple(() =>
        {
            Assert.That(bound.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
            Assert.That((string?)bound.Window!["process"], Is.EqualTo("POWERPNT"));
            // The player shows «Tres» and no thumbnails: it is never the destination, not even alone.
            Assert.That(alone.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.NotFound));
            Assert.That(ComputerUseDestination.Score(referent, Player()), Is.Null);
        });
    }

    [Test]
    public void TDrag2TheItemAddsToAWindowThatFits()
    {
        // Two presentations with thumbnails: the one showing the slide «Tres» is ahead.
        var referent = new ComputerUseDestination.Referent(["miniaturas"], Selection: false, Items: ["tres"]);
        JsonObject other = Window(
            7, 906, "POWERPNT", "otra - PowerPoint", false, null, ("TabItem", "Archivo"), ("Thumb", "Miniatura"), ("ListItem", "Uno"));

        var choice = ComputerUseDestination.Choose(referent, [other, PowerPoint()], frontWindow: false, Recent);

        Assert.That(choice.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
        Assert.That((string?)choice.Window!["title"], Is.EqualTo("presentacion-v3 - PowerPoint"));
    }

    [Test]
    public void ItemsAloneAreNoReferent()
    {
        var arguments = new JsonObject { ["goal"] = "arrastrá «Tres» arriba", ["referentItems"] = new JsonArray("Tres") };

        Assert.That(ComputerUseDestination.ReferentOf(arguments), Is.Null);
    }

    [Test]
    public void ContracaseTheMenuRouteBindsPaintNeverAPageThatMentionsItsWords()
    {
        // «desde el menú Imagen > Girar, gira 90°» with Paint and a browser open: Paint shows «Imagen» in its frame.
        var referent = new ComputerUseDestination.Referent(["imagen", "girar"], Selection: false);

        var both = ComputerUseDestination.Choose(referent, [Person(), Page(), Paint()], frontWindow: false, Recent);
        var page = ComputerUseDestination.Choose(referent, [Person(), Page()], frontWindow: false, Recent);
        // Revision 2 (B2): the browser's title says its other pages after the page's own title; the tab is still the
        // page's. Probe over the bridge on 9a8103b2e: this page with its tab was bound by the words of its title.
        var more = ComputerUseDestination.Choose(
            referent, [Person(), Page("Cómo girar una imagen y 1 página más - Personal - Microsoft Edge")], frontWindow: false, Recent);

        Assert.Multiple(() =>
        {
            Assert.That(both.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
            Assert.That((string?)both.Window!["process"], Is.EqualTo("mspaint"));
            Assert.That(page.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.NotFound), "a page's content names no menu");
            Assert.That(ComputerUseDestination.DocumentTabs(Page()), Is.True);
            Assert.That(ComputerUseDestination.Score(referent, Page()), Is.Null, "the page's tab is its content");
            Assert.That(more.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.NotFound));
        });
    }

    [Test]
    public void TDrag2APageTabNamedWithThePanelsWordsIsContent()
    {
        // Probe over the bridge on 9a8103b2e: «miniaturas» with the item «tres» against a page whose tab is «Miniaturas de
        // YouTube: guía» bound the browser. A page's tab is the document it shows, never a panel of the window.
        var referent = new ComputerUseDestination.Referent(["miniaturas"], Selection: false, Items: ["tres"]);

        var page = ComputerUseDestination.Choose(referent, [Person(), ThumbnailsPage()], frontWindow: false, Recent);
        // The other page's tab, beside the one in front in the strip, is a document too.
        var other = ComputerUseDestination.Choose(referent, [Person(), Page()], frontWindow: false, Recent);
        var both = ComputerUseDestination.Choose(referent, [Person(), ThumbnailsPage(), PowerPoint()], frontWindow: false, Recent);

        Assert.Multiple(() =>
        {
            Assert.That(page.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.NotFound));
            Assert.That(other.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.NotFound));
            Assert.That(both.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
            Assert.That((string?)both.Window!["process"], Is.EqualTo("POWERPNT"));
        });
    }

    [Test]
    public void ContracaseARibbonTabIsStructureAndBindsTheWordProcessor()
    {
        // «desde la pestaña Insertar, agregá una tabla»: the word processor's ribbon tab «Insertar» names no document (the
        // title's document is «Informe semanal»), so it is structure; a page titled «Cómo insertar una tabla» is not.
        var referent = new ComputerUseDestination.Referent(["insertar"], Selection: false);
        JsonObject Ribbon(string title) => Window(
            5, 904, "WINWORD", title, false, null,
            ("TabItem", "Archivo"), ("TabItem", "Inicio"), ("TabItem", "Insertar"), ("TabItem", "Diseño"),
            ("Document", "Informe semanal"));
        JsonObject HowToPage() => Window(
            14, 913, "msedge", "Cómo insertar una tabla - Microsoft Edge", false, null,
            ("TabItem", "Cómo insertar una tabla"), ("Button", "Nueva pestaña"), ("Document", "Cómo insertar una tabla"));

        var both = ComputerUseDestination.Choose(referent, [Person(), HowToPage(), Ribbon("Informe semanal - Word")], frontWindow: false, Recent);
        var alone = ComputerUseDestination.Choose(referent, [Person(), HowToPage()], frontWindow: false, Recent);
        // A document whose name begins with one word of the ribbon («Inicio de obra») leaves the ribbon structure.
        var start = ComputerUseDestination.Choose(
            new ComputerUseDestination.Referent(["inicio"], Selection: false),
            [Person(), Ribbon("Inicio de obra - Word")], frontWindow: false, Recent);

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseDestination.DocumentTabs(Ribbon("Informe semanal - Word")), Is.False);
            Assert.That(both.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
            Assert.That((string?)both.Window!["process"], Is.EqualTo("WINWORD"));
            Assert.That(alone.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.NotFound));
            Assert.That(start.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
            Assert.That((string?)start.Window!["process"], Is.EqualTo("WINWORD"));
        });
    }

    [Test]
    public void TForm4ADialogNotOpenYetLeavesTheSelectionToChoose()
    {
        // «Ponme el texto seleccionado en Arial…, desde el cuadro de diálogo de Fuente»: no window shows «Fuente» yet.
        var referent = new ComputerUseDestination.Referent([], Selection: true, Dialogs: ["fuente"]);

        var one = ComputerUseDestination.Choose(referent, [Person(), Paint(), Word(selection: true)], frontWindow: false, Recent);
        JsonObject second = Word(selection: true);
        second["hwnd"] = 15L;
        second["title"] = "Notas - Word";
        var two = ComputerUseDestination.Choose(referent, [Person(), Word(selection: true), second], frontWindow: false, Recent);
        var none = ComputerUseDestination.Choose(referent, [Person(), Word(selection: false)], frontWindow: false, Recent);

        Assert.Multiple(() =>
        {
            Assert.That(one.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
            Assert.That((string?)one.Window!["process"], Is.EqualTo("WINWORD"));
            Assert.That(two.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Ambiguous), "several selections are asked about");
            Assert.That(two.Titles, Is.EqualTo(new[] { "Informe semanal - Word", "Notas - Word" }));
            Assert.That(none.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.NotFound));
        });
    }

    [Test]
    public void ContracaseADialogAlreadyOpenIsBoundAsBefore()
    {
        // «en el cuadro de diálogo Guardar como escribí informe», with the dialog open.
        var referent = new ComputerUseDestination.Referent([], Selection: false, Dialogs: ["guardar"]);
        JsonObject dialog = Window(
            20, 902, "Notepad", "Guardar como", false, null, ("Edit", "Nombre de archivo:"), ("Button", "Guardar"));

        var open = ComputerUseDestination.Choose(referent, [Person(), Player(), dialog], frontWindow: false, Recent);
        var closed = ComputerUseDestination.Choose(referent, [Person(), Player()], frontWindow: false, Recent);

        Assert.Multiple(() =>
        {
            Assert.That(open.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
            Assert.That((long?)open.Window!["hwnd"], Is.EqualTo(20));
            Assert.That(closed.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.NotFound), "a dialog alone, not open, binds nothing");
        });
    }

    // Revision 3 of ronda 24 (B1): probes over the bridge on f05f9609b (ZzRev3DestinoProbes). A page's text is listed
    // as Text, Button or ListItem controls inside its Document (content), not as links: «Abrí el menú Imagen y elegí
    // Girar» bound the browser for the menu route (Score 4) and made it Ambiguous beside Paint; «El panel de miniaturas
    // muestra cada diapositiva» with «Tres» bound it for the slide's drag; «Fuente: agencia» bound it for a dialog not
    // open. What the provider read inside a document names no menu, panel or dialog of the window.
    [Test]
    public void Revision3APagesTextReadInsideItsDocumentNamesNoMenuPanelOrDialog()
    {
        var menu = new ComputerUseDestination.Referent(["imagen", "girar"], Selection: false);
        var panel = new ComputerUseDestination.Referent(["miniaturas"], Selection: false, Items: ["tres"]);
        var font = new ComputerUseDestination.Referent([], Selection: false, Dialogs: ["fuente"]);
        JsonObject HowTo() => ProbePage(31, "Cómo girar una imagen - Microsoft Edge", ("Text", "Abrí el menú Imagen y elegí Girar"));
        JsonObject Slides() => ProbePage(
            32, "Presentaciones - Microsoft Edge",
            ("Text", "El panel de miniaturas muestra cada diapositiva"), ("ListItem", "Tres"));
        JsonObject News() => ProbePage(33, "Noticias del día - Microsoft Edge", ("Text", "Fuente: agencia"), ("Button", "Fuente"));

        var p1 = ComputerUseDestination.Choose(menu, [Person(), HowTo()], frontWindow: false, Recent);
        var p1Paint = ComputerUseDestination.Choose(menu, [Person(), HowTo(), Paint()], frontWindow: false, Recent);
        var p2 = ComputerUseDestination.Choose(panel, [Person(), Slides()], frontWindow: false, Recent);
        var p2PowerPoint = ComputerUseDestination.Choose(panel, [Person(), Slides(), PowerPoint()], frontWindow: false, Recent);
        var p3 = ComputerUseDestination.Choose(font, [Person(), News()], frontWindow: false, Recent);
        // Counter-case: the dialog already open is bound beside the page, as before.
        JsonObject dialog = Window(34, 934, "WINWORD", "Fuente", false, null, ("ComboBox", "Fuente:"), ("Button", "Aceptar"));
        var p3Open = ComputerUseDestination.Choose(font, [Person(), News(), dialog], frontWindow: false, Recent);

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseDestination.Score(menu, HowTo()), Is.Null, "the page's text is its content");
            Assert.That(p1.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.NotFound));
            Assert.That(p1Paint.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
            Assert.That((string?)p1Paint.Window!["process"], Is.EqualTo("mspaint"));
            Assert.That(ComputerUseDestination.Score(panel, Slides()), Is.Null);
            Assert.That(p2.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.NotFound), "the person's browser is never acted on");
            Assert.That(p2PowerPoint.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
            Assert.That((string?)p2PowerPoint.Window!["process"], Is.EqualTo("POWERPNT"));
            Assert.That(ComputerUseDestination.Score(font, News()), Is.Null);
            Assert.That(p3.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.NotFound), "a dialog not open is seen nowhere");
            Assert.That(p3Open.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
            Assert.That((long?)p3Open.Window!["hwnd"], Is.EqualTo(34L));
        });
    }

    // Revision 4 of ronda 24 (B2): probes over the bridge on e2486a699. A dialog said made a window fit by its title,
    // which for a window that shows a document is the document's name: a page «Fuentes tipográficas gratis» was bound
    // for «el cuadro de Fuente», «How to print a PDF» for «the Print dialog», and «fuente.txt - Bloc de notas» (its file
    // menu and its text area, no «Fuente» control) for «Fuente» too. The title names a dialog only when the window is
    // the dialog itself: no document in it and a title that is the dialog's own name.
    [Test]
    public void Revision4AWindowsTitleNamesADialogOnlyWhenTheWindowIsTheDialog()
    {
        var font = new ComputerUseDestination.Referent([], Selection: false, Dialogs: ["fuente"]);
        var print = new ComputerUseDestination.Referent([], Selection: false, Dialogs: ["print"]);
        JsonObject Fonts() => Content(Window(
            41, 941, "msedge", "Fuentes tipográficas gratis - Microsoft Edge", false, null,
            ("Button", "Atrás"), ("Edit", "Barra de direcciones y de búsqueda"), ("Document", "Fuentes tipográficas gratis"),
            ("Text", "Descargá tipografías")), 3);
        JsonObject HowTo() => Content(Window(
            42, 942, "chrome", "How to print a PDF - Google Chrome", false, null,
            ("Button", "Back"), ("Edit", "Address and search bar"), ("Document", "How to print a PDF"),
            ("Text", "Open the file and choose Print")), 3);
        JsonObject Notes() => Window(
            43, 943, "Notepad", "fuente.txt - Bloc de notas", false, null,
            ("MenuItem", "Archivo"), ("MenuItem", "Editar"), ("Document", "Editor de texto"));
        // Counter-cases: the dialog itself, open, whose controls never carry its name; the same dialog in English.
        JsonObject FontDialog() => Window(44, 944, "WINWORD", "Fuente", false, null, ("Button", "Aceptar"), ("Button", "Cancelar"));
        JsonObject PrintDialog() => Window(45, 945, "Notepad", "Print", false, null, ("Button", "OK"), ("Button", "Cancel"));

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseDestination.Score(font, Fonts()), Is.Null, "a page's title is its content");
            Assert.That(ComputerUseDestination.Choose(font, [Person(), Fonts()], frontWindow: false, Recent).Outcome,
                Is.EqualTo(ComputerUseDestination.Outcome.NotFound));
            Assert.That(ComputerUseDestination.Score(print, HowTo()), Is.Null);
            Assert.That(ComputerUseDestination.Choose(print, [Person(), HowTo()], frontWindow: false, Recent).Outcome,
                Is.EqualTo(ComputerUseDestination.Outcome.NotFound), "nobody named that page");
            Assert.That(ComputerUseDestination.Score(font, Notes()), Is.Null, "a file's name is its content");
            Assert.That(ComputerUseDestination.Choose(font, [Person(), Notes()], frontWindow: false, Recent).Outcome,
                Is.EqualTo(ComputerUseDestination.Outcome.NotFound));
            Assert.That(ComputerUseDestination.DialogItself(FontDialog()), Is.True);
            Assert.That(ComputerUseDestination.DialogItself(Notes()), Is.False);
            Assert.That(ComputerUseDestination.Score(font, FontDialog()), Is.EqualTo(2));
            var bound = ComputerUseDestination.Choose(font, [Person(), Fonts(), Notes(), FontDialog()], frontWindow: false, Recent);
            Assert.That(bound.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
            Assert.That((long?)bound.Window!["hwnd"], Is.EqualTo(44L));
            var english = ComputerUseDestination.Choose(print, [Person(), HowTo(), PrintDialog()], frontWindow: false, Recent);
            Assert.That(english.Outcome, Is.EqualTo(ComputerUseDestination.Outcome.Bound));
            Assert.That((long?)english.Window!["hwnd"], Is.EqualTo(45L));
        });
    }

    [Test]
    public void Revision3ContracaseTheSameWordsInTheFrameStillFit()
    {
        // The same words in the window's own frame (no content mark) are its structure: a Text «Imagen» menu and a
        // «Girar» button, a «Fuente» combo of a ribbon. The mark, never the control's kind, decides.
        var menu = new ComputerUseDestination.Referent(["imagen", "girar"], Selection: false);
        var font = new ComputerUseDestination.Referent([], Selection: false, Dialogs: ["fuente"]);
        JsonObject editor = Window(
            35, 935, "editor", "foto.png - Editor de imágenes", false, null, ("Text", "Imagen"), ("Button", "Girar"));
        JsonObject ribbon = Content(Window(
            36, 936, "WINWORD", "Informe - Word", false, null, ("TabItem", "Inicio"), ("ComboBox", "Fuente"),
            ("Document", "Informe"), ("Text", "Fuente: agencia")), 3);

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseDestination.Score(menu, editor), Is.EqualTo(4));
            Assert.That(ComputerUseDestination.Score(font, ribbon), Is.EqualTo(2), "the ribbon's combo counts, the text never");
            Assert.That(ComputerUseDestination.Choose(menu, [Person(), editor], frontWindow: false, Recent).Outcome,
                Is.EqualTo(ComputerUseDestination.Outcome.Bound));
        });
    }

    // Marks the controls at these positions as read inside a document (the provider's «content»).
    private static JsonObject Content(JsonObject window, params int[] positions)
    {
        foreach (int position in positions)
            ((JsonObject)((JsonArray)window["controls"]!)[position]!)["content"] = true;
        return window;
    }

    [Test]
    public void TheNewReferentArgumentsPassTheCatalogSchema()
    {
        OperationArgumentsSchema mission = ProductCatalog.GetRequired("mission.computer.use").ArgumentsSchema;

        Assert.Multiple(() =>
        {
            Assert.That(Valid(mission, new JsonObject
            {
                ["goal"] = "En el panel de miniaturas arrastra la diapositiva «Tres» para que quede la primera",
                ["referentItems"] = new JsonArray("tres"),
                ["referentLabels"] = new JsonArray("miniaturas"),
            }), Is.True);
            Assert.That(Valid(mission, new JsonObject
            {
                ["goal"] = "Ponme el texto seleccionado en Arial, desde el cuadro de diálogo de Fuente",
                ["referentDialogs"] = new JsonArray("fuente"),
                ["referentSelection"] = true,
            }), Is.True);
            // Counter-cases: a blank item, a dialog that is no list.
            Assert.That(Valid(mission, new JsonObject { ["goal"] = "x", ["referentItems"] = new JsonArray(" ") }), Is.False);
            Assert.That(Valid(mission, new JsonObject { ["goal"] = "x", ["referentDialogs"] = "fuente" }), Is.False);
        });
    }

    [Test]
    public void TheFinalNeverNamesAWindowNobodyAskedFor()
    {
        var state = new JsonObject { ["goal"] = "x", ["window"] = new JsonObject { ["title"] = "Spotify Premium" } };
        Assert.That(ComputerUseMission.WindowAsked(state), Is.False);
        foreach (JsonObject asked in new[]
        {
            new JsonObject { ["application"] = "Paint" },
            new JsonObject { ["frontWindow"] = true },
            new JsonObject { ["destinationBound"] = new JsonObject { ["hwnd"] = 6 } },
            new JsonObject { ["processId"] = 905 },
            new JsonObject { ["window"] = new JsonObject { ["requested"] = true } },
        })
        {
            Assert.That(ComputerUseMission.WindowAsked(asked), Is.True, asked.ToJsonString());
        }

        foreach (bool english in new[] { false, true })
        {
            var source = (JsonObject)JsonNode.Parse(
                """{"kind":"operation","operation":"mission.computer.use","polarity":"failure","verified":true,"succeeded":false,"observed":{"goal":"En el panel de miniaturas arrastra la diapositiva «Tres» para que quede la primera","reached":false,"steps":[],"window":{"title":"Spotify Premium"},"windowAsked":false,"stoppedBy":"computer_use_no_step_visible"}}""")!;
            string? final = OperationFloor.Final(source, english);
            Assert.That(final ?? string.Empty, Does.Not.Contain("Spotify"));
            // Counter-case: the window asked for is still named.
            source["observed"]!["windowAsked"] = true;
            Assert.That(OperationFloor.Final(source, english) ?? string.Empty, Does.Contain("Spotify Premium"));
        }
    }

    private static bool Valid(OperationArgumentsSchema schema, JsonObject arguments)
    {
        using JsonDocument document = JsonDocument.Parse(arguments.ToJsonString());
        return OperationArgumentValidator.IsValid(document.RootElement, schema);
    }

    internal static JsonObject Window(
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
        return window;
    }
}

internal static class DestinationWindowExtensions
{
    internal static JsonObject WithSelection(this JsonObject window, bool selection)
    {
        if (selection)
            window["selection"] = true;
        return window;
    }
}
