using System.Text.Json;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class MediaStatusNarrationTests
{
    [TestCase("playing", "Está sonando «Billie Jean» de Michael Jackson.")]
    [TestCase("paused", "Está en pausa «Billie Jean» de Michael Jackson.")]
    public void VerifiedMediaStatusNamesTheObservedTitleArtistAndState(
        string status,
        string expected)
    {
        JsonElement result = JsonDocument.Parse($$"""
            {"version":1,"sourceAppUserModelId":"Spotify.exe","title":"Billie Jean","artist":"Michael Jackson","playbackStatus":"{{status}}","authority":"windows_smtc_current_session_read"}
            """).RootElement.Clone();

        string narration = OperationOutcomeNarration.For(
            "media.status",
            OperationOutcome.Success(result));

        Assert.That(narration, Is.EqualTo(expected));
    }

    [Test]
    public void MissingMediaSessionIsReportedAsAnObservedAbsence()
    {
        string narration = OperationOutcomeNarration.For(
            "media.status",
            OperationOutcome.Failure("media_session_not_found"));

        Assert.That(
            narration,
            Is.EqualTo("No hay ninguna reproducción visible para Windows en este momento."));
    }

    [TestCase(8, "Listo, adelanté 8 segundos y verifiqué la posición.")]
    [TestCase(-12, "Listo, retrocedí 12 segundos y verifiqué la posición.")]
    public void VerifiedRelativeSeekNamesTheObservedDirection(int seconds, string expected)
    {
        JsonElement result = JsonDocument.Parse($$"""
            {"version":1,"requestedDeltaSeconds":{{seconds}},"previousPositionSeconds":20,"positionSeconds":28,"durationSeconds":180,"sourceAppUserModelId":"Browser","authority":"windows_smtc_timeline_postread"}
            """).RootElement.Clone();

        Assert.That(
            OperationOutcomeNarration.For(
                "media.seek.relative",
                OperationOutcome.Success(result)),
            Is.EqualTo(expected));
    }
}
