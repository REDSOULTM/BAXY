using System.Globalization;
using System.Security.Cryptography;
using Baxy.Providers.Windows.Capture;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class WindowsScreenshotProviderTests
{
    [Test]
    public async Task CaptureStoresVerifiedBmpAndReturnsOnlyOpaqueIdentity()
    {
        using TemporaryDirectory temporary = new();
        var provider = new WindowsScreenshotProvider(
            temporary.Path,
            new FakePlatform(),
            new FixedTimeProvider());

        CaptureResult result = await provider.CaptureAsync(CancellationToken.None);
        string file = Directory.GetFiles(temporary.Path, "*.bmp").Single();
        byte[] bytes = File.ReadAllBytes(file);

        Assert.Multiple(() =>
        {
            Assert.That(result.CaptureId, Does.Match("^capture_[0-9a-f]{32}$"));
            Assert.That((result.Width, result.Height), Is.EqualTo((2, 1)));
            Assert.That(bytes[0], Is.EqualTo((byte)'B'));
            Assert.That(bytes[1], Is.EqualTo((byte)'M'));
            Assert.That(Convert.ToHexStringLower(SHA256.HashData(bytes)), Is.EqualTo(result.Sha256));
        });
    }

    private sealed class FakePlatform : IScreenshotPlatform
    {
        public ScreenshotFrame CaptureVirtualScreen() => new(2, 1,
            [0, 0, 255, 255, 0, 255, 0, 255]);
        public ScreenshotFrame CaptureActiveWindow() => new(1, 1, [0, 0, 255, 255]);
    }
    private sealed class FixedTimeProvider : TimeProvider
    {
        public override DateTimeOffset GetUtcNow() => DateTimeOffset.UnixEpoch;
    }
    private sealed class TemporaryDirectory : IDisposable
    {
        public TemporaryDirectory()
        {
            Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-capture-tests",
                Guid.NewGuid().ToString("N", CultureInfo.InvariantCulture)); Directory.CreateDirectory(Path);
        }
        public string Path { get; }
        public void Dispose() { if (Directory.Exists(Path)) Directory.Delete(Path, recursive: true); }
    }
}
