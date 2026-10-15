using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// D39 (owner, 2026-09-29; v3d-final F-s040 «Cancela las alarmas, por favor.»): the alarms are read and BAXY offers to
/// cancel them with the list. The shell lets the offer through as the answer to the verified read; nothing is
/// cancelled until the person says yes, which the mind turns into one cancellation per alarm read.
/// </summary>
[TestFixture]
public sealed class D39CancelarAlarmasTests
{
    private static string AlarmsRead() => new JsonObject
    {
        ["kind"] = "operation",
        ["operation"] = "notification.list",
        ["polarity"] = "success",
        ["verified"] = true,
        ["succeeded"] = true,
        ["observed"] = new JsonObject
        {
            ["version"] = 1,
            ["count"] = 3,
            ["notifications"] = new JsonArray(
                Alarm("2026-09-30T10:00:00Z"), Alarm("2026-09-30T11:30:00Z"), Alarm("2026-09-30T15:00:00Z")),
            ["staleTaskCount"] = 0,
            ["resultLimit"] = 20,
            ["resultsMayBeTruncated"] = false,
            ["authority"] = "windows_task_scheduler_notification_list_postread",
        },
    }.ToJsonString();

    private static JsonObject Alarm(string nextRunUtc) => new()
    {
        ["kind"] = "alarm",
        ["title"] = "alarma",
        ["nextRunUtc"] = nextRunUtc,
        ["state"] = "Ready",
    };

    [TestCase("Tienes 3 alarmas (7:00, 8:30 y 12:00). ¿Las cancelo todas?")]
    [TestCase("Tienes 3 alarmas para mañana: a las 7:00, a las 8:30 y a las 12:00. ¿Quieres que las cancele todas?")]
    public void TheOfferWithTheAlarmsReadIsTheAnswer(string reply)
    {
        UserMessageDraft draft = UserMessagePolicy.Create(AlarmsRead(), UserMessageEvent.Status);
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(reply, draft, "Cancela las alarmas, por favor."), Is.Null);
    }
}
