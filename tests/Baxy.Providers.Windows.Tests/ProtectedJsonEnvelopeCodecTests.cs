using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Security.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class ProtectedJsonEnvelopeCodecTests
{
    [Test]
    public void JsonEnvelopeRoundTripsWithoutPersistingPlaintext()
    {
        using TemporaryDirectory temporary = new();
        var codec = CreateCodec(temporary);
        byte[] plaintext = "{\"name\":\"BAXY-CANARY-private-memory\",\"revision\":1}"u8.ToArray();

        JsonElement envelope = codec.Seal(
            plaintext,
            ProtectedPayloadPurposes.MemoryArgumentsV1);
        byte[] opened = codec.Open(
            envelope,
            ProtectedPayloadPurposes.MemoryArgumentsV1);

        try
        {
            Assert.Multiple(() =>
            {
                Assert.That(opened, Is.EqualTo(plaintext));
                Assert.That(envelope.GetProperty("version").GetInt32(), Is.EqualTo(1));
                Assert.That(
                    envelope.GetProperty("protection").GetString(),
                    Is.EqualTo("windows-dpapi-current-user"));
                Assert.That(
                    envelope.GetRawText(),
                    Does.Not.Contain("BAXY-CANARY-private-memory"));
            });
        }
        finally
        {
            CryptographicOperations.ZeroMemory(opened);
            CryptographicOperations.ZeroMemory(plaintext);
        }
    }

    [Test]
    public void JsonEnvelopeBindsThePublicAndAuthenticatedPurpose()
    {
        using TemporaryDirectory temporary = new();
        var codec = CreateCodec(temporary);
        JsonElement envelope = codec.Seal(
            "{\"scope\":\"all\"}"u8,
            ProtectedPayloadPurposes.MemoryArgumentsV1);

        ProtectedPayloadException? exception = Assert.Throws<ProtectedPayloadException>(() =>
            codec.Open(envelope, ProtectedPayloadPurposes.MemoryResultV1));

        Assert.That(exception!.ErrorCode, Is.EqualTo(ProtectedPayloadErrorCode.InvalidEnvelope));
    }

    [TestCase("{\"version\":1,\"protection\":\"windows-dpapi-current-user\",\"purpose\":\"memory.arguments.v1\"}")]
    [TestCase("{\"version\":2,\"protection\":\"windows-dpapi-current-user\",\"purpose\":\"memory.arguments.v1\",\"ciphertext\":\"AAAA\"}")]
    [TestCase("{\"version\":1,\"protection\":\"wrong\",\"purpose\":\"memory.arguments.v1\",\"ciphertext\":\"AAAA\"}")]
    [TestCase("{\"version\":1,\"protection\":\"windows-dpapi-current-user\",\"purpose\":\"memory.arguments.v1\",\"ciphertext\":\"not+canonical/for_url\"}")]
    [TestCase("{\"version\":1,\"protection\":\"windows-dpapi-current-user\",\"purpose\":\"memory.arguments.v1\",\"ciphertext\":\"AAAA\",\"extra\":1}")]
    [TestCase("{\"version\":1,\"version\":1,\"protection\":\"windows-dpapi-current-user\",\"purpose\":\"memory.arguments.v1\",\"ciphertext\":\"AAAA\"}")]
    public void JsonEnvelopeRejectsMalformedNonCanonicalAndDuplicateShapes(string json)
    {
        using TemporaryDirectory temporary = new();
        var codec = CreateCodec(temporary);
        using JsonDocument document = JsonDocument.Parse(json);

        ProtectedPayloadException? exception = Assert.Throws<ProtectedPayloadException>(() =>
            codec.Open(document.RootElement, ProtectedPayloadPurposes.MemoryArgumentsV1));

        Assert.That(exception!.ErrorCode, Is.EqualTo(ProtectedPayloadErrorCode.InvalidEnvelope));
    }

    [TestCase("")]
    [TestCase("not-json")]
    [TestCase("{\"duplicate\":1,\"duplicate\":2}")]
    public void JsonEnvelopeRejectsEmptyInvalidOrDuplicatePlaintextJson(string plaintext)
    {
        using TemporaryDirectory temporary = new();
        var codec = CreateCodec(temporary);

        ProtectedPayloadException? exception = Assert.Throws<ProtectedPayloadException>(() =>
            codec.Seal(Encoding.UTF8.GetBytes(plaintext), ProtectedPayloadPurposes.MemoryArgumentsV1));

        Assert.That(exception!.ErrorCode, Is.EqualTo(ProtectedPayloadErrorCode.InvalidPlaintext));
    }

    [Test]
    public void JsonEnvelopeRejectsTamperedCiphertextWithoutLeakingPayload()
    {
        using TemporaryDirectory temporary = new();
        var codec = CreateCodec(temporary);
        JsonElement envelope = codec.Seal(
            "{\"secret\":\"BAXY-PRIVATE-DO-NOT-LEAK\"}"u8,
            ProtectedPayloadPurposes.MemoryResultV1);
        string ciphertext = envelope.GetProperty("ciphertext").GetString()!;
        char replacement = ciphertext[8] == 'A' ? 'B' : 'A';
        string tampered = ciphertext[..8] + replacement + ciphertext[9..];
        JsonObject envelopeObject = JsonNode.Parse(envelope.GetRawText())!.AsObject();
        envelopeObject["ciphertext"] = tampered;
        using JsonDocument document = JsonDocument.Parse(envelopeObject.ToJsonString());

        ProtectedPayloadException? exception = Assert.Throws<ProtectedPayloadException>(() =>
            codec.Open(document.RootElement, ProtectedPayloadPurposes.MemoryResultV1));

        Assert.Multiple(() =>
        {
            Assert.That(exception!.ErrorCode, Is.EqualTo(ProtectedPayloadErrorCode.InvalidEnvelope));
            Assert.That(exception.Message, Does.Not.Contain("BAXY-PRIVATE-DO-NOT-LEAK"));
            Assert.That(exception.Message, Does.Not.Contain("memory.result"));
        });
    }

    [Test]
    public void JsonEnvelopeEnforcesItsWireBoundBeforeProtection()
    {
        using TemporaryDirectory temporary = new();
        var codec = CreateCodec(temporary);
        byte[] oversized = new byte[ProtectedJsonEnvelopeCodec.MaximumPlaintextBytes + 1];
        Array.Fill(oversized, (byte)' ');

        ProtectedPayloadException? exception = Assert.Throws<ProtectedPayloadException>(() =>
            codec.Seal(oversized, ProtectedPayloadPurposes.MemoryArgumentsV1));

        Assert.That(exception!.ErrorCode, Is.EqualTo(ProtectedPayloadErrorCode.PayloadTooLarge));
    }

    private static ProtectedJsonEnvelopeCodec CreateCodec(TemporaryDirectory temporary) =>
        new(new WindowsProtectedPayload(Path.Combine(temporary.Path, "security", "payload.key")));

    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(
                System.IO.Path.GetTempPath(),
                $"baxy-envelope-codec-{Guid.NewGuid():N}");
            Directory.CreateDirectory(Path);
        }

        public string Path { get; }

        public void Dispose()
        {
            if (Directory.Exists(Path))
            {
                Directory.Delete(Path, recursive: true);
            }
        }
    }
}
