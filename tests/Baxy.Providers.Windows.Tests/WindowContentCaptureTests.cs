using System.Diagnostics;
using Baxy.Providers.Windows.Capture;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// v3 point 0 (texto4 §6): a look never brings its window to the front, so a window behind the person's own is
/// captured as it draws itself (PrintWindow) instead of copying the screen, where the cover is. The capture is cut
/// to the same screen bounds as the screen copy, gives up within its budget on a window that does not answer, and
/// never passes off an empty (black) frame as the window.
/// </summary>
[TestFixture]
public sealed class WindowContentCaptureTests
{
    [Test]
    public void TheCutKeepsTheScreenPointsOfTheWindowDrawnFromItsWholeRectangle()
    {
        // A 5×4 drawing at screen (100, 200), bottom-up; each pixel's blue channel is its column, green its row.
        const int width = 5, height = 4;
        byte[] drawn = new byte[width * height * 4];
        for (int y = 0; y < height; y++)
        {
            for (int x = 0; x < width; x++)
            {
                int offset = ((height - 1 - y) * width + x) * 4;
                drawn[offset] = (byte)x;
                drawn[offset + 1] = (byte)y;
                drawn[offset + 3] = 255;
            }
        }

        // The frame bounds inside the drawing: columns 1..3, rows 1..2 (the invisible border cut away).
        byte[] cut = GdiScreenshotPlatform.CropBottomUp(drawn, width, height, 100, 200, new CaptureBounds(101, 201, 3, 2));

        Assert.That(cut, Has.Length.EqualTo(3 * 2 * 4));
        for (int row = 0; row < 2; row++)
        {
            for (int column = 0; column < 3; column++)
            {
                int offset = ((2 - 1 - row) * 3 + column) * 4;
                Assert.Multiple(() =>
                {
                    Assert.That(cut[offset], Is.EqualTo(column + 1), "column");
                    Assert.That(cut[offset + 1], Is.EqualTo(row + 1), "row");
                });
            }
        }
    }

    [Test]
    public void ACutOutsideTheDrawingIsRefused()
    {
        byte[] drawn = new byte[4 * 4 * 4];

        Assert.Throws<IOException>(() =>
            GdiScreenshotPlatform.CropBottomUp(drawn, 4, 4, 0, 0, new CaptureBounds(2, 2, 3, 3)));
    }

    [Test]
    public void AWindowThatDoesNotAnswerIsGivenUpWithinTheBudget()
    {
        using var release = new ManualResetEventSlim(false);
        var watch = Stopwatch.StartNew();

        Assert.Throws<IOException>(() => WindowsScreenshotProvider.CaptureWithin(
            () =>
            {
                release.Wait(TimeSpan.FromSeconds(5));
                return Lit(2, 2);
            },
            TimeSpan.FromMilliseconds(100)));
        watch.Stop();
        release.Set();

        Assert.That(watch.Elapsed, Is.LessThan(TimeSpan.FromSeconds(2)));
    }

    [Test]
    public void AnEmptyBlackFrameIsNoImageOfTheWindow()
    {
        var black = new ScreenshotFrame(3, 3, new byte[3 * 3 * 4]);

        Assert.Throws<IOException>(() => WindowsScreenshotProvider.CaptureWithin(() => black, TimeSpan.FromSeconds(1)));
    }

    [Test]
    public void ADarkFrameWithAnyDrawnPixelIsKept()
    {
        // Contracase of the black frame: a dark page with one lighter pixel (a letter, a border) is the window.
        ScreenshotFrame dark = Lit(3, 3);

        ScreenshotFrame kept = WindowsScreenshotProvider.CaptureWithin(() => dark, TimeSpan.FromSeconds(1));

        Assert.That(kept, Is.SameAs(dark));
    }

    [Test]
    public void AFailedDrawingIsAnInputOutputFailureTheLookSurvives()
    {
        Assert.Throws<IOException>(() => WindowsScreenshotProvider.CaptureWithin(
            () => throw new InvalidOperationException("no surface"), TimeSpan.FromSeconds(1)));
    }

    private static ScreenshotFrame Lit(int width, int height)
    {
        byte[] pixels = new byte[width * height * 4];
        pixels[4 + 2] = 60;
        return new ScreenshotFrame(width, height, pixels);
    }
}
