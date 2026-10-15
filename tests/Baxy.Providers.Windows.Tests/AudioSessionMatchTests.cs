using Baxy.Providers.Windows.Audio;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew audit (2026-10-15): the application whose volume changes is the one named — a word of its name is the
/// process name, exactly — never another one that shares a prefix.
/// </summary>
[TestFixture]
public sealed class AudioSessionMatchTests
{
    [TestCase("Spotify", "Spotify", true)]
    [TestCase("chrome", "Google Chrome", true)]
    [TestCase("opera", "Opera GX", true)]
    [TestCase("Discord", "discord", true)]
    [TestCase("WindowsTerminal", "Windows Media Player", false)]
    [TestCase("chromium", "Chrome", false)]
    [TestCase("spotifywebhelper", "Spotify", false)]
    public void A_word_of_the_name_is_the_process_exactly(string process, string application, bool matches) =>
        Assert.That(WindowsCoreAudioPlatform.ApplicationSessionMatches(process, application), Is.EqualTo(matches));
}
