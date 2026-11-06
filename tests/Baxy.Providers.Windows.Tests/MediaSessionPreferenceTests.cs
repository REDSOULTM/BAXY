using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;
using Windows.Media.Control;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Owner's live check 2026-10-06: Spotify kept playing while BAXY played YouTube in Opera GX and «para la música»
/// paused Spotify, the session Windows still called current. An unnamed media request means what BAXY played.
/// </summary>
[TestFixture]
public sealed class MediaSessionPreferenceTests
{
    private const string Opera = "OperaSoftware.OperaGXWebBrowser.1732473326";
    private const string Spotify = "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify";

    [Test]
    public void WhatBaxyPlaysWinsOverAnotherPlayingSession() =>
        Assert.That(
            WindowsMediaSessionAdapter.PreferAssistantSession(
                [(Spotify, true, false), (Opera, true, false)], Opera),
            Is.EqualTo(Opera));

    [Test]
    public void WhatBaxyPausedIsResumedWhenNothingElsePlays() =>
        Assert.That(
            WindowsMediaSessionAdapter.PreferAssistantSession(
                [(Spotify, false, true), (Opera, false, true)], Opera),
            Is.EqualTo(Opera));

    [Test]
    public void SomethingThePersonStartedLaterIsNotOverridden() =>
        Assert.That(
            WindowsMediaSessionAdapter.PreferAssistantSession(
                [(Spotify, true, false), (Opera, false, true)], Opera),
            Is.Null);

    // Renew al máximo (R6.1): with a paused session in front and the person's music playing, «pausa la música» said
    // «paused» on the paused one and the music played on.
    [TestCase(new[] { false, true }, "pause", 1)]
    [TestCase(new[] { true, false }, "stop", 0)]
    [TestCase(new[] { false, false, true }, "next", 2)]
    [TestCase(new[] { false, true }, "previous", 1)]
    [TestCase(new[] { false, true }, "toggle", 1)]
    public void AnUnnamedControlReachesTheOneSessionPlayingWhenTheCurrentDoesNot(bool[] playing, string action, int expected) =>
        Assert.That(WindowsMediaSessionAdapter.PlayingInsteadOfCurrent(false, playing, action), Is.EqualTo(expected));

    [Test]
    public void TheCurrentSessionStaysWhenItPlaysWhenNoneOrSeveralOthersDoOrToResume()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsMediaSessionAdapter.PlayingInsteadOfCurrent(true, [true, true], "pause"), Is.Null);
            Assert.That(WindowsMediaSessionAdapter.PlayingInsteadOfCurrent(false, [false, false], "pause"), Is.Null);
            Assert.That(WindowsMediaSessionAdapter.PlayingInsteadOfCurrent(false, [true, false, true], "pause"), Is.Null);
            Assert.That(WindowsMediaSessionAdapter.PlayingInsteadOfCurrent(false, [false, true], "play"), Is.Null);
        });
    }

    // Renew al máximo (auditoría de flujos): «¿qué está sonando?» with a paused tab in front and the person's music
    // playing read the paused tab as what plays (playbackStatus paused), the music only among otherSessions. A read
    // reports the one session playing when the current does not, as an unnamed control acts on it (R6.1).
    [Test]
    public void TheStatusReadsTheOneSessionPlayingWhenTheCurrentDoesNot()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsMediaSessionAdapter.PlayingInsteadOfCurrent(
                false, [false, true], "media.status", action: null), Is.EqualTo(1));
            Assert.That(WindowsMediaSessionAdapter.PlayingInsteadOfCurrent(
                true, [true, true], "media.status", action: null), Is.Null);
            Assert.That(WindowsMediaSessionAdapter.PlayingInsteadOfCurrent(
                false, [true, false, true], "media.status", action: null), Is.Null);
            Assert.That(WindowsMediaSessionAdapter.PlayingInsteadOfCurrent(
                false, [false, true], "media.control", "pause"), Is.EqualTo(1));
            Assert.That(WindowsMediaSessionAdapter.PlayingInsteadOfCurrent(
                false, [false, true], "media.control", "play"), Is.Null);
            Assert.That(WindowsMediaSessionAdapter.PlayingInsteadOfCurrent(
                false, [false, true], "media.seek.relative", action: null), Is.Null);
        });
    }

    // Renew al máximo (R6.5): two sessions of the client made the choice throw, and media.play.exact answered
    // smtc_session_access_failed. The one playing is checked, else the first; the play is verified on it either way.
    [Test]
    public void TwoSessionsOfTheClientNeverMakeTheExactPlayFail()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsMediaSessionAdapter.ClientSession([(Opera, true), (Spotify, false), (Spotify, true)]),
                Is.EqualTo(2));
            Assert.That(WindowsMediaSessionAdapter.ClientSession([(Spotify, false), (Opera, true), (Spotify, false)]),
                Is.EqualTo(0));
            Assert.That(WindowsMediaSessionAdapter.ClientSession([(Opera, true), (Spotify, false)]), Is.EqualTo(1));
            Assert.That(WindowsMediaSessionAdapter.ClientSession([(Opera, true)]), Is.Null);
        });
    }

    // Renew al máximo (6.1): media.status reported only the session it chose, and media.control's sourceApp is an id
    // a media.status result gave, so «pausa Spotify» with two players could never name the other one.
    [Test]
    public void TheStatusNamesTheOtherSessionsShortly()
    {
        string longTitle = new('a', 200);
        JsonElement result = WindowsMediaSessionAdapter.StatusResult(Opera, "Video", "Canal", null, "paused",
        [
            new UserMediaSession(Spotify, "Canción", "Artista", "paused"),
            new UserMediaSession("Closed.App", "Nada", "", "closed"),
            new UserMediaSession("", "Sin fuente", "", "playing"),
            new UserMediaSession("Other.One", longTitle, "", "stopped"),
            new UserMediaSession("Other.Two", "Dos", "", "paused"),
            new UserMediaSession("Other.Playing", "Suena", "Alguien", "playing"),
        ]);

        JsonElement[] others = result.TryGetProperty("otherSessions", out JsonElement list)
            ? [.. list.EnumerateArray()]
            : [];
        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("sourceAppUserModelId").GetString(), Is.EqualTo(Opera));
            Assert.That(others.Select(other => other.GetProperty("sourceAppUserModelId").GetString()),
                Is.EqualTo(new[] { "Other.Playing", Spotify, "Other.One" }));
            Assert.That(others[0].GetProperty("playbackStatus").GetString(), Is.EqualTo("playing"));
            Assert.That(others[1].GetProperty("title").GetString(), Is.EqualTo("Canción"));
            Assert.That(others[2].GetProperty("title").GetString(), Has.Length.LessThanOrEqualTo(60).And.StartWith("aaa"));
            Assert.That(others.SelectMany(other => other.EnumerateObject()).Select(property => property.Name).Distinct(),
                Is.EquivalentTo(new[] { "sourceAppUserModelId", "title", "playbackStatus" }));
        });
    }

    [Test]
    public void WithoutOtherSessionsTheStatusSaysNothingMore()
    {
        JsonElement result = WindowsMediaSessionAdapter.StatusResult(Spotify, "Canción", "Artista", "Disco", "playing",
            [new UserMediaSession("Closed.App", "Nada", "", "closed")]);

        Assert.Multiple(() =>
        {
            Assert.That(result.TryGetProperty("otherSessions", out _), Is.False);
            Assert.That(result.GetProperty("album").GetString(), Is.EqualTo("Disco"));
        });
    }

    // Uso real 2026-11-02 («para la canción y pon otra»): SMTC leaves a Play or a Pause to the app, and an app may take it
    // as its play/pause key, so a play sent to the song already playing paused it. A session that already reads the
    // state asked for gets no command; a toggle, a stop and a skip are still sent.
    [TestCase("play", GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing, null)]
    [TestCase("pause", GlobalSystemMediaTransportControlsSessionPlaybackStatus.Paused, null)]
    [TestCase("stop", GlobalSystemMediaTransportControlsSessionPlaybackStatus.Stopped, null)]
    [TestCase("stop", GlobalSystemMediaTransportControlsSessionPlaybackStatus.Closed, null)]
    [TestCase("play", GlobalSystemMediaTransportControlsSessionPlaybackStatus.Paused, "play")]
    [TestCase("pause", GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing, "pause")]
    [TestCase("stop", GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing, "stop")]
    [TestCase("toggle", GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing, "pause")]
    [TestCase("toggle", GlobalSystemMediaTransportControlsSessionPlaybackStatus.Paused, "play")]
    [TestCase("next", GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing, "next")]
    public void AControlSendsNothingToASessionAlreadyInTheStateAskedFor(
        string action, GlobalSystemMediaTransportControlsSessionPlaybackStatus before, string? expected) =>
        Assert.That(WindowsMediaSessionAdapter.ControlCommand(action, before), Is.EqualTo(expected));

    [Test]
    public void WithoutAPlaybackOfItsOwnWindowsDecides()
    {
        Assert.Multiple(() =>
        {
            Assert.That(
                WindowsMediaSessionAdapter.PreferAssistantSession([(Spotify, true, false)], null),
                Is.Null);
            Assert.That(
                WindowsMediaSessionAdapter.PreferAssistantSession([(Spotify, true, false)], Opera),
                Is.Null);
            Assert.That(
                WindowsMediaSessionAdapter.PreferAssistantSession(
                    [(Spotify, true, false)], "BAXY YouTube (Edge)"),
                Is.Null);
        });
    }
}
