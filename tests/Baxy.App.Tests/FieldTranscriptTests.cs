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
}
