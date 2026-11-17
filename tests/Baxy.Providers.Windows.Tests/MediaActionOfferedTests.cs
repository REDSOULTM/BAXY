using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// DIAX19 (H-081, caso 21 del 16-11): «siguiente canción» on a single YouTube video in Edge. The browser's media
/// session said IsNextEnabled = false, media.control sent the skip anyway, nothing changed and the receipt was «failed,
/// maybe happened» (smtc_postcondition_not_verified); the model then said the next song was playing 3 of 5 times and
/// paused the video 3 of 5. A command the session does not offer is not sent: the failure says so, with what it offers.
/// </summary>
[TestFixture]
public sealed class MediaActionOfferedTests
{
    private const string Edge = "MSEdge";
    private const string Spotify = "Spotify.exe";

    // What the 16-11 session published: pause and stop only (playing; no next, no previous).
    private static readonly WindowsMediaSessionAdapter.OfferedControls SingleVideo =
        new(Play: false, Pause: true, Stop: true, Next: false, Previous: false, Toggle: false);

    private static readonly WindowsMediaSessionAdapter.OfferedControls Everything =
        new(Play: true, Pause: true, Stop: true, Next: true, Previous: true, Toggle: true);

    private static WindowsMediaSessionAdapter.OfferedControls Without(string command) => command switch
    {
        "play" => Everything with { Play = false, Toggle = false },
        "pause" => Everything with { Pause = false, Toggle = false },
        "stop" => Everything with { Stop = false },
        "next" => Everything with { Next = false },
        _ => Everything with { Previous = false },
    };

    [TestCase("next")]
    [TestCase("previous")]
    [TestCase("play")]
    [TestCase("pause")]
    [TestCase("stop")]
    public void ACommandTheSessionDoesNotOfferIsNotSentAndFailsForCertain(string command)
    {
        ExternalCapabilityReceipt? refused = WindowsMediaSessionAdapter.NotOffered(
            "media.control", command, Without(command), Edge, "Canción", "Canal", "playing", null);

        Assert.That(refused, Is.Not.Null);
        JsonElement result = refused!.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(refused.ErrorCode, Is.EqualTo("media_action_not_offered"));
            Assert.That(refused.Verified, Is.False);
            // Nothing was sent: the failure is certain, not «pudo o no ocurrir».
            Assert.That(refused.EffectObserved, Is.False);
            Assert.That(refused.EffectMayHaveOccurred, Is.False);
            Assert.That(result.GetProperty("actionNotOffered").GetString(), Is.EqualTo(command));
            Assert.That(result.GetProperty("sourceAppUserModelId").GetString(), Is.EqualTo(Edge));
            Assert.That(result.GetProperty("title").GetString(), Is.EqualTo("Canción"));
            Assert.That(result.GetProperty("playbackStatus").GetString(), Is.EqualTo("playing"));
            Assert.That(
                result.GetProperty("actionsOffered").EnumerateArray().Select(item => item.GetString()),
                Does.Not.Contain(command));
        });
    }

    [Test]
    public void TheSingleVideoSaysItOffersPauseAndStopOnly()
    {
        JsonElement result = WindowsMediaSessionAdapter.NotOffered(
            "media.control", "next", SingleVideo, Edge, "Canción", "Canal", "playing", null)!.Result!.Value;

        Assert.That(
            result.GetProperty("actionsOffered").EnumerateArray().Select(item => item.GetString()),
            Is.EqualTo(new[] { "pause", "stop" }));
    }

    [TestCase("next")]
    [TestCase("previous")]
    [TestCase("play")]
    [TestCase("pause")]
    [TestCase("stop")]
    public void ACommandTheSessionOffersIsSentAsBefore(string command) =>
        Assert.That(
            WindowsMediaSessionAdapter.NotOffered(
                "media.control", command, Everything, Spotify, "Canción", "Artista", "playing", null),
            Is.Null);

    // A player that only publishes its play/pause key still takes a play or a pause (sent as before).
    [TestCase("play")]
    [TestCase("pause")]
    public void ThePlayPauseKeyOffersPlayAndPause(string command) =>
        Assert.That(
            WindowsMediaSessionAdapter.NotOffered(
                "media.control", command,
                new WindowsMediaSessionAdapter.OfferedControls(false, false, false, false, false, Toggle: true),
                Edge, "Canción", "Canal", "paused", null),
            Is.Null);

    [Test]
    public void MediaStatusSaysWhatTheSessionOffers()
    {
        JsonElement result = WindowsMediaSessionAdapter.StatusResult(Edge, "Canción", "Canal", null, "playing", [],
            SingleVideo.Names);

        Assert.That(
            result.GetProperty("actionsOffered").EnumerateArray().Select(item => item.GetString()),
            Is.EqualTo(new[] { "pause", "stop" }));
    }
}
