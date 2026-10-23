using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
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
            (_, _) => ValueTask.FromResult(OperationOutcome.Success(Element("{}"))));

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("""{"appId":"Bloc de notas"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("clipboard_empty"));
            Assert.That(outcome.EffectMayHaveOccurred, Is.True);
            Assert.That(outcome.Result!.Value.GetProperty("applicationOpened").GetString(), Is.EqualTo("Bloc de notas"));
            Assert.That(paste.Arguments, Is.EqualTo(new[] { "{}" }));
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
