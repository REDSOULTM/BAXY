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

    // Audit 2026-10-15 R2: a page of a text read by offset whose text the message cuts goes on from where the shown
    // text ends, so the model never pages past text it did not see.
    [Test]
    public void APageWhoseTextIsCutGoesOnFromWhereItsShownTextEnds()
    {
        string page = string.Join(' ', Enumerable.Range(0, 3_000).Select(static index => "w" + index));
        JsonElement result = JsonSerializer.SerializeToElement(new
        {
            offset = 1_000,
            lines = 1,
            returnedCharacters = page.Length,
            hasMore = false,
            text = page,
        });

        using JsonDocument message = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("file.read", OperationOutcome.Success(result)));
        JsonElement observed = message.RootElement.GetProperty("observed");
        string shown = observed.GetProperty("text").GetString()!;
        int kept = shown.Length - 1;

        Assert.Multiple(() =>
        {
            Assert.That(shown, Does.EndWith("…"));
            Assert.That(page, Does.StartWith(shown[..kept]));
            Assert.That(observed.GetProperty("returnedCharacters").GetInt32(), Is.EqualTo(kept));
            Assert.That(observed.GetProperty("nextOffset").GetInt32(), Is.EqualTo(1_000 + kept));
            Assert.That(observed.GetProperty("hasMore").GetBoolean(), Is.True);
            Assert.That(observed.TryGetProperty("lines", out _), Is.False, "the page's line count is not the shown text's");
        });
    }

    // Round 1 (2026-10-15): a cut page keeps as much text as the message holds, not the first step's 2,000 characters.
    [Test]
    public void ACutPageKeepsAsMuchTextAsTheMessageHolds()
    {
        // Line breaks and quotes take two characters each in the message's JSON (a real page has dozens per 2,000).
        string page = string.Join(' ', Enumerable.Range(0, 3_000).Select(static index => index % 20 == 0 ? "\"w\"\n" : "w" + index));
        JsonElement result = JsonSerializer.SerializeToElement(new { offset = 0, hasMore = true, nextOffset = page.Length, text = page });

        string message = OperationVisibleFacts.FromOutcome("web.fetch", OperationOutcome.Success(result));
        using JsonDocument parsed = JsonDocument.Parse(message);
        string shown = parsed.RootElement.GetProperty("observed").GetProperty("text").GetString()!;

        Assert.Multiple(() =>
        {
            Assert.That(message.Length, Is.LessThanOrEqualTo(8_192));
            Assert.That(shown.Length, Is.GreaterThan(6_000));
            Assert.That(parsed.RootElement.GetProperty("observed").GetProperty("nextOffset").GetInt32(), Is.EqualTo(shown.Length - 1));
        });
    }

    // Round 3: a page that fits unescaped but not escaped is still cut to what the message holds, not to 2,000.
    [Test]
    public void APageThatFitsOnlyUnescapedIsCutToWhatTheMessageHolds()
    {
        string page = string.Concat(Enumerable.Range(0, 770).Select(static index => index % 4 == 0 ? "\"a\"\n line " : "word word "));
        Assert.That(page.Length, Is.InRange(7_600, 7_800));
        JsonElement result = JsonSerializer.SerializeToElement(new { offset = 0, returnedCharacters = page.Length, hasMore = false, text = page });

        string message = OperationVisibleFacts.FromOutcome("file.read", OperationOutcome.Success(result));
        using JsonDocument parsed = JsonDocument.Parse(message);

        Assert.Multiple(() =>
        {
            Assert.That(message.Length, Is.LessThanOrEqualTo(8_192));
            Assert.That(parsed.RootElement.GetProperty("observed").GetProperty("returnedCharacters").GetInt32(), Is.GreaterThan(2_000));
        });
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
            // Ronda final 11: the next page starts at the first window not shown, never at the provider's 50.
            Assert.That(observed.GetProperty("nextOffset").GetInt32(), Is.EqualTo(20));
            Assert.That(observed.GetProperty("hasMore").GetBoolean(), Is.True);
        });
    }

    // Ronda final 11: the provider's offset, nextOffset and hasMore come after its list (window.resolve, note.list); a
    // list cut in the projection still says the shown page, whichever cut was last.
    [Test]
    public void APageByOffsetCutInTheProjectionGoesOnFromTheFirstItemNotShown()
    {
        JsonElement result = JsonSerializer.SerializeToElement(new
        {
            windows = Enumerable.Range(0, 40).Select(static index => new { title = new string('w', 300) + index }).ToArray(),
            count = 40,
            limit = 40,
            offset = 10,
            hasMore = false,
            nextOffset = (int?)null,
        });

        using JsonDocument message = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("window.resolve", OperationOutcome.Success(result)));
        JsonElement observed = message.RootElement.GetProperty("observed");
        int shown = observed.GetProperty("windows").GetArrayLength();

        Assert.Multiple(() =>
        {
            Assert.That(shown, Is.LessThan(40));
            Assert.That(observed.GetProperty("windowsShown").GetInt32(), Is.EqualTo(shown));
            Assert.That(observed.GetProperty("nextOffset").GetInt32(), Is.EqualTo(10 + shown));
            Assert.That(observed.GetProperty("hasMore").GetBoolean(), Is.True);
        });
    }

    // Ronda final 12: a last page («nextOffset: null») whose list only the 8 KiB projection cuts still goes on from the
    // first item not shown; and an operation that takes no offset (note.search) is never given a next page.
    [Test]
    public void ALastPageCutByTheSizeBoundGoesOnAndASearchWithoutOffsetsIsNeverPaged()
    {
        JsonElement lastPage = JsonSerializer.SerializeToElement(new
        {
            windows = Enumerable.Range(0, 18).Select(static index => new { title = "w" + index, detail = new string('d', 600) }).ToArray(),
            count = 18,
            limit = 20,
            offset = 40,
            hasMore = false,
            nextOffset = (int?)null,
        });
        JsonElement search = JsonSerializer.SerializeToElement(new
        {
            notes = Enumerable.Range(0, 30).Select(static index => new { title = "n" + index }).ToArray(),
            count = 30,
            totalCount = 30,
            scope = "search",
            limit = 30,
            offset = 0,
            nextOffset = (int?)null,
        });

        using JsonDocument cutPage = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("window.resolve", OperationOutcome.Success(lastPage)));
        using JsonDocument cutSearch = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("note.search", OperationOutcome.Success(search)));
        JsonElement page = cutPage.RootElement.GetProperty("observed");
        JsonElement found = cutSearch.RootElement.GetProperty("observed");
        int shown = page.GetProperty("windows").GetArrayLength();

        Assert.Multiple(() =>
        {
            Assert.That(shown, Is.LessThan(18), "the size bound cut the page");
            Assert.That(page.GetProperty("nextOffset").GetInt32(), Is.EqualTo(40 + shown));
            Assert.That(page.GetProperty("hasMore").GetBoolean(), Is.True);
            Assert.That(found.GetProperty("notesShown").GetInt32(), Is.EqualTo(20));
            Assert.That(found.GetProperty("nextOffset").ValueKind, Is.EqualTo(JsonValueKind.Null));
            Assert.That(found.TryGetProperty("hasMore", out _), Is.False);
        });
    }

    // Ronda final 42 (regla 3): a provider's shownCount and hasMore spoke of its list before the kernel's cut to 20; they
    // say what the model sees after it.
    [Test]
    public void AProvidersShownCountAndHasMoreFollowTheKernelsCut()
    {
        JsonElement listed = JsonSerializer.SerializeToElement(new
        {
            entries = Enumerable.Range(0, 35).Select(static index => new { name = "e" + index }).ToArray(),
            shownCount = 35,
            totalCount = 35,
            hasMore = false,
            resultsMayBeTruncated = false,
            searchScope = new { exhaustive = true, resultsMayBeTruncated = false },
        });

        using JsonDocument cut = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("filesystem.list", OperationOutcome.Success(listed)));
        JsonElement observed = cut.RootElement.GetProperty("observed");

        Assert.Multiple(() =>
        {
            Assert.That(observed.GetProperty("entriesShown").GetInt32(), Is.EqualTo(20));
            Assert.That(observed.GetProperty("shownCount").GetInt32(), Is.EqualTo(20));
            Assert.That(observed.GetProperty("hasMore").GetBoolean(), Is.True);
            Assert.That(observed.GetProperty("totalCount").GetInt32(), Is.EqualTo(35));
            Assert.That(observed.GetProperty("resultsMayBeTruncated").GetBoolean(), Is.True);
            Assert.That(observed.GetProperty("searchScope").GetProperty("resultsMayBeTruncated").GetBoolean(), Is.True);
        });
    }

    // Ronda final 43 (regla 3): a page read and a clipboard read keep their own bounds, not the 8 KiB budget (a page of
    // the default 12,000 characters reached the model as 2,000).
    [Test]
    public void APageReadOfTwelveThousandCharactersReachesTheModelWhole()
    {
        string text = new('a', 12_000);
        JsonElement read = JsonSerializer.SerializeToElement(new { title = "t", text, truncated = false });

        using JsonDocument facts = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("browser.page.read", OperationOutcome.Success(read)));

        Assert.That(facts.RootElement.GetProperty("observed").GetProperty("text").GetString(), Has.Length.EqualTo(12_000));
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
