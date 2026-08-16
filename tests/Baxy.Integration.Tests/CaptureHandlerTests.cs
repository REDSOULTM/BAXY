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
            Assert.That(handler.Definition.Risk, Is.EqualTo(OperationRisk.Sensitive));
        });
    }

    private sealed class StubProvider : IScreenshotProvider
    {
        public ValueTask<CaptureResult> CaptureAsync(CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(new CaptureResult(
                "capture_0123456789abcdef0123456789abcdef", 1920, 1080,
                new string('a', 64), DateTimeOffset.UnixEpoch));
        }

        public ValueTask<CaptureResult> CaptureActiveWindowAsync(
            CancellationToken cancellationToken) => CaptureAsync(cancellationToken);
    }
}
