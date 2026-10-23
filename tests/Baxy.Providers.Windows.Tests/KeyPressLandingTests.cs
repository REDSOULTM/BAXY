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
/// Al máximo, K-2 refinada (2026-10-22): Enter with neither target nor onto asks in normal mode only where it may send
/// or run something: a messaging client (the clients message.draft writes into), a console, or a window that cannot be
/// read. In a search box it goes without asking. Through the engine, with Core's handler and its preflight.
/// </summary>
[TestFixture]
public sealed class KeyPressLandingTests
{
    [Test]
    public async Task EnterWithNoTargetInASearchWindowGoesWithoutAsking()
    {
        (OperationResponse response, KeysProvider keys) = await Press(KeyWindowKind.Ordinary, """{"key":"enter","window":7}""");

        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Completed), response.ErrorCode);
            Assert.That(keys.Pressed, Is.EqualTo(1));
        });
    }

    [TestCase(KeyWindowKind.Messaging, """{"key":"enter","window":7}""")]
    [TestCase(KeyWindowKind.Messaging, """{"key":"space"}""")]
    [TestCase(KeyWindowKind.Console, """{"key":"enter"}""")]
    [TestCase(KeyWindowKind.Unknown, """{"key":"enter","window":7}""")]
    public async Task EnterWithNoTargetInAMessagingConsoleOrUnknownWindowAsks(KeyWindowKind kind, string arguments)
    {
        (OperationResponse response, KeysProvider keys) = await Press(kind, arguments);

        Assert.Multiple(() =>
        {
            Assert.That(response.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(keys.Pressed, Is.Zero);
        });
    }

    // Contracaso: a declared landing is judged as before; onto a send control it asks in any window.
    [Test]
    public async Task ADeclaredLandingIsNotReadAgain()
    {
        var reader = new FixedReader(KeyWindowKind.Ordinary);
        (OperationResponse response, KeysProvider keys) = await Press(reader, """{"key":"enter","onto":"Send"}""");

        Assert.Multiple(() =>
        {
            Assert.That(response.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(keys.Pressed, Is.Zero);
            Assert.That(reader.Reads, Is.Zero);
        });
    }

    // Contracaso: a reader that fails keeps the question.
    [Test]
    public async Task AReaderThatFailsKeepsTheQuestion()
    {
        (OperationResponse response, KeysProvider keys) = await Press(new FixedReader(null), """{"key":"enter"}""");

        Assert.Multiple(() =>
        {
            Assert.That(response.ErrorCode, Is.EqualTo("confirmation_required"));
            Assert.That(keys.Pressed, Is.Zero);
        });
    }

    // The providers' own data: the messaging clients' process names and the protected consoles' and editors'.
    [TestCase("chrome", KeyWindowKind.Ordinary)]
    [TestCase("msedge.exe", KeyWindowKind.Ordinary)]
    [TestCase("WhatsApp.Root", KeyWindowKind.Messaging)]
    [TestCase("Discord.exe", KeyWindowKind.Messaging)]
    [TestCase("WindowsTerminal", KeyWindowKind.Console)]
    [TestCase("cmd", KeyWindowKind.Console)]
    [TestCase("pwsh.exe", KeyWindowKind.Console)]
    [TestCase("Code", KeyWindowKind.Console)]
    [TestCase("", KeyWindowKind.Unknown)]
    public void AWindowIsToldByItsProcessNames(string processName, KeyWindowKind expected) =>
        Assert.That(KeyWindowReader.Classify([processName]), Is.EqualTo(expected));

    // A frame's own process (ApplicationFrameHost) is ordinary; the app it hosts decides.
    [Test]
    public void TheHostedAppDecidesOverItsFrame() =>
        Assert.That(KeyWindowReader.Classify(["ApplicationFrameHost", "WhatsApp.Root"]), Is.EqualTo(KeyWindowKind.Messaging));

    // A window that does not exist cannot be read: unknown, and the press keeps asking. Read only, no input sent.
    [Test]
    public void AWindowThatDoesNotExistIsUnknown() =>
        Assert.That(new KeyWindowReader().KindOf(0x7FFF_FFF0), Is.EqualTo(KeyWindowKind.Unknown));

    private static Task<(OperationResponse, KeysProvider)> Press(KeyWindowKind kind, string arguments) =>
        Press(new FixedReader(kind), arguments);

    private static async Task<(OperationResponse, KeysProvider)> Press(IKeyWindowReader reader, string arguments)
    {
        var keys = new KeysProvider();
        IOperationHandler handler = ExternalCapabilityHandlers.Create(keys, keyWindows: reader)
            .Single(candidate => candidate.Definition.Name == "input.key.press");
        string root = Path.Combine(Path.GetTempPath(), "baxy-key-landing-" + Guid.NewGuid().ToString("N"));
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
            return (response, keys);
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    private sealed class FixedReader(KeyWindowKind? kind) : IKeyWindowReader
    {
        public int Reads { get; private set; }

        public KeyWindowKind KindOf(long? window)
        {
            Reads++;
            return kind ?? throw new InvalidOperationException("the window cannot be read");
        }
    }

    private sealed class KeysProvider : IExternalCapabilityProvider
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
    }
}
