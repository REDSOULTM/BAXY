using System.Diagnostics;
using System.Globalization;
using System.Net;
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
            [[identity], []], terminateResult: true);
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
            [[identity], [identity]], terminateResult: false);
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
    public async Task ExactNamedProcessTerminationAllowsAWindowsRestartWithANewIdentity()
    {
        var original = new WindowsProcessIdentity(5151, 638900000000000001);
        var replacement = new WindowsProcessIdentity(6262, 638900000000000099);
        var platform = new StubProcessTerminationPlatform(
            [[original], [replacement]], terminateResult: true);
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
        var platform = new StubProcessTerminationPlatform([], terminateResult: true);
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
            Arguments = "/d /c ping -t 127.0.0.1",
            CreateNoWindow = true,
            UseShellExecute = false,
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
            Assert.That(receipt.ErrorCode, Is.EqualTo("smtc_session_adapter_required"));
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
            Assert.That(receipt.ErrorCode, Is.EqualTo("smtc_session_adapter_required"));
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
        var adapter = new WingetPackageAdapter(runner, Path.Combine(Path.GetTempPath(), "baxy-winget-tests"), _ => null);

        ExternalCapabilityReceipt? receipt = null;
        Assert.DoesNotThrowAsync(async () =>
        {
            receipt = await adapter.InvokeAsync(
                "package.install.prepare",
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
    public async Task FallbackPeripheralInventoryDispatchesOnlyRequestedCategory()
    {
        const string output = """
            {"printers":[{"Name":"Printer","PrinterStatus":0}],"scanners":[],"usb":[],"mice":[],"keyboards":[]}
        """;
        var runner = new StubProcessRunner(output);
        var adapter = new WindowsInventoryAdapter(runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "peripheral.list",
            Json("""{"kind":"printer"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(
                receipt.Result?.GetProperty("devices").GetArrayLength(),
                Is.EqualTo(1));
            Assert.That(
                receipt.Result?.GetProperty("devices")[0].GetProperty("kind").GetString(),
                Is.EqualTo("printer"));
            Assert.That(runner.LastArguments[^1], Is.EqualTo("printer"));
            Assert.That(runner.LastArguments[3], Does.Contain("$kind=[string]$args[0]"));
        });
    }

    [Test]
    public async Task SlowWinRtBluetoothInventoryYieldsToTheBoundedFallback()
    {
        using TemporaryDirectory temporary = new();
        var first = new WindowsDeviceControlAdapter(
            temporary.Path,
            temporary.Path,
            new StubProcessRunner(""),
            new SlowBluetoothInventory(TimeSpan.FromSeconds(1)),
            TimeSpan.FromMilliseconds(50));
        var second = new StubExternalAdapter(new ExternalCapabilityReceipt(
            "bluetooth.device.list",
            false,
            true,
            Json("""{"version":1,"count":0,"devices":[],"authority":"bounded_fallback"}"""),
            null));
        using var provider = new WindowsExternalCapabilityProvider([first, second]);
        var stopwatch = Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "bluetooth.device.list",
            Json("{}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(stopwatch.Elapsed, Is.LessThan(TimeSpan.FromMilliseconds(500)));
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("bounded_fallback"));
            Assert.That(second.Calls, Is.EqualTo(1));
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
            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", "https://vision.example/v1/chat/completions");
            Environment.SetEnvironmentVariable("BAXY_VISION_MODEL", "vision-test");
            using var http = new HttpClient(new VisionHttpHandler());
            using var adapter = new CaptureVisionAdapter(directory.Path, http);

            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
                "vision.describe",
                Json($$"""{"captureId":"{{captureId}}","prompt":"describe"}"""),
                CancellationToken.None);

            Assert.Multiple(() =>
            {
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
    public async Task ScheduledNotificationRequiresWindowsTaskIdentityPostread()
    {
        using TemporaryDirectory temporary = new();
        string scheduler = Path.Combine(temporary.Path, "WindowsScheduledNotification.ps1");
        await File.WriteAllTextAsync(scheduler, "# fixture");
        var runner = new NotificationSchedulerRunner();
        var adapter = new WindowsScheduledNotificationAdapter(
            temporary.Path, runner, scheduler);
        string due = DateTimeOffset.UtcNow.AddHours(1).ToString("O");

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "notification.schedule",
            Json($$"""{"dueUtc":"{{due}}","kind":"alarm","title":"Prueba"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("taskName").GetString(),
                Is.EqualTo(runner.TaskName));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("windows_task_scheduler_postread"));
            Assert.That(File.Exists(Path.Combine(
                temporary.Path, "scheduled-notifications", runner.TaskName + ".ps1")), Is.True);
        });
    }

    [Test]
    public async Task RecurringNotificationPassesARealHourlyTaskTriggerRequest()
    {
        using TemporaryDirectory temporary = new();
        string scheduler = Path.Combine(temporary.Path, "WindowsScheduledNotification.ps1");
        await File.WriteAllTextAsync(scheduler, "# fixture");
        var runner = new NotificationSchedulerRunner();
        var adapter = new WindowsScheduledNotificationAdapter(temporary.Path, runner, scheduler);
        string due = DateTimeOffset.UtcNow.AddHours(1).ToString("O");

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "notification.schedule",
            Json($$"""{"dueUtc":"{{due}}","kind":"reminder","recurrence":"hourly","title":"Drink water"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("recurrence").GetString(), Is.EqualTo("hourly"));
            Assert.That(runner.Arguments, Does.Contain("schedule-recurring"));
            Assert.That(runner.Arguments, Does.Contain("hourly"));
        });
    }

    [Test]
    public async Task NotificationDiagnosticsReturnsObservedServiceTasksAndReceipts()
    {
        using TemporaryDirectory temporary = new();
        string scheduler = Path.Combine(temporary.Path, "WindowsScheduledNotification.ps1");
        await File.WriteAllTextAsync(scheduler, "# fixture");
        const string output = "{\"ok\":true,\"schedulerRunning\":true," +
            "\"toastEnabled\":true,\"healthy\":true,\"taskCount\":1," +
            "\"firedReceiptCount\":1,\"issueCount\":0,\"tasks\":[{" +
            "\"taskName\":\"BAXY-Reminder-private\",\"state\":\"Ready\"," +
            "\"lastTaskResult\":0,\"resultAcceptable\":true}]}";
        var adapter = new WindowsScheduledNotificationAdapter(
            temporary.Path, new StubProcessRunner(output), scheduler);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "notification.diagnose", Json("{}"), CancellationToken.None);

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
        string scheduler = Path.Combine(temporary.Path, "WindowsScheduledNotification.ps1");
        await File.WriteAllTextAsync(scheduler, "# fixture");
        const string taskName = "BAXY-Alarm-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        string due = DateTimeOffset.UtcNow.AddHours(2).ToString("O");
        var runner = new SequencedProcessRunner([
            $$"""{"ok":true,"effectObserved":false,"matchCount":1,"taskName":"{{taskName}}","nextRunUtc":"{{due}}"}""",
            $$"""{"ok":true,"effectObserved":true,"effectBoundaryCrossed":true,"canceled":true,"taskName":"{{taskName}}","nextRunUtc":"{{due}}","authority":"windows_task_scheduler_exact_identity_absence_postread"}""",
        ]);
        var adapter = new WindowsScheduledNotificationAdapter(temporary.Path, runner, scheduler);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "notification.cancel.at",
            Json("""{"kind":"alarm","hour":5,"period":"pm"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result?.GetProperty("taskName").GetString(), Is.EqualTo(taskName));
            Assert.That(receipt.Result?.GetProperty("expectedNextRunUtc").GetString(), Is.EqualTo(due));
            Assert.That(runner.Calls, Is.EqualTo(2));
        });
    }

    [Test]
    public async Task ExactClockNotificationCancellationRefusesAmbiguousMatchesBeforeEffect()
    {
        using TemporaryDirectory temporary = new();
        string scheduler = Path.Combine(temporary.Path, "WindowsScheduledNotification.ps1");
        await File.WriteAllTextAsync(scheduler, "# fixture");
        var runner = new SequencedProcessRunner([
            "{\"ok\":false,\"effectObserved\":false,\"effectBoundaryCrossed\":false,\"matchCount\":2}",
        ]);
        var adapter = new WindowsScheduledNotificationAdapter(temporary.Path, runner, scheduler);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "notification.cancel.at",
            Json("""{"kind":"alarm","hour":5,"period":"pm"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("notification_clock_ambiguous"));
            Assert.That(runner.Calls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task ExactClockNotificationCancellationRefusesChangedIdentityBeforeEffect()
    {
        using TemporaryDirectory temporary = new();
        string scheduler = Path.Combine(temporary.Path, "WindowsScheduledNotification.ps1");
        await File.WriteAllTextAsync(scheduler, "# fixture");
        const string taskName = "BAXY-Alarm-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
        string due = DateTimeOffset.UtcNow.AddHours(2).ToString("O");
        var runner = new SequencedProcessRunner([
            $$"""{"ok":true,"effectObserved":false,"matchCount":1,"taskName":"{{taskName}}","nextRunUtc":"{{due}}"}""",
            "{\"ok\":false,\"effectObserved\":false,\"effectBoundaryCrossed\":false,\"error\":\"task_changed_before_effect\"}",
        ]);
        var adapter = new WindowsScheduledNotificationAdapter(temporary.Path, runner, scheduler);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "notification.cancel.at",
            Json("""{"kind":"alarm","hour":5,"period":"pm"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("notification_scheduler_precondition_changed"));
            Assert.That(runner.Calls, Is.EqualTo(2));
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
        var adapter = new WindowsKnownFileAdapter(temporary.Path, roots);

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

    [Test]
    public async Task AbsoluteFileDeleteIsIdempotentAndUsesPrivateTrashInsideTemp()
    {
        using TemporaryDirectory temporary = new();
        string source = Path.Combine(temporary.Path, "delete-me.txt");
        await File.WriteAllTextAsync(source, "recoverable");
        var adapter = new WindowsKnownFileAdapter(
            temporary.Path, new Dictionary<string, string[]>());

        ExternalCapabilityReceipt missing = await adapter.InvokeAsync(
            "filesystem.path.ensure.absent",
            Json("""{"path":"C:/no/existe/zzz_fake.txt"}"""), CancellationToken.None);
        ExternalCapabilityReceipt removed = await adapter.InvokeAsync(
            "filesystem.path.ensure.absent",
            Json(JsonSerializer.Serialize(new { path = source })), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(missing.Verified, Is.True);
            Assert.That(missing.EffectObserved, Is.False);
            Assert.That(missing.EffectMayHaveOccurred, Is.False);
            Assert.That(missing.Result?.GetProperty("alreadyAbsent").GetBoolean(), Is.True);
            Assert.That(removed.Verified, Is.True);
            Assert.That(removed.EffectObserved, Is.True);
            Assert.That(File.Exists(source), Is.False);
            Assert.That(Directory.GetFiles(Path.Combine(temporary.Path, "known-file-trash")),
                Has.Length.EqualTo(1));
        });
    }

    [Test]
    public async Task VisibleButtonClickRequiresUiaPostreadThatTheControlChanged()
    {
        using TemporaryDirectory temporary = new();
        string script = Path.Combine(temporary.Path, "DesktopClickVisible.ps1");
        await File.WriteAllTextAsync(script, "# fixture");
        var runner = new CapturingProcessRunner(
            "{\"version\":1,\"ok\":true,\"effectObserved\":true," +
            "\"error\":\"\",\"name\":\"Aceptar\",\"controlIdentity\":\"1.2.3\"," +
            "\"absentOrDisabled\":true,\"authority\":\"windows_uia_invoke_postread\"}");
        var adapter = new WindowsVisibleControlAdapter(runner, script);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"aceptar"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("absentOrDisabled").GetBoolean(), Is.True);
            Assert.That(runner.Arguments, Does.Contain("-LabelBase64"));
        });
    }

    [Test]
    public async Task VisibleClickAcceptsASelectedControlPostread()
    {
        using TemporaryDirectory temporary = new();
        string script = Path.Combine(temporary.Path, "DesktopClickVisible.ps1");
        await File.WriteAllTextAsync(script, "# fixture");
        var runner = new CapturingProcessRunner(
            "{\"version\":1,\"ok\":true,\"effectObserved\":true," +
            "\"error\":\"\",\"name\":\"Library\",\"controlIdentity\":\"1.2.3\"," +
            "\"absentOrDisabled\":false,\"selected\":true,\"surfaceChanged\":false," +
            "\"cascadeStage\":\"uia\",\"authority\":\"windows_uia_invoke_postread\"}");
        var adapter = new WindowsVisibleControlAdapter(runner, script);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Library"}"""),
            CancellationToken.None);

        Assert.That(receipt.Verified, Is.True);
        Assert.That(receipt.Result?.GetProperty("selected").GetBoolean(), Is.True);
    }

    [Test]
    public async Task VisibleClickCascadeSkipsOcrAndVisionWhenUiaFindsTheControl()
    {
        using TemporaryDirectory temporary = new();
        string script = Path.Combine(temporary.Path, "DesktopClickVisible.ps1");
        await File.WriteAllTextAsync(script, "# fixture");
        var runner = new CapturingProcessRunner(
            "{\"version\":1,\"ok\":true,\"effectObserved\":true," +
            "\"error\":\"\",\"name\":\"Aceptar\",\"controlIdentity\":\"1.2.3\"," +
            "\"absentOrDisabled\":true,\"selected\":false,\"surfaceChanged\":false}");
        var ocr = new CountingLocator("ocr", hit: true);
        var vision = new CountingLocator("vision", hit: true);
        var adapter = new WindowsVisibleControlAdapter(runner, script, ocr, vision);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"aceptar"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(ocr.Calls, Is.Zero);
            Assert.That(vision.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task VisibleClickCascadeUsesOcrWhenUiaExposesNothing()
    {
        using TemporaryDirectory temporary = new();
        string script = Path.Combine(temporary.Path, "DesktopClickVisible.ps1");
        await File.WriteAllTextAsync(script, "# fixture");
        var runner = new CapturingProcessRunner(
            "{\"version\":1,\"ok\":false,\"effectObserved\":false," +
            "\"error\":\"visible_button_not_found\",\"name\":\"\"," +
            "\"controlIdentity\":\"\",\"absentOrDisabled\":false}");
        var ocr = new CountingLocator("ocr", hit: true);
        var vision = new CountingLocator("vision", hit: true);
        var adapter = new WindowsVisibleControlAdapter(runner, script, ocr, vision);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Library"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("cascadeStage").GetString(), Is.EqualTo("ocr"));
            Assert.That(ocr.Calls, Is.EqualTo(1));
            Assert.That(vision.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task VisibleClickCascadeUsesVisionOnlyAfterUiaAndOcrMiss()
    {
        using TemporaryDirectory temporary = new();
        string script = Path.Combine(temporary.Path, "DesktopClickVisible.ps1");
        await File.WriteAllTextAsync(script, "# fixture");
        var runner = new CapturingProcessRunner(
            "{\"version\":1,\"ok\":false,\"effectObserved\":false," +
            "\"error\":\"visible_button_not_found\",\"name\":\"\"," +
            "\"controlIdentity\":\"\",\"absentOrDisabled\":false}");
        var ocr = new CountingLocator("ocr", hit: false);
        var vision = new CountingLocator("vision", hit: true);
        var adapter = new WindowsVisibleControlAdapter(runner, script, ocr, vision);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Library"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("cascadeStage").GetString(), Is.EqualTo("vision"));
            Assert.That(ocr.Calls, Is.EqualTo(1));
            Assert.That(vision.Calls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task NamedSandboxFilesAppendDiffAndMoveWithHashPostreads()
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "filesystem-sandbox");
        Directory.CreateDirectory(sandbox);
        await File.WriteAllTextAsync(Path.Combine(sandbox, "notas.txt"), "uno");
        await File.WriteAllTextAsync(Path.Combine(sandbox, "README.md"), "uno\ndos\n");
        await File.WriteAllTextAsync(Path.Combine(sandbox, "README.backup.md"), "uno\ntres\n");
        await File.WriteAllTextAsync(Path.Combine(sandbox, "backup.txt"), "payload");
        var adapter = new WindowsSandboxNamedFileAdapter(temporary.Path);

        ExternalCapabilityReceipt appended = await adapter.InvokeAsync(
            "filesystem.sandbox.append.named",
            Json("""{"fileName":"notas.txt","text":"\n"}"""), CancellationToken.None);
        ExternalCapabilityReceipt diff = await adapter.InvokeAsync(
            "filesystem.sandbox.diff.named",
            Json("""{"leftQuery":"README.md","rightQuery":"backup"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt moved = await adapter.InvokeAsync(
            "filesystem.sandbox.move.named",
            Json("""{"sourceFileName":"backup.txt","destinationRelativePath":"logs/backup.txt"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(appended.Verified, Is.True);
            Assert.That(appended.Result?.GetProperty("appendedBytes").GetInt32(), Is.EqualTo(1));
            Assert.That(diff.Verified, Is.True);
            Assert.That(diff.EffectMayHaveOccurred, Is.False);
            Assert.That(diff.Result?.GetProperty("changedLines")[0].GetInt32(), Is.EqualTo(2));
            Assert.That(moved.Verified, Is.True);
            Assert.That(File.Exists(Path.Combine(sandbox, "logs", "backup.txt")), Is.True);
            Assert.That(File.Exists(Path.Combine(sandbox, "backup.txt")), Is.False);
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
            selectScript);

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
            selectScript);

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
        var adapter = new WindowsDesktopInteractionAdapter(
            new StubProcessRunner(
                "{\"version\":1,\"ok\":true,\"effectObserved\":true," +
                "\"key\":\"escape\",\"acceptedEvents\":2," +
                "\"authority\":\"win32_sendinput_return_count\"}"),
            folderScript,
            fileScript,
            selectScript,
            keyScript);

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
    public async Task TextAndPointerInputUseTheVerifiedDesktopInputScript()
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
        var adapter = new WindowsDesktopInteractionAdapter(
            runner, folderScript, fileScript, selectScript, keyScript);

        ExternalCapabilityReceipt typed = await adapter.InvokeAsync(
            "input.text.type", Json("""{"text":"hola"}"""), CancellationToken.None);
        string encodedText = runner.Arguments[^1];
        ExternalCapabilityReceipt pointer = await adapter.InvokeAsync(
            "input.pointer.control", Json("""{"action":"move_center"}"""),
            CancellationToken.None);
        string[] pointerArguments = runner.Arguments.ToArray();
        ExternalCapabilityReceipt layout = await adapter.InvokeAsync(
            "input.keyboard.layout", Json("""{"language":"spanish"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(typed.Verified, Is.True);
            Assert.That(Encoding.UTF8.GetString(Convert.FromBase64String(encodedText)),
                Is.EqualTo("hola"));
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
            "",
            "{\"connected\":true,\"profile\":\"Galaxy Phone 5G 0000\"}",
        ]);
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path, temporary.Path, runner, delays.DelayAsync);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "wifi.connect.named",
            Json("""{"profileName":"galaxy"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("connected").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("Galaxy"));
            Assert.That(runner.Calls, Is.EqualTo(3));
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

    [Test]
    public async Task StructuredWebSearchRejectsDtdAndReturnsBoundedHttpsResults()
    {
        string page = SearchResultsPage(("Example", "https://example.com/", "Result"));
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(new StubHttpHandler(page));
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"Example","limit":1}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result?.GetProperty("count").GetInt32(), Is.EqualTo(1));
            Assert.That(receipt.Result?.GetProperty("results")[0].GetProperty("url").GetString(),
                Is.EqualTo("https://example.com/"));
        });
    }

    // Uso real tanda 4c «en qué lugares puedo pedir comida para llevar cerca»: a
    // search near the person carries this PC's city, read from its public address;
    // only the city name joins the query (no coordinates), and the receipt says so.
    [Test]
    public async Task ASearchNearbyCarriesThisPcsCityAndOnlyItsName()
    {
        string page = SearchResultsPage(
            ("Comida para llevar en Curico", "https://example.com/valpo", "Locales de comida para llevar en Curico"));
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        var handler = new RoutingHttpHandler(page,
            """{"success":true,"country":"Chile","region":"Curico","city":"Curico","latitude":-34.9828,"longitude":-71.2394}""");
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"comida para llevar cerca","nearby":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("query").GetString(), Is.EqualTo("comida para llevar cerca Curico"));
            Assert.That(receipt.Result?.GetProperty("near").GetString(), Is.EqualTo("Curico"));
            Assert.That(handler.Asked.Where(uri => !uri.Host.Contains("ipwho", StringComparison.Ordinal)),
                Has.All.Matches<Uri>(uri => !uri.Query.Contains("33.03", StringComparison.Ordinal)
                    && !uri.Query.Contains("71.62", StringComparison.Ordinal)));
        });
    }

    [Test]
    public async Task ASearchNearbyWithoutThisPcsPlaceIsAnHonestAbsenceNotAGenericSearch()
    {
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        var handler = new RoutingHttpHandler(SearchResultsPage(("x", "https://example.com/", "x")), """{"success":false}""");
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"farmacias cerca","nearby":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("web_search_place_unavailable"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(handler.Asked, Has.None.Matches<Uri>(uri => uri.Query.Contains("farmacias", StringComparison.Ordinal)));
        });
    }

    [Test]
    public async Task ASearchWithoutNearbyNeverAsksWhereThisPcIs()
    {
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        var handler = new RoutingHttpHandler(
            SearchResultsPage(("Hoteles en Madrid", "https://example.com/madrid", "Hoteles en Madrid")), """{"success":true}""");
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"hoteles en Madrid"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("query").GetString(), Is.EqualTo("hoteles en Madrid"));
            Assert.That(receipt.Result?.TryGetProperty("near", out _), Is.False);
            Assert.That(handler.Asked, Has.None.Matches<Uri>(uri => uri.Host.Contains("ipwho", StringComparison.Ordinal)
                || uri.Host.Contains("ip-api", StringComparison.Ordinal)));
        });
    }

    [Test]
    public async Task StructuredWebSearchRejectsAValidButUnrelatedFeed()
    {
        string page = SearchResultsPage(
            ("Soldier Field", "https://example.com/stadium", "Sports venue in Chicago"));
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(
            temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(new StubHttpHandler(page));
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search",
            Json("""{"query":"BAXY assistant audit","limit":5}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("web_search_results_irrelevant"));
            Assert.That(receipt.Result, Is.Null);
        });
    }

    [Test]
    public async Task StructuredWebSearchReturnsOnlyResultsRelatedToTheQuery()
    {
        string page = SearchResultsPage(
            ("Unrelated marketplace", "https://example.com/shop", "Discount products"),
            ("Windows 11 Calculator help", "https://support.example.com/windows/calculator",
                "Use Calculator on Windows 11"));
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(
            temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(new StubHttpHandler(page));
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search",
            Json("""{"query":"Windows 11 calculator","limit":5}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("count").GetInt32(), Is.EqualTo(1));
            Assert.That(receipt.Result?.GetProperty("results")[0]
                .GetProperty("title").GetString(), Does.Contain("Calculator"));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("marketplace"));
        });
    }

    [Test]
    public async Task StructuredWebSearchAcceptsAQuestionWhosePageConjugatesItsVerbs()
    {
        // H0060: the mind binds the person's own words, typo included («me falla mucho
        // whatsapp porqeu suele fallar»). No page repeats «porqeu», «mucho» or «suele»,
        // so those terms are unverifiable on this page; «whatsapp» and «fallar»→«falla»
        // are, and a page that shares half of the verifiable terms is pertinent.
        string page = SearchResultsPage(
            ("Problemas con WhatsApp y sus soluciones",
                "https://example.net/whatsapp/razones-fallos/",
                "Son muchas las razones por las que WhatsApp falla; recopilamos los fallos habituales."),
            ("Recetas de cocina", "https://example.org/recetas", "Pizza casera paso a paso"));
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(
            temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(new StubHttpHandler(page));
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search",
            Json("""{"query":"me falla mucho whatsapp porqeu suele fallar","limit":5}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result?.GetProperty("count").GetInt32(), Is.EqualTo(1));
            Assert.That(receipt.Result?.GetProperty("results")[0].GetProperty("url").GetString(),
                Is.EqualTo("https://example.net/whatsapp/razones-fallos/"));
            Assert.That(receipt.Result?.GetProperty("results")[0].GetProperty("snippet").GetString(),
                Does.Not.Contain("<strong>"));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("duckduckgo_lite_https"));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("recetas"));
        });
    }

    [Test]
    public async Task StructuredWebSearchReportsABlockPageAsUnavailableNotAsNoResults()
    {
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(
            temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(new StubHttpHandler(
            "<html><body><form>Please verify you are a human</form></body></html>"));
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search",
            Json("""{"query":"Windows 11 calculator","limit":5}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("web_search_unavailable"));
            Assert.That(receipt.Result, Is.Null);
        });
    }

    // D32: a knowledge question is answered by Wikipedia's open API, Spanish first for
    // a Spanish question; the request carries the project's Wikimedia User-Agent and
    // only the query's content words, and the general engine is never asked.
    [Test]
    public async Task AKnowledgeQuestionIsAnsweredByWikipediaWithTheProjectUserAgent()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["es.wikipedia.org"] = WikipediaAnswer("es",
                ("Canberra (desambiguación)", "", true),
                ("Canberra", "Canberra es la capital de Australia.​\n\nEstá en el Territorio de la Capital Australiana.", false),
                ("Territorio de la Capital Australiana", "Territorio federal de Australia que contiene la capital, Canberra.", false)),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"¿Cuál es la capital de Australia?","limit":5}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("wikipedia_es_api"));
            Assert.That(receipt.Result?.GetProperty("count").GetInt32(), Is.EqualTo(2));
            JsonElement first = receipt.Result!.Value.GetProperty("results")[0];
            Assert.That(first.GetProperty("title").GetString(), Is.EqualTo("Canberra"));
            Assert.That(first.GetProperty("url").GetString(), Is.EqualTo("https://es.wikipedia.org/wiki/Canberra"));
            Assert.That(first.GetProperty("snippet").GetString(),
                Is.EqualTo("Canberra es la capital de Australia. Está en el Territorio de la Capital Australiana."));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("desambiguaci"));
            Assert.That(handler.Asked, Has.Count.EqualTo(1));
            Assert.That(handler.Asked[0].Uri.Host, Is.EqualTo("es.wikipedia.org"));
            Assert.That(handler.Asked[0].UserAgent,
                Does.Match(@"^BAXY/\d+\.\d+ \(https://github\.com/REDSOULTM/baxy-assistant\)$"));
            Assert.That(Uri.UnescapeDataString(handler.Asked[0].Uri.Query), Does.Contain("gsrsearch=capital australia&"));
        });
    }

    [Test]
    public async Task AnEnglishQuestionAsksEnglishWikipediaFirstAndSpanishOnlyWhenItHasNothing()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["en.wikipedia.org"] = WikipediaAnswer("en", ("Bran Castle", "A castle in Romania.", false)),
            ["es.wikipedia.org"] = WikipediaAnswer("es",
                ("Drácula", "Drácula es una novela de Bram Stoker publicada en 1897.", false)),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"who wrote Dracula"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(handler.Asked.Select(asked => asked.Uri.Host),
                Is.EqualTo(new[] { "en.wikipedia.org", "es.wikipedia.org" }));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("wikipedia_es_api"));
            Assert.That(receipt.Result?.GetProperty("results")[0].GetProperty("url").GetString(),
                Is.EqualTo("https://es.wikipedia.org/wiki/Dr%C3%A1cula"));
        });
    }

    // What changes by the day (a price, the news, today) is not an encyclopedia's:
    // Wikipedia is never asked; the news feed is, and when it does not answer the
    // general engine does.
    [Test]
    public async Task ATimeBoundQuestionSkipsWikipediaForTheGeneralEngine()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["es.wikipedia.org"] = WikipediaAnswer("es", ("Dólar estadounidense", "El dólar es la moneda de Estados Unidos.", false)),
            ["lite.duckduckgo.com"] = new(HttpStatusCode.OK, SearchResultsPage(
                ("Precio del dólar hoy en Chile", "https://example.cl/dolar", "El dólar cierra hoy a 950 pesos.")), "text/html"),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"precio del dólar hoy"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("duckduckgo_lite_https"));
            Assert.That(handler.Asked.Select(asked => asked.Uri.Host),
                Is.EqualTo(new[] { "news.google.com", "lite.duckduckgo.com" }));
        });
    }

    // Nothing searched (Wikipedia down, the engine behind a challenge page) is an
    // honest «could not look it up», never «not found» and never the page's text.
    [Test]
    public async Task WhenNoSourceSearchesTheReceiptSaysSearchUnavailable()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["es.wikipedia.org"] = new(HttpStatusCode.ServiceUnavailable, "busy", "text/plain"),
            ["en.wikipedia.org"] = new(HttpStatusCode.OK, "<html>not json</html>", "text/html"),
            ["lite.duckduckgo.com"] = new(HttpStatusCode.OK,
                "<html><body><form>Please verify you are a human. Buy now!</form></body></html>", "text/html"),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"primer libro de zombies"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("web_search_unavailable"));
            Assert.That(receipt.Result, Is.Null);
            Assert.That(handler.Asked.Select(asked => asked.Uri.Host),
                Is.EqualTo(new[] { "es.wikipedia.org", "en.wikipedia.org", "lite.duckduckgo.com" }));
        });
    }

    [Test]
    public void WikipediaReadingKeepsRankDropsForeignHostsAndPicksTheQueryLanguage()
    {
        const string body = """
            {"batchcomplete":true,"query":{"pages":[
              {"pageid":2,"ns":0,"title":"Segundo","index":2,"fullurl":"https://es.wikipedia.org/wiki/Segundo","extract":"Dos."},
              {"pageid":3,"ns":0,"title":"Ajeno","index":0,"fullurl":"https://example.com/wiki/Ajeno","extract":"No."},
              {"pageid":1,"ns":0,"title":"Primero","index":1,"fullurl":"https://es.wikipedia.org/wiki/Primero","extract":"Uno.\n\nOtro párrafo."}
            ]}}
            """;
        List<(string Title, string Url, string Snippet)> parsed = WikipediaSearchSource.ParseSearchResponse(body, "es");
        Assert.Multiple(() =>
        {
            Assert.That(parsed.Select(item => item.Title), Is.EqualTo(new[] { "Primero", "Segundo" }));
            Assert.That(parsed[0].Snippet, Is.EqualTo("Uno. Otro párrafo."));
            Assert.That(WikipediaSearchSource.ParseSearchResponse("""{"batchcomplete":true}""", "es"), Is.Empty);
            Assert.Throws<JsonException>(() => WikipediaSearchSource.ParseSearchResponse(
                """{"error":{"code":"maxlag"}}""", "es"));
            Assert.That(WikipediaSearchSource.Languages("quién escribió Drácula", CultureInfo.InvariantCulture),
                Is.EqualTo(new[] { "es", "en" }));
            Assert.That(WikipediaSearchSource.Languages("who wrote Dracula", new CultureInfo("es-CL")),
                Is.EqualTo(new[] { "en", "es" }));
            Assert.That(WikipediaSearchSource.Languages("Dracula", new CultureInfo("en-US")),
                Is.EqualTo(new[] { "en", "es" }));
            Assert.That(SearchPertinence.ContentTerms("busca en internet quién escribió Drácula"), Is.EqualTo(new[] { "dracula" }));
            Assert.That(WikipediaSearchSource.IsEncyclopedic("quién ganó el Mundial de 2010"), Is.True);
            Assert.That(WikipediaSearchSource.IsEncyclopedic("noticias de Chile"), Is.False);
            Assert.That(WikipediaSearchSource.IsEncyclopedic("what's the weather tomorrow"), Is.False);
        });
    }

    // M51: the results Wikipedia gave in the official-window run v3a-final (2026-09-28),
    // with the queries the mind sent. Each was published as if it answered; none does.
    // The two knowledge questions of D32 still pass with their real extracts.
    [Test]
    public void OnlyAResultAboutTheQueryPassesThePertinenceGate()
    {
        (string Query, string Title, string Snippet, bool Pertinent)[] cases =
        [
            ("any new status updates", "HTTP 301",
                "On the World Wide Web, HTTP 301, or 301 Moved Permanently, is the HTTP status code used for permanent redirecting. It means that links or records to this URL should be updated to the destination provided in the Location field of the server response.", false),
            ("any new status updates", "National Living Treasure (Australia)",
                "National Living Treasure is a status created and occasionally updated by the National Trust of Australia's New South Wales branch, awarded to up to 100 living people.", false),
            ("Show me something funny about food.", "Remotely Funny",
                "Remotely Funny is a British children's game show hosted by SAARA. The show is produced by Twenty Twenty Kids for CBBC.", false),
            ("Show me something funny about food.", "The Shnookums & Meat Funny Cartoon Show",
                "The Shnookums & Meat Funny Cartoon Show is a half-hour American animated comedy television series produced by Walt Disney Television Animation and aired in 1995.", false),
            ("el artículo más leído de Wikipedia", "Artículo II de la Constitución de los Estados Unidos",
                "El Artículo II de la Constitución de los Estados Unidos crea el poder ejecutivo del Gobierno estadounidense, el cual está formado por el presidente y otros funcionarios principales.", false),
            ("el artículo más leído de Wikipedia", "Cómo hablar de los libros que no se han leído",
                "Cómo hablar de los libros que no se han leído (en francés: Comment parler des livres que l'on n'a pas lus ?) es un ensayo del psicoanalista, profesor de literatura, crítico literario y escritor francés Pierre Bayard.", false),
            ("el artículo más leído de Wikipedia", "Las fuentes del comportamiento soviético",
                "El Artículo X es un artículo, formalmente titulado Las fuentes de la conducta soviética, escrito por George F. Kennan y publicado bajo el seudónimo \"X\" en el número de julio de 1947 de la revista Foreign Affairs.", false),
            ("Show me gas stations in Buford.", "Buford, Wyoming",
                "Buford is an unincorporated community and ghost town in Albany County, Wyoming, United States. It is located between Laramie and Cheyenne on Interstate 80. Its last resident, who had been the lone resident for nearly two decades, left in 2012.", false),
            ("¿Cuáles son los números ganadores del loto?", "Baloto",
                "Baloto es un juego de tipo loto en línea de suerte y azar en Colombia, donde el jugador por $9.000 apuesta por un acumulado multimillonario inicial de $4.000 millones de pesos colombianos, que se irá acumulando en cada sorteo, si no se tiene un ganador.", false),
            ("Get train schedules to Manchester on Wednesday.", "Opening of the Liverpool and Manchester Railway",
                "The Liverpool and Manchester Railway (L&M) opened on 15 September 1830. Work on the L&M had begun in the 1820s, to connect the textile mills of the city of Manchester with the nearest deep water port at the Port of Liverpool.", false),
            ("what is the rate for 500 cad in usd", "List of European countries by minimum wage",
                "Most minimum wages are fixed at a monthly rate, but some countries set their minimum wage at an hourly rate or annual rate.", false),
            ("Does Bob live in France?", "Live! (Bob Marley and the Wailers album)",
                "Live! is a 1975 album by Bob Marley and the Wailers which was recorded live in concert during July 1975 at the Lyceum Theatre, London.", false),
            ("capital de Australia", "Territorio de la Capital Australiana",
                "El Territorio de la Capital Australiana es un territorio federal de Australia que contiene la capital nacional, Camberra.", true),
            ("who wrote Dracula", "Dracula",
                "Dracula is an 1897 Gothic horror novel by Irish author Bram Stoker.", true),
            ("¿Cuál es la capital de Australia?", "Canberra",
                "Canberra es la capital de Australia.", true),
        ];
        Assert.Multiple(() =>
        {
            foreach ((string query, string title, string snippet, bool pertinent) in cases)
            {
                Assert.That(SearchPertinence.IsPertinent(query, title, snippet), Is.EqualTo(pertinent),
                    query + " → " + title);
            }
        });
    }

    // M51 F-s012: Wikipedia answered with articles that shared a word with the query;
    // none passes the gate, so Wikipedia did not answer and the engine is asked.
    [Test]
    public async Task WikipediaResultsThatDoNotAnswerAreNotAnAnswer()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["en.wikipedia.org"] = WikipediaAnswer("en",
                ("HTTP 301", "HTTP 301 is the HTTP status code used for permanent redirecting; links should be updated.", false)),
            ["es.wikipedia.org"] = WikipediaAnswer("es", ("Estado", "Un estado es una organización política.", false)),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"Are there any new status updates?"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("web_search_unavailable"));
            Assert.That(receipt.Result, Is.Null);
            Assert.That(handler.Asked.Select(asked => asked.Uri.Host),
                Is.EqualTo(new[] { "en.wikipedia.org", "es.wikipedia.org", "lite.duckduckgo.com" }));
            Assert.That(Uri.UnescapeDataString(handler.Asked[0].Uri.Query), Does.Contain("gsrsearch=status updates&"));
        });
    }

    // M53 (D35): the mind asks a named dish's recipe with its class word; Wikibooks'
    // Spanish recipe book answers with the recipe read from its wikitext, the receipt
    // says it is a recipe, and the encyclopedia is not asked.
    [Test]
    public async Task ARecipeIsReadFromTheRecipeBookAndSaysItIsOne()
    {
        var handler = new SearchSourcesHttpHandler();
        handler.Routes.Add(("es.wikibooks.org", new(HttpStatusCode.OK,
            WikimediaReferenceSourceTests.Fixture("wikibooks_es_sopaipillas.json"), "application/json")));
        handler.Routes.Add(("es.wikipedia.org", new(HttpStatusCode.OK,
            WikimediaReferenceSourceTests.Fixture("wikipedia_es_langlinks_pan_banana.json"), "application/json")));
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"receta sopaipillas"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("wikibooks_es_api"));
            Assert.That(receipt.Result?.GetProperty("reference").GetString(), Is.EqualTo("recipe"));
            Assert.That(receipt.Result?.GetProperty("count").GetInt32(), Is.EqualTo(1));
            JsonElement first = receipt.Result!.Value.GetProperty("results")[0];
            Assert.That(first.GetProperty("title").GetString(), Is.EqualTo("Sopaipilla"));
            Assert.That(first.GetProperty("url").GetString(), Does.StartWith("https://es.wikibooks.org/wiki/"));
            Assert.That(first.GetProperty("snippet").GetString(), Does.Contain("Ingredientes"));
            Assert.That(handler.Asked.Select(asked => asked.Uri.Host), Does.Not.Contain("lite.duckduckgo.com"));
            Assert.That(handler.Asked.All(asked => asked.UserAgent.StartsWith("BAXY/", StringComparison.Ordinal)));
            Assert.That(handler.Asked.Select(asked => Uri.UnescapeDataString(asked.Uri.Query)),
                Has.Some.Contain("gsrsearch=sopaipillas prefix:Artes culinarias/Recetas/&"));
        });
    }

    // Without the dish in either recipe book, the query goes on as any other: Wikipedia's
    // article about it answers, with no «reference».
    [Test]
    public async Task ARecipeNoBookHasFallsBackToTheEncyclopedia()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["es.wikipedia.org"] = WikipediaAnswer("es",
                ("Pastel de choclo", "El pastel de choclo es un plato de la gastronomía de Chile.", false)),
        };
        handler.Routes.Add(("wikibooks.org", new(HttpStatusCode.OK, """{"batchcomplete":true}""", "application/json")));
        handler.Routes.Add(("lllang=en", new(HttpStatusCode.OK, """{"batchcomplete":true}""", "application/json")));
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"receta pastel de choclo"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("wikipedia_es_api"));
            Assert.That(receipt.Result?.TryGetProperty("reference", out _), Is.False);
        });
    }

    // The plot of a named work is its article's plot section, one request.
    [Test]
    public async Task AWorksPlotIsReadFromItsArticle()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["es.wikipedia.org"] = new(HttpStatusCode.OK,
                WikimediaReferenceSourceTests.Fixture("wikipedia_es_plot_hobbit.json"), "application/json"),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"resumen libro Hobbit"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("reference").GetString(), Is.EqualTo("plot"));
            Assert.That(receipt.Result?.GetProperty("results")[0].GetProperty("snippet").GetString(), Does.Contain("Smaug"));
            Assert.That(handler.Asked, Has.Count.EqualTo(1));
            Assert.That(Uri.UnescapeDataString(handler.Asked[0].Uri.Query), Does.Contain("exsectionformat=wiki"));
        });
    }

    // M51 F-p09-t2: Wikipedia wants every word it is given and the answer says «film»;
    // after nothing pertinent, the proper names alone are asked once in the query's
    // language, and the article is judged by the whole query («movie» = «film»).
    [Test]
    public async Task AfterNothingPertinentWikipediaIsAskedForTheProperNamesAlone()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["en.wikipedia.org"] = new(HttpStatusCode.OK, """{"batchcomplete":true}""", "application/json"),
            ["es.wikipedia.org"] = new(HttpStatusCode.OK, """{"batchcomplete":true}""", "application/json"),
        };
        handler.Routes.Add(("gsrsearch=kirill mikhanovsky&", WikipediaAnswer("en",
            ("Give Me Liberty (film)",
                "Give Me Liberty is a 2019 American comedy-drama film directed by Kirill Mikhanovsky, starring Chris Galust and Lauren Spencer.",
                false))));
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"Who played in the movie directed by Kirill Mikhanovsky?"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("wikipedia_en_api"));
            Assert.That(receipt.Result?.GetProperty("results")[0].GetProperty("title").GetString(),
                Is.EqualTo("Give Me Liberty (film)"));
            Assert.That(handler.Asked.Select(asked => Uri.UnescapeDataString(asked.Uri.Query).Split("gsrsearch=")[1].Split('&')[0]),
                Is.EqualTo(new[] { "movie kirill mikhanovsky", "movie kirill mikhanovsky", "kirill mikhanovsky" }));
        });
    }

    // M51 F-w12-t4/F-w13-t1: a price of today was «could not look it up». The search
    // feed of the news answers it, in the query's language, with the headlines about it
    // and only those.
    [Test]
    public async Task ADayBoundQuestionIsAnsweredByTheNewsFeedWithItsPertinentHeadlines()
    {
        const string feed = """
            <?xml version="1.0" encoding="UTF-8"?>
            <rss version="2.0"><channel><title>Noticias</title>
            <item><title>Dólar blue hoy: a cuánto cotiza este lunes - Diario Uno</title><link>https://news.google.com/rss/articles/abc?oc=5</link><pubDate>Mon, 28 Sep 2026 12:00:00 GMT</pubDate><source url="https://www.example.com.ar">Diario Uno</source></item>
            <item><title>El fútbol argentino vuelve este fin de semana - Diario Dos</title><link>https://news.google.com/rss/articles/def?oc=5</link><pubDate>Mon, 28 Sep 2026 11:00:00 GMT</pubDate><source url="https://www.example.com">Diario Dos</source></item>
            </channel></rss>
            """;
        var handler = new SearchSourcesHttpHandler
        {
            ["news.google.com"] = new(HttpStatusCode.OK, feed, "application/rss+xml"),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"¿Cuánto está el dólar blue hoy?"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("google_news_rss_search"));
            Assert.That(receipt.Result?.GetProperty("count").GetInt32(), Is.EqualTo(1));
            JsonElement first = receipt.Result!.Value.GetProperty("results")[0];
            Assert.That(first.GetProperty("title").GetString(), Is.EqualTo("Dólar blue hoy: a cuánto cotiza este lunes"));
            Assert.That(first.GetProperty("url").GetString(), Is.EqualTo("https://news.google.com/rss/articles/abc"));
            Assert.That(first.GetProperty("snippet").GetString(), Is.EqualTo("Diario Uno, Mon, 28 Sep 2026 12:00:00 GMT"));
            Assert.That(handler.Asked.Select(asked => asked.Uri.Host), Is.EqualTo(new[] { "news.google.com" }));
            Assert.That(Uri.UnescapeDataString(handler.Asked[0].Uri.Query),
                Is.EqualTo("?q=dolar blue&hl=es-419&gl=CL&ceid=CL:es-419"));
            Assert.That(handler.Asked[0].UserAgent,
                Does.Match(@"^BAXY/\d+\.\d+ \(https://github\.com/REDSOULTM/baxy-assistant\)$"));
        });
    }

    // M51 F-s090 «what is the rate for 500 cad in usd»: two currencies are a conversion,
    // answered by Frankfurter's reference rate with the amount already multiplied.
    [Test]
    public async Task ACurrencyConversionIsAnsweredByFrankfurterWithTheAmountConverted()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["api.frankfurter.dev"] = new(HttpStatusCode.OK,
                """[{"date":"2026-09-28","base":"CAD","quote":"USD","rate":0.70774}]""", "application/json"),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"what is the rate for 500 cad in usd"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("frankfurter_reference_rates"));
            JsonElement first = receipt.Result!.Value.GetProperty("results")[0];
            Assert.That(first.GetProperty("title").GetString(), Is.EqualTo("500 CAD = 353.87 USD"));
            Assert.That(first.GetProperty("snippet").GetString(),
                Is.EqualTo("Reference rate on 2026-09-28: 1 CAD = 0.70774 USD."));
            Assert.That(handler.Asked.Single().Uri.AbsoluteUri,
                Is.EqualTo("https://api.frankfurter.dev/v2/rates?base=CAD&quotes=USD"));
        });
    }

    [Test]
    public void ACurrencyAskNeedsTwoCurrenciesAndNoInformalRate()
    {
        var chile = new RegionInfo("CL");
        Assert.Multiple(() =>
        {
            Assert.That(FrankfurterRateSource.Parse("what is the rate for 500 cad in usd", chile),
                Is.EqualTo(new FrankfurterRateSource.CurrencyAsk(500m, "CAD", "USD")));
            Assert.That(FrankfurterRateSource.Parse("cuántos pesos son 1.000 dólares", chile),
                Is.EqualTo(new FrankfurterRateSource.CurrencyAsk(1000m, "USD", "CLP")));
            Assert.That(FrankfurterRateSource.Parse("20 euros a pesos mexicanos", chile),
                Is.EqualTo(new FrankfurterRateSource.CurrencyAsk(20m, "EUR", "MXN")));
            Assert.That(FrankfurterRateSource.Parse("¿Cuánto está el dólar blue hoy?", chile), Is.Null);
            Assert.That(FrankfurterRateSource.Parse("precio del dólar hoy", chile), Is.Null);
            Assert.That(FrankfurterRateSource.Parse("dólares a pesos", new RegionInfo("ES")), Is.Null);
        });
    }

    [Test]
    public void APlaceAskIsAKindOfSiteInANamedPlace()
    {
        Assert.Multiple(() =>
        {
            Assert.That(OpenStreetMapPlaceSource.Parse("Encuentrame aparcamiento cerca de La Puntilla", null),
                Is.EqualTo(new OpenStreetMapPlaceSource.PlaceAsk("parking", "La Puntilla")));
            Assert.That(OpenStreetMapPlaceSource.Parse("Show me gas stations in Buford.", null),
                Is.EqualTo(new OpenStreetMapPlaceSource.PlaceAsk("fuel", "Buford")));
            // M56 (v3c-final F-p06-t2): the sentence's lower-case article is not the place's name;
            // Nominatim answered nothing for «la Plaza de las Salesas, Madrid».
            Assert.That(OpenStreetMapPlaceSource.Parse("Busca aparcamiento en la calle Génova en Madrid.", null),
                Is.EqualTo(new OpenStreetMapPlaceSource.PlaceAsk("parking", "calle Génova, Madrid")));
            Assert.That(OpenStreetMapPlaceSource.Parse("aparcamiento en la Plaza de las Salesas en Madrid", null),
                Is.EqualTo(new OpenStreetMapPlaceSource.PlaceAsk("parking", "Plaza de las Salesas, Madrid")));
            Assert.That(OpenStreetMapPlaceSource.Parse("aparcamiento en Plaza del Polvorista", null),
                Is.EqualTo(new OpenStreetMapPlaceSource.PlaceAsk("parking", "Plaza del Polvorista")));
            Assert.That(OpenStreetMapPlaceSource.Parse("Busca taquerías cerca que tengan servicio a domicilio.", "Curico"),
                Is.EqualTo(new OpenStreetMapPlaceSource.PlaceAsk("taqueria", "Curico")));
            Assert.That(OpenStreetMapPlaceSource.Parse("un aparcamiento en el centro de la ciudad", null), Is.Null);
            Assert.That(OpenStreetMapPlaceSource.Parse("farmacias cerca de mí", null), Is.Null);
            Assert.That(OpenStreetMapPlaceSource.Parse("capital de Australia", null), Is.Null);
        });
    }

    // M51 F-p05-t1 «Encuentra aparcamiento en Plaza del Polvorista» was answered from a
    // party's proposal. OpenStreetMap answers: the named place's box first, then the
    // kind of site inside it, both with the project's User-Agent.
    [Test]
    public async Task AParkingQueryIsAnsweredByOpenStreetMapInsideTheNamedPlace()
    {
        var handler = new SearchSourcesHttpHandler();
        handler.Routes.Add(("q=Plaza del Polvorista", new(HttpStatusCode.OK,
            """[{"lat":"36.5985","lon":"-6.2330","boundingbox":["36.5982","36.5988","-6.2334","-6.2326"],"display_name":"Plaza del Polvorista, El Puerto de Santa María, Cádiz, España"}]""",
            "application/json")));
        handler.Routes.Add(("q=parking", new(HttpStatusCode.OK,
            """[{"osm_type":"way","osm_id":123,"name":"Aparcamiento Polvorista","type":"parking","display_name":"Aparcamiento Polvorista, Calle Larga, El Puerto de Santa María, Cádiz, España"},{"osm_type":"node","osm_id":456,"name":"","type":"parking","display_name":"Calle Ganado, El Puerto de Santa María, Cádiz, España"}]""",
            "application/json")));
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"aparcamiento en Plaza del Polvorista"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("openstreetmap_nominatim"));
            JsonElement results = receipt.Result!.Value.GetProperty("results");
            Assert.That(results.GetArrayLength(), Is.EqualTo(2));
            Assert.That(results[0].GetProperty("title").GetString(), Is.EqualTo("Aparcamiento Polvorista"));
            Assert.That(results[0].GetProperty("url").GetString(), Is.EqualTo("https://www.openstreetmap.org/way/123"));
            Assert.That(results[1].GetProperty("title").GetString(), Is.EqualTo("parking"));
            Assert.That(handler.Asked, Has.Count.EqualTo(2));
            Assert.That(handler.Asked, Has.All.Matches<AskedRequest>(asked => asked.Uri.Host == "nominatim.openstreetmap.org"
                && asked.UserAgent.Contains("github.com/REDSOULTM/baxy-assistant", StringComparison.Ordinal)));
            Assert.That(Uri.UnescapeDataString(handler.Asked[1].Uri.Query),
                Does.Contain("bounded=1").And.Contain("viewbox=-6.243,36.6085,-6.223,36.5885"));
        });
    }

    // Real answer of 2026-09-28: «La Puntilla, El Puerto» geocodes to a bar in Ceuta
    // named «El Puerto». A place whose address lacks «Puntilla» is not the place; the
    // first part is asked alone and the candidate in El Puerto de Santa María wins.
    [Test]
    public async Task APlaceIsTheCandidateWhoseAddressCarriesItsName()
    {
        var handler = new SearchSourcesHttpHandler();
        handler.Routes.Add(("q=La Puntilla, El Puerto", new(HttpStatusCode.OK,
            """[{"boundingbox":["35.89135","35.89145","-5.31856","-5.31846"],"display_name":"Bar El Puerto, Avenida Juan de Borbón, Ceuta, España"}]""",
            "application/json")));
        handler.Routes.Add(("q=La Puntilla", new(HttpStatusCode.OK,
            """[{"boundingbox":["-32.99","-32.98","-68.87","-68.86"],"display_name":"La Puntilla, Luján de Cuyo, Mendoza, Argentina"},{"boundingbox":["36.585","36.587","-6.245","-6.243"],"display_name":"La Puntilla, Valdelagrana, El Puerto de Santa María, Cádiz, España"}]""",
            "application/json")));
        handler.Routes.Add(("q=parking", new(HttpStatusCode.OK,
            """[{"osm_type":"way","osm_id":7,"name":"Parking La Puntilla","type":"parking","display_name":"Parking La Puntilla, El Puerto de Santa María, Cádiz, España"}]""",
            "application/json")));
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"Encuentrame aparcamiento cerca de La Puntilla, El Puerto."}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("results")[0].GetProperty("title").GetString(), Is.EqualTo("Parking La Puntilla"));
            Assert.That(handler.Asked, Has.Count.EqualTo(3));
            Assert.That(Uri.UnescapeDataString(handler.Asked[2].Uri.Query), Does.Contain("viewbox=-6.254,36.596,-6.234,36.576"));
        });
    }

    // M56 (v3c-final F-p06-t2, Nominatim's real answers of 2026-09-28): «Plaza de las Salesas,
    // Madrid» asked with the sentence's «la» found nothing, and the first part alone found only
    // the Plaza de las Salesas of Cartagena, whose car parks were told as Madrid's. A candidate
    // outside the city the person named is not the place: the source does not answer.
    [Test]
    public async Task APlaceOutsideTheNamedCityIsNotThePlace()
    {
        var handler = new SearchSourcesHttpHandler();
        handler.Routes.Add(("q=Plaza de las Salesas, Madrid", new(HttpStatusCode.OK, "[]", "application/json")));
        handler.Routes.Add(("q=Plaza de las Salesas", new(HttpStatusCode.OK,
            """[{"boundingbox":["37.6125952","37.6129237","-0.9894311","-0.9889022"],"display_name":"Plaza de las Salesas, Cartagena Casco, Cartagena, Campo de Cartagena y Mar Menor, Región de Murcia, España","address":{"country_code":"es"}},{"boundingbox":["37.6125121","37.6129570","-0.9894855","-0.9888487"],"display_name":"Plaza de las Salesas, Ciudad Jardín, Cartagena Casco, Cartagena, Campo de Cartagena y Mar Menor, Región de Murcia, 30204, España","address":{"country_code":"es"}}]""",
            "application/json")));
        using var http = new HttpClient(handler);
        var source = new OpenStreetMapPlaceSource(http);
        OpenStreetMapPlaceSource.PlaceAsk ask =
            OpenStreetMapPlaceSource.Parse("aparcamiento en la Plaza de las Salesas en Madrid", null)!.Value;

        List<(string Title, string Url, string Snippet)>? places =
            await source.SearchAsync(ask, 5, "es", CancellationToken.None, "CL");

        Assert.Multiple(() =>
        {
            Assert.That(places, Is.Empty);
            Assert.That(handler.Asked, Has.Count.EqualTo(2), "no car park is asked around another city's square");
            Assert.That(handler.Asked.Select(asked => Uri.UnescapeDataString(asked.Uri.Query)),
                Has.None.Contains("q=la "));
        });
    }

    [Test]
    public void TheNamedCityBindsTheCandidate()
    {
        const string both = """
            [{"boundingbox":["37.6125","37.6129","-0.9894","-0.9889"],"display_name":"Plaza de las Salesas, Cartagena Casco, Cartagena, Región de Murcia, España"},
             {"boundingbox":["40.4239","40.4244","-3.6947","-3.6943"],"display_name":"Plaza de las Salesas, Justicia, Centro, Madrid, Comunidad de Madrid, España"}]
            """;
        string[] square = ["plaza", "salesas"];
        string[] madrid = ["madrid"];

        Assert.Multiple(() =>
        {
            Assert.That(OpenStreetMapPlaceSource.AreaOf(both, square, square, within: [madrid])?.Latitude,
                Is.EqualTo(40.42415).Within(0.001), "the square of the named city, not Nominatim's first");
            Assert.That(OpenStreetMapPlaceSource.AreaOf(both, square, square, within: [["sevilla"]]), Is.Null);
            Assert.That(OpenStreetMapPlaceSource.AreaOf(both, square, square)?.Latitude, Is.EqualTo(37.6127).Within(0.001),
                "with no city named, Nominatim's order stands");
        });
    }

    // M58 (v3d-final F-p06-t3 «aparcamiento en la calle Génova en Madrid», Nominatim's real answer of
    // 2026-09-28 for «calle Génova, Madrid»): the Calle Génova of Villa del Prado came first and carries
    // «Madrid» only in «Comunidad de Madrid»; its car parks were told. The candidate whose own town is
    // the named one wins; «Las Rozas de Madrid» is another town.
    [Test]
    public void TheNamedCityIsTheCandidatesOwnTownNotItsRegion()
    {
        const string genova = """
            [{"display_name":"Calle Génova, Villa del Prado, Comunidad de Madrid, 28630, España","boundingbox":["40.2763773","40.2772820","-4.3081919","-4.3068498"],"address":{"road":"Calle Génova","village":"Villa del Prado","state":"Comunidad de Madrid","postcode":"28630","country":"España","country_code":"es"}},
             {"display_name":"Calle Génova, Parque Industrial Tecnológico Európolis, La Puentecilla y Los Majuelos, Las Rozas de Madrid, Comunidad de Madrid, 28230, España","boundingbox":["40.4991016","40.4991277","-3.8902731","-3.8895388"],"address":{"road":"Calle Génova","town":"Las Rozas de Madrid","state":"Comunidad de Madrid","postcode":"28230","country":"España","country_code":"es"}},
             {"display_name":"Calle Genova, Quijorna, Comunidad de Madrid, 28693, España","boundingbox":["40.4316964","40.4336917","-4.0625033","-4.0615325"],"address":{"road":"Calle Genova","village":"Quijorna","state":"Comunidad de Madrid","postcode":"28693","country":"España","country_code":"es"}},
             {"display_name":"Calle de Génova, Chueca, Almagro, Chamberí, Centro, Madrid, Comunidad de Madrid, 28004, España","boundingbox":["40.4251315","40.4271468","-3.6947895","-3.6909553"],"address":{"road":"Calle de Génova","city":"Madrid","state":"Comunidad de Madrid","postcode":"28004","country":"España","country_code":"es"}},
             {"display_name":"Calle de Génova, Almagro, Chamberí, Madrid, Comunidad de Madrid, 28004, España","boundingbox":["40.4254918","40.4267445","-3.6938416","-3.6907592"],"address":{"road":"Calle de Génova","city":"Madrid","state":"Comunidad de Madrid","postcode":"28004","country":"España","country_code":"es"}}]
            """;
        string[] street = ["calle", "genova"];
        string[] wanted = ["calle", "genova", "madrid"];

        Assert.Multiple(() =>
        {
            Assert.That(OpenStreetMapPlaceSource.AreaOf(genova, street, wanted, "ES", within: [["madrid"]])?.Latitude,
                Is.EqualTo(40.42614).Within(0.001), "the Calle de Génova of Madrid, not Villa del Prado's");
            Assert.That(OpenStreetMapPlaceSource.AreaOf(genova, street, wanted, "ES")?.Latitude,
                Is.EqualTo(40.27683).Within(0.001), "with no city named, Nominatim's order stands");
        });
    }

    // M54 (v3b-final F-p01-t2): this PC's city «Curico» (Chile) geocoded to Curico,
    // Indiana, the first candidate, and its car parks were the answer. Among candidates of
    // the same name the one in the preferred country wins; this PC's own city must be in
    // this PC's country; more words of the place still win over the country.
    [Test]
    public void ThePlaceOfThisPcsCityIsInThisPcsCountry()
    {
        const string curico = """
            [{"boundingbox":["41.4","41.5","-87.1","-87.0"],"display_name":"Curico, Porter County, Indiana, United States","address":{"country_code":"us"}},
             {"boundingbox":["-35.03","-34.93","-71.30","-71.18"],"display_name":"Curicó, Provincia de Curicó, Región de Curicó, Chile","address":{"country_code":"cl"}}]
            """;
        const string indianaOnly = """
            [{"boundingbox":["41.4","41.5","-87.1","-87.0"],"display_name":"Curico, Porter County, Indiana, United States","address":{"country_code":"us"}}]
            """;
        const string named = """
            [{"boundingbox":["41.4","41.5","-87.1","-87.0"],"display_name":"Curico, Porter County, Indiana, United States","address":{"country_code":"us"}},
             {"boundingbox":["-35.03","-34.93","-71.30","-71.18"],"display_name":"Curicó, Chile","address":{"country_code":"cl"}}]
            """;
        string[] words = ["curico"];

        Assert.Multiple(() =>
        {
            Assert.That(OpenStreetMapPlaceSource.AreaOf(curico, words, words)?.Latitude, Is.EqualTo(41.45).Within(0.001),
                "without a country, Nominatim's order stands");
            Assert.That(OpenStreetMapPlaceSource.AreaOf(curico, words, words, "CL")?.Latitude, Is.EqualTo(-34.98).Within(0.001));
            Assert.That(OpenStreetMapPlaceSource.AreaOf(curico, words, words, "CL", requireCountry: true)?.Latitude,
                Is.EqualTo(-34.98).Within(0.001));
            Assert.That(OpenStreetMapPlaceSource.AreaOf(indianaOnly, words, words, "CL", requireCountry: true), Is.Null);
            Assert.That(OpenStreetMapPlaceSource.AreaOf(indianaOnly, words, words, "CL")?.Latitude, Is.EqualTo(41.45).Within(0.001),
                "a named place of another country is still that place");
            Assert.That(OpenStreetMapPlaceSource.AreaOf(named, words, ["curico", "indiana"], "CL")?.Latitude,
                Is.EqualTo(41.45).Within(0.001), "the place's own words outrank the preferred country");
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

    private sealed record HttpAnswer(HttpStatusCode Status, string Body, string ContentType);

    private sealed record AskedRequest(Uri Uri, string UserAgent);

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
            Asked.Add(new AskedRequest(uri, request.Headers.UserAgent.ToString()));
            string address = Uri.UnescapeDataString(uri.AbsoluteUri);
            HttpAnswer? answer = Routes.FirstOrDefault(route => address.Contains(route.Contains, StringComparison.Ordinal)).Answer;
            if (answer is null && !_answers.TryGetValue(uri.Host, out answer))
            {
                throw new HttpRequestException("unreachable host " + uri.Host);
            }
            return Task.FromResult(new HttpResponseMessage(answer.Status)
            {
                Content = new StringContent(answer.Body, Encoding.UTF8, answer.ContentType),
            });
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
            "\"sentUtc\":\"2026-09-21T02:10:00Z\",\"sentTo\":\"autor@example.com\",\"subject\":\"llego tarde\"}";
        using TemporaryDirectory temporary = new();
        var runner = new StubProcessRunner(output);
        var adapter = new MicrosoftAccountAdapter(temporary.Path, runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "email.send",
            Json("""{"to":"autor@example.com","text":"llego tarde"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt invalid = await adapter.InvokeAsync(
            "email.send",
            Json("""{"to":"juan","text":"hola"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("to").GetString(), Is.EqualTo("autor@example.com"));
            Assert.That(receipt.Result?.GetProperty("subject").GetString(), Is.EqualTo("llego tarde"));
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
    public async Task GraphCalendarListUsesBearerAndProjectsOpaqueIdentity()
    {
        const string body = """
            {"value":[{"id":"remote-id","subject":"Reunión","start":{"dateTime":"2026-07-17T10:00:00","timeZone":"UTC"},"end":{"dateTime":"2026-07-17T11:00:00","timeZone":"UTC"}}]}
            """;
        using var http = new HttpClient(new StubHttpHandler(body));
        using var adapter = new MicrosoftGraphCalendarAdapter(http, () => "token");
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "calendar.event.list",
            Json("""{"startUtc":"2026-07-17T00:00:00Z","endUtc":"2026-07-18T00:00:00Z"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("events")[0].GetProperty("eventId").GetString(),
                Does.StartWith("event_"));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("remote-id"));
        });
    }

    [Test]
    public async Task GraphCreateWithUnreadableAcceptedResponsePreservesAmbiguousEffect()
    {
        var handler = new RecordingInvalidJsonHttpHandler();
        using var http = new HttpClient(handler);
        using var adapter = new MicrosoftGraphCalendarAdapter(http, () => "token");

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "calendar.event.create",
            Json(
                """{"title":"Reunión","startUtc":"2026-07-29T10:00:00Z","endUtc":"2026-07-29T11:00:00Z"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(handler.PostCalls, Is.EqualTo(1));
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo("microsoft_graph_calendar_failed"));
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
    public async Task SpotifyApiSearchDispatchAndPostreadBindTheExactTrack()
    {
        var handler = new SpotifyHttpHandler();
        var delays = new RecordingDelay();
        using var http = new HttpClient(handler);
        using var adapter = new WindowsMediaSessionAdapter(
            http,
            () => "token",
            delay: delays.DelayAsync);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.exact",
            Json("""{"provider":"spotify","title":"Billie Jean"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("trackId").GetString(), Is.EqualTo("track-1"));
            Assert.That(handler.PlayCalls, Is.EqualTo(1));
            Assert.That(handler.CurrentlyPlayingCalls, Is.EqualTo(1));
            Assert.That(delays.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task SpotifyApiQuerySelectsAResultAndBindsNowPlaying()
    {
        var handler = new SpotifyHttpHandler();
        var delays = new RecordingDelay();
        using var http = new HttpClient(handler);
        using var adapter = new WindowsMediaSessionAdapter(
            http,
            () => "token",
            delay: delays.DelayAsync);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.query",
            Json("""{"provider":"spotify","query":"Michael Jackson"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("query").GetString(),
                Is.EqualTo("Michael Jackson"));
            Assert.That(receipt.Result?.GetProperty("title").GetString(),
                Is.EqualTo("Billie Jean"));
            Assert.That(handler.PlayCalls, Is.EqualTo(1));
            Assert.That(handler.CurrentlyPlayingCalls, Is.EqualTo(1));
            Assert.That(delays.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task SpotifyApiPostreadFailureRetainsTenSecondRetryHorizon()
    {
        var handler = new SpotifyHttpHandler
        {
            NowPlayingMatches = false,
        };
        var delays = new RecordingDelay();
        using var http = new HttpClient(handler);
        using var adapter = new WindowsMediaSessionAdapter(
            http,
            () => "token",
            delay: delays.DelayAsync);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.exact",
            Json("""{"provider":"spotify","title":"Billie Jean"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo("spotify_now_playing_not_verified"));
            Assert.That(handler.PlayCalls, Is.EqualTo(1));
            Assert.That(handler.CurrentlyPlayingCalls, Is.EqualTo(21));
            AssertRetryHorizon(delays, expectedIntervals: 20, intervalMilliseconds: 500);
        });
    }

    [Test]
    public async Task SpotifyApiImmediateProbeFailureFallsBackToOriginalSchedule()
    {
        var handler = new SpotifyHttpHandler
        {
            FirstCurrentlyPlayingThrows = true,
        };
        var delays = new RecordingDelay();
        using var http = new HttpClient(handler);
        using var adapter = new WindowsMediaSessionAdapter(
            http,
            () => "token",
            delay: delays.DelayAsync);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.exact",
            Json("""{"provider":"spotify","title":"Billie Jean"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(handler.CurrentlyPlayingCalls, Is.EqualTo(2));
            AssertRetryHorizon(delays, expectedIntervals: 1, intervalMilliseconds: 500);
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

    // 2026-09-22 (owner's turn 148): with no Spotify process the automation died
    // after crossing the boundary and the failure travelled as an ambiguous effect.
    // Tanda 6 «pasar al siguiente episodio» with nothing playing was told Spotify was
    // not open: the last player of the chain found nothing playing, and Spotify's
    // absence is the cause only when the person named Spotify.
    [TestCase("""{"action":"stop"}""", "media_session_not_found")]
    [TestCase("""{"action":"next","sourceApp":null}""", "media_session_not_found")]
    [TestCase("""{"action":"next","sourceApp":"spotify"}""", "spotify_client_not_running")]
    public async Task SpotifyDesktopControlStandsAsideWithoutAClientProcess(string arguments, string error)
    {
        var runner = new StubProcessRunner("{\"ok\":true}");
        var adapter = new SpotifyDesktopAdapter(runner, processExists: static _ => false);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.control", Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(error));
            Assert.That(runner.LastArguments, Is.Empty);
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

    [Test]
    public async Task SpotifyDesktopControlRequiresUiaPostreadBeforeSuccess()
    {
        var adapter = new SpotifyDesktopAdapter(new StubProcessRunner(
            "{\"ok\":true,\"effectObserved\":true,\"action\":\"pause\"," +
            "\"playbackStatus\":\"paused\",\"processId\":42}"));
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.control",
            Json("""{"action":"pause"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("playbackStatus").GetString(),
                Is.EqualTo("paused"));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("spotify_windows_uia_postread"));
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
            bool locator = uri.Host.Contains("ipwho", StringComparison.Ordinal)
                || uri.Host.Contains("ip-api", StringComparison.Ordinal);
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(locator ? located : page, Encoding.UTF8,
                    locator ? "application/json" : "text/html"),
            });
        }
    }

    private sealed class RecordingInvalidJsonHttpHandler : HttpMessageHandler
    {
        internal int PostCalls { get; private set; }

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (request.Method == HttpMethod.Post)
            {
                PostCalls++;
            }

            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.Created)
            {
                Content = new StringContent("{invalid", Encoding.UTF8, "application/json"),
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

    private sealed class NotificationSchedulerRunner : IExternalProcessRunner
    {
        internal string TaskName { get; private set; } = string.Empty;
        internal IReadOnlyList<string> Arguments { get; private set; } = [];

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            Arguments = arguments.ToArray();
            int taskIndex = arguments.ToList().IndexOf("-TaskName");
            TaskName = taskIndex >= 0 ? arguments[taskIndex + 1] : string.Empty;
            string output = JsonSerializer.Serialize(new
            {
                version = 1,
                ok = true,
                effectObserved = true,
                taskName = TaskName,
                state = "Ready",
                nextRunUtc = DateTimeOffset.UtcNow.AddHours(1).ToString("O"),
                authority = "windows_task_scheduler_postread",
            });
            return ValueTask.FromResult(new ExternalProcessResult(0, output, string.Empty));
        }
    }

    private sealed class CountingLocator : IVisibleControlLocator
    {
        private readonly bool _hit;

        internal CountingLocator(string stage, bool hit)
        {
            Stage = stage;
            _hit = hit;
        }

        internal int Calls { get; private set; }

        public string Stage { get; }

        public ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
            string operation,
            string label,
            CancellationToken cancellationToken)
        {
            Calls++;
            if (!_hit)
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
        internal IReadOnlyList<string> Arguments { get; private set; } = [];

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

        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            string output = outputs[Math.Min(Calls, outputs.Count - 1)];
            Calls++;
            return ValueTask.FromResult(new ExternalProcessResult(0, output, ""));
        }
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
        bool terminateResult) : IWindowsProcessTerminationPlatform
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

        public bool Terminate(string processName, WindowsProcessIdentity identity)
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

    private sealed class SpotifyHttpHandler : HttpMessageHandler
    {
        internal int PlayCalls { get; private set; }

        internal int CurrentlyPlayingCalls { get; private set; }

        internal bool NowPlayingMatches { get; init; } = true;

        internal bool FirstCurrentlyPlayingThrows { get; init; }

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken)
        {
            string path = request.RequestUri!.AbsolutePath;
            if (request.Method == HttpMethod.Put)
            {
                PlayCalls++;
                return Response("{}");
            }
            if (path.EndsWith("/search", StringComparison.Ordinal))
            {
                return Response("""{"tracks":{"items":[{"id":"track-1","uri":"spotify:track:track-1","name":"Billie Jean","popularity":99,"artists":[{"name":"Michael Jackson"}]}]}}""");
            }
            if (path.EndsWith("/devices", StringComparison.Ordinal))
            {
                return Response("""{"devices":[{"id":"device-1","is_active":true,"is_restricted":false}]}""");
            }
            CurrentlyPlayingCalls++;
            if (FirstCurrentlyPlayingThrows && CurrentlyPlayingCalls == 1)
            {
                throw new HttpRequestException("Transient simulated postread failure.");
            }
            return Response(NowPlayingMatches
                ? """{"is_playing":true,"item":{"id":"track-1"}}"""
                : """{"is_playing":false,"item":{"id":"other-track"}}""");
        }

        private static Task<HttpResponseMessage> Response(string body) => Task.FromResult(
            new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(body, Encoding.UTF8, "application/json"),
            });
    }

    private sealed class VisionHttpHandler : HttpMessageHandler
    {
        protected override async Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken)
        {
            string body = await request.Content!.ReadAsStringAsync(cancellationToken);
            Assert.Multiple(() =>
            {
                Assert.That(request.RequestUri?.Scheme, Is.EqualTo("https"));
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
