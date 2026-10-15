using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Tasks;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M106 (DEV-D v4a D-w08-t3 «ponme recordatorio una ora antes d ese partido»): a verified reminder reached the mind
/// without its observation, so no draft could say its time. The reminder record repeated «version», and an
/// observation over the budget was dropped whole. Now the record has one «version», a repeated key keeps its last
/// value, and an observation over the budget is projected: identifying and asked fields whole, free text and lists
/// bounded, «truncated» set, and the message names the bound (observedLimit) for the trace. Sizes are the families'
/// realistic ones; the phrasings are our own.
/// </summary>
[TestFixture]
public sealed class M106ObservacionAcotadaTests
{
    private static readonly DateTimeOffset Now = new(2026, 10, 1, 12, 0, 0, TimeSpan.Zero);

    [Test]
    public async Task AVerifiedReminderReachesTheMindWithItsTitleAndTime()
    {
        JsonObject message = await CreateReminderAsync(details: string.Empty);
        JsonObject observed = message["observed"]!.AsObject();
        Assert.Multiple(() =>
        {
            Assert.That(observed["title"]!.GetValue<string>(), Is.EqualTo("Partido de la Selección"));
            Assert.That(observed["dueUtc"]!.GetValue<string>(), Does.StartWith("2026-10-03T23:00:00"));
            Assert.That(observed["version"]!.GetValue<long>(), Is.EqualTo(1));
            Assert.That(observed.ContainsKey("truncated"), Is.False);
            Assert.That(message.ContainsKey(OperationVisibleFacts.ObservedLimitKey), Is.False);
        });
    }

    // The mind now tells the verified due at the person's clock (test_c03_m106_observacion_acotada.py); the App
    // publishes that final over the record it carries.
    [Test]
    public async Task TheReminderFinalWithItsLocalTimeIsPublished()
    {
        JsonObject message = await CreateReminderAsync(details: string.Empty);
        DateTimeOffset local = DateTimeOffset.Parse("2026-10-03T23:00:00Z", CultureInfo.InvariantCulture).ToLocalTime();
        string final = $"Creé el recordatorio «Partido de la Selección» para el {local.Day} de octubre a las {local:HH:mm}.";
        var draft = new UserMessageDraft(message.ToJsonString(), "status", null);
        ModelMessageCompositionOutcome outcome = await ModelMessageComposer.ComposeAsync(
            draft, "ponme recordatorio una hora antes de ese partido", ModelMessageComposer.CreateFacts(draft),
            (_, _, _, _, _) => Task.FromResult<MindComposedMessage?>(new(final, Reproducible: true)),
            cpuFallback: false, allowRecovery: true, CancellationToken.None);
        Assert.That(outcome.Text, Is.EqualTo(final));
    }

    [Test]
    public async Task AReminderWithLongDetailsKeepsTitleAndTimeAndCutsTheDetails()
    {
        string details = Prose(60_000);
        JsonObject message = await CreateReminderAsync(details);
        JsonObject observed = message["observed"]!.AsObject();
        string kept = observed["details"]!.GetValue<string>();
        Assert.Multiple(() =>
        {
            Assert.That(message[OperationVisibleFacts.ObservedLimitKey]!.GetValue<string>(), Is.EqualTo("projected"));
            Assert.That(observed["title"]!.GetValue<string>(), Is.EqualTo("Partido de la Selección"));
            Assert.That(observed["dueUtc"]!.GetValue<string>(), Does.StartWith("2026-10-03T23:00:00"));
            Assert.That(observed["truncated"]!.GetValue<bool>(), Is.True);
            Assert.That(kept, Does.EndWith("…"));
            Assert.That(details, Does.StartWith(kept.TrimEnd('…')));
            Assert.That(kept.Length, Is.LessThanOrEqualTo(2_001));
        });
    }

    [Test]
    public void ARepeatedKeyKeepsItsLastValueInsteadOfDroppingTheObservation()
    {
        JsonObject message = Facts("reminder.create",
            """{"version":1,"reminderId":"x","title":"Llamar al dentista","dueUtc":"2026-10-02T13:00:00+00:00","version":4}""");
        Assert.Multiple(() =>
        {
            Assert.That(message["observed"]!["title"]!.GetValue<string>(), Is.EqualTo("Llamar al dentista"));
            Assert.That(message["observed"]!["version"]!.GetValue<int>(), Is.EqualTo(4));
        });
    }

    [Test]
    public void AReminderListOverTheBudgetKeepsEveryListedTitleAndTime()
    {
        var reminders = new JsonArray();
        for (int index = 0; index < 20; index++)
        {
            reminders.Add(new JsonObject
            {
                ["reminderId"] = Guid.NewGuid().ToString("D"),
                ["title"] = $"Recordatorio {index:D2}",
                ["details"] = Prose(1_500),
                ["dueUtc"] = Now.AddDays(index + 1).ToString("O", CultureInfo.InvariantCulture),
                ["dismissed"] = false,
                ["deleted"] = false,
                ["version"] = 1,
            });
        }
        var observation = new JsonObject { ["version"] = 1, ["reminders"] = reminders, ["count"] = 20, ["mode"] = "scheduled", ["limit"] = 20 };
        JsonObject message = Facts("reminder.list", observation);
        JsonObject observed = message["observed"]!.AsObject();
        JsonArray listed = observed["reminders"]!.AsArray();
        Assert.Multiple(() =>
        {
            Assert.That(message[OperationVisibleFacts.ObservedLimitKey]!.GetValue<string>(), Is.EqualTo("projected"));
            Assert.That(observed["count"]!.GetValue<int>(), Is.EqualTo(20));
            Assert.That(observed["truncated"]!.GetValue<bool>(), Is.True);
            Assert.That(listed, Is.Not.Empty);
            for (int index = 0; index < listed.Count; index++)
            {
                Assert.That(listed[index]!["title"]!.GetValue<string>(), Is.EqualTo($"Recordatorio {index:D2}"));
                Assert.That(listed[index]!["dueUtc"]!.GetValue<string>(),
                    Is.EqualTo(Now.AddDays(index + 1).ToString("O", CultureInfo.InvariantCulture)));
            }
        });
    }

    // M98 reads the first three result pages and appends up to 600 characters of each to its snippet. Five results
    // with three excerpts cross the old 4 KiB message ceiling; the observation now travels whole.
    [Test]
    public void ASearchWithPageExcerptsTravelsWhole()
    {
        JsonObject observation = Search(results: 5, excerpts: 3);
        Assert.That(observation.ToJsonString().Length, Is.InRange(4_096, 7_000));
        JsonObject message = Facts("web.search", observation);
        Assert.Multiple(() =>
        {
            Assert.That(message.ContainsKey(OperationVisibleFacts.ObservedLimitKey), Is.False);
            Assert.That(JsonNode.DeepEquals(message["observed"], observation), Is.True);
        });
    }

    [Test]
    public void ATwentyResultSearchKeepsEveryTitleAndAddressAndCutsSnippets()
    {
        JsonObject observation = Search(results: 20, excerpts: 3);
        Assert.That(observation.ToJsonString().Length, Is.GreaterThan(8_192));
        JsonObject message = Facts("web.search", observation);
        JsonObject observed = message["observed"]!.AsObject();
        JsonArray results = observed["results"]!.AsArray();
        Assert.Multiple(() =>
        {
            Assert.That(message[OperationVisibleFacts.ObservedLimitKey]!.GetValue<string>(), Is.EqualTo("projected"));
            Assert.That(observed["query"]!.GetValue<string>(), Is.EqualTo(observation["query"]!.GetValue<string>()));
            Assert.That(observed["count"]!.GetValue<int>(), Is.EqualTo(20));
            Assert.That(observed["truncated"]!.GetValue<bool>(), Is.True);
            Assert.That(results.Count, Is.GreaterThanOrEqualTo(5));
            for (int index = 0; index < results.Count; index++)
            {
                JsonNode original = observation["results"]![index]!;
                Assert.That(results[index]!["title"]!.GetValue<string>(), Is.EqualTo(original["title"]!.GetValue<string>()));
                Assert.That(results[index]!["url"]!.GetValue<string>(), Is.EqualTo(original["url"]!.GetValue<string>()));
                string snippet = results[index]!["snippet"]!.GetValue<string>();
                Assert.That(original["snippet"]!.GetValue<string>(), Does.StartWith(snippet.TrimEnd('…')));
            }
        });
    }

    [TestCase("browser.page.read")]
    [TestCase("document.pdf.read")]
    public void ALongReadKeepsItsDocumentAndTheBeginningOfItsText(string operation)
    {
        string text = Prose(12_000);
        var observation = new JsonObject
        {
            ["version"] = 1,
            ["reviewLabel"] = "informe-anual.pdf",
            ["url"] = "https://example.org/informe/anual",
            ["title"] = "Informe anual de la cooperativa",
            ["text"] = text,
            ["truncated"] = false,
            ["authority"] = "read_snapshot",
        };
        JsonObject message = Facts(operation, observation);
        JsonObject observed = message["observed"]!.AsObject();
        string lead = observed["text"]!.GetValue<string>();
        Assert.Multiple(() =>
        {
            Assert.That(message[OperationVisibleFacts.ObservedLimitKey]!.GetValue<string>(), Is.EqualTo("projected"));
            Assert.That(observed["title"]!.GetValue<string>(), Is.EqualTo("Informe anual de la cooperativa"));
            Assert.That(observed["reviewLabel"]!.GetValue<string>(), Is.EqualTo("informe-anual.pdf"));
            Assert.That(observed["url"]!.GetValue<string>(), Is.EqualTo("https://example.org/informe/anual"));
            Assert.That(observed["truncated"]!.GetValue<bool>(), Is.True);
            Assert.That(text, Does.StartWith(lead.TrimEnd('…')));
            Assert.That(lead.Length, Is.GreaterThan(600), "the mind's page lead (600) and PDF lead (450) still fit");
        });
    }

    [Test]
    public void ALongEmailKeepsItsSubjectSenderAndTime()
    {
        var observation = new JsonObject
        {
            ["version"] = 1,
            ["messageId"] = "email_opaque",
            ["subject"] = "Cambio de horario del taller",
            ["sender"] = "Coordinación del taller",
            ["receivedUtc"] = "2026-09-30T18:20:00Z",
            ["body"] = Prose(30_000),
            ["authority"] = "outlook_mapi_latest_snapshot",
        };
        JsonObject observed = Facts("email.latest.read", observation)["observed"]!.AsObject();
        Assert.Multiple(() =>
        {
            Assert.That(observed["subject"]!.GetValue<string>(), Is.EqualTo("Cambio de horario del taller"));
            Assert.That(observed["sender"]!.GetValue<string>(), Is.EqualTo("Coordinación del taller"));
            Assert.That(observed["receivedUtc"]!.GetValue<string>(), Is.EqualTo("2026-09-30T18:20:00Z"));
            Assert.That(observed["truncated"]!.GetValue<bool>(), Is.True);
        });
    }

    // A raw listing far over the budget whose sanitized form (twenty rows) fits is no longer dropped: the old gate
    // measured the raw result before the twenty-row cap.
    [Test]
    public void ALargeListingWhoseTwentyRowsFitTravelsUncut()
    {
        var entries = new JsonArray();
        for (int index = 0; index < 400; index++)
            entries.Add(new JsonObject { ["name"] = $"foto-{index:D3}.jpg", ["sizeBytes"] = 1_000 + index });
        var observation = new JsonObject { ["version"] = 1, ["folder"] = "Imágenes", ["count"] = 400, ["entries"] = entries };
        Assert.That(observation.ToJsonString().Length, Is.GreaterThan(8_192));
        JsonObject message = Facts("filesystem.known.list", observation);
        Assert.Multiple(() =>
        {
            Assert.That(message.ContainsKey(OperationVisibleFacts.ObservedLimitKey), Is.False);
            Assert.That(message["observed"]!["entries"]!.AsArray(), Has.Count.EqualTo(20));
            Assert.That(message["observed"]!["count"]!.GetValue<int>(), Is.EqualTo(400));
        });
    }

    [Test]
    public void AWindowInventoryWithLongTitlesKeepsTheTitlesAndCountsTheCutRows()
    {
        var windows = new JsonArray();
        for (int index = 0; index < 20; index++)
        {
            windows.Add(new JsonObject
            {
                ["title"] = $"Documento {index:D2} — " + new string('x', 120),
                ["processName"] = "WINWORD",
                ["executablePath"] = "C:/Program Files/Microsoft Office/root/Office16/" + new string('y', 400) + "/WINWORD.EXE",
                ["foreground"] = index == 0,
            });
        }
        var observation = new JsonObject { ["version"] = 1, ["windows"] = windows };
        JsonObject message = Facts("window.resolve", observation);
        JsonObject observed = message["observed"]!.AsObject();
        JsonArray kept = observed["windows"]!.AsArray();
        Assert.Multiple(() =>
        {
            Assert.That(message[OperationVisibleFacts.ObservedLimitKey]!.GetValue<string>(), Is.EqualTo("projected"));
            Assert.That(observed["truncated"]!.GetValue<bool>(), Is.True);
            for (int index = 0; index < kept.Count; index++)
                Assert.That(kept[index]!["title"]!.GetValue<string>(), Is.EqualTo(windows[index]!["title"]!.GetValue<string>()));
            if (kept.Count < 20)
                Assert.That(observed["windowsCount"]!.GetValue<int>(), Is.EqualTo(20));
        });
    }

    [Test]
    public void AnObservationThatCannotFitIsOmittedAndSaysSo()
    {
        var observation = new JsonObject();
        for (int index = 0; index < 400; index++) observation[$"title{index}"] = new string('t', 40);
        // Four hundred short fields: no step has a text or a list to cut, so nothing fits.
        JsonObject message = Facts("app.installed", observation);
        Assert.Multiple(() =>
        {
            Assert.That(message.ContainsKey("observed"), Is.False);
            Assert.That(message[OperationVisibleFacts.ObservedLimitKey]!.GetValue<string>(), Is.EqualTo("omitted"));
            Assert.That(message["polarity"]!.GetValue<string>(), Is.EqualTo("success"));
        });
    }

    [Test]
    public void TheBoundIsReadBackForTheTrace()
    {
        string projected = OperationVisibleFacts.FromOutcome("email.latest.read", OperationOutcome.Success(
            Element(new JsonObject { ["subject"] = "s", ["body"] = Prose(20_000) })));
        string whole = OperationVisibleFacts.FromOutcome("system.time", OperationOutcome.Success(
            Element(new JsonObject { ["utc"] = "2026-10-01T12:00:00Z" })));
        Assert.Multiple(() =>
        {
            Assert.That(OperationVisibleFacts.ObservedLimit(projected), Is.EqualTo("projected"));
            Assert.That(OperationVisibleFacts.ObservedLimit(whole), Is.Null);
            Assert.That(OperationVisibleFacts.ObservedLimit("not json"), Is.Null);
        });
    }

    private static async Task<JsonObject> CreateReminderAsync(string details)
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-m106-" + Guid.NewGuid().ToString("N"));
        try
        {
            IOperationHandler handler = ReminderHandlers.Create(new LocalTaskStore(root), new FixedTime(Now))
                .Single(item => item.Definition.Name == "reminder.create");
            var arguments = new JsonObject
            {
                ["title"] = "Partido de la Selección",
                ["dueUtc"] = "2026-10-03T23:00:00Z",
                ["details"] = details,
            };
            OperationOutcome outcome = await handler.ExecuteAsync(
                new OperationInvocation(
                    Guid.NewGuid().ToString("D"), Guid.NewGuid().ToString("D"), Guid.NewGuid().ToString("D"),
                    Element(arguments)),
                CancellationToken.None);
            Assert.That(outcome.Succeeded && outcome.Verified, Is.True);
            return ThroughTheApp("reminder.create", OperationVisibleFacts.FromOutcome("reminder.create", outcome));
        }
        finally
        {
            if (Directory.Exists(root)) Directory.Delete(root, recursive: true);
        }
    }

    private static JsonObject Facts(string operation, string observation)
    {
        using JsonDocument document = JsonDocument.Parse(observation);
        return ThroughTheApp(operation,
            OperationVisibleFacts.FromOutcome(operation, OperationOutcome.Success(document.RootElement.Clone())));
    }

    private static JsonObject Facts(string operation, JsonObject observation) =>
        Facts(operation, observation.ToJsonString());

    private static JsonObject ThroughTheApp(string operation, string facts)
    {
        Assert.That(facts.Length, Is.LessThanOrEqualTo(8_192));
        var response = new OperationResponse(
            ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"), Guid.NewGuid().ToString("D"),
            OperationStatuses.Completed, facts, true, false, null, null);
        string message = OperationResponseProjection.Create(response, operation).Message;
        Assert.That(message, Is.EqualTo(facts));
        return JsonNode.Parse(message)!.AsObject();
    }

    private static JsonElement Element(JsonObject value)
    {
        using JsonDocument document = JsonDocument.Parse(value.ToJsonString());
        return document.RootElement.Clone();
    }

    private static JsonObject Search(int results, int excerpts)
    {
        var items = new JsonArray();
        for (int index = 0; index < results; index++)
        {
            string snippet = "La regla general del agua de cocción es salarla como el mar; las cocinas profesionales "
                + "miden la sal por litro y la añaden cuando el agua ya hierve, antes de echar la pasta seca, y nunca "
                + "antes, porque la sal tarda en disolverse en agua fría. " + index;
            if (index < excerpts)
                snippet += " … " + Prose(600);
            items.Add(new JsonObject
            {
                ["title"] = $"Cuánta sal echarle al agua de la pasta, explicado paso a paso ({index})",
                ["url"] = $"https://www.ejemplo-cocina.example/recetas/pasta/sal-en-el-agua-de-coccion-cuanta-poner-{index}",
                ["snippet"] = snippet,
            });
        }
        return new JsonObject
        {
            ["version"] = 1,
            ["query"] = "cuánta sal le echo al agua de la pasta",
            ["count"] = results,
            ["results"] = items,
            ["authority"] = "general_web_search",
        };
    }

    private static string Prose(int length)
    {
        var text = new StringBuilder(length + 80);
        int sentence = 0;
        while (text.Length < length)
            text.Append("Esta es la frase ").Append(sentence++).Append(" del texto leído, con palabras corrientes y acentos. ");
        return text.ToString(0, length);
    }

    private sealed class FixedTime(DateTimeOffset utcNow) : TimeProvider
    {
        public override DateTimeOffset GetUtcNow() => utcNow;
    }
}
