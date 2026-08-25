using System.Text.Json;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class MediaStatusNarrationTests
{
    [TestCase("playing")]
    [TestCase("paused")]
    public void VerifiedMediaStatusCarriesObservedTitleArtistAndState(string status)
    {
        JsonElement result = JsonDocument.Parse($$"""
            {"version":1,"sourceAppUserModelId":"Spotify.exe","title":"Billie Jean","artist":"Michael Jackson","playbackStatus":"{{status}}","authority":"windows_smtc_current_session_read"}
            """).RootElement.Clone();

        JsonElement facts = OperationOutcomeNarration.AssertFacts(
            "media.status",
            OperationOutcome.Success(result));
        JsonElement observed = facts.GetProperty("observed");

        Assert.Multiple(() =>
        {
            Assert.That(observed.GetProperty("title").GetString(), Is.EqualTo("Billie Jean"));
            Assert.That(observed.GetProperty("artist").GetString(), Is.EqualTo("Michael Jackson"));
            Assert.That(observed.GetProperty("playbackStatus").GetString(), Is.EqualTo(status));
        });
    }

    [Test]
    public void MissingMediaSessionIsReportedAsAnObservedAbsence()
    {
        JsonElement facts = OperationOutcomeNarration.AssertFacts(
            "media.status",
            OperationOutcome.Failure("media_session_not_found"));

        Assert.That(facts.GetProperty("error").GetString(), Is.EqualTo("media_session_not_found"));
    }

    [TestCase(8)]
    [TestCase(-12)]
    public void VerifiedRelativeSeekCarriesTheObservedDirection(int seconds)
    {
        JsonElement result = JsonDocument.Parse($$"""
            {"version":1,"requestedDeltaSeconds":{{seconds}},"previousPositionSeconds":20,"positionSeconds":28,"durationSeconds":180,"sourceAppUserModelId":"Browser","authority":"windows_smtc_timeline_postread"}
            """).RootElement.Clone();

        JsonElement facts = OperationOutcomeNarration.AssertFacts(
            "media.seek.relative",
            OperationOutcome.Success(result));

        Assert.That(
            facts.GetProperty("observed").GetProperty("requestedDeltaSeconds").GetInt32(),
            Is.EqualTo(seconds));
    }
}
