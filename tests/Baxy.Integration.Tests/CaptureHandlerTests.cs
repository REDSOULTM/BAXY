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

    private sealed class StubProvider(ActiveWindowCaptureProvenance? activeWindow = null) : IScreenshotProvider
    {
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
