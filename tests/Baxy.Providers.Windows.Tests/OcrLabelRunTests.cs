using Baxy.Providers.Windows.External;
using NUnit.Framework;
using Rect = Windows.Foundation.Rect;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Auditoría final: a run of words inside a longer OCR line reads a label only when a visual gap sets it apart from the
/// line's other words on both sides; words of a sentence that happen to spell the label are not it.
/// </summary>
[TestFixture]
public sealed class OcrLabelRunTests
{
    private static readonly Rect Label = new(400, 100, 90, 16);

    [Test]
    public void AWholeLineIsItsOwnLabel() =>
        Assert.That(WindowsVisibleOcrLocator.SetApart(Label, null, null), Is.True);

    [Test]
    public void ALabelOfARowReadAsOneLineStandsApartFromItsNeighbours() =>
        // «BIBLIOTECA      COMUNIDAD»: 60 px on each side, more than a body and a half (24 px).
        Assert.That(WindowsVisibleOcrLocator.SetApart(Label, new Rect(250, 100, 90, 16), new Rect(550, 100, 90, 16)),
            Is.True);

    [Test]
    public void ContracaseWordsOfASentenceAreNotTheLabel() =>
        Assert.Multiple(() =>
        {
            // «Ir a la biblioteca»: the word before stands one space away.
            Assert.That(WindowsVisibleOcrLocator.SetApart(Label, new Rect(380, 100, 14, 16), null), Is.False);
            // «Biblioteca de juegos»: the word after stands one space away.
            Assert.That(WindowsVisibleOcrLocator.SetApart(Label, null, new Rect(496, 100, 20, 16)), Is.False);
        });
}
