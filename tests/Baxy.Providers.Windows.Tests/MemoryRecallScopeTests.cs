using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Memory;
using Baxy.Security.Windows;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// FT/proveedores goal (E4): memory.recall with scope all takes no selector, and may leave it out. The model reads the
/// selector as a plain string (the mind drops «null» from its types), so every recall of everything carried one and read
/// a bare invalid_arguments; now the selector is optional and «all» with one says so by its own code.
/// </summary>
[TestFixture]
public sealed class MemoryRecallScopeTests
{
    [Test]
    public void TheCatalogDoesNotRequireASelector()
    {
        Assert.That(ProductCatalog.GetRequired("memory.recall").ArgumentsSchema.Required,
            Is.EquivalentTo(new[] { "scope", "version" }));
    }

    [Test]
    public async Task ScopeAllWithoutASelectorIsAValidRecall()
    {
        using var temporary = new Temporary();
        OperationOutcome outcome = await temporary.RecallAsync(new JsonObject { ["version"] = 1, ["scope"] = "all" });
        Assert.That(outcome.ErrorCode, Is.Not.EqualTo("invalid_arguments"));
    }

    [Test]
    public async Task ScopeAllWithASelectorSaysWhatAllTakes()
    {
        using var temporary = new Temporary();
        OperationOutcome outcome = await temporary.RecallAsync(
            new JsonObject { ["version"] = 1, ["scope"] = "all", ["selector"] = "color favorito" });
        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("memory_recall_all_takes_no_selector"));
        });
    }

    // Uso real 2026-10-21: «¿cuál es mi comida favorita?» makes the model send scope exact with no selector, every time
    // (reproduced with the real catalog); a bare invalid_arguments made it say nothing was remembered. An exact recall
    // that names nothing reads what is remembered.
    [Test]
    public async Task ScopeExactWithoutASelectorReadsWhatIsRemembered()
    {
        using var temporary = new Temporary();
        OperationOutcome outcome = await temporary.RecallAsync(new JsonObject { ["version"] = 1, ["scope"] = "exact" });
        Assert.That(outcome.ErrorCode, Is.Not.EqualTo("invalid_arguments"));
    }

    // Al máximo 11.2: an exact recall that matched nothing showed what is remembered as if it were the match (the model
    // told the favorite food as the name asked for). The list comes back said as not the exact match.
    [Test]
    public async Task AnExactRecallThatMatchesNothingSaysSo()
    {
        using var temporary = new Temporary();
        temporary.Remember("comida favorita", "pizza");
        JsonObject missed = await temporary.RecallOpenedAsync(
            new JsonObject { ["version"] = 1, ["scope"] = "exact", ["selector"] = "nombre" });
        JsonObject matched = await temporary.RecallOpenedAsync(
            new JsonObject { ["version"] = 1, ["scope"] = "exact", ["selector"] = "comida favorita" });
        Assert.Multiple(() =>
        {
            Assert.That((bool?)missed["exactMatch"], Is.False);
            Assert.That(missed["records"]!.AsArray(), Has.Count.EqualTo(1));
            Assert.That((bool?)matched["exactMatch"], Is.True);
        });
    }

    // Renew al máximo (w8): a corrected record says whether it is sensitive (the App then never says its value back).
    [TestCase(MemorySensitivity.Sensitive, true)]
    [TestCase(MemorySensitivity.Normal, false)]
    public async Task ACorrectSaysWhetherTheRecordIsSensitive(MemorySensitivity sensitivity, bool flagged)
    {
        using var temporary = new Temporary();
        temporary.Remember("mi direccion", "Calle Uno 1", sensitivity);
        JsonObject corrected = await temporary.RunOpenedAsync("memory.correct", new JsonObject
        {
            ["version"] = 1, ["selector"] = "mi direccion", ["value"] = "Calle Dos 2", ["retention"] = "persistent",
        });
        Assert.Multiple(() =>
        {
            Assert.That(corrected.ContainsKey("sensitive"), Is.EqualTo(flagged));
            Assert.That(corrected.ToJsonString(), Does.Not.Contain("Calle"));
        });
    }

    private sealed class Temporary : IDisposable
    {
        private readonly string _path = Path.Combine(Path.GetTempPath(), "baxy-memory-recall-" + Guid.NewGuid().ToString("N"));
        private readonly WindowsProtectedPayload _protector;
        private readonly LocalMemoryStore _store;
        private readonly BoundProtectedJsonCodec _codec;

        internal Temporary()
        {
            Directory.CreateDirectory(_path);
            _protector = new WindowsProtectedPayload(Path.Combine(_path, "payload.key"));
            _store = new LocalMemoryStore(Path.Combine(_path, "memory-store"), _protector);
            _codec = new BoundProtectedJsonCodec(_protector);
        }

        internal void Remember(string selector, string value, MemorySensitivity sensitivity = MemorySensitivity.Normal)
        {
            _store.Configure(new MemoryConfigureRequest("enable-1", Enabled: true));
            _store.Save(new MemorySaveRequest("save-1", selector, selector, value, Sensitivity: sensitivity));
        }

        internal async Task<JsonObject> RunOpenedAsync(string operation, JsonObject payload)
        {
            IOperationHandler handler = MemoryHandlers.Create(_store, _codec)
                .Single(candidate => candidate.Definition.Name == operation);
            string mission = Guid.NewGuid().ToString("D");
            string invocation = Guid.NewGuid().ToString("D");
            JsonElement sealedArguments = _codec.SealArguments(operation, mission, invocation,
                Guid.NewGuid().ToString("D"), payload);
            OperationOutcome outcome = await handler.ExecuteAsync(
                new OperationInvocation("r1", mission, invocation, sealedArguments), CancellationToken.None);
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            using OpenedBoundProtectedJson opened = _codec.OpenResult(outcome.Result!.Value, operation, mission, invocation);
            return JsonNode.Parse(opened.Payload.GetRawText())!.AsObject();
        }

        internal async Task<OperationOutcome> RecallAsync(JsonObject payload) =>
            (await RecallSealedAsync(payload)).Outcome;

        internal async Task<JsonObject> RecallOpenedAsync(JsonObject payload)
        {
            (OperationOutcome outcome, string mission, string invocation) = await RecallSealedAsync(payload);
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            using OpenedBoundProtectedJson opened = _codec.OpenResult(outcome.Result!.Value, "memory.recall", mission,
                invocation);
            return JsonNode.Parse(opened.Payload.GetRawText())!.AsObject();
        }

        private async Task<(OperationOutcome Outcome, string Mission, string Invocation)> RecallSealedAsync(
            JsonObject payload)
        {
            IOperationHandler recall = MemoryHandlers.Create(_store, _codec)
                .Single(static handler => handler.Definition.Name == "memory.recall");
            string mission = Guid.NewGuid().ToString("D");
            string invocation = Guid.NewGuid().ToString("D");
            JsonElement sealedArguments = _codec.SealArguments("memory.recall", mission, invocation,
                Guid.NewGuid().ToString("D"), payload);
            return (await recall.ExecuteAsync(new OperationInvocation("r1", mission, invocation, sealedArguments),
                CancellationToken.None), mission, invocation);
        }

        public void Dispose()
        {
            if (Directory.Exists(_path)) Directory.Delete(_path, recursive: true);
        }
    }
}
