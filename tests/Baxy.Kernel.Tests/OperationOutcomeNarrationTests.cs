using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

[TestFixture]
public sealed class OperationOutcomeNarrationTests
{
    [Test]
    public async Task MissionEngineMessageIsTheVisibleFactsOfTheHandlerOutcome()
    {
        JsonElement result = JsonDocument.Parse("{\"title\":\"Compras\"}").RootElement.Clone();
        var handler = new ResultHandler(result);
        using var journal = new InMemoryInvocationJournal();
        using var engine = new MissionEngine(new OperationRegistry([handler]), journal);
        var request = new OperationRequest(
            ProtocolTypes.OperationRequest,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            handler.Definition.Name,
            JsonDocument.Parse("{}").RootElement.Clone());

        OperationResponse response = await engine.ExecuteAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(response.Message, Is.EqualTo(OperationVisibleFacts.FromOutcome(handler.Definition.Name, handler.Outcome)));
            Assert.That(response.Result?.GetProperty("title").GetString(), Is.EqualTo("Compras"));
        });
    }

    [Test]
    public void ObservationCarriesTheIdsTypedArgumentsAskForAndHoldsBackSecretsAndBookkeeping()
    {
        JsonElement result = JsonSerializer.SerializeToElement(new
        {
            id = "a1",
            noteId = "8f0c7c56-6a3e-4c55-9a4b-2f1f4c5a9d10",
            deviceId = "bluetooth.4f2a",
            sha256 = "ab12",
            hash = "cd34",
            recordId = "r1",
            token = "secret-token",
            fingerprint = "fp",
            invocationId = "inv",
            requestId = "req",
            missionId = "mis",
            hwnd = 42,
            handle = 43,
            processId = 44,
        });

        using JsonDocument message = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("note.read", OperationOutcome.Success(result)));
        JsonElement observed = message.RootElement.GetProperty("observed");
        string[] keys = [.. observed.EnumerateObject().Select(static property => property.Name)];

        Assert.That(keys, Is.EquivalentTo(new[] { "id", "noteId", "deviceId", "sha256", "hash", "recordId" }));
    }

    // Auditoría final V2: a list cut to what the observation shows says how many it shows, and the observation says
    // something was left out, where the model reads it (window.resolve with limit 50 showed 20 under count 50).
    [Test]
    public void AListCutToWhatIsShownSaysHowManyItShowsAndThatMoreWasLeftOut()
    {
        JsonElement result = JsonSerializer.SerializeToElement(new
        {
            windows = Enumerable.Range(0, 50).Select(static index => new { title = "w" + index }).ToArray(),
            count = 50,
            nextOffset = 50,
        });

        using JsonDocument message = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("window.resolve", OperationOutcome.Success(result)));
        JsonElement observed = message.RootElement.GetProperty("observed");

        Assert.Multiple(() =>
        {
            Assert.That(observed.GetProperty("windows").GetArrayLength(), Is.EqualTo(20));
            Assert.That(observed.GetProperty("windowsShown").GetInt32(), Is.EqualTo(20));
            Assert.That(observed.TryGetProperty("windowsCount", out _), Is.False, "the provider's count stays the total");
            Assert.That(observed.GetProperty("count").GetInt32(), Is.EqualTo(50));
            Assert.That(observed.GetProperty("truncated").GetBoolean(), Is.True);
        });
    }

    [Test]
    public void AListWithoutACountKeepsItsLengthAndADeepValueLeftOutIsSaid()
    {
        JsonElement listed = JsonSerializer.SerializeToElement(new
        {
            tasks = Enumerable.Range(0, 30).Select(static index => new { title = "t" + index }).ToArray(),
        });
        JsonElement deep = JsonSerializer.SerializeToElement(new { a = new { b = new { c = new { d = new { e = 1 } } } } });
        JsonElement whole = JsonSerializer.SerializeToElement(new { tasks = new[] { new { title = "t" } } });

        using JsonDocument cut = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("task.list", OperationOutcome.Success(listed)));
        using JsonDocument cutDeep = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("task.list", OperationOutcome.Success(deep)));
        using JsonDocument kept = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("task.list", OperationOutcome.Success(whole)));

        Assert.Multiple(() =>
        {
            Assert.That(cut.RootElement.GetProperty("observed").GetProperty("tasksShown").GetInt32(), Is.EqualTo(20));
            Assert.That(cut.RootElement.GetProperty("observed").GetProperty("tasksCount").GetInt32(), Is.EqualTo(30));
            Assert.That(cutDeep.RootElement.GetProperty("observed").GetProperty("truncated").GetBoolean(), Is.True);
            Assert.That(kept.RootElement.GetProperty("observed").TryGetProperty("truncated", out _), Is.False);
            Assert.That(kept.RootElement.GetProperty("observed").TryGetProperty("tasksShown", out _), Is.False);
        });
    }

    [Test]
    public void OperationOutcomeDoesNotExposeNaturalLanguageMessage()
    {
        Assert.That(typeof(OperationOutcome).GetProperty("Message"), Is.Null);
        Assert.That(
            typeof(OperationOutcome).GetConstructors()
                .SelectMany(static constructor => constructor.GetParameters())
                .Select(static parameter => parameter.Name),
            Does.Not.Contain("message"));
    }

    private sealed class ResultHandler(JsonElement result) : IOperationHandler
    {
        public OperationDefinition Definition { get; } =
            new("note.create", OperationRisk.Reversible, "Test operation.");

        public OperationOutcome Outcome { get; } = OperationOutcome.Success(result);

        public ValueTask<OperationOutcome> ExecuteAsync(
            OperationInvocation invocation,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(Outcome);
        }
    }
}
