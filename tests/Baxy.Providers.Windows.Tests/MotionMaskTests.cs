using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

// PLAN_GENERAL A3/A4 (uso real 2026-10-21, e2e del notebook: Epic's store plays a video): what a window changes by itself
// is told apart, by cells, from what a press changed and from the room around the point pressed.
public sealed class MotionMaskTests
{
    private const int Width = 128;
    private const int Height = 64;

    // A 32-bit bottom-up BMP of the window, every pixel grey but the rectangles painted.
    private static VisibleControlSurface.CapturedWindow Frame(string tag, params (int X, int Y, int W, int H, byte Shade)[] paint)
    {
        int stride = Width * 4;
        var bmp = new byte[54 + (stride * Height)];
        bmp[0] = (byte)'B';
        bmp[1] = (byte)'M';
        BitConverter.GetBytes(54).CopyTo(bmp, 10);
        BitConverter.GetBytes(40).CopyTo(bmp, 14);
        BitConverter.GetBytes(Width).CopyTo(bmp, 18);
        BitConverter.GetBytes(Height).CopyTo(bmp, 22);
        BitConverter.GetBytes((short)1).CopyTo(bmp, 26);
        BitConverter.GetBytes((short)32).CopyTo(bmp, 28);
        bmp.AsSpan(54).Fill(0x80);
        foreach ((int x, int y, int w, int h, byte shade) in paint)
        {
            for (int row = y; row < y + h; row++)
                bmp.AsSpan(54 + ((Height - 1 - row) * stride) + (x * 4), w * 4).Fill(shade);
        }

        return new VisibleControlSurface.CapturedWindow(7, bmp, 0, 0, Width, Height, tag);
    }

    private static VisibleControlSurface.MotionMask Mask(params VisibleControlSurface.CapturedWindow[] frames)
    {
        bool[] moving = new bool[8];
        int columns = 0, rows = 0;
        foreach (VisibleControlSurface.CapturedWindow next in frames[1..])
        {
            bool[] differing = VisibleControlSurface.DifferingCells(frames[0], next, out columns, out rows)!;
            for (int cell = 0; cell < differing.Length; cell++)
                moving[cell] |= differing[cell];
        }

        return new VisibleControlSurface.MotionMask(columns, rows, moving);
    }

    [Test]
    public void TheCellsThatDifferAreFound()
    {
        bool[]? differing = VisibleControlSurface.DifferingCells(Frame("a"), Frame("b", (70, 40, 4, 4, 0xFF)), out int columns, out int rows);
        Assert.Multiple(() =>
        {
            Assert.That((columns, rows), Is.EqualTo((4, 2)));
            Assert.That(differing!.Select((d, i) => d ? i : -1).Where(i => i >= 0), Is.EqualTo(new[] { 6 }));
        });
    }

    [Test]
    public void APressChangeOutsideTheVideoProvesThePressAndTheVideoAloneDoesNot()
    {
        var video1 = (0, 0, 32, 32, (byte)0x10);
        var video2 = (0, 0, 32, 32, (byte)0x20);
        VisibleControlSurface.CapturedWindow before = Frame("v1", video1);
        VisibleControlSurface.MotionMask motion = Mask(before, Frame("v2", video2));
        Assert.Multiple(() =>
        {
            Assert.That(motion.Any, Is.True);
            Assert.That(VisibleControlSurface.ChangedOutsideMotion(before, Frame("v3", video2), motion), Is.False,
                "only the video moved");
            Assert.That(VisibleControlSurface.ChangedOutsideMotion(before, Frame("v4", video2, (96, 40, 20, 20, 0xFF)), motion),
                Is.True, "the press changed a still part");
            Assert.That(VisibleControlSurface.ChangedOutsideMotion(before, Frame("v5", video2), null), Is.False,
                "an unknown motion proves nothing");
            Assert.That(motion.MovingAt(10, 10), Is.True);
            Assert.That(motion.MovingAt(100, 50), Is.False);
        });
    }

    [Test]
    public void APointWhoseRoomDidNotChangeStillHoldsWhileAFarCornerMoves()
    {
        VisibleControlSurface.CapturedWindow before = Frame("a", (0, 0, 16, 16, 0x10));
        VisibleControlSurface.CapturedWindow far = Frame("b", (0, 0, 16, 16, 0x20));
        VisibleControlSurface.CapturedWindow near = Frame("c", (0, 0, 16, 16, 0x10), (100, 40, 8, 8, 0xFF));
        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.SameAround(before, far, 110, 48), Is.True);
            Assert.That(VisibleControlSurface.SameAround(before, near, 110, 48), Is.False);
        });
    }
}
