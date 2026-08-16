namespace Baxy.Providers.Windows.Capture;

public sealed record CaptureResult(
    string CaptureId,
    int Width,
    int Height,
    string Sha256,
    DateTimeOffset CreatedAtUtc);

public interface IScreenshotProvider
{
    ValueTask<CaptureResult> CaptureAsync(CancellationToken cancellationToken);
    ValueTask<CaptureResult> CaptureActiveWindowAsync(CancellationToken cancellationToken);
}

internal sealed record ScreenshotFrame(int Width, int Height, byte[] BgraBottomUp);

internal interface IScreenshotPlatform
{
    ScreenshotFrame CaptureVirtualScreen();
    ScreenshotFrame CaptureActiveWindow();
}
