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
