using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Capture;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class CaptureHandlerTests
{
    [Test]
    public async Task HandlerProjectsOpaqueVerifiedMetadataWithoutPath()
    {
        var handler = new ScreenshotCaptureHandler(new StubProvider());
        OperationOutcome outcome = await handler.ExecuteAsync(
            default!, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(outcome.Result!.Value.GetProperty("captureId").GetString(),
                Is.EqualTo("capture_0123456789abcdef0123456789abcdef"));
            Assert.That(outcome.Result.Value.TryGetProperty("path", out _), Is.False);
            Assert.That(outcome.Result.Value.TryGetProperty("activeWindow", out _), Is.False);
            Assert.That(handler.Definition.Risk, Is.EqualTo(OperationRisk.Sensitive));
        });
    }

    [Test]
    public async Task ActiveWindowHandlerProjectsIdentityTimeAndClippingFromProvider()
    {
        var provenance = new ActiveWindowCaptureProvenance(
            123, 456, DateTimeOffset.UnixEpoch.AddTicks(123),
            new CaptureBounds(-20, 30, 1940, 1080), new CaptureBounds(0, 30, 1920, 1080),
            DateTimeOffset.UnixEpoch.AddSeconds(1), DateTimeOffset.UnixEpoch.AddSeconds(2));
        var handler = new ScreenshotCaptureHandler(new StubProvider(provenance), "capture.active.window", true);

        OperationOutcome outcome = await handler.ExecuteAsync(default!, CancellationToken.None);
        var result = outcome.Result!.Value;
        var window = result.GetProperty("activeWindow");

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(result.GetProperty("scope").GetString(), Is.EqualTo("active_window"));
            Assert.That(window.GetProperty("windowHandle").GetInt64(), Is.EqualTo(provenance.WindowHandle));
            Assert.That(window.GetProperty("processId").GetUInt32(), Is.EqualTo(provenance.ProcessId));
            Assert.That(window.GetProperty("processCreatedAtUtc").GetDateTimeOffset(), Is.EqualTo(provenance.ProcessCreatedAtUtc));
            Assert.That(window.GetProperty("windowBounds").GetProperty("left").GetInt32(), Is.EqualTo(-20));
            Assert.That(window.GetProperty("windowBounds").GetProperty("width").GetInt32(), Is.EqualTo(1940));
            Assert.That(window.GetProperty("captureBounds").GetProperty("left").GetInt32(), Is.Zero);
            Assert.That(window.GetProperty("captureBounds").GetProperty("top").GetInt32(), Is.EqualTo(30));
            Assert.That(window.GetProperty("captureBounds").GetProperty("width").GetInt32(), Is.EqualTo(1920));
            Assert.That(window.GetProperty("captureBounds").GetProperty("height").GetInt32(), Is.EqualTo(1080));
            Assert.That(window.GetProperty("isClipped").GetBoolean(), Is.True);
            Assert.That(window.GetProperty("captureStartedAtUtc").GetDateTimeOffset(), Is.EqualTo(provenance.CaptureStartedAtUtc));
            Assert.That(window.GetProperty("captureCompletedAtUtc").GetDateTimeOffset(), Is.EqualTo(provenance.CaptureCompletedAtUtc));
        });
    }

    // 2026-09-28: the provider's IOException escaped the handler and ended
    // baxy-core (Steam's helper window, parked off-screen, held the foreground).
    // A capture that cannot be taken is a failed operation with its reason.
    [TestCase(true, "unavailable", "active_window_not_visible")]
    [TestCase(true, "io", "active_window_capture_failed")]
    [TestCase(true, "access", "active_window_capture_failed")]
    [TestCase(false, "io", "screen_capture_failed")]
    public async Task CaptureThatCannotBeTakenIsAFailedOperationNotACoreFault(
        bool activeWindow, string failure, string expectedError)
    {
        Exception exception = failure switch
        {
            "unavailable" => new ScreenshotUnavailableException(
                "active_window_not_visible", "Active window is outside the visible desktop."),
            "io" => new IOException("Screenshot copy failed."),
            "access" => new UnauthorizedAccessException("Capture directory denied."),
            _ => throw new ArgumentOutOfRangeException(nameof(failure)),
        };
        var handler = activeWindow
            ? new ScreenshotCaptureHandler(new FailingProvider(exception), "capture.active.window", true)
            : new ScreenshotCaptureHandler(new FailingProvider(exception));

        OperationOutcome outcome = await handler.ExecuteAsync(default!, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.Verified, Is.False);
            Assert.That(outcome.Retryable, Is.False);
            Assert.That(outcome.EffectMayHaveOccurred, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo(expectedError));
            Assert.That(outcome.Result, Is.Null);
        });
    }

    // Ronda 22 (uso real r18 t3-c11 «hazme una captura de pantalla y guárdala en el escritorio porfa»): the folder
    // asked reaches the provider and the receipt says where the verified copy is (the folder's key and the file's
    // name, never a path).
    [TestCase("capture.screenshot", false)]
    [TestCase("capture.active.window", true)]
    public async Task AFolderAskedSavesAVerifiedCopyAndTheReceiptSaysWhere(string operation, bool activeWindow)
    {
        var provider = new StubProvider();
        var handler = new ScreenshotCaptureHandler(provider, operation, activeWindow);

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("""{"folder":"desktop"}"""), CancellationToken.None);
        JsonElement result = outcome.Result!.Value;

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(provider.Saved, Is.EqualTo(new[] { ("capture_0123456789abcdef0123456789abcdef", "desktop") }));
            Assert.That(result.GetProperty("savedFolder").GetString(), Is.EqualTo("desktop"));
            Assert.That(result.GetProperty("fileName").GetString(), Is.EqualTo("Screenshot 1970-01-01 000000.png"));
            Assert.That(result.TryGetProperty("path", out _), Is.False);
        });
    }

    // Contracaso: «hazme una captura y dime qué ves», «sacale un screenshot a la pantalla» carry no folder; the capture
    // stays private and no copy is written.
    [TestCase("{}")]
    [TestCase(null)]
    public async Task WithoutAFolderTheCaptureStaysPrivateAndNothingIsSaved(string? arguments)
    {
        var provider = new StubProvider();
        var handler = new ScreenshotCaptureHandler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(
            arguments is null ? default! : Invocation(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True);
            Assert.That(provider.Saved, Is.Empty);
            Assert.That(outcome.Result!.Value.TryGetProperty("savedFolder", out _), Is.False);
            Assert.That(outcome.Result.Value.TryGetProperty("fileName", out _), Is.False);
        });
    }

    // A copy that could not be saved is the request's failure, never a capture told as kept.
    [TestCase("io", "capture_save_failed")]
    [TestCase("unavailable", "capture_folder_unavailable")]
    public async Task ACopyThatCannotBeSavedIsAFailedOperation(string failure, string expectedError)
    {
        var provider = new StubProvider(saveFailure: failure == "io"
            ? new IOException("Saved capture verification failed.")
            : new ScreenshotUnavailableException("capture_folder_unavailable", "The known folder is not available."));
        var handler = new ScreenshotCaptureHandler(provider);

        OperationOutcome outcome = await handler.ExecuteAsync(Invocation("""{"folder":"pictures"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo(expectedError));
            Assert.That(outcome.Result, Is.Null);
        });
    }

    private static OperationInvocation Invocation(string arguments)
    {
        using JsonDocument document = JsonDocument.Parse(arguments);
        return new OperationInvocation("request", "mission", "invocation", document.RootElement.Clone());
    }

    private sealed class FailingProvider(Exception failure) : IScreenshotProvider
    {
        public ValueTask<CaptureResult> CaptureAsync(CancellationToken cancellationToken) =>
            ValueTask.FromException<CaptureResult>(failure);

        public ValueTask<CaptureResult> CaptureActiveWindowAsync(CancellationToken cancellationToken) =>
            throw failure;
    }

    private sealed class StubProvider(
        ActiveWindowCaptureProvenance? activeWindow = null,
        Exception? saveFailure = null) : IScreenshotProvider
    {
        public List<(string CaptureId, string Folder)> Saved { get; } = [];

        public ValueTask<SavedCaptureCopy> SaveCopyAsync(string captureId, string folder, CancellationToken cancellationToken)
        {
            if (saveFailure is not null)
                throw saveFailure;
            Saved.Add((captureId, folder));
            return ValueTask.FromResult(new SavedCaptureCopy(folder, "Screenshot 1970-01-01 000000.png", new string('b', 64)));
        }

        public ValueTask<CaptureResult> CaptureAsync(CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(new CaptureResult(
                "capture_0123456789abcdef0123456789abcdef", 1920, 1080,
                new string('a', 64), DateTimeOffset.UnixEpoch));
        }

        public ValueTask<CaptureResult> CaptureActiveWindowAsync(
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(new CaptureResult(
                "capture_0123456789abcdef0123456789abcdef", 1920, 1080,
                new string('a', 64), DateTimeOffset.UnixEpoch, activeWindow));
        }
    }
}
