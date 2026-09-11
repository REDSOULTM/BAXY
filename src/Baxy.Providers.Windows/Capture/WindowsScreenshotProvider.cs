using System.Buffers.Binary;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using Microsoft.Win32.SafeHandles;

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
        return new CaptureResult(id, frame.Width, frame.Height, hash, _time.GetUtcNow(), frame.ActiveWindow);
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
    private readonly Func<ActiveWindowSnapshot> _observeActiveWindow;
    private readonly Func<CaptureBounds, ScreenshotFrame> _captureRegion;
    private readonly Func<CaptureBounds> _readDesktopBounds;
    private readonly Func<nint, nint> _setThreadDpiContext;
    private readonly TimeProvider _time;

    public GdiScreenshotPlatform()
        : this(ObserveActiveWindow, bounds => CaptureRegion(
            bounds.Left, bounds.Top, bounds.Width, bounds.Height), TimeProvider.System)
    {
    }

    internal GdiScreenshotPlatform(
        Func<ActiveWindowSnapshot> observeActiveWindow,
        Func<CaptureBounds, ScreenshotFrame> captureRegion,
        TimeProvider time,
        Func<nint, nint>? setThreadDpiContext = null,
        Func<CaptureBounds>? readDesktopBounds = null)
    {
        _observeActiveWindow = observeActiveWindow;
        _captureRegion = captureRegion;
        _time = time;
        _setThreadDpiContext = setThreadDpiContext ?? SetThreadDpiAwarenessContext;
        _readDesktopBounds = readDesktopBounds ?? ReadDesktopBounds;
    }

    public ScreenshotFrame CaptureVirtualScreen() => CaptureInPhysicalPixels(
        () => _captureRegion(_readDesktopBounds()));

    public ScreenshotFrame CaptureActiveWindow() => CaptureInPhysicalPixels(CaptureActiveWindowCore);

    private ScreenshotFrame CaptureInPhysicalPixels(Func<ScreenshotFrame> capture)
    {
        // DWM bounds are physical pixels. Keep metrics, fallback bounds and GDI in
        // that same coordinate space, on this synchronous thread only.
        nint previous = _setThreadDpiContext((nint)(-4));
        if (previous == 0) throw new IOException("Screenshot DPI context unavailable.");
        ScreenshotFrame frame;
        nint restored;
        try
        {
            frame = capture();
        }
        finally
        {
            restored = _setThreadDpiContext(previous);
        }
        if (restored == 0) throw new IOException("Screenshot DPI context restoration failed.");
        return frame;
    }

    private ScreenshotFrame CaptureActiveWindowCore()
    {
        DateTimeOffset started = _time.GetUtcNow();
        ActiveWindowSnapshot before = _observeActiveWindow();
        if (before.WindowHandle == 0 || before.ProcessId == 0
            || before.ProcessCreatedAtUtc <= DateTimeOffset.FromFileTime(0))
            throw new IOException("Active window identity unavailable.");
        CaptureBounds window = before.WindowBounds, screen = before.DesktopBounds;
        int left = Math.Max(window.Left, screen.Left);
        int top = Math.Max(window.Top, screen.Top);
        int right = Math.Min(checked(window.Left + window.Width), checked(screen.Left + screen.Width));
        int bottom = Math.Min(checked(window.Top + window.Height), checked(screen.Top + screen.Height));
        if (right <= left || bottom <= top)
            throw new IOException("Active window is outside the visible desktop.");
        var crop = new CaptureBounds(left, top, right - left, bottom - top);
        ScreenshotFrame frame = _captureRegion(crop);
        ActiveWindowSnapshot after = _observeActiveWindow();
        if (before != after)
            throw new IOException("Active window identity, focus or bounds changed during capture.");
        if (frame.Width != crop.Width || frame.Height != crop.Height)
            throw new IOException("Active window capture dimensions do not match its bounds.");
        return frame with
        {
            ActiveWindow = new ActiveWindowCaptureProvenance(
                before.WindowHandle, before.ProcessId, before.ProcessCreatedAtUtc,
                window, crop, started, _time.GetUtcNow()),
        };
    }

    private static ActiveWindowSnapshot ObserveActiveWindow()
    {
        nint window = GetForegroundWindow();
        if (window == 0) throw new IOException("Active window unavailable.");
        if (GetWindowThreadProcessId(window, out uint processId) == 0 || processId == 0)
            throw new IOException("Active window process unavailable.");
        using SafeProcessHandle process = OpenProcess(0x1000, false, processId);
        if (process.IsInvalid || !GetProcessTimes(process, out long created, out _, out _, out _)
            || created <= 0)
            throw new IOException("Active window process creation identity unavailable.");
        Rectangle rectangle;
        if (DwmGetWindowAttribute(window, 9, out rectangle,
                Marshal.SizeOf<Rectangle>()) != 0
            && !GetWindowRect(window, out rectangle))
            throw new IOException("Active window bounds unavailable.");
        var bounds = new CaptureBounds(rectangle.Left, rectangle.Top,
            checked(rectangle.Right - rectangle.Left), checked(rectangle.Bottom - rectangle.Top));
        CaptureBounds desktop = ReadDesktopBounds();
        if (GetForegroundWindow() != window
            || GetWindowThreadProcessId(window, out uint finalProcessId) == 0 || finalProcessId != processId)
            throw new IOException("Active window changed while observing its identity.");
        return new ActiveWindowSnapshot((long)window, processId, DateTimeOffset.FromFileTime(created),
            bounds, desktop);
    }

    private static CaptureBounds ReadDesktopBounds() => new(
        GetSystemMetrics(76), GetSystemMetrics(77), GetSystemMetrics(78), GetSystemMetrics(79));

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
    private static partial nint SetThreadDpiAwarenessContext(nint context);

    [LibraryImport("user32.dll")]
    private static partial nint GetForegroundWindow();

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint window, out uint processId);

    [LibraryImport("kernel32.dll")]
    private static partial SafeProcessHandle OpenProcess(
        uint desiredAccess, [MarshalAs(UnmanagedType.Bool)] bool inheritHandle, uint processId);

    [LibraryImport("kernel32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetProcessTimes(
        SafeProcessHandle process, out long creationTime, out long exitTime,
        out long kernelTime, out long userTime);

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
