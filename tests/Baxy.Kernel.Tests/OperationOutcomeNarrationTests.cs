using System.Text.Json;
using Baxy.Contracts;
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

    // Revisión 2026-10-22 (C-7): a window's raw handle is no id any operation takes (e2e p3 E007: the model passed
    // app.open's windowHandle as windowId and read the refusal as «it is no longer open»); app.open's and a capture's
    // stay with the receipt, and the windowId the window operations take reaches the model.
    [Test]
    public void AWindowHandleNeverReachesTheModel()
    {
        JsonElement opened = JsonSerializer.SerializeToElement(new { appId = "Bloc de notas", windowHandle = 777, windowId = "w-1", window = 777 });
        JsonElement captured = JsonSerializer.SerializeToElement(new { captureId = "c1", activeWindow = new { windowHandle = 777, isClipped = false } });

        using JsonDocument openedFacts = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("app.open", OperationOutcome.Success(opened)));
        using JsonDocument capturedFacts = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("capture.active.window", OperationOutcome.Success(captured)));
        JsonElement openedObserved = openedFacts.RootElement.GetProperty("observed");
        JsonElement window = capturedFacts.RootElement.GetProperty("observed").GetProperty("activeWindow");

        Assert.Multiple(() =>
        {
            Assert.That(openedObserved.TryGetProperty("windowHandle", out _), Is.False);
            Assert.That(openedObserved.GetProperty("windowId").GetString(), Is.EqualTo("w-1"));
            // NB-R1 P1.12: the number the input operations take as «window» reaches it under that name.
            Assert.That(openedObserved.GetProperty("window").GetInt64(), Is.EqualTo(777));
            Assert.That(window.TryGetProperty("windowHandle", out _), Is.False);
            Assert.That(window.GetProperty("isClipped").GetBoolean(), Is.False);
        });
    }

    // Al máximo 8.2: how a completed call was verified is one typed fact, from what its receipt already says; the mind
    // translates only it («ya estaba así» was told «completado y verificado»).
    [TestCase("app.close", "{\"windowClosed\":true}", "readback")]
    [TestCase("audio.volume", "{\"applied\":false,\"reconciled\":true}", "readback")]
    [TestCase("input.text.type", "{\"delivered\":true,\"readBack\":true}", "readback")]
    [TestCase("clipboard.write.text", "{\"characterCount\":4,\"changed\":false}", "unchanged")]
    [TestCase("app.close", "{\"windowClosed\":false,\"alreadyGone\":true}", "unchanged")]
    [TestCase("audio.volume", "{\"applied\":false,\"reconciled\":false}", "unchanged")]
    [TestCase("input.text.type", "{\"delivered\":true}", "delivered_only")]
    [TestCase("input.text.type", "{\"delivered\":true,\"readBack\":false}", "delivered_only")]
    [TestCase("shell.command.run", "{\"exitCode\":0,\"effectReadBack\":false}", "delivered_only")]
    [TestCase("note.read", "{\"title\":\"Compras\"}", "output_only")]
    [TestCase("browser.page.read", "{\"title\":\"Compras\"}", "output_only")]
    // Auditoría de falsedades 2026-11-04 (P1, 18 turnos): Enter sent a message, its receipt brought the window read again
    // after it with the message in the history (after.changed), and «delivered_only» was told «no se volvió a mirar si
    // hizo efecto»: «pero no se envió todavía». A key's window read after it with a change is its effect read back; one
    // that read no change, or only the focus moving, and a text whose read back did not match, are not.
    [TestCase("input.key.press",
        "{\"ok\":true,\"delivered\":true,\"action\":\"key\",\"key\":\"enter\",\"textLength\":0,\"method\":\"keyboard\","
        + "\"sentTo\":{\"title\":\"Chat de prueba\",\"process\":\"ChatPrueba\"},\"restored\":true,\"after\":{\"changed\":["
        + "\"[7] Edit «Escribe un mensaje» focused\",\"[8] Edit «Mensajes» readonly = Yo: llego en diez minutos.\"]}}",
        "readback")]
    [TestCase("input.key.press", "{\"delivered\":true,\"after\":{\"appeared\":[\"[3] Button «Aceptar»\"]}}", "readback")]
    [TestCase("input.key.press", "{\"delivered\":true,\"after\":{\"title\":\"Otra\"}}", "readback")]
    [TestCase("input.key.press", "{\"delivered\":true,\"after\":{\"same\":true}}", "delivered_only")]
    [TestCase("input.key.press", "{\"delivered\":true,\"after\":{\"sameListed\":true,\"cut\":true}}", "delivered_only")]
    [TestCase("input.key.press",
        "{\"delivered\":true,\"after\":{\"changed\":[\"[7] Edit «Escribe» focused\"],\"focusOnly\":true}}", "delivered_only")]
    [TestCase("input.key.press", "{\"delivered\":true,\"after\":{\"omitted\":3}}", "delivered_only")]
    [TestCase("input.text.type",
        "{\"delivered\":true,\"readBack\":false,\"after\":{\"changed\":[\"[2] Edit «Buscar» = hola\"]}}", "delivered_only")]
    public void ACompletedCallSaysHowItWasVerified(string operation, string result, string verification)
    {
        using JsonDocument message = JsonDocument.Parse(OperationVisibleFacts.FromOutcome(
            operation, OperationOutcome.Success(JsonDocument.Parse(result).RootElement.Clone())));

        Assert.That(message.RootElement.GetProperty("verification").GetString(), Is.EqualTo(verification));
    }

    // Al máximo 8.2: a verified result whose observation did not fit the message is still verified (it was told «sin
    // verificar»): the receipt is read before the observation is cut.
    [Test]
    public void AVerifiedResultWhoseObservationDidNotFitStaysVerified()
    {
        JsonElement result = JsonSerializer.SerializeToElement(new { windowClosed = true, title = new string('a', 9_000) });
        using JsonDocument message = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("app.close", OperationOutcome.Success(result)));

        Assert.Multiple(() =>
        {
            Assert.That(message.RootElement.GetProperty(OperationVisibleFacts.ObservedLimitKey).GetString(),
                Is.EqualTo(OperationVisibleFacts.ObservedOmitted));
            Assert.That(message.RootElement.GetProperty("verification").GetString(), Is.EqualTo("readback"));
        });
    }

    // Uso-108 (B2): a key whose window's image changed was looked at again, even with the same tree (after «sameListed»);
    // with no such fact it stays what Windows accepted.
    [TestCase("""{"delivered":true,"surfaceChanged":true}""", "readback")]
    [TestCase("""{"delivered":true,"surfaceChanged":true,"after":{"sameListed":true}}""", "readback")]
    [TestCase("""{"delivered":true}""", "delivered_only")]
    [TestCase("""{"delivered":true,"after":{"same":true}}""", "delivered_only")]
    [TestCase("""{"delivered":true,"surfaceChanged":true,"readBack":false}""", "delivered_only")]
    public void AKeysImageThatChangedIsItsEffectReadBack(string receipt, string told)
    {
        using JsonDocument facts = JsonDocument.Parse(receipt);

        Assert.That(OperationVisibleFacts.Verification("input.key.press", facts.RootElement), Is.EqualTo(told));
    }

    // A call that did not complete says how it ended by its status and error, and nothing of a verification.
    [Test]
    public void ACallThatDidNotCompleteSaysNoVerification()
    {
        using JsonDocument message = JsonDocument.Parse(OperationVisibleFacts.FromOutcome(
            "app.close", OperationOutcome.Failure("window_not_found")));

        Assert.That(message.RootElement.TryGetProperty("verification", out _), Is.False);
    }

    // Revisión 2026-10-22 (C-2): a retryable outcome is what the engine answers as pending; the facts say pending too,
    // not failed beside a pending flag.
    [Test]
    public void ARetryableOutcomeIsPendingInTheFactsAsInTheResponse()
    {
        using JsonDocument message = JsonDocument.Parse(OperationVisibleFacts.FromOutcome(
            "note.create", OperationOutcome.RetryableFailure("reconciliation_required", effectMayHaveOccurred: true)));

        Assert.Multiple(() =>
        {
            Assert.That(message.RootElement.GetProperty("status").GetString(), Is.EqualTo(OperationStatuses.Pending));
            Assert.That(message.RootElement.GetProperty("error").GetString(), Is.EqualTo("reconciliation_required"));
            Assert.That(message.RootElement.GetProperty("effectUncertain").GetBoolean(), Is.True);
        });
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

    // Holdout v4 (falsedad, «revisé todo el archivo» after part of it): a page the message cuts ends on the line its shown
    // text reaches, is never the last one, and is read in part.
    [Test]
    public void ACutPageEndsOnTheLineItsShownTextReachesAndIsReadInPart()
    {
        string page = string.Concat(Enumerable.Range(0, 1_500).Select(static index => $"línea {index:D4}\n"));
        JsonElement result = JsonSerializer.SerializeToElement(new
        {
            characters = page.Length,
            totalLines = 1_500,
            offset = 0,
            lines = 1_500,
            fromLine = 1,
            toLine = 1_500,
            returnedCharacters = page.Length,
            hasMore = false,
            endReached = true,
            text = page,
        });

        using JsonDocument message = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("file.read", OperationOutcome.Success(result)));
        JsonElement observed = message.RootElement.GetProperty("observed");
        string shown = observed.GetProperty("text").GetString()!;
        int shownLines = shown[..^1].Count(static character => character == '\n')
            + (shown[..^1].EndsWith('\n') ? 0 : 1);

        Assert.Multiple(() =>
        {
            Assert.That(shown, Does.EndWith("…"));
            Assert.That(observed.GetProperty("toLine").GetInt32(), Is.EqualTo(shownLines));
            Assert.That(observed.GetProperty("toLine").GetInt32(), Is.LessThan(1_500));
            Assert.That(observed.GetProperty("endReached").GetBoolean(), Is.False);
            Assert.That(observed.GetProperty("readInPart").GetBoolean(), Is.True);
        });
    }

    // Revisión de calidad del núcleo (final2): a page one character longer than a projection step, with no space near
    // the cut (a minified file, a text in Chinese), loses its last character and gains «…»: as long as before, but cut.
    [Test]
    public void APageOneCharacterOverAStepIsStillReadInPart()
    {
        string page = new('字', 2_001);
        JsonElement result = JsonSerializer.SerializeToElement(new
        {
            offset = 0,
            fromLine = 1,
            toLine = 1,
            returnedCharacters = page.Length,
            hasMore = false,
            endReached = true,
            nextOffset = (int?)null,
            text = page,
            // What else the result carries pushes the message past its budget; the first step cuts it to fit.
            summary = string.Join(' ', Enumerable.Repeat("resumen", 900)),
        });

        using JsonDocument message = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("file.read", OperationOutcome.Success(result)));
        JsonElement observed = message.RootElement.GetProperty("observed");
        string shown = observed.GetProperty("text").GetString()!;

        Assert.Multiple(() =>
        {
            Assert.That(shown, Is.Not.EqualTo(page));
            Assert.That(observed.GetProperty("readInPart").GetBoolean(), Is.True);
            Assert.That(observed.GetProperty("endReached").GetBoolean(), Is.False);
            Assert.That(observed.GetProperty("hasMore").GetBoolean(), Is.True);
            Assert.That(observed.GetProperty("nextOffset").GetInt32(), Is.EqualTo(shown.Length - 1));
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
            windows = Enumerable.Range(0, 50).Select(static index => new { title = "w" + index, detail = new string('d', 300) }).ToArray(),
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
            notes = Enumerable.Range(0, 30).Select(static index => new { title = "n" + index, detail = new string('d', 300) }).ToArray(),
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

    // Ronda final 42 (regla 3): a provider's shownCount and hasMore spoke of its list before the kernel's cut; they say
    // what the model sees after it.
    [Test]
    public void AProvidersShownCountAndHasMoreFollowTheKernelsCut()
    {
        JsonElement listed = JsonSerializer.SerializeToElement(new
        {
            entries = Enumerable.Range(0, 35).Select(static index => new { name = "e" + index, detail = new string('d', 300) }).ToArray(),
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

    // Rondas finales 43-44 (regla 3): a page read of its 6,000 characters fits the 8 KiB budget whole (a page of the
    // former default 12,000 characters reached the model as 2,000).
    [Test]
    public void APageReadOfSixThousandCharactersReachesTheModelWhole()
    {
        string text = new('a', 6_000);
        JsonElement read = JsonSerializer.SerializeToElement(new { title = "t", text, truncated = false });

        using JsonDocument facts = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("browser.page.read", OperationOutcome.Success(read)));

        Assert.That(facts.RootElement.GetProperty("observed").GetProperty("text").GetString(), Has.Length.EqualTo(6_000));
    }

    // Encargo 62: 6,000 characters in short lines at a long address take the page's links past 8 KiB: the links go, said,
    // and the text stays whole (it was the read's answer before the links came to the receipt).
    [Test]
    public void APageReadPastEightKibLeavesItsLinksOutAndKeepsItsText()
    {
        string url = "https://ejemplo.test/" + new string('a', 500);
        string text = string.Concat(Enumerable.Repeat("una linea\n", 600));
        string[] links = [.. Enumerable.Range(0, 40).Select(static i => $"Enlace de prueba numero {i,2}")];
        JsonElement read = JsonSerializer.SerializeToElement(new { url, title = "t", text, truncated = false, links });

        using JsonDocument facts = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("browser.page.read", OperationOutcome.Success(read)));
        JsonElement observed = facts.RootElement.GetProperty("observed");

        Assert.Multiple(() =>
        {
            Assert.That(observed.GetProperty("text").GetString(), Has.Length.EqualTo(6_000));
            Assert.That(observed.TryGetProperty("links", out _), Is.False);
            Assert.That(observed.GetProperty("linksTruncated").GetBoolean(), Is.True);
        });
    }

    // Uso-111 (P3): a page read in blocks fits the budget with them whole, as PageBlocks bounds them.
    [Test]
    public void APageReadInBlocksFitsTheBudgetWhole()
    {
        var blocks = Enumerable.Range(0, 12)
            .Select(static i => new { title = $"Resultado {i}", url = $"https://sitio{i}.test/pagina", text = new string('b', 380) })
            .ToArray();
        string[] links = [.. Enumerable.Range(0, 40).Select(static i => $"Enlace de prueba numero {i,2}")];
        JsonElement read = JsonSerializer.SerializeToElement(new
        {
            url = "https://motor.test/?q=algo",
            title = "t",
            blocks,
            text = new string('t', 1_000),
            truncated = false,
            links,
        });

        string message = OperationVisibleFacts.FromOutcome("browser.page.read", OperationOutcome.Success(read));
        using JsonDocument facts = JsonDocument.Parse(message);
        JsonElement observed = facts.RootElement.GetProperty("observed");

        Assert.Multiple(() =>
        {
            Assert.That(message, Has.Length.LessThanOrEqualTo(8_192));
            Assert.That(observed.GetProperty("blocks").GetArrayLength(), Is.EqualTo(12));
            Assert.That(observed.GetProperty("blocks")[11].GetProperty("text").GetString(), Has.Length.EqualTo(380));
        });
    }

    // Ronda final 45 (the model's context): an OCR whose word boxes pass 8 KiB keeps its text and says the boxes are out.
    [Test]
    public void AnOcrPastEightKibLeavesItsWordBoxesOutAndKeepsItsText()
    {
        var words = Enumerable.Range(0, 300)
            .Select(static i => new { text = $"palabra{i}", boundingRect = new { x = i, y = i, width = 40, height = 12 } })
            .ToArray();
        string text = string.Join(' ', words.Select(static word => word.text));
        JsonElement read = JsonSerializer.SerializeToElement(new
        {
            text,
            layout = new { available = true, lines = new[] { new { text, words } } },
        });

        using JsonDocument facts = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("ocr.read", OperationOutcome.Success(read)));

        JsonElement observed = facts.RootElement.GetProperty("observed");
        Assert.Multiple(() =>
        {
            Assert.That(observed.GetProperty("text").GetString(), Is.EqualTo(text));
            Assert.That(observed.GetProperty("layout").GetProperty("available").GetBoolean(), Is.False);
            Assert.That(facts.RootElement.GetRawText(), Has.Length.LessThanOrEqualTo(8_192));
        });
    }

    // Uso real 02-11 («juegos instalados en Steam»): 30 games in about 5.8k characters reached the model as 20 and it said
    // the list was cut. A list that fits the 8 KiB budget reaches it whole, with nothing said left out.
    [Test]
    public void AListThatFitsTheBudgetReachesTheModelWhole()
    {
        JsonElement listed = JsonSerializer.SerializeToElement(new
        {
            games = Enumerable.Range(0, 30).Select(static index => new { appId = "1" + index, name = "Game " + index, state = "installed" }).ToArray(),
            count = 30,
        });

        using JsonDocument facts = JsonDocument.Parse(
            OperationVisibleFacts.FromOutcome("game.catalog.list", OperationOutcome.Success(listed)));
        JsonElement observed = facts.RootElement.GetProperty("observed");

        Assert.Multiple(() =>
        {
            Assert.That(observed.GetProperty("games").GetArrayLength(), Is.EqualTo(30));
            Assert.That(observed.TryGetProperty("gamesShown", out _), Is.False);
            Assert.That(observed.TryGetProperty("truncated", out _), Is.False);
            Assert.That(facts.RootElement.TryGetProperty(OperationVisibleFacts.ObservedLimitKey, out _), Is.False);
        });
    }

    [Test]
    public void AListWithoutACountKeepsItsLengthAndADeepValueLeftOutIsSaid()
    {
        JsonElement listed = JsonSerializer.SerializeToElement(new
        {
            tasks = Enumerable.Range(0, 30).Select(static index => new { title = "t" + index, detail = new string('d', 300) }).ToArray(),
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
