using Baxy.Providers.Windows.External;
using NUnit.Framework;

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
