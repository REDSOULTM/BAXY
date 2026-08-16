using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Memory;
using Baxy.Security.Windows;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class MvpMemoryHandlerMatrixTests
{
    private const int ExpectedOperations = 11;
    private const string SecretCanary = "BAXY-MVP-SECRET-CANARY-9217";
    private static readonly DateTimeOffset Now =
        new(2026, 8, 11, 18, 0, 0, TimeSpan.Zero);
    private static readonly JsonSerializerOptions EvidenceJsonOptions = new()
    {
        WriteIndented = true,
    };

    [Test]
    public async Task EveryMemoryHandlerCrossesDpapiBoundaryAndRealIsolatedStore()
    {
        using var temporary = new TemporaryDirectory();
        string keyPath = Path.Combine(
            temporary.Path,
            "security",
            "private-payload.v1.key");
        var privatePayload = new WindowsProtectedPayload(keyPath);
        var codec = new BoundProtectedJsonCodec(privatePayload);
        var store = new LocalMemoryStore(
            Path.Combine(temporary.Path, "memory-store"),
            privatePayload,
            new FixedTimeProvider(Now));
        var exportWriter = new LocalMemoryExportWriter(
            Path.Combine(temporary.Path, "Documents"));
        Dictionary<string, IOperationHandler> handlers = MemoryHandlers.Create(
                store,
                codec,
                new FixedTimeProvider(Now),
                exportWriter)
            .ToDictionary(handler => handler.Definition.Name, StringComparer.Ordinal);
        var rows = new List<MatrixRow>(ExpectedOperations);
        string sessionId = Guid.NewGuid().ToString("D");

        await RunAsync(
            handlers,
            codec,
            MemoryOperationIds.Enable,
            new JsonObject { ["version"] = 1, ["enabled"] = true },
            sessionId,
            rows);
        await RunAsync(
            handlers,
            codec,
            MemoryOperationIds.Save,
            SavePayload("favorite_color", "azul", "normal"),
            sessionId,
            rows);
        await RunAsync(
            handlers,
            codec,
            MemoryOperationIds.SensitiveSave,
            SavePayload("private_note", SecretCanary, "secret"),
            sessionId,
            rows);
        await RunAsync(
            handlers,
            codec,
            MemoryOperationIds.Status,
            new JsonObject { ["version"] = 1 },
            sessionId,
            rows);
        await RunAsync(
            handlers,
            codec,
            MemoryOperationIds.Recall,
            new JsonObject
            {
                ["version"] = 1,
                ["scope"] = "exact",
                ["selector"] = "favorite_color",
            },
            sessionId,
            rows);
        await RunAsync(
            handlers,
            codec,
            MemoryOperationIds.List,
            new JsonObject
            {
                ["version"] = 1,
                ["limit"] = 20,
                ["offset"] = 0,
            },
            sessionId,
            rows);
        await RunAsync(
            handlers,
            codec,
            MemoryOperationIds.Correct,
            new JsonObject
            {
                ["version"] = 1,
                ["selector"] = "favorite_color",
                ["value"] = "verde",
                ["expectedValue"] = "azul",
                ["kind"] = "fact",
                ["retention"] = "persistent",
            },
            sessionId,
            rows);
        OpenedResult exported = await RunAsync(
            handlers,
            codec,
            MemoryOperationIds.Export,
            new JsonObject
            {
                ["version"] = 1,
                ["destination"] = "documents",
                ["includeSecrets"] = false,
            },
            sessionId,
            rows);
        AssertExportIsRedacted(exported.Payload);
        await RunAsync(
            handlers,
            codec,
            MemoryOperationIds.Forget,
            new JsonObject
            {
                ["version"] = 1,
                ["scope"] = "exact",
                ["selector"] = "private_note",
                ["confirmationRequired"] = true,
            },
            sessionId,
            rows);
        await RunAsync(
            handlers,
            codec,
            MemoryOperationIds.SessionClear,
            new JsonObject
            {
                ["version"] = 1,
                ["scope"] = "session",
                ["selector"] = null,
                ["confirmationRequired"] = false,
                ["mustNotDeletePersistent"] = true,
            },
            sessionId,
            rows);
        await RunAsync(
            handlers,
            codec,
            MemoryOperationIds.Disable,
            new JsonObject { ["version"] = 1, ["enabled"] = false },
            sessionId,
            rows);

        bool canaryAtRest = Directory.EnumerateFiles(
                temporary.Path,
                "*",
                SearchOption.AllDirectories)
            .Any(path => ContainsUtf8(path, SecretCanary));
        Assert.Multiple(() =>
        {
            Assert.That(handlers, Has.Count.EqualTo(ExpectedOperations));
            Assert.That(rows, Has.Count.EqualTo(ExpectedOperations));
            Assert.That(rows.Select(row => row.Operation), Is.Unique);
            Assert.That(rows, Has.All.Matches<MatrixRow>(row => row.Verified));
            Assert.That(rows, Has.All.Matches<MatrixRow>(
                row => row.PrivateResultOpened));
            Assert.That(rows, Has.All.Matches<MatrixRow>(
                row => !row.SecretInPublicOutcome));
            Assert.That(canaryAtRest, Is.False);
        });
        WriteOptionalEvidence(rows, privatePayload.ProtectionMode, canaryAtRest);
    }

    private static JsonObject SavePayload(
        string selector,
        string value,
        string sensitivity) => new()
        {
            ["version"] = 1,
            ["selector"] = selector,
            ["value"] = value,
            ["kind"] = "fact",
            ["retention"] = "persistent",
            ["sensitivity"] = sensitivity,
            ["tags"] = new JsonArray(),
        };

    private static async Task<OpenedResult> RunAsync(
        Dictionary<string, IOperationHandler> handlers,
        BoundProtectedJsonCodec codec,
        string operation,
        JsonObject payload,
        string sessionId,
        List<MatrixRow> rows)
    {
        string missionId = Guid.NewGuid().ToString("D");
        string invocationId = Guid.NewGuid().ToString("D");
        JsonElement arguments = codec.SealArguments(
            operation,
            missionId,
            invocationId,
            sessionId,
            payload);
        var invocation = new OperationInvocation(
            Guid.NewGuid().ToString("D"),
            missionId,
            invocationId,
            arguments);
        OperationOutcome outcome = await handlers[operation].ExecuteAsync(
            invocation,
            CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, operation);
            Assert.That(outcome.Verified, Is.True, operation);
            Assert.That(outcome.Result, Is.Not.Null, operation);
            Assert.That(outcome.EffectMayHaveOccurred, Is.False, operation);
            Assert.That(outcome.Result!.Value.GetRawText(),
                Does.Not.Contain(SecretCanary),
                operation);
        });
        using OpenedBoundProtectedJson opened = codec.OpenResult(
            outcome.Result!.Value,
            operation,
            missionId,
            invocationId);
        JsonElement privateResult = opened.Payload.Clone();
        rows.Add(new MatrixRow(
            operation,
            "real_isolated_encrypted_store",
            "bound_dpapi_envelope_plus_store_postread",
            outcome.Verified,
            PrivateResultOpened: true,
            SecretInPublicOutcome: false,
            ActualUserEffectsExecuted: 0));
        return new OpenedResult(privateResult);
    }

    private static void AssertExportIsRedacted(JsonElement result)
    {
        string path = result.GetProperty("path").GetString()
            ?? throw new InvalidDataException("Missing memory export path.");
        byte[] bytes = File.ReadAllBytes(path);
        string text = Encoding.UTF8.GetString(bytes);
        Assert.Multiple(() =>
        {
            Assert.That(path, Does.Match("memory-export-[0-9a-f]{64}\\.json$"));
            Assert.That(text, Does.Not.Contain(SecretCanary));
            Assert.That(text, Does.Contain(LocalMemoryExportWriter.RedactedValue));
            Assert.That(
                Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant(),
                Is.EqualTo(result.GetProperty("sha256").GetString()));
        });
    }

    private static bool ContainsUtf8(string path, string value)
    {
        byte[] needle = Encoding.UTF8.GetBytes(value);
        byte[] contents = File.ReadAllBytes(path);
        return contents.AsSpan().IndexOf(needle) >= 0;
    }

    private static void WriteOptionalEvidence(
        List<MatrixRow> rows,
        string protectionMode,
        bool canaryAtRest)
    {
        string? configured = Environment.GetEnvironmentVariable(
            "BAXY_MVP_MEMORY_MATRIX_OUTPUT");
        if (string.IsNullOrWhiteSpace(configured)) return;
        string output = Path.GetFullPath(configured);
        if (File.Exists(output))
            throw new InvalidOperationException($"Refusing to overwrite evidence: {output}");
        Directory.CreateDirectory(Path.GetDirectoryName(output)!);
        string coreAssembly = typeof(MemoryHandlers).Assembly.Location;
        string providerAssembly = typeof(LocalMemoryStore).Assembly.Location;
        string securityAssembly = typeof(WindowsProtectedPayload).Assembly.Location;
        var report = new
        {
            schema = "baxy.mvp-memory-handler-matrix.v1",
            measuredAtUtc = DateTimeOffset.UtcNow.ToString("O"),
            scope = "all_memory_handlers_bound_to_real_isolated_encrypted_store",
            protectionMode,
            actualUserEffectsExecuted = 0,
            isolatedStoreOperations = rows.Count,
            secretCanaryFoundAtRest = canaryAtRest,
            metrics = new
            {
                operations = rows.Count,
                verified = rows.Count(row => row.Verified),
                privateResultsOpened = rows.Count(row => row.PrivateResultOpened),
                publicSecretLeaks = rows.Count(row => row.SecretInPublicOutcome),
                failed = 0,
            },
            coreAssemblySha256 = FileSha256(coreAssembly),
            providerAssemblySha256 = FileSha256(providerAssembly),
            securityAssemblySha256 = FileSha256(securityAssembly),
            rows,
            gatePassed = rows.Count == ExpectedOperations
                && rows.All(row => row.Verified && row.PrivateResultOpened)
                && rows.All(row => !row.SecretInPublicOutcome)
                && rows.Sum(row => row.ActualUserEffectsExecuted) == 0
                && !canaryAtRest,
        };
        File.WriteAllText(
            output,
            JsonSerializer.Serialize(report, EvidenceJsonOptions) + Environment.NewLine);
    }

    private static string FileSha256(string path) =>
        Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();

    private sealed record MatrixRow(
        string Operation,
        string EvidenceKind,
        string Verifier,
        bool Verified,
        bool PrivateResultOpened,
        bool SecretInPublicOutcome,
        int ActualUserEffectsExecuted);

    private sealed record OpenedResult(JsonElement Payload);

    private sealed class FixedTimeProvider(DateTimeOffset utcNow) : TimeProvider
    {
        public override DateTimeOffset GetUtcNow() => utcNow;
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(
                System.IO.Path.GetTempPath(),
                "baxy-mvp-memory-matrix",
                Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(Path);
        }

        public string Path { get; }

        public void Dispose()
        {
            if (Directory.Exists(Path)) Directory.Delete(Path, recursive: true);
        }
    }
}
