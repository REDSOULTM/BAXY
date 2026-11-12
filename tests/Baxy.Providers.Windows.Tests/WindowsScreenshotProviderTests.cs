using System.Globalization;
using System.Security.Cryptography;
using Baxy.Providers.Windows.Capture;
using Baxy.Providers.Windows.External;
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

    // Auditoría de estabilidad r19, hallazgo 4: the private capture folder kept every bitmap. A new capture removes
    // the oldest beyond the cap and nothing else in the folder.
    [Test]
    public async Task StoringACaptureRemovesTheOldestBeyondTheCapOnly()
    {
        using TemporaryDirectory temporary = new();
        DateTime now = DateTime.UtcNow;
        // PRV1 (PRIV-02): a provider that starts removes what an earlier run left, so these are of this run.
        var provider = new WindowsScreenshotProvider(temporary.Path, new FakePlatform(), new FixedTimeProvider());
        string[] seeded = Enumerable.Range(0, 20)
            .Select(index => Seed(temporary.Path, index, now.AddHours(index - 20)))
            .ToArray();
        string diagnostic = Path.Combine(temporary.Path, "streaming-playback-rejections.jsonl");
        File.WriteAllText(diagnostic, "{}\n");
        File.SetLastWriteTimeUtc(diagnostic, now.AddDays(-30));

        CaptureResult result = await provider.CaptureAsync(CancellationToken.None);

        string[] left = Directory.GetFiles(temporary.Path, "capture_*.bmp");
        Assert.Multiple(() =>
        {
            Assert.That(left, Has.Length.EqualTo(WindowsScreenshotProvider.RetainedCaptures));
            Assert.That(File.Exists(Path.Combine(temporary.Path, result.CaptureId + ".bmp")), Is.True);
            Assert.That(seeded.Take(5).Any(File.Exists), Is.False);
            Assert.That(seeded.Skip(5).All(File.Exists), Is.True);
            Assert.That(File.Exists(diagnostic), Is.True);
        });
    }

    [Test]
    public async Task StoringACaptureBelowTheCapKeepsEveryEarlierCapture()
    {
        using TemporaryDirectory temporary = new();
        DateTime now = DateTime.UtcNow;
        var provider = new WindowsScreenshotProvider(temporary.Path, new FakePlatform(), new FixedTimeProvider());
        string[] seeded = Enumerable.Range(0, 3)
            .Select(index => Seed(temporary.Path, index, now.AddDays(index - 40)))
            .ToArray();

        await provider.CaptureAsync(CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(seeded.All(File.Exists), Is.True);
            Assert.That(Directory.GetFiles(temporary.Path, "capture_*.bmp"), Has.Length.EqualTo(4));
        });
    }

    // PRV1 (revisión de privacidad 2026-11-09, PRIV-02): up to 16 whole screens stayed in the folder from one run of
    // BAXY to the next. What an earlier run left goes when the engine starts; nothing else in the folder does.
    [Test]
    public void AProviderThatStartsRemovesTheCapturesAnEarlierRunLeft()
    {
        using TemporaryDirectory temporary = new();
        string[] left = [.. Enumerable.Range(0, 3).Select(index => Seed(temporary.Path, index, DateTime.UtcNow.AddDays(-2)))];
        string unfinished = Path.Combine(temporary.Path, ".capture_" + Guid.NewGuid().ToString("N") + ".tmp");
        string diagnostic = Path.Combine(temporary.Path, "streaming-playback-rejections.jsonl");
        File.WriteAllText(unfinished, "x");
        File.WriteAllText(diagnostic, "{}\n");

        _ = new WindowsScreenshotProvider(temporary.Path, new FakePlatform(), new FixedTimeProvider());

        Assert.Multiple(() =>
        {
            Assert.That(left.Where(File.Exists), Is.Empty);
            Assert.That(File.Exists(unfinished), Is.False);
            Assert.That(File.Exists(diagnostic), Is.True);
        });
    }

    [Test]
    public void ClearingTheStoredCapturesSaysHowManyAReaderStillHolds()
    {
        using TemporaryDirectory temporary = new();
        string free = Seed(temporary.Path, 1, DateTime.UtcNow);
        string held = Seed(temporary.Path, 2, DateTime.UtcNow);
        string other = Path.Combine(temporary.Path, "notas.bmp");
        File.WriteAllText(other, "x");

        using (new FileStream(held, FileMode.Open, FileAccess.Read, FileShare.Read))
        {
            Assert.That(StoredCaptures.Clear(temporary.Path), Is.EqualTo(1));
            Assert.That(File.Exists(free), Is.False);
            Assert.That(File.Exists(held), Is.True);
        }

        Assert.Multiple(() =>
        {
            Assert.That(StoredCaptures.Clear(temporary.Path), Is.Zero);
            Assert.That(File.Exists(held), Is.False);
            Assert.That(File.Exists(other), Is.True);
            Assert.That(StoredCaptures.Clear(Path.Combine(temporary.Path, "no-esta")), Is.Zero);
        });
    }

    // Revisión a ciegas de PRV1 (PRIV-02): the note of a playback that was not verified stayed in this folder, in clear
    // text and without end, with the title the person asked for and the last address and page; deleting everything left
    // it. It is written only where the PC's owner asked for words to be kept, and deleting everything removes it.
    [Test]
    public void ThePlaybackNoteIsWrittenOnlyWhereWordsAreKeptAndGoesWhenEverythingIsDeleted()
    {
        using TemporaryDirectory temporary = new();
        var playback = new CdpStreamingPlaybackResult(false, false, "la casa del lago",
            "https://stream.example/search?q=la%20casa%20del%20lago", "Buscar: la casa del lago", "t1", 0,
            "playback_not_verified", "{\"profile\":\"Infantil\"}");
        string note = Path.Combine(temporary.Path, StoredCaptures.PlaybackNotes);
        string other = Path.Combine(temporary.Path, "notas.jsonl");
        File.WriteAllText(other, "x");

        WebBrowserAdapter.RecordStreamingRejection(temporary.Path, keepsWords: false, "la casa del lago", playback);
        Assert.That(File.Exists(note), Is.False, "the note was written where nobody asked for words to be kept");

        WebBrowserAdapter.RecordStreamingRejection(temporary.Path, keepsWords: true, "la casa del lago", playback);
        string capture = Seed(temporary.Path, 1, DateTime.UtcNow);
        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllText(note), Does.Contain("la casa del lago").And.Contain("playback_not_verified"));
            // The end of a request removes its captures alone.
            Assert.That(StoredCaptures.Clear(temporary.Path), Is.Zero);
            Assert.That(File.Exists(capture), Is.False);
            Assert.That(File.Exists(note), Is.True);
        });

        capture = Seed(temporary.Path, 2, DateTime.UtcNow);
        Assert.Multiple(() =>
        {
            Assert.That(StoredCaptures.ClearAll(temporary.Path), Is.Zero);
            Assert.That(File.Exists(capture), Is.False);
            Assert.That(File.Exists(note), Is.False, "the note of a playback stayed after everything was deleted");
            Assert.That(File.Exists(other), Is.True);
        });
    }

    private static string Seed(string directory, int index, DateTime writtenUtc)
    {
        string path = Path.Combine(directory, "capture_" + index.ToString("x32", CultureInfo.InvariantCulture) + ".bmp");
        File.WriteAllBytes(path, [(byte)'B', (byte)'M']);
        File.SetLastWriteTimeUtc(path, writtenUtc);
        return path;
    }

    // Computer use looks at windows it never keeps: the image held in memory is the stored capture, byte for byte and
    // hash for hash, so a click compares surfaces as before without writing, flushing and re-reading each one.
    [Test]
    public async Task AWindowImageInMemoryIsTheStoredCaptureWithoutTheFile()
    {
        using TemporaryDirectory temporary = new();
        var platform = new FakePlatform();
        var provider = new WindowsScreenshotProvider(temporary.Path, platform, new FixedTimeProvider());

        CaptureResult stored = await provider.CaptureAsync(CancellationToken.None);
        byte[] file = File.ReadAllBytes(Directory.GetFiles(temporary.Path, "*.bmp").Single());
        WindowImage image = WindowsScreenshotProvider.Image(platform.CaptureVirtualScreen());

        Assert.Multiple(() =>
        {
            Assert.That(image.Bmp, Is.EqualTo(file));
            Assert.That(image.Sha256, Is.EqualTo(stored.Sha256));
            Assert.That((image.Width, image.Height), Is.EqualTo((stored.Width, stored.Height)));
        });
    }

    [Test]
    public void AnInvalidFrameIsNoWindowImage()
    {
        Assert.Throws<IOException>(() => WindowsScreenshotProvider.Image(new ScreenshotFrame(2, 1, [0, 0, 255, 255])));
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
            // A drawn window (ronda final 17: an all-black frame is refused as the picture of a protected window).
            return new ScreenshotFrame(bounds.Width, bounds.Height,
                Enumerable.Repeat((byte)128, bounds.Width * bounds.Height * 4).ToArray());
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

    // Ronda final 17: the screen copy of a window with display affinity, a locked session or the secure desktop comes
    // back all black; it is said, never stored as the capture.
    [Test]
    public void AnAllBlackFrameIsNeverStoredAsTheCapture()
    {
        using TemporaryDirectory temporary = new();
        ActiveWindowSnapshot snapshot = Snapshot();
        var time = new AdvancingTimeProvider();
        var platform = new GdiScreenshotPlatform(() => snapshot,
            bounds => new ScreenshotFrame(bounds.Width, bounds.Height, new byte[bounds.Width * bounds.Height * 4]), time);
        var provider = new WindowsScreenshotProvider(temporary.Path, platform, time);

        ScreenshotUnavailableException? refused = Assert.ThrowsAsync<ScreenshotUnavailableException>(
            async () => await provider.CaptureActiveWindowAsync(CancellationToken.None));

        Assert.Multiple(() =>
        {
            Assert.That(refused!.Code, Is.EqualTo("capture_frame_black"));
            Assert.That(Directory.GetFiles(temporary.Path, "*.bmp"), Is.Empty);
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
            return new ScreenshotFrame(bounds.Width, bounds.Height, Lit(bounds.Width * bounds.Height * 4));
        }, new FixedTimeProvider());
        var provider = new WindowsScreenshotProvider(temporary.Path, platform, new FixedTimeProvider());

        // Renew al máximo (w8): the change has its own code, not the generic active_window_capture_failed.
        ScreenshotUnavailableException? changed = Assert.ThrowsAsync<ScreenshotUnavailableException>(
            async () => await provider.CaptureActiveWindowAsync(CancellationToken.None));
        Assert.Multiple(() =>
        {
            Assert.That(changed!.Code, Is.EqualTo("active_window_changed_during_capture"));
            Assert.That(copied, Is.True);
            Assert.That(observations, Is.EqualTo(2));
            Assert.That(Directory.GetFiles(temporary.Path), Is.Empty);
        });
    }

    // 2026-09-28: Steam's helper window, parked at (-25600, -25600), held the
    // foreground. The failure names why, so the operation reports it instead of
    // a bare I/O fault, and nothing is read or stored.
    [Test]
    public void ActiveWindowOutsideTheVisibleDesktopFailsWithItsReasonWithoutStoringImage()
    {
        using TemporaryDirectory temporary = new();
        ActiveWindowSnapshot parked = Snapshot() with
        {
            WindowBounds = new CaptureBounds(-25600, -25600, 1010, 600),
        };
        int copies = 0;
        var platform = new GdiScreenshotPlatform(() => parked, bounds =>
        {
            copies++;
            return new ScreenshotFrame(bounds.Width, bounds.Height, Lit(bounds.Width * bounds.Height * 4));
        }, new FixedTimeProvider());
        var provider = new WindowsScreenshotProvider(temporary.Path, platform, new FixedTimeProvider());

        ScreenshotUnavailableException? failure = Assert.ThrowsAsync<ScreenshotUnavailableException>(
            async () => await provider.CaptureActiveWindowAsync(CancellationToken.None));
        Assert.Multiple(() =>
        {
            Assert.That(failure!.Code, Is.EqualTo("active_window_not_visible"));
            Assert.That(failure, Is.InstanceOf<IOException>());
            Assert.That(copies, Is.Zero);
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
            return new ScreenshotFrame(bounds.Width, bounds.Height, Lit(bounds.Width * bounds.Height * 4));
        }, new FixedTimeProvider());
        var provider = new WindowsScreenshotProvider(temporary.Path, platform, new FixedTimeProvider());

        Assert.ThrowsAsync<IOException>(async () => await provider.CaptureActiveWindowAsync(CancellationToken.None));
        Assert.That(copies, Is.EqualTo(failingObservation - 1));
        Assert.That(Directory.GetFiles(temporary.Path), Is.Empty);
    }

    [TestCase(false)]
    [TestCase(true)]
    public void CaptureUsesPhysicalDesktopCoordinatesAndRestoresOriginalDpiContext(bool activeWindow)
    {
        var dpi = new FakeThreadDpiContext();
        var physicalDesktop = new CaptureBounds(0, 0, 2800, 1840);
        var virtualizedDesktop = new CaptureBounds(0, 0, 1244, 818);
        var window = new CaptureBounds(136, 124, 2564, 1320);
        int observations = 0;
        CaptureBounds ReadDesktop() => dpi.Current == (nint)(-4) ? physicalDesktop : virtualizedDesktop;
        var platform = new GdiScreenshotPlatform(() =>
        {
            Assert.That(dpi.Current, Is.EqualTo((nint)(-4)));
            observations++;
            return Snapshot() with { WindowBounds = window, DesktopBounds = ReadDesktop() };
        }, bounds =>
        {
            Assert.That(dpi.Current, Is.EqualTo((nint)(-4)), "Pixel acquisition must share the physical bounds context.");
            Assert.That(bounds, Is.EqualTo(activeWindow ? window : physicalDesktop));
            return new ScreenshotFrame(bounds.Width, bounds.Height, []);
        }, new FixedTimeProvider(), dpi.Set, ReadDesktop);

        ScreenshotFrame frame = activeWindow ? platform.CaptureActiveWindow() : platform.CaptureVirtualScreen();

        Assert.Multiple(() =>
        {
            Assert.That((frame.Width, frame.Height), Is.EqualTo(activeWindow ? (2564, 1320) : (2800, 1840)));
            Assert.That(observations, Is.EqualTo(activeWindow ? 2 : 0));
            Assert.That(dpi.Current, Is.EqualTo(FakeThreadDpiContext.Original));
            Assert.That(dpi.Requests, Is.EqualTo(new nint[] { -4, FakeThreadDpiContext.Original }));
            if (activeWindow)
            {
                Assert.That(frame.ActiveWindow!.CaptureBounds, Is.EqualTo(window));
                Assert.That(frame.ActiveWindow.IsClipped, Is.False);
            }
            else
            {
                Assert.That(frame.ActiveWindow, Is.Null);
            }
        });
    }

    [TestCase(true, "before")]
    [TestCase(true, "pixels")]
    [TestCase(true, "after")]
    [TestCase(false, "bounds")]
    [TestCase(false, "pixels")]
    public void CaptureFailureRestoresThreadDpiContext(bool activeWindow, string failureStage)
    {
        var dpi = new FakeThreadDpiContext();
        int observations = 0;
        var platform = new GdiScreenshotPlatform(() =>
        {
            Assert.That(dpi.Current, Is.EqualTo((nint)(-4)));
            observations++;
            if (failureStage == (observations == 1 ? "before" : "after"))
                throw new IOException("Observation unavailable.");
            return Snapshot();
        }, bounds =>
        {
            Assert.That(dpi.Current, Is.EqualTo((nint)(-4)));
            if (failureStage == "pixels") throw new IOException("Pixel copy failed.");
            return new ScreenshotFrame(bounds.Width, bounds.Height, []);
        }, new FixedTimeProvider(), dpi.Set, () =>
        {
            Assert.That(dpi.Current, Is.EqualTo((nint)(-4)));
            if (failureStage == "bounds") throw new IOException("Desktop bounds unavailable.");
            return Snapshot().DesktopBounds;
        });

        Assert.Throws<IOException>(() =>
        {
            if (activeWindow) _ = platform.CaptureActiveWindow();
            else _ = platform.CaptureVirtualScreen();
        });
        Assert.That(dpi.Current, Is.EqualTo(FakeThreadDpiContext.Original));
        Assert.That(dpi.Requests, Is.EqualTo(new nint[] { -4, FakeThreadDpiContext.Original }));
    }

    [TestCase(false)]
    [TestCase(true)]
    public void UnavailableDpiContextDoesNotReadBoundsOrPixels(bool activeWindow)
    {
        var dpi = new FakeThreadDpiContext { RejectEnter = true };
        int nativeReads = 0;
        var platform = new GdiScreenshotPlatform(() =>
        {
            nativeReads++;
            return Snapshot();
        }, bounds =>
        {
            nativeReads++;
            return new ScreenshotFrame(bounds.Width, bounds.Height, []);
        }, new FixedTimeProvider(), dpi.Set, () =>
        {
            nativeReads++;
            return Snapshot().DesktopBounds;
        });

        Assert.Throws<IOException>(() =>
        {
            if (activeWindow) _ = platform.CaptureActiveWindow();
            else _ = platform.CaptureVirtualScreen();
        });
        Assert.That(nativeReads, Is.Zero);
        Assert.That(dpi.Current, Is.EqualTo(FakeThreadDpiContext.Original));
        Assert.That(dpi.Requests, Is.EqualTo(new nint[] { -4 }));
    }

    [TestCase(false)]
    [TestCase(true)]
    public void FailedDpiRestorationDoesNotPersistASuccessfulCapture(bool activeWindow)
    {
        using TemporaryDirectory temporary = new();
        var dpi = new FakeThreadDpiContext { RejectRestore = true };
        var platform = new GdiScreenshotPlatform(Snapshot,
            bounds => new ScreenshotFrame(bounds.Width, bounds.Height, Lit(bounds.Width * bounds.Height * 4)),
            new FixedTimeProvider(), dpi.Set, () => Snapshot().DesktopBounds);
        var provider = new WindowsScreenshotProvider(temporary.Path, platform, new FixedTimeProvider());

        Assert.ThrowsAsync<IOException>(async () =>
        {
            if (activeWindow) _ = await provider.CaptureActiveWindowAsync(CancellationToken.None);
            else _ = await provider.CaptureAsync(CancellationToken.None);
        });
        Assert.That(dpi.Requests, Is.EqualTo(new nint[] { -4, FakeThreadDpiContext.Original }));
        Assert.That(Directory.GetFiles(temporary.Path), Is.Empty);
    }

    private sealed class FakeThreadDpiContext
    {
        internal static readonly nint Original = 12345;
        public nint Current { get; private set; } = Original;
        public List<nint> Requests { get; } = [];
        public bool RejectEnter { get; init; }
        public bool RejectRestore { get; init; }

        public nint Set(nint context)
        {
            Requests.Add(context);
            if ((context == (nint)(-4) && RejectEnter) || (context == Original && RejectRestore)) return 0;
            nint previous = Current;
            Current = context;
            return previous;
        }
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

    // A drawn frame (ronda final 17: an all-black one is refused as the screen copy of what could not be read).
    private static byte[] Lit(int length) => Enumerable.Repeat((byte)128, length).ToArray();
}

/// <summary>Renew al máximo (w8): a capture that could not be taken for a reason it knows says what to do.</summary>
[TestFixture]
public sealed class ScreenshotCaptureHandlerFailureTests
{
    [Test]
    public async Task AWindowThatChangedDuringTheCaptureSaysSoAndWhatToDo()
    {
        var handler = new Baxy.Core.Operations.ScreenshotCaptureHandler(
            new ChangingWindow(), "capture.active.window", activeWindow: true);

        Baxy.Kernel.Operations.OperationOutcome outcome = await handler.ExecuteAsync(
            new Baxy.Kernel.Operations.OperationInvocation(
                "request", "mission", "invocation", System.Text.Json.JsonDocument.Parse("{}").RootElement.Clone()),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.False);
            Assert.That(outcome.ErrorCode, Is.EqualTo("active_window_changed_during_capture"));
            Assert.That(outcome.Result!.Value.GetProperty("next").GetString(),
                Does.Contain("capture again").And.Contain("nothing was stored"));
        });
    }

    private sealed class ChangingWindow : IScreenshotProvider
    {
        public ValueTask<CaptureResult> CaptureAsync(CancellationToken cancellationToken) =>
            throw new NotSupportedException();

        public ValueTask<CaptureResult> CaptureActiveWindowAsync(CancellationToken cancellationToken) =>
            throw new ScreenshotUnavailableException("active_window_changed_during_capture", "changed");
    }
}
