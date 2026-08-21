using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Clipboard;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class ClipboardHandlerTests
{
    [Test]
    public async Task ControlledProviderProjectsStructuredPrivateRead()
    {
        var provider = new StubClipboardProvider();
        var handler = new ClipboardReadTextHandler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"maxCharacters\":42}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Verified, Is.True);
            Assert.That(outcome.Result!.Value.GetProperty("text").GetString(), Is.EqualTo("controlado"));
            Assert.That(outcome.Result.Value.GetProperty("sequenceNumber").GetUInt32(), Is.EqualTo(9));
            Assert.That(provider.LastLimit, Is.EqualTo(42));
            Assert.That(handler.Definition.Risk, Is.EqualTo(OperationRisk.Sensitive));
        });
    }

    [Test]
    public async Task ControlledProviderProjectsVerifiedWriteReceipt()
    {
        var provider = new StubClipboardProvider();
        var handler = new ClipboardWriteTextHandler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(
            Invocation("{\"text\":\"nuevo\"}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Result!.Value.GetProperty("changed").GetBoolean(), Is.True);
            Assert.That(provider.LastWritten, Is.EqualTo("nuevo"));
        });
    }

    private static OperationInvocation Invocation(string json) => new(
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        Guid.NewGuid().ToString("D"),
        JsonDocument.Parse(json).RootElement.Clone());

    private sealed class StubClipboardProvider : IClipboardProvider
    {
        public int? LastLimit { get; private set; }

        public string? LastWritten { get; private set; }

        public ValueTask<ClipboardTextSnapshot> ReadTextAsync(
            int maximumCharacters,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            LastLimit = maximumCharacters;
            string text = LastWritten ?? "controlado";
            return ValueTask.FromResult(new ClipboardTextSnapshot(text, text.Length, false, 9));
        }

        public ValueTask<ClipboardWriteResult> WriteTextAsync(
            string text,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            LastWritten = text;
            return ValueTask.FromResult(new ClipboardWriteResult(10, text.Length, true));
        }
    }
}
