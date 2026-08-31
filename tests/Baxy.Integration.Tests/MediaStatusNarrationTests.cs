using System.Text.Json;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class MediaStatusNarrationTests
{
    [TestCase("playing")]
    [TestCase("paused")]
    public void VerifiedMediaStatusNamesTheObservedTitleArtistAndState(string status)
    {
        JsonElement result = JsonDocument.Parse($$"""
            {"version":1,"sourceAppUserModelId":"Spotify.exe","title":"Billie Jean","artist":"Michael Jackson","playbackStatus":"{{status}}","authority":"windows_smtc_current_session_read"}
            """).RootElement.Clone();

        string narration = OperationOutcomeNarration.For(
            "media.status",
            OperationOutcome.Success(result));

        Assert.That(narration, Does.Contain("Billie Jean"));
        Assert.That(narration, Does.Contain("Michael Jackson"));
        Assert.That(narration, Does.Contain(status));
        Assert.That(
            OperationOutcomeNarration.Facts("media.status", OperationOutcome.Success(result))["polarity"]
                ?.GetValue<string>(),
            Is.EqualTo("success"));
    }

    [Test]
    public void MissingMediaSessionIsReportedAsAnObservedAbsence()
    {
        var facts = OperationOutcomeNarration.Facts(
            "media.status",
            OperationOutcome.Failure("media_session_not_found"));

        Assert.That(facts["polarity"]?.GetValue<string>(), Is.EqualTo("failure"));
        Assert.That(facts["error"]?.GetValue<string>(), Is.EqualTo("media_session_not_found"));
    }

    [TestCase(8)]
    [TestCase(-12)]
    public void VerifiedRelativeSeekNamesTheObservedDirection(int seconds)
    {
        JsonElement result = JsonDocument.Parse($$"""
            {"version":1,"requestedDeltaSeconds":{{seconds}},"previousPositionSeconds":20,"positionSeconds":28,"durationSeconds":180,"sourceAppUserModelId":"Browser","authority":"windows_smtc_timeline_postread"}
            """).RootElement.Clone();

        string narration = OperationOutcomeNarration.For(
            "media.seek.relative",
            OperationOutcome.Success(result));

        Assert.That(narration, Does.Contain($"\"requestedDeltaSeconds\":{seconds}"));
        Assert.That(
            OperationOutcomeNarration.Facts("media.seek.relative", OperationOutcome.Success(result))["polarity"]
                ?.GetValue<string>(),
            Is.EqualTo("success"));
    }
}
