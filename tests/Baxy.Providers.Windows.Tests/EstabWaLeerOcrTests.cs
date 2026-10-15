using Baxy.Providers.Windows.External;
using NUnit.Framework;
using Line = Baxy.Providers.Windows.External.WindowsVisibleOcrLocator.LayoutLine;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo WA-LEER: the lines a chat is read from keep every place a text is read (redpc, chat «Abuela», 1938×1098: by
/// text 45 of 66 lines stayed, 12 of its 13 bubbles «prueba BAXY imp» out, and the last bubble's time «4:51», which the
/// chat list repeats); only the second reading of the same text in the same place is the same line.
/// </summary>
[TestFixture]
public sealed class EstabWaLeerOcrTests
{
    private static Line At(string text, double x, double y, double w = 138, double h = 18) => new(text, x, y, w, h);

    [Test]
    public void TheSameTextReadAgainInTheSamePlaceIsOneLine() =>
        Assert.That(WindowsVisibleOcrLocator.ReadAgain(At("prueba BAXY imp", 1630, 955), At("Prueba BAXY imp", 1631, 956)),
            Is.True);

    [Test]
    public void ContracaseTheSameTextElsewhereIsAnotherLine() =>
        Assert.Multiple(() =>
        {
            // Two bubbles one under the other, and the list's time beside the bubble's time.
            Assert.That(WindowsVisibleOcrLocator.ReadAgain(At("prueba BAXY imp", 1630, 910), At("prueba BAXY imp", 1630, 955)),
                Is.False);
            Assert.That(WindowsVisibleOcrLocator.ReadAgain(At("4:51", 482, 339, 26, 11), At("4:51", 1783, 965, 26, 11)), Is.False);
        });

    [Test]
    public void ContracaseAnotherTextInTheSamePlaceIsLeftToTheMind() =>
        Assert.That(WindowsVisibleOcrLocator.ReadAgain(At("2311", 482, 339, 26, 11), At("23:11", 482, 339, 26, 11)), Is.False);
}
