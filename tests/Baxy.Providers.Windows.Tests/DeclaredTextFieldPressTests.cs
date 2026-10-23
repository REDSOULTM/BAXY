using System.Security.Cryptography;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Auditoría del núcleo 2026-10-23: input.key.press's <c>target:"text_field"</c> is the model's word; before Delete,
/// Enter or space go unasked on it, the key press's preflight reads what really holds the focus (the worker's
/// «focuskind»). A focus that is no text field, lies outside the window, or cannot be read asks; Enter asks in a
/// messaging client or a console even on its composer. Through the engine, with Core's handler and the real adapter.
/// </summary>
[TestFixture]
public sealed class DeclaredTextFieldPressTests
{
    private const string EditFocus = """{"ok":true,"kind":"Edit","editable":true,"text":true,"inside":true}""";

    // A text field in an ordinary window: Delete erases characters, Enter and space type; nothing asks.
    [TestCase("""{"key":"delete","target":"text_field","window":7}""", KeyWindowKind.Ordinary)]
    [TestCase("""{"key":"enter","target":"text_field","window":7}""", KeyWindowKind.Ordinary)]
    [TestCase("""{"key":"space","target":"text_field","window":7}""", KeyWindowKind.Messaging)]
    [TestCase("""{"key":"delete","target":"text_field"}""", KeyWindowKind.Messaging)]
    public async Task AKeyOnARealTextFieldGoesWithoutAsking(string arguments, KeyWindowKind kind)
    {
        (OperationResponse response, Keys keys, _) = await Press(arguments, EditFocus, kind);

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Completed), response.ErrorCode);
            Assert.That(keys.Pressed, Is.EqualTo(1));
        });
    }

    // What is declared a text field and is not (a file list, a button), lies outside the window, or cannot be read;
    // and Enter on a messaging client's composer or a console's line, which sends or runs what they hold.
    [TestCase("""{"key":"delete","target":"text_field"}""", """{"ok":true,"kind":"List","editable":false,"text":false,"inside":true}""", KeyWindowKind.Ordinary)]
    [TestCase("""{"key":"space","target":"text_field"}""", """{"ok":true,"kind":"Button","editable":false,"text":false,"inside":true}""", KeyWindowKind.Ordinary)]
    [TestCase("""{"key":"delete","target":"text_field","window":7}""", """{"ok":true,"kind":"Edit","editable":true,"text":true,"inside":false}""", KeyWindowKind.Ordinary)]
    [TestCase("""{"key":"delete","target":"text_field"}""", """{"ok":false,"error":"focus_not_found"}""", KeyWindowKind.Ordinary)]
    [TestCase("""{"key":"delete","target":"text_field"}""", null, KeyWindowKind.Ordinary)]
    [TestCase("""{"key":"enter","target":"text_field","window":7}""", EditFocus, KeyWindowKind.Messaging)]
    [TestCase("""{"key":"enter","target":"text_field"}""", EditFocus, KeyWindowKind.Console)]
    [TestCase("""{"key":"enter","target":"text_field"}""", EditFocus, KeyWindowKind.Unknown)]
    public async Task ADeclaredTextFieldThatIsNotOneAsks(string arguments, string? focus, KeyWindowKind kind)
    {
        (OperationResponse response, Keys keys, Fields fields) = await Press(arguments, focus, kind);

        Assert.Multiple(() =>
        {
            Assert.That(response.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(keys.Pressed, Is.Zero);
            Assert.That(fields.Asked, Is.EqualTo(1));
        });
    }

    // Contracases: a key the policy never asks for, or one with no declared text field, is not read here.
    [TestCase("""{"key":"tab","target":"text_field"}""")]
    [TestCase("""{"key":"backspace","target":"text_field"}""")]
    [TestCase("""{"key":"delete","target":"message_composer"}""")]
    public async Task OtherKeysAreNotReadForAFocus(string arguments)
    {
        (_, _, Fields fields) = await Press(arguments, EditFocus, KeyWindowKind.Ordinary);

        Assert.That(fields.Asked, Is.Zero);
    }

    private static async Task<(OperationResponse, Keys, Fields)> Press(string arguments, string? focus, KeyWindowKind kind)
    {
        var fields = new Fields(focus);
        var adapter = new WindowsDesktopInteractionAdapter(
            new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", new FakeDesktopKeyboard(), fields)
        {
            KeyWindows = new Reader(kind),
        };
        var keys = new Keys(adapter);
        IOperationHandler handler = ExternalCapabilityHandlers.Create(keys, keyWindows: new Reader(kind))
            .Single(candidate => candidate.Definition.Name == "input.key.press");
        string root = Path.Combine(Path.GetTempPath(), "baxy-text-field-press-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            await using FileInvocationJournal journal = await FileInvocationJournal.OpenAsync(
                Path.Combine(root, "journal.jsonl"),
                new JournalHmacAuthenticator(RandomNumberGenerator.GetBytes(JournalHmacAuthenticator.KeyLength)));
            using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
            OperationResponse response = await engine.ExecuteAsync(
                new OperationRequest(
                    ProtocolTypes.OperationRequest,
                    Guid.NewGuid().ToString("D"),
                    Guid.NewGuid().ToString("D"),
                    Guid.NewGuid().ToString("D"),
                    "input.key.press",
                    JsonDocument.Parse(arguments).RootElement.Clone()),
                CancellationToken.None);
            return (response, keys, fields);
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    // The provider: its preflight is the real adapter's; pressing is counted, nothing is sent.
    private sealed class Keys(WindowsDesktopInteractionAdapter adapter) : IExternalCapabilityProvider
    {
        public int Pressed { get; private set; }

        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation,
            JsonElement arguments,
            CancellationToken cancellationToken)
        {
            Pressed++;
            return ValueTask.FromResult(ExternalJson.Success(
                operation, JsonDocument.Parse("""{"version":1,"accepted":2}""").RootElement.Clone(), effectObserved: true));
        }

        public ValueTask<ExternalCapabilityReceipt?> PreflightAsync(
            string operation,
            JsonElement arguments,
            CancellationToken cancellationToken) =>
            adapter.PreflightAsync(operation, arguments, cancellationToken);

        public bool PreflightMayRaise(string operation, JsonElement arguments) =>
            adapter.PreflightMayRaise(operation, arguments);
    }

    private sealed class Fields(string? focus) : IViewedFields
    {
        public int Asked { get; private set; }

        public bool TryViewedField(int index, out nint window, out string controlId)
        {
            window = 0;
            controlId = string.Empty;
            return false;
        }

        public ValueTask<JsonDocument?> FieldAsync(
            nint window, string controlId, string? text, bool replace, CancellationToken cancellationToken) =>
            ValueTask.FromResult<JsonDocument?>(null);

        public ValueTask<JsonDocument?> EntryAsync(
            nint window, string controlId, string text, CancellationToken cancellationToken) =>
            ValueTask.FromResult<JsonDocument?>(null);

        public ValueTask<JsonDocument?> FocusKindAsync(nint window, CancellationToken cancellationToken)
        {
            Asked++;
            return ValueTask.FromResult(focus is null ? null : JsonDocument.Parse(focus));
        }
    }

    private sealed class Reader(KeyWindowKind kind) : IKeyWindowReader
    {
        public KeyWindowKind KindOf(long? window) => kind;
    }

    private sealed class NoProcessRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken) =>
            throw new AssertionException("a preflight starts no process");
    }
}
