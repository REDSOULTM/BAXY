using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew cu (C18): clipboard.paste.into opens a new document of the application named (in front, for control) and
/// then pastes, with no argument of its own; an opening that fails pastes nothing.
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
            return ValueTask.FromResult(OperationOutcome.Success(Element("""{"appId":"Word"}""")));
        });

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("""{"appId":"Word"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(opened, Has.Count.EqualTo(1));
            Assert.That(opened[0].GetProperty("appId").GetString(), Is.EqualTo("Word"));
            Assert.That(opened[0].GetProperty("newDocument").GetBoolean(), Is.True);
            Assert.That(opened[0].GetProperty("foreground").GetBoolean(), Is.True);
            Assert.That(paste.Arguments, Is.EqualTo(new[] { "{}" }));
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
            (_, _) => { opened++; return ValueTask.FromResult(OperationOutcome.Success(Element("{}"))); },
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
            (_, _) => { opened++; return ValueTask.FromResult(OperationOutcome.Success(Element("{}"))); },
            (_, _) => ValueTask.FromResult<Baxy.Providers.Windows.External.OfficePasteResult?>(null));

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("""{"appId":"Word"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(opened, Is.EqualTo(1));
            Assert.That(paste.Arguments, Is.EqualTo(new[] { "{}" }));
        });
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
