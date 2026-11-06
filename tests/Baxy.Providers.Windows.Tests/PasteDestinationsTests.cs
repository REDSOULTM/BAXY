using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo 94: where a paste named goes. The windows open come first (title and process, as the window operations), and
/// only with none does the installed application count; yet an application's own name keeps its new document, because
/// «un Bloc de notas nuevo» once went into the person's open note (cu-v3-documento-nuevo), and no browser is ever opened.
/// </summary>
[TestFixture]
public sealed class PasteDestinationsTests
{
    private const long Window = 4242;

    // Live (encargo 94): Windows 11's Notepad titles «nota.txt: Bloc de notas», so naming the document found no window,
    // and the paste went into a new document instead. A whole document name of the title names it, with or without its
    // file's extension, also unsaved («*»); never a word of it, nor the program's own name after the separator.
    [TestCase("lista_lumbre.txt: Editor Lumbre", "lista_lumbre", true)]
    [TestCase("lista_lumbre.txt: Editor Lumbre", "lista_lumbre.txt", true)]
    [TestCase("*lista_lumbre.txt: Editor Lumbre", "Lista_Lumbre", true)]
    [TestCase("lista lumbre.txt - Editor Lumbre", "lista lumbre", true)]
    [TestCase("Recetas de pan - Sitio - Navegador", "Sitio", true)]
    [TestCase("lista_lumbre.txt: Editor Lumbre", "lista", false)]
    [TestCase("lista_lumbre.txt: Editor Lumbre", "Editor Lumbre", false)]
    [TestCase("versión 1.2 final: Editor Lumbre", "versión 1", false)]
    [TestCase("Cuaderno Lumbre", "Cuaderno", false)]
    public void ADocumentIsNamedByItsWholeNameInTheTitle(string title, string name, bool names)
    {
        Assert.That(VisibleControlSurface.TitleNamesDocument(title, name), Is.EqualTo(names));
    }

    private static PasteDestinations Destinations(
        long window = 0,
        InstalledApplicationFacts? installed = null,
        string? editor = "Editor Lumbre",
        List<bool>? documents = null) =>
        new(
            (_, inDocuments, _) =>
            {
                documents?.Add(inDocuments);
                return ValueTask.FromResult(window);
            },
            (_, _) => ValueTask.FromResult(installed),
            _ => ValueTask.FromResult(editor));

    [Test]
    public async Task AWindowOpenUnderANameNoApplicationBearsIsTheDestination()
    {
        var documents = new List<bool>();

        PasteDestination where = await Destinations(window: Window, documents: documents)
            .ResolveAsync("Cuaderno Lumbre", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(where.Window, Is.EqualTo(Window));
            Assert.That(where.Application, Is.Null);
            // No installed application bears it: a document's title in any program may be the name.
            Assert.That(documents, Is.EqualTo(new[] { true }));
        });
    }

    // Contracase of the reuse: «un Bloc de notas nuevo» with the person's note open names the application, whose own
    // window is that note. It keeps its new document, never that window.
    [Test]
    public async Task AnApplicationsOwnNameKeepsItsNewDocumentWithItsWindowOpen()
    {
        var documents = new List<bool>();

        PasteDestination where = await Destinations(
                window: Window, installed: new InstalledApplicationFacts("Bloc Lumbre", false, [Window]), documents: documents)
            .ResolveAsync("Bloc Lumbre", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(where.Window, Is.Zero);
            Assert.That(where.Application, Is.EqualTo("Bloc Lumbre"));
            // An installed application's name is never read as a document's title («Steam - Bloc de notas»).
            Assert.That(documents, Is.EqualTo(new[] { false }));
        });
    }

    // A window that does bear the name, of another program than the installed application of that name.
    [Test]
    public async Task AWindowOfAnotherProgramUnderAnInstalledNameIsTheDestination()
    {
        PasteDestination where = await Destinations(
                window: Window, installed: new InstalledApplicationFacts("Faro", false, [1, 2]))
            .ResolveAsync("Faro", CancellationToken.None);

        Assert.That(where.Window, Is.EqualTo(Window));
    }

    // With its windows unread nothing proves the window is another program's: the person's document is never risked.
    [Test]
    public async Task AnApplicationWhoseWindowsCouldNotBeReadKeepsItsNewDocument()
    {
        PasteDestination where = await Destinations(
                window: Window, installed: new InstalledApplicationFacts("Bloc Lumbre", false, null))
            .ResolveAsync("Bloc Lumbre", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(where.Window, Is.Zero);
            Assert.That(where.Application, Is.EqualTo("Bloc Lumbre"));
        });
    }

    // A browser already open is a window like any other: nothing is launched and no new session starts.
    [Test]
    public async Task ABrowserAlreadyOpenTakesThePasteInItsWindow()
    {
        PasteDestination where = await Destinations(
                window: Window, installed: new InstalledApplicationFacts("Navegador Nimbo", true, [Window]))
            .ResolveAsync("Navegador Nimbo", CancellationToken.None);

        Assert.That(where.Window, Is.EqualTo(Window));
    }

    [Test]
    public async Task ABrowserNotOpenGivesWayToTheTextEditor()
    {
        PasteDestination where = await Destinations(installed: new InstalledApplicationFacts("Navegador Nimbo", true, []))
            .ResolveAsync("Navegador Nimbo", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(where.Window, Is.Zero);
            Assert.That(where.InsteadOfBrowser, Is.True);
            Assert.That(where.Application, Is.EqualTo("Editor Lumbre"));
        });
    }

    [Test]
    public async Task ABrowserNotOpenWithNoEditorHasNoDestination()
    {
        PasteDestination where = await Destinations(
                installed: new InstalledApplicationFacts("Navegador Nimbo", true, []), editor: null)
            .ResolveAsync("Navegador Nimbo", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(where.InsteadOfBrowser, Is.True);
            Assert.That(where.Application, Is.Null);
        });
    }

    [Test]
    public async Task AnInstalledApplicationNotOpenIsItsNewDocument()
    {
        PasteDestination where = await Destinations(installed: new InstalledApplicationFacts("Bloc Lumbre", false, []))
            .ResolveAsync("Bloc Lumbre", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(where.Window, Is.Zero);
            Assert.That(where.InsteadOfBrowser, Is.False);
            Assert.That(where.Application, Is.EqualTo("Bloc Lumbre"));
        });
    }

    // A name that answers to nothing goes to the opening, which refuses it; the editor is known, to be offered.
    [Test]
    public async Task ANameThatAnswersToNothingGoesToTheOpeningWithTheEditorKnown()
    {
        PasteDestination where = await Destinations().ResolveAsync("Algo Inventado", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(where.Window, Is.Zero);
            Assert.That(where.Application, Is.EqualTo("Algo Inventado"));
            Assert.That(where.TextEditor, Is.EqualTo("Editor Lumbre"));
        });
    }
}
