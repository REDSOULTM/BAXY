using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class ChromeUiaFlagTests
{
    private const string Chrome = @"C:\Program Files\Google\Chrome\Application\chrome.exe";

    [TestCase(136, true, TestName = "a Chrome that shows only its frame gets the flag")]
    [TestCase(137, true, TestName = "the last one without it too")]
    [TestCase(138, false, TestName = "from 138 it is the default")]
    [TestCase(150, false, TestName = "and later")]
    public void TheFlagGoesOnlyToAChromeThatNeedsIt(int major, bool flagged)
    {
        Assert.That(ChromeUiaFlag.For(Chrome, _ => major), flagged ? Is.EqualTo(ChromeUiaFlag.Flag) : Is.Null);
    }

    [TestCase(@"C:\Program Files\Opera\opera.exe")]
    [TestCase(@"C:\Program Files\Microsoft\Edge\Application\msedge.exe")]
    [TestCase("")]
    [TestCase(null)]
    public void NoOtherProgramGetsIt(string? executable)
    {
        Assert.That(ChromeUiaFlag.For(executable, _ => 100), Is.Null);
    }

    [Test]
    public void AVersionThatCannotBeReadLeavesItAsItWas()
    {
        Assert.That(ChromeUiaFlag.For(Chrome, _ => null), Is.Null);
    }
}
