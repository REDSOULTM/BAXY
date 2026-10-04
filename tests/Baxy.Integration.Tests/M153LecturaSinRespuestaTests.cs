using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M153 (sealed set v4r→v4s, metadata only: four task.list reads of seven open tasks and one notification.schedule
/// ended «filtered: no_response»; DEV-F v4o F-w47-t4 «Apúntamelo en una nota, que luego se me olvida» is the iterable
/// twin): every draft was refused, and the App's floor was published by the queue after the turn had closed — under
/// the next request. A refusal the mind answered is final, so its floor is this turn's final (InTurnFloor), and a
/// task list read is told by its titles (the mind's M58 final). The titles below are our own or DEV-F/G/H's.
/// </summary>
[TestFixture]
public sealed class M153LecturaSinRespuestaTests
{
    private static readonly string[] SevenTitles =
    [
        "queso gaudá laminado", "marraqueta para la once", "dos paltas hass", "llamar al contador mañana",
        "Renovar el pasaporte", "oat milk", "hago la cena",
    ];

    private static string TaskList(string[] titles, int completedIndex = -1)
    {
        var tasks = new JsonArray();
        for (int index = 0; index < titles.Length; index++)
        {
            tasks.Add(new JsonObject
            {
                ["taskId"] = $"id{index}", ["title"] = titles[index], ["completed"] = index == completedIndex,
                ["deleted"] = false, ["updatedAtUtc"] = "2026-10-03T09:31:50.4692362+00:00", ["version"] = 1,
            });
        }

        return new JsonObject
        {
            ["kind"] = "operation", ["operation"] = "task.list", ["polarity"] = "success", ["verified"] = true,
            ["succeeded"] = true,
            ["observed"] = new JsonObject
            {
                ["tasks"] = tasks, ["count"] = titles.Length, ["mode"] = "tasks", ["limit"] = 20,
            },
        }.ToJsonString();
    }

    private static ModelMessageCompositionOutcome Refused(string failure = "reversed_result") =>
        new(null, failure, UsedRecovery: false, RejectedText: string.Empty);

    private static string? Floor(string situation, string userText, ModelMessageCompositionOutcome outcome,
        bool queued = false)
    {
        var draft = new UserMessageDraft(situation, "status", null);
        return ModelMessageComposer.InTurnFloor(outcome, draft, userText, ModelMessageComposer.CreateFacts(draft), queued);
    }

    [TestCase("que tengo pendiente para hoy baxy",
        "Tienes pendientes «queso gaudá laminado», «marraqueta para la once», «dos paltas hass», «llamar al contador "
        + "mañana», «Renovar el pasaporte», «oat milk» y «hago la cena».")]
    [TestCase("q tengo pendiente pa esta semana",
        "Tienes pendientes «queso gaudá laminado», «marraqueta para la once», «dos paltas hass», «llamar al contador "
        + "mañana», «Renovar el pasaporte», «oat milk» y «hago la cena».")]
    [TestCase("anything still outstanding on my to-do list, or have I cleared the lot?",
        "Pending: «queso gaudá laminado», «marraqueta para la once», «dos paltas hass», «llamar al contador mañana», "
        + "«Renovar el pasaporte», «oat milk» and «hago la cena».")]
    public void ARefusedTaskListIsToldByItsTitlesInTheTurn(string userText, string expected)
    {
        Assert.That(Floor(TaskList(SevenTitles), userText, Refused()), Is.EqualTo(expected));
    }

    [Test]
    public void TheTaskListFloorSaysOnlyWhatWasRead()
    {
        // A repeated title is said once with its count; a completed one is not pending.
        string[] titles = ["huevos", "beer", "huevos", "iPhone"];
        Assert.That(
            Floor(TaskList(titles, completedIndex: 1), "what's on my list", Refused("task_title_not_named")),
            Is.EqualTo("Pending: «huevos» (2 times) and «iPhone»."));
    }

    [Test]
    public void ANoteTheMindCouldNotTellIsToldInItsTurn()
    {
        // DEV-F v4o F-w47-t4: three drafts refused; the App's floor reached the person only under the next request.
        string note = """{"kind":"operation","operation":"note.create","polarity":"success","verified":true,"succeeded":true,"observed":{"title":"en noviembre me voy a Boston, ¿cuántos dólares me dan hoy por cada euro","content":"En noviembre me voy a Boston, ¿cuántos dólares me dan hoy por cada euro?","createdAtUtc":"2026-10-03T10:08:51.9207367+00:00","updatedAtUtc":"2026-10-03T10:08:51.9207367+00:00","revision":1,"isTrashed":false}}""";
        Assert.That(
            Floor(note, "Apúntamelo en una nota, que luego se me olvida", Refused("no_response")),
            Is.EqualTo("Creé la nota «en noviembre me voy a Boston, ¿cuántos dólares me dan hoy por cada euro»."));
    }

    [Test]
    public void WhatIsNotAnAnsweredRefusalStillGoesThroughTheQueue()
    {
        string situation = TaskList(SevenTitles);
        Assert.Multiple(() =>
        {
            // The mind did not answer: the queue may compose it again.
            Assert.That(Floor(situation, "que tengo pendiente",
                new ModelMessageCompositionOutcome(null, "no_response", UsedRecovery: true, Unanswered: true)), Is.Null);
            // A message queued ahead keeps the order.
            Assert.That(Floor(situation, "que tengo pendiente", Refused(), queued: true), Is.Null);
            // An accepted draft is the final itself.
            Assert.That(Floor(situation, "que tengo pendiente",
                new ModelMessageCompositionOutcome("Tienes 7 tareas pendientes.", null, UsedRecovery: false)), Is.Null);
        });
    }

    private static string Reminder(string kind, string title, DateTime localDue)
    {
        string due = new DateTimeOffset(localDue).UtcDateTime.ToString("O", System.Globalization.CultureInfo.InvariantCulture);
        return new JsonObject
        {
            ["kind"] = "operation", ["operation"] = "notification.schedule", ["polarity"] = "success",
            ["verified"] = true, ["succeeded"] = true,
            ["observed"] = new JsonObject
            {
                ["version"] = 1, ["kind"] = kind, ["title"] = title, ["dueUtc"] = due, ["taskName"] = "BAXY-Reminder-1",
                ["state"] = "Ready", ["nextRunUtc"] = due, ["authority"] = "windows_task_scheduler_postread",
            },
        }.ToJsonString();
    }

    // The mind now publishes these (its title-blind claim checks were the refusal); the App accepts them as they are.
    [Test]
    public void TheAppAcceptsAReminderToldWithItsTitle()
    {
        DateTime today = DateTime.Today;
        (string Situation, string UserText, string Text)[] cases =
        [
            (Reminder("reminder", "Poner el celular en silencio", today.AddHours(22)),
                "recuérdame a las diez poner el celular en silencio",
                "Te recordaré a las 22:00 poner el celular en silencio."),
            (Reminder("reminder", "Mute the TV", today.AddHours(21)),
                "remind me at 9pm to mute the tv",
                "I'll remind you at 21:00 to mute the TV."),
            (Reminder("reminder", "¿Tomaste la pastilla?", today.AddHours(21)),
                "a las nueve pregúntame si tomé la pastilla",
                "Te avisaré a las 21:00: «¿Tomaste la pastilla?»."),
            // DEV-G v4s G-w01-t3: the first draft, refused by the mind as «bajo» (I lower).
            (Reminder("alarm", "Turno temprano", today.AddDays(1).AddHours(7)),
                "ya baxy dejame una alarma mañana a las 7 que tengo turno temprano",
                "He programado la alarma para mañana a las 07:00 bajo el título \"Turno temprano\"."),
        ];
        var refused = new List<string>();
        foreach ((string situation, string userText, string text) in cases)
        {
            var draft = new UserMessageDraft(situation, "status", null);
            if (UserMessagePolicy.AcceptModelAuthoredResponse(text, draft, userText, null) != text)
            {
                refused.Add($"{text} → {UserMessagePolicy.ModelResponseRejectionReason(text, draft, userText)}");
            }
        }

        Assert.That(refused, Is.Empty);
    }

    // A silence the observed data does not carry is still BAXY's claim (InventedVolume), beside a reminder.
    [Test]
    public void ASilenceNotObservedIsStillRefused()
    {
        DateTime today = DateTime.Today;
        (string Situation, string UserText, string Text)[] cases =
        [
            (Reminder("reminder", "Sacar la basura", today.AddHours(19)),
                "recuérdame a las siete sacar la basura",
                "Silencié el teléfono y te avisaré a las 19:00."),
            (Reminder("reminder", "Llamar a mamá", today.AddHours(22)),
                "recuérdame a las diez llamar a mamá",
                "Te recordaré a las 22:00 poner el celular en silencio."),
        ];
        foreach ((string situation, string userText, string text) in cases)
        {
            var draft = new UserMessageDraft(situation, "status", null);
            Assert.That(UserMessagePolicy.ModelResponseRejectionReason(text, draft, userText),
                Is.EqualTo("missing_literal_fact"), text);
        }
    }
}
