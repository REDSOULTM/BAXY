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
            Assert.That(result.ActiveWindow, Is.Null);
        });
    }

    [TestCase(false)]
    [TestCase(true)]
    public async Task ActiveWindowPreservesVerifiedIdentityCaptureIntervalAndCrop(bool clipped)
    {
        using TemporaryDirectory temporary = new();
        ActiveWindowSnapshot snapshot = Snapshot() with
        {
            WindowBounds = new CaptureBounds(clipped ? -1 : 0, 0, 2, 2),
        };
        CaptureBounds? capturedBounds = null;
        var time = new AdvancingTimeProvider();
        var platform = new GdiScreenshotPlatform(() => snapshot, bounds =>
        {
            capturedBounds = bounds;
            return new ScreenshotFrame(bounds.Width, bounds.Height, new byte[bounds.Width * bounds.Height * 4]);
        }, time);
        var provider = new WindowsScreenshotProvider(temporary.Path, platform, time);

        CaptureResult result = await provider.CaptureActiveWindowAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.ActiveWindow, Is.Not.Null);
            Assert.That(result.ActiveWindow!.WindowHandle, Is.EqualTo(snapshot.WindowHandle));
            Assert.That(result.ActiveWindow.ProcessId, Is.EqualTo(snapshot.ProcessId));
            Assert.That(result.ActiveWindow.ProcessCreatedAtUtc, Is.EqualTo(snapshot.ProcessCreatedAtUtc));
            Assert.That(result.ActiveWindow.WindowBounds, Is.EqualTo(snapshot.WindowBounds));
            Assert.That(result.ActiveWindow.CaptureBounds, Is.EqualTo(capturedBounds));
            Assert.That(capturedBounds, Is.EqualTo(new CaptureBounds(0, 0, clipped ? 1 : 2, 2)));
            Assert.That(result.ActiveWindow.IsClipped, Is.EqualTo(clipped));
            Assert.That(result.ActiveWindow.CaptureStartedAtUtc, Is.EqualTo(DateTimeOffset.UnixEpoch));
            Assert.That(result.ActiveWindow.CaptureCompletedAtUtc, Is.EqualTo(DateTimeOffset.UnixEpoch.AddSeconds(1)));
            Assert.That(result.CreatedAtUtc, Is.EqualTo(DateTimeOffset.UnixEpoch.AddSeconds(2)));
            Assert.That((result.Width, result.Height), Is.EqualTo((capturedBounds!.Width, capturedBounds.Height)));
            Assert.That(Directory.GetFiles(temporary.Path, "*.bmp"), Has.Length.EqualTo(1));
        });
    }

    [TestCase("focus")]
    [TestCase("pid")]
    [TestCase("creation")]
    [TestCase("position")]
    [TestCase("size")]
    [TestCase("desktop")]
    public void ActiveWindowChangedDuringCaptureDoesNotStoreStaleFrame(string change)
    {
        using TemporaryDirectory temporary = new();
        ActiveWindowSnapshot before = Snapshot();
        ActiveWindowSnapshot after = change switch
        {
            "focus" => before with { WindowHandle = 789 },
            "pid" => before with { ProcessId = 987 },
            "creation" => before with { ProcessCreatedAtUtc = before.ProcessCreatedAtUtc.AddTicks(1) },
            "position" => before with { WindowBounds = before.WindowBounds with { Left = 1 } },
            "size" => before with { WindowBounds = before.WindowBounds with { Width = 3 } },
            "desktop" => before with { DesktopBounds = before.DesktopBounds with { Width = 3 } },
            _ => throw new ArgumentOutOfRangeException(nameof(change)),
        };
        int observations = 0;
        bool copied = false;
        var platform = new GdiScreenshotPlatform(() => ++observations == 1 ? before : after, bounds =>
        {
            Assert.That(observations, Is.EqualTo(1));
            copied = true;
            return new ScreenshotFrame(bounds.Width, bounds.Height, new byte[bounds.Width * bounds.Height * 4]);
        }, new FixedTimeProvider());
        var provider = new WindowsScreenshotProvider(temporary.Path, platform, new FixedTimeProvider());

        Assert.ThrowsAsync<IOException>(async () => await provider.CaptureActiveWindowAsync(CancellationToken.None));
        Assert.Multiple(() =>
        {
            Assert.That(copied, Is.True);
            Assert.That(observations, Is.EqualTo(2));
            Assert.That(Directory.GetFiles(temporary.Path), Is.Empty);
        });
    }

    [TestCase(1)]
    [TestCase(2)]
    public void UnavailableWindowIdentityFailsWithoutStoringImage(int failingObservation)
    {
        using TemporaryDirectory temporary = new();
        int observations = 0, copies = 0;
        var platform = new GdiScreenshotPlatform(() => ++observations == failingObservation
            ? throw new IOException("Process identity unavailable.") : Snapshot(), bounds =>
        {
            copies++;
            return new ScreenshotFrame(bounds.Width, bounds.Height, new byte[bounds.Width * bounds.Height * 4]);
        }, new FixedTimeProvider());
        var provider = new WindowsScreenshotProvider(temporary.Path, platform, new FixedTimeProvider());

        Assert.ThrowsAsync<IOException>(async () => await provider.CaptureActiveWindowAsync(CancellationToken.None));
        Assert.That(copies, Is.EqualTo(failingObservation - 1));
        Assert.That(Directory.GetFiles(temporary.Path), Is.Empty);
    }

    private static ActiveWindowSnapshot Snapshot() => new(
        123, 456, DateTimeOffset.UnixEpoch.AddTicks(123),
        new CaptureBounds(0, 0, 2, 2), new CaptureBounds(0, 0, 2, 2));

    private sealed class AdvancingTimeProvider : TimeProvider
    {
        private int _seconds;
        public override DateTimeOffset GetUtcNow() => DateTimeOffset.UnixEpoch.AddSeconds(_seconds++);
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
