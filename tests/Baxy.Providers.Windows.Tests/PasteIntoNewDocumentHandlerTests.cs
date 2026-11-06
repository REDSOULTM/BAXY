using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew cu (C18): clipboard.paste.into opens a new document of the application named (in front, for control) and
/// then pastes into the window that opening verified; an opening that fails pastes nothing.
/// </summary>
[TestFixture]
public sealed class PasteIntoNewDocumentHandlerTests
{
    [Test]
    public async Task TheApplicationIsOpenedWithANewDocumentThenPastedInto()
    {
        var opened = new List<JsonElement>();
        var paste = new RecordingPaste();
        var handler = new PasteIntoNewDocumentHandler(paste, (invocation, _) =>
        {
            opened.Add(invocation.Arguments.Clone());
            return ValueTask.FromResult(OperationOutcome.Success(Element("""{"appId":"Word","windowHandle":4242}""")));
        });

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("""{"appId":"Word"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(opened, Has.Count.EqualTo(1));
            Assert.That(opened[0].GetProperty("appId").GetString(), Is.EqualTo("Word"));
            Assert.That(opened[0].GetProperty("newDocument").GetBoolean(), Is.True);
            Assert.That(opened[0].GetProperty("foreground").GetBoolean(), Is.True);
            Assert.That(paste.Arguments, Is.EqualTo(new[] { """{"window":4242}""" }));
        });
    }

    [Test]
    public async Task AFailedOpeningPastesNothing()
    {
        var paste = new RecordingPaste();
        var handler = new PasteIntoNewDocumentHandler(paste,
            (_, _) => ValueTask.FromResult(OperationOutcome.Failure("app_not_found")));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"appId":"Programa Que No Existe"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("app_not_found"));
            Assert.That(paste.Arguments, Is.Empty);
        });
    }

    // Renew al máximo (w5): a paste refused after the application was opened (an empty clipboard, refused before any key)
    // keeps its code and says the application was opened, an effect that did occur; it read as «nothing happened».
    [Test]
    public async Task APasteThatFailsAfterTheOpeningSaysTheApplicationWasOpened()
    {
        var paste = new RecordingPaste(OperationOutcome.Failure("clipboard_empty"));
        var handler = new PasteIntoNewDocumentHandler(paste,
            (_, _) => ValueTask.FromResult(OperationOutcome.Success(Element("""{"windowHandle":4242}"""))));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"appId":"Bloc de notas"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("clipboard_empty"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            Assert.That(outcome.Result!.Value.GetProperty("applicationOpened").GetString(), Is.EqualTo("Bloc de notas"));
            Assert.That(paste.Arguments, Is.EqualTo(new[] { """{"window":4242}""" }));
        });
    }

    // BAXY Renew cu (C18 variante): Word already running takes the new document and the paste through its object model;
    // nothing is opened nor pasted by the window. Its failure is the answer, said as it is.
    [TestCase(true, null)]
    [TestCase(false, "paste_not_read_back")]
    public async Task AnOfficeApplicationAlreadyRunningTakesTheNewDocumentAndThePasteItself(bool verified, string? code)
    {
        var paste = new RecordingPaste();
        int opened = 0;
        var handler = new PasteIntoNewDocumentHandler(paste,
            (_, _) => { opened++; return ValueTask.FromResult(OperationOutcome.Success(Element("""{"windowHandle":4242}"""))); },
            (_, _) => ValueTask.FromResult<Baxy.Providers.Windows.External.OfficePasteResult?>(
                new(verified, true, code, "Documento2", verified ? 63 : 0)));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("""{"appId":"Word"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.EqualTo(verified));
            Assert.That(outcome.ErrorCode, Is.EqualTo(code));
            Assert.That(opened, Is.Zero);
            Assert.That(paste.Arguments, Is.Empty);
            if (verified)
                Assert.That(outcome.Result!.Value.GetProperty("document").GetString(), Is.EqualTo("Documento2"));
            else
                Assert.That(outcome.EffectMayHaveOccurred, Is.True);
        });
    }

    // Contracase: an application not running (or not Office) goes the ordinary way.
    [Test]
    public async Task AnApplicationNotRunningGoesTheOrdinaryWay()
    {
        var paste = new RecordingPaste();
        int opened = 0;
        var handler = new PasteIntoNewDocumentHandler(paste,
            (_, _) => { opened++; return ValueTask.FromResult(OperationOutcome.Success(Element("""{"windowHandle":4242}"""))); },
            (_, _) => ValueTask.FromResult<Baxy.Providers.Windows.External.OfficePasteResult?>(null));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("""{"appId":"Word"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(opened, Is.EqualTo(1));
            Assert.That(paste.Arguments, Is.EqualTo(new[] { """{"window":4242}""" }));
        });
    }

    // Auditoría del Core (w8): an opening asked in front while the person works elsewhere raises its window without
    // their keyboard (shownWithoutFocus), and a paste with no window went to theirs. The window the opening verified
    // reaches the provider as the mission's window, the one its lease brings up after the person's pause or refuses.
    [Test]
    public async Task ThePasteReachesTheProviderNamingTheOpenedWindowEvenWhenItWasShownWithoutFocus()
    {
        var provider = new RecordingProvider();
        var handler = new PasteIntoNewDocumentHandler(
            new ExternalCapabilityHandler("clipboard.paste", provider),
            (_, _) => ValueTask.FromResult(OperationOutcome.Success(Element(
                """{"appId":"Bloc de notas","windowHandle":4242,"foreground":false,"shownWithoutFocus":true}"""))));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"appId":"Bloc de notas"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(provider.Operations, Is.EqualTo(new[] { "clipboard.paste" }));
            Assert.That(Baxy.Providers.Windows.External.WindowsExternalCapabilityProvider.MissionWindow(provider.Arguments[0]),
                Is.EqualTo((nint)4242));
        });
    }

    // Contracase: an opening told done without the window it verified pastes nothing (the application may be open).
    [Test]
    public async Task AnOpeningWithoutItsWindowPastesNothing()
    {
        var paste = new RecordingPaste();
        var handler = new PasteIntoNewDocumentHandler(paste,
            (_, _) => ValueTask.FromResult(OperationOutcome.Success(Element("""{"appId":"Word"}"""))));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("""{"appId":"Word"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("verification_failed"));
            Assert.That(outcome.CauseCode, Is.EqualTo("paste_window_unknown"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            Assert.That(paste.Arguments, Is.Empty);
        });
    }

    // Encargo 94 (verificación en vivo 84, F3: 0 of 6): a window open under the name given takes the paste as it is:
    // nothing is opened, and no new document is made.
    [Test]
    public async Task AWindowOpenUnderTheNameTakesThePasteAndNothingIsOpened()
    {
        var paste = new RecordingPaste();
        int opened = 0;
        var handler = new PasteIntoNewDocumentHandler(paste,
            (_, _) => { opened++; return ValueTask.FromResult(OperationOutcome.Success(Element("""{"windowHandle":1}"""))); },
            destination: (_, _) => ValueTask.FromResult(PasteDestination.OpenWindow(4242)));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"appId":"Cuaderno Lumbre"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(opened, Is.Zero);
            Assert.That(paste.Arguments, Is.EqualTo(new[] { """{"window":4242}""" }));
        });
    }

    // A paste that fails in the window named is that failure: no application was opened, so none is told.
    [Test]
    public async Task APasteThatFailsInTheWindowNamedSaysNoApplicationWasOpened()
    {
        var paste = new RecordingPaste(OperationOutcome.Failure("clipboard_empty"));
        var handler = new PasteIntoNewDocumentHandler(paste,
            (_, _) => throw new InvalidOperationException("nothing is opened"),
            destination: (_, _) => ValueTask.FromResult(PasteDestination.OpenWindow(4242)));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"appId":"Cuaderno Lumbre"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("clipboard_empty"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(outcome.Result?.ValueKind == JsonValueKind.Object
                && outcome.Result.Value.TryGetProperty("applicationOpened", out _), Is.False);
        });
    }

    // Encargo 94 (verificación en vivo 84, F2): «pega…» with a browser's name opened the real browser of the person, with
    // their session, and left the text in its address bar. A browser is not opened: the document is the PC's text editor,
    // and the receipt says which, and what was asked.
    [Test]
    public async Task ABrowserIsNotOpenedAndTheReceiptSaysWhichEditorTookThePaste()
    {
        var opened = new List<string>();
        var paste = new RecordingPaste();
        var handler = new PasteIntoNewDocumentHandler(paste,
            (invocation, _) =>
            {
                opened.Add(invocation.Arguments.GetProperty("appId").GetString()!);
                return ValueTask.FromResult(OperationOutcome.Success(Element("""{"windowHandle":4242}""")));
            },
            destination: (_, _) => ValueTask.FromResult(PasteDestination.EditorForBrowser("Editor Lumbre")));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"appId":"Navegador Nimbo"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(opened, Is.EqualTo(new[] { "Editor Lumbre" }));
            Assert.That(paste.Arguments, Is.EqualTo(new[] { """{"window":4242}""" }));
            JsonElement facts = outcome.Result!.Value;
            Assert.That(facts.GetProperty("pasted").GetBoolean(), Is.True);
            Assert.That(facts.GetProperty("textEditor").GetString(), Is.EqualTo("Editor Lumbre"));
            Assert.That(facts.GetProperty("browserNotOpened").GetString(), Is.EqualTo("Navegador Nimbo"));
            Assert.That(facts.GetProperty("next").GetString(), Does.Contain("Editor Lumbre").And.Contain("Navegador Nimbo"));
        });
    }

    // Live: told only new_document_not_created, the model opened the browser itself by app_open. The failure says the
    // browser was not opened, and why; what failed was the editor's document.
    [Test]
    public async Task AnEditorThatFailsSaysTheBrowserWasNotOpenedAndWhy()
    {
        var paste = new RecordingPaste();
        var handler = new PasteIntoNewDocumentHandler(paste,
            (_, _) => ValueTask.FromResult(OperationOutcome.Failure("new_document_not_created", effectMayHaveOccurred: true)),
            destination: (_, _) => ValueTask.FromResult(PasteDestination.EditorForBrowser("Editor Lumbre")));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"appId":"Navegador Nimbo"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("new_document_not_created"));
            Assert.That(paste.Arguments, Is.Empty);
            JsonElement facts = outcome.Result!.Value;
            Assert.That(facts.GetProperty("browserNotOpened").GetString(), Is.EqualTo("Navegador Nimbo"));
            Assert.That(facts.GetProperty("textEditor").GetString(), Is.EqualTo("Editor Lumbre"));
            Assert.That(facts.GetProperty("next").GetString(), Does.Contain("nothing was pasted").And.Contain("was not opened"));
        });
    }

    // With no fit editor nothing is opened and nothing pasted, and the failure says what else takes it.
    [Test]
    public async Task WithNoEditorABrowserNamedFailsHonestlyOpeningNothing()
    {
        var paste = new RecordingPaste();
        var handler = new PasteIntoNewDocumentHandler(paste,
            (_, _) => throw new InvalidOperationException("nothing is opened"),
            destination: (_, _) => ValueTask.FromResult(PasteDestination.EditorForBrowser(null)),
            desktop: () => [("cuaderno", "Cuaderno Lumbre")]);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"appId":"Navegador Nimbo"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("paste_no_text_editor"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(paste.Arguments, Is.Empty);
            JsonElement facts = outcome.Result!.Value;
            Assert.That(facts.GetProperty("openWindows")[0].GetProperty("title").GetString(), Is.EqualTo("Cuaderno Lumbre"));
            Assert.That(facts.GetProperty("next").GetString(), Does.Contain("Navegador Nimbo"));
        });
    }

    // Live (encargo 94): led by the editor's call, the model pasted into a new document with the window named in view. A
    // window whose title holds the name leads, with its call written as the title reads (a next that leads with the call
    // is followed: encargos 20, 28 and 34), its minimized mark left out.
    [TestCase("Cuaderno Lumbre")]
    [TestCase("Cuaderno Lumbre (minimizada)")]
    public async Task AWindowWhoseTitleHoldsTheNameLeadsTheNext(string title)
    {
        var handler = new PasteIntoNewDocumentHandler(new RecordingPaste(),
            (_, _) => ValueTask.FromResult(OperationOutcome.Failure("app_not_found")),
            destination: (_, _) => ValueTask.FromResult(PasteDestination.NewDocument("cuaderno", "Editor Lumbre")),
            desktop: () => [("otro", "Otra Ventana"), ("cuaderno", title)]);

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("""{"appId":"cuaderno"}"""), CancellationToken.None);

        string next = outcome.Result!.Value.GetProperty("next").GetString()!;
        Assert.Multiple(() =>
        {
            Assert.That(next, Does.StartWith("""clipboard_paste_into {"appId":"Cuaderno Lumbre"} pastes into that window"""));
            Assert.That(next, Does.Contain("pasted nothing"));
        });
    }

    // F3: «no está abierto» with the window in view came from a failure that listed no window. A name that answers to
    // nothing says so first and the windows open; the editor only as what makes a new document, if that is what the
    // person wants (a next that led with its call was followed with a window named: above).
    [Test]
    public async Task ANameThatAnswersToNothingSaysTheWindowsOpenAndTheTextEditor()
    {
        var paste = new RecordingPaste();
        var handler = new PasteIntoNewDocumentHandler(paste,
            (_, _) => ValueTask.FromResult(OperationOutcome.Failure("app_not_found", Element("""{"candidates":["Otra Cosa"]}"""))),
            destination: (_, _) => ValueTask.FromResult(PasteDestination.NewDocument("Algo Inventado", "Editor Lumbre")),
            desktop: () => [("cuaderno", "Cuaderno Lumbre")]);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"appId":"Algo Inventado"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.ErrorCode, Is.EqualTo("app_not_found"));
            Assert.That(paste.Arguments, Is.Empty);
            JsonElement facts = outcome.Result!.Value;
            Assert.That(facts.GetProperty("candidates")[0].GetString(), Is.EqualTo("Otra Cosa"));
            Assert.That(facts.GetProperty("openWindows")[0].GetProperty("title").GetString(), Is.EqualTo("Cuaderno Lumbre"));
            Assert.That(facts.GetProperty("openWindows")[0].GetProperty("process").GetString(), Is.EqualTo("cuaderno"));
            string next = facts.GetProperty("next").GetString()!;
            Assert.That(next, Does.StartWith("this call pasted nothing"));
            Assert.That(next, Does.Contain("Algo Inventado").And.Contain("openWindows"));
            Assert.That(next, Does.Contain("""if the person wants a new document: clipboard_paste_into {"appId":"Editor Lumbre"}"""));
        });
    }

    private sealed class RecordingProvider : Baxy.Providers.Windows.External.IExternalCapabilityProvider
    {
        internal List<string> Operations { get; } = [];

        internal List<JsonElement> Arguments { get; } = [];

        public ValueTask<Baxy.Providers.Windows.External.ExternalCapabilityReceipt> InvokeAsync(
            string operation, JsonElement arguments, CancellationToken cancellationToken)
        {
            Operations.Add(operation);
            Arguments.Add(arguments.Clone());
            return ValueTask.FromResult(Baxy.Providers.Windows.External.ExternalJson.Success(
                operation, Element("""{"version":1,"delivered":true}""")));
        }
    }

    [TestCase("Word", "word")]
    [TestCase("Microsoft Excel", "excel")]
    [TestCase("Bloc de notas", null)]
    public void TheOfficeApplicationIsToldByItsName(string name, string? office)
    {
        Assert.That(Baxy.Providers.Windows.External.OfficeNewDocumentPaste.OfficeOf(name), Is.EqualTo(office));
    }

    private static JsonElement Element(string json)
    {
        using JsonDocument document = JsonDocument.Parse(json);
        return document.RootElement.Clone();
    }

    private static OperationInvocation Invocation(string arguments) =>
        new("request", "mission", "invocation", Element(arguments));

    private sealed class RecordingPaste(OperationOutcome? answer = null) : IOperationHandler
    {
        internal List<string> Arguments { get; } = [];

        public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("clipboard.paste");

        public ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
        {
            Arguments.Add(invocation.Arguments.GetRawText());
            return ValueTask.FromResult(answer ?? OperationOutcome.Success(Element("""{"pasted":true}""")));
        }
    }
}
