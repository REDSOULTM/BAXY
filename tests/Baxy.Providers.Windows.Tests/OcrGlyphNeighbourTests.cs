using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// BAXY Renew cu (C03): Steam's store tab was read «"D TIENDA», its icon as a word beside the label, and the click on
/// «TIENDA» found nothing set apart. An icon read as a word does not keep a label from being set apart; a short word of
/// a sentence still does.
/// </summary>
[TestFixture]
public sealed class OcrGlyphNeighbourTests
{
    [TestCase("\"D", true)]
    [TestCase("»", true)]
    [TestCase("@", true)]
    [TestCase("y", false)]
    [TestCase("de", false)]
    [TestCase("a,", false)]
    [TestCase("12", false)]
    [TestCase("TIENDA", false)]
    public void AnIconReadAsAWordIsAGlyphAndAShortWordIsNot(string text, bool glyph)
    {
        Assert.That(WindowsVisibleOcrLocator.IsGlyph(text), Is.EqualTo(glyph));
    }
}
