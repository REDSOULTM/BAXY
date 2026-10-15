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
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(DateTimeOffset.Parse(due, CultureInfo.InvariantCulture))}}","kind":"alarm","title":"Prueba"}"""),
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
            "schedule.alarms",
            Json($$"""{"action":"create","at":"{{LocalAt(DateTimeOffset.Parse(due, CultureInfo.InvariantCulture))}}","kind":"reminder","recurrence":"hourly","title":"Drink water"}"""),
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
            "schedule.alarms",
            Json("""{"action":"cancel","kind":"alarm","at":"17:00"}"""),
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
            "schedule.alarms",
            Json("""{"action":"cancel","kind":"alarm","at":"17:00"}"""),
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

    [TestCase("schedule.alarms", """{"action":"cancel","kind":"reminder"}""")]
    [TestCase("schedule.alarms", """{"action":"cancel","kind":"alarm","at":"06:45"}""")]
    public async Task NotificationCancellationIsScopedToTheNotificationsThisDataRootSet(
        string operation, string arguments)
    {
        // M80 (DEV-D v3m D-w16-t2, D-w18-t5): the scheduler is shared by every BAXY data root of the user; six runs
        // left six alarms at 06:45 and «cancel the latest» picked another run's reminder.
        using TemporaryDirectory temporary = new();
        string scheduler = Path.Combine(temporary.Path, "WindowsScheduledNotification.ps1");
        await File.WriteAllTextAsync(scheduler, "# fixture");
        var runner = new CapturingProcessRunner("{\"ok\":false,\"matchCount\":0}");
        var adapter = new WindowsScheduledNotificationAdapter(temporary.Path, runner, scheduler);

        await adapter.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        int root = Array.IndexOf(runner.Arguments, "-AlarmRoot");
        Assert.That(root, Is.GreaterThan(0));
        Assert.That(runner.Arguments[root + 1], Is.EqualTo(Path.Combine(temporary.Path, "scheduled-notifications")));
    }

    [Test]
    public async Task NotificationListShowsOnlyTheNotificationsThisDataRootSet()
    {
        using TemporaryDirectory temporary = new();
        string scheduler = Path.Combine(temporary.Path, "WindowsScheduledNotification.ps1");
        await File.WriteAllTextAsync(scheduler, "# fixture");
        const string own = "BAXY-Alarm-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        const string other = "BAXY-Alarm-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
        string alarms = Path.Combine(temporary.Path, "scheduled-notifications");
        Directory.CreateDirectory(alarms);
        await File.WriteAllTextAsync(Path.Combine(alarms, own + ".ps1"), "# ring");
        string next = DateTimeOffset.UtcNow.AddHours(3).ToString("O");
        string output = $$"""{"ok":true,"tasks":[{"taskName":"{{own}}","state":"Ready","nextRunUtc":"{{next}}"},{"taskName":"{{other}}","state":"Ready","nextRunUtc":"{{next}}"}]}""";
        var adapter = new WindowsScheduledNotificationAdapter(
            temporary.Path, new StubProcessRunner(output), scheduler);

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
            Assert.That(typed.Verified, Is.True);
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
            // M81 (DEV-D v3m D-p12-t2 → Curico, Indiana): the city goes with this PC's country.
            Assert.That(receipt.Result?.GetProperty("query").GetString(), Is.EqualTo("comida para llevar cerca Curico Chile"));
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

    // Uso real 2026-10-07 («un top 3 peliculas de suspenso del 2026» → el artículo de UNA película): un listado
    // pedido (listing) no es una pregunta de enciclopedia; la misma consulta sin listing sí lo es (prueba de arriba).
    [Test]
    public async Task AListingAskedIsNeverAnsweredByAnEncyclopediaArticle()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["es.wikipedia.org"] = WikipediaAnswer("es",
                ("The Eyes (película de 2026)", "The Eyes es una película surcoreana de suspenso de 2026.", false)),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt listing = await adapter.InvokeAsync(
            "web.search",
            Json("""{"query":"un top 3 de películas de suspenso del 2026","limit":3,"listing":true}"""),
            CancellationToken.None);
        int askedForTheListing = handler.Asked.Count;
        ExternalCapabilityReceipt single = await adapter.InvokeAsync(
            "web.search",
            Json("""{"query":"un top 3 de películas de suspenso del 2026","limit":3}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(handler.Asked.Take(askedForTheListing).Select(asked => asked.Uri.Host),
                Has.None.Contains("wikipedia"));
            Assert.That(listing.Result?.GetRawText() ?? "", Does.Not.Contain("The Eyes"));
            Assert.That(handler.Asked.Skip(askedForTheListing).Select(asked => asked.Uri.Host),
                Has.Some.Contains("wikipedia"));
            Assert.That(single.Result?.GetProperty("authority").GetString(), Is.EqualTo("wikipedia_es_api"));
        });
    }

    // Revisión 2026-10-07: tres titulares pertinentes no son «el top 3»; un titular no es un elemento del listado.
    // Con listing no se pregunta a noticias: responde el buscador general (sin listing, las noticias siguen
    // respondiendo lo del día: ADayBoundQuestionIsAnsweredByTheNewsFeedWithItsPertinentHeadlines).
    [Test]
    public async Task AListingAskedIsNeverAnsweredByNewsHeadlines()
    {
        const string feed = """
            <?xml version="1.0" encoding="UTF-8"?>
            <rss version="2.0"><channel><title>Noticias</title>
            <item><title>Películas de suspenso 2026: los estrenos del año - Diario Uno</title><link>https://news.google.com/rss/articles/a1?oc=5</link><pubDate>Mon, 28 Sep 2026 12:00:00 GMT</pubDate><source url="https://www.example.com">Diario Uno</source></item>
            <item><title>Las mejores películas de suspenso de 2026, según la crítica - Diario Dos</title><link>https://news.google.com/rss/articles/a2?oc=5</link><pubDate>Mon, 28 Sep 2026 11:00:00 GMT</pubDate><source url="https://www.example.org">Diario Dos</source></item>
            <item><title>Suspenso en 2026: películas que no te puedes perder - Diario Tres</title><link>https://news.google.com/rss/articles/a3?oc=5</link><pubDate>Mon, 28 Sep 2026 10:00:00 GMT</pubDate><source url="https://www.example.net">Diario Tres</source></item>
            </channel></rss>
            """;
        var handler = new SearchSourcesHttpHandler
        {
            ["news.google.com"] = new(HttpStatusCode.OK, feed, "application/rss+xml"),
            ["lite.duckduckgo.com"] = new(HttpStatusCode.OK, SearchResultsPage(
                ("Top 3 películas de suspenso de 2026", "https://example.cl/top",
                    "Las tres mejores películas de suspenso de 2026: The Eyes, Silencio y La Presa.")), "text/html"),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search",
            Json("""{"query":"las 3 mejores películas de suspenso de 2026","limit":3,"listing":true}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(handler.Asked.Select(asked => asked.Uri.Host), Has.None.EqualTo("news.google.com"));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.Not.EqualTo("google_news_rss_search"));
            Assert.That(receipt.Result?.GetRawText() ?? "", Does.Not.Contain("Diario"));
        });
    }

    // Uso real v3 tanda 1 («quien gano el mundial del 2014» → «Brasil ganó la Copa Mundial de Fútbol de 2014.»): the
    // article's first three sentences, as the tanda read them (compose_audit fila 82), name Brasil as the host and say
    // nobody won. With the mind's answerWords, the article is read whole and the sentence that states it follows.
    private const string Mundial2014Intro =
        "La Copa Mundial de la FIFA Brasil 2014 (en portugués: Copa do Mundo FIFA de 2014) fue la vigésima edición de "
        + "la Copa Mundial de Fútbol. Se realizó en Brasil entre el 12 de junio y el 13 de julio de 2014, por segunda "
        + "vez en dicho país, tras el campeonato de 1950. Después de que el presidente de la FIFA, Joseph Blatter, "
        + "estableció en 2001 el criterio de rotación continental de la sede del torneo, América del Sur fue "
        + "seleccionada en 2004 para celebrar en 2014 su primera copa desde Argentina 1978.";

    private const string Mundial2014Article = Mundial2014Intro + "\n\nLa final se jugó en el estadio Maracaná de Río "
        + "de Janeiro ante 74 738 espectadores.\nEn la final, Alemania derrotó por 1-0 a Argentina en la prórroga y se "
        + "coronó por cuarta vez como campeón mundial.\nLa organización del torneo recibió críticas por los costes.";

    private static SearchSourcesHttpHandler Mundial2014Sources()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["es.wikipedia.org"] = WikipediaAnswer("es", ("Copa Mundial de Fútbol de 2014", Mundial2014Intro, false)),
        };
        handler.Routes.Add(("&titles=", WikipediaAnswer("es", ("Copa Mundial de Fútbol de 2014", Mundial2014Article, false))));
        return handler;
    }

    [Test]
    public async Task ARelationNoFragmentStatesReadsTheFirstArticleForTheSentenceThatStatesIt()
    {
        SearchSourcesHttpHandler handler = Mundial2014Sources();
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search",
            Json("""{"query":"quien gano el mundial del 2014","limit":5,"answerWords":"gan campeon vencio derroto corono titulo won champion"}"""),
            CancellationToken.None);

        string read = receipt.Result?.GetProperty("results")[0].GetProperty("snippet").GetString() ?? "";
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("wikipedia_es_api"));
            Assert.That(handler.Asked.Select(asked => Uri.UnescapeDataString(asked.Uri.AbsoluteUri)),
                Has.Some.Contains("&titles=Copa Mundial de Fútbol de 2014"));
            Assert.That(read, Does.Contain("Alemania derrotó por 1-0 a Argentina"));
            Assert.That(read, Does.Not.Contain("críticas por los costes"));
        });
    }

    [Test]
    public async Task WithoutAnswerWordsTheEncyclopediaSnippetStandsAlone()
    {
        SearchSourcesHttpHandler handler = Mundial2014Sources();
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"quien gano el mundial del 2014","limit":5}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(handler.Asked.Select(asked => asked.Uri.Query), Has.None.Contains("titles="));
            Assert.That(receipt.Result?.GetRawText() ?? "", Does.Not.Contain("Alemania"));
        });
    }

    // Contracaso: the datum is in the fragment («dirigida por James Cameron»), so no article is read.
    [Test]
    public async Task AFragmentThatStatesTheRelationIsAnsweredWithoutReadingTheArticle()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["es.wikipedia.org"] = WikipediaAnswer("es", ("Titanic (película de 1997)",
                "Titanic es una película estadounidense de 1997 escrita y dirigida por James Cameron.", false)),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search",
            Json("""{"query":"quien dirigio titanic","limit":5,"answerWords":"dirig direct"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result?.GetRawText() ?? "", Does.Contain("James Cameron"));
            Assert.That(handler.Asked.Select(asked => asked.Uri.Query), Has.None.Contains("titles="));
        });
    }

    [Test]
    public void AFragmentAnswersOnlyWithTheRelationAndEveryContentWordInOneSentence()
    {
        string[] win = ["gan", "campeon", "derroto", "corono"];
        Assert.Multiple(() =>
        {
            // «tras el campeonato de 1950» sits beside Brasil and 2014, without the «mundial» asked.
            Assert.That(SearchPageExcerpt.FragmentAnswers(
                "Copa Mundial de Fútbol de 2014. " + Mundial2014Intro, "quien gano el mundial del 2014", win), Is.False);
            Assert.That(SearchPageExcerpt.FragmentAnswers(
                "En la final de 2014, Alemania se coronó campeón mundial.", "quien gano el mundial del 2014", win), Is.True);
            Assert.That(SearchPageExcerpt.FragmentAnswers("Cualquier cosa.", "quien gano el mundial del 2014", []), Is.True);
        });
    }

    // Revisión adversarial (tanda 1, compose_audit fila 82): the four results the tanda read. The Conmebol
    // qualification's «el repechaje contra el ganador de la quinta ronda» carries «ganador», «mundial» and «2014» and
    // answers nothing; only the fragment of the article that would be read is judged, so the article is read.
    private static readonly (string Title, string Extract, bool Disambiguation)[] Mundial2014Results =
    [
        ("Copa Mundial de Fútbol de 2014", Mundial2014Intro, false),
        ("Clasificación de Conmebol para la Copa Mundial de Fútbol de 2014",
            "La clasificación de Conmebol para la Copa Mundial de Fútbol de 2014 contó con cuatro cupos directos y un "
            + "cupo para el repechaje contra el ganador de la quinta ronda de la clasificatoria asiática. Como "
            + "anfitrión, Brasil no pasó por la clasificación, por lo que en esta edición participaron las nueve "
            + "selecciones restantes.", false),
        ("Clasificación para la Copa Mundial de Fútbol de 2014",
            "Fueron 32 equipos los que compitieron en la Copa Mundial de Fútbol de 2014, con una plaza destinada al "
            + "país organizador, Brasil. En el programa publicado inicialmente se preveían 824 partidos para decidir "
            + "las 31 plazas en disputa para el Mundial de Brasil 2014, pero con el retiro de Bahamas y Mauricio, "
            + "solo se necesitaron 816.", false),
        ("Copa Mundial de Baloncesto de 2014",
            "Fue la segunda vez que se celebró un mundial de baloncesto en España (el anterior, en 1986), entrando así "
            + "en el grupo de países con más de un mundial organizado, en el que están Brasil (1954 y 1963) y "
            + "Argentina (1950 y 1990). Con un equipo NBA, Estados Unidos derrotó ampliamente a todos sus rivales y "
            + "logró defender de manera invicta y exitosa el título de 2010.", false),
    ];

    private const string WinWords =
        "gan campeon campeona vencio derroto corono consagro titulo won win champion beat defeat victor triumph";

    private const string WinWordsNot = "campeonato campeonatos championship championships ganancia ganancias";

    [Test]
    public async Task OnlyTheReadArticlesFragmentIsJudgedNotAnotherResultThatSaysWinner()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["es.wikipedia.org"] = WikipediaAnswer("es", Mundial2014Results),
        };
        handler.Routes.Add(("&titles=", WikipediaAnswer("es", ("Copa Mundial de Fútbol de 2014", Mundial2014Article, false))));
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search",
            Json("{\"query\":\"quien gano el mundial del 2014\",\"limit\":5,\"answerWords\":\"" + WinWords
                + "\",\"answerWordsNot\":\"" + WinWordsNot + "\"}"),
            CancellationToken.None);

        string read = receipt.Result?.GetProperty("results")[0].GetProperty("snippet").GetString() ?? "";
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("results").GetArrayLength(), Is.GreaterThan(1));
            Assert.That(handler.Asked.Select(asked => Uri.UnescapeDataString(asked.Uri.AbsoluteUri)),
                Has.Some.Contains("&titles=Copa Mundial de Fútbol de 2014"));
            Assert.That(read, Does.Contain("Alemania derrotó por 1-0 a Argentina"));
        });
    }

    // Revisión adversarial: the English article's opening, as the open API gives it, calls the cup «the quadrennial
    // world championship»; «championship» begins as «champion» and says nobody won. With the mind's answerWordsNot it
    // states nothing, and the article is read for the sentence that does.
    private const string WorldCup2014EnglishIntro =
        "The 2014 FIFA World Cup was the 20th FIFA World Cup, the quadrennial world championship for men's national "
        + "football teams organised by FIFA. It took place in Brazil from 12 June to 13 July 2014, after the country "
        + "was awarded the hosting rights in 2007.";

    [Test]
    public async Task AWordThatOnlyBeginsLikeTheRelationDoesNotSpareTheArticleRead()
    {
        string article = WorldCup2014EnglishIntro + "\n\nThe final was played at the Maracanã Stadium in Rio de "
            + "Janeiro.\nGermany won the tournament and its fourth World Cup title, beating Argentina 1–0 in extra "
            + "time in the final.\nThe tournament was criticised for its costs.";
        var handler = new SearchSourcesHttpHandler
        {
            ["en.wikipedia.org"] = WikipediaAnswer("en", ("2014 FIFA World Cup", WorldCup2014EnglishIntro, false)),
        };
        handler.Routes.Add(("&titles=", WikipediaAnswer("en", ("2014 FIFA World Cup", article, false))));
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search",
            Json("{\"query\":\"who won the 2014 world cup\",\"limit\":5,\"answerWords\":\"" + WinWords
                + "\",\"answerWordsNot\":\"" + WinWordsNot + "\"}"),
            CancellationToken.None);

        string read = receipt.Result?.GetProperty("results")[0].GetProperty("snippet").GetString() ?? "";
        string[] win = WinWords.Split(' ');
        string[] notStated = WinWordsNot.Split(' ');
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(read, Does.Contain("Germany won the tournament"));
            Assert.That(read, Does.Not.Contain("criticised"));
            // The cause, and its counter-case: without the exclusions «championship» passed for the relation.
            Assert.That(SearchPageExcerpt.FragmentAnswers(
                "2014 FIFA World Cup. " + WorldCup2014EnglishIntro, "who won the 2014 world cup", win), Is.True);
            Assert.That(SearchPageExcerpt.FragmentAnswers(
                "2014 FIFA World Cup. " + WorldCup2014EnglishIntro, "who won the 2014 world cup", win, notStated),
                Is.False);
            Assert.That(SearchPageExcerpt.FragmentAnswers(
                "Germany won the 2014 World Cup.", "who won the 2014 world cup", win, notStated), Is.True);
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
            // M65: what people or critics think of a work is not an encyclopedia's.
            Assert.That(WikipediaSearchSource.IsEncyclopedic("qué dijo la crítica sobre Oppenheimer"), Is.False);
            Assert.That(WikipediaSearchSource.IsEncyclopedic("¿La serie The Last of Us vale la pena?"), Is.False);
            Assert.That(WikipediaSearchSource.IsEncyclopedic("reseñas de la nueva película de Resident Evil"), Is.False);
            Assert.That(WikipediaSearchSource.IsEncyclopedic("qué piensa la gente de Colony"), Is.False);
            Assert.That(WikipediaSearchSource.IsEncyclopedic("is Dune worth watching"), Is.False);
            Assert.That(WikipediaSearchSource.IsEncyclopedic("quién dirigió Oppenheimer"), Is.True);
            // M81 (DEV-D v3m D-s012): what a share is worth today is not an encyclopedia's.
            Assert.That(WikipediaSearchSource.IsEncyclopedic("Cuánto vale la acción de Movistar"), Is.False);
            Assert.That(WikipediaSearchSource.IsEncyclopedic("how much is Tesla stock"), Is.False);
            Assert.That(WikipediaSearchSource.IsEncyclopedic("¿Vale la pena Dune?"), Is.False);
            Assert.That(WikipediaSearchSource.IsEncyclopedic("qué vale más en el Monopoly"), Is.True);
        });
    }

    // M65 (conv-v3g held-out t14): «qué dijo la crítica sobre Oppenheimer» was answered by
    // Wikipedia with «The Act of Killing» (a film by Joshua Oppenheimer) and the reply said it
    // found nothing. Opinions go to the news and the general engine; when neither answers,
    // the receipt says nothing was searched, and the encyclopedia is never asked.
    [Test]
    public async Task WhatCriticsSaidIsNotAskedToTheEncyclopedia()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["es.wikipedia.org"] = WikipediaAnswer("es",
                ("The Act of Killing", "The Act of Killing es una película de no-ficción dirigida por Joshua Oppenheimer.", false)),
            ["en.wikipedia.org"] = WikipediaAnswer("en",
                ("The Act of Killing", "The Act of Killing is a documentary film directed by Joshua Oppenheimer.", false)),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"qué dijo la crítica sobre Oppenheimer"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("web_search_unavailable"));
            Assert.That(handler.Asked.Select(asked => asked.Uri.Host), Has.None.Contains("wikipedia.org"));
            Assert.That(handler.Asked.Select(asked => asked.Uri.Host), Does.Contain("lite.duckduckgo.com"));
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

    // M98 (DEV-D v3x D-s111, D-p24-t1): a result that carries the query's names and not what is asked of them only
    // names what was asked about.
    [Test]
    public void AResultThatOnlyNamesWhatWasAskedAboutIsNotItsAnswer()
    {
        (string Query, string Title, string Snippet, SearchPertinence.Pertinence Expected)[] cases =
        [
            ("¿Qué distancia hay entre Lima y Cusco?", "Clásico Lima–Cusco",
                "El clásico entre equipos de Lima y Cusco se juega desde 1960.", SearchPertinence.Pertinence.NamesOnly),
            ("¿Qué distancia hay entre Lima y Cusco?", "Carretera Lima–Cusco",
                "La carretera une Lima y Cusco; la distancia por ella es de 1.105 km.", SearchPertinence.Pertinence.About),
            ("a fantasy film with Keanu Reeves", "John Wick",
                "John Wick is a 2014 American action thriller film starring Keanu Reeves.", SearchPertinence.Pertinence.NamesOnly),
            ("a fantasy film with Keanu Reeves", "Constantine (film)",
                "Constantine is a 2005 supernatural fantasy film starring Keanu Reeves.", SearchPertinence.Pertinence.About),
            ("an epic science fiction film with Keanu Reeves", "The Matrix",
                "The Matrix is a 1999 epic science fiction action film starring Keanu Reeves.", SearchPertinence.Pertinence.About),
            ("an epic science fiction film with Keanu Reeves", "Keanu (cat)",
                "A cat named after an actor.", SearchPertinence.Pertinence.None),
        ];
        Assert.Multiple(() =>
        {
            foreach ((string query, string title, string snippet, SearchPertinence.Pertinence expected) in cases)
                Assert.That(SearchPertinence.Judge(query, title, snippet), Is.EqualTo(expected), query + " → " + title);
        });
    }

    // M98 (DEV-D v3x D-s111): the encyclopedia's articles only named the two cities; the general engine answers the
    // distance. With the engine down, the article that names them is still what was read.
    [Test]
    public async Task WhatTheArticlesOnlyNameIsAskedToTheGeneralEngine()
    {
        HttpAnswer article = WikipediaAnswer("es",
            ("Clásico Lima–Cusco", "El clásico entre equipos de Lima y Cusco se juega desde 1960.", false));
        var handler = new SearchSourcesHttpHandler
        {
            ["es.wikipedia.org"] = article,
            ["en.wikipedia.org"] = new(HttpStatusCode.OK, """{"batchcomplete":true}""", "application/json"),
            ["lite.duckduckgo.com"] = new(HttpStatusCode.OK, SearchResultsPage(
                ("Distancia Lima - Cusco", "https://rutas.example.pe/lima-cusco",
                    "La distancia por carretera entre Lima y Cusco es de 1.105 km.")), "text/html"),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"¿Qué distancia hay entre Lima y Cusco?"}"""), CancellationToken.None);

        var down = new SearchSourcesHttpHandler { ["es.wikipedia.org"] = article };
        using var downHttp = new HttpClient(down);
        using var downAdapter = new WebBrowserAdapter(browser, downHttp);
        ExternalCapabilityReceipt named = await downAdapter.InvokeAsync(
            "web.search", Json("""{"query":"¿Qué distancia hay entre Lima y Cusco?"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("duckduckgo_lite_https"));
            Assert.That(receipt.Result?.GetProperty("results")[0].GetProperty("snippet").GetString(), Does.Contain("1.105 km"));
            Assert.That(named.Verified, Is.True, named.ErrorCode);
            Assert.That(named.Result?.GetProperty("authority").GetString(), Is.EqualTo("wikipedia_es_api"));
            Assert.That(named.Result?.GetProperty("results")[0].GetProperty("title").GetString(), Is.EqualTo("Clásico Lima–Cusco"));
        });
    }

    // M98 (DEV-D v3x D-w14-t1 «¿quién ha ganado la Vuelta este año?»): a year said by its relation to today reaches
    // the sources as its number.
    [Test]
    public void AYearSaidByItsRelationToTodayBecomesItsNumber()
    {
        Assert.Multiple(() =>
        {
            Assert.That(SearchQueryYear.Anchor("¿quién ganó el Giro este año?", 2031), Is.EqualTo("¿quién ganó el Giro 2031?"));
            Assert.That(SearchQueryYear.Anchor("campeón de la Copa América del año pasado", 2031),
                Is.EqualTo("campeón de la Copa América de 2030"));
            Assert.That(SearchQueryYear.Anchor("qué discos salieron en lo que va del año", 2031),
                Is.EqualTo("qué discos salieron en 2031"));
            Assert.That(SearchQueryYear.Anchor("dónde será el Mundial el año que viene", 2031),
                Is.EqualTo("dónde será el Mundial 2032"));
            Assert.That(SearchQueryYear.Anchor("who won the Masters this year?", 2031), Is.EqualTo("who won the Masters 2031?"));
            Assert.That(SearchQueryYear.Anchor("this year's Booker shortlist", 2031), Is.EqualTo("2031 Booker shortlist"));
            Assert.That(SearchQueryYear.Anchor("best laptops of last year", 2031), Is.EqualTo("best laptops of 2030"));
            Assert.That(SearchQueryYear.Anchor("el año del dragón en China", 2031), Is.EqualTo("el año del dragón en China"));
        });
    }

    // M98 (D-w14-t1): who won a race this year is asked with the year. The article of this year's race that does not
    // say who won only names it; the engine's results of another year are not about it.
    [Test]
    public async Task WhoWonThisYearIsAskedWithTheYear()
    {
        string year = DateTime.Now.Year.ToString(CultureInfo.InvariantCulture);
        string last = (DateTime.Now.Year - 1).ToString(CultureInfo.InvariantCulture);
        var handler = new SearchSourcesHttpHandler
        {
            ["es.wikipedia.org"] = WikipediaAnswer("es", ("Giro de Lombardía " + year,
                "El Giro de Lombardía " + year + " fue la edición de la carrera celebrada en octubre de " + year + ".", false)),
            ["lite.duckduckgo.com"] = new(HttpStatusCode.OK, SearchResultsPage(
                ("Ana Ríos ha ganado el Giro de Lombardía " + year, "https://ciclismo.example.com/" + year,
                    "Ana Ríos se impuso en el Giro de Lombardía " + year + "."),
                ("Bea Soto ha ganado el Giro de Lombardía " + last, "https://ciclismo.example.com/" + last,
                    "Bea Soto se impuso en el Giro de Lombardía " + last + ".")), "text/html"),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"¿Quién ha ganado el Giro de Lombardía este año?"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("duckduckgo_lite_https"));
            Assert.That(receipt.Result?.GetProperty("query").GetString(),
                Is.EqualTo("¿Quién ha ganado el Giro de Lombardía " + year + "?"));
            Assert.That(receipt.Result?.GetProperty("count").GetInt32(), Is.EqualTo(1));
            Assert.That(receipt.Result?.GetProperty("results")[0].GetProperty("title").GetString(), Does.Contain("Ana Ríos"));
            Assert.That(Uri.UnescapeDataString(handler.Asked[0].Uri.Query),
                Does.Contain("gsrsearch=ganado giro lombardia " + year + "&"));
        });
    }

    // M98 (DEV-D v3x D-p28-t2 «Look for movies in Union City.»): what is showing in a named place is a listing the
    // general engine answers; neither the encyclopedia (the film named like the town) nor the news is asked.
    [Test]
    public async Task WhatIsShowingInATownIsAskedToTheGeneralEngine()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WikipediaSearchSource.IsEncyclopedic("películas en Valdivia"), Is.False);
            Assert.That(WikipediaSearchSource.IsEncyclopedic("what movies are showing in Springfield"), Is.False);
            Assert.That(WikipediaSearchSource.IsEncyclopedic("Cines en Rancagua"), Is.False);
            Assert.That(WikipediaSearchSource.IsEncyclopedic("films set in Italy"), Is.True);
            Assert.That(WikipediaSearchSource.IsEncyclopedic("películas rodadas en Almería"), Is.True);
            Assert.That(WikipediaSearchSource.IsEncyclopedic("¿Quién dirigió la película Casablanca?"), Is.True);
        });
        var handler = new SearchSourcesHttpHandler
        {
            ["es.wikipedia.org"] = WikipediaAnswer("es", ("Valdivia (película)", "Valdivia es una película chilena.", false)),
            ["lite.duckduckgo.com"] = new(HttpStatusCode.OK, SearchResultsPage(
                ("Cartelera de cine en Valdivia - películas hoy", "https://cines.example.cl/valdivia",
                    "Películas en cartelera en los cines de Valdivia y sus horarios.")), "text/html"),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"películas en Valdivia"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("duckduckgo_lite_https"));
            Assert.That(handler.Asked.Select(asked => asked.Uri.Host), Is.EqualTo(new[] { "lite.duckduckgo.com" }));
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
            Assert.That(pages.Asked, Has.Count.EqualTo(1));
        });
    }

    // M98 (DEV-D v3x D-w01-t2): the sentences of the page that answer, figures first when a figure is asked; never
    // the page's scripts, menus or footer, and never what the snippet already said.
    [Test]
    public void APageIsReadForTheSentencesThatAnswerTheQuery()
    {
        string excerpt = SearchPageExcerpt.Read(RicePage, "cuánto arroz cocer por persona para la cena",
            "Cuánto arroz cocer por persona - Recetas Muchos cocineros dudan cuánto arroz cocer por persona cuando preparan una comida familiar.");
        Assert.Multiple(() =>
        {
            Assert.That(excerpt, Does.Contain("80 gramos de arroz crudo por persona"));
            Assert.That(excerpt, Does.Contain("320 gramos de arroz"));
            Assert.That(excerpt.IndexOf("80 gramos", StringComparison.Ordinal),
                Is.LessThan(excerpt.IndexOf("320 gramos", StringComparison.Ordinal)));
            Assert.That(excerpt, Does.Not.Contain("999"));
            Assert.That(excerpt, Does.Not.Contain("copyright"));
            Assert.That(excerpt, Does.Not.Contain("Muchos cocineros"));
            Assert.That(excerpt.Length, Is.LessThanOrEqualTo(600));
            Assert.That(SearchPageExcerpt.Read(RicePage, "historia de la ópera italiana", ""), Is.Empty);
        });
    }

    // M98 (D-w01-t2): the general engine's first pages are read within the search, and what answers follows the
    // snippet; a query of one or two content words reads no page, and a page that cannot be read keeps the snippet.
    [Test]
    public async Task TheGeneralEnginesFirstPagesAreReadForWhatTheSnippetCut()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["lite.duckduckgo.com"] = new(HttpStatusCode.OK, SearchResultsPage(
                ("Cuánto arroz cocer por persona - Recetas", "https://cocina.example.com/arroz",
                    "Muchos cocineros dudan cuánto arroz cocer por persona cuando preparan..."),
                ("Arroz para la cena por persona: guía", "https://caido.example.com/arroz",
                    "Guía de arroz por persona para la cena familiar...")), "text/html"),
            ["cocina.example.com"] = new(HttpStatusCode.OK, RicePage, "text/html"),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"cuánto arroz cocer por persona para la cena"}"""), CancellationToken.None);

        var shortHandler = new SearchSourcesHttpHandler
        {
            ["lite.duckduckgo.com"] = new(HttpStatusCode.OK, SearchResultsPage(
                ("Precio del arroz integral hoy", "https://cocina.example.com/arroz", "El arroz integral sube...")), "text/html"),
            ["cocina.example.com"] = new(HttpStatusCode.OK, RicePage, "text/html"),
        };
        using var shortHttp = new HttpClient(shortHandler);
        using var shortAdapter = new WebBrowserAdapter(browser, shortHttp);
        ExternalCapabilityReceipt brief = await shortAdapter.InvokeAsync(
            "web.search", Json("""{"query":"precio del arroz integral hoy"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            JsonElement results = receipt.Result!.Value.GetProperty("results");
            string first = results[0].GetProperty("snippet").GetString()!;
            Assert.That(first, Does.StartWith("Muchos cocineros dudan").And.Contain(" … ").And.Contain("80 gramos"));
            // The sentence the snippet cut is not read twice.
            Assert.That(first.IndexOf("Muchos cocineros", StringComparison.Ordinal),
                Is.EqualTo(first.LastIndexOf("Muchos cocineros", StringComparison.Ordinal)));
            Assert.That(results[1].GetProperty("snippet").GetString(),
                Is.EqualTo("Guía de arroz por persona para la cena familiar..."));
            Assert.That(handler.Asked.Select(asked => asked.Uri.Host),
                Does.Contain("cocina.example.com").And.Contain("caido.example.com"));
            Assert.That(brief.Verified, Is.True, brief.ErrorCode);
            Assert.That(brief.Result?.GetProperty("results")[0].GetProperty("snippet").GetString(),
                Is.EqualTo("El arroz integral sube..."));
            Assert.That(shortHandler.Asked.Select(asked => asked.Uri.Host), Does.Not.Contain("cocina.example.com"));
        });
    }

    // Ronda 24 (r23 t1-c03 «cuales son las peliculas mas taquilleras de la historia? dame el top 5» → «No lo
    // encontré.»): the annex's ranking is a table, as es.wikipedia writes it (a sorting key hidden with display:none,
    // references as <sup>); its rows were cut cell by cell and never read.
    private const string GrossingAnnexPage = """
        <html><head><title>Anexo:Películas con las mayores recaudaciones</title></head><body>
        <nav>Portada Categorías</nav>
        <h1>Anexo:Películas con las mayores recaudaciones</h1>
        <p>La película más taquillera de la historia es la primera de la tabla de abajo, en dólares sin ajustar.</p>
        <h2>Mayores recaudaciones por año</h2>
        <table><tr><th>Año</th><th>Película</th></tr><tr><td>1915</td><td>El nacimiento de una nación</td></tr>
        <tr><td>1939</td><td>Lo que el viento se llevó</td></tr></table>
        <h3>Lista</h3>
        <table class="wikitable"><caption>Películas con las mayores recaudaciones a nivel mundial (en USD)<sup class="mw-ref reference"><a href="#n1">[1]</a></sup></caption>
        <tr><th>N.º</th><th>Película</th><th>Recaudación mundial</th><th>Año de estreno</th></tr>
        <tr><th>1</th><td><i><a href="/wiki/Avatar">Avatar</a></i></td><td><span style="display:none">&amp;&amp;02923706026</span>2&nbsp;923&nbsp;706&nbsp;026</td><td>2009</td></tr>
        <tr><th>2</th><td><i>Avengers: Endgame</i></td><td>2&nbsp;799&nbsp;439&nbsp;100</td><td>2019</td></tr>
        <tr><th>3</th><td><i>Avatar: el sentido del agua</i></td><td>2&nbsp;320&nbsp;250&nbsp;281</td><td>2022</td></tr>
        <tr><th>4</th><td><i>Titanic</i></td><td>2&nbsp;264&nbsp;750&nbsp;694</td><td>1997</td></tr>
        <tr><th>5</th><td><i>Star Wars: el despertar de la Fuerza</i></td><td>2&nbsp;071&nbsp;310&nbsp;218</td><td>2015</td></tr>
        <tr><th>6</th><td><i>Avengers: Infinity War</i></td><td>2&nbsp;052&nbsp;415&nbsp;039</td><td>2018</td></tr>
        </table>
        <h3>Ajuste debido a la inflación</h3>
        <table class="wikitable"><caption>Películas más taquilleras por ajuste de inflación</caption>
        <tr><th>N.º</th><th>Película</th><th>Recaudación ajustada</th></tr>
        <tr><td>1</td><td>Lo que el viento se llevó</td><td>3&nbsp;700&nbsp;000&nbsp;000</td></tr>
        <tr><td>2</td><td>Avatar</td><td>3&nbsp;300&nbsp;000&nbsp;000</td></tr>
        </table>
        <h2>Referencias</h2><ol class="references"><li>Box Office Mojo, consultado en 2026.</li><li>The Numbers.</li></ol>
        </body></html>
        """;

    [Test]
    public void AListingAskedReadsThePagesFirstRankingAsRows()
    {
        const string asked = "cuales son las peliculas mas taquilleras de la historia? dame el top 5";
        string rows = SearchPageExcerpt.Rows(GrossingAnnexPage, asked, 5);
        string three = SearchPageExcerpt.Rows(GrossingAnnexPage, asked, 3);
        const string listicle = """
            <html><body><h2>Las 3 películas más taquilleras de la historia</h2>
            <ol><li>Avatar (2009)</li><li>Avengers: Endgame (2019)</li><li>Avatar: el sentido del agua (2022)</li></ol>
            </body></html>
            """;
        Assert.Multiple(() =>
        {
            Assert.That(rows, Does.StartWith("1. Avatar · 2 923 706 026 · 2009 | 2. Avengers: Endgame · 2 799 439 100 · 2019"));
            Assert.That(rows, Does.Contain("5. Star Wars: el despertar de la Fuerza · 2 071 310 218 · 2015"));
            Assert.That(rows, Does.Not.Contain("Infinity War"));
            // The sorting key hidden from the reader and the reference mark are no part of a row.
            Assert.That(rows, Does.Not.Contain("&").And.Not.Contain("[1]").And.Not.Contain("02923706026"));
            // A later ranking (adjusted for inflation) and a table ordered by year are not the ranking asked.
            Assert.That(rows, Does.Not.Contain("Lo que el viento").And.Not.Contain("nacimiento"));
            Assert.That(three.Split(" | "), Has.Length.EqualTo(3));
            Assert.That(SearchPageExcerpt.Rows(listicle, "las peliculas mas taquilleras", 5),
                Is.EqualTo("1. Avatar (2009) | 2. Avengers: Endgame (2019) | 3. Avatar: el sentido del agua (2022)"));
            // A ranking under a heading that names nothing asked (the references) is not read.
            Assert.That(SearchPageExcerpt.Rows(GrossingAnnexPage, "fuentes de box office mojo", 5), Is.Empty);
            Assert.That(SearchPageExcerpt.Rows(RicePage, asked, 5), Is.Empty);
        });
    }

    // Revisión 2 de la ronda 24: en.wikipedia's «List of highest-grossing films» writes Rank · Peak · Title; the peak
    // column was read as the row's name («1. 1 · Avengers: Endgame †»), and the mind took «1» for the first.
    [Test]
    public void ARankingsPeakColumnIsNoPartOfItsRows()
    {
        const string page = """
            <html><body><h2>Highest-grossing films</h2>
            <table class="wikitable"><caption>Highest-grossing films worldwide</caption>
            <tr><th>Rank</th><th>Peak</th><th>Title</th><th>Worldwide gross</th><th>Year</th></tr>
            <tr><td>1</td><td>1</td><th><i>Avengers: Endgame</i> †</th><td>$2,926,896,227</td><td>2019</td></tr>
            <tr><td>2</td><td>1</td><th><i>Avatar</i></th><td>$2,923,706,026</td><td>2009</td></tr>
            <tr><td>3</td><td>3</td><th><i>Avatar: The Way of Water</i></th><td>$2,320,250,281</td><td>2022</td></tr>
            </table></body></html>
            """;
        const string scored = """
            <html><body><h2>Top scorers of the league</h2>
            <table><tr><th>Rank</th><th>Player</th><th>Goals</th></tr>
            <tr><td>1</td><td>Ana Pérez</td><td>12</td></tr><tr><td>2</td><td>Lucía Gómez</td><td>9</td></tr></table>
            </body></html>
            """;
        Assert.Multiple(() =>
        {
            Assert.That(SearchPageExcerpt.Rows(page, "what are the highest grossing films", 3), Is.EqualTo(
                "1. Avengers: Endgame † · $2,926,896,227 · 2019 | 2. Avatar · $2,923,706,026 · 2009 | "
                + "3. Avatar: The Way of Water · $2,320,250,281 · 2022"));
            // Counter-case: a figure after the name (the goals) stays a cell of its row.
            Assert.That(SearchPageExcerpt.Rows(scored, "top scorers of the league", 2),
                Is.EqualTo("1. Ana Pérez · 12 | 2. Lucía Gómez · 9"));
        });
    }

    // Revisión 1 de la ronda 24: an <ol> under a heading that names what was asked is a ranking only when its items
    // are short entries. A WordPress comment list (h2.comments-title + ol.comment-list, each comment an <article>) and
    // a list of steps (sentences) are not; the listicle whose places are <h3> gives no rows from them.
    [Test]
    public void AnOrderedListOfCommentsOrStepsIsNoRanking()
    {
        const string asked = "cuales son las peliculas mas taquilleras de la historia? dame el top 5";
        const string comments = """
            <html><body><h1>Las 10 películas más taquilleras de la historia</h1>
            <h3>1. Avatar</h3><p>Dirigida por James Cameron.</p><h3>2. Avengers: Endgame</h3><p>De Marvel.</p>
            <h2 class="comments-title">2 comentarios en «Las 10 películas más taquilleras de la historia»</h2>
            <ol class="comment-list">
            <li id="comment-1" class="comment"><article class="comment-body"><footer class="comment-meta"><b class="fn">Juan Pérez</b> <span class="says">dice:</span></footer>
            <div class="comment-content"><p>Faltó Titanic, para mí es la mejor de todas.</p></div></article></li>
            <li id="comment-2" class="comment"><article class="comment-body"><footer class="comment-meta"><b class="fn">María</b> <span class="says">dice:</span></footer>
            <div class="comment-content"><p>Excelente artículo, gracias.</p></div></article></li>
            </ol></body></html>
            """;
        // Encargo W: comments that end with no mark and run short are told by their blocks (<article>, <p>): the check of
        // a block inside an item was written with a backspace character for its word boundary and never matched.
        const string bareComments = """
            <html><body><h2 class="comments-title">2 comentarios en «Las 10 películas más taquilleras de la historia»</h2>
            <ol class="comment-list">
            <li class="comment"><article class="comment-body"><b class="fn">Juan</b><p>Faltó Titanic</p></article></li>
            <li class="comment"><article class="comment-body"><b class="fn">María</b><p>Buenísimo el artículo</p></article></li>
            </ol></body></html>
            """;
        const string steps = """
            <html><body><h2>Cómo ver las películas más taquilleras gratis</h2>
            <ol><li>Abre la app y crea una cuenta.</li><li>Busca la película en el catálogo.</li><li>Pulsa reproducir.</li></ol>
            </body></html>
            """;
        const string entries = """
            <html><body><h2>Las 3 películas más taquilleras de la historia</h2>
            <ol><li><a href="/avatar">Avatar</a> (2009) – 2 923 millones</li><li>Avengers: Endgame (2019)</li><li>Titanic (1997)</li></ol>
            </body></html>
            """;
        Assert.Multiple(() =>
        {
            Assert.That(SearchPageExcerpt.Rows(comments, asked, 5), Is.Empty);
            Assert.That(SearchPageExcerpt.Rows(bareComments, asked, 5), Is.Empty);
            Assert.That(SearchPageExcerpt.Rows(steps, asked, 5), Is.Empty);
            // Counter-case: short entries, a link and a figure among them, are still the ranking.
            Assert.That(SearchPageExcerpt.Rows(entries, asked, 5),
                Is.EqualTo("1. Avatar (2009) – 2 923 millones | 2. Avengers: Endgame (2019) | 3. Titanic (1997)"));
        });
    }

    // Ronda 24: with listing (limit = how many), the first pages are read even for a short query and the ranking's
    // rows follow the snippet; the same query without listing reads no page (TheGeneralEnginesFirstPagesAreRead…).
    [Test]
    public async Task AListingAskedCarriesTheRankingRowsOfTheFirstPages()
    {
        static SearchSourcesHttpHandler Sources() => new()
        {
            ["lite.duckduckgo.com"] = new(HttpStatusCode.OK, SearchResultsPage(
                ("Anexo:Películas con las mayores recaudaciones - Wikipedia", "https://anexo.example.org/recaudaciones",
                    "La película más taquillera de la historia es la primera de la tabla.")), "text/html"),
            ["anexo.example.org"] = new(HttpStatusCode.OK, GrossingAnnexPage, "text/html"),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        SearchSourcesHttpHandler listed = Sources();
        using var listedHttp = new HttpClient(listed);
        using var listedAdapter = new WebBrowserAdapter(browser, listedHttp);
        ExternalCapabilityReceipt listing = await listedAdapter.InvokeAsync(
            "web.search", Json("""{"query":"peliculas mas taquilleras","limit":3,"listing":true}"""),
            CancellationToken.None);
        SearchSourcesHttpHandler plain = Sources();
        using var plainHttp = new HttpClient(plain);
        using var plainAdapter = new WebBrowserAdapter(browser, plainHttp);
        ExternalCapabilityReceipt single = await plainAdapter.InvokeAsync(
            "web.search", Json("""{"query":"peliculas mas taquilleras","limit":3}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(listing.Verified, Is.True, listing.ErrorCode);
            string snippet = listing.Result!.Value.GetProperty("results")[0].GetProperty("snippet").GetString()!;
            Assert.That(snippet, Does.StartWith("La película más taquillera de la historia es la primera de la tabla."));
            Assert.That(snippet, Does.Contain(" … ").And.Contain("1. Avatar · 2 923 706 026 · 2009 | 2. Avengers: Endgame"));
            Assert.That(snippet, Does.Contain("3. Avatar: el sentido del agua").And.Not.Contain("4. Titanic"));
            Assert.That(single.Verified, Is.True, single.ErrorCode);
            Assert.That(single.Result!.Value.GetProperty("results")[0].GetProperty("snippet").GetString(),
                Does.Not.Contain("1. Avatar"));
            Assert.That(plain.Asked.Select(asked => asked.Uri.Host), Does.Not.Contain("anexo.example.org"));
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

    // M98: a Latin-1 result page is read with its accents, and the request carries only a generic User-Agent.
    [Test]
    public async Task ALatinOneResultPageIsReadWithItsAccentsAndNothingOfThePerson()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["lite.duckduckgo.com"] = new(HttpStatusCode.OK, SearchResultsPage(
                ("Paella valenciana: cuánto arroz lleva", "https://recetas.example.es/paella",
                    "La receta tradicional de la paella valenciana y el arroz que lleva...")), "text/html"),
            ["recetas.example.es"] = new(HttpStatusCode.OK, "", "text/html; charset=ISO-8859-1",
                Raw: Encoding.Latin1.GetBytes(
                    "<html><body><p>Según la tradición, la paella valenciana lleva 400 gramos de arroz para cuatro personas y azafrán.</p></body></html>")),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"cuánto arroz lleva la paella valenciana"}"""), CancellationToken.None);

        AskedRequest page = handler.Asked.Single(asked => asked.Uri.Host == "recetas.example.es");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("results")[0].GetProperty("snippet").GetString(),
                Does.Contain("Según la tradición, la paella valenciana lleva 400 gramos de arroz para cuatro personas y azafrán."));
            Assert.That(page.Headers, Is.EqualTo(new[] { "User-Agent" }));
            Assert.That(page.UserAgent, Is.EqualTo("BAXY/1.0 page-read"));
        });
    }

    // M98: a result in the local network is never read, and neither is a public page's redirect into it.
    [Test]
    public async Task AResultPageInTheLocalNetworkIsNeverRead()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["lite.duckduckgo.com"] = new(HttpStatusCode.OK, SearchResultsPage(
                ("Paella valenciana: cuánto arroz lleva", "https://192.168.1.20/paella", "El arroz que lleva la paella valenciana..."),
                ("Paella valenciana: el arroz que lleva", "https://intranet.local/paella", "Cuánto arroz lleva la paella valenciana..."),
                ("Arroz de la paella valenciana: cuánto lleva", "https://recetas.example.es/paella", "La paella valenciana lleva arroz...")),
                "text/html"),
            ["192.168.1.20"] = new(HttpStatusCode.OK, "<p>La paella valenciana lleva 400 gramos de arroz, dice el router.</p>", "text/html"),
            ["intranet.local"] = new(HttpStatusCode.OK, "<p>La paella valenciana lleva 400 gramos de arroz, dice la intranet.</p>", "text/html"),
            ["recetas.example.es"] = new(HttpStatusCode.Found, "", "text/html", Location: "http://127.0.0.1/admin"),
            ["127.0.0.1"] = new(HttpStatusCode.OK, "<p>La paella valenciana lleva 400 gramos de arroz, dice este PC.</p>", "text/html"),
        };
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"cuánto arroz lleva la paella valenciana"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("dice"));
            Assert.That(handler.Asked.Select(asked => asked.Uri.Host), Does.Contain("recetas.example.es"));
            Assert.That(handler.Asked.Select(asked => asked.Uri.Host),
                Has.None.EqualTo("192.168.1.20").And.None.EqualTo("intranet.local").And.None.EqualTo("127.0.0.1"));
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

    private const string ArepasPage = """
        <html><head><title>Arepas de queso fáciles</title>
        <script type="application/ld+json">{"@context":"https://schema.org","@graph":[
          {"@type":"WebSite","name":"Cocina de prueba"},
          {"@type":["Recipe"],"name":"Arepas de queso","description":"Arepas rellenas de queso, crujientes por fuera. Ideales para el desayuno.",
           "recipeYield":["4","4 arepas"],
           "recipeIngredient":["2 tazas de harina de maíz precocida","2 1/2 tazas de agua tibia","1 cucharadita de sal &amp; pimienta","200 g de queso rallado"],
           "recipeInstructions":[{"@type":"HowToSection","name":"Masa","itemListElement":[
             {"@type":"HowToStep","text":"Mezcla el agua con la sal y agrega la harina poco a poco."},
             {"@type":"HowToStep","text":"Amasa 2 minutos y agrega el queso."}]},
             {"@type":"HowToStep","text":"Forma 4 bolas, aplánalas y cocínalas 5 minutos por lado en un sartén caliente."}]}
        ]}</script></head><body><p>Hoy te enseño unas arepas de queso.</p></body></html>
        """;

    // M102 (DEV-D v3z D-w10-t1): a recipe page publishes its recipe as schema.org data; it is read with its quantities,
    // its steps (sections included) and its servings, and only for the dish asked.
    [Test]
    public void ARecipePageIsReadFromItsPublishedData()
    {
        SearchPageRecipe.PageRecipe? read = SearchPageRecipe.Read(ArepasPage, "Arepas de queso fáciles", ["arepas", "queso"]);
        Assert.Multiple(() =>
        {
            Assert.That(read, Is.Not.Null);
            Assert.That(read!.Value.Name, Is.EqualTo("Arepas de queso"));
            Assert.That(read.Value.Recipe.Ingredients, Does.Contain("2 1/2 tazas de agua tibia").And.Contain("1 cucharadita de sal & pimienta"));
            Assert.That(read.Value.Recipe.Steps, Has.Length.EqualTo(3));
            Assert.That(read.Value.Recipe.Steps[1], Is.EqualTo("Amasa 2 minutos y agrega el queso."));
            Assert.That(read.Value.Recipe.Servings, Is.EqualTo(4));
            Assert.That(read.Value.Recipe.Description, Is.EqualTo("Arepas rellenas de queso, crujientes por fuera."));
            // Another dish, or a page with no data, is no recipe read.
            Assert.That(SearchPageRecipe.Read(ArepasPage, "Arepas de queso fáciles", ["pan", "pascua"]), Is.Null);
            Assert.That(SearchPageRecipe.Read(RicePage, "Cuánto arroz cocer", ["arroz"]), Is.Null);
            Assert.That(SearchPageRecipe.Read(
                ArepasPage.Replace("\"recipeInstructions\"", "\"otherInstructions\"", StringComparison.Ordinal),
                "Arepas de queso", ["arepas", "queso"]), Is.Null);
        });
    }

    // M102 (DEV-D v3z D-s017, D-w10-t1): with the dish in neither recipe book, the general engine is asked once, and the
    // first of its pages that publishes the recipe answers as the recipe read; the encyclopedia is not asked.
    [Test]
    public async Task ARecipeNoBookHasIsReadFromAResultsPage()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["lite.duckduckgo.com"] = new(HttpStatusCode.OK, SearchResultsPage(
                ("Arepas de queso - Recetas de casa", "https://sinreceta.example.com/arepas",
                    "Las arepas de queso son un clásico de la cocina venezolana y colombiana..."),
                ("Arepas de queso fáciles", "https://cocina.example.com/arepas-de-queso",
                    "Receta de arepas de queso caseras con harina de maíz...")), "text/html"),
            ["sinreceta.example.com"] = new(HttpStatusCode.OK, RicePage, "text/html"),
            ["cocina.example.com"] = new(HttpStatusCode.OK, ArepasPage, "text/html"),
        };
        handler.Routes.Add(("wikibooks.org", new(HttpStatusCode.OK, """{"batchcomplete":true}""", "application/json")));
        handler.Routes.Add(("lllang=en", new(HttpStatusCode.OK, """{"batchcomplete":true}""", "application/json")));
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"receta arepas de queso"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("reference").GetString(), Is.EqualTo("recipe"));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("recipe_page_jsonld"));
            Assert.That(receipt.Result?.GetProperty("servings").GetInt32(), Is.EqualTo(4));
            JsonElement first = receipt.Result!.Value.GetProperty("results")[0];
            Assert.That(first.GetProperty("url").GetString(), Is.EqualTo("https://cocina.example.com/arepas-de-queso"));
            Assert.That(first.GetProperty("snippet").GetString(),
                Does.Contain("Ingredientes (para 4 personas):").And.Contain("- 2 tazas de harina de maíz precocida")
                    .And.Contain("3. Forma 4 bolas"));
            Assert.That(handler.Asked.Count(asked => asked.Uri.Host == "lite.duckduckgo.com"), Is.EqualTo(1));
            Assert.That(handler.Asked.Where(asked => asked.Uri.Host.EndsWith("example.com", StringComparison.Ordinal))
                .All(asked => asked.UserAgent == "BAXY/1.0 page-read"));
        });
    }

    // M102: with no page publishing the recipe, the search goes on with the engine's reading (not asked twice).
    [Test]
    public async Task ARecipeNoPagePublishesKeepsTheEnginesResults()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["lite.duckduckgo.com"] = new(HttpStatusCode.OK, SearchResultsPage(
                ("Arepas de queso - Recetas de casa", "https://sinreceta.example.com/arepas",
                    "Las arepas de queso son un clásico de la cocina venezolana y colombiana...")), "text/html"),
            ["sinreceta.example.com"] = new(HttpStatusCode.OK, RicePage, "text/html"),
        };
        handler.Routes.Add(("wikibooks.org", new(HttpStatusCode.OK, """{"batchcomplete":true}""", "application/json")));
        handler.Routes.Add(("wikipedia.org", new(HttpStatusCode.OK, """{"batchcomplete":true}""", "application/json")));
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"receta arepas de queso"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("duckduckgo_lite_https"));
            Assert.That(receipt.Result?.TryGetProperty("reference", out _), Is.False);
            Assert.That(handler.Asked.Count(asked => asked.Uri.Host == "lite.duckduckgo.com"), Is.EqualTo(1));
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

    // M168 (D77; DEV-G G-w42-t1 «when do the Lakers play next?» → «I could not find when the Lakers play next.»): when a
    // named team plays is answered by ESPN's public calendar, with two requests (the team, its calendar) that carry
    // BAXY's User-Agent, and the same question again within minutes asks nothing new.
    [Test]
    public async Task WhenATeamPlaysIsAnsweredByEspnsCalendar()
    {
        var handler = new SearchSourcesHttpHandler();
        handler.Routes.Add(("apis/search/v2", new(HttpStatusCode.OK,
            EspnScheduleSourceTests.Fixture("search_lakers.json"), "application/json")));
        handler.Routes.Add(("basketball/nba/teams/13/schedule", new(HttpStatusCode.OK,
            EspnScheduleSourceTests.Fixture("nba_lakers_schedule.json"), "application/json")));
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http, sports: new EspnScheduleSource(
            http, static () => EspnScheduleSourceTests.Now, EspnScheduleSourceTests.Santiago));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"When do the Lakers play next?"}"""), CancellationToken.None);
        ExternalCapabilityReceipt again = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"When do the Lakers play next?"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("espn_public_schedule"));
            Assert.That(receipt.Result!.Value.GetProperty("results")[0].GetProperty("snippet").GetString(),
                Does.StartWith("Next game: Los Angeles Lakers play away against Sacramento Kings on Monday 2026-10-05 at 23:00"));
            Assert.That(again.Result?.GetProperty("authority").GetString(), Is.EqualTo("espn_public_schedule"));
            Assert.That(handler.Asked.Select(static asked => asked.Uri.AbsoluteUri), Is.EqualTo(new[]
            {
                "https://site.api.espn.com/apis/search/v2?query=lakers&limit=8&type=team",
                "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/schedule",
            }));
            Assert.That(handler.Asked.Select(static asked => asked.UserAgent),
                Has.All.Match(@"^BAXY/\d+\.\d+ \(https://github\.com/REDSOULTM/baxy-assistant\)$"));
        });
    }

    // M168: a team ESPN does not know leaves the search as it was (here every other source is unreachable, so it could
    // not be looked up); nothing is answered from ESPN.
    [Test]
    public async Task ATeamEspnDoesNotKnowGoesOnToTheOtherSources()
    {
        var handler = new SearchSourcesHttpHandler();
        handler.Routes.Add(("apis/search/v2", new(HttpStatusCode.OK,
            EspnScheduleSourceTests.Fixture("search_xyzzy.json"), "application/json")));
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http, sports: new EspnScheduleSource(
            http, static () => EspnScheduleSourceTests.Now, EspnScheduleSourceTests.Santiago));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"When do the Xyzzy Quux play next?"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("web_search_unavailable"));
            Assert.That(handler.Asked[0].Uri.AbsoluteUri,
                Is.EqualTo("https://site.api.espn.com/apis/search/v2?query=xyzzy%20quux&limit=8&type=team"));
            Assert.That(handler.Asked.Skip(1).Select(static asked => asked.Uri.Host), Has.None.EqualTo("site.api.espn.com"));
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
            // M154 (DEV-H H-s093): the nationality said before the peso, in English.
            Assert.That(FrankfurterRateSource.Parse("whats the dollar to mexican peso rate todya", chile),
                Is.EqualTo(new FrankfurterRateSource.CurrencyAsk(1m, "USD", "MXN")));
            Assert.That(FrankfurterRateSource.Parse("how many chilean pesos is 85000 dollars", chile),
                Is.EqualTo(new FrankfurterRateSource.CurrencyAsk(85000m, "USD", "CLP")));
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

    // M62 (v3e2-final F-p05-t1, Nominatim's answers of 2026-09-29): the car parks around the
    // Plaza del Polvorista were told by their whole addresses with nothing saying how near they
    // are. Each site carries its distance to the square, nearest first, and one farther than
    // the square's surroundings (1.5 km at least) is left out.
    [Test]
    public async Task APlaceReadSaysHowFarEachSiteIsAndLeavesOutTheFarOnes()
    {
        var handler = new SearchSourcesHttpHandler();
        handler.Routes.Add(("q=Plaza del Polvorista", new(HttpStatusCode.OK,
            """[{"lat":"36.5948388","lon":"-6.2270183","boundingbox":["36.5945842","36.5950933","-6.2272746","-6.2267619"],"display_name":"Plaza del Polvorista, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"}]""",
            "application/json")));
        handler.Routes.Add(("q=parking", new(HttpStatusCode.OK,
            """[{"osm_type":"way","osm_id":1,"name":"","type":"parking","lat":"36.5902","lon":"-6.2190","display_name":"Avenida de Europa, Las Viñas, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":2,"name":"","type":"parking","lat":"36.5958","lon":"-6.2260","display_name":"Avenida de la Bajamar, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":3,"name":"","type":"parking","lat":"36.6100","lon":"-6.2400","display_name":"Calle Lejana, El Puerto de Santa María, Cádiz, España"}]""",
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
            JsonElement results = receipt.Result!.Value.GetProperty("results");
            Assert.That(results.GetArrayLength(), Is.EqualTo(2), "the car park 2 km away is not near the square");
            Assert.That(results[0].GetProperty("snippet").GetString(), Does.StartWith("Avenida de la Bajamar"));
            Assert.That(results[0].GetProperty("distanceMeters").GetInt32(), Is.InRange(130, 160));
            Assert.That(results[1].GetProperty("distanceMeters").GetInt32(), Is.InRange(850, 950));
        });
    }

    // M63 (v3f-final F-p05-t1, reviewed «aparcamientos de Valdelagrana a 150 m de una plaza del centro, a
    // 2–3 km»): Nominatim's own answers of 2026-09-29 (both reproduced, compacted to the fields read). The
    // three candidates are the one Plaza del Polvorista OpenStreetMap has (street, park and bus stop within
    // 50 m, on the left bank of the Guadalete, whose suburb OpenStreetMap calls Valdelagrana), so the anchor
    // is not misresolved: the car parks said are 150–620 m from it, as published.
    private const string PolvoristaCandidates =
        """[{"osm_type":"way","osm_id":29451698,"lat":"36.5948388","lon":"-6.2270183","category":"highway","type":"tertiary","name":"Plaza del Polvorista","display_name":"Plaza del Polvorista, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España","boundingbox":["36.5945842","36.5950933","-6.2272746","-6.2267619"],"address":{"country_code":"es"}},{"osm_type":"way","osm_id":29451697,"lat":"36.5950470","lon":"-6.2273243","category":"leisure","type":"park","name":"Plaza del Polvorista","display_name":"Plaza del Polvorista, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, España","boundingbox":["36.5947017","36.5953921","-6.2277549","-6.2268937"],"address":{"country_code":"es"}},{"osm_type":"node","osm_id":13398649899,"lat":"36.5947788","lon":"-6.2271996","category":"highway","type":"bus_stop","name":"Plaza del Polvorista","display_name":"Plaza del Polvorista, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España","boundingbox":["36.5947288","36.5948288","-6.2272496","-6.2271496"],"address":{"country_code":"es"}}]""";

    private const string PolvoristaParking =
        """[{"osm_type":"way","osm_id":952407268,"lat":"36.5931010","lon":"-6.2204714","type":"parking","name":"","display_name":"Calle Río Majaceite, Las Viñas, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":237016676,"lat":"36.5952887","lon":"-6.2254513","type":"parking","name":"","display_name":"Avenida de la Bajamar, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":952407272,"lat":"36.5930603","lon":"-6.2224781","type":"parking","name":"","display_name":"Avenida de Valdelagrana, Las Viñas, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":1106171484,"lat":"36.5948204","lon":"-6.2221896","type":"parking","name":"","display_name":"Avenida de Europa, Las Viñas, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":1423300837,"lat":"36.6041595","lon":"-6.2182015","type":"parking","name":"Vehículos Autorizados","display_name":"Vehículos Autorizados, Avenida del Monasterio, El Tejar, Sudamérica, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":1423300839,"lat":"36.6045170","lon":"-6.2175435","type":"parking","name":"","display_name":"Avenida del Monasterio, El Tejar, Sudamérica, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":302015013,"lat":"36.6035873","lon":"-6.2174271","type":"parking","name":"","display_name":"Calle Francisco Cossi Ochoa, El Tejar, Sudamérica, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":301734888,"lat":"36.5917584","lon":"-6.2365322","type":"parking","name":"","display_name":"Calle Tórtola, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":301734891,"lat":"36.5914572","lon":"-6.2304048","type":"parking","name":"","display_name":"Calle Brújula, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"},{"osm_type":"way","osm_id":301734896,"lat":"36.5912467","lon":"-6.2365437","type":"parking","name":"","display_name":"Calle Pescadores, Valdelagrana, El Puerto de Santa María, Bahía de Cádiz, Cádiz, Andalucía, 11500, España"}]""";

    [Test]
    public void ThePlazaDelPolvoristaIsWhereOpenStreetMapHasIt()
    {
        OpenStreetMapPlaceSource.Area? anchor = OpenStreetMapPlaceSource.AreaOf(
            PolvoristaCandidates, ["plaza", "polvorista"], ["plaza", "polvorista"], "es");
        Assert.That(anchor, Is.Not.Null);
        List<OpenStreetMapPlaceSource.Place> parks =
            OpenStreetMapPlaceSource.Places(PolvoristaParking, anchor!.Value.Latitude, anchor.Value.Longitude);
        Assert.Multiple(() =>
        {
            Assert.That(anchor.Value.Latitude, Is.EqualTo(36.5948).Within(0.0005));
            Assert.That(anchor.Value.Longitude, Is.EqualTo(-6.2270).Within(0.0005));
            Assert.That(parks.Take(5).Select(static place => place.DistanceMeters),
                Is.EqualTo(new int?[] { 150, 430, 450, 480, 620 }), "the distances published in v3f-final t113");
            Assert.That(parks[0].Snippet, Does.StartWith("Avenida de la Bajamar"));
        });
    }

    [Test]
    public async Task APlaceWithSitesOnlyFarAwayHasNoneNear()
    {
        var handler = new SearchSourcesHttpHandler();
        handler.Routes.Add(("q=Plaza del Polvorista", new(HttpStatusCode.OK,
            """[{"lat":"36.5948388","lon":"-6.2270183","boundingbox":["36.5945842","36.5950933","-6.2272746","-6.2267619"],"display_name":"Plaza del Polvorista, Valdelagrana, El Puerto de Santa María, Cádiz, España"}]""",
            "application/json")));
        handler.Routes.Add(("q=parking", new(HttpStatusCode.OK,
            """[{"osm_type":"way","osm_id":3,"name":"","type":"parking","lat":"36.6100","lon":"-6.2400","display_name":"Calle Lejana, El Puerto de Santa María, Cádiz, España"}]""",
            "application/json")));
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(handler);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"aparcamiento en Plaza del Polvorista"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("web_search_places_not_found_near"));
            Assert.That(handler.Asked, Has.Count.EqualTo(2), "nothing else is searched for a place that was found");
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

    // M86 (held-out t17 «tengo ganas de escuchar reggaetón»): a query press the
    // client never showed playing stays an honest ambiguous failure and is never
    // retried by the adapter — the script already spent its one re-press.
    [Test]
    public async Task SpotifyQueryPressNotSeenPlayingIsNeverRetried()
    {
        var runner = new SequencedProcessRunner([
            "{\"ok\":false,\"effectObserved\":true,\"error\":\"spotify_play_clicked_not_verified\",\"title\":\"Spotify Premium\",\"selectedControl\":\"Reproducir Reggaetón Mix\",\"beforeNowPlaying\":\"after de conep\",\"observedNowPlaying\":\"after de conep\",\"pauseBefore\":false,\"selectedFlipped\":false,\"presses\":2,\"processId\":42}",
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
            Assert.That(receipt.Result, Is.Null);
            Assert.That(runner.Calls, Is.EqualTo(1));
        });
    }

    // M86: the cold client restored paused on the result's first track; the
    // script proved playback by the paused-to-playing change after its press.
    [Test]
    public async Task SpotifyQueryPlaybackSeenAfterThePressIsVerified()
    {
        var runner = new StubProcessRunner(
            "{\"ok\":true,\"effectObserved\":true,\"error\":null,\"title\":\"Conep - After (feat. Young Miko)\",\"selectedControl\":\"Reproducir Reggaetón Mix\",\"beforeNowPlaying\":\"after feat young miko de conep young miko\",\"observedNowPlaying\":\"after feat young miko de conep young miko\",\"pauseBefore\":false,\"selectedFlipped\":false,\"presses\":1,\"processId\":42}");
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
            (TimeSpan.FromSeconds(23), "{\"ok\":false,\"effectObserved\":false,\"error\":\"spotify_exact_result_not_found\",\"searches\":2,\"coldStart\":false,\"elements\":334}"),
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
