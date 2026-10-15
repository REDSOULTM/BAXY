using System.Globalization;
using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Tasks;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 19b, palanca «recordatorio-por-id» (t1-c04-2 «no, mejor a las nueve y media» → «la instrucción era
/// ambigua»): the reminder this conversation just made is resolved by the id its verified reminder.create returned,
/// so other reminders with the same title, made in other conversations, never make the move ambiguous. A resolve by
/// title alone keeps its ambiguity, and an id whose reminder has another title is not found.
/// </summary>
[TestFixture]
public sealed class R19bRecordatorioPorIdTests
{
    private static readonly DateTimeOffset Now = new(2026, 10, 9, 12, 0, 0, TimeSpan.Zero);

    [Test]
    public void The_catalog_declares_the_verified_id_of_the_reminder_resolved()
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("reminder.resolve.exact");
        using JsonDocument byId = JsonDocument.Parse(
            """{"title":"llamar al dentista","reminderId":"2062b659-6ef7-4109-8d99-c932580db43d"}""");
        using JsonDocument byTitle = JsonDocument.Parse("""{"title":"llamar al dentista"}""");
        using JsonDocument idAlone = JsonDocument.Parse("""{"reminderId":"2062b659-6ef7-4109-8d99-c932580db43d"}""");
        Assert.Multiple(() =>
        {
            Assert.That(OperationArgumentValidator.IsValid(byId.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(OperationArgumentValidator.IsValid(byTitle.RootElement, descriptor.ArgumentsSchema), Is.True);
            // The title stays required: an id alone never names a reminder.
            Assert.That(OperationArgumentValidator.IsValid(idAlone.RootElement, descriptor.ArgumentsSchema), Is.False);
        });
    }

    [Test]
    public async Task The_reminder_just_made_is_moved_by_its_id_and_the_same_titled_others_stay()
    {
        using var temporary = new TemporaryDirectory();
        Dictionary<string, IOperationHandler> handlers = Handlers(temporary.Path);
        // Two «llamar al dentista» made in other conversations, then the one this conversation made.
        string older = Id(await Run(handlers, "reminder.create", Create("llamar al dentista", 60)));
        string other = Id(await Run(handlers, "reminder.create", Create("llamar al dentista", 120)));
        JsonElement made = await Run(handlers, "reminder.create", Create("llamar al dentista", 180));
        string madeId = Id(made);

        OperationOutcome byTitle = await Execute(
            handlers, "reminder.resolve.exact", """{"title":"llamar al dentista"}""");
        JsonElement selected = await Run(handlers, "reminder.resolve.exact",
            $$"""{"title":"llamar al dentista","reminderId":"{{madeId}}"}""");
        await Run(handlers, "reminder.delete",
            $$"""{"reminderId":"{{selected.GetProperty("reminderId").GetString()}}","expectedVersion":{{selected.GetProperty("expectedVersion").GetInt64()}},"reviewLabel":"{{selected.GetProperty("reviewLabel").GetString()}}"}""");
        await Run(handlers, "reminder.create", Create("llamar al dentista", 210));
        JsonElement listed = await Run(handlers, "reminder.list", "{}");
        string[] open = listed.GetProperty("reminders").EnumerateArray()
            .Select(item => item.GetProperty("reminderId").GetString()!).ToArray();

        Assert.Multiple(() =>
        {
            Assert.That(byTitle.Succeeded, Is.False);
            Assert.That(byTitle.ErrorCode, Is.EqualTo("reminder_ambiguous"));
            Assert.That(selected.GetProperty("reminderId").GetString(), Is.EqualTo(madeId));
            Assert.That(selected.GetProperty("reviewLabel").GetString(), Is.EqualTo("llamar al dentista"));
            Assert.That(open, Does.Contain(older).And.Contain(other).And.Not.Contain(madeId));
            Assert.That(open, Has.Length.EqualTo(3));
        });
    }

    [Test]
    public async Task An_id_whose_reminder_has_another_title_or_was_deleted_is_not_found()
    {
        using var temporary = new TemporaryDirectory();
        Dictionary<string, IOperationHandler> handlers = Handlers(temporary.Path);
        JsonElement made = await Run(handlers, "reminder.create", Create("pagar el gas", 60));
        string id = Id(made);

        OperationOutcome otherTitle = await Execute(handlers, "reminder.resolve.exact",
            $$"""{"title":"llamar al dentista","reminderId":"{{id}}"}""");
        await Run(handlers, "reminder.delete",
            $$"""{"reminderId":"{{id}}","expectedVersion":{{made.GetProperty("version").GetInt64()}},"reviewLabel":"pagar el gas"}""");
        OperationOutcome deleted = await Execute(handlers, "reminder.resolve.exact",
            $$"""{"title":"pagar el gas","reminderId":"{{id}}"}""");

        Assert.Multiple(() =>
        {
            Assert.That(otherTitle.Succeeded, Is.False);
            Assert.That(otherTitle.ErrorCode, Is.EqualTo("reminder_not_found"));
            Assert.That(deleted.Succeeded, Is.False);
            Assert.That(deleted.ErrorCode, Is.EqualTo("reminder_not_found"));
        });
    }

    private static Dictionary<string, IOperationHandler> Handlers(string root) =>
        ReminderHandlers.Create(new LocalTaskStore(Path.Combine(root, "reminders")), new FixedTime(Now))
            .ToDictionary(handler => handler.Definition.Name, StringComparer.Ordinal);

    private static string Create(string title, int minutes) =>
        $$"""{"title":"{{title}}","dueUtc":"{{Now.AddMinutes(minutes).ToString("O", CultureInfo.InvariantCulture)}}"}""";

    private static string Id(JsonElement record) => record.GetProperty("reminderId").GetString()!;

    private static async Task<JsonElement> Run(
        Dictionary<string, IOperationHandler> handlers, string operation, string arguments)
    {
        OperationOutcome outcome = await Execute(handlers, operation, arguments);
        Assert.That(outcome.Succeeded, Is.True, $"{operation}: {outcome.ErrorCode}");
        return outcome.Result!.Value;
    }

    private static async Task<OperationOutcome> Execute(
        Dictionary<string, IOperationHandler> handlers, string operation, string arguments)
    {
        IOperationHandler handler = handlers[operation];
        using JsonDocument document = JsonDocument.Parse(arguments);
        Assert.That(
            OperationArgumentValidator.IsValid(document.RootElement, ProductCatalog.GetRequired(operation).ArgumentsSchema),
            Is.True,
            $"{operation} arguments must be valid against the real catalog");
        var invocation = new OperationInvocation(
            Guid.NewGuid().ToString("D"), Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"), document.RootElement.Clone());
        return await handler.ExecuteAsync(invocation, CancellationToken.None);
    }

    private sealed class FixedTime(DateTimeOffset utcNow) : TimeProvider
    {
        public override DateTimeOffset GetUtcNow() => utcNow;
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(
                System.IO.Path.GetTempPath(), "baxy-r19b-recordatorio-por-id",
                Guid.NewGuid().ToString("N", CultureInfo.InvariantCulture));
            Directory.CreateDirectory(Path);
        }

        public string Path { get; }

        public void Dispose()
        {
            if (Directory.Exists(Path)) Directory.Delete(Path, recursive: true);
        }
    }
}
