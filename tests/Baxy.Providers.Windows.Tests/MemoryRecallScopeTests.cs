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

    private sealed class Temporary : IDisposable
    {
        private readonly string _path = Path.Combine(Path.GetTempPath(), "baxy-memory-recall-" + Guid.NewGuid().ToString("N"));

        internal async Task<OperationOutcome> RecallAsync(JsonObject payload)
        {
            Directory.CreateDirectory(_path);
            var protector = new WindowsProtectedPayload(Path.Combine(_path, "payload.key"));
            var store = new LocalMemoryStore(Path.Combine(_path, "memory-store"), protector);
            var codec = new BoundProtectedJsonCodec(protector);
            IOperationHandler recall = MemoryHandlers.Create(store, codec)
                .Single(static handler => handler.Definition.Name == "memory.recall");
            string mission = Guid.NewGuid().ToString("D");
            string invocation = Guid.NewGuid().ToString("D");
            JsonElement sealedArguments = codec.SealArguments("memory.recall", mission, invocation,
                Guid.NewGuid().ToString("D"), payload);
            return await recall.ExecuteAsync(new OperationInvocation("r1", mission, invocation, sealedArguments),
                CancellationToken.None);
        }

        public void Dispose()
        {
            if (Directory.Exists(_path)) Directory.Delete(_path, recursive: true);
        }
    }
}
