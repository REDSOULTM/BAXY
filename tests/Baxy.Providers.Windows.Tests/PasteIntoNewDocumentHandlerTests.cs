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

    private static JsonElement Element(string json)
    {
        using JsonDocument document = JsonDocument.Parse(json);
        return document.RootElement.Clone();
    }

    private static OperationInvocation Invocation(string arguments) =>
        new("request", "mission", "invocation", Element(arguments));

    private sealed class RecordingPaste : IOperationHandler
    {
        internal List<string> Arguments { get; } = [];

        public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("clipboard.paste");

        public ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
        {
            Arguments.Add(invocation.Arguments.GetRawText());
            return ValueTask.FromResult(OperationOutcome.Success(Element("""{"pasted":true}""")));
        }
    }
}
