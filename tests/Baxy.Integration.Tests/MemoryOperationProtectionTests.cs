using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using Baxy.Security.Windows;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class MemoryOperationProtectionTests
{
    private const string Canary = "BAXY-MEMORY-CANARY-private-name-Alex";

    [Test]
    [NonParallelizable]
    public void AppAndOutboxRejectTheSameSharedDataRoot()
    {
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        string shared = Path.Combine(
            Environment.GetFolderPath(
                Environment.SpecialFolder.CommonApplicationData,
                Environment.SpecialFolderOption.DoNotVerify),
            $"baxy-shared-{Guid.NewGuid():N}");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", shared);
        try
        {
            Assert.Multiple(() =>
            {
                Assert.That(
                    () => MemoryOperationProtector.ResolveDataRoot(),
                    Throws.TypeOf<UnsafePrivateStoragePathException>());
                Assert.That(
                    () => DurableRetryStore.ResolveDefaultPath(),
                    Throws.TypeOf<UnsafePrivateStoragePathException>());
                Assert.That(Directory.Exists(shared), Is.False);
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
        }
    }

    [Test]
    public void ProtectedMemoryRouteSurvivesOutboxRestartWithoutPlaintext()
    {
        using TemporaryDirectory temporary = new();
        string outbox = Path.Combine(temporary.Path, "shell", "retry-outbox.v1.json");
        string sessionId = Guid.NewGuid().ToString("D");
        MemoryOperationProtector protector = CreateProtector(temporary, sessionId);

        ProtectedMemoryOperation protectedOperation = protector.Prepare(CreatePrivateRoute(Canary));
        PreparedOperation prepared = new RetryableOperationRegistry(outbox, protector)
            .GetOrAdd(protectedOperation);
        PreparedOperation recovered = new RetryableOperationRegistry(outbox, protector)
            .SnapshotPendingOperations()
            .Single();
        using OpenedBoundProtectedJson opened = protector.OpenPrivateArguments(recovered);

        Assert.Multiple(() =>
        {
            Assert.That(prepared.Arguments.GetRawText(), Does.Not.Contain(Canary));
            Assert.That(File.ReadAllText(outbox, Encoding.UTF8), Does.Not.Contain(Canary));
            Assert.That(
                Directory.EnumerateFiles(temporary.Path, "*", SearchOption.AllDirectories)
                    .SelectMany(File.ReadAllBytes)
                    .ContainsSequence(Encoding.UTF8.GetBytes(Canary)),
                Is.False);
            Assert.That(recovered.OperationName, Is.EqualTo("memory.save"));
            Assert.That(opened.Payload.GetProperty("value").GetString(), Is.EqualTo(Canary));
            Assert.That(opened.SessionId, Is.EqualTo(sessionId));
            Assert.That(recovered.MissionId, Is.EqualTo(prepared.MissionId));
            Assert.That(recovered.InvocationId, Is.EqualTo(prepared.InvocationId));
            Assert.That(recovered.Arguments.GetRawText(), Is.EqualTo(prepared.Arguments.GetRawText()));
        });
    }

    [Test]
    public void PreparingAgainUsesFreshIdentityWhileRecoveryKeepsTheExistingIdentity()
    {
        using TemporaryDirectory temporary = new();
        string outbox = Path.Combine(temporary.Path, "shell", "retry-outbox.v1.json");
        MemoryOperationProtector protector = CreateProtector(
            temporary,
            Guid.NewGuid().ToString("D"));
        MemoryRoutedOperation privateRoute = CreatePrivateRoute("same semantic value");

        ProtectedMemoryOperation first = protector.Prepare(privateRoute);
        ProtectedMemoryOperation second = protector.Prepare(privateRoute);
        PreparedOperation pending = new RetryableOperationRegistry(outbox, protector).GetOrAdd(first);
        PreparedOperation recovered = new RetryableOperationRegistry(outbox, protector)
            .SnapshotPendingOperations()
            .Single();

        Assert.Multiple(() =>
        {
            Assert.That(
                second.Prepared.Arguments.GetRawText(),
                Is.Not.EqualTo(first.Prepared.Arguments.GetRawText()));
            Assert.That(second.Prepared.MissionId, Is.Not.EqualTo(first.Prepared.MissionId));
            Assert.That(second.Prepared.InvocationId, Is.Not.EqualTo(first.Prepared.InvocationId));
            Assert.That(recovered.IdentityKey, Is.EqualTo(pending.IdentityKey));
            Assert.That(recovered.MissionId, Is.EqualTo(pending.MissionId));
            Assert.That(recovered.InvocationId, Is.EqualTo(pending.InvocationId));
        });
    }

    [Test]
    public void PrivateArgumentsRejectRelabelingAndNonMemoryOperations()
    {
        using TemporaryDirectory temporary = new();
        MemoryOperationProtector protector = CreateProtector(
            temporary,
            Guid.NewGuid().ToString("D"));
        PreparedOperation prepared = protector.Prepare(CreatePrivateRoute("value")).Prepared;
        PreparedOperation relabeled = PreparedOperation.Restore(
            "memory.recall",
            prepared.Arguments,
            prepared.MissionId,
            prepared.InvocationId);
        PreparedOperation reboundMission = PreparedOperation.Restore(
            prepared.OperationName,
            prepared.Arguments,
            Guid.NewGuid().ToString("D"),
            prepared.InvocationId);
        PreparedOperation wrongOperation = PreparedOperation.Create(
            "note.create",
            new JsonObject());

        Assert.Multiple(() =>
        {
            Assert.That(
                () => protector.OpenPrivateArguments(relabeled),
                Throws.TypeOf<ProtectedPayloadException>());
            Assert.That(
                () => protector.OpenPrivateArguments(reboundMission),
                Throws.TypeOf<ProtectedPayloadException>());
            Assert.That(
                () => protector.OpenPrivateArguments(wrongOperation),
                Throws.TypeOf<InvalidDataException>());
        });
    }

    [Test]
    public void ProtectedResultOpensOnlyForTheBoundPreparedOperationAndSession()
    {
        using TemporaryDirectory temporary = new();
        string sessionId = Guid.NewGuid().ToString("D");
        BoundProtectedJsonCodec codec = CreateCodec(temporary);
        var protector = new MemoryOperationProtector(codec, sessionId);
        PreparedOperation prepared = protector.Prepare(CreatePrivateRoute("value")).Prepared;
        JsonElement privateResult = Parse($"{{\"message\":\"{Canary}\",\"count\":1}}");
        JsonElement sealedResult = codec.SealResult(
            prepared.OperationName,
            prepared.MissionId,
            prepared.InvocationId,
            sessionId,
            privateResult);
        OperationResponse response = Response(prepared, sealedResult);

        using OpenedBoundProtectedJson opened = protector.OpenResult(response, prepared);
        OperationResponse mismatched = response with
        {
            InvocationId = Guid.NewGuid().ToString("D"),
        };
        OperationResponse unverified = response with
        {
            Status = OperationStatuses.Failed,
            Verified = false,
            ErrorCode = "operation_failed",
        };
        JsonElement wrongSessionResult = codec.SealResult(
            prepared.OperationName,
            prepared.MissionId,
            prepared.InvocationId,
            Guid.NewGuid().ToString("D"),
            privateResult);

        Assert.Multiple(() =>
        {
            Assert.That(opened.Payload.GetProperty("message").GetString(), Is.EqualTo(Canary));
            Assert.That(response.Result?.GetRawText(), Does.Not.Contain(Canary));
            Assert.That(
                () => protector.OpenResult(mismatched, prepared),
                Throws.TypeOf<InvalidDataException>());
            Assert.That(
                () => protector.OpenResult(unverified, prepared),
                Throws.TypeOf<InvalidDataException>());
            Assert.That(
                () => protector.OpenResult(Response(prepared, wrongSessionResult), prepared),
                Throws.TypeOf<InvalidDataException>());
        });
    }

    [Test]
    public void AppAcceptsACompletedExportReplayAfterTheCoreMarksItVerified()
    {
        using TemporaryDirectory temporary = new();
        string sessionId = Guid.NewGuid().ToString("D");
        BoundProtectedJsonCodec codec = CreateCodec(temporary);
        var protector = new MemoryOperationProtector(codec, sessionId);
        PreparedOperation prepared = protector.Prepare(
            new MemoryRoutedOperation(
                "memory.export",
                new JsonObject
                {
                    ["version"] = 1,
                    ["destination"] = "documents",
                    ["includeSecrets"] = false,
                })).Prepared;
        JsonElement sealedResult = codec.SealResult(
            prepared.OperationName,
            prepared.MissionId,
            prepared.InvocationId,
            sessionId,
            Parse("{\"version\":1}"));
        OperationResponse replay = Response(prepared, sealedResult) with { Replayed = true };

        using OpenedBoundProtectedJson opened = protector.OpenResult(replay, prepared);

        Assert.That(opened.Payload.GetProperty("version").GetInt32(), Is.EqualTo(1));
    }

    [Test]
    public void SessionChangeBlocksOpeningAndClassifiesDurableRecovery()
    {
        using TemporaryDirectory temporary = new();
        BoundProtectedJsonCodec codec = CreateCodec(temporary);
        var previous = new MemoryOperationProtector(codec, Guid.NewGuid().ToString("D"));
        var current = new MemoryOperationProtector(codec, Guid.NewGuid().ToString("D"));
        MemoryRoutedOperation sessionRoute = CreatePrivateRoute(
            "session value",
            retention: "session");
        PreparedOperation persistent = previous.Prepare(CreatePrivateRoute("persistent value")).Prepared;
        PreparedOperation session = previous.Prepare(sessionRoute).Prepared;
        PreparedOperation recall = previous.Prepare(
            new MemoryRoutedOperation(
                "memory.recall",
                new JsonObject
                {
                    ["version"] = 1,
                    ["scope"] = "exact",
                    ["selector"] = "name",
                })).Prepared;

        MemoryOperationInspection persistentInspection = current.InspectForRecovery(persistent);
        MemoryOperationInspection sessionInspection = current.InspectForRecovery(session);
        MemoryOperationInspection recallInspection = current.InspectForRecovery(recall);

        Assert.Multiple(() =>
        {
            Assert.That(persistentInspection.OriginatesInCurrentSession, Is.False);
            Assert.That(persistentInspection.CancelAfterSessionChange, Is.False);
            Assert.That(sessionInspection.CancelAfterSessionChange, Is.True);
            Assert.That(recallInspection.CancelAfterSessionChange, Is.True);
            Assert.That(
                () => current.OpenPrivateArguments(persistent),
                Throws.TypeOf<StaleMemorySessionException>());
        });
    }

    [Test]
    public void PlaintextMemoryRouteCannotEnterTheDurableOutbox()
    {
        using TemporaryDirectory temporary = new();
        var registry = new RetryableOperationRegistry(
            Path.Combine(temporary.Path, "shell", "retry-outbox.v1.json"));
        var route = new RoutedOperation("memory.save", new JsonObject
        {
            ["value"] = Canary,
        });
        PreparedOperation normal = registry.GetOrAdd(
            new RoutedOperation("note.list", new JsonObject { ["scope"] = "active" }));

        Assert.Multiple(() =>
        {
            Assert.That(
                () => PreparedOperation.Create("memory.save", route.Arguments),
                Throws.TypeOf<InvalidOperationException>());
            Assert.That(
                () => registry.GetOrAdd(route),
                Throws.TypeOf<InvalidOperationException>());
            Assert.That(
                () => registry.Replace(normal, route),
                Throws.TypeOf<InvalidOperationException>());
            Assert.That(registry.SnapshotPendingOperations(), Is.EqualTo(new[] { normal }));
            Assert.That(File.ReadAllText(
                Path.Combine(temporary.Path, "shell", "retry-outbox.v1.json"),
                Encoding.UTF8), Does.Not.Contain(Canary));
        });
    }

    [Test]
    public void PlaintextMemoryEntryLoadedFromDiskFailsAuthentication()
    {
        using TemporaryDirectory temporary = new();
        string outbox = Path.Combine(temporary.Path, "shell", "retry-outbox.v1.json");
        var store = new DurableRetryStore(outbox);
        PreparedOperation forged = PreparedOperation.Restore(
            "memory.save",
            Parse($"{{\"version\":1,\"value\":\"{Canary}\"}}"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"));
        store.Save(new[] { forged });
        MemoryOperationProtector protector = CreateProtector(
            temporary,
            Guid.NewGuid().ToString("D"));

        Assert.That(
            () => new RetryableOperationRegistry(store, protector),
            Throws.TypeOf<InvalidDataException>());
    }

    [Test]
    public void ProtectedWrapperIsBoundToTheProtectorThatAuthenticatedIt()
    {
        using TemporaryDirectory temporary = new();
        var first = new MemoryOperationProtector(
            CreateCodec(temporary),
            Guid.NewGuid().ToString("D"));
        var second = new MemoryOperationProtector(
            CreateCodec(temporary),
            first.SessionId);
        ProtectedMemoryOperation operation = first.Prepare(CreatePrivateRoute("value"));
        var registry = new RetryableOperationRegistry(
            Path.Combine(temporary.Path, "shell", "retry-outbox.v1.json"),
            second);

        Assert.That(
            () => registry.GetOrAdd(operation),
            Throws.TypeOf<InvalidOperationException>());
    }

    [Test]
    public void ConfirmationChallengeIsExactBoundFutureAndNeverPersisted()
    {
        using TemporaryDirectory temporary = new();
        string outbox = Path.Combine(temporary.Path, "shell", "retry-outbox.v1.json");
        MemoryOperationProtector protector = CreateProtector(
            temporary,
            Guid.NewGuid().ToString("D"));
        PreparedOperation prepared = new RetryableOperationRegistry(outbox, protector)
            .GetOrAdd(protector.Prepare(CreatePrivateRoute("value")));
        var clock = new ManualTimeProvider(
            new DateTimeOffset(2026, 7, 15, 15, 0, 0, TimeSpan.Zero));
        string token = Base64Url(RandomNumberGenerator.GetBytes(32));
        JsonElement result = Parse(
            $"{{\"version\":1,\"token\":\"{token}\",\"expiresAtUtc\":\"{clock.GetUtcNow().AddMinutes(2):O}\",\"reconciliationRequired\":false}}");
        OperationResponse response = PendingResponse(prepared, result);

        bool parsed = PendingMemoryConfirmation.TryCreate(
            response,
            prepared,
            clock,
            out PendingMemoryConfirmation? confirmation);

        Assert.Multiple(() =>
        {
            Assert.That(parsed, Is.True);
            Assert.That(confirmation?.Prepared, Is.SameAs(prepared));
            Assert.That(confirmation?.Token, Is.EqualTo(token));
            Assert.That(confirmation?.ReconciliationRequired, Is.False);
            Assert.That(confirmation?.ToString(), Does.Not.Contain(token));
            Assert.That(File.ReadAllText(outbox, Encoding.UTF8), Does.Not.Contain(token));
            Assert.That(
                PendingMemoryConfirmation.TryCreate(
                    response with { MissionId = Guid.NewGuid().ToString("D") },
                    prepared,
                    clock,
                    out _),
                Is.False);
            Assert.That(
                PendingMemoryConfirmation.TryCreate(
                    PendingResponse(
                        prepared,
                        Parse($"{{\"version\":1,\"token\":\"{token}\",\"expiresAtUtc\":\"{clock.GetUtcNow():O}\",\"reconciliationRequired\":false}}")),
                    prepared,
                    clock,
                    out _),
                Is.False);
            Assert.That(
                PendingMemoryConfirmation.TryCreate(
                    PendingResponse(
                        prepared,
                        Parse($"{{\"version\":1,\"token\":\"{token}\",\"expiresAtUtc\":\"{clock.GetUtcNow().AddMinutes(2):O}\",\"reconciliationRequired\":false,\"extra\":true}}")),
                    prepared,
                    clock,
                    out _),
                Is.False);
            Assert.That(
                PendingMemoryConfirmation.TryCreate(
                    PendingResponse(
                        prepared,
                        Parse($"{{\"version\":1,\"token\":\"{token}\",\"expiresAtUtc\":\"{clock.GetUtcNow().AddMinutes(2):O}\"}}")),
                    prepared,
                    clock,
                    out _),
                Is.False);
            Assert.That(
                PendingMemoryConfirmation.TryCreate(
                    PendingResponse(
                        prepared,
                        Parse($"{{\"version\":1,\"token\":\"{token}\",\"expiresAtUtc\":\"{clock.GetUtcNow().AddMinutes(2):O}\",\"reconciliationRequired\":\"false\"}}")),
                    prepared,
                    clock,
                    out _),
                Is.False);
            PreparedOperation nonMemory = PreparedOperation.Create(
                "note.list",
                new JsonObject { ["scope"] = "active" });
            Assert.That(
                PendingMemoryConfirmation.TryCreate(
                    PendingResponse(nonMemory, result),
                    nonMemory,
                    clock,
                    out _),
                Is.False);
        });
    }

    [Test]
    public async Task KernelSensitiveChallengeRoundTripsThroughTheAppParser()
    {
        using TemporaryDirectory temporary = new();
        BoundProtectedJsonCodec codec = CreateCodec(temporary);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(
            new OperationRegistry([new ConfirmationOnlyMemoryHandler()]),
            journal,
            new MemoryEnvelopeAuthenticator(codec));
        var protector = new MemoryOperationProtector(
            codec,
            Guid.NewGuid().ToString("D"));
        PreparedOperation prepared = protector
            .Prepare(CreatePrivateRoute("value"))
            .Prepared;

        OperationResponse response = await engine.ExecuteAsync(
            prepared.CreateRequest(),
            CancellationToken.None);

        Assert.That(
            PendingMemoryConfirmation.TryCreate(
                response,
                prepared,
                TimeProvider.System,
                out PendingMemoryConfirmation? confirmation),
            Is.True);
        Assert.That(confirmation?.Prepared, Is.SameAs(prepared));
        Assert.That(confirmation?.ReconciliationRequired, Is.False);
    }

    [TestCase("si", "Confirm")]
    [TestCase("s\u00ed", "Confirm")]
    [TestCase("confirmo", "Confirm")]
    [TestCase("yes", "Confirm")]
    [TestCase("go ahead", "Confirm")]
    [TestCase("no", "Cancel")]
    [TestCase("cancelar", "Cancel")]
    [TestCase("never mind", "Cancel")]
    [TestCase("yes and export it", "Invalid")]
    [TestCase("maybe", "Invalid")]
    public void ConfirmationReplyIsStandaloneAndFinite(string text, string expected)
    {
        Assert.That(ConfirmationReplyParser.Parse(text).ToString(), Is.EqualTo(expected));
    }

    private static BoundProtectedJsonCodec CreateCodec(TemporaryDirectory temporary) =>
        new(
            new WindowsProtectedPayload(
                Path.Combine(temporary.Path, "security", "private-payload.v1.key")));

    private static MemoryOperationProtector CreateProtector(
        TemporaryDirectory temporary,
        string sessionId) =>
        new(CreateCodec(temporary), sessionId);

    private static MemoryRoutedOperation CreatePrivateRoute(
        string value,
        string retention = "persistent")
    {
        var arguments = new JsonObject
        {
            ["version"] = 1,
            ["selector"] = "name",
            ["value"] = value,
            ["kind"] = "fact",
            ["retention"] = retention,
            ["sensitivity"] = "personal",
            ["tags"] = new JsonArray(),
        };
        if (string.Equals(retention, "session", StringComparison.Ordinal))
        {
            arguments["expiryPolicy"] = "session_end";
        }

        return new MemoryRoutedOperation("memory.save", arguments);
    }

    private static OperationResponse Response(
        PreparedOperation prepared,
        JsonElement result) =>
        new(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            prepared.MissionId,
            prepared.InvocationId,
            OperationStatuses.Completed,
            "Resultado privado disponible.",
            true,
            false,
            result,
            null);

    private static OperationResponse PendingResponse(
        PreparedOperation prepared,
        JsonElement result) =>
        new(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            prepared.MissionId,
            prepared.InvocationId,
            OperationStatuses.Pending,
            "Necesito confirmacion.",
            false,
            false,
            result,
            "confirmation_required");

    private static JsonElement Parse(string json) =>
        JsonDocument.Parse(json).RootElement.Clone();

    private static string Base64Url(ReadOnlySpan<byte> value) =>
        Convert.ToBase64String(value)
            .TrimEnd('=')
            .Replace('+', '-')
            .Replace('/', '_');

    private sealed class ManualTimeProvider(DateTimeOffset now) : TimeProvider
    {
        public override DateTimeOffset GetUtcNow() => now;
    }

    private sealed class ConfirmationOnlyMemoryHandler : IOperationHandler
    {
        public OperationDefinition Definition { get; } =
            new("memory.save", OperationRisk.Sensitive, "Test memory confirmation.");

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken) =>
            throw new InvalidOperationException("The confirmation gate must run before the handler.");
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        internal TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(
                System.IO.Path.GetTempPath(),
                $"baxy-memory-protection-{Guid.NewGuid():N}");
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

internal static class MemoryProtectionTestEnumerableExtensions
{
    internal static bool ContainsSequence(
        this IEnumerable<byte> source,
        ReadOnlySpan<byte> value)
    {
        byte[] bytes = source.ToArray();
        return bytes.AsSpan().IndexOf(value) >= 0;
    }
}
