using System.Security.Cryptography;
using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class MvpExternalCatalogMatrixTests
{
    private const int ExpectedExternalHandlers = 85;
    private static readonly JsonSerializerOptions EvidenceJsonOptions = new()
    {
        WriteIndented = true,
    };

    [Test]
    public async Task EveryExternalHandlerCrossesItsProviderAndVerifierBoundary()
    {
        var verifiedProvider = new RecordingProvider(verified: true);
        IOperationHandler[] handlers = CreateHandlers(verifiedProvider);
        Dictionary<string, OperationRisk> risks = handlers.ToDictionary(
            handler => handler.Definition.Name,
            handler => handler.Definition.Risk,
            StringComparer.Ordinal);
        verifiedProvider.SetRisks(risks);

        var rejectingProvider = new RecordingProvider(verified: false);
        IOperationHandler[] rejectingHandlers = CreateHandlers(rejectingProvider);
        rejectingProvider.SetRisks(risks);
        Dictionary<string, IOperationHandler> rejectingByName = rejectingHandlers.ToDictionary(
            handler => handler.Definition.Name,
            StringComparer.Ordinal);

        var rows = new List<object>(handlers.Length);
        foreach (IOperationHandler handler in handlers.OrderBy(
                     candidate => candidate.Definition.Name,
                     StringComparer.Ordinal))
        {
            string operation = handler.Definition.Name;
            OperationInvocation invocation = Invocation();
            OperationOutcome accepted = await handler.ExecuteAsync(
                invocation,
                CancellationToken.None);
            OperationOutcome rejected = await rejectingByName[operation].ExecuteAsync(
                invocation,
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(accepted.Succeeded, Is.True, operation);
                Assert.That(accepted.Verified, Is.True, operation);
                Assert.That(accepted.EffectMayHaveOccurred, Is.False, operation);
                Assert.That(rejected.Succeeded, Is.False, operation);
                Assert.That(rejected.Verified, Is.False, operation);
                Assert.That(rejected.ErrorCode, Is.EqualTo("simulated_unverified"), operation);
                Assert.That(rejected.EffectMayHaveOccurred, Is.False, operation);
            });

            rows.Add(new
            {
                operation,
                risk = RiskName(handler.Definition.Risk),
                provider = nameof(IExternalCapabilityProvider),
                exactOperationForwarded = verifiedProvider.Calls.Contains(operation),
                verifiedReceiptAccepted = accepted.Succeeded && accepted.Verified,
                unverifiedReceiptRejected = !rejected.Succeeded && !rejected.Verified,
                actualEffectsExecuted = 0,
            });
        }

        string[] names = handlers.Select(handler => handler.Definition.Name).ToArray();
        Assert.Multiple(() =>
        {
            Assert.That(handlers, Has.Length.EqualTo(ExpectedExternalHandlers));
            Assert.That(names, Is.Unique);
            Assert.That(verifiedProvider.Calls, Has.Count.EqualTo(ExpectedExternalHandlers));
            Assert.That(rejectingProvider.Calls, Has.Count.EqualTo(ExpectedExternalHandlers));
            Assert.That(names, Has.All.Matches<string>(name => ProductCatalog.TryGet(name, out _)));
        });

        WriteOptionalEvidence(rows, handlers);
    }

    private static IOperationHandler[] CreateHandlers(IExternalCapabilityProvider provider) =>
    [
        new ExternalCapabilityHandler("audio.microphone.mute", provider),
        new ExternalCapabilityHandler("audio.volume.adjust", provider),
        .. ExternalCapabilityHandlers.Create(provider),
    ];

    private static OperationInvocation Invocation()
    {
        using JsonDocument document = JsonDocument.Parse("{}");
        return new OperationInvocation(
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            document.RootElement.Clone());
    }

    private static string RiskName(OperationRisk risk) => risk switch
    {
        OperationRisk.ReadOnly => "read_only",
        OperationRisk.Reversible => "low_reversible",
        OperationRisk.Sensitive => "privacy_sensitive",
        OperationRisk.External => "external_communication",
        OperationRisk.Irreversible => "irreversible",
        OperationRisk.Forbidden => "forbidden",
        _ => throw new ArgumentOutOfRangeException(nameof(risk), risk, null),
    };

    private static void WriteOptionalEvidence(
        List<object> rows,
        IReadOnlyCollection<IOperationHandler> handlers)
    {
        string? configured = Environment.GetEnvironmentVariable(
            "BAXY_MVP_EXTERNAL_MATRIX_OUTPUT");
        if (string.IsNullOrWhiteSpace(configured))
        {
            return;
        }

        string output = Path.GetFullPath(configured);
        if (File.Exists(output))
        {
            throw new InvalidOperationException($"Refusing to overwrite evidence: {output}");
        }

        Directory.CreateDirectory(Path.GetDirectoryName(output)!);
        string coreAssembly = typeof(ExternalCapabilityHandler).Assembly.Location;
        string testAssembly = typeof(MvpExternalCatalogMatrixTests).Assembly.Location;
        var report = new
        {
            schema = "baxy.mvp-external-provider-contract-matrix.v1",
            measuredAtUtc = DateTimeOffset.UtcNow.ToString("O"),
            scope = "all_external_handlers_inert_provider_and_verifier_simulation",
            actualEffectsExecuted = 0,
            simulatedEffectReceipts = handlers.Count(
                handler => handler.Definition.Risk != OperationRisk.ReadOnly),
            coreAssembly,
            coreAssemblySha256 = FileSha256(coreAssembly),
            testAssembly,
            testAssemblySha256 = FileSha256(testAssembly),
            metrics = new
            {
                operations = rows.Count,
                exactProviderForwards = rows.Count,
                verifiedReceiptsAccepted = rows.Count,
                unverifiedReceiptsRejected = rows.Count,
                failed = 0,
            },
            rows,
            gatePassed = rows.Count == ExpectedExternalHandlers,
        };
        File.WriteAllText(
            output,
            JsonSerializer.Serialize(report, EvidenceJsonOptions) + Environment.NewLine);
    }

    private static string FileSha256(string path) =>
        Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();

    private sealed class RecordingProvider(bool verified) : IExternalCapabilityProvider
    {
        private IReadOnlyDictionary<string, OperationRisk> _risks =
            new Dictionary<string, OperationRisk>();

        public List<string> Calls { get; } = [];

        public void SetRisks(IReadOnlyDictionary<string, OperationRisk> risks) =>
            _risks = risks;

        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation,
            JsonElement arguments,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            Assert.That(arguments.ValueKind, Is.EqualTo(JsonValueKind.Object));
            Calls.Add(operation);
            if (!verified)
            {
                return ValueTask.FromResult(new ExternalCapabilityReceipt(
                    operation,
                    EffectObserved: false,
                    Verified: false,
                    Result: null,
                    ErrorCode: "simulated_unverified"));
            }

            using JsonDocument evidence = JsonDocument.Parse(
                $$"""{"operation":"{{operation}}","source":"inert_test_provider"}""");
            return ValueTask.FromResult(new ExternalCapabilityReceipt(
                operation,
                EffectObserved: _risks[operation] != OperationRisk.ReadOnly,
                Verified: true,
                Result: evidence.RootElement.Clone(),
                ErrorCode: null));
        }
    }
}
