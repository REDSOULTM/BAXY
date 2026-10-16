using System.Diagnostics;
using System.Globalization;
using System.IO.Pipes;
using System.Net;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.Audio;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class ExternalAdaptersTests
{
    // schedule takes the person's local time; seconds keep the trigger exact.
    private static string LocalAt(DateTimeOffset due) =>
        due.ToLocalTime().ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture);

    [TestCase("lock", "win32_lockworkstation_acceptance")]
    [TestCase("restart", "win32_initiatesystemshutdownex_restart_acceptance")]
    [TestCase("shutdown", "win32_initiatesystemshutdownex_shutdown_acceptance")]
    // POWER2079: when Windows refuses the older call the transition is asked through
    // InitiateShutdownW, the door shutdown.exe uses, and its authority is reported.
    [TestCase("restart", "win32_initiateshutdown_restart_acceptance")]
    [TestCase("shutdown", "win32_initiateshutdown_shutdown_acceptance")]
    [TestCase("signout", "win32_exitwindowsex_logoff_acceptance")]
    [TestCase("sleep", "win32_setsuspendstate_acceptance")]
    public async Task PowerTransitionsDispatchToTheExactOfficialWindowsAuthority(
        string action, string authority)
    {
        var platform = new StubPowerTransitionPlatform(authority, accepted: true);
        var adapter = new WindowsPowerTransitionAdapter(platform);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.power",
            JsonSerializer.SerializeToElement(new { action }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("action").GetString(), Is.EqualTo(action));
            Assert.That(receipt.Result?.GetProperty("accepted").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo(authority));
            Assert.That(platform.RequestedAction, Is.EqualTo(action));
            // REOPEN1993 grupo P (H0401, H0714): a restart or shutdown is asked with
            // the delay Windows announces and `shutdown /a` can still abort; the
            // other transitions have no delay.
            if (action is "restart" or "shutdown")
            {
                Assert.That(receipt.Result?.GetProperty("delaySeconds").GetUInt32(),
                    Is.EqualTo(WindowsPowerTransitionPlatform.TransitionDelaySeconds));
                Assert.That(WindowsPowerTransitionPlatform.TransitionDelaySeconds, Is.EqualTo(30u));
            }
            else
            {
                Assert.That(receipt.Result?.TryGetProperty("delaySeconds", out _), Is.False);
            }
        });
    }

    [Test]
    public async Task ExactNamedProcessTerminationPreservesIdentityAndVerifiesAbsence()
    {
        var identity = new WindowsProcessIdentity(4242, 638900000000000000);
        var platform = new StubProcessTerminationPlatform(
            [[identity], []], terminateResult: WindowsProcessTermination.Terminated);
        var adapter = new WindowsProcessTerminationAdapter(platform);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.process.terminate.named",
            Json("""{"name":"steam.exe"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(receipt.Result?.GetProperty("processName").GetString(), Is.EqualTo("steam"));
            Assert.That(receipt.Result?.GetProperty("beforeCount").GetInt32(), Is.EqualTo(1));
            Assert.That(receipt.Result?.GetProperty("afterCount").GetInt32(), Is.Zero);
            Assert.That(
                receipt.Result?.GetProperty("identities")[0].GetProperty("processId").GetInt32(),
                Is.EqualTo(4242));
            Assert.That(platform.Terminated, Is.EqualTo(new[] { identity }));
        });
    }

    [Test]
    public async Task ExactNamedProcessTerminationFailsAmbiguouslyWhenPostreadStillFindsIt()
    {
        var identity = new WindowsProcessIdentity(5151, 638900000000000001);
        var platform = new StubProcessTerminationPlatform(
            [[identity], [identity]], terminateResult: WindowsProcessTermination.NotTerminated);
        var adapter = new WindowsProcessTerminationAdapter(platform);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.process.terminate.named",
            Json("""{"name":"steam"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo("process_termination_postread_failed"));
        });
    }

    [Test]
    public async Task ExactNamedProcessTerminationFailsBeforeEffectWhenNothingRuns()
    {
        var platform = new StubProcessTerminationPlatform([[]], terminateResult: WindowsProcessTermination.Terminated);
        var adapter = new WindowsProcessTerminationAdapter(platform);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.process.terminate.named",
            Json("""{"name":"steam"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("process_not_running"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(platform.Terminated, Is.Empty);
        });
    }

    [Test]
    public async Task ExactNamedProcessTerminationDoesNotCountAProcessThatHadAlreadyExited()
    {
        var identity = new WindowsProcessIdentity(5252, 638900000000000002);
        var platform = new StubProcessTerminationPlatform(
            [[identity], []], terminateResult: WindowsProcessTermination.AlreadyExited);
        var adapter = new WindowsProcessTerminationAdapter(platform);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.process.terminate.named",
            Json("""{"name":"steam"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.StateAlreadyReached, Is.True);
            Assert.That(receipt.Result?.GetProperty("terminatedCount").GetInt32(), Is.Zero);
            Assert.That(receipt.Result?.GetProperty("alreadyExitedCount").GetInt32(), Is.EqualTo(1));
        });
    }

    [Test]
    public async Task ExactNamedProcessTerminationAllowsAWindowsRestartWithANewIdentity()
    {
        var original = new WindowsProcessIdentity(5151, 638900000000000001);
        var replacement = new WindowsProcessIdentity(6262, 638900000000000099);
        var platform = new StubProcessTerminationPlatform(
            [[original], [replacement]], terminateResult: WindowsProcessTermination.Terminated);
        var adapter = new WindowsProcessTerminationAdapter(platform);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.process.terminate.named",
            Json("""{"name":"explorer.exe"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("originalIdentitiesAbsent").GetBoolean(),
                Is.True);
            Assert.That(receipt.Result?.GetProperty("replacementCount").GetInt32(),
                Is.EqualTo(1));
            Assert.That(receipt.Result?.GetProperty("replacementIdentities")[0]
                .GetProperty("processId").GetInt32(), Is.EqualTo(6262));
        });
    }

    [Test]
    public async Task BrightnessStatusReturnsOnlyACoherentDoubleRead()
    {
        const string output =
            """{"ok":true,"monitors":[{"instanceName":"DISPLAY\\A","value":64}]}""";
        using TemporaryDirectory temporary = new();
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path, temporary.Path, new StubProcessRunner(output));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.settings.status",
            Json("""{"setting":"brightness"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result?.GetProperty("monitors")[0]
                .GetProperty("value").GetInt32(), Is.EqualTo(64));
        });
    }

    [Test]
    public async Task ApplicationCrashDiagnosticReturnsStableEventLogRecords()
    {
        const string output = """
            {"ok":true,"firstObservationCount":2,"secondObservationCount":2,"events":[{"recordId":9123,"eventId":1000,"provider":"Application Error","timeUtc":"2026-07-21T10:00:00.0000000Z","applicationName":"game.exe"}]}
            """;
        var adapter = new WindowsApplicationCrashDiagnosticAdapter(
            new StubProcessRunner(output));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.application.crash.diagnose",
            Json("""{"hours":24,"limit":20}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result?.GetProperty("events")[0]
                .GetProperty("recordId").GetInt64(), Is.EqualTo(9123));
        });
    }

    [Test]
    public async Task ExactNamedProcessTerminationRejectsPathsBeforeTakingAnEffect()
    {
        var platform = new StubProcessTerminationPlatform([], terminateResult: WindowsProcessTermination.Terminated);
        var adapter = new WindowsProcessTerminationAdapter(platform);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.process.terminate.named",
            Json("""{"name":"C:\\Windows\\steam.exe"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("invalid_arguments"));
            Assert.That(platform.Terminated, Is.Empty);
        });
    }

    [Test]
    public async Task ExactNamedProcessTerminationKillsAControlledRealWindowsProcess()
    {
        string probeRoot = Path.Combine(
            Path.GetTempPath(), "BaxyTerminationProbe_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(probeRoot);
        string probePath = Path.Combine(probeRoot, "BaxyTerminationProbe.exe");
        File.Copy(Environment.GetEnvironmentVariable("ComSpec") ?? "C:\\Windows\\System32\\cmd.exe",
            probePath);
        using var process = Process.Start(new ProcessStartInfo
        {
            FileName = probePath,
            // A single process: the console waits on its own input, so ending it leaves no child behind.
            Arguments = "/d /q /k",
            CreateNoWindow = true,
            UseShellExecute = false,
            RedirectStandardInput = true,
        })!;
        try
        {
            Assert.That(process.WaitForExit(250), Is.False, "The controlled probe exited early.");
            var adapter = new WindowsProcessTerminationAdapter();

            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
                "system.process.terminate.named",
                Json("""{"name":"BaxyTerminationProbe"}"""),
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.True);
                Assert.That(receipt.EffectObserved, Is.True);
                Assert.That(receipt.Result?.GetProperty("afterCount").GetInt32(), Is.Zero);
                Assert.That(process.WaitForExit(5000), Is.True);
            });
        }
        finally
        {
            if (!process.HasExited) process.Kill(entireProcessTree: true);
            try { Directory.Delete(probeRoot, recursive: true); } catch (IOException) { }
        }
    }

    [Test]
    public async Task MediaStatusWithoutAnSmtcAdapterFailsExplicitlyWithoutAnEffect()
    {
        using var provider = new WindowsExternalCapabilityProvider([]);

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "media.status",
            Json("{}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("external_operation_not_supported"));
        });
    }

    [Test]
    public async Task MediaSeekWithoutAnSmtcAdapterFailsExplicitlyWithoutAnEffect()
    {
        using var provider = new WindowsExternalCapabilityProvider([]);

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "media.seek.relative",
            Json("""{"seconds":5}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("external_operation_not_supported"));
        });
    }

    [Test]
    public async Task ProviderFallsBackOnlyAfterAProviderSafeFailure()
    {
        var first = new StubExternalAdapter(new ExternalCapabilityReceipt(
            "media.control", false, false, null, "smtc_session_not_found"));
        var second = new StubExternalAdapter(new ExternalCapabilityReceipt(
            "media.control", true, true, Json("""{"playbackStatus":"paused"}"""), null));
        using var provider = new WindowsExternalCapabilityProvider([first, second]);

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "media.control",
            Json("""{"action":"pause"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(first.Calls, Is.EqualTo(1));
            Assert.That(second.Calls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task ProviderNeverRetriesAfterAnAmbiguousEffect()
    {
        var first = new StubExternalAdapter(new ExternalCapabilityReceipt(
            "media.control", true, false, null, "postread_failed"));
        var second = new StubExternalAdapter(new ExternalCapabilityReceipt(
            "media.control", true, true, Json("{}"), null));
        using var provider = new WindowsExternalCapabilityProvider([first, second]);

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "media.control",
            Json("""{"action":"pause"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(first.Calls, Is.EqualTo(1));
            Assert.That(second.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task ProviderNeverFallsBackWhenDispatchWasAmbiguousWithoutObservedEvidence()
    {
        var first = new StubExternalAdapter(new ExternalCapabilityReceipt(
            "media.control", false, false, null, "post_dispatch_receipt_lost")
        {
            EffectMayHaveOccurred = true,
        });
        var second = new StubExternalAdapter(new ExternalCapabilityReceipt(
            "media.control", true, true, Json("{}"), null));
        using var provider = new WindowsExternalCapabilityProvider([first, second]);

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "media.control",
            Json("""{"action":"pause"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(first.Calls, Is.EqualTo(1));
            Assert.That(second.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task MissingWingetReturnsAStableReadOnlyFailure()
    {
        var runner = new ThrowingProcessRunner(
            new System.ComponentModel.Win32Exception(2, "winget.exe was not found"));
        // REOPEN1993 grupo G: the package operations moved to WingetPackageAdapter.
        var adapter = new WingetPackageAdapter(runner, _ => null);

        ExternalCapabilityReceipt? receipt = null;
        Assert.DoesNotThrowAsync(async () =>
        {
            receipt = await adapter.InvokeAsync(
                "package.install",
                Json("""{"packageId":"Microsoft.PowerToys"}"""),
                CancellationToken.None);
        });

        Assert.Multiple(() =>
        {
            Assert.That(runner.Calls, Is.EqualTo(1));
            Assert.That(receipt, Is.Not.Null);
            Assert.That(receipt!.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("winget_adapter_unavailable"));
        });
    }

    [Test]
    public async Task SlowWinRtBluetoothInventorySaysItsTimeoutWithinItsBound()
    {
        using TemporaryDirectory temporary = new();
        var devices = new WindowsDeviceControlAdapter(
            temporary.Path,
            temporary.Path,
            new StubProcessRunner(""),
            new SlowBluetoothInventory(TimeSpan.FromSeconds(1)),
            TimeSpan.FromMilliseconds(50));
        using var provider = new WindowsExternalCapabilityProvider([devices]);
        var stopwatch = Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "bluetooth.device.list",
            Json("{}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(stopwatch.Elapsed, Is.LessThan(TimeSpan.FromMilliseconds(500)));
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("bluetooth_winrt_inventory_timeout"));
        });
    }

    [Test]
    public async Task CaptureAdapterRejectsInventedAndMissingIdentitiesBeforeProviderUse()
    {
        using TemporaryDirectory temporary = new();
        using var adapter = new CaptureVisionAdapter(temporary.Path);

        ExternalCapabilityReceipt invented = await adapter.InvokeAsync(
            "ocr.read", Json("""{"captureId":"../../secret"}"""), CancellationToken.None);
        ExternalCapabilityReceipt missing = await adapter.InvokeAsync(
            "ocr.read",
            Json("""{"captureId":"capture_00000000000000000000000000000000"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(invented.ErrorCode, Is.EqualTo("capture_identity_invalid"));
            Assert.That(invented.EffectObserved, Is.False);
            Assert.That(missing.ErrorCode, Is.EqualTo("capture_not_found"));
            Assert.That(missing.EffectObserved, Is.False);
        });
    }

    [Test]
    [NonParallelizable]
    public void CaptureAdapterDiscoversConfiguredBoundedTesseractAssets()
    {
        using TemporaryDirectory temporary = new();
        string executable = Path.Combine(temporary.Path, "tesseract.exe");
        string tessdata = Path.Combine(temporary.Path, "tessdata");
        File.WriteAllBytes(executable, [0x4d, 0x5a]);
        Directory.CreateDirectory(tessdata);
        File.WriteAllBytes(Path.Combine(tessdata, "eng.traineddata"), [1]);
        File.WriteAllBytes(Path.Combine(tessdata, "spa.traineddata"), [1]);
        string? previousExecutable = Environment.GetEnvironmentVariable("BAXY_TESSERACT_EXE");
        string? previousTessdata = Environment.GetEnvironmentVariable("BAXY_TESSDATA_DIR");
        try
        {
            Environment.SetEnvironmentVariable("BAXY_TESSERACT_EXE", executable);
            Environment.SetEnvironmentVariable("BAXY_TESSDATA_DIR", tessdata);

            Assert.That(CaptureVisionAdapter.FindTesseract(), Is.EqualTo(executable));
            Assert.That(
                CaptureVisionAdapter.FindTessdata(executable, null, out string automatic),
                Is.EqualTo(tessdata));
            Assert.That(automatic, Is.EqualTo("spa+eng"));
            Assert.That(
                CaptureVisionAdapter.FindTessdata(executable, "es-CL", out string spanish),
                Is.EqualTo(tessdata));
            Assert.That(spanish, Is.EqualTo("spa"));
            Assert.That(
                CaptureVisionAdapter.FindTessdata(executable, "fr-FR", out string unsupported),
                Is.Null);
            Assert.That(unsupported, Is.Empty);
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_TESSERACT_EXE", previousExecutable);
            Environment.SetEnvironmentVariable("BAXY_TESSDATA_DIR", previousTessdata);
        }
    }

    [Test]
    [NonParallelizable]
    public async Task VisionBindsConfiguredProviderResponseToExactCaptureHash()
    {
        using var directory = new TemporaryDirectory();
        string captureId = "capture_" + new string('a', 32);
        byte[] bytes = Enumerable.Range(0, 64).Select(value => (byte)value).ToArray();
        await File.WriteAllBytesAsync(Path.Combine(directory.Path, captureId + ".bmp"), bytes);
        string? endpoint = Environment.GetEnvironmentVariable("BAXY_VISION_ENDPOINT");
        string? model = Environment.GetEnvironmentVariable("BAXY_VISION_MODEL");
        try
        {
            // A remote vision service would receive the person's screen: refused before anything is sent.
            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", "https://vision.example/v1/chat/completions");
            Environment.SetEnvironmentVariable("BAXY_VISION_MODEL", "vision-test");
            using var http = new HttpClient(new VisionHttpHandler());
            using var adapter = new CaptureVisionAdapter(directory.Path, http);
            ExternalCapabilityReceipt remote = await adapter.InvokeAsync(
                "vision.describe",
                Json($$"""{"captureId":"{{captureId}}","prompt":"describe"}"""),
                CancellationToken.None);

            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", "http://127.0.0.1:8090/v1/chat/completions");
            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
                "vision.describe",
                Json($$"""{"captureId":"{{captureId}}","prompt":"describe"}"""),
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(remote.Verified, Is.False);
                Assert.That(remote.ErrorCode, Is.EqualTo("vision_provider_not_configured"));
                Assert.That(receipt.Verified, Is.True);
                Assert.That(receipt.EffectObserved, Is.False);
                Assert.That(receipt.Result?.GetProperty("description").GetString(),
                    Is.EqualTo("A bounded test image."));
                Assert.That(receipt.Result?.GetProperty("captureSha256").GetString(),
                    Is.EqualTo(Convert.ToHexStringLower(SHA256.HashData(bytes))));
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", endpoint);
            Environment.SetEnvironmentVariable("BAXY_VISION_MODEL", model);
        }
    }

    [Test]
    public async Task BrowserNavigationReturnsOnlyObservedCdpIdentity()
    {
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(
            temporary.Path,
            new(true, true, "https://example.com/", "https://example.com/final", "page-1", ""));
        using var http = new HttpClient(new StubHttpHandler("<rss><channel></channel></rss>"));
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "browser.navigate",
            Json("""{"url":"https://example.com/"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("finalUrl").GetString(),
                Is.EqualTo("https://example.com/final"));
            Assert.That(receipt.Result?.GetProperty("targetId").GetString(), Is.EqualTo("page-1"));
        });
    }

    [Test]
    public async Task BrowserControlReturnsOnlyObservedCdpPostread()
    {
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserControlSession(
            temporary.Path,
            new(true, true, "scroll_down", "page-7", "scroll_y:640", ""));
        using var http = new HttpClient(new StubHttpHandler("<rss><channel></channel></rss>"));
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "browser.control",
            Json("""{"action":"scroll_down"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("action").GetString(), Is.EqualTo("scroll_down"));
            Assert.That(receipt.Result?.GetProperty("observedState").GetString(),
                Is.EqualTo("scroll_y:640"));
            Assert.That(receipt.Result?.GetProperty("targetId").GetString(), Is.EqualTo("page-7"));
        });
    }

    [Test]
    public async Task BrowserPageReadReturnsBoundedObservedDomSnapshotWithoutAnEffect()
    {
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserPageSession(
            temporary.Path,
            new(true, "page-8", "https://example.com/article", "Example article",
                "Visible article text", false, ""));
        using var http = new HttpClient(new StubHttpHandler("<rss><channel></channel></rss>"));
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "browser.page.read",
            Json("""{"maximumCharacters":4096}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result?.GetProperty("targetId").GetString(), Is.EqualTo("page-8"));
            Assert.That(receipt.Result?.GetProperty("title").GetString(), Is.EqualTo("Example article"));
            Assert.That(receipt.Result?.GetProperty("text").GetString(), Is.EqualTo("Visible article text"));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("cdp_dom_visible_text_snapshot"));
        });
    }

    [Test]
    public async Task NamedBrowserNavigationKeepsItsSessionForTheImmediatePageRead()
    {
        using TemporaryDirectory temporary = new();
        var context = new CdpBrowserSessionContext();
        var opera = new StubBrowserChainSession(
            temporary.Path,
            new(true, true, "https://example.com/", "https://example.com/", "opera-page", ""),
            new(true, "opera-page", "https://example.com/", "Example Domain",
                "Opera-owned snapshot", false, ""),
            observedExecutablePath: Path.Combine(temporary.Path, "opera.exe"));
        using var named = new NamedBrowserAdapter(temporary.Path, context, opera);
        using var edge = new StubBrowserPageSession(
            temporary.Path,
            new(true, "edge-page", "https://edge.example/", "Wrong session",
                "Edge-owned snapshot", false, ""));
        using var http = new HttpClient(new StubHttpHandler("<rss><channel></channel></rss>"));
        using var web = new WebBrowserAdapter(edge, http, context);

        ExternalCapabilityReceipt navigation = await named.InvokeAsync(
            "browser.navigate.named",
            Json("""{"browser":"opera","url":"https://example.com/"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt page = await web.InvokeAsync(
            "browser.page.read",
            Json("""{"maximumCharacters":2000}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(navigation.Verified, Is.True);
            Assert.That(page.Verified, Is.True);
            Assert.That(page.Result?.GetProperty("targetId").GetString(),
                Is.EqualTo("opera-page"));
            Assert.That(page.Result?.GetProperty("text").GetString(),
                Is.EqualTo("Opera-owned snapshot"));
            Assert.That(opera.ReadCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task GenericNavigationReclaimsTheSessionForFollowingBrowserSteps()
    {
        using TemporaryDirectory temporary = new();
        var context = new CdpBrowserSessionContext();
        using var opera = new StubBrowserPageSession(
            temporary.Path,
            new(true, "opera-page", "https://opera.example/", "Opera",
                "Stale named session", false, ""));
        context.Activate(opera);
        using var edge = new StubBrowserChainSession(
            temporary.Path,
            new(true, true, "https://example.com/", "https://example.com/", "edge-page", ""),
            new(true, "edge-page", "https://example.com/", "Example Domain",
                "Fresh generic session", false, ""));
        using var http = new HttpClient(new StubHttpHandler("<rss><channel></channel></rss>"));
        using var web = new WebBrowserAdapter(edge, http, context);

        ExternalCapabilityReceipt navigation = await web.InvokeAsync(
            "browser.navigate",
            Json("""{"url":"https://example.com/"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt page = await web.InvokeAsync(
            "browser.page.read",
            Json("""{"maximumCharacters":2000}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(navigation.Verified, Is.True);
            Assert.That(page.Verified, Is.True);
            Assert.That(page.Result?.GetProperty("targetId").GetString(),
                Is.EqualTo("edge-page"));
            Assert.That(page.Result?.GetProperty("text").GetString(),
                Is.EqualTo("Fresh generic session"));
            Assert.That(edge.ReadCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public void BrowserPageSnapshotIsConsumableOnlyAfterDocumentReadiness()
    {
        CdpPageReadResult loading = CdpBrowserSession.ParsePageSnapshot(
            "page-1",
            2000,
            """{"url":"https://example.com/","title":"Example","text":"","truncated":false,"readyState":"loading"}""");
        CdpPageReadResult ready = CdpBrowserSession.ParsePageSnapshot(
            "page-1",
            2000,
            """{"url":"https://example.com/","title":"Example","text":"Ready","truncated":false,"readyState":"interactive"}""");

        Assert.Multiple(() =>
        {
            Assert.That(loading.Verified, Is.False);
            Assert.That(loading.ErrorCode, Is.EqualTo("browser_page_snapshot_invalid"));
            Assert.That(ready.Verified, Is.True);
            Assert.That(ready.Text, Is.EqualTo("Ready"));
        });
    }

    [Test]
    public void OwnedCdpEndpointLossAfterCloseIsARecognizedTerminalAbsence()
    {
        Assert.Multiple(() =>
        {
            Assert.That(
                CdpBrowserSession.IsEndpointLossAfterClose(
                    new HttpRequestException("endpoint closed"),
                    CancellationToken.None),
                Is.True);
            Assert.That(
                CdpBrowserSession.IsEndpointLossAfterClose(
                    new OperationCanceledException(),
                    new CancellationToken(canceled: true)),
                Is.False);
        });
    }

    [Test]
    public async Task BrowserTabListReturnsOnlyObservedWebTargetsWithoutAnEffect()
    {
        using TemporaryDirectory temporary = new();
        CdpBrowserTab[] observed =
        [
            new("page-1", "First", "https://example.com/"),
            new("page-2", "Second", "https://openai.com/"),
        ];
        using var browser = new StubBrowserTabsSession(
            temporary.Path, new(true, observed, 2, false, ""));
        using var http = new HttpClient(new StubHttpHandler("<rss><channel></channel></rss>"));
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "browser.tabs.list", Json("""{"limit":50}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result?.GetProperty("count").GetInt32(), Is.EqualTo(2));
            Assert.That(receipt.Result?.GetProperty("tabs").GetArrayLength(), Is.EqualTo(2));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("cdp_page_targets_snapshot"));
        });
    }

    [Test]
    public async Task YouTubePlaybackRequiresObservedPlayingVideo()
    {
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserPlaybackSession(
            temporary.Path,
            new(true, true, "gatos", "https://www.youtube.com/watch?v=verified",
                "Gatos - YouTube", "page-9", ""));
        using var http = new HttpClient(new StubHttpHandler(
            "{\"videoRenderer\":{\"videoId\":\"abcdefghijk\"}}"));
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.youtube",
            Json("""{"query":"gatos"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("playbackStatus").GetString(),
                Is.EqualTo("playing"));
            Assert.That(receipt.Result?.GetProperty("finalUrl").GetString(),
                Is.EqualTo("https://www.youtube.com/watch?v=verified"));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("youtube_cdp_video_postread"));
        });
    }

    [Test]
    public async Task NetflixPlaybackRequiresObservedAdvancingVideo()
    {
        using TemporaryDirectory temporary = new();
        using var browser = new StubNetflixPlaybackSession(
            temporary.Path,
            new(true, true, "Stranger Things", "https://www.netflix.com/watch/verified",
                "Watch Stranger Things | Netflix", "page-10", 1.25, ""));
        using var http = new HttpClient(new StubHttpHandler(""));
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "streaming.play.named",
            Json("""{"service":"netflix","title":"Stranger Things"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("playbackStatus").GetString(),
                Is.EqualTo("playing"));
            Assert.That(receipt.Result?.GetProperty("observedProgressSeconds").GetDouble(),
                Is.GreaterThanOrEqualTo(0.5));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("netflix_cdp_video_progress_postread"));
        });
    }

    [Test]
    public async Task NetflixWithoutACardNamedAsTheTitleReturnsTheCardsAsCandidates()
    {
        using TemporaryDirectory temporary = new();
        using var browser = new StubNetflixPlaybackSession(
            temporary.Path,
            new(false, true, "Wednesday", "https://www.netflix.com/search?q=Wednesday",
                "Netflix", "page-10", 0, UserBrowserSurface.StreamingTitleNotFound, "",
                ["Merlina", "Wednesday Addams: la serie"]));
        using var http = new HttpClient(new StubHttpHandler(""));
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "streaming.play.named",
            Json("""{"service":"netflix","title":"Wednesday"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("streaming_title_not_found"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.Result?.GetProperty("candidates").GetArrayLength(), Is.EqualTo(2));
            Assert.That(receipt.Result?.GetProperty("candidates")[0].GetString(), Is.EqualTo("Merlina"));
        });
    }

    [Test]
    public async Task ScheduledNotificationRequiresWindowsTaskIdentityPostread()
    {
        using TemporaryDirectory temporary = new();
        var backend = ScriptedNotificationBackend.Registering();
        var adapter = new WindowsScheduledNotificationAdapter(temporary.Path, backend);
        string due = DateTimeOffset.UtcNow.AddHours(1).ToString("O");

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(DateTimeOffset.Parse(due, CultureInfo.InvariantCulture))}}","kind":"alarm","title":"Prueba"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("taskName").GetString(),
                Is.EqualTo(backend.Requests[^1].TaskName));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("windows_task_scheduler_postread"));
            Assert.That(File.Exists(Path.Combine(
                temporary.Path, "scheduled-notifications", backend.Requests[^1].TaskName + ".ps1")), Is.True);
        });
    }

    [Test]
    public async Task RecurringNotificationPassesARealHourlyTaskTriggerRequest()
    {
        using TemporaryDirectory temporary = new();
        var backend = ScriptedNotificationBackend.Registering();
        var adapter = new WindowsScheduledNotificationAdapter(temporary.Path, backend);
        string due = DateTimeOffset.UtcNow.AddHours(1).ToString("O");

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(DateTimeOffset.Parse(due, CultureInfo.InvariantCulture))}}","kind":"reminder","recurrence":"hourly","title":"Drink water"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("recurrence").GetString(), Is.EqualTo("hourly"));
            Assert.That(backend.Requests[^1].Mode, Is.EqualTo("schedule-recurring"));
            Assert.That(backend.Requests[^1].Recurrence, Is.EqualTo("hourly"));
        });
    }

    [Test]
    public async Task NotificationDiagnosticsReturnsObservedServiceTasksAndReceipts()
    {
        using TemporaryDirectory temporary = new();
        const string output = "{\"ok\":true,\"schedulerRunning\":true," +
            "\"toastEnabled\":true,\"healthy\":true,\"taskCount\":1," +
            "\"firedReceiptCount\":1,\"issueCount\":0,\"tasks\":[{" +
            "\"taskName\":\"BAXY-Reminder-private\",\"state\":\"Ready\"," +
            "\"lastTaskResult\":0,\"resultAcceptable\":true}]}";
        var adapter = new WindowsScheduledNotificationAdapter(
            temporary.Path, ScriptedNotificationBackend.Lines(output));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms", Json("""{"action":"diagnose"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result?.GetProperty("schedulerRunning").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("taskCount").GetInt32(), Is.EqualTo(1));
            Assert.That(receipt.Result?.GetProperty("tasks")[0]
                .GetProperty("resultAcceptable").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("windows_task_scheduler_notification_diagnostics_postread"));
        });
    }

    [Test]
    public async Task ExactClockNotificationCancellationBindsPreReadIdentityAndVerifiesAbsence()
    {
        using TemporaryDirectory temporary = new();
        const string taskName = "BAXY-Alarm-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        string due = DateTimeOffset.UtcNow.AddHours(2).ToString("O");
        var backend = ScriptedNotificationBackend.Lines([
            $$"""{"ok":true,"effectObserved":false,"matchCount":1,"taskName":"{{taskName}}","nextRunUtc":"{{due}}"}""",
            $$"""{"ok":true,"effectObserved":true,"effectBoundaryCrossed":true,"canceled":true,"taskName":"{{taskName}}","nextRunUtc":"{{due}}","authority":"windows_task_scheduler_exact_identity_absence_postread"}""",
        ]);
        var adapter = new WindowsScheduledNotificationAdapter(temporary.Path, backend);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms",
            Json("""{"action":"cancel","kind":"alarm","at":"17:00"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result?.GetProperty("taskName").GetString(), Is.EqualTo(taskName));
            Assert.That(receipt.Result?.GetProperty("expectedNextRunUtc").GetString(), Is.EqualTo(due));
            Assert.That(backend.Requests, Has.Count.EqualTo(2));
        });
    }

    [Test]
    public async Task ExactClockNotificationCancellationRefusesAmbiguousMatchesBeforeEffect()
    {
        using TemporaryDirectory temporary = new();
        var backend = ScriptedNotificationBackend.Lines([
            "{\"ok\":false,\"effectObserved\":false,\"effectBoundaryCrossed\":false,\"matchCount\":2}",
        ]);
        var adapter = new WindowsScheduledNotificationAdapter(temporary.Path, backend);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms",
            Json("""{"action":"cancel","kind":"alarm","at":"17:00"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("notification_clock_ambiguous"));
            Assert.That(backend.Requests, Has.Count.EqualTo(1));
        });
    }

    [Test]
    public async Task ExactClockNotificationCancellationRefusesChangedIdentityBeforeEffect()
    {
        using TemporaryDirectory temporary = new();
        const string taskName = "BAXY-Alarm-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
        string due = DateTimeOffset.UtcNow.AddHours(2).ToString("O");
        var backend = ScriptedNotificationBackend.Lines([
            $$"""{"ok":true,"effectObserved":false,"matchCount":1,"taskName":"{{taskName}}","nextRunUtc":"{{due}}"}""",
            "{\"ok\":false,\"effectObserved\":false,\"effectBoundaryCrossed\":false,\"error\":\"task_changed_before_effect\"}",
        ]);
        var adapter = new WindowsScheduledNotificationAdapter(temporary.Path, backend);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms",
            Json("""{"action":"cancel","kind":"alarm","at":"17:00"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("notification_scheduler_precondition_changed"));
            Assert.That(backend.Requests, Has.Count.EqualTo(2));
        });
    }

    [TestCase("schedule.alarms", """{"action":"cancel","kind":"reminder"}""")]
    [TestCase("schedule.alarms", """{"action":"cancel","kind":"alarm","at":"06:45"}""")]
    public async Task NotificationCancellationIsScopedToTheNotificationsThisDataRootSet(
        string operation, string arguments)
    {
        // M80 (DEV-D v3m D-w16-t2, D-w18-t5): the scheduler is shared by every BAXY data root of the user; six runs
        // left six alarms at 06:45 and «cancel the latest» picked another run's reminder.
        using TemporaryDirectory temporary = new();
        var backend = ScriptedNotificationBackend.Lines("{\"ok\":false,\"matchCount\":0}");
        var adapter = new WindowsScheduledNotificationAdapter(temporary.Path, backend);

        await adapter.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.That(backend.Requests[^1].AlarmRoot, Is.EqualTo(Path.Combine(temporary.Path, "scheduled-notifications")));
    }

    [Test]
    public async Task NotificationListShowsOnlyTheNotificationsThisDataRootSet()
    {
        using TemporaryDirectory temporary = new();
        const string own = "BAXY-Alarm-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        const string other = "BAXY-Alarm-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
        string alarms = Path.Combine(temporary.Path, "scheduled-notifications");
        Directory.CreateDirectory(alarms);
        await File.WriteAllTextAsync(Path.Combine(alarms, own + ".ps1"), "# ring");
        string next = DateTimeOffset.UtcNow.AddHours(3).ToString("O");
        string output = $$"""{"ok":true,"tasks":[{"taskName":"{{own}}","state":"Ready","nextRunUtc":"{{next}}"},{"taskName":"{{other}}","state":"Ready","nextRunUtc":"{{next}}"}]}""";
        var adapter = new WindowsScheduledNotificationAdapter(
            temporary.Path, ScriptedNotificationBackend.Lines(output));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms", Json("""{"action":"list"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("count").GetInt32(), Is.EqualTo(1));
            Assert.That(receipt.Result?.GetProperty("notifications").GetArrayLength(), Is.EqualTo(1));
        });
    }

    [Test]
    public async Task NamedGameInstallationReadsSteamAndEpicManifestsAndExistingDirectories()
    {
        using TemporaryDirectory temporary = new();
        string steamApps = Path.Combine(temporary.Path, "steamapps");
        string steamInstall = Path.Combine(steamApps, "common", "Fall Guys");
        string epicManifests = Path.Combine(temporary.Path, "epic-manifests");
        string epicInstall = Path.Combine(temporary.Path, "Fortnite");
        Directory.CreateDirectory(steamInstall);
        Directory.CreateDirectory(epicManifests);
        Directory.CreateDirectory(epicInstall);
        await File.WriteAllTextAsync(
            Path.Combine(steamApps, "appmanifest_1097150.acf"),
            "\"AppState\" { \"appid\" \"1097150\" \"name\" \"Fall Guys\" " +
            "\"installdir\" \"Fall Guys\" }");
        await File.WriteAllTextAsync(
            Path.Combine(epicManifests, "fortnite.item"),
            JsonSerializer.Serialize(new
            {
                DisplayName = "Fortnite",
                InstallLocation = epicInstall,
                CatalogItemId = "fortnite-catalog-id",
            }));
        var adapter = new WindowsGameInstallationAdapter(
            [steamApps], [epicManifests]);

        ExternalCapabilityReceipt steam = await adapter.InvokeAsync(
            "game.installed.named",
            Json("""{"provider":"any","title":"Fall Guys"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt epic = await adapter.InvokeAsync(
            "game.installed.named",
            Json("""{"provider":"epic","title":"Fortnite"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(steam.Verified, Is.True);
            Assert.That(steam.Result?.GetProperty("installed").GetBoolean(), Is.True);
            Assert.That(steam.Result?.GetProperty("games")[0]
                .GetProperty("provider").GetString(), Is.EqualTo("steam"));
            Assert.That(epic.Verified, Is.True);
            Assert.That(epic.Result?.GetProperty("installed").GetBoolean(), Is.True);
            Assert.That(epic.Result?.GetProperty("games")[0]
                .GetProperty("provider").GetString(), Is.EqualTo("epic"));
        });
    }

    [Test]
    public async Task RecycleBinEmptyRequiresZeroItemPostread()
    {
        const string output = "{\"ok\":true,\"beforeCount\":3," +
            "\"afterCount\":0,\"effectObserved\":true}";
        var adapter = new WindowsRecycleBinAdapter(new StubProcessRunner(output));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.recyclebin.empty", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("empty").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("afterCount").GetInt32(), Is.Zero);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("windows_recycle_bin_empty_postread"));
        });
    }

    [Test]
    public async Task KnownFolderBackupCreatesListsAndReverifiesAnActualZipHash()
    {
        using TemporaryDirectory temporary = new();
        string documents = Path.Combine(temporary.Path, "documents");
        Directory.CreateDirectory(Path.Combine(documents, "nested"));
        await File.WriteAllTextAsync(Path.Combine(documents, "one.txt"), "uno");
        await File.WriteAllTextAsync(Path.Combine(documents, "nested", "two.txt"), "dos");
        var roots = new Dictionary<string, string[]>
        {
            ["documents"] = [documents],
            ["all_known"] = [documents],
        };
        var adapter = new WindowsKnownBackupAdapter(temporary.Path, roots);

        ExternalCapabilityReceipt created = await adapter.InvokeAsync(
            "backup.known.create", Json("""{"folder":"documents"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt listed = await adapter.InvokeAsync(
            "backup.known.list", Json("""{"limit":10}"""), CancellationToken.None);
        ExternalCapabilityReceipt verified = await adapter.InvokeAsync(
            "backup.known.verify.latest", Json("""{"folder":"documents"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt restored = await adapter.InvokeAsync(
            "backup.known.restore.latest", Json("""{"folder":"documents"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(created.Verified, Is.True);
            Assert.That(created.EffectObserved, Is.True);
            Assert.That(created.Result?.GetProperty("fileCount").GetInt32(), Is.EqualTo(2));
            Assert.That(created.Result?.GetProperty("sha256").GetString(), Has.Length.EqualTo(64));
            Assert.That(listed.Result?.GetProperty("count").GetInt32(), Is.EqualTo(1));
            Assert.That(listed.EffectMayHaveOccurred, Is.False);
            Assert.That(verified.Verified, Is.True);
            Assert.That(verified.EffectMayHaveOccurred, Is.False);
            Assert.That(verified.Result?.GetProperty("verified").GetBoolean(), Is.True);
            Assert.That(restored.Verified, Is.True);
            Assert.That(restored.EffectObserved, Is.True);
            Assert.That(restored.Result?.GetProperty("fileCount").GetInt32(), Is.EqualTo(2));
            string restoreId = restored.Result?.GetProperty("restoreId").GetString()!;
            Assert.That(File.Exists(Path.Combine(temporary.Path, "known-backups", "restored",
                restoreId, "documents", "one.txt")), Is.True);
        });
    }

    [Test]
    public async Task KnownDownloadsDuplicateFinderUsesSizeAndSha256WithoutChanges()
    {
        using TemporaryDirectory temporary = new();
        string downloads = Path.Combine(temporary.Path, "downloads");
        Directory.CreateDirectory(downloads);
        await File.WriteAllTextAsync(Path.Combine(downloads, "one.bin"), "same");
        await File.WriteAllTextAsync(Path.Combine(downloads, "two.bin"), "same");
        await File.WriteAllTextAsync(Path.Combine(downloads, "other.bin"), "else");
        var roots = new Dictionary<string, string[]> { ["downloads"] = [downloads] };
        var adapter = new WindowsKnownFileAdapter(roots);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "filesystem.known.duplicates", Json("""{"folder":"downloads","limit":10}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result?.GetProperty("groupCount").GetInt32(), Is.EqualTo(1));
            Assert.That(receipt.Result?.GetProperty("groups")[0].GetProperty("files")
                .GetArrayLength(), Is.EqualTo(2));
            Assert.That(File.ReadAllText(Path.Combine(downloads, "one.bin")), Is.EqualTo("same"));
        });
    }

    // M132 (owner script t36 «abre steam y ve a la biblioteca», launched cold): the click after an opening waits for
    // the opened application's own window, never looks at another one meanwhile, and then finds the label on it.
    [Test]
    public async Task VisibleClickAfterALaunchWaitsForTheOpenedWindowBeforeLooking()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var focus = new ScriptedFocus(launched: true, windowAfter: 3);
        var ocr = new CountingLocator("ocr", hit: true, hitFromCall: 2);
        var adapter = new WindowsVisibleControlAdapter(
            worker, ocr, vision: null, focus, ShortTiming);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"biblioteca"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("cascadeStage").GetString(), Is.EqualTo("ocr"));
            // Three answers «no window yet», then two looks on the opened window.
            Assert.That(focus.FrontCalls, Is.EqualTo(5));
            Assert.That(worker.Commands.Count, Is.EqualTo(2));
            Assert.That(ocr.Calls, Is.EqualTo(2));
        });
    }

    [Test]
    public async Task VisibleClickAfterALaunchWhoseWindowNeverShowsPressesNothingElsewhere()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var focus = new ScriptedFocus(launched: true, windowAfter: int.MaxValue);
        var ocr = new CountingLocator("ocr", hit: true);
        var adapter = new WindowsVisibleControlAdapter(
            worker, ocr, vision: null, focus, ShortTiming);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"biblioteca"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_not_found"));
            Assert.That(worker.Commands.Count, Is.Zero);
            Assert.That(ocr.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task VisibleClickOnTheOpenedWindowStopsLookingAfterTheOpenedLabelBudget()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var focus = new ScriptedFocus(launched: false, windowAfter: 0);
        var ocr = new CountingLocator("ocr", hit: false);
        var adapter = new WindowsVisibleControlAdapter(
            worker, ocr, vision: null, focus, ShortTiming);
        var clock = Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"counter strike 2"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_not_found"));
            Assert.That(worker.Commands.Count, Is.GreaterThan(1));
            Assert.That(clock.Elapsed, Is.GreaterThanOrEqualTo(ShortTiming.OpenedLabel));
            Assert.That(clock.Elapsed, Is.LessThan(TimeSpan.FromSeconds(5)));
            // An application that was already running is not waited on to draw.
            Assert.That(focus.JudgedDrawn, Is.All.False);
        });
    }

    // M132, measured live: a client launched cold shows its navigation over a blank page and then loads its start
    // page, undoing a click made before. Nothing is looked at or pressed while the page is blank.
    [Test]
    public async Task VisibleClickAfterALaunchDoesNotLookWhileThePageIsBlank()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var focus = new ScriptedFocus(launched: true, windowAfter: 1, drawnAfter: 4);
        var ocr = new CountingLocator("ocr", hit: true);
        var adapter = new WindowsVisibleControlAdapter(
            worker, ocr, vision: null, focus, ShortTiming);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"biblioteca"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(focus.FrontCalls, Is.EqualTo(5));
            Assert.That(focus.JudgedDrawn, Is.All.True);
            Assert.That(worker.Commands.Count, Is.EqualTo(1));
            Assert.That(ocr.Calls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task VisibleClickAfterALaunchLooksAnywayOnceTheSettlingTimeHasPassed()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        // A page that never stops looking blank (a plain dark application) is looked at after the settling time.
        var focus = new ScriptedFocus(launched: true, windowAfter: 0, drawnAfter: int.MaxValue);
        var ocr = new CountingLocator("ocr", hit: true);
        var adapter = new WindowsVisibleControlAdapter(
            worker, ocr, vision: null, focus, ShortTiming);
        var clock = Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"ajustes"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(clock.Elapsed, Is.GreaterThanOrEqualTo(ShortTiming.LaunchSurface - TimeSpan.FromMilliseconds(50)));
            Assert.That(worker.Commands.Count, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task VisibleClickConfirmedLongAfterTheOpeningLooksAtOnce()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var focus = new ScriptedFocus(
            launched: true, windowAfter: 0, drawnAfter: int.MaxValue, noted: TimeSpan.FromSeconds(60));
        var ocr = new CountingLocator("ocr", hit: true);
        var adapter = new WindowsVisibleControlAdapter(
            worker, ocr, vision: null, focus, ShortTiming);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"biblioteca"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(focus.FrontCalls, Is.EqualTo(1));
            Assert.That(worker.Commands.Count, Is.EqualTo(1));
        });
    }

    // v2-u3 «abrí Fotos y andá a Carpetas»: a control already pressed by its identity in the opened application proves
    // it drawn; the next click by label looks at once instead of waiting for a dark page to stop looking blank.
    [Test]
    public async Task VisibleClickByLabelAfterAnIdentifiedPressDoesNotWaitForTheOpening()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Buscar\"," +
            "\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":true,\"authority\":\"windows_uia_or_win32_button_postread\"}",
            NotFoundByUia);
        var focus = new ScriptedFocus(launched: true, windowAfter: 0, drawnAfter: int.MaxValue);
        var ocr = new CountingLocator("ocr", hit: true);
        var adapter = new WindowsVisibleControlAdapter(
            worker, ocr, vision: null, focus, ShortTiming);

        ExternalCapabilityReceipt pressed = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"buscar","controlId":"1.2.3"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"carpetas"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(pressed.Verified, Is.True);
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("cascadeStage").GetString(), Is.EqualTo("ocr"));
            Assert.That(focus.FrontCalls, Is.Zero);
        });
    }

    // M132, measured live: while the label was looked for, the front fell to the person's editor, where the same
    // word was on screen, and it was pressed there. A click after an opening reads the opened window only.
    [Test]
    public async Task VisibleClickAfterAnOpeningIsBoundToTheOpenedWindow()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var focus = new ScriptedFocus(launched: false, windowAfter: 0);
        var adapter = new WindowsVisibleControlAdapter(
            worker, ocr: null, vision: null, focus, ShortTiming);

        _ = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"biblioteca"}"""),
            CancellationToken.None);

        Assert.That(worker.Commands[^1], Does.Contain("\"hwnd\":77"));
    }

    // v3 point 0, fix 1 (this test used to want nothing read while the opened window was not in front, because the
    // tree stage read the window in front; it now reads the bound window by its handle). The opened window behind
    // the person's is read and pressed where it is, and never any other window: every command names its handle.
    [Test]
    public async Task VisibleClickReadsOnlyTheOpenedWindowWhenItIsBehindThePersonsWindow()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var focus = new ScriptedFocus(launched: false, windowAfter: 0);
        var adapter = new WindowsVisibleControlAdapter(
            worker, ocr: null, vision: null, focus, ShortTiming);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"biblioteca"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(worker.Commands, Is.Not.Empty);
            Assert.That(worker.Commands, Has.All.Contain("\"hwnd\":77"));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_not_found"));
        });
    }

    [Test]
    public void DominantColourShareTellsABlankPageFromADrawnOne()
    {
        static byte[] Bitmap(int width, int height, Func<int, (byte B, byte G, byte R)> pixel)
        {
            byte[] bmp = new byte[54 + (width * height * 4)];
            bmp[0] = (byte)'B';
            bmp[1] = (byte)'M';
            BitConverter.GetBytes((short)32).CopyTo(bmp, 28);
            for (int index = 0; index < width * height; index++)
            {
                (byte b, byte g, byte r) = pixel(index);
                bmp[54 + (index * 4)] = b;
                bmp[54 + (index * 4) + 1] = g;
                bmp[54 + (index * 4) + 2] = r;
                bmp[54 + (index * 4) + 3] = 255;
            }
            return bmp;
        }

        // A navigation strip over a black page, and a page of varied content.
        byte[] blank = Bitmap(100, 100, index => index < 1500 ? ((byte)40, (byte)30, (byte)20) : ((byte)0, (byte)0, (byte)0));
        byte[] drawn = Bitmap(100, 100, index => ((byte)(index % 7 * 36), (byte)(index % 5 * 50), (byte)(index % 3 * 80)));

        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlSurface.DominantColourShare(blank), Is.GreaterThan(0.7));
            Assert.That(VisibleControlSurface.DominantColourShare(drawn), Is.LessThan(0.7));
            Assert.That(VisibleControlSurface.DominantColourShare([1, 2, 3]), Is.Null);
        });
    }

    // M132 (owner script t42 «En steam ve a crash bandicoot», 28 s): on a window that was already there the label
    // is looked for twice or three times and the honest «not there» comes in a few seconds.
    [Test]
    public async Task VisibleClickWithoutAnOpeningAnswersNotFoundWithinSeconds()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var ocr = new CountingLocator("ocr", hit: false);
        var adapter = new WindowsVisibleControlAdapter(worker, ocr, vision: null);
        var clock = Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"crash bandicoot"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_not_found"));
            Assert.That(worker.Commands.Count, Is.InRange(2, 3));
            Assert.That(clock.Elapsed, Is.LessThan(TimeSpan.FromSeconds(8)));
            Assert.That(VisibleClickTiming.Default.SettledLabel, Is.LessThanOrEqualTo(TimeSpan.FromSeconds(3)));
            Assert.That(VisibleClickTiming.Default.OpenedLabel, Is.LessThanOrEqualTo(TimeSpan.FromSeconds(10)));
        });
    }

    // r8 (live missions: a label no stage found cost 4.2–4.4 s): a window that was already there and stays exactly the
    // same while the click waits is not drawing the label, so «not found» comes after one look, before anything is
    // pressed.
    [Test]
    public async Task VisibleClickOnAStillWindowAnswersNotFoundAfterOneLook()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var ocr = new CountingLocator("ocr", hit: false);
        int samples = 0;
        var adapter = new WindowsVisibleControlAdapter(
            worker, ocr, vision: null, timing: StillTiming,
            surfaceHash: (_, _) => { samples++; return ValueTask.FromResult<string?>("same"); });
        var clock = Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"crash bandicoot"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_not_found"));
            Assert.That(worker.Commands.Count, Is.EqualTo(1));
            Assert.That(ocr.Calls, Is.EqualTo(1));
            Assert.That(samples, Is.GreaterThanOrEqualTo(2));
            Assert.That(clock.Elapsed, Is.LessThan(StillTiming.SettledLabel));
            Assert.That(VisibleClickTiming.Default.StillFor, Is.LessThan(VisibleClickTiming.Default.Interval));
        });
    }

    // A window that changes while the click waits may be drawing the label: it is looked at again at once and the
    // label that appeared is pressed.
    [Test]
    public async Task VisibleClickOnAChangingWindowLooksAgainAndFindsTheLabel()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var ocr = new CountingLocator("ocr", hit: true, hitFromCall: 2);
        int samples = 0;
        var adapter = new WindowsVisibleControlAdapter(
            worker, ocr, vision: null, timing: StillTiming,
            surfaceHash: (_, _) => ValueTask.FromResult<string?>("frame" + samples++));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"biblioteca"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("cascadeStage").GetString(), Is.EqualTo("ocr"));
            Assert.That(ocr.Calls, Is.EqualTo(2));
        });
    }

    // A window that cannot be captured is waited on as before: the whole interval, then another look.
    [Test]
    public async Task VisibleClickWithoutASurfaceToWatchWaitsTheWholeInterval()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var ocr = new CountingLocator("ocr", hit: false);
        var adapter = new WindowsVisibleControlAdapter(
            worker, ocr, vision: null, timing: StillTiming,
            surfaceHash: (_, _) => ValueTask.FromResult<string?>(null));
        var clock = Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"crash bandicoot"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_not_found"));
            Assert.That(worker.Commands.Count, Is.GreaterThanOrEqualTo(2));
            Assert.That(clock.Elapsed, Is.GreaterThanOrEqualTo(StillTiming.Interval));
        });
    }

    // Review r10: the window watched is the one the look read and the click targets (the hwnd sent to the worker),
    // never whatever holds the front while the click waits.
    [Test]
    public async Task VisibleClickWatchesTheWindowItsLookRead()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var watched = new List<nint>();
        var adapter = new WindowsVisibleControlAdapter(
            worker, new CountingLocator("ocr", hit: false), vision: null, timing: StillTiming,
            surfaceHash: (window, _) => { watched.Add(window); return ValueTask.FromResult<string?>("same"); });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"crash bandicoot"}"""),
            CancellationToken.None);

        Assume.That(receipt.ErrorCode, Is.EqualTo("visible_button_not_found"), "a window in front to look at");
        long looked = JsonDocument.Parse(worker.Commands[0]).RootElement.GetProperty("hwnd").GetInt64();
        Assert.Multiple(() =>
        {
            Assert.That(looked, Is.Not.Zero);
            Assert.That(watched, Is.Not.Empty);
            Assert.That(watched, Is.All.EqualTo((nint)looked));
        });
    }

    // Review r10: a page the previous click navigated to may still be loading behind a still frame; the first click
    // after a click that changed the screen keeps the full wait, the one after it answers after one still look.
    [Test]
    public async Task VisibleClickAfterAScreenChangeKeepsTheFullWait()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var adapter = new WindowsVisibleControlAdapter(
            worker, new CountingLocator("ocr", hit: true, hitFromCall: 1) { HitsUpTo = 1 }, vision: null,
            timing: StillTiming, surfaceHash: (_, _) => ValueTask.FromResult<string?>("same"));

        ExternalCapabilityReceipt navigated = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"biblioteca"}"""), CancellationToken.None);
        Assume.That(navigated.Verified, Is.True);
        int before = worker.Commands.Count;
        ExternalCapabilityReceipt next = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"crash bandicoot"}"""), CancellationToken.None);
        int afterChange = worker.Commands.Count - before;
        before = worker.Commands.Count;
        ExternalCapabilityReceipt still = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"crash bandicoot"}"""), CancellationToken.None);

        Assume.That(next.ErrorCode, Is.EqualTo("visible_button_not_found"), "a window in front to look at");
        Assert.Multiple(() =>
        {
            Assert.That(afterChange, Is.GreaterThanOrEqualTo(2));
            Assert.That(still.ErrorCode, Is.EqualTo("visible_button_not_found"));
            Assert.That(worker.Commands.Count - before, Is.EqualTo(1));
        });
    }

    // Goal v3, analysis r3a M7 (t-scroll-2: 31 s on a label the Character Map just opened never had): once the opened
    // application's interface is up (a tree of InterfaceUp elements or more), a tree that stopped growing on a window
    // that stays still is not drawing the label: «not found» comes well before the opened label's whole wait.
    [Test]
    public async Task VisibleClickAfterAnOpeningStopsWaitingWhenTheTreeStoppedGrowingOnAStillWindow()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundWithTree(120));
        var focus = new ScriptedFocus(launched: true, windowAfter: 0);
        var ocr = new CountingLocator("ocr", hit: false);
        var adapter = new WindowsVisibleControlAdapter(
            worker, ocr, vision: null, focus, TreeTiming,
            surfaceHash: (_, _) => ValueTask.FromResult<string?>("same"));
        var clock = Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"omega"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_not_found"));
            Assert.That(worker.Commands.Count, Is.GreaterThanOrEqualTo(2), "two looks tell the tree did not grow");
            Assert.That(clock.Elapsed, Is.LessThan(TreeTiming.OpenedLabel / 2));
            Assert.That(VisibleClickTiming.Default.OpenedLabel, Is.LessThanOrEqualTo(TimeSpan.FromSeconds(8)));
        });
    }

    // Counter-case (a client launched cold, UI1731): a loading screen has a handful of elements; still and not growing,
    // it is waited on the whole opened label's stretch, since its interface is not up yet.
    [Test]
    public async Task VisibleClickAfterAnOpeningKeepsWaitingOnALoadingScreen()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundWithTree(4));
        var focus = new ScriptedFocus(launched: true, windowAfter: 0);
        var adapter = new WindowsVisibleControlAdapter(
            worker, new CountingLocator("ocr", hit: false), vision: null, focus, TreeTiming,
            surfaceHash: (_, _) => ValueTask.FromResult<string?>("same"));
        var clock = Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"biblioteca"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_not_found"));
            Assert.That(clock.Elapsed, Is.GreaterThanOrEqualTo(TreeTiming.OpenedLabel));
        });
    }

    // Counter-case: a tree that keeps growing is an interface still being built; it is looked at again and the label
    // that appears is pressed.
    [Test]
    public async Task VisibleClickAfterAnOpeningKeepsLookingWhileTheTreeGrows()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(
            NotFoundWithTree(30), NotFoundWithTree(45), NotFoundWithTree(60), NotFoundWithTree(80), NotFoundWithTree(100));
        var focus = new ScriptedFocus(launched: true, windowAfter: 0);
        var ocr = new CountingLocator("ocr", hit: true, hitFromCall: 5);
        var adapter = new WindowsVisibleControlAdapter(
            worker, ocr, vision: null, focus, TreeTiming with { SettledLabel = TimeSpan.Zero },
            surfaceHash: (_, _) => ValueTask.FromResult<string?>("same"));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"biblioteca"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("cascadeStage").GetString(), Is.EqualTo("ocr"));
            Assert.That(ocr.Calls, Is.EqualTo(5));
        });
    }

    private static string NotFoundWithTree(int elements) =>
        NotFoundByUia[..^1] + ",\"treeSize\":" + elements + "}";

    private static readonly VisibleClickTiming TreeTiming = VisibleClickTiming.Default with
    {
        LaunchSurface = TimeSpan.FromMilliseconds(200),
        OpenedLabel = TimeSpan.FromMilliseconds(2400),
        SettledLabel = TimeSpan.FromMilliseconds(200),
        Interval = TimeSpan.FromMilliseconds(60),
        StillSample = TimeSpan.FromMilliseconds(20),
        StillFor = TimeSpan.FromMilliseconds(50),
    };

    private static readonly VisibleClickTiming StillTiming = VisibleClickTiming.Default with
    {
        SettledLabel = TimeSpan.FromMilliseconds(900),
        Interval = TimeSpan.FromMilliseconds(400),
        StillSample = TimeSpan.FromMilliseconds(30),
        StillFor = TimeSpan.FromMilliseconds(90),
    };

    private const string NotFoundByUia =
        "{\"version\":1,\"ok\":false,\"effectObserved\":false," +
        "\"error\":\"visible_button_not_found\",\"name\":\"\"," +
        "\"controlIdentity\":\"\",\"absentOrDisabled\":false}";

    private static readonly VisibleClickTiming ShortTiming = VisibleClickTiming.Default with
    {
        LaunchSurface = TimeSpan.FromMilliseconds(400),
        ReusedSurface = TimeSpan.FromMilliseconds(100),
        OpenedLabel = TimeSpan.FromMilliseconds(1500),
        SettledLabel = TimeSpan.FromMilliseconds(50),
        Interval = TimeSpan.FromMilliseconds(20),
    };

    [Test]
    public async Task NamedSandboxFilesDiffAndMoveWithHashPostreads()
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "filesystem-sandbox");
        Directory.CreateDirectory(sandbox);
        await File.WriteAllTextAsync(Path.Combine(sandbox, "README.md"), "uno\ndos\n");
        await File.WriteAllTextAsync(Path.Combine(sandbox, "README.backup.md"), "uno\ntres\n");
        await File.WriteAllTextAsync(Path.Combine(sandbox, "backup.txt"), "payload");
        var adapter = new WindowsSandboxNamedFileAdapter(temporary.Path);

        ExternalCapabilityReceipt diff = await adapter.InvokeAsync(
            "filesystem.sandbox.diff.named",
            Json("""{"leftFileName":"README.md","rightFileName":"README.backup.md"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt moved = await adapter.InvokeAsync(
            "filesystem.sandbox.move.named",
            Json("""{"sourceFileName":"backup.txt","destinationRelativePath":"logs/backup.txt"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(diff.Verified, Is.True);
            Assert.That(diff.EffectMayHaveOccurred, Is.False);
            Assert.That(diff.Result?.GetProperty("changedLines")[0].GetInt32(), Is.EqualTo(2));
            Assert.That(moved.Verified, Is.True);
            Assert.That(File.Exists(Path.Combine(sandbox, "logs", "backup.txt")), Is.True);
            Assert.That(File.Exists(Path.Combine(sandbox, "backup.txt")), Is.False);
        });
    }

    [Test]
    public async Task NamedSandboxDiffResolvesOnlyTheExactFileName()
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "filesystem-sandbox");
        Directory.CreateDirectory(sandbox);
        await File.WriteAllTextAsync(Path.Combine(sandbox, "README.md"), "uno\n");
        await File.WriteAllTextAsync(Path.Combine(sandbox, "README.backup.md"), "dos\n");
        var adapter = new WindowsSandboxNamedFileAdapter(temporary.Path);

        ExternalCapabilityReceipt diff = await adapter.InvokeAsync(
            "filesystem.sandbox.diff.named",
            Json("""{"leftFileName":"README.md","rightFileName":"backup"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(diff.Verified, Is.False);
            Assert.That(diff.ErrorCode, Is.EqualTo("sandbox_named_file_not_found"));
        });
    }

    [Test]
    public async Task DesktopFolderOpenRequiresScriptPostreadBeforeSuccess()
    {
        using TemporaryDirectory temporary = new();
        string folderScript = Path.Combine(temporary.Path, "KnownFolderOpen.ps1");
        string selectScript = Path.Combine(temporary.Path, "DesktopSelectAll.ps1");
        await File.WriteAllTextAsync(folderScript, "# test fixture");
        await File.WriteAllTextAsync(selectScript, "# test fixture");
        var adapter = new WindowsDesktopInteractionAdapter(
            new StubProcessRunner(
                "{\"version\":1,\"ok\":true,\"effectObserved\":true," +
                "\"folder\":\"downloads\",\"authority\":\"windows_shell_location_postread\"}"),
            folderScript,
            Path.Combine(temporary.Path, "KnownFileOpen.ps1"),
            selectScript,
            Path.Combine(temporary.Path, "DesktopKeyPress.ps1"));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "filesystem.folder.open",
            Json("""{"folder":"downloads"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("folder").GetString(), Is.EqualTo("downloads"));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("windows_shell_location_postread"));
        });
    }

    [Test]
    public async Task LatestKnownFileOpenRequiresAProcessPostreadReceipt()
    {
        using TemporaryDirectory temporary = new();
        string folderScript = Path.Combine(temporary.Path, "KnownFolderOpen.ps1");
        string fileScript = Path.Combine(temporary.Path, "KnownFileOpen.ps1");
        string selectScript = Path.Combine(temporary.Path, "DesktopSelectAll.ps1");
        await File.WriteAllTextAsync(folderScript, "# test fixture");
        await File.WriteAllTextAsync(fileScript, "# test fixture");
        await File.WriteAllTextAsync(selectScript, "# test fixture");
        var adapter = new WindowsDesktopInteractionAdapter(
            new StubProcessRunner(
                "{\"version\":1,\"ok\":true,\"effectObserved\":true," +
                "\"folder\":\"downloads\",\"fileName\":\"report.pdf\"," +
                "\"authority\":\"known_folder_latest_safe_file_process_postread\"}"),
            folderScript,
            fileScript,
            selectScript,
            Path.Combine(temporary.Path, "DesktopKeyPress.ps1"));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "filesystem.file.open.latest",
            Json("""{"folder":"downloads"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("fileName").GetString(),
                Is.EqualTo("report.pdf"));
        });
    }

    [Test]
    public async Task AllowedKeyPressRequiresWin32AcceptedEventReceipt()
    {
        using TemporaryDirectory temporary = new();
        string folderScript = Path.Combine(temporary.Path, "KnownFolderOpen.ps1");
        string fileScript = Path.Combine(temporary.Path, "KnownFileOpen.ps1");
        string selectScript = Path.Combine(temporary.Path, "DesktopSelectAll.ps1");
        string keyScript = Path.Combine(temporary.Path, "DesktopKeyPress.ps1");
        await File.WriteAllTextAsync(folderScript, "# test fixture");
        await File.WriteAllTextAsync(fileScript, "# test fixture");
        await File.WriteAllTextAsync(selectScript, "# test fixture");
        await File.WriteAllTextAsync(keyScript, "# test fixture");
        var runner = new CapturingProcessRunner("{\"version\":1,\"ok\":true}");
        var keyboard = new FakeDesktopKeyboard();
        var adapter = new WindowsDesktopInteractionAdapter(
            runner,
            folderScript,
            fileScript,
            selectScript,
            keyScript,
            keyboard);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.key.press",
            Json("""{"key":"escape"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("key").GetString(), Is.EqualTo("escape"));
            Assert.That(receipt.Result?.GetProperty("acceptedEvents").GetInt32(), Is.EqualTo(2));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("win32_sendinput_return_count"));
            Assert.That(keyboard.Chords, Has.Count.EqualTo(1));
            Assert.That(keyboard.Chords[0], Is.EqualTo(new ushort[] { 0x1B }));
            Assert.That(runner.Arguments, Is.Empty, "a key is sent in-process, without a PowerShell");
        });
    }

    [Test]
    public async Task ClipboardPasteRequiresNonemptyClipboardStableFocusAndAcceptedChord()
    {
        using TemporaryDirectory temporary = new();
        string folderScript = Path.Combine(temporary.Path, "KnownFolderOpen.ps1");
        string fileScript = Path.Combine(temporary.Path, "KnownFileOpen.ps1");
        string selectScript = Path.Combine(temporary.Path, "DesktopSelectAll.ps1");
        string keyScript = Path.Combine(temporary.Path, "DesktopKeyPress.ps1");
        foreach (string path in new[] { folderScript, fileScript, selectScript, keyScript })
            await File.WriteAllTextAsync(path, "# test fixture");
        var runner = new CapturingProcessRunner(
            "{\"version\":1,\"ok\":true,\"effectObserved\":true," +
            "\"clipboardFormatCount\":2,\"acceptedEvents\":4,\"expectedEvents\":4," +
            "\"foregroundProcessIdBefore\":42,\"foregroundProcessIdAfter\":42," +
            "\"authority\":\"win32_clipboard_nonempty_foreground_identity_sendinput_acceptance\"}");
        var adapter = new WindowsDesktopInteractionAdapter(
            runner, folderScript, fileScript, selectScript, keyScript);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "clipboard.paste", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(runner.Arguments, Does.Contain("-PasteClipboard"));
            Assert.That(receipt.Result?.GetProperty("acceptedEvents").GetInt32(), Is.EqualTo(4));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("win32_clipboard_nonempty_foreground_identity_sendinput_acceptance"));
        });
    }

    [Test]
    public async Task ClipboardCopyRequiresStableFocusAcceptedChordAndSequenceChange()
    {
        using TemporaryDirectory temporary = new();
        string folderScript = Path.Combine(temporary.Path, "KnownFolderOpen.ps1");
        string fileScript = Path.Combine(temporary.Path, "KnownFileOpen.ps1");
        string selectScript = Path.Combine(temporary.Path, "DesktopSelectAll.ps1");
        string keyScript = Path.Combine(temporary.Path, "DesktopKeyPress.ps1");
        foreach (string path in new[] { folderScript, fileScript, selectScript, keyScript })
            await File.WriteAllTextAsync(path, "# test fixture");
        var runner = new CapturingProcessRunner(
            "{\"version\":1,\"ok\":true,\"effectObserved\":true," +
            "\"clipboardFormatCount\":1,\"clipboardSequenceBefore\":7," +
            "\"clipboardSequenceAfter\":8,\"acceptedEvents\":4,\"expectedEvents\":4," +
            "\"foregroundProcessIdBefore\":42,\"foregroundProcessIdAfter\":42," +
            "\"authority\":\"win32_foreground_identity_sendinput_clipboard_sequence_postread\"}");
        var adapter = new WindowsDesktopInteractionAdapter(
            runner, folderScript, fileScript, selectScript, keyScript);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "clipboard.copy", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(runner.Arguments, Does.Contain("-CopySelection"));
            Assert.That(receipt.Result?.GetProperty("acceptedEvents").GetInt32(), Is.EqualTo(4));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("win32_foreground_identity_sendinput_clipboard_sequence_postread"));
        });
    }

    [Test]
    public async Task TextInputIsSentInProcessAndPointerInputUsesTheVerifiedDesktopInputScript()
    {
        using TemporaryDirectory temporary = new();
        string folderScript = Path.Combine(temporary.Path, "KnownFolderOpen.ps1");
        string fileScript = Path.Combine(temporary.Path, "KnownFileOpen.ps1");
        string selectScript = Path.Combine(temporary.Path, "DesktopSelectAll.ps1");
        string keyScript = Path.Combine(temporary.Path, "DesktopKeyPress.ps1");
        foreach (string path in new[] { folderScript, fileScript, selectScript, keyScript })
            await File.WriteAllTextAsync(path, "# test fixture");
        var runner = new CapturingProcessRunner(
            "{\"version\":1,\"ok\":true,\"effectObserved\":true," +
            "\"acceptedEvents\":2,\"authority\":\"win32_sendinput_return_count\"}");
        var keyboard = new FakeDesktopKeyboard();
        var adapter = new WindowsDesktopInteractionAdapter(
            runner, folderScript, fileScript, selectScript, keyScript, keyboard);

        ExternalCapabilityReceipt typed = await adapter.InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);
        string[] typingArguments = runner.Arguments.ToArray();
        ExternalCapabilityReceipt pointer = await adapter.InvokeAsync(
            "input.pointer.control", Json("""{"action":"move_center"}"""),
            CancellationToken.None);
        string[] pointerArguments = runner.Arguments.ToArray();
        ExternalCapabilityReceipt layout = await adapter.InvokeAsync(
            "input.keyboard.layout", Json("""{"language":"spanish"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            // BAXY Renew (notebook), F004: without the field's messages nothing reads the text back, so it is not told
            // verified; what Windows accepted travels with it.
            Assert.That(typed.Verified, Is.False);
            Assert.That(typed.ErrorCode, Is.EqualTo("input_text_not_read_back"));
            Assert.That(typed.Result?.GetProperty("readBack").GetBoolean(), Is.False);
            Assert.That(keyboard.Texts, Is.EqualTo(new[] { "hola" }));
            Assert.That(typed.Result?.GetProperty("acceptedEvents").GetInt32(), Is.EqualTo(8));
            Assert.That(typed.Result?.GetProperty("textLength").GetInt32(), Is.EqualTo(4));
            Assert.That(typingArguments, Is.Empty, "typing starts no PowerShell");
            Assert.That(pointer.Verified, Is.True);
            Assert.That(layout.Verified, Is.True);
            Assert.That(pointerArguments, Does.Contain("-PointerAction"));
            Assert.That(pointerArguments, Does.Contain("move_center"));
            Assert.That(runner.Arguments, Does.Contain("-Layout"));
            Assert.That(runner.Arguments, Does.Contain("spanish"));
        });
    }

    [Test]
    public async Task MicrophoneMuteRequiresCaptureEndpointPostread()
    {
        var endpoint = new FakeAudioEndpoint("capture-private", muted: false);
        var adapter = new WindowsMicrophoneAdapter(() => endpoint);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.microphone.mute", Json("""{"state":true}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(endpoint.ReadMuted(), Is.True);
            Assert.That(receipt.Result?.GetProperty("baselineMuted").GetBoolean(), Is.False);
            Assert.That(receipt.Result?.GetProperty("muted").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("windows_core_audio_capture_endpoint_postread"));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("capture-private"));
        });
    }

    // Owner's test 2026-09-21 (turn 205): «activa mi micrófono» on an already
    // active microphone ended in an unobserved effect. The state is the fact,
    // said before any boundary is crossed.
    [TestCase(true, "microphone_already_muted")]
    [TestCase(false, "microphone_already_unmuted")]
    public async Task MicrophoneStateAlreadySatisfiedIsANamedFactBeforeTheEffectBoundary(
        bool state, string expectedError)
    {
        var endpoint = new FakeAudioEndpoint("capture-private", muted: state);
        var adapter = new WindowsMicrophoneAdapter(() => endpoint);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.microphone.mute", Json($$"""{"state":{{(state ? "true" : "false")}}}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(expectedError));
            Assert.That(endpoint.ReadMuted(), Is.EqualTo(state));
        });
    }

    [Test]
    public async Task MicrophoneUnmuteIsVerifiedByTheCaptureEndpointPostread()
    {
        var endpoint = new FakeAudioEndpoint("capture-private", muted: true);
        var adapter = new WindowsMicrophoneAdapter(() => endpoint);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.microphone.mute", Json("""{"state":false}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(endpoint.ReadMuted(), Is.False);
            Assert.That(receipt.Result?.GetProperty("muted").GetBoolean(), Is.False);
        });
    }

    [Test]
    public async Task RelativeVolumeUsesObservedOutputEndpointAndPreservesMute()
    {
        var endpoint = new FakeAudioEndpoint("output-private", muted: false, volume: 0.40f);
        var adapter = new WindowsAudioAdjustmentAdapter(() => endpoint);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.volume.adjust",
            Json("""{"amount":10,"direction":"up"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("baselineLevel").GetInt32(), Is.EqualTo(40));
            Assert.That(receipt.Result?.GetProperty("level").GetInt32(), Is.EqualTo(50));
            Assert.That(endpoint.ReadMuted(), Is.False);
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("output-private"));
        });
    }

    // M54 (v3b-final F-w02-t4, F-w11-t3): «súbele harto a la música» with the output at 100 % and muted ended in
    // «no se pudo observar el cambio». The level already at the end asked is the fact, with the mute that explains
    // the silence, said before any boundary is crossed.
    [TestCase(1.0f, true, "up", "volume_already_at_maximum_muted")]
    [TestCase(1.0f, false, "up", "volume_already_at_maximum")]
    [TestCase(0.0f, false, "down", "volume_already_at_minimum")]
    public async Task RelativeVolumeAlreadyAtTheAskedEndIsANamedFactBeforeTheEffectBoundary(
        float volume, bool muted, string direction, string expectedError)
    {
        var endpoint = new FakeAudioEndpoint("output-private", muted: muted, volume: volume);
        var adapter = new WindowsAudioAdjustmentAdapter(() => endpoint);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.volume.adjust",
            Json($$"""{"amount":20,"direction":"{{direction}}"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(expectedError));
            Assert.That(endpoint.ReadVolumeScalar(), Is.EqualTo(volume));
            Assert.That(endpoint.ReadMuted(), Is.EqualTo(muted));
        });
    }

    [Test]
    public async Task AudioPostreadExceptionAfterSetPreservesAmbiguousEffect()
    {
        var endpoint = new PostDispatchFailingAudioEndpoint();
        var adapter = new WindowsAudioAdjustmentAdapter(() => endpoint);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.volume.adjust",
            Json("""{"direction":"up","amount":10}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo("audio_output_endpoint_unavailable"));
            Assert.That(endpoint.SetCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task RunnerExceptionAfterDispatchBoundaryPreservesAmbiguousEffect()
    {
        var runner = new ThrowingProcessRunner(
            new IOException("simulated receipt loss after process dispatch"));
        var adapter = new WindowsRecycleBinAdapter(runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.recyclebin.empty", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(runner.Calls, Is.EqualTo(1));
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo("recycle_bin_empty_failed"));
        });
    }

    [Test]
    public async Task RequestedCancellationAfterDispatchBoundaryReturnsAmbiguousReceipt()
    {
        using var cancellation = new CancellationTokenSource();
        var runner = new CancelingProcessRunner(cancellation);
        var adapter = new WindowsRecycleBinAdapter(runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.recyclebin.empty", Json("{}"), cancellation.Token);

        Assert.Multiple(() =>
        {
            Assert.That(runner.Calls, Is.EqualTo(1));
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo("recycle_bin_empty_failed"));
        });
    }

    [Test]
    public void RequestedCancellationBeforeDispatchBoundaryStillPropagatesWithoutDispatch()
    {
        using var cancellation = new CancellationTokenSource();
        var runner = new CancelingProcessRunner(cancellation);
        var adapter = new WindowsRecycleBinAdapter(runner);
        cancellation.Cancel();

        Assert.ThrowsAsync<OperationCanceledException>(async () =>
            await adapter.InvokeAsync(
                "system.recyclebin.empty", Json("{}"), cancellation.Token));
        Assert.That(runner.Calls, Is.Zero);
    }

    [Test]
    public async Task RelativeBrightnessRequiresPerMonitorPostread()
    {
        using TemporaryDirectory temporary = new();
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path, temporary.Path,
            new StubProcessRunner(
                "{\"ok\":true,\"effectObserved\":true," +
                "\"baselineValues\":[40],\"values\":[30]}"));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.settings.adjust",
            Json("""{"amount":10,"direction":"down","setting":"brightness"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("baselineValues")[0].GetInt32(), Is.EqualTo(40));
            Assert.That(receipt.Result?.GetProperty("values")[0].GetInt32(), Is.EqualTo(30));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("wmi_monitor_brightness_relative_postread"));
        });
    }

    [Test]
    public async Task BrightnessAlreadyAtTheAskedLevelReturnsAtOnceUnchanged()
    {
        // Ronda 22 (r18 t4-c04 t2): «pon el brillo al 40» again with it at 40 took 10.2 s waiting for a change.
        using TemporaryDirectory temporary = new();
        var runner = new StubProcessRunner(
            "{\"ok\":true,\"effectObserved\":false,\"changed\":false," +
            "\"baselineValues\":[40],\"values\":[40]}");
        var adapter = new WindowsDeviceControlAdapter(temporary.Path, temporary.Path, runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.settings.set",
            Json("""{"setting":"brightness","value":40}"""),
            CancellationToken.None);
        string script = runner.LastArguments[3];
        int sameLevel = script.IndexOf("changed=$false", StringComparison.Ordinal);
        int firstSet = script.IndexOf("WmiSetBrightness", StringComparison.Ordinal);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.StateAlreadyReached, Is.True);
            Assert.That(receipt.Result?.GetProperty("changed").GetBoolean(), Is.False);
            Assert.That(receipt.Result?.GetProperty("baselineValues")[0].GetInt32(), Is.EqualTo(40));
            Assert.That(sameLevel, Is.GreaterThanOrEqualTo(0));
            Assert.That(firstSet, Is.GreaterThan(sameLevel), "the same level is answered before any set");
        });
    }

    [Test]
    public async Task BrightnessAtAnotherLevelStillSetsAndVerifiesTheChange()
    {
        // Contracaso: 30 → 40 still applies and verifies the change.
        using TemporaryDirectory temporary = new();
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path, temporary.Path,
            new StubProcessRunner(
                "{\"ok\":true,\"effectObserved\":true,\"changed\":true," +
                "\"baselineValues\":[30],\"values\":[40]}"));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.settings.set",
            Json("""{"setting":"brightness","value":40}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.StateAlreadyReached, Is.False);
            Assert.That(receipt.Result?.GetProperty("changed").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("baselineValues")[0].GetInt32(), Is.EqualTo(30));
        });
    }

    [Test]
    public async Task BrightnessSetThatDidNotReachTheLevelStillFails()
    {
        // Contracaso: a set whose post-read differs is not done, whatever was asked.
        using TemporaryDirectory temporary = new();
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path, temporary.Path,
            new StubProcessRunner(
                "{\"ok\":false,\"effectObserved\":true,\"changed\":true," +
                "\"baselineValues\":[30],\"values\":[30]}"));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.settings.set",
            Json("""{"setting":"brightness","value":40}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("brightness_postread_failed"));
            Assert.That(receipt.StateAlreadyReached, Is.False);
        });
    }

    [TestCase("system.settings.set", """{"setting":"brightness","value":30}""")]
    [TestCase("system.settings.adjust", """{"setting":"brightness","direction":"down","amount":10}""")]
    [TestCase("system.settings.status", """{"setting":"brightness"}""")]
    public async Task BrightnessOnAMonitorThatDoesNotExposeItIsTheComputersLimit(string operation, string arguments)
    {
        // Encargo H2 (redpc, estado_antes «Brightness []»: WMI answers its brightness classes with «not supported»): the
        // absence is read before anything is changed and answered as such, never as a change left unconfirmed.
        using TemporaryDirectory temporary = new();
        var runner = new StubProcessRunner(
            "{\"ok\":false,\"effectObserved\":false,\"error\":\"brightness_not_supported\"}");
        var adapter = new WindowsDeviceControlAdapter(temporary.Path, temporary.Path, runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(operation, Json(arguments), CancellationToken.None);
        string script = runner.LastArguments[3];
        int absent = script.IndexOf("Write-BaxyBrightnessAbsent;exit 2", StringComparison.Ordinal);
        int firstSet = script.IndexOf("Invoke-CimMethod", StringComparison.Ordinal);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(WindowsDeviceControlAdapter.BrightnessNotSupported));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(script, Does.Contain("-ne 'NotSupported'"), "only WMI's «not supported» is the absence");
            Assert.That(absent, Is.GreaterThan(0));
            Assert.That(firstSet < 0 || absent < firstSet, Is.True, "the absence is answered before any set");
        });
    }

    [Test]
    public async Task DoNotDisturbRequiresObservedWindowsToggleState()
    {
        using TemporaryDirectory temporary = new();
        var runner = new StubProcessRunner(
            "{\"ok\":true,\"effectObserved\":true,\"before\":0,\"value\":1}");
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path, temporary.Path,
            runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.settings.set",
            Json("""{"setting":"do_not_disturb","value":1}"""),
            CancellationToken.None);
        string script = runner.LastArguments[3];
        int firstProbe = script.IndexOf(
            "$toggle=$root.FindFirst",
            StringComparison.Ordinal);
        int firstSleep = script.IndexOf("Start-Sleep", StringComparison.Ordinal);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("value").GetInt32(), Is.EqualTo(1));
            Assert.That(receipt.Result?.GetProperty("before").GetInt32(), Is.EqualTo(0));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("windows_uia_notifications_toggle_postread"));
            Assert.That(firstProbe, Is.GreaterThanOrEqualTo(0));
            Assert.That(firstSleep, Is.GreaterThan(firstProbe));
            Assert.That(script, Does.Contain("$launchProbe"));
            Assert.That(script, Does.Contain("$toggleProbe"));
        });
    }

    [Test]
    public async Task NamedWifiResolvesOneSavedProfileBeforeVerifiedConnect()
    {
        using TemporaryDirectory temporary = new();
        var delays = new RecordingDelay();
        var runner = new SequencedProcessRunner([
            "{\"profiles\":[\"Galaxy Phone 5G 0000\",\"Other\"]}",
            "{\"profiles\":[\"Galaxy Phone 5G 0000\",\"Other\"]}",
            "",
            "{\"connected\":true,\"profile\":\"Galaxy Phone 5G 0000\"}",
        ]);
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path, temporary.Path, runner, delays.DelayAsync);

        // A part of the name is another network: nothing is connected (BAXY Renew audit 2026-10-15).
        ExternalCapabilityReceipt partial = await adapter.InvokeAsync(
            "wifi.connect.named",
            Json("""{"profileName":"galaxy"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "wifi.connect.named",
            Json("""{"profileName":"galaxy phone 5g 0000"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(partial.Verified, Is.False);
            Assert.That(partial.ErrorCode, Is.EqualTo("wifi_profile_not_found"));
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("connected").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("Galaxy"));
            Assert.That(runner.Calls, Is.EqualTo(4));
            Assert.That(delays.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task WifiDisconnectVerifiesImmediatePostreadWithoutDelay()
    {
        using TemporaryDirectory temporary = new();
        var delays = new RecordingDelay();
        var runner = new SequencedProcessRunner([
            "",
            "{\"connected\":false,\"profile\":\"\"}",
        ]);
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path,
            temporary.Path,
            runner,
            delays.DelayAsync);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "wifi.disconnect",
            Json("{}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("connected").GetBoolean(), Is.False);
            Assert.That(runner.Calls, Is.EqualTo(2));
            Assert.That(delays.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task WifiConnectFailureRetainsFifteenSecondRetryHorizon()
    {
        using TemporaryDirectory temporary = new();
        var delays = new RecordingDelay();
        var runner = new SequencedProcessRunner([
            "{\"profiles\":[\"Casa\"]}",
            "",
            "{\"connected\":false,\"profile\":\"\"}",
        ]);
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path,
            temporary.Path,
            runner,
            delays.DelayAsync);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "wifi.connect.named",
            Json("""{"profileName":"Casa"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("wifi_connect_not_verified"));
            Assert.That(runner.Calls, Is.EqualTo(33));
            AssertRetryHorizon(delays, expectedIntervals: 30, intervalMilliseconds: 500);
        });
    }

    [Test]
    public async Task WifiDisconnectFailureRetainsSixSecondRetryHorizon()
    {
        using TemporaryDirectory temporary = new();
        var delays = new RecordingDelay();
        var runner = new SequencedProcessRunner([
            "",
            "{\"connected\":true,\"profile\":\"Casa\"}",
        ]);
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path,
            temporary.Path,
            runner,
            delays.DelayAsync);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "wifi.disconnect",
            Json("{}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("wifi_disconnect_not_verified"));
            Assert.That(runner.Calls, Is.EqualTo(22));
            AssertRetryHorizon(delays, expectedIntervals: 20, intervalMilliseconds: 300);
        });
    }

    [Test]
    public async Task EnsureWifiConnectedReturnsOnlyAnObservedCurrentSavedProfile()
    {
        using TemporaryDirectory temporary = new();
        var runner = new WifiProcessRunner();
        var adapter = new WindowsDeviceControlAdapter(temporary.Path, temporary.Path, runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "wifi.ensure.connected", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result?.GetProperty("connected").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("Casa"));
        });
    }

    [Test]
    public async Task WifiStatusRequiresTwoStableReadsAndHidesProfileName()
    {
        using TemporaryDirectory temporary = new();
        var runner = new SequencedProcessRunner([
            "{\"connected\":true,\"profile\":\"Private WiFi\"}",
            "{\"connected\":true,\"profile\":\"Private WiFi\"}",
        ]);
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path, temporary.Path, runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "wifi.status", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result?.GetProperty("connected").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("profileId").GetString(),
                Does.StartWith("wifi_"));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("netsh_wlan_status_secondread"));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("Private WiFi"));
            Assert.That(runner.Calls, Is.EqualTo(2));
        });
    }

    [Test]
    public async Task WifiStatusRejectsConnectionChangeBetweenReads()
    {
        using TemporaryDirectory temporary = new();
        var runner = new SequencedProcessRunner([
            "{\"connected\":false,\"profile\":\"\"}",
            "{\"connected\":true,\"profile\":\"Private WiFi\"}",
        ]);
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path, temporary.Path, runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "wifi.status", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("wifi_status_changed_during_read"));
            Assert.That(receipt.EffectObserved, Is.False);
        });
    }

    [Test]
    [Explicit("Reads the actual Windows WLAN state twice without changing it.")]
    public async Task WifiStatusReadsActualWindowsStateTwice()
    {
        using TemporaryDirectory temporary = new();
        var adapter = new WindowsDeviceControlAdapter(temporary.Path, temporary.Path);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "wifi.status", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result?.GetProperty("connected").ValueKind,
                Is.EqualTo(JsonValueKind.True).Or.EqualTo(JsonValueKind.False));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("netsh_wlan_status_secondread"));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("profile\""));
        });
    }

    // BAXY Renew (2026-10-15): web.search asks only the source the model named, with the arguments it typed, and
    // returns what that source returned. These tests answer each source from a stub and check that the receipt says
    // exactly that: no source chosen by the query's words, no result judged, no page read for its sentences.
    private const string ProjectUserAgent = @"^BAXY/\d+\.\d+ \(https://github\.com/REDSOULTM/baxy-assistant\)$";

    private static WebBrowserAdapter SearchAdapter(TemporaryDirectory temporary, HttpClient http, EspnScheduleSource? sports = null) =>
        new(new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused")), http, sports: sports);

    // The general engine's results come back in its order, title, url and snippet as it gave them (its markup
    // removed), bounded by limit; only what is structurally no result is left out: the engine's own links and
    // addresses that are not http or https. A result that shares no word with the query is still a result.
    [Test]
    public async Task AWebSearchReturnsTheEnginesResultsAsItGaveThem()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["lite.duckduckgo.com"] = new(HttpStatusCode.OK, SearchResultsPage(
                ("Unrelated marketplace", "https://example.com/shop", "Discount products"),
                ("More results", "https://duckduckgo.com/?q=more", "next page"),
                ("Calculadora de WhatsApp", "ftp://files.example.com/calc", "no web page"),
                ("Windows 11 Calculator help", "https://support.example.com/windows/calculator", "Use Calculator with WhatsApp"),
                ("Third", "https://example.org/third", "")), "text/html"),
        };
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"Windows 11 calculator","limit":2}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.EffectObserved, Is.False);
            JsonElement result = receipt.Result!.Value;
            Assert.That(result.GetProperty("version").GetInt32(), Is.EqualTo(1));
            Assert.That(result.GetProperty("source").GetString(), Is.EqualTo("web"));
            Assert.That(result.GetProperty("query").GetString(), Is.EqualTo("Windows 11 calculator"));
            Assert.That(result.GetProperty("authority").GetString(), Is.EqualTo("duckduckgo_lite_https"));
            Assert.That(result.GetProperty("resultCount").GetInt32(), Is.EqualTo(2));
            Assert.That(result.TryGetProperty("sent", out _), Is.False);
            JsonElement results = result.GetProperty("results");
            Assert.That(results[0].GetProperty("title").GetString(), Is.EqualTo("Unrelated marketplace"));
            Assert.That(results[0].GetProperty("url").GetString(), Is.EqualTo("https://example.com/shop"));
            Assert.That(results[0].GetProperty("snippet").GetString(), Is.EqualTo("Discount products"));
            Assert.That(results[1].GetProperty("url").GetString(), Is.EqualTo("https://support.example.com/windows/calculator"));
            Assert.That(results[1].GetProperty("snippet").GetString(), Is.EqualTo("Use Calculator with WhatsApp"));
            Assert.That(handler.Asked.Select(asked => asked.Uri.Host), Is.EqualTo(new[] { "lite.duckduckgo.com" }));
        });
    }

    [Test]
    public async Task AWebSearchSaysABlockPageIsUnavailableAndAnEmptyResultsPageHasNoResults()
    {
        using TemporaryDirectory temporary = new();
        using var blocked = new HttpClient(new StubHttpHandler(
            "<html><body><form>Please verify you are a human</form></body></html>"));
        using WebBrowserAdapter blockedAdapter = SearchAdapter(temporary, blocked);
        using var empty = new HttpClient(new StubHttpHandler(SearchResultsPage()));
        using WebBrowserAdapter emptyAdapter = SearchAdapter(temporary, empty);
        using var unreachable = new HttpClient(new SearchSourcesHttpHandler());
        using WebBrowserAdapter unreachableAdapter = SearchAdapter(temporary, unreachable);

        ExternalCapabilityReceipt block = await blockedAdapter.InvokeAsync(
            "web.search", Json("""{"query":"Windows 11 calculator"}"""), CancellationToken.None);
        ExternalCapabilityReceipt none = await emptyAdapter.InvokeAsync(
            "web.search", Json("""{"query":"Windows 11 calculator"}"""), CancellationToken.None);
        ExternalCapabilityReceipt down = await unreachableAdapter.InvokeAsync(
            "web.search", Json("""{"query":"Windows 11 calculator"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(block.Verified, Is.False);
            Assert.That(block.ErrorCode, Is.EqualTo("web_search_unavailable"));
            Assert.That(block.Result, Is.Null);
            Assert.That(none.Verified, Is.False);
            Assert.That(none.ErrorCode, Is.EqualTo("web_search_no_results"));
            Assert.That(down.ErrorCode, Is.EqualTo("web_search_unavailable"));
            Assert.That(new[] { block, none, down }, Has.All.Matches<ExternalCapabilityReceipt>(
                receipt => !receipt.EffectObserved && !receipt.EffectMayHaveOccurred));
        });
    }

    // Uso real tanda 4c «en qué lugares puedo pedir comida para llevar cerca»: with nearby, this PC's city and its
    // country (M81: Curico is also in Indiana), read from its public address, join the query; no coordinates
    // leave, and the receipt says the query as it was sent.
    [Test]
    public async Task ASearchNearbyCarriesThisPcsCityAndCountryAndNothingElse()
    {
        string page = SearchResultsPage(
            ("Comida para llevar en Curico", "https://example.com/valpo", "Locales de comida para llevar"));
        var handler = new RoutingHttpHandler(page,
            """{"success":true,"country":"Chile","region":"Curico","city":"Curico","latitude":-34.9828,"longitude":-71.2394}""");
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"comida para llevar","nearby":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("query").GetString(), Is.EqualTo("comida para llevar Curico, Chile"));
            Assert.That(handler.Asked.Where(uri => !uri.Host.Contains("ipwho", StringComparison.Ordinal)),
                Has.All.Matches<Uri>(uri => !uri.Query.Contains("33.03", StringComparison.Ordinal)
                    && !uri.Query.Contains("71.62", StringComparison.Ordinal)));
        });
    }

    [Test]
    public async Task ASearchNearbyWithoutThisPcsPlaceIsAnHonestAbsenceNotAGenericSearch()
    {
        var handler = new RoutingHttpHandler(SearchResultsPage(("x", "https://example.com/", "x")), """{"success":false}""");
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"farmacias","nearby":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("web_search_place_unavailable"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(handler.Asked, Has.All.Matches<Uri>(uri => uri.Host.Contains("ipwho", StringComparison.Ordinal)));
        });
    }

    // Without nearby nothing asks where this PC is; neither does a source nearby does not apply to (currency).
    [Test]
    public async Task ASearchWithoutNearbyNeverAsksWhereThisPcIs()
    {
        var handler = new RoutingHttpHandler(
            SearchResultsPage(("Hoteles en Madrid", "https://example.com/madrid", "Hoteles en Madrid")), """{"success":true}""");
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"hoteles en Madrid"}"""), CancellationToken.None);
        await adapter.InvokeAsync(
            "web.search", Json("""{"query":"usd a clp","source":"currency","from":"USD","to":"CLP","nearby":true}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("query").GetString(), Is.EqualTo("hoteles en Madrid"));
            Assert.That(handler.Asked, Has.None.Matches<Uri>(uri => uri.Host.Contains("ipwho", StringComparison.Ordinal)));
        });
    }

    // D32: source=encyclopedia asks Wikipedia's open API in the language the model chose, with the project's Wikimedia
    // User-Agent and the query as written; each article comes back with the opening the API gave, and a page the API
    // marks as a disambiguation is no article. No other source is asked.
    [Test]
    public async Task AnEncyclopediaSearchAsksWikipediaInTheChosenLanguage()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["es.wikipedia.org"] = WikipediaAnswer("es",
                ("Canberra (desambiguación)", "", true),
                ("Canberra", "Canberra es la capital de Australia.​\n\nEstá en el Territorio de la Capital Australiana.", false),
                ("Territorio de la Capital Australiana", "Territorio federal de Australia que contiene la capital, Canberra.", false)),
            ["en.wikipedia.org"] = WikipediaAnswer("en", ("Canberra", "Canberra is the capital city of Australia.", false)),
        };
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);

        ExternalCapabilityReceipt spanish = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"capital de Australia","source":"encyclopedia","limit":5}"""), CancellationToken.None);
        ExternalCapabilityReceipt english = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"capital of Australia","source":"encyclopedia","language":"en"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(spanish.Verified, Is.True, spanish.ErrorCode);
            Assert.That(spanish.Result?.GetProperty("source").GetString(), Is.EqualTo("encyclopedia"));
            Assert.That(spanish.Result?.GetProperty("authority").GetString(), Is.EqualTo("wikipedia_es_api"));
            Assert.That(spanish.Result?.GetProperty("resultCount").GetInt32(), Is.EqualTo(2));
            JsonElement first = spanish.Result!.Value.GetProperty("results")[0];
            Assert.That(first.GetProperty("title").GetString(), Is.EqualTo("Canberra"));
            Assert.That(first.GetProperty("url").GetString(), Is.EqualTo("https://es.wikipedia.org/wiki/Canberra"));
            Assert.That(first.GetProperty("extract").GetString(),
                Is.EqualTo("Canberra es la capital de Australia. Está en el Territorio de la Capital Australiana."));
            Assert.That(spanish.Result?.GetRawText(), Does.Not.Contain("desambiguaci"));
            Assert.That(english.Result?.GetProperty("authority").GetString(), Is.EqualTo("wikipedia_en_api"));
            Assert.That(handler.Asked.Select(asked => asked.Uri.Host), Is.EqualTo(new[] { "es.wikipedia.org", "en.wikipedia.org" }));
            Assert.That(handler.Asked[0].UserAgent, Does.Match(ProjectUserAgent));
            Assert.That(Uri.UnescapeDataString(handler.Asked[0].Uri.Query), Does.Contain("gsrsearch=capital de Australia&"));
            Assert.That(Uri.UnescapeDataString(handler.Asked[0].Uri.Query), Does.Contain("gsrlimit=5&"));
        });
    }

    [Test]
    public async Task AnEncyclopediaThatAnswersNothingHasNoResultsAndOneThatDoesNotAnswerIsUnavailable()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["es.wikipedia.org"] = new(HttpStatusCode.OK, """{"batchcomplete":true}""", "application/json"),
        };
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);

        ExternalCapabilityReceipt none = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"xyzzy quux","source":"encyclopedia"}"""), CancellationToken.None);
        ExternalCapabilityReceipt down = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"xyzzy quux","source":"encyclopedia","language":"en"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(none.ErrorCode, Is.EqualTo("web_search_no_results"));
            Assert.That(down.ErrorCode, Is.EqualTo("web_search_unavailable"));
            Assert.That(handler.Asked.Select(asked => asked.Uri.Host), Is.EqualTo(new[] { "es.wikipedia.org", "en.wikipedia.org" }));
        });
    }

    // source=news asks the search feed of Google News in the edition of the chosen language and returns its items as
    // the feed gave them (title without the outlet's tail, outlet, link without its tracking query, time), none left
    // out for what it says.
    [Test]
    public async Task ANewsSearchReturnsTheFeedsItemsAsItGaveThem()
    {
        const string feed = """
            <?xml version="1.0" encoding="UTF-8"?>
            <rss version="2.0"><channel><title>Noticias</title>
            <item><title>Dólar blue hoy: a cuánto cotiza este lunes - Diario Uno</title><link>https://news.google.com/rss/articles/abc?oc=5</link><pubDate>Mon, 28 Sep 2026 12:00:00 GMT</pubDate><source url="https://www.example.com.ar">Diario Uno</source></item>
            <item><title>El fútbol argentino vuelve este fin de semana - Diario Dos</title><link>https://news.google.com/rss/articles/def?oc=5</link><pubDate>Mon, 28 Sep 2026 11:00:00 GMT</pubDate><source url="https://www.example.com">Diario Dos</source></item>
            <item><title>Sin enlace seguro - Diario Tres</title><link>http://news.example.com/plain</link><pubDate>Mon, 28 Sep 2026 10:00:00 GMT</pubDate><source url="http://news.example.com">Diario Tres</source></item>
            </channel></rss>
            """;
        var handler = new SearchSourcesHttpHandler
        {
            ["news.google.com"] = new(HttpStatusCode.OK, feed, "application/rss+xml"),
        };
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"dólar blue hoy","source":"news"}"""), CancellationToken.None);
        await adapter.InvokeAsync(
            "web.search", Json("""{"query":"dollar today","source":"news","language":"en","limit":1}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("source").GetString(), Is.EqualTo("news"));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("google_news_rss_search"));
            Assert.That(receipt.Result?.GetProperty("resultCount").GetInt32(), Is.EqualTo(2));
            JsonElement first = receipt.Result!.Value.GetProperty("results")[0];
            Assert.That(first.GetProperty("title").GetString(), Is.EqualTo("Dólar blue hoy: a cuánto cotiza este lunes"));
            Assert.That(first.GetProperty("source").GetString(), Is.EqualTo("Diario Uno"));
            Assert.That(first.GetProperty("url").GetString(), Is.EqualTo("https://news.google.com/rss/articles/abc"));
            Assert.That(first.GetProperty("published").GetString(), Is.EqualTo("Mon, 28 Sep 2026 12:00:00 GMT"));
            Assert.That(receipt.Result!.Value.GetProperty("results")[1].GetProperty("title").GetString(),
                Is.EqualTo("El fútbol argentino vuelve este fin de semana"));
            Assert.That(Uri.UnescapeDataString(handler.Asked[0].Uri.Query),
                Is.EqualTo("?q=dólar blue hoy&hl=es-419&gl=CL&ceid=CL:es-419"));
            Assert.That(Uri.UnescapeDataString(handler.Asked[1].Uri.Query),
                Is.EqualTo("?q=dollar today&hl=en-US&gl=US&ceid=US:en"));
            Assert.That(handler.Asked[0].UserAgent, Does.Match(ProjectUserAgent));
        });
    }

    // M51 (D32): source=currency asks Frankfurter for the pair of ISO codes the model wrote; the receipt carries the
    // rate and its date as given and the amount converted with it. Only the pair leaves.
    [Test]
    public async Task ACurrencySearchReturnsTheRateItsDateAndTheAmountConverted()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["api.frankfurter.dev"] = new(HttpStatusCode.OK,
                """[{"date":"2026-09-28","base":"CAD","quote":"USD","rate":0.70774}]""", "application/json"),
        };
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"500 cad in usd","source":"currency","from":"cad","to":"USD","amount":500}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("frankfurter_reference_rates"));
            Assert.That(receipt.Result?.GetProperty("sent").GetProperty("from").GetString(), Is.EqualTo("CAD"));
            Assert.That(receipt.Result?.GetProperty("sent").GetProperty("to").GetString(), Is.EqualTo("USD"));
            JsonElement first = receipt.Result!.Value.GetProperty("results")[0];
            Assert.That(first.GetProperty("from").GetString(), Is.EqualTo("CAD"));
            Assert.That(first.GetProperty("to").GetString(), Is.EqualTo("USD"));
            Assert.That(first.GetProperty("amount").GetDecimal(), Is.EqualTo(500m));
            Assert.That(first.GetProperty("rate").GetDecimal(), Is.EqualTo(0.70774m));
            Assert.That(first.GetProperty("date").GetString(), Is.EqualTo("2026-09-28"));
            Assert.That(first.GetProperty("converted").GetDecimal(), Is.EqualTo(353.87m));
            Assert.That(handler.Asked.Single().Uri.AbsoluteUri,
                Is.EqualTo("https://api.frankfurter.dev/v2/rates?base=CAD&quotes=USD"));
        });
    }

    // A currency is its ISO 4217 code and a conversion names two of them; the provider reads no currency names.
    [TestCase("""{"query":"dólares a pesos","source":"currency","from":"dolares","to":"CLP"}""")]
    [TestCase("""{"query":"usd","source":"currency","from":"USD","to":"USD"}""")]
    [TestCase("""{"query":"usd","source":"currency","from":"USD"}""")]
    [TestCase("""{"query":"usd","source":"currency","from":"USD","to":"CLP","amount":-3}""")]
    [TestCase("""{"query":"farmacias","source":"places","kind":"pharmacy"}""")]
    [TestCase("""{"query":"boca","source":"sports"}""")]
    [TestCase("""{"query":"boca","source":"sports","team":"Boca Juniors","wants":"tomorrow"}""")]
    [TestCase("""{"query":"x","source":"recipes"}""")]
    [TestCase("""{"query":"x","source":"encyclopedia","language":"fr"}""")]
    public async Task ATypedSearchWithoutItsArgumentsAsksNothing(string arguments)
    {
        var handler = new SearchSourcesHttpHandler();
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("web.search", Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("web_argument_invalid"));
            Assert.That(handler.Asked, Is.Empty);
        });
    }

    // M168 (D77): source=sports asks ESPN for the team the model wrote (two requests: the team, its calendar, both with
    // BAXY's User-Agent) and returns the match as the calendar gives it, with the team ESPN found; the same question
    // again within minutes asks nothing new.
    [Test]
    public async Task ASportsSearchReturnsTheMatchAsEspnsCalendarGivesIt()
    {
        var handler = new SearchSourcesHttpHandler();
        handler.Routes.Add(("apis/search/v2", new(HttpStatusCode.OK,
            EspnScheduleSourceTests.Fixture("search_lakers.json"), "application/json")));
        handler.Routes.Add(("basketball/nba/teams/13/schedule", new(HttpStatusCode.OK,
            EspnScheduleSourceTests.Fixture("nba_lakers_schedule.json"), "application/json")));
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http, new EspnScheduleSource(
            http, static () => EspnScheduleSourceTests.Now, EspnScheduleSourceTests.Santiago));
        JsonElement arguments = Json("""{"query":"when do the Lakers play next","source":"sports","team":"Lakers"}""");

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("web.search", arguments, CancellationToken.None);
        ExternalCapabilityReceipt again = await adapter.InvokeAsync("web.search", arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("source").GetString(), Is.EqualTo("sports"));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("espn_public_schedule"));
            Assert.That(receipt.Result?.GetProperty("sent").GetProperty("team").GetString(), Is.EqualTo("Lakers"));
            Assert.That(receipt.Result?.GetProperty("sent").GetProperty("wants").GetString(), Is.EqualTo("next"));
            JsonElement match = receipt.Result!.Value.GetProperty("results")[0];
            Assert.That(match.GetProperty("team").GetString(), Is.EqualTo("Los Angeles Lakers"));
            Assert.That(match.GetProperty("opponent").GetString(), Is.EqualTo("Sacramento Kings"));
            Assert.That(match.GetProperty("homeAway").GetString(), Is.EqualTo("away"));
            Assert.That(match.GetProperty("start").GetString(), Is.EqualTo("2026-10-05T23:00-03:00"));
            Assert.That(match.GetProperty("startTimeAnnounced").GetBoolean(), Is.True);
            Assert.That(match.GetProperty("state").GetString(), Is.EqualTo("pre"));
            Assert.That(match.GetProperty("competition").GetString(), Is.EqualTo("NBA Preseason"));
            Assert.That(match.GetProperty("venue").GetString(), Is.EqualTo("Golden 1 Center"));
            Assert.That(again.Result?.GetProperty("results")[0].GetProperty("opponent").GetString(), Is.EqualTo("Sacramento Kings"));
            Assert.That(handler.Asked.Select(static asked => asked.Uri.AbsoluteUri), Is.EqualTo(new[]
            {
                "https://site.api.espn.com/apis/search/v2?query=Lakers&limit=8&type=team",
                "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/schedule",
            }));
            Assert.That(handler.Asked.Select(static asked => asked.UserAgent), Has.All.Match(ProjectUserAgent));
        });
    }

    // A team ESPN does not know is no result; ESPN unreachable is a search that could not be made.
    [Test]
    public async Task ATeamEspnDoesNotKnowHasNoResultsAndEspnUnreachableIsUnavailable()
    {
        var handler = new SearchSourcesHttpHandler();
        handler.Routes.Add(("query=Xyzzy", new(HttpStatusCode.OK,
            EspnScheduleSourceTests.Fixture("search_xyzzy.json"), "application/json")));
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http, new EspnScheduleSource(
            http, static () => EspnScheduleSourceTests.Now, EspnScheduleSourceTests.Santiago));

        ExternalCapabilityReceipt unknown = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"xyzzy","source":"sports","team":"Xyzzy Quux","wants":"last"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt down = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"boca","source":"sports","team":"Boca Juniors"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(unknown.ErrorCode, Is.EqualTo("web_search_no_results"));
            Assert.That(down.ErrorCode, Is.EqualTo("web_search_unavailable"));
            Assert.That(handler.Asked.Select(static asked => asked.Uri.AbsoluteUri), Is.EqualTo(new[]
            {
                "https://site.api.espn.com/apis/search/v2?query=Xyzzy%20Quux&limit=8&type=team",
                "https://site.api.espn.com/apis/search/v2?query=Boca%20Juniors&limit=8&type=team",
            }));
        });
    }

    // M51 F-p05-t1 «Encuentra aparcamiento en Plaza del Polvorista»: source=places asks Nominatim for the place the
    // model wrote (its first answer is the place), then for the kind of site, in English, inside its box, both with
    // the project's User-Agent. Each site comes back with its name, address and page as Nominatim gave them and its
    // distance from the place's centre, nearest first; the receipt says the place Nominatim found.
    [Test]
    public async Task APlacesSearchAsksTheKindOfSiteInsideThePlace()
    {
        var handler = new SearchSourcesHttpHandler();
        handler.Routes.Add(("q=Plaza del Polvorista, El Puerto de Santa María", new(HttpStatusCode.OK,
            """[{"lat":"36.5985","lon":"-6.2330","boundingbox":["36.5982","36.5988","-6.2334","-6.2326"],"display_name":"Plaza del Polvorista, El Puerto de Santa María, Cádiz, España"}]""",
            "application/json")));
        handler.Routes.Add(("q=parking", new(HttpStatusCode.OK,
            """[{"osm_type":"way","osm_id":123,"name":"Aparcamiento Polvorista","type":"parking","lat":"36.6010","lon":"-6.2330","display_name":"Aparcamiento Polvorista, Calle Larga, El Puerto de Santa María, Cádiz, España"},{"osm_type":"node","osm_id":456,"name":"","type":"parking","lat":"36.5986","lon":"-6.2330","display_name":"Calle Ganado, El Puerto de Santa María, Cádiz, España"},{"osm_type":"other","osm_id":789,"name":"Nada","type":"parking","display_name":"Nada"}]""",
            "application/json")));
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search",
            Json("""{"query":"aparcamiento en Plaza del Polvorista","source":"places","kind":"parking","place":"Plaza del Polvorista, El Puerto de Santa María"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("openstreetmap_nominatim"));
            JsonElement sent = receipt.Result!.Value.GetProperty("sent");
            Assert.That(sent.GetProperty("kind").GetString(), Is.EqualTo("parking"));
            Assert.That(sent.GetProperty("place").GetString(), Is.EqualTo("Plaza del Polvorista, El Puerto de Santa María"));
            Assert.That(sent.GetProperty("placeFound").GetString(), Is.EqualTo("Plaza del Polvorista, El Puerto de Santa María, Cádiz, España"));
            JsonElement results = receipt.Result!.Value.GetProperty("results");
            Assert.That(results.GetArrayLength(), Is.EqualTo(2));
            Assert.That(results[0].GetProperty("name").GetString(), Is.EqualTo("parking"));
            Assert.That(results[0].GetProperty("address").GetString(), Is.EqualTo("Calle Ganado, El Puerto de Santa María, Cádiz, España"));
            Assert.That(results[0].GetProperty("url").GetString(), Is.EqualTo("https://www.openstreetmap.org/node/456"));
            Assert.That(results[0].GetProperty("distanceMeters").GetInt32(), Is.EqualTo(10));
            Assert.That(results[1].GetProperty("name").GetString(), Is.EqualTo("Aparcamiento Polvorista"));
            Assert.That(results[1].GetProperty("distanceMeters").GetInt32(), Is.InRange(270, 290));
            Assert.That(handler.Asked, Has.Count.EqualTo(2));
            Assert.That(handler.Asked, Has.All.Matches<AskedRequest>(asked => asked.Uri.Host == "nominatim.openstreetmap.org"
                && asked.UserAgent.Contains("github.com/REDSOULTM/baxy-assistant", StringComparison.Ordinal)));
            Assert.That(Uri.UnescapeDataString(handler.Asked[0].Uri.Query), Does.Contain("limit=1&accept-language=es&"));
            Assert.That(Uri.UnescapeDataString(handler.Asked[1].Uri.Query),
                Does.Contain("bounded=1").And.Contain("viewbox=-6.243,36.6085,-6.223,36.5885"));
        });
    }

    // With nearby and no place, the place is this PC's city and country; a place Nominatim does not find is no result,
    // and no site is asked.
    [Test]
    public async Task APlacesSearchNearbyIsInThisPcsCityAndAnUnknownPlaceHasNoResults()
    {
        var handler = new SearchSourcesHttpHandler();
        handler.Routes.Add(("ipwho.is", new(HttpStatusCode.OK,
            """{"success":true,"country":"Chile","region":"Curico","city":"Curico","latitude":-34.9828,"longitude":-71.2394}""",
            "application/json")));
        handler.Routes.Add(("q=Curico, Chile", new(HttpStatusCode.OK,
            """[{"boundingbox":["-35.03","-34.93","-71.30","-71.18"],"display_name":"Curicó, Chile"}]""", "application/json")));
        handler.Routes.Add(("q=pharmacy", new(HttpStatusCode.OK,
            """[{"osm_type":"node","osm_id":1,"name":"Farmacia Central","type":"pharmacy","display_name":"Farmacia Central, Curicó, Chile"}]""",
            "application/json")));
        handler.Routes.Add(("q=Nowhere Land", new(HttpStatusCode.OK, "[]", "application/json")));
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);

        ExternalCapabilityReceipt near = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"farmacias cerca","source":"places","kind":"pharmacy","nearby":true}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt unknown = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"farmacias","source":"places","kind":"pharmacy","place":"Nowhere Land"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(near.Verified, Is.True, near.ErrorCode);
            Assert.That(near.Result?.GetProperty("sent").GetProperty("place").GetString(), Is.EqualTo("Curico, Chile"));
            JsonElement first = near.Result!.Value.GetProperty("results")[0];
            Assert.That(first.GetProperty("name").GetString(), Is.EqualTo("Farmacia Central"));
            Assert.That(first.TryGetProperty("distanceMeters", out _), Is.False);
            Assert.That(unknown.ErrorCode, Is.EqualTo("web_search_no_results"));
            Assert.That(handler.Asked.Count(asked => asked.Uri.Query.Contains("pharmacy", StringComparison.Ordinal)), Is.EqualTo(1));
            Assert.That(handler.Asked.Where(asked => asked.Uri.Host != "ipwho.is"),
                Has.All.Matches<AskedRequest>(asked => !asked.Uri.Query.Contains("33.03", StringComparison.Ordinal)));
        });
    }

    // M63 (v3f-final F-p05-t1, Nominatim's answers of 2026-09-29): the place is Nominatim's first answer, and the car
    // parks around it are said with their distances from it, nearest first (as published: 150–620 m).
    [Test]
    public void ThePlazaDelPolvoristaIsWhereOpenStreetMapHasIt()
    {
        OpenStreetMapPlaceSource.Area? anchor = OpenStreetMapPlaceSource.AreaOf(PolvoristaCandidates);
        Assert.That(anchor, Is.Not.Null);
        List<OpenStreetMapPlaceSource.Place> parks =
            OpenStreetMapPlaceSource.Places(PolvoristaParking, anchor!.Value.Latitude, anchor.Value.Longitude);
        Assert.Multiple(() =>
        {
            Assert.That(anchor.Value.Name, Does.StartWith("Plaza del Polvorista, Valdelagrana"));
            Assert.That(anchor.Value.Latitude, Is.EqualTo(36.5948).Within(0.0005));
            Assert.That(anchor.Value.Longitude, Is.EqualTo(-6.2270).Within(0.0005));
            Assert.That(parks.Take(5).Select(static place => place.DistanceMeters),
                Is.EqualTo(new int?[] { 150, 430, 450, 480, 620 }), "the distances published in v3f-final t113");
            Assert.That(parks[0].Address, Does.StartWith("Avenida de la Bajamar"));
            Assert.That(OpenStreetMapPlaceSource.AreaOf("[]"), Is.Null);
        });
    }

    private const string PolvoristaCandidates =
        """[{"osm_type":"way","osm_id":29451698,"lat":"36.5948388","lon":"-6.2270183","category":"highway","type":"tertiary","name":"Plaza del Polvorista","display_name":"Plaza del Polvorista, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España","boundingbox":["36.5945842","36.5950933","-6.2272746","-6.2267619"],"address":{"country_code":"es"}},{"osm_type":"way","osm_id":29451697,"lat":"36.5950470","lon":"-6.2273243","category":"leisure","type":"park","name":"Plaza del Polvorista","display_name":"Plaza del Polvorista, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, España","boundingbox":["36.5947017","36.5953921","-6.2277549","-6.2268937"],"address":{"country_code":"es"}},{"osm_type":"node","osm_id":13398649899,"lat":"36.5947788","lon":"-6.2271996","category":"highway","type":"bus_stop","name":"Plaza del Polvorista","display_name":"Plaza del Polvorista, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España","boundingbox":["36.5947288","36.5948288","-6.2272496","-6.2271496"],"address":{"country_code":"es"}}]""";

    private const string PolvoristaParking =
        """[{"osm_type":"way","osm_id":952407268,"lat":"36.5931010","lon":"-6.2204714","type":"parking","name":"","display_name":"Calle Río Majaceite, Las Viñas, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":237016676,"lat":"36.5952887","lon":"-6.2254513","type":"parking","name":"","display_name":"Avenida de la Bajamar, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":952407272,"lat":"36.5930603","lon":"-6.2224781","type":"parking","name":"","display_name":"Avenida de Valdelagrana, Las Viñas, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":1106171484,"lat":"36.5948204","lon":"-6.2221896","type":"parking","name":"","display_name":"Avenida de Europa, Las Viñas, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":1423300837,"lat":"36.6041595","lon":"-6.2182015","type":"parking","name":"Vehículos Autorizados","display_name":"Vehículos Autorizados, Avenida del Monasterio, El Tejar, Sudamérica, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":1423300839,"lat":"36.6045170","lon":"-6.2175435","type":"parking","name":"","display_name":"Avenida del Monasterio, El Tejar, Sudamérica, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":302015013,"lat":"36.6035873","lon":"-6.2174271","type":"parking","name":"","display_name":"Calle Francisco Cossi Ochoa, El Tejar, Sudamérica, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":301734888,"lat":"36.5917584","lon":"-6.2365322","type":"parking","name":"","display_name":"Calle Tórtola, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":301734891,"lat":"36.5914572","lon":"-6.2304048","type":"parking","name":"","display_name":"Calle Brújula, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":301734896,"lat":"36.5912467","lon":"-6.2365437","type":"parking","name":"","display_name":"Calle Pescadores, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"}]""";

    // The video played is the first one YouTube's results page lists, whatever its title says.
    [Test]
    public void TheVideoPlayedIsTheFirstOneTheResultsPageLists()
    {
        string html = "var ytInitialData = {"
            + "\"videoRenderer\":{\"videoId\":\"serie000001\",\"title\":{\"runs\":[{\"text\":\"Avatar: Los Siete Refugios | Tráiler\"}]}},"
            + "\"videoRenderer\":{\"videoId\":\"pelicula003\",\"title\":{\"runs\":[{\"text\":\"Avatar | Tráiler oficial\"}]}}};";

        YouTubeSearchResult video = YouTubeSearch.Parse(html);

        Assert.Multiple(() =>
        {
            Assert.That(video.Found, Is.True);
            Assert.That(video.VideoId, Is.EqualTo("serie000001"));
            Assert.That(video.Title, Is.EqualTo("Avatar: Los Siete Refugios | Tráiler"));
        });
    }

    private const string RicePage = """
        <html><head><title>Arroz</title><script>var dato = "cuánto arroz cocer por persona 999";</script>
        <style>.arroz{color:red}</style></head><body>
        <nav>Inicio Recetas Arroz por persona para la cena 2026</nav>
        <article><h1>Cuánto arroz cocer por persona</h1>
        <p>Muchos cocineros dudan cuánto arroz cocer por persona cuando preparan una comida familiar.</p>
        <p>La medida habitual es de 80 gramos de arroz crudo por persona, que se cuecen en el doble de agua.</p>
        <p>El arroz integral necesita algo más de tiempo de cocción que el blanco.</p>
        <p>Para una cena de cuatro personas bastan unos 320 gramos de arroz y 640 mililitros de agua.</p>
        </article><footer>Arroz por persona para la cena, copyright 2026, todos los derechos</footer></body></html>
        """;

    // BAXY Renew agent tools (2026-10-15): web.fetch reads one public page as text, its title and the address it was
    // read from; never its scripts, styles, menu or footer, and never an address of this PC or its network.
    [Test]
    public async Task WebFetchReadsAPublicPageAsText()
    {
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        var pages = new RoutingHttpHandler(RicePage, "{}");
        using var http = new HttpClient(pages);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt read = await adapter.InvokeAsync(
            "web.fetch", Json("""{"url":"https://recetas.example.com/arroz"}"""), CancellationToken.None);
        ExternalCapabilityReceipt local = await adapter.InvokeAsync(
            "web.fetch", Json("""{"url":"http://192.168.1.10/admin"}"""), CancellationToken.None);
        // A page comes in pages: the second one starts where the first said, and says there is no more.
        var longPages = new RoutingHttpHandler("<html><body><p>" + new string('a', 800) + "</p></body></html>", "{}");
        using var longHttp = new HttpClient(longPages);
        using var longAdapter = new WebBrowserAdapter(browser, longHttp);
        ExternalCapabilityReceipt first = await longAdapter.InvokeAsync(
            "web.fetch", Json("""{"url":"https://largo.example.com/","maximumCharacters":500}"""),
            CancellationToken.None);
        int next = first.Result!.Value.GetProperty("nextOffset").GetInt32();
        ExternalCapabilityReceipt second = await longAdapter.InvokeAsync(
            "web.fetch", Json($$"""{"url":"https://largo.example.com/","maximumCharacters":500,"offset":{{next}}}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(read.Verified, Is.True);
            Assert.That(read.EffectObserved, Is.False);
            Assert.That(read.Result?.GetProperty("title").GetString(), Is.EqualTo("Arroz"));
            Assert.That(read.Result?.GetProperty("finalUrl").GetString(), Is.EqualTo("https://recetas.example.com/arroz"));
            string text = read.Result?.GetProperty("text").GetString() ?? "";
            Assert.That(text, Does.Contain("80 gramos de arroz crudo por persona"));
            Assert.That(text, Does.Not.Contain("999"));
            Assert.That(text, Does.Not.Contain("copyright"));
            Assert.That(text, Does.Not.Contain("Inicio Recetas"));
            Assert.That(local.Verified, Is.False);
            Assert.That(local.ErrorCode, Is.EqualTo("web_fetch_address_not_public"));
            Assert.That(first.Result?.GetProperty("hasMore").GetBoolean(), Is.True);
            Assert.That(next, Is.EqualTo(500));
            Assert.That(second.Result?.GetProperty("offset").GetInt32(), Is.EqualTo(500));
            Assert.That(second.Result?.GetProperty("hasMore").GetBoolean(), Is.False);
            Assert.That(second.Result?.GetProperty("totalCharacters").GetInt32(), Is.EqualTo(800));
            Assert.That(pages.Asked, Has.Count.EqualTo(1));
        });
    }

    // M98: a page is decoded in the charset its response declares, else the one its own first bytes declare, else
    // UTF-8; Latin-1 is read as Windows-1252, as browsers do.
    [Test]
    public void APageIsDecodedInTheCharsetItDeclares()
    {
        Encoding windows1252 = CodePagesEncodingProvider.Instance.GetEncoding(1252)!;
        const string Prose = "<p>Según la tradición, la paella lleva azafrán y cuesta 12 €.</p>";
        Assert.Multiple(() =>
        {
            Assert.That(SearchPageReader.Decode(Encoding.Latin1.GetBytes("<p>Según la tradición, azafrán.</p>"), "ISO-8859-1"),
                Does.Contain("Según la tradición, azafrán."));
            Assert.That(SearchPageReader.Decode(windows1252.GetBytes("<html><head><meta charset=\"windows-1252\"></head>" + Prose), null),
                Does.Contain("tradición, la paella lleva azafrán y cuesta 12 €."));
            Assert.That(SearchPageReader.Decode(windows1252.GetBytes(
                    "<meta http-equiv=\"Content-Type\" content=\"text/html; charset=ISO-8859-1\">" + Prose), null),
                Does.Contain("cuesta 12 €."));
            Assert.That(SearchPageReader.Decode(Encoding.UTF8.GetBytes(Prose), null), Does.Contain("Según la tradición"));
            // The response's charset is the page's, whatever its <meta> says.
            Assert.That(SearchPageReader.Decode(Encoding.UTF8.GetBytes("<meta charset=\"iso-8859-1\">" + Prose), "utf-8"),
                Does.Contain("Según la tradición"));
            Assert.That(SearchPageReader.Decode(Encoding.UTF8.GetBytes(Prose), "no-such-charset"), Does.Contain("azafrán"));
        });
    }

    // M98: only a public web address is read; this PC, the local network, Tailscale's range and non-web schemes never.
    [Test]
    public void OnlyAPublicWebAddressIsRead()
    {
        Assert.Multiple(() =>
        {
            foreach (string address in new[] { "https://example.com/a", "http://example.com/a", "https://93.184.216.34/" })
                Assert.That(SearchPageReader.IsPublicPageAddress(new Uri(address)), Is.True, address);
            foreach (string address in new[]
            {
                "file:///C:/Users/x/secret.txt", "ftp://example.com/a", "http://localhost/admin", "https://127.0.0.1/",
                "https://10.0.0.5/", "https://172.20.1.1/", "https://192.168.1.1/", "https://169.254.169.254/latest",
                "https://100.101.102.103/", "https://[::1]/", "https://[fd00::1]/", "https://[fe80::1]/",
                "https://[::ffff:192.168.0.1]/", "https://router/", "https://printer.local/", "https://nas.home.arpa/",
                "https://pc.tail1234.ts.net/", "https://user:pass@example.com/",
            })
            {
                Assert.That(SearchPageReader.IsPublicPageAddress(new Uri(address)), Is.False, address);
            }
            Assert.That(SearchPageReader.PublicEndpoint([IPAddress.Parse("93.184.216.34")]),
                Is.EqualTo(IPAddress.Parse("93.184.216.34")));
            // A name that also resolves into the LAN is trusted with none of its addresses.
            Assert.That(SearchPageReader.PublicEndpoint([IPAddress.Parse("93.184.216.34"), IPAddress.Parse("192.168.1.10")]),
                Is.Null);
            Assert.That(SearchPageReader.PublicEndpoint([IPAddress.Parse("2606:4700::1111")]), Is.Not.Null);
            Assert.That(SearchPageReader.PublicEndpoint([]), Is.Null);
        });
    }

    // M98: a Latin-1 page is read with its accents, and the request carries only a generic User-Agent.
    [Test]
    public async Task ALatinOnePageIsFetchedWithItsAccentsAndNothingOfThePerson()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["recetas.example.es"] = new(HttpStatusCode.OK, "", "text/html; charset=ISO-8859-1",
                Raw: Encoding.Latin1.GetBytes(
                    "<html><body><p>Según la tradición, la paella valenciana lleva 400 gramos de arroz para cuatro personas y azafrán.</p></body></html>")),
        };
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.fetch", Json("""{"url":"https://recetas.example.es/paella"}"""), CancellationToken.None);

        AskedRequest page = handler.Asked.Single();
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("text").GetString(),
                Is.EqualTo("Según la tradición, la paella valenciana lleva 400 gramos de arroz para cuatro personas y azafrán."));
            Assert.That(page.Headers, Is.EqualTo(new[] { "User-Agent" }));
            Assert.That(page.UserAgent, Is.EqualTo("BAXY/1.0 page-read"));
        });
    }

    // M98: an address in the local network is never read, and neither is a public page's redirect into it.
    [Test]
    public async Task APageInTheLocalNetworkIsNeverFetched()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["192.168.1.20"] = new(HttpStatusCode.OK, "<p>dice el router</p>", "text/html"),
            ["intranet.local"] = new(HttpStatusCode.OK, "<p>dice la intranet</p>", "text/html"),
            ["recetas.example.es"] = new(HttpStatusCode.Found, "", "text/html", Location: "http://127.0.0.1/admin"),
            ["127.0.0.1"] = new(HttpStatusCode.OK, "<p>dice este PC</p>", "text/html"),
        };
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);

        ExternalCapabilityReceipt router = await adapter.InvokeAsync(
            "web.fetch", Json("""{"url":"https://192.168.1.20/paella"}"""), CancellationToken.None);
        ExternalCapabilityReceipt intranet = await adapter.InvokeAsync(
            "web.fetch", Json("""{"url":"https://intranet.local/paella"}"""), CancellationToken.None);
        ExternalCapabilityReceipt redirected = await adapter.InvokeAsync(
            "web.fetch", Json("""{"url":"https://recetas.example.es/paella"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(router.ErrorCode, Is.EqualTo("web_fetch_address_not_public"));
            Assert.That(intranet.ErrorCode, Is.EqualTo("web_fetch_address_not_public"));
            Assert.That(redirected.ErrorCode, Is.EqualTo("web_fetch_redirect_not_public"));
            Assert.That(handler.Asked.Select(asked => asked.Uri.Host), Is.EqualTo(new[] { "recetas.example.es" }));
        });
    }

    private static HttpAnswer WikipediaAnswer(
        string language,
        params (string Title, string Extract, bool Disambiguation)[] pages)
    {
        var body = new StringBuilder("""{"batchcomplete":true,"query":{"pages":[""");
        for (int index = 0; index < pages.Length; index++)
        {
            (string title, string extract, bool disambiguation) = pages[index];
            if (index > 0) body.Append(',');
            body.Append("{\"pageid\":").Append(index + 10).Append(",\"ns\":0,\"title\":")
                .Append(JsonSerializer.Serialize(title))
                .Append(",\"index\":").Append(index + 1)
                .Append(",\"fullurl\":").Append(JsonSerializer.Serialize(
                    "https://" + language + ".wikipedia.org/wiki/" + Uri.EscapeDataString(title.Replace(' ', '_'))))
                .Append(",\"extract\":").Append(JsonSerializer.Serialize(extract));
            if (disambiguation) body.Append(",\"pageprops\":{\"disambiguation\":\"\"}");
            body.Append('}');
        }
        return new(HttpStatusCode.OK, body.Append("]}}").ToString(), "application/json");
    }

    // The general engine's lite page: each result a «result-link» anchor followed by
    // its snippet cell.
    private static string SearchResultsPage(params (string Title, string Url, string Snippet)[] results)
    {
        var page = new StringBuilder("<html><body><!-- Web results are present --><table>");
        foreach ((string title, string url, string snippet) in results)
        {
            page.Append("<tr><td><a rel=\"nofollow\" href=\"")
                .Append(url)
                .Append("\" class='result-link'>")
                .Append(title)
                .Append("</a></td></tr><tr><td class='result-snippet'>")
                .Append(snippet.Replace("WhatsApp", "<b>WhatsApp</b>"))
                .Append("</td></tr>");
        }
        return page.Append("</table></body></html>").ToString();
    }

    // M98: a body of raw bytes (a page in another charset) and a redirect's Location.
    private sealed record HttpAnswer(
        HttpStatusCode Status, string Body, string ContentType, byte[]? Raw = null, string? Location = null);

    private sealed record AskedRequest(Uri Uri, string UserAgent, string[] Headers);

    // Answers each host with its own reply; a host it does not know is unreachable.
    private sealed class SearchSourcesHttpHandler : HttpMessageHandler
    {
        private readonly Dictionary<string, HttpAnswer> _answers = new(StringComparer.OrdinalIgnoreCase);

        internal List<AskedRequest> Asked { get; } = [];

        internal HttpAnswer this[string host]
        {
            set => _answers[host] = value;
        }

        // An answer for the requests whose unescaped address contains the text, asked
        // before the answer of the whole host.
        internal List<(string Contains, HttpAnswer Answer)> Routes { get; } = [];

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Uri uri = request.RequestUri!;
            Asked.Add(new AskedRequest(uri, request.Headers.UserAgent.ToString(),
                request.Headers.Select(static header => header.Key).ToArray()));
            string address = Uri.UnescapeDataString(uri.AbsoluteUri);
            HttpAnswer? answer = Routes.FirstOrDefault(route => address.Contains(route.Contains, StringComparison.Ordinal)).Answer;
            if (answer is null && !_answers.TryGetValue(uri.Host, out answer))
            {
                throw new HttpRequestException("unreachable host " + uri.Host);
            }
            HttpContent content;
            if (answer.Raw is not null)
            {
                content = new ByteArrayContent(answer.Raw);
                content.Headers.ContentType = System.Net.Http.Headers.MediaTypeHeaderValue.Parse(answer.ContentType);
            }
            else
            {
                content = new StringContent(answer.Body, Encoding.UTF8, answer.ContentType);
            }
            var response = new HttpResponseMessage(answer.Status) { Content = content };
            if (answer.Location is not null) response.Headers.Location = new Uri(answer.Location, UriKind.RelativeOrAbsolute);
            return Task.FromResult(response);
        }
    }

    [Test]
    public async Task OutlookCalendarListProjectsOpaqueEventIdentities()
    {
        const string output = """
            {"ok":true,"effectObserved":false,"events":[{"entryId":"private-entry","title":"Reunión","startUtc":"2026-07-17T10:00:00.0000000Z","endUtc":"2026-07-17T11:00:00.0000000Z"}]}
            """;
        using TemporaryDirectory temporary = new();
        var adapter = new MicrosoftAccountAdapter(temporary.Path, new StubProcessRunner(output));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "calendar.event.list",
            Json("""{"startUtc":"2026-07-17T00:00:00Z","endUtc":"2026-07-18T00:00:00Z"}"""),
            CancellationToken.None);

        string? eventId = receipt.Result?.GetProperty("events")[0].GetProperty("eventId").GetString();
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(eventId, Does.StartWith("event_"));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("private-entry"));
        });
    }

    [Test]
    public async Task EmailSendGoesToTheFreeAddressAndIsVerifiedInSentItems()
    {
        // Fase 7 (D4): a mail to any address from the classic Outlook profile; the
        // subject defaults to the text's opening; the address is checked first.
        const string output = "{\"ok\":true,\"effectObserved\":true,\"sentEntryId\":\"private-sent-entry\"," +
            "\"sentUtc\":\"2026-09-21T02:10:00Z\",\"sentTo\":[\"persona@example.com\"],\"subject\":\"llego tarde (copia)\"}";
        using TemporaryDirectory temporary = new();
        var runner = new StubProcessRunner(output);
        var adapter = new MicrosoftAccountAdapter(temporary.Path, runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "email.send",
            Json("""{"to":"persona@example.com","text":"llego tarde"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt invalid = await adapter.InvokeAsync(
            "email.send",
            Json("""{"to":"juan","text":"hola"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.EffectObserved, Is.True);
            // What the copy in Sent Items shows, not what was asked.
            Assert.That(receipt.Result?.GetProperty("sentTo")[0].GetString(), Is.EqualTo("persona@example.com"));
            Assert.That(receipt.Result?.GetProperty("subject").GetString(), Is.EqualTo("llego tarde (copia)"));
            Assert.That(receipt.Result?.GetProperty("sent").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("sentMessageId").GetString(), Does.StartWith("email_"));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("private-sent-entry"));
            Assert.That(invalid.Verified, Is.False);
            Assert.That(invalid.EffectObserved, Is.False);
            Assert.That(invalid.ErrorCode, Is.EqualTo("mail_address_invalid"));
        });
    }

    [Test]
    public async Task AppVolumeSetFixesTheSessionsAtAnAbsoluteLevelAndReportsThePostread()
    {
        // Fase 8 (D18) «poné Spotify al 40»: the sessions (paused or not) are set to the level and read back.
        var requested = new List<(string App, int Level)>();
        var adapter = new WindowsAppVolumeSetAdapter((app, level, beforeEffect, _) =>
        {
            beforeEffect?.Invoke();
            requested.Add((app, level));
            return new ApplicationSessionAdjustment("Spotify", 2, 85, level, false, "endpoint-1");
        });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.app.volume.set", Json("""{"app":"Spotify","level":40}"""), CancellationToken.None);
        ExternalCapabilityReceipt tooHigh = await adapter.InvokeAsync(
            "audio.app.volume.set", Json("""{"app":"Spotify","level":140}"""), CancellationToken.None);
        ExternalCapabilityReceipt noSession = await new WindowsAppVolumeSetAdapter((_, _, _, _) => null).InvokeAsync(
            "audio.app.volume.set", Json("""{"app":"Spotify","level":40}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("level").GetInt32(), Is.EqualTo(40));
            Assert.That(receipt.Result?.GetProperty("baselineLevel").GetInt32(), Is.EqualTo(85));
            Assert.That(receipt.Result?.GetProperty("requestedLevel").GetInt32(), Is.EqualTo(40));
            Assert.That(receipt.Result?.GetProperty("app").GetString(), Is.EqualTo("Spotify"));
            Assert.That(requested, Is.EqualTo(new[] { ("Spotify", 40) }));
            Assert.That(tooHigh.Verified, Is.False);
            Assert.That(tooHigh.ErrorCode, Is.EqualTo("volume_level_invalid"));
            Assert.That(noSession.Verified, Is.False);
            Assert.That(noSession.ErrorCode, Is.EqualTo("app_audio_session_not_found"));
        });
    }

    [Test]
    public async Task OutlookLatestReplyRequiresASentFolderPostread()
    {
        const string output = "{\"ok\":true,\"effectObserved\":true," +
            "\"entryId\":\"private-inbox-entry\",\"subject\":\"Informe\"," +
            "\"sender\":\"sender@example.test\",\"receivedUtc\":\"2026-07-17T10:00:00Z\"," +
            "\"body\":\"Contenido privado\",\"sentEntryId\":\"private-sent-entry\"," +
            "\"sentUtc\":\"2026-07-17T10:01:00Z\"}";
        using TemporaryDirectory temporary = new();
        var adapter = new MicrosoftAccountAdapter(
            temporary.Path, new StubProcessRunner(output));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "email.latest.reply",
            Json("""{"text":"I'll check tomorrow"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("subject").GetString(), Is.EqualTo("Informe"));
            Assert.That(receipt.Result?.GetProperty("messageId").GetString(),
                Does.StartWith("email_"));
            Assert.That(receipt.Result?.GetProperty("sentMessageId").GetString(),
                Does.StartWith("email_"));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("outlook_mapi_sent_postread"));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("private-inbox-entry"));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("private-sent-entry"));
        });
    }

    [Test]
    public async Task MissingLocalYouTubeDependenciesFailBeforeTheEffectBoundary()
    {
        using var adapter = new YouTubeMpvAdapter(
            mpvPath: null,
            ytDlpPath: null,
            nodePath: null);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.youtube", Json("""{"query":"gatos"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("youtube_local_player_dependency_missing"));
        });
    }

    [Test]
    public async Task UnresolvedYouTubeStreamDoesNotCrossThePlaybackEffectBoundary()
    {
        using TemporaryDirectory temporary = new();
        string mpv = Path.Combine(temporary.Path, "mpv.exe");
        string ytDlp = Path.Combine(temporary.Path, "yt-dlp.exe");
        await File.WriteAllTextAsync(mpv, "fixture");
        await File.WriteAllTextAsync(ytDlp, "fixture");
        bool resolverCalled = false;
        using var adapter = new YouTubeMpvAdapter(
            mpv,
            ytDlp,
            nodePath: null,
            (query, cancellationToken) =>
            {
                cancellationToken.ThrowIfCancellationRequested();
                resolverCalled = query == "gatos";
                return ValueTask.FromResult<Uri?>(null);
            });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.youtube", Json("""{"query":"gatos"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(resolverCalled, Is.True);
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("youtube_stream_not_resolved"));
        });
    }

    // BAXY Renew (notebook): the pause command reached the player and its answer could not be read; the request
    // may have paused it, so the dispatch stops there and no other player gets pressed.
    [Test]
    public async Task LocalPlayerFailureAfterThePauseWasSentStopsTheDispatch()
    {
        string pipeName = "baxy-test-mpv-" + Guid.NewGuid().ToString("N");
        string? sentCommand = null;
        Task player = Task.Run(async () =>
        {
            await AnswerOnceAsync(pipeName, request =>
                $$"""{"request_id":{{RequestId(request)}},"error":"success","data":false}""");
            await AnswerOnceAsync(pipeName, request =>
            {
                sentCommand = request;
                return "not json";
            });
        });
        var other = new StubExternalAdapter(new ExternalCapabilityReceipt(
            "media.control", true, true, Json("{}"), null));
        var local = new YouTubeMpvAdapter(mpvPath: null, ytDlpPath: null, nodePath: null);
        using var provider = new WindowsExternalCapabilityProvider([local, other]);
        const BindingFlags Private = BindingFlags.NonPublic | BindingFlags.Instance;
        FieldInfo activePlayer = typeof(YouTubeMpvAdapter).GetField("_activePlayer", Private)!;
        FieldInfo activePipe = typeof(YouTubeMpvAdapter).GetField("_activePipe", Private)!;
        using Process alive = Process.GetCurrentProcess();
        activePlayer.SetValue(local, alive);
        activePipe.SetValue(local, pipeName);
        ExternalCapabilityReceipt receipt;
        try
        {
            receipt = await provider.InvokeAsync(
                "media.control", Json("""{"action":"pause"}"""), CancellationToken.None);
            await player;
        }
        finally
        {
            // The player stands for this test's own process: nothing stops it when the provider is disposed.
            activePlayer.SetValue(local, null);
            activePipe.SetValue(local, null);
        }

        Assert.Multiple(() =>
        {
            Assert.That(sentCommand, Does.Contain("""["set_property","pause",true]"""));
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("local_player_ipc_failed"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(other.Calls, Is.Zero);
        });
    }

    // One connection of the player's IPC: one request line answered, then the client's close.
    private static async Task AnswerOnceAsync(string pipeName, Func<string, string> answer)
    {
        await using var pipe = new NamedPipeServerStream(
            pipeName, PipeDirection.InOut, 1, PipeTransmissionMode.Byte, PipeOptions.Asynchronous);
        await pipe.WaitForConnectionAsync();
        using var reader = new StreamReader(pipe, new UTF8Encoding(false), false, 4_096, leaveOpen: true);
        using var writer = new StreamWriter(pipe, new UTF8Encoding(false), 4_096, leaveOpen: true) { AutoFlush = true };
        string request = await reader.ReadLineAsync() ?? throw new IOException("No request.");
        await writer.WriteLineAsync(answer(request));
        while (await reader.ReadLineAsync() is not null)
        {
        }
    }

    private static int RequestId(string request)
    {
        using JsonDocument document = JsonDocument.Parse(request);
        return document.RootElement.GetProperty("request_id").GetInt32();
    }

    [Test]
    public async Task WifiRequiresListedOpaqueProfileAndVerifiesConnectedProfile()
    {
        using TemporaryDirectory temporary = new();
        var runner = new WifiProcessRunner();
        var adapter = new WindowsDeviceControlAdapter(temporary.Path, temporary.Path, runner);
        ExternalCapabilityReceipt listed = await adapter.InvokeAsync(
            "wifi.profile.list", Json("{}"), CancellationToken.None);
        string profileId = listed.Result!.Value.GetProperty("profiles")[0]
            .GetProperty("profileId").GetString()!;
        ExternalCapabilityReceipt connected = await adapter.InvokeAsync(
            "wifi.connect", Json($$"""{"profileId":"{{profileId}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(listed.Verified, Is.True);
            Assert.That(listed.Result?.GetRawText(), Does.Contain("Casa"));
            Assert.That(connected.Verified, Is.True);
            Assert.That(connected.EffectObserved, Is.True);
            Assert.That(runner.ConnectCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task PeripheralInventoryIncludesConnectedUsbWithOpaqueIdentity()
    {
        const string output = """
            {"printers":[],"scanners":[],"usb":[{"FriendlyName":"USB Camera","Status":"OK","InstanceId":"USB\\VID_PRIVATE"}],"mice":[],"keyboards":[]}
        """;
        using TemporaryDirectory temporary = new();
        var runner = new StubProcessRunner(output);
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path,
            temporary.Path,
            runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "peripheral.list", Json("""{"kind":"usb"}"""), CancellationToken.None);

        JsonElement device = receipt.Result!.Value.GetProperty("devices")[0];
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(device.GetProperty("kind").GetString(), Is.EqualTo("usb"));
            Assert.That(device.GetProperty("name").GetString(), Is.EqualTo("USB Camera"));
            Assert.That(device.GetProperty("deviceId").GetString(), Does.StartWith("usb_"));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("VID_PRIVATE"));
            Assert.That(runner.LastArguments[^1], Is.EqualTo("usb"));
        });
    }

    [Test]
    public async Task PeripheralInventoryFiltersMouseAndReturnsItsResolvedHardwareName()
    {
        const string output = """
            {"printers":[{"Name":"Wrong Printer","PrinterStatus":0}],"scanners":[],"usb":[],"mice":[{"FriendlyName":"ELAN1203 (I2C HID Device)","Status":"OK","InstanceId":"HID\\PRIVATE_MOUSE"}],"keyboards":[]}
        """;
        using TemporaryDirectory temporary = new();
        var runner = new StubProcessRunner(output);
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path,
            temporary.Path,
            runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "peripheral.list", Json("""{"kind":"mouse"}"""), CancellationToken.None);

        JsonElement result = receipt.Result!.Value;
        JsonElement device = result.GetProperty("devices")[0];
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(result.GetProperty("requestedKind").GetString(), Is.EqualTo("mouse"));
            Assert.That(result.GetProperty("devices").GetArrayLength(), Is.EqualTo(1));
            Assert.That(device.GetProperty("kind").GetString(), Is.EqualTo("mouse"));
            Assert.That(device.GetProperty("name").GetString(), Is.EqualTo("ELAN1203 (I2C HID Device)"));
            Assert.That(result.GetRawText(), Does.Not.Contain("Wrong Printer"));
            Assert.That(result.GetRawText(), Does.Not.Contain("PRIVATE_MOUSE"));
            Assert.That(runner.LastArguments[^1], Is.EqualTo("Mouse"));
        });
    }

    [Test]
    public async Task SpotifyDesktopResultRequiresUiaPostreadBeforeSuccess()
    {
        var adapter = new SpotifyDesktopAdapter(new StubProcessRunner(
            "{\"ok\":true,\"effectObserved\":true,\"title\":\"Billie Jean\",\"processId\":42}"));
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.exact",
            Json("""{"provider":"spotify","title":"Billie Jean"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("spotify_windows_uia_postread"));
        });
    }

    [Test]
    public async Task SpotifyExactSelectionRetriesOneUnobservedEmptyResult()
    {
        var runner = new SequencedProcessRunner([
            "{\"ok\":false,\"effectObserved\":false,\"error\":\"spotify_exact_result_not_found\"}",
            "{\"ok\":true,\"effectObserved\":true,\"title\":\"Billie Jean\",\"processId\":42}",
        ]);
        var adapter = new SpotifyDesktopAdapter(runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.exact",
            Json("""{"provider":"spotify","title":"Billie Jean"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(runner.Calls, Is.EqualTo(2));
            Assert.That(receipt.Result?.GetProperty("title").GetString(),
                Is.EqualTo("Billie Jean"));
        });
    }

    [Test]
    public async Task SpotifyExactSelectionRetriesOneUnobservedTransientPlayControl()
    {
        var runner = new SequencedProcessRunner([
            "{\"ok\":false,\"effectObserved\":false,\"error\":\"spotify_exact_play_control_not_found\"}",
            "{\"ok\":true,\"effectObserved\":true,\"title\":\"Billie Jean\",\"processId\":42}",
        ]);
        var adapter = new SpotifyDesktopAdapter(runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.exact",
            Json("""{"provider":"spotify","title":"Billie Jean"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(runner.Calls, Is.EqualTo(2));
            Assert.That(receipt.Result?.GetProperty("title").GetString(),
                Is.EqualTo("Billie Jean"));
        });
    }

    [Test]
    public async Task SpotifyExactSelectionNeverRetriesAfterAnObservedEffect()
    {
        var runner = new SequencedProcessRunner([
            "{\"ok\":false,\"effectObserved\":true,\"error\":\"spotify_exact_play_control_not_found\"}",
            "{\"ok\":true,\"effectObserved\":true,\"title\":\"Wrong retry\",\"processId\":42}",
        ]);
        var adapter = new SpotifyDesktopAdapter(runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.exact",
            Json("""{"provider":"spotify","title":"Billie Jean"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.ErrorCode,
                Is.EqualTo("spotify_exact_play_control_not_found"));
            Assert.That(runner.Calls, Is.EqualTo(1));
        });
    }

    // M86 (held-out t17 «tengo ganas de escuchar reggaetón»): a query press the
    // client never showed playing stays an honest ambiguous failure and is never
    // retried by the adapter — the script already spent its one re-press.
    [Test]
    public async Task SpotifyQueryPressNotSeenPlayingIsNeverRetried()
    {
        var runner = new SequencedProcessRunner([
            "{\"ok\":false,\"effectObserved\":true,\"error\":\"spotify_play_clicked_not_verified\",\"title\":\"Spotify Premium\",\"selectedControl\":\"Reproducir Reggaetón Mix\",\"beforeNowPlaying\":\"after de conep\",\"observedNowPlaying\":\"after de conep\",\"processId\":42}",
            "{\"ok\":true,\"effectObserved\":true,\"title\":\"Wrong retry\",\"processId\":42}",
        ]);
        var adapter = new SpotifyDesktopAdapter(runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.query",
            Json("""{"provider":"spotify","query":"reggaetón"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo("spotify_play_clicked_not_verified"));
            // Round A (fault 2): what was pressed and what the client kept playing, as the script read them.
            Assert.That(receipt.Result?.GetProperty("selectedControl").GetString(), Is.EqualTo("Reproducir Reggaetón Mix"));
            Assert.That(receipt.Result?.GetProperty("beforeNowPlaying").GetString(), Is.EqualTo("after de conep"));
            Assert.That(receipt.Result?.GetProperty("observedNowPlaying").GetString(), Is.EqualTo("after de conep"));
            Assert.That(receipt.Result?.GetProperty("title").GetString(), Is.EqualTo("Spotify Premium"));
            Assert.That(runner.Calls, Is.EqualTo(1));
        });
    }

    // M86: the cold client restored paused on the result's first track; the
    // script proved playback by the paused-to-playing change after its press.
    [Test]
    public async Task SpotifyQueryPlaybackSeenAfterThePressIsVerified()
    {
        var runner = new StubProcessRunner(
            "{\"ok\":true,\"effectObserved\":true,\"error\":null,\"title\":\"Conep - After (feat. Young Miko)\",\"selectedControl\":\"Reproducir Reggaetón Mix\",\"beforeNowPlaying\":\"after feat young miko de conep young miko\",\"observedNowPlaying\":\"after feat young miko de conep young miko\",\"processId\":42}");
        var adapter = new SpotifyDesktopAdapter(runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.query",
            Json("""{"provider":"spotify","query":"reggaetón"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("title").GetString(),
                Is.EqualTo("Conep - After (feat. Young Miko)"));
            Assert.That(receipt.Result?.GetProperty("query").GetString(), Is.EqualTo("reggaetón"));
            Assert.That(receipt.Result?.GetProperty("playbackStatus").GetString(), Is.EqualTo("playing"));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("spotify_windows_uia_postread"));
            Assert.That(runner.LastArguments[^1], Is.EqualTo("query"));
        });
    }

    // M169 (v5a-devG/devI «salsa», «Soda Stereo», «reggaetón»: the search page of a
    // client still building its accessibility tree showed nothing playable for the
    // whole 12 s). The script now waits up to 20 s there with one re-issued search,
    // so its process gets 65 s; the whole call, the exact retry included, stays
    // inside the 85 s the App waits for the core.
    [Test]
    public async Task SpotifyQueryProcessGetsTheExtendedScriptBudget()
    {
        var time = new SteppingTimeProvider();
        var runner = new TimedSequencedProcessRunner(time, [
            (TimeSpan.FromSeconds(23), "{\"ok\":false,\"effectObserved\":false,\"error\":\"spotify_exact_result_not_found\"}"),
        ]);
        var adapter = new SpotifyDesktopAdapter(runner, time: time);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.query",
            Json("""{"provider":"spotify","query":"salsa"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("spotify_exact_result_not_found"));
            Assert.That(runner.Timeouts, Is.EqualTo(new[] { TimeSpan.FromSeconds(65) }));
        });
    }

    [Test]
    public async Task SpotifyExactRetryGetsOnlyWhatIsLeftOfTheCallBudget()
    {
        var time = new SteppingTimeProvider();
        var runner = new TimedSequencedProcessRunner(time, [
            (TimeSpan.FromSeconds(30), "{\"ok\":false,\"effectObserved\":false,\"error\":\"spotify_exact_play_control_not_found\"}"),
            (TimeSpan.FromSeconds(10), "{\"ok\":true,\"effectObserved\":true,\"title\":\"Billie Jean\",\"processId\":42}"),
        ]);
        var adapter = new SpotifyDesktopAdapter(runner, time: time);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.exact",
            Json("""{"provider":"spotify","title":"Billie Jean"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(runner.Timeouts, Is.EqualTo(new[]
            {
                TimeSpan.FromSeconds(65),
                TimeSpan.FromSeconds(85) - TimeSpan.FromSeconds(30) - TimeSpan.FromMilliseconds(400),
            }));
        });
    }

    [Test]
    public async Task SpotifyExactRetryIsNotStartedWhenTheCallBudgetIsSpent()
    {
        var time = new SteppingTimeProvider();
        var runner = new TimedSequencedProcessRunner(time, [
            (TimeSpan.FromSeconds(56), "{\"ok\":false,\"effectObserved\":false,\"error\":\"spotify_exact_result_not_found\",\"searches\":2}"),
            (TimeSpan.FromSeconds(10), "{\"ok\":true,\"effectObserved\":true,\"title\":\"Wrong retry\",\"processId\":42}"),
        ]);
        var adapter = new SpotifyDesktopAdapter(runner, time: time);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.exact",
            Json("""{"provider":"spotify","title":"Billie Jean"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("spotify_exact_result_not_found"));
            Assert.That(runner.Calls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task YouTubeTabControlPausesTheVideoOfTheSessionTab()
    {
        using TemporaryDirectory temporary = new();
        var browser = new StubYouTubeTabSession(
            temporary.Path,
            new CdpMediaControlResult(true, true, "pause", "Amor (Letra) - YouTube",
                "https://www.youtube.com/watch?v=abc", "t1", "paused", string.Empty));
        using var http = new HttpClient();
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.control", Json("""{"action":"stop"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(browser.LastAction, Is.EqualTo("stop"));
            Assert.That(receipt.Result?.GetProperty("playbackStatus").GetString(), Is.EqualTo("paused"));
            Assert.That(receipt.Result?.GetProperty("title").GetString(), Is.EqualTo("Amor (Letra) - YouTube"));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("youtube_cdp_video_postread"));
        });
    }

    // Tanda 5 «pausar el audiolibro»: the tab's video had ended; the reply said the pause «could not be observed».
    [TestCase("pause")]
    [TestCase("stop")]
    public async Task YouTubeTabControlSaysTheVideoWasNotPlayingWithoutClaimingAnEffect(string action)
    {
        using TemporaryDirectory temporary = new();
        var browser = new StubYouTubeTabSession(
            temporary.Path,
            new CdpMediaControlResult(false, false, action, "Emisión inaugural - YouTube",
                "https://www.youtube.com/watch?v=abc", "t1", "stopped", WebBrowserAdapter.YouTubeVideoNotPlaying));
        using var http = new HttpClient();
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.control", Json($$"""{"action":"{{action}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("youtube_playing_video_not_found"));
            Assert.That(receipt.Result?.GetProperty("playbackStatus").GetString(), Is.EqualTo("stopped"));
        });
    }

    [Test]
    public async Task ProviderKeepsTheFailureThatReadItsPlayerOverALaterAdapterWithNoPlayer()
    {
        var tab = new StubExternalAdapter(new ExternalCapabilityReceipt(
            "media.control", false, false, Json("""{"playbackStatus":"paused"}"""),
            "youtube_playing_video_not_found"));
        var client = new StubExternalAdapter(new ExternalCapabilityReceipt(
            "media.control", false, false, null, "spotify_client_not_running"));
        using var provider = new WindowsExternalCapabilityProvider([tab, client]);

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "media.control", Json("""{"action":"pause"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("youtube_playing_video_not_found"));
            Assert.That(tab.Calls, Is.EqualTo(1));
            // A later adapter still gets its chance: another player may be the one playing.
            Assert.That(client.Calls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task ProviderStillReportsTheLastFailureWhenNoAdapterReadItsPlayer()
    {
        var first = new StubExternalAdapter(new ExternalCapabilityReceipt(
            "media.control", false, false, null, "youtube_tab_not_found"));
        var second = new StubExternalAdapter(new ExternalCapabilityReceipt(
            "media.control", false, false, null, "spotify_client_not_running"));
        using var provider = new WindowsExternalCapabilityProvider([first, second]);

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "media.control", Json("""{"action":"pause"}"""), CancellationToken.None);

        Assert.That(receipt.ErrorCode, Is.EqualTo("spotify_client_not_running"));
    }

    // M105 (DEV-D v4a D-s047): «No hay música reproduciéndose porque no se ha abierto ningún video de YouTube» came
    // from the tab's absence replacing the system session's read.
    [Test]
    public async Task ProviderKeepsTheSystemSessionReadOverTheAbsentAssistantTab()
    {
        var session = new StubExternalAdapter(new ExternalCapabilityReceipt(
            "media.status", false, false, null, "media_session_not_found"));
        var tab = new StubExternalAdapter(new ExternalCapabilityReceipt(
            "media.status", false, false, null, "youtube_tab_not_found"));
        using var provider = new WindowsExternalCapabilityProvider([session, tab]);

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "media.status", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("media_session_not_found"));
            Assert.That(tab.Calls, Is.EqualTo(1));
        });
    }

    [TestCase("media.control", """{"action":"pause"}""")]
    [TestCase("media.status", "{}")]
    public async Task YouTubeTabControlStandsAsideWithoutASessionTab(string operation, string arguments)
    {
        using TemporaryDirectory temporary = new();
        var browser = new StubYouTubeTabSession(temporary.Path, result: null);
        using var http = new HttpClient();
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("youtube_tab_not_found"));
        });
    }

    // media.control's sourceApp names a player by the id media.status gave it, compared whole (BAXY Renew audit
    // 2026-10-15): the tab and the local player stand aside before any effect for any other, so «pausa Spotify» never
    // pauses them, and a word of the id is not the id.
    [TestCase("spotify", "media_source_app_not_youtube_tab")]
    [TestCase("youtube", "media_source_app_not_youtube_tab")]
    [TestCase("BAXY YouTube (Edge)", "youtube_tab_not_found")]
    public async Task TheYouTubeTabIsNamedOnlyByItsOwnId(string sourceApp, string error)
    {
        using TemporaryDirectory temporary = new();
        var browser = new StubYouTubeTabSession(temporary.Path, result: null, hasEndpoint: false);
        using var http = new HttpClient();
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.control",
            Json(JsonSerializer.Serialize(new Dictionary<string, string> { ["action"] = "pause", ["sourceApp"] = sourceApp })),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(error));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(browser.Calls, Is.Zero);
        });
    }

    [TestCase("spotify", "media_source_app_not_local_player")]
    [TestCase("mpv", "media_source_app_not_local_player")]
    [TestCase("BAXY YouTube (mpv)", "local_player_inactive")]
    public async Task TheLocalPlayerIsNamedOnlyByItsOwnId(string sourceApp, string error)
    {
        using var adapter = new YouTubeMpvAdapter(mpvPath: null, ytDlpPath: null, nodePath: null);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.control",
            Json(JsonSerializer.Serialize(new Dictionary<string, string> { ["action"] = "pause", ["sourceApp"] = sourceApp })),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(error));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
        });
    }

    [Test]
    public async Task YouTubeTabControlNeverLaunchesABrowserToLookForATab()
    {
        using TemporaryDirectory temporary = new();
        var browser = new StubYouTubeTabSession(temporary.Path, result: null, hasEndpoint: false);
        using var http = new HttpClient();
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.control", Json("""{"action":"pause"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("youtube_tab_not_found"));
            Assert.That(browser.Calls, Is.Zero);
        });
    }

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private sealed class StubBrowserSession(string profile, CdpNavigationResult result)
        : CdpBrowserSession(profile)
    {
        internal override ValueTask<CdpNavigationResult> NavigateAsync(
            Uri target, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(result);
        }
    }

    private sealed class StubBrowserControlSession(string profile, CdpBrowserControlResult result)
        : CdpBrowserSession(profile)
    {
        internal override ValueTask<CdpBrowserControlResult> ControlAsync(
            string action, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(result);
        }
    }

    private sealed class StubBrowserPageSession(string profile, CdpPageReadResult result)
        : CdpBrowserSession(profile)
    {
        internal override ValueTask<CdpPageReadResult> ReadPageAsync(
            int maximumCharacters, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(result);
        }
    }

    private sealed class StubBrowserChainSession(
        string profile,
        CdpNavigationResult navigation,
        CdpPageReadResult page,
        string? observedExecutablePath = null)
        : CdpBrowserSession(profile)
    {
        internal int ReadCalls { get; private set; }

        // APP_MISSING952 (d2cf40e0c): a named navigation verifies the browser's
        // identity by the observed executable; a stub without one stays unverified.
        internal override string? ObservedExecutablePath => observedExecutablePath;

        internal override ValueTask<CdpNavigationResult> NavigateAsync(
            Uri target,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(navigation);
        }

        internal override ValueTask<CdpPageReadResult> ReadPageAsync(
            int maximumCharacters,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ReadCalls++;
            return ValueTask.FromResult(page);
        }
    }

    private sealed class StubBrowserTabsSession(string profile, CdpBrowserTabsResult result)
        : CdpBrowserSession(profile)
    {
        internal override ValueTask<CdpBrowserTabsResult> ListTabsAsync(
            int limit, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(result);
        }
    }

    private sealed class StubBrowserPlaybackSession(string profile, CdpMediaPlaybackResult result)
        : CdpBrowserSession(profile)
    {
        internal override ValueTask<CdpMediaPlaybackResult> PlayYouTubeAsync(
            string query, Uri watchUri, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(result);
        }
    }

    private sealed class StubYouTubeTabSession(
        string profile, CdpMediaControlResult? result, bool hasEndpoint = true)
        : CdpBrowserSession(profile)
    {
        internal string? LastAction { get; private set; }

        internal int Calls { get; private set; }

        internal override bool HasEndpoint => hasEndpoint;

        internal override ValueTask<CdpMediaControlResult?> ControlYouTubeAsync(
            string? action, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            Calls++;
            LastAction = action;
            return ValueTask.FromResult(result);
        }
    }

    private sealed class StubNetflixPlaybackSession(
        string profile, CdpStreamingPlaybackResult result) : CdpBrowserSession(profile)
    {
        internal override ValueTask<CdpStreamingPlaybackResult> PlayNetflixAsync(
            string title, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(result);
        }
    }

    private sealed class StubHttpHandler(string body) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken) => Task.FromResult(
                new HttpResponseMessage(HttpStatusCode.OK)
                {
                    Content = new StringContent(body, Encoding.UTF8, "application/xml"),
                });
    }

    // The public-address readers answer the located body; every other address the search page.
    private sealed class RoutingHttpHandler(string page, string located) : HttpMessageHandler
    {
        internal List<Uri> Asked { get; } = [];

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Uri uri = request.RequestUri!;
            Asked.Add(uri);
            bool locator = uri.Host.Contains("ipwho", StringComparison.Ordinal);
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(locator ? located : page, Encoding.UTF8,
                    locator ? "application/json" : "text/html"),
            });
        }
    }

    private sealed class StubProcessRunner(string output) : IExternalProcessRunner
    {
        internal string[] LastArguments { get; private set; } = [];

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            LastArguments = arguments.ToArray();
            return ValueTask.FromResult(new ExternalProcessResult(0, output, ""));
        }
    }

    private sealed class ThrowingProcessRunner(Exception exception) : IExternalProcessRunner
    {
        internal int Calls { get; private set; }

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable,
            IReadOnlyList<string> arguments,
            TimeSpan timeout,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            Calls++;
            return ValueTask.FromException<ExternalProcessResult>(exception);
        }
    }

    private sealed class CancelingProcessRunner(CancellationTokenSource cancellation)
        : IExternalProcessRunner
    {
        internal int Calls { get; private set; }

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable,
            IReadOnlyList<string> arguments,
            TimeSpan timeout,
            CancellationToken cancellationToken)
        {
            Calls++;
            cancellation.Cancel();
            return ValueTask.FromException<ExternalProcessResult>(
                new OperationCanceledException(cancellationToken));
        }
    }

    private sealed class SlowBluetoothInventory(TimeSpan delay) : IBluetoothDeviceInventory
    {
        public async ValueTask<IReadOnlyList<BluetoothDeviceSnapshot>> ListAsync(
            CancellationToken cancellationToken)
        {
            await Task.Delay(delay, cancellationToken);
            return [];
        }
    }

    // The opened application shows no window for `windowAfter` calls, then a blank page until call `drawnAfter`,
    // then its drawn main window.
    private sealed class ScriptedFocus(
        bool launched,
        int windowAfter,
        int drawnAfter = 0,
        TimeSpan noted = default) : IOpenedApplicationFocus
    {
        private bool _taken;

        internal int FrontCalls { get; private set; }

        internal List<bool> JudgedDrawn { get; } = [];

        public VisibleControlSurface.OpenedApplication? TakeOpened()
        {
            if (_taken)
                return null;
            _taken = true;
            DateTime at = DateTime.UtcNow - noted;
            return new VisibleControlSurface.OpenedApplication(4242, at.AddSeconds(-1), at, launched);
        }

        public VisibleControlSurface.OpenedApplication? PeekOpened() => null;

        public ValueTask<VisibleControlSurface.OpenedSurface> FrontAsync(
            VisibleControlSurface.OpenedApplication opened,
            bool judgeDrawn,
            CancellationToken cancellationToken,
            bool bringToFront = false)
        {
            // v3 point 0, fix 1: a click on the opened application locates its window and presses it where it is,
            // behind the person's; only the pointer, inside a burst of the lease, takes the front (a look never does).
            Assert.That(bringToFront, Is.False, "a click on the opened application never asks for its window in front");
            FrontCalls++;
            JudgedDrawn.Add(judgeDrawn);
            if (FrontCalls <= windowAfter)
                return ValueTask.FromResult(default(VisibleControlSurface.OpenedSurface));
            return ValueTask.FromResult(new VisibleControlSurface.OpenedSurface(
                77, Drawn: !judgeDrawn || FrontCalls > drawnAfter));
        }
    }

    private sealed class CountingLocator : IVisibleControlLocator
    {
        private readonly bool _hit;
        private readonly int _hitFromCall;

        internal CountingLocator(string stage, bool hit, int hitFromCall = 1)
        {
            Stage = stage;
            _hit = hit;
            _hitFromCall = hitFromCall;
        }

        internal int Calls { get; private set; }

        // The last call that hits (none: every call from _hitFromCall on).
        internal int HitsUpTo { get; init; } = int.MaxValue;

        public string Stage { get; }

        public ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
            string operation,
            string label,
            CancellationToken cancellationToken)
        {
            Calls++;
            if (!_hit || Calls < _hitFromCall || Calls > HitsUpTo)
                return ValueTask.FromResult<ExternalCapabilityReceipt?>(null);
            JsonElement result = JsonSerializer.SerializeToElement(new
            {
                version = 1,
                ok = true,
                effectObserved = true,
                error = "",
                name = label,
                controlIdentity = Stage + ".1",
                absentOrDisabled = false,
                selected = false,
                surfaceChanged = true,
                cascadeStage = Stage,
                authority = Stage + "_locate_click_postread",
            });
            return ValueTask.FromResult<ExternalCapabilityReceipt?>(
                new ExternalCapabilityReceipt(operation, true, true, result, null));
        }
    }

    private sealed class CapturingProcessRunner(string output) : IExternalProcessRunner
    {
        internal string[] Arguments { get; private set; } = [];

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            Arguments = arguments.ToArray();
            return ValueTask.FromResult(new ExternalProcessResult(0, output, ""));
        }
    }

    private sealed class SequencedProcessRunner(IReadOnlyList<string> outputs)
        : IExternalProcessRunner
    {
        internal int Calls { get; private set; }

        internal IReadOnlyList<string> LastArguments { get; private set; } = [];

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            LastArguments = arguments.ToArray();
            string output = outputs[Math.Min(Calls, outputs.Count - 1)];
            Calls++;
            return ValueTask.FromResult(new ExternalProcessResult(0, output, ""));
        }
    }

    // M169: each scripted run advances the clock by its own duration and keeps
    // the process budget it was given.
    private sealed class TimedSequencedProcessRunner(
        SteppingTimeProvider time,
        IReadOnlyList<(TimeSpan Duration, string Output)> runs) : IExternalProcessRunner
    {
        internal int Calls { get; private set; }

        internal List<TimeSpan> Timeouts { get; } = [];

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            (TimeSpan duration, string output) = runs[Math.Min(Calls, runs.Count - 1)];
            Calls++;
            Timeouts.Add(timeout);
            time.Advance(duration);
            return ValueTask.FromResult(new ExternalProcessResult(0, output, ""));
        }
    }

    private sealed class SteppingTimeProvider : TimeProvider
    {
        private long _ticks;

        public override long TimestampFrequency => TimeSpan.TicksPerSecond;

        public override long GetTimestamp() => _ticks;

        internal void Advance(TimeSpan duration) => _ticks += duration.Ticks;
    }

    private static void AssertRetryHorizon(
        RecordingDelay delay,
        int expectedIntervals,
        int intervalMilliseconds)
    {
        Assert.That(delay.Calls, Is.EqualTo(expectedIntervals));
        Assert.That(
            delay.Delays,
            Is.All.EqualTo(TimeSpan.FromMilliseconds(intervalMilliseconds)));
        Assert.That(
            delay.Elapsed,
            Is.EqualTo(TimeSpan.FromMilliseconds(
                expectedIntervals * intervalMilliseconds)));
    }

    private sealed class RecordingDelay
    {
        private readonly List<TimeSpan> _delays = [];

        internal int Calls => _delays.Count;

        internal IReadOnlyList<TimeSpan> Delays => _delays;

        internal TimeSpan Elapsed { get; private set; }

        internal ValueTask DelayAsync(
            TimeSpan delay,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            _delays.Add(delay);
            Elapsed += delay;
            return ValueTask.CompletedTask;
        }
    }

    private sealed class FakeAudioEndpoint(
        string endpointId, bool muted, float volume = 0.5f) : IWindowsAudioEndpoint
    {
        private bool _muted = muted;
        private float _volume = volume;
        public string EndpointId { get; } = endpointId;
        public string? ReadDisplayName() => "Test audio endpoint";
        public float ReadVolumeScalar() => _volume;
        public bool ReadMuted() => _muted;
        public void SetVolumeScalar(float scalar, Guid eventContext) => _volume = scalar;
        public void SetMuted(bool value, Guid eventContext) => _muted = value;
        public void Dispose() { }
    }

    private sealed class PostDispatchFailingAudioEndpoint : IWindowsAudioEndpoint
    {
        private bool _setCalled;

        public string EndpointId => "post-dispatch-failure";
        public string? ReadDisplayName() => "Test failing endpoint";
        internal int SetCalls { get; private set; }

        public float ReadVolumeScalar()
        {
            ObjectDisposedException.ThrowIf(_setCalled, this);
            return 0.4f;
        }

        public bool ReadMuted() => false;

        public void SetVolumeScalar(float scalar, Guid eventContext)
        {
            SetCalls++;
            _setCalled = true;
        }

        public void SetMuted(bool value, Guid eventContext) =>
            throw new NotSupportedException();

        public void Dispose() { }
    }

    private sealed class StubExternalAdapter(ExternalCapabilityReceipt receipt)
        : IExternalOperationAdapter
    {
        internal int Calls { get; private set; }

        public bool CanHandle(string operation) => operation == receipt.Operation;

        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation,
            JsonElement arguments,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            Calls++;
            return ValueTask.FromResult(receipt);
        }
    }

    private sealed class StubProcessTerminationPlatform(
        IReadOnlyList<IReadOnlyList<WindowsProcessIdentity>> snapshots,
        WindowsProcessTermination terminateResult) : IWindowsProcessTerminationPlatform
    {
        private int _snapshotIndex;
        internal List<WindowsProcessIdentity> Terminated { get; } = [];

        public IReadOnlyList<WindowsProcessIdentity> Snapshot(string processName)
        {
            if (snapshots.Count == 0) return [];
            IReadOnlyList<WindowsProcessIdentity> snapshot = snapshots[
                Math.Min(_snapshotIndex, snapshots.Count - 1)];
            _snapshotIndex++;
            return snapshot;
        }

        public WindowsProcessTermination Terminate(string processName, WindowsProcessIdentity identity)
        {
            Terminated.Add(identity);
            return terminateResult;
        }
    }

    private sealed class StubPowerTransitionPlatform(string authority, bool accepted)
        : IWindowsPowerTransitionPlatform
    {
        internal string? RequestedAction { get; private set; }

        public WindowsPowerTransitionResult Request(string action)
        {
            RequestedAction = action;
            return new WindowsPowerTransitionResult(accepted, authority);
        }
    }

    private sealed class WifiProcessRunner : IExternalProcessRunner
    {
        internal int ConnectCalls { get; private set; }

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (executable == "netsh.exe")
            {
                ConnectCalls++;
                return ValueTask.FromResult(new ExternalProcessResult(0, "", ""));
            }
            string script = arguments[3];
            string output = script.Contains("show profiles", StringComparison.Ordinal)
                ? "{\"profiles\":[\"Casa\"]}"
                : "{\"connected\":true,\"profile\":\"Casa\"}";
            return ValueTask.FromResult(new ExternalProcessResult(0, output, ""));
        }
    }


    private sealed class VisionHttpHandler : HttpMessageHandler
    {
        protected override async Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken)
        {
            string body = await request.Content!.ReadAsStringAsync(cancellationToken);
            Assert.Multiple(() =>
            {
                Assert.That(request.RequestUri?.IsLoopback, Is.True);
                Assert.That(body, Does.Contain("data:image/bmp;base64,"));
                Assert.That(body, Does.Contain("vision-test"));
            });
            return new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(
                    """{"choices":[{"message":{"content":"A bounded test image."}}]}""",
                    Encoding.UTF8,
                    "application/json"),
            };
        }
    }

    private sealed class TemporaryDirectory : IDisposable
    {
        internal string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(), "baxy-external-tests-" + Guid.NewGuid().ToString("N"));

        internal TemporaryDirectory() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }
}
