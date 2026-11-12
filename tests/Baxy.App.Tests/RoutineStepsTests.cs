using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// RUT1 (documentacion/RUTINAS.md §7): the steps of a baxy.routines call are read as the calls they will be, so the
/// App refuses one its tool profile or a privacy switch would refuse before the routine is saved.
/// </summary>
[TestFixture]
public sealed class RoutineStepsTests
{
    [Test]
    public void EachStepIsReadAsItsCallAndWordsToSayAreNoCall()
    {
        var arguments = (JsonObject)JsonNode.Parse("""
            {"action":"create","phrase":"cine","steps":[
              "media.control {\"action\":\"pause\"}", "say: a ver la peli", "audio.volume {\"level\":20}",
              "no.such.tool {}", "audio.mute [1]", "audio.status"]}
            """)!;

        (string Operation, JsonObject Arguments)[] steps = [.. NativeTurnLoop.RoutineSteps("baxy.routines", arguments)];

        Assert.Multiple(() =>
        {
            Assert.That(steps.Select(static step => step.Operation),
                Is.EqualTo(new[] { "media.control", "audio.volume", "audio.status" }));
            Assert.That((string?)steps[0].Arguments["action"], Is.EqualTo("pause"));
            Assert.That(steps[2].Arguments, Is.Empty);
            Assert.That(NativeTurnLoop.RoutineSteps("schedule.alarms", arguments), Is.Empty);
        });
    }
}
