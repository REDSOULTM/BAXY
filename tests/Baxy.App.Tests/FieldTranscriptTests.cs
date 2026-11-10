using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>The conversation the host keeps for the view (FieldTranscript): what a kept session shows again.</summary>
[TestFixture]
public sealed class FieldTranscriptTests
{
    [Test]
    public void ACardKeptPendingIsNoLongerPendingWhenItsSessionIsOpened()
    {
        var transcript = new FieldTranscript();
        transcript.Replace(new JsonArray(
            new JsonObject { ["who"] = "card", ["id"] = "k1", ["status"] = "pending", ["expires"] = long.MaxValue },
            new JsonObject { ["who"] = "card", ["id"] = "k2", ["status"] = "yes" }));

        Assert.Multiple(() =>
        {
            Assert.That((string?)transcript.Items[0]["status"], Is.EqualTo("dropped"));
            Assert.That((string?)transcript.Items[1]["status"], Is.EqualTo("yes"));
            Assert.That(transcript.Resolve("approved", null), Is.Null, "nothing kept is left to answer");
        });
    }

    // INT16, second blind review: a session saved while an alarm rang (BAXY closed, or another conversation opened) kept
    // its card «ringing»: opened again it showed a live Parar and, in the view, held Enter and Esc for every card after.
    // A kept ring rings no more; the App gives back the ones that still ring (FieldProductChannel.StartSession).
    [Test]
    public void ARingKeptRingingRingsNoMoreWhenItsSessionIsOpenedUnlessItStillRings()
    {
        static JsonObject Ring(string id, string status) => new()
        {
            ["who"] = "ring", ["id"] = "ring-" + id,
            ["ring"] = new JsonObject { ["id"] = id[^8..], ["kind"] = "alarm", ["clock"] = "07:00", ["words"] = "Alarma", ["status"] = status },
        };
        var transcript = new FieldTranscript();
        transcript.Replace(new JsonArray(Ring(new string('a', 32), "ringing"), Ring(new string('b', 32), "ringing"),
            Ring(new string('c', 32), "stopped")));

        Assert.That(transcript.Items.Select(static item => (string?)item["ring"]!["status"]), Is.EqualTo(new[] { "ended", "ended", "stopped" }));

        transcript.Ring(Ring(new string('b', 32), "ringing"));

        Assert.That(transcript.Items.Select(static item => (string?)item["ring"]!["status"]), Is.EqualTo(new[] { "ended", "ringing", "stopped" }));
    }
}
