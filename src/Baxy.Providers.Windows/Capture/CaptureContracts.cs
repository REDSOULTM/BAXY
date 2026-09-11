namespace Baxy.Providers.Windows.Capture;

public sealed record CaptureResult(
    string CaptureId,
    int Width,
    int Height,
    string Sha256,
    DateTimeOffset CreatedAtUtc,
    ActiveWindowCaptureProvenance? ActiveWindow = null);

// Bounds are in screen pixels; CaptureBounds maps the image origin into that space.
public sealed record CaptureBounds(int Left, int Top, int Width, int Height);

public sealed record ActiveWindowCaptureProvenance(
    long WindowHandle,
    uint ProcessId,
    DateTimeOffset ProcessCreatedAtUtc,
    CaptureBounds WindowBounds,
    CaptureBounds CaptureBounds,
    DateTimeOffset CaptureStartedAtUtc,
    DateTimeOffset CaptureCompletedAtUtc)
{
    public bool IsClipped => WindowBounds != CaptureBounds;
}

public interface IScreenshotProvider
{
    ValueTask<CaptureResult> CaptureAsync(CancellationToken cancellationToken);
    ValueTask<CaptureResult> CaptureActiveWindowAsync(CancellationToken cancellationToken);
}

internal sealed record ScreenshotFrame(
    int Width, int Height, byte[] BgraBottomUp,
    ActiveWindowCaptureProvenance? ActiveWindow = null);

internal sealed record ActiveWindowSnapshot(
    long WindowHandle, uint ProcessId, DateTimeOffset ProcessCreatedAtUtc,
    CaptureBounds WindowBounds, CaptureBounds DesktopBounds);

internal interface IScreenshotPlatform
{
    ScreenshotFrame CaptureVirtualScreen();
    ScreenshotFrame CaptureActiveWindow();
}
