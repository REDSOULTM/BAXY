using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Security.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class BoundProtectedJsonCodecTests
{
    private const string Canary = "BAXY-BOUND-PRIVATE-CANARY";

    [Test]
    public void ArgumentsRoundTripWithOperationAndInvocationBinding()
    {
        using TemporaryDirectory temporary = new();
        BoundProtectedJsonCodec codec = CreateCodec(temporary);
        string missionId = NewId();
        string invocationId = NewId();
        string sessionId = NewId();
        var payload = new JsonObject
        {
            ["selector"] = "name",
            ["value"] = Canary,
        };

        JsonElement envelope = codec.SealArguments(
            "memory.save",
            missionId,
            invocationId,
            sessionId,
            payload);

        using OpenedBoundProtectedJson opened = codec.OpenArguments(
            envelope,
            "memory.save",
            missionId,
            invocationId);
        Assert.Multiple(() =>
        {
            Assert.That(opened.SessionId, Is.EqualTo(sessionId));
            Assert.That(opened.Payload.GetProperty("value").GetString(), Is.EqualTo(Canary));
            Assert.That(envelope.GetRawText(), Does.Not.Contain(Canary));
            Assert.That(opened.ToString(), Does.Not.Contain(Canary));
        });
    }

    [Test]
    public void ArgumentsCannotBeRelabeledAcrossOperationMissionOrInvocation()
    {
        using TemporaryDirectory temporary = new();
        BoundProtectedJsonCodec codec = CreateCodec(temporary);
        string missionId = NewId();
        string invocationId = NewId();
        JsonElement envelope = codec.SealArguments(
            "memory.save",
            missionId,
            invocationId,
            NewId(),
            new JsonObject { ["value"] = Canary });

        Assert.Multiple(() =>
        {
            Assert.That(
                () => codec.OpenArguments(
                    envelope,
                    "memory.forget",
                    missionId,
                    invocationId),
                Throws.TypeOf<ProtectedPayloadException>()
                    .With.Property(nameof(ProtectedPayloadException.ErrorCode))
                    .EqualTo(ProtectedPayloadErrorCode.InvalidEnvelope));
            Assert.That(
                () => codec.OpenArguments(envelope, "memory.save", NewId(), invocationId),
                Throws.TypeOf<ProtectedPayloadException>());
            Assert.That(
                () => codec.OpenArguments(envelope, "memory.save", missionId, NewId()),
                Throws.TypeOf<ProtectedPayloadException>());
        });
    }

    [Test]
    public void ResultDirectionAndIdentityAreAuthenticated()
    {
        using TemporaryDirectory temporary = new();
        BoundProtectedJsonCodec codec = CreateCodec(temporary);
        string missionId = NewId();
        string invocationId = NewId();
        string sessionId = NewId();
        using JsonDocument resultDocument = JsonDocument.Parse(
            $"{{\"message\":\"{Canary}\",\"count\":1}}");
        JsonElement envelope = codec.SealResult(
            "memory.recall",
            missionId,
            invocationId,
            sessionId,
            resultDocument.RootElement);

        using OpenedBoundProtectedJson opened = codec.OpenResult(
            envelope,
            "memory.recall",
            missionId,
            invocationId);
        Assert.Multiple(() =>
        {
            Assert.That(opened.Payload.GetProperty("message").GetString(), Is.EqualTo(Canary));
            Assert.That(
                () => codec.OpenArguments(
                    envelope,
                    "memory.recall",
                    missionId,
                    invocationId),
                Throws.TypeOf<ProtectedPayloadException>());
            Assert.That(envelope.GetRawText(), Does.Not.Contain(Canary));
        });
    }

    [TestCase("Memory.Save")]
    [TestCase("memory")]
    [TestCase("memory.save-sensitive")]
    public void InvalidPublicBindingsAreRejectedBeforeSealing(string operation)
    {
        using TemporaryDirectory temporary = new();
        BoundProtectedJsonCodec codec = CreateCodec(temporary);

        Assert.That(
            () => codec.SealArguments(
                operation,
                NewId(),
                NewId(),
                NewId(),
                new JsonObject()),
            Throws.TypeOf<ProtectedPayloadException>()
                .With.Property(nameof(ProtectedPayloadException.ErrorCode))
                .EqualTo(ProtectedPayloadErrorCode.InvalidPurpose));
    }

    private static BoundProtectedJsonCodec CreateCodec(TemporaryDirectory temporary) =>
        new(new WindowsProtectedPayload(Path.Combine(temporary.Path, "payload.key")));

    private static string NewId() => Guid.NewGuid().ToString("D");

    private sealed class TemporaryDirectory : IDisposable
    {
        internal TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(
                System.IO.Path.GetTempPath(),
                $"baxy-bound-payload-{Guid.NewGuid():N}");
            Directory.CreateDirectory(Path);
        }

        internal string Path { get; }

        public void Dispose()
        {
            if (Directory.Exists(Path))
            {
                Directory.Delete(Path, recursive: true);
            }
        }
    }
}
