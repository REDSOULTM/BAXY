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

/// <summary>
/// The active window is not on the visible desktop (minimized, or parked
/// off-screen like Steam's helper window). An honest capture failure with a
/// reason the person can act on; still an <see cref="IOException"/> for callers
/// that only need "no image was stored".
/// </summary>
public sealed class ScreenshotUnavailableException(string code, string message) : IOException(message)
{
    public string Code { get; } = code;

    /// <summary>Encargo 17 (U23): the facts the failure carries for the model (a copy's folder that is not there:
    /// CaptureCopies.MissingFolder); null when the code says it all.</summary>
    public System.Text.Json.JsonElement? Result { get; init; }
}

/// <summary>Captures fail with <see cref="IOException"/> and never store a partial image.</summary>
public interface IScreenshotProvider
{
    ValueTask<CaptureResult> CaptureAsync(CancellationToken cancellationToken);
    ValueTask<CaptureResult> CaptureActiveWindowAsync(CancellationToken cancellationToken);

    /// <summary>Ronda 22: saves a verified PNG copy of the capture just taken into the known folder named
    /// (desktop, documents, downloads, pictures), under a new dated name. A provider that cannot keep copies says so.</summary>
    ValueTask<SavedCaptureCopy> SaveCopyAsync(string captureId, string folder, CancellationToken cancellationToken) =>
        throw new NotSupportedException("This capture provider does not save copies.");

    /// <summary>Banco de uso 03-11 (U23): the same copy into a folder of the person's given by its path, as a file
    /// tool's path is read (PersonFolders.Place, inside <paramref name="labels"/>); a folder that is not there is never
    /// made.</summary>
    ValueTask<SavedCaptureCopy> SaveCopyAtAsync(
        string captureId, string path, IReadOnlyCollection<string> labels, CancellationToken cancellationToken) =>
        throw new NotSupportedException("This capture provider does not save copies.");
}

// A window image held in memory only: a 32-bit bottom-up BMP and its SHA-256.
internal sealed record WindowImage(int Width, int Height, byte[] Bmp, string Sha256);

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
