using System.Buffers.Binary;
using System.Runtime.InteropServices;
using System.Security.Cryptography;

namespace Baxy.Providers.Windows.Capture;

public sealed class WindowsScreenshotProvider : IScreenshotProvider
{
    private readonly string _directory;
    private readonly IScreenshotPlatform _platform;
    private readonly TimeProvider _time;

    public WindowsScreenshotProvider(string directory)
        : this(directory, new GdiScreenshotPlatform(), TimeProvider.System)
    {
    }

    internal WindowsScreenshotProvider(
        string directory,
        IScreenshotPlatform platform,
        TimeProvider time)
    {
        _directory = Path.GetFullPath(directory);
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));
        _time = time ?? throw new ArgumentNullException(nameof(time));
        Directory.CreateDirectory(_directory);
        if (new DirectoryInfo(_directory).LinkTarget is not null)
            throw new IOException("Capture directory cannot be a link.");
    }

    public ValueTask<CaptureResult> CaptureAsync(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        return ValueTask.FromResult(CaptureAndStore(_platform.CaptureVirtualScreen()));
    }

    public ValueTask<CaptureResult> CaptureActiveWindowAsync(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        return ValueTask.FromResult(CaptureAndStore(_platform.CaptureActiveWindow()));
    }

    private CaptureResult CaptureAndStore(ScreenshotFrame frame)
    {
        if (frame.Width is < 1 or > 32_768 || frame.Height is < 1 or > 32_768
            || frame.BgraBottomUp.Length != checked(frame.Width * frame.Height * 4))
            throw new IOException("Screenshot frame is invalid.");
        byte[] bmp = EncodeBmp(frame);
        string hash = Convert.ToHexStringLower(SHA256.HashData(bmp));
        string id = "capture_" + Guid.NewGuid().ToString("N");
        string final = Path.Combine(_directory, id + ".bmp");
        string temporary = Path.Combine(_directory, "." + id + ".tmp");
        try
        {
            using (var stream = new FileStream(
                temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None,
                4096, FileOptions.WriteThrough))
            {
                stream.Write(bmp); stream.Flush(flushToDisk: true);
            }
            File.Move(temporary, final);
        }
        finally
        {
            if (File.Exists(temporary)) File.Delete(temporary);
        }
        if (!File.Exists(final)
            || !string.Equals(Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(final))),
                hash, StringComparison.Ordinal)) throw new IOException("Screenshot verification failed.");
        return new CaptureResult(id, frame.Width, frame.Height, hash, _time.GetUtcNow());
    }

    private static byte[] EncodeBmp(ScreenshotFrame frame)
    {
        const int header = 14 + 40;
        byte[] result = new byte[checked(header + frame.BgraBottomUp.Length)];
        result[0] = (byte)'B'; result[1] = (byte)'M';
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(2), result.Length);
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(10), header);
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(14), 40);
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(18), frame.Width);
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(22), frame.Height);
        BinaryPrimitives.WriteInt16LittleEndian(result.AsSpan(26), 1);
        BinaryPrimitives.WriteInt16LittleEndian(result.AsSpan(28), 32);
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(34), frame.BgraBottomUp.Length);
        frame.BgraBottomUp.CopyTo(result, header);
        return result;
    }
}

internal sealed partial class GdiScreenshotPlatform : IScreenshotPlatform
{
    public ScreenshotFrame CaptureVirtualScreen()
    {
        int x = GetSystemMetrics(76), y = GetSystemMetrics(77);
        int width = GetSystemMetrics(78), height = GetSystemMetrics(79);
        return CaptureRegion(x, y, width, height);
    }

    public ScreenshotFrame CaptureActiveWindow()
    {
        nint window = GetForegroundWindow();
        if (window == 0) throw new IOException("Active window unavailable.");
        Rectangle rectangle;
        if (DwmGetWindowAttribute(window, 9, out rectangle,
                Marshal.SizeOf<Rectangle>()) != 0
            && !GetWindowRect(window, out rectangle))
            throw new IOException("Active window bounds unavailable.");
        int screenLeft = GetSystemMetrics(76), screenTop = GetSystemMetrics(77);
        int screenRight = checked(screenLeft + GetSystemMetrics(78));
        int screenBottom = checked(screenTop + GetSystemMetrics(79));
        int left = Math.Max(rectangle.Left, screenLeft);
        int top = Math.Max(rectangle.Top, screenTop);
        int right = Math.Min(rectangle.Right, screenRight);
        int bottom = Math.Min(rectangle.Bottom, screenBottom);
        if (right <= left || bottom <= top)
            throw new IOException("Active window is outside the visible desktop.");
        return CaptureRegion(left, top, right - left, bottom - top);
    }

    private static ScreenshotFrame CaptureRegion(int x, int y, int width, int height)
    {
        nint screen = GetDC(0);
        if (screen == 0) throw new IOException("Screen DC unavailable.");
        nint memory = 0, bitmap = 0, previous = 0;
        try
        {
            memory = CreateCompatibleDC(screen);
            bitmap = CreateCompatibleBitmap(screen, width, height);
            if (memory == 0 || bitmap == 0) throw new IOException("Screenshot allocation failed.");
            previous = SelectObject(memory, bitmap);
            if (previous == 0 || !BitBlt(memory, 0, 0, width, height, screen, x, y, 0x40CC0020))
                throw new IOException("Screenshot copy failed.");
            var info = new BitmapInfo
            {
                Header = new BitmapInfoHeader
                {
                    Size = (uint)Marshal.SizeOf<BitmapInfoHeader>(),
                    Width = width,
                    Height = height,
                    Planes = 1,
                    BitCount = 32,
                    Compression = 0,
                }
            };
            byte[] pixels = new byte[checked(width * height * 4)];
            if (GetDIBits(memory, bitmap, 0, (uint)height, pixels, ref info, 0) != height)
                throw new IOException("Screenshot pixels unavailable.");
            return new ScreenshotFrame(width, height, pixels);
        }
        finally
        {
            if (previous != 0 && memory != 0) _ = SelectObject(memory, previous);
            if (bitmap != 0) _ = DeleteObject(bitmap);
            if (memory != 0) _ = DeleteDC(memory);
            _ = ReleaseDC(0, screen);
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct BitmapInfoHeader
    {
        public uint Size;
        public int Width;
        public int Height;
        public ushort Planes;
        public ushort BitCount;
        public uint Compression;
        public uint SizeImage;
        public int XPelsPerMeter;
        public int YPelsPerMeter;
        public uint ClrUsed;
        public uint ClrImportant;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct BitmapInfo
    {
        public BitmapInfoHeader Header;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Rectangle
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [LibraryImport("user32.dll")]
    private static partial int GetSystemMetrics(int index);

    [LibraryImport("user32.dll")]
    private static partial nint GetForegroundWindow();

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetWindowRect(nint window, out Rectangle rectangle);

    [LibraryImport("dwmapi.dll")]
    private static partial int DwmGetWindowAttribute(
        nint window, int attribute, out Rectangle value, int valueSize);

    [LibraryImport("user32.dll")]
    private static partial nint GetDC(nint window);

    [LibraryImport("user32.dll")]
    private static partial int ReleaseDC(nint window, nint dc);

    [LibraryImport("gdi32.dll")]
    private static partial nint CreateCompatibleDC(nint dc);

    [LibraryImport("gdi32.dll")]
    private static partial nint CreateCompatibleBitmap(
        nint dc,
        int width,
        int height);

    [LibraryImport("gdi32.dll")]
    private static partial nint SelectObject(nint dc, nint value);

    [LibraryImport("gdi32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool BitBlt(
        nint dest,
        int x,
        int y,
        int width,
        int height,
        nint source,
        int sx,
        int sy,
        uint operation);

    [LibraryImport("gdi32.dll")]
    private static partial int GetDIBits(
        nint dc,
        nint bitmap,
        uint start,
        uint lines,
        [Out] byte[] bits,
        ref BitmapInfo info,
        uint usage);

    [LibraryImport("gdi32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool DeleteObject(nint value);

    [LibraryImport("gdi32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool DeleteDC(nint dc);
}
