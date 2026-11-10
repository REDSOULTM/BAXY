using System.Diagnostics;
using System.Globalization;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.Audio;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Infrastructure;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class ExternalAdaptersTests
{
    // schedule takes the person's local time; seconds keep the trigger exact.
    private static string LocalAt(DateTimeOffset due) =>
        due.ToLocalTime().ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture);

    // FT/proveedores goal (review of receipts): «reiniciá» accepted, then «no, mejor apagala»: Windows refuses because a
    // transition is already scheduled; the receipt says so (nothing done by this request, the PC still goes down),
    // never the plain «not accepted» that read as nothing happening.
    [TestCase(true, "power_transition_already_pending")]
    [TestCase(false, "power_transition_not_accepted")]
    public async Task APowerTransitionRefusedBecauseOneIsPendingSaysSo(bool pending, string error)
    {
        var adapter = new WindowsPowerTransitionAdapter(
            new StubPowerTransitionPlatform("win32_initiateshutdown_shutdown_acceptance", accepted: false, pending));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.power", JsonSerializer.SerializeToElement(new { action = "shutdown" }), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(error));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
        });
    }

    [Test]
    public void TheShutdownPrivilegeIsEnabledOnThisProcessToken()
    {
        // Arreglos de uso real (2026-10-26): the privilege's LUID was laid out where Windows does not read it, so enabling
        // it always failed and every shutdown was refused before Windows was asked. Enabling it shuts nothing down.
        Assert.That(WindowsPowerTransitionPlatform.EnableShutdownPrivilege(), Is.True);
    }

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

    // Renew al máximo (8.3): the post-read that still found the instance was dropped from the failure; it is the state
    // after, with its authority, and the failure stays.
    [Test]
    public async Task ProcessTerminationWhosePostreadStillFindsItSaysItIsStillRunning()
    {
        var identity = new WindowsProcessIdentity(5151, 638900000000000001);
        var platform = new StubProcessTerminationPlatform(
            [[identity], [identity]], terminateResult: WindowsProcessTermination.NotTerminated);
        var adapter = new WindowsProcessTerminationAdapter(platform);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.process.terminate.named", Json("""{"name":"steam"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("process_termination_postread_failed"));
            JsonElement? state = receipt.Result?.GetProperty("stateAfter");
            Assert.That(state?.GetProperty("stillRunningCount").GetInt32(), Is.EqualTo(1));
            Assert.That(state?.GetProperty("requestedStateReached").GetBoolean(), Is.False);
            Assert.That(state?.GetProperty("authority").GetString(),
                Is.EqualTo("windows_process_original_identity_postread"));
        });
    }

    // Renew al máximo (8.3): the kill was sent and the post-read threw: one more read of the name says whether the
    // instances asked to end are gone; one that fails too adds nothing.
    [TestCase(false, 0, true)]
    [TestCase(false, 1, false)]
    [TestCase(true, -1, false)]
    public async Task ProcessTerminationWhosePostreadThrewReadsOnceMore(bool rereadThrows, int stillRunning, bool reached)
    {
        var identity = new WindowsProcessIdentity(5151, 638900000000000001);
        var platform = new FlakyProcessTerminationPlatform(identity, rereadThrows, stillRunning == 1);
        var adapter = new WindowsProcessTerminationAdapter(platform);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.process.terminate.named", Json("""{"name":"steam"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo("process_termination_failed"));
            if (rereadThrows)
            {
                Assert.That(receipt.Result, Is.Null);
                return;
            }
            JsonElement? state = receipt.Result?.GetProperty("stateAfter");
            Assert.That(state?.GetProperty("stillRunningCount").GetInt32(), Is.EqualTo(stillRunning));
            Assert.That(state?.GetProperty("requestedStateReached").GetBoolean(), Is.EqualTo(reached));
        });
    }

    // FT/proveedores goal (review of receipts): the one instance runs elevated (Windows refuses BAXY): the receipt names
    // that, with the counts, and nothing was done, so its effect is not «possible».
    [Test]
    public async Task AnInstanceWindowsWillNotLetBaxyEndIsNamedAsDenied()
    {
        var identity = new WindowsProcessIdentity(5151, 638900000000000001);
        var platform = new StubProcessTerminationPlatform(
            [[identity], [identity]], terminateResult: WindowsProcessTermination.Denied);
        var adapter = new WindowsProcessTerminationAdapter(platform);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.process.terminate.named", Json("""{"name":"steam"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("process_termination_access_denied"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result?.GetProperty("deniedCount").GetInt32(), Is.EqualTo(1));
            Assert.That(receipt.Result?.GetProperty("stillRunningCount").GetInt32(), Is.EqualTo(1));
        });
    }

    // Renew al máximo (B-SYS-6): «cierra svchost» finds dozens of instances, most of them SYSTEM services whose start
    // time Windows will not let BAXY read; the read threw and the whole call ended as process_termination_failed
    // before ending the person's own instances. Each unreadable one is now its own denied identity.
    [Test]
    public void ASnapshotCountsAnInstanceWhoseStartTimeIsRefusedAsDeniedAndSkipsOneThatExited()
    {
        DateTime started = new(2026, 10, 22, 9, 0, 0, DateTimeKind.Utc);

        IReadOnlyList<WindowsProcessIdentity> identities = WindowsProcessTerminationPlatform.Identities(
        [
            (4242, () => started),
            (9001, () => throw new System.ComponentModel.Win32Exception(5)),
            (7070, () => throw new InvalidOperationException("exited")),
        ]);

        Assert.That(identities, Is.EqualTo(new[]
        {
            new WindowsProcessIdentity(4242, started.Ticks),
            new WindowsProcessIdentity(9001, 0, AccessDenied: true),
        }));
    }

    [Test]
    public async Task AnInstanceWhoseIdentityCannotBeReadIsNeverEndedAndIsNamedAsDenied()
    {
        var system = new WindowsProcessIdentity(9001, 0, AccessDenied: true);
        var own = new WindowsProcessIdentity(4242, 638900000000000000);
        var platform = new StubProcessTerminationPlatform(
            [[own, system], [system]], terminateResult: WindowsProcessTermination.Terminated);
        var adapter = new WindowsProcessTerminationAdapter(platform);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.process.terminate.named", Json("""{"name":"node"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(platform.Terminated, Is.EqualTo(new[] { own }));
            Assert.That(receipt.ErrorCode, Is.EqualTo("process_termination_access_denied"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.Result?.GetProperty("terminatedCount").GetInt32(), Is.EqualTo(1));
            Assert.That(receipt.Result?.GetProperty("deniedCount").GetInt32(), Is.EqualTo(1));
            Assert.That(receipt.Result?.GetProperty("stillRunningCount").GetInt32(), Is.EqualTo(1));
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
            Json("""{"name":"steamwebhelper.exe"}"""),
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

    // Encargo 80: Windows' light or dark mode is read from where Windows keeps it, not from a page's words: 0 dark, 1 light,
    // the two choices apart «custom» (Microsoft's «Light, Dark, or Custom»), and no value at all Windows' default.
    [TestCase(0, 0, "dark", "dark", "dark", "hkcu_themes_personalize")]
    [TestCase(1, 1, "light", "light", "light", "hkcu_themes_personalize")]
    [TestCase(0, 1, "custom", "dark", "light", "hkcu_themes_personalize")]
    [TestCase(1, 0, "custom", "light", "dark", "hkcu_themes_personalize")]
    [TestCase(null, null, "light", "light", "light", "windows_default_light_no_value_set")]
    public async Task ColorModeIsReadFromWhereWindowsKeepsIt(
        int? windows, int? apps, string mode, string windowsMode, string appsMode, string authority)
    {
        using TemporaryDirectory temporary = new();
        var adapter = new WindowsDeviceControlAdapter(temporary.Path, temporary.Path, new StubProcessRunner(""))
        {
            PersonalizeValue = name => name switch
            {
                "SystemUsesLightTheme" => windows,
                "AppsUseLightTheme" => apps,
                _ => throw new InvalidOperationException(name),
            },
        };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.settings.status", Json("""{"setting":"color_mode"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result?.GetProperty("mode").GetString(), Is.EqualTo(mode));
            Assert.That(receipt.Result?.GetProperty("windowsMode").GetString(), Is.EqualTo(windowsMode));
            Assert.That(receipt.Result?.GetProperty("appsMode").GetString(), Is.EqualTo(appsMode));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo(authority));
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

    // Holdout v4 (falsedad, a partial read told as a whole one): a log read that stopped at its limit of events says it
    // read only the newest ones of those hours; one that read all of them reached the end.
    [Test]
    public async Task ACrashLogReadThatStoppedAtItsLimitIsReadInPart()
    {
        const string stopped = """
            {"ok":true,"firstObservationCount":80,"secondObservationCount":80,"stableCount":80,"readCap":80,"events":[{"recordId":1,"eventId":1000}]}
            """;
        const string whole = """
            {"ok":true,"firstObservationCount":3,"secondObservationCount":3,"stableCount":3,"readCap":80,"events":[{"recordId":1,"eventId":1000}]}
            """;

        ExternalCapabilityReceipt cut = await new WindowsApplicationCrashDiagnosticAdapter(new StubProcessRunner(stopped))
            .InvokeAsync("system.application.crash.diagnose", Json("""{"hours":24,"limit":20}"""), CancellationToken.None);
        ExternalCapabilityReceipt all = await new WindowsApplicationCrashDiagnosticAdapter(new StubProcessRunner(whole))
            .InvokeAsync("system.application.crash.diagnose", Json("""{"hours":24,"limit":20}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(cut.Result?.GetProperty("readInPart").GetBoolean(), Is.True);
            Assert.That(cut.Result?.GetProperty("endReached").GetBoolean(), Is.False);
            Assert.That(cut.Result?.GetProperty("eventsSeen").GetInt32(), Is.EqualTo(80));
            Assert.That(cut.Result?.GetProperty("eventsShown").GetInt32(), Is.EqualTo(1));
            Assert.That(all.Result?.TryGetProperty("readInPart", out _), Is.False);
            Assert.That(all.Result?.GetProperty("endReached").GetBoolean(), Is.True);
        });
    }

    // Banco ciego c3 C3-130 s0 («termina explorer.exe desde el Administrador de tareas»): the force-kill of explorer.exe
    // was accepted and asked «Should I force-kill explorer.exe?»; a yes would have taken the taskbar and the desktop.
    // A process of Windows' shell or session is refused before the person is asked, and never ended.
    [TestCase("explorer.exe")]
    [TestCase("DWM")]
    [TestCase("sihost")]
    [TestCase("StartMenuExperienceHost.exe")]
    [TestCase("winlogon")]
    public async Task ForceKillingAProcessOfWindowsShellOrSessionIsRefusedBeforeTheQuestion(string name)
    {
        var identity = new WindowsProcessIdentity(4242, 638900000000000000);
        var platform = new StubProcessTerminationPlatform(
            [[identity], []], terminateResult: WindowsProcessTermination.Terminated);
        var adapter = new WindowsProcessTerminationAdapter(platform);
        JsonElement arguments = Json(JsonSerializer.Serialize(new { name }));

        ExternalCapabilityReceipt? preflight = await ((IExternalOperationAdapter)adapter).PreflightAsync(
            "system.process.terminate.named", arguments, CancellationToken.None);
        ExternalCapabilityReceipt invoked = await adapter.InvokeAsync(
            "system.process.terminate.named", arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(preflight?.ErrorCode, Is.EqualTo("process_part_of_windows"));
            Assert.That(preflight?.EffectMayHaveOccurred, Is.False);
            Assert.That(invoked.ErrorCode, Is.EqualTo("process_part_of_windows"));
            Assert.That(platform.Terminated, Is.Empty);
        });
    }

    [Test]
    public async Task ForceKillingAnOrdinaryProgramHasNoPreflightFailure()
    {
        var platform = new StubProcessTerminationPlatform([], terminateResult: WindowsProcessTermination.Terminated);
        ExternalCapabilityReceipt? preflight = await ((IExternalOperationAdapter)new WindowsProcessTerminationAdapter(
            platform)).PreflightAsync("system.process.terminate.named", Json("""{"name":"steam.exe"}"""),
            CancellationToken.None);

        Assert.That(preflight, Is.Null);
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
            // With no capture kept, the way to one.
            Assert.That(missing.Result?.GetProperty("next").GetString(), Is.EqualTo(
                "capture_screenshot {} takes a capture; this call read nothing: no capture is kept with the id "
                + "«capture_00000000000000000000000000000000», and none is kept at all"));
        });
    }

    // uso-88 (diag-946e F10 c2: «capture_9d0d…284», one digit short, failed bare as capture_identity_invalid and the
    // answer was «la imagen no quedó guardada»): an id that is not a kept capture's fails naming the newest capture
    // kept, as the same call with it written.
    [Test]
    public async Task AMiscopiedCaptureIdFailsNamingTheNewestCaptureKept()
    {
        using TemporaryDirectory temporary = new();
        string older = "capture_" + new string('a', 32);
        string newest = "capture_9d0d79cae9964288c5f5da38f7bc2841";
        await File.WriteAllBytesAsync(Path.Combine(temporary.Path, older + ".bmp"), WideCapture());
        await File.WriteAllBytesAsync(Path.Combine(temporary.Path, newest + ".bmp"), WideCapture());
        File.SetLastWriteTimeUtc(Path.Combine(temporary.Path, older + ".bmp"), DateTime.UtcNow.AddMinutes(-5));
        File.WriteAllText(Path.Combine(temporary.Path, "capture_notes.txt"), "not a capture");
        using var adapter = new CaptureVisionAdapter(temporary.Path);

        ExternalCapabilityReceipt shortId = await adapter.InvokeAsync(
            "vision.describe", Json("""{"captureId":"capture_9d0d79cae9964288c5f5da38f7bc284"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt absent = await adapter.InvokeAsync(
            "ocr.read", Json("""{"captureId":"capture_9d0d79cae9964288c5f5da38f7bc2842"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(shortId.ErrorCode, Is.EqualTo("capture_identity_invalid"));
            Assert.That(shortId.Result?.GetProperty("next").GetString(), Is.EqualTo(
                "vision_describe {\"captureId\":\"" + newest + "\"} reads the newest capture kept; this call read "
                + "nothing: «capture_9d0d79cae9964288c5f5da38f7bc284» is not a capture's id"));
            Assert.That(absent.ErrorCode, Is.EqualTo("capture_not_found"));
            Assert.That(absent.Result?.GetProperty("next").GetString(), Is.EqualTo(
                "ocr_read {\"captureId\":\"" + newest + "\"} reads the newest capture kept; this call read nothing: "
                + "no capture is kept with the id «capture_9d0d79cae9964288c5f5da38f7bc2842»"));
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

    // Encargo 34: with no OCR engine, the call that can describe the capture comes first, with its argument written.
    [Test]
    public void NoOcrEngineStartsWithTheDescriptionOfTheCapture() =>
        Assert.That(CaptureVisionAdapter.EngineMissingNext("capture_" + new string('b', 32)), Is.EqualTo(
            "vision_describe {\"captureId\":\"capture_" + new string('b', 32) + "\"} can describe it; this call read "
            + "nothing: Windows has no OCR for this language and Tesseract is not installed, so this capture cannot be "
            + "read as text here"));

    // Renew al máximo (w8): a Tesseract that starts and fails is told as that, with what to do, never as a missing
    // Windows OCR language pack (windows_ocr_language_not_available, as every Tesseract failure was).
    [Test]
    [NonParallelizable]
    public async Task ATesseractThatFailsIsToldAsItsOwnFailureWithWhatToDo()
    {
        using TemporaryDirectory temporary = new();
        string tessdata = Path.Combine(temporary.Path, "tessdata");
        Directory.CreateDirectory(tessdata);
        File.WriteAllBytes(Path.Combine(tessdata, "eng.traineddata"), [1]);
        File.WriteAllBytes(Path.Combine(tessdata, "spa.traineddata"), [1]);
        string capture = Path.Combine(temporary.Path, "capture_" + new string('a', 32) + ".bmp");
        File.WriteAllBytes(capture, new byte[64]);
        // where.exe takes Tesseract's arguments as a bad search and exits with an error, as a broken Tesseract does.
        string failing = Path.Combine(Environment.SystemDirectory, "where.exe");
        string? previousExecutable = Environment.GetEnvironmentVariable("BAXY_TESSERACT_EXE");
        string? previousTessdata = Environment.GetEnvironmentVariable("BAXY_TESSDATA_DIR");
        try
        {
            Environment.SetEnvironmentVariable("BAXY_TESSERACT_EXE", failing);
            Environment.SetEnvironmentVariable("BAXY_TESSDATA_DIR", tessdata);

            ExternalCapabilityReceipt failed = await CaptureVisionAdapter.ReadTesseractOcrAsync(
                "ocr.read", "capture_" + new string('a', 32), capture, null, CancellationToken.None);
            ExternalCapabilityReceipt french = await CaptureVisionAdapter.ReadTesseractOcrAsync(
                "ocr.read", "capture_" + new string('a', 32), capture, "fr-FR", CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(failed.ErrorCode, Is.EqualTo("tesseract_ocr_failed"));
                Assert.That(failed.Verified, Is.False);
                Assert.That(failed.Result!.Value.GetProperty("exitCode").GetInt32(), Is.Not.Zero);
                Assert.That(failed.Result!.Value.GetProperty("next").GetString(), Does.Contain("vision_describe"));
                Assert.That(french.ErrorCode, Is.EqualTo("windows_ocr_language_not_available"));
                // Encargo 34: the read without the language comes first, as the call with its argument written.
                Assert.That(french.Result!.Value.GetProperty("next").GetString(), Is.EqualTo(
                    "ocr_read {\"captureId\":\"capture_" + new string('a', 32) + "\"}, without «language», reads "
                    + "Spanish and English; this call read nothing: neither Windows OCR nor Tesseract has this language"));
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_TESSERACT_EXE", previousExecutable);
            Environment.SetEnvironmentVariable("BAXY_TESSDATA_DIR", previousTessdata);
        }
    }

    // Encargo 48 (banco de uso F10, 4 of 4): «dime qué número de turno me salió en lo que tengo abierto» took a capture,
    // its description failed with vision_provider_not_configured and nothing more, and the answer was «no puedo ver la
    // pantalla» with the number written in the Notepad in front. The failure leads with the read of the window in front
    // (its process; a protected one, or none, keeps the call without it).
    [Test]
    [NonParallelizable]
    public async Task ADescriptionWithNoVisionModelLeadsWithReadingTheWindowInFront()
    {
        using var directory = new TemporaryDirectory();
        string captureId = "capture_" + new string('b', 32);
        await File.WriteAllBytesAsync(Path.Combine(directory.Path, captureId + ".bmp"), WideCapture());
        string? endpoint = Environment.GetEnvironmentVariable("BAXY_VISION_ENDPOINT");
        string? model = Environment.GetEnvironmentVariable("BAXY_VISION_MODEL");
        try
        {
            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", null);
            Environment.SetEnvironmentVariable("BAXY_VISION_MODEL", null);
            using var notepad = new CaptureVisionAdapter(directory.Path)
            {
                ApplicationInFront = _ => ValueTask.FromResult<string?>("Notepad"),
            };
            using var none = new CaptureVisionAdapter(directory.Path)
            {
                ApplicationInFront = _ => ValueTask.FromResult<string?>(null),
            };
            string arguments = $$"""{"captureId":"{{captureId}}","prompt":"¿qué número sale?"}""";
            ExternalCapabilityReceipt named = await notepad.InvokeAsync(
                "vision.describe", Json(arguments), CancellationToken.None);
            ExternalCapabilityReceipt unnamed = await none.InvokeAsync(
                "vision.describe", Json(arguments), CancellationToken.None);

            // uso-88 (diag-bc8c F10, 2 of 6 answered «no hay un modelo de visión» with the number on screen): the OCR of
            // this same capture comes first, as the call with its argument written; the window's read stays beside it.
            string ocr = "ocr_read {\"captureId\":\"" + captureId + "\"} reads the text in this capture, and ";
            const string Rest = " the text the window in front shows; this call described nothing: no vision "
                + "model is configured on this PC, so no capture can be described here";
            Assert.Multiple(() =>
            {
                Assert.That(named.ErrorCode, Is.EqualTo("vision_provider_not_configured"));
                Assert.That(named.Verified, Is.False);
                Assert.That(named.EffectObserved, Is.False);
                Assert.That(named.Result?.GetProperty("next").GetString(), Is.EqualTo(
                    ocr + "input_visible_controls {\"application\":\"Notepad\",\"includeText\":true}" + Rest));
                Assert.That(unnamed.ErrorCode, Is.EqualTo("vision_provider_not_configured"));
                Assert.That(unnamed.Result?.GetProperty("next").GetString(), Is.EqualTo(
                    ocr + "input_visible_controls {\"includeText\":true}" + Rest));
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", endpoint);
            Environment.SetEnvironmentVariable("BAXY_VISION_MODEL", model);
        }
    }

    // Pedido del dueño 2026-11-08: «si el modelo no tiene visión, BAXY ya no podrá usar la visión, y listo». With another
    // model the vision endpoint is that model (the translator); one that does not see answers 501, and the description says
    // so, with the same reads that need no vision first, not as a failed request.
    [Test]
    [NonParallelizable]
    public async Task ADescriptionByAModelThatDoesNotSeeSaysSoAndLeadsWithWhatNeedsNoVision()
    {
        using var directory = new TemporaryDirectory();
        string captureId = "capture_" + new string('c', 32);
        await File.WriteAllBytesAsync(Path.Combine(directory.Path, captureId + ".bmp"), WideCapture());
        string? endpoint = Environment.GetEnvironmentVariable("BAXY_VISION_ENDPOINT");
        string? model = Environment.GetEnvironmentVariable("BAXY_VISION_MODEL");
        try
        {
            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", "http://127.0.0.1:8091/v1/chat/completions");
            Environment.SetEnvironmentVariable("BAXY_VISION_MODEL", "otro");
            using var http = new HttpClient(new NoVisionHandler());
            using var adapter = new CaptureVisionAdapter(directory.Path, http)
            {
                ApplicationInFront = _ => ValueTask.FromResult<string?>("Notepad"),
            };
            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
                "vision.describe", Json($$"""{"captureId":"{{captureId}}","prompt":"¿qué sale?"}"""), CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(receipt.ErrorCode, Is.EqualTo("vision_provider_not_configured"));
                Assert.That(receipt.Verified, Is.False);
                Assert.That(receipt.Result?.GetProperty("next").GetString(), Does.StartWith("ocr_read {\"captureId\":\"" + captureId + "\"}")
                    .And.EndWith("the model BAXY uses now does not see images, so no capture can be described while it is in use"));
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", endpoint);
            Environment.SetEnvironmentVariable("BAXY_VISION_MODEL", model);
        }
    }

    private sealed class NoVisionHandler : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken) =>
            Task.FromResult(new HttpResponseMessage(HttpStatusCode.NotImplemented)
            {
                Content = new StringContent("""{"error":{"code":"model_without_vision"}}"""),
            });
    }

    [Test]
    [NonParallelizable]
    public async Task VisionBindsConfiguredProviderResponseToExactCaptureHash()
    {
        using var directory = new TemporaryDirectory();
        string captureId = "capture_" + new string('a', 32);
        byte[] bytes = WideCapture();
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

    // Uso 104 (F31, uso real 04-11: 5 of 5 turns with vision.describe spent the next decision's whole budget re-reading
    // the conversation): a description goes to the slot that holds the mind's conversation, so it sets the slot's state
    // aside first and puts it back after, as the click's vision does, and asks on that same slot.
    [Test]
    [NonParallelizable]
    public async Task ADescriptionSetsTheMindsSlotAsideAndPutsItBack()
    {
        using var directory = new TemporaryDirectory();
        using var slots = new TemporaryDirectory();
        string captureId = "capture_" + new string('a', 32);
        await File.WriteAllBytesAsync(Path.Combine(directory.Path, captureId + ".bmp"), WideCapture());
        string[] names = ["BAXY_VISION_ENDPOINT", "BAXY_VISION_MODEL", "BAXY_VISION_SLOT", "BAXY_VISION_SLOT_DIR"];
        string?[] saved = [.. names.Select(Environment.GetEnvironmentVariable)];
        var asked = new List<string>();
        string? chat = null;
        string? held = null;
        using var http = new HttpClient(new LambdaHttpHandler(async (request, token) =>
        {
            asked.Add(request.RequestUri!.PathAndQuery);
            string body = await request.Content!.ReadAsStringAsync(token);
            if (request.RequestUri.AbsolutePath.StartsWith("/slots/", StringComparison.Ordinal))
            {
                held = JsonDocument.Parse(body).RootElement.GetProperty("filename").GetString();
                await File.WriteAllTextAsync(Path.Combine(slots.Path, held!), "state", token);
                return new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent("{}") };
            }
            chat = body;
            return new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent("""{"choices":[{"message":{"content":"Una ventana."}}]}"""),
            };
        }));
        try
        {
            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", "http://127.0.0.1:8090/v1/chat/completions");
            Environment.SetEnvironmentVariable("BAXY_VISION_MODEL", "vision-test");
            Environment.SetEnvironmentVariable("BAXY_VISION_SLOT", "0");
            Environment.SetEnvironmentVariable("BAXY_VISION_SLOT_DIR", slots.Path);
            using var adapter = new CaptureVisionAdapter(directory.Path, http);
            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
                "vision.describe", Json($$"""{"captureId":"{{captureId}}"}"""), CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.True);
                Assert.That(asked, Is.EqualTo(new[]
                {
                    "/slots/0?action=save", "/v1/chat/completions", "/slots/0?action=restore",
                }));
                Assert.That(JsonDocument.Parse(chat!).RootElement.GetProperty("id_slot").GetInt32(), Is.Zero);
                // The file holds the person's conversation: it stays on disk no longer than the question.
                Assert.That(Directory.GetFiles(slots.Path), Is.Empty);
            });
        }
        finally
        {
            for (int index = 0; index < names.Length; index++)
                Environment.SetEnvironmentVariable(names[index], saved[index]);
        }
    }

    // A slot that could not be set aside costs a slower next decision, not the description the person asked for.
    [Test]
    [NonParallelizable]
    public async Task ADescriptionStillAnswersWhenTheSlotCouldNotBeSetAside()
    {
        using var directory = new TemporaryDirectory();
        using var slots = new TemporaryDirectory();
        string captureId = "capture_" + new string('a', 32);
        await File.WriteAllBytesAsync(Path.Combine(directory.Path, captureId + ".bmp"), WideCapture());
        string[] names = ["BAXY_VISION_ENDPOINT", "BAXY_VISION_MODEL", "BAXY_VISION_SLOT", "BAXY_VISION_SLOT_DIR"];
        string?[] saved = [.. names.Select(Environment.GetEnvironmentVariable)];
        var asked = new List<string>();
        using var http = new HttpClient(new LambdaHttpHandler((request, _) =>
        {
            asked.Add(request.RequestUri!.PathAndQuery);
            return Task.FromResult(request.RequestUri.AbsolutePath.StartsWith("/slots/", StringComparison.Ordinal)
                ? new HttpResponseMessage(HttpStatusCode.InternalServerError)
                : new HttpResponseMessage(HttpStatusCode.OK)
                {
                    Content = new StringContent("""{"choices":[{"message":{"content":"Una ventana."}}]}"""),
                });
        }));
        try
        {
            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", "http://127.0.0.1:8090/v1/chat/completions");
            Environment.SetEnvironmentVariable("BAXY_VISION_MODEL", "vision-test");
            Environment.SetEnvironmentVariable("BAXY_VISION_SLOT", "0");
            Environment.SetEnvironmentVariable("BAXY_VISION_SLOT_DIR", slots.Path);
            using var adapter = new CaptureVisionAdapter(directory.Path, http);
            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
                "vision.describe", Json($$"""{"captureId":"{{captureId}}"}"""), CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.True);
                Assert.That(asked, Is.EqualTo(new[] { "/slots/0?action=save", "/v1/chat/completions" }));
            });
        }
        finally
        {
            for (int index = 0; index < names.Length; index++)
                Environment.SetEnvironmentVariable(names[index], saved[index]);
        }
    }

    [Test]
    [NonParallelizable]
    public async Task ADescriptionPastTheVisionServersTimeIsAnHonestTimeoutNotAnException()
    {
        // P2.17 (noche 27-10): the shared server busy with the mind, the description outlasted its client; the timeout
        // escaped as an exception and the App waited the budget and its reconciliation (~150 s) for a bare provider error.
        using var directory = new TemporaryDirectory();
        string captureId = "capture_" + new string('b', 32);
        await File.WriteAllBytesAsync(Path.Combine(directory.Path, captureId + ".bmp"), WideCapture());
        string? endpoint = Environment.GetEnvironmentVariable("BAXY_VISION_ENDPOINT");
        string? model = Environment.GetEnvironmentVariable("BAXY_VISION_MODEL");
        try
        {
            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", "http://127.0.0.1:8090/v1/chat/completions");
            Environment.SetEnvironmentVariable("BAXY_VISION_MODEL", "vision-test");
            using var http = new HttpClient(new LambdaHttpHandler(async (_, token) =>
            {
                await Task.Delay(Timeout.Infinite, token);
                return new HttpResponseMessage(HttpStatusCode.OK);
            }))
            {
                Timeout = TimeSpan.FromMilliseconds(200),
            };
            using var adapter = new CaptureVisionAdapter(directory.Path, http);
            ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
                "vision.describe",
                Json($$"""{"captureId":"{{captureId}}"}"""),
                CancellationToken.None);

            // A capture the decoder cannot read fails with the adapter's code, not as a bare provider exception.
            await File.WriteAllBytesAsync(
                Path.Combine(directory.Path, captureId + ".bmp"), Enumerable.Repeat((byte)7, 64).ToArray());
            ExternalCapabilityReceipt undecodable = await adapter.InvokeAsync(
                "vision.describe",
                Json($$"""{"captureId":"{{captureId}}"}"""),
                CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(receipt.Verified, Is.False);
                Assert.That(receipt.ErrorCode, Is.EqualTo("vision_provider_timeout"));
                Assert.That(receipt.EffectObserved, Is.False);
                Assert.That(undecodable.ErrorCode, Is.EqualTo("capture_vision_adapter_failed"));
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", endpoint);
            Environment.SetEnvironmentVariable("BAXY_VISION_MODEL", model);
        }
    }

    // A screen-wide capture (2000 px), a real 32-bit BMP the vision request can decode and shrink.
    private static byte[] WideCapture()
    {
        const int width = 2000, height = 4;
        byte[] bmp = new byte[54 + (width * height * 4)];
        bmp[0] = (byte)'B';
        bmp[1] = (byte)'M';
        BitConverter.GetBytes(bmp.Length).CopyTo(bmp, 2);
        BitConverter.GetBytes(54).CopyTo(bmp, 10);
        BitConverter.GetBytes(40).CopyTo(bmp, 14);
        BitConverter.GetBytes(width).CopyTo(bmp, 18);
        BitConverter.GetBytes(height).CopyTo(bmp, 22);
        BitConverter.GetBytes((short)1).CopyTo(bmp, 26);
        BitConverter.GetBytes((short)32).CopyTo(bmp, 28);
        BitConverter.GetBytes(width * height * 4).CopyTo(bmp, 34);
        for (int index = 54; index < bmp.Length; index++)
            bmp[index] = (byte)(index % 251);
        return bmp;
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

    // Ajuste c4 (C3-061, 083, 097, 146): a tab step on a session whose browser ended sent nothing, so its receipt says
    // failed before any effect, not an uncertain one.
    [Test]
    public async Task BrowserControlOnABrowserThatEndedFailsBeforeAnyEffect()
    {
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserControlSession(
            temporary.Path,
            new(false, false, "close", "", "", "cdp_session_closed"));
        using var http = new HttpClient(new StubHttpHandler("<rss><channel></channel></rss>"));
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "browser.control",
            Json("""{"action":"close"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("cdp_session_closed"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
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

    [TestCase("https://bank@evil.example/")]
    [TestCase("https://bank:secret@evil.example/login")]
    [TestCase("javascript:alert(1)")]
    [TestCase("file:///C:/Windows/win.ini")]
    [TestCase("data:text/html,<b>hola</b>")]
    public async Task NamedBrowserRefusesWhatBrowserNavigateRefusesBeforeOpening(string url)
    {
        using TemporaryDirectory temporary = new();
        var context = new CdpBrowserSessionContext();
        var opera = new StubBrowserChainSession(
            temporary.Path,
            new(true, true, url, url, "opera-page", ""),
            new(true, "opera-page", url, "Page", "text", false, ""),
            observedExecutablePath: Path.Combine(temporary.Path, "opera.exe"));
        using var named = new NamedBrowserAdapter(temporary.Path, context, opera, userBrowser: null);

        ExternalCapabilityReceipt receipt = await named.InvokeAsync(
            "browser.navigate.named",
            ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteString("browser", "opera");
                writer.WriteString("url", url);
                writer.WriteEndObject();
            }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("named_browser_url_invalid"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(opera.NavigateCalls, Is.Zero);
        });
    }

    // Ronda q-web: a page evaluation that threw (exceptionDetails), a CDP error, or a value of another type escaped as
    // KeyNotFoundException or InvalidOperationException, out of the adapter; it is cdp_evaluation_failed.
    [TestCase("""{"id":1,"result":{"result":{"type":"object","subtype":"error","description":"ReferenceError"},"exceptionDetails":{"text":"Uncaught"}}}""")]
    [TestCase("""{"id":1,"error":{"code":-32000,"message":"Cannot find context with specified id"}}""")]
    [TestCase("""{"id":1,"result":{"result":{"type":"undefined"}}}""")]
    [TestCase("""{"id":1,"result":{"result":{"type":"number","value":3}}}""")]
    public void AnEvaluationWithoutAStringIsACdpEvaluationFailure(string response)
    {
        using JsonDocument document = JsonDocument.Parse(response);

        CdpCommandException failure = Assert.Throws<CdpCommandException>(
            () => CdpBrowserSession.EvaluatedString(document.RootElement))!;

        Assert.That(failure.Code, Is.EqualTo("cdp_evaluation_failed"));
    }

    [TestCase("""{"id":1,"result":{"result":{"type":"string","value":"8"}}}""")]
    [TestCase("""{"id":1,"result":{"result":{"type":"undefined"}}}""")]
    [TestCase("""{"id":1,"result":{"result":{"type":"number","value":1},"exceptionDetails":{"text":"Uncaught"}}}""")]
    public void AnEvaluationWithoutANumberIsACdpEvaluationFailure(string response)
    {
        using JsonDocument document = JsonDocument.Parse(response);

        CdpCommandException failure = Assert.Throws<CdpCommandException>(
            () => CdpBrowserSession.EvaluatedNumber(document.RootElement))!;

        Assert.That(failure.Code, Is.EqualTo("cdp_evaluation_failed"));
    }

    [Test]
    public void AnEvaluationReturnsItsValue()
    {
        using JsonDocument text = JsonDocument.Parse("""{"id":1,"result":{"result":{"type":"string","value":"https://example.com/"}}}""");
        using JsonDocument none = JsonDocument.Parse("""{"id":1,"result":{"result":{"type":"object","subtype":"null","value":null}}}""");
        using JsonDocument number = JsonDocument.Parse("""{"id":1,"result":{"result":{"type":"number","value":120.5}}}""");

        Assert.Multiple(() =>
        {
            Assert.That(CdpBrowserSession.EvaluatedString(text.RootElement), Is.EqualTo("https://example.com/"));
            Assert.That(CdpBrowserSession.EvaluatedString(none.RootElement), Is.Empty);
            Assert.That(CdpBrowserSession.EvaluatedNumber(number.RootElement), Is.EqualTo(120.5));
        });
    }

    [Test]
    public void ACdpCommandWithoutAnswerEndsAtItsOwnTimeoutAndClosesTheSocket()
    {
        // Ronda q-web: an alert() on the page holds Runtime.evaluate; the command waited on the turn's token alone.
        using var socket = new SilentWebSocket();

        CdpCommandException failure = Assert.ThrowsAsync<CdpCommandException>(async () =>
            await CdpBrowserSession.SendCommandAsync(
                socket, 7, "Runtime.evaluate", null, TimeSpan.FromMilliseconds(200), CancellationToken.None))!;

        Assert.Multiple(() =>
        {
            Assert.That(failure.Code, Is.EqualTo("cdp_command_timeout"));
            Assert.That(socket.Sent, Is.EqualTo(1));
            Assert.That(socket.Aborted, Is.True);
        });
    }

    [Test]
    public void ATurnCancelledDuringACdpCommandStaysACancellation()
    {
        using var socket = new SilentWebSocket();
        using var turn = new CancellationTokenSource(TimeSpan.FromMilliseconds(100));

        Assert.That(async () => await CdpBrowserSession.SendCommandAsync(
                socket, 7, "Runtime.evaluate", null, TimeSpan.FromSeconds(30), turn.Token),
            Throws.InstanceOf<OperationCanceledException>());
    }

    [Test]
    public async Task AFailedPageEvaluationIsToldByItsCodeNotAsAnEscapedException()
    {
        using TemporaryDirectory temporary = new();
        using var edge = new ThrowingPageSession(
            temporary.Path, new CdpCommandException("cdp_evaluation_failed", "Runtime.evaluate threw."));
        using var http = new HttpClient(new StubHttpHandler("<rss><channel></channel></rss>"));
        using var web = new WebBrowserAdapter(edge, http, new CdpBrowserSessionContext());

        ExternalCapabilityReceipt page = await web.InvokeAsync(
            "browser.page.read", Json("""{"maximumCharacters":2000}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(page.Verified, Is.False);
            Assert.That(page.ErrorCode, Is.EqualTo("cdp_evaluation_failed"));
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
            // Feria 2026-10-27 (caso 19): the receipt says where it plays, here the product's own browser.
            Assert.That(receipt.Result?.GetProperty("browser").GetString(), Is.EqualTo("product"));
        });
    }

    // Caso 19: a playback in the product's browser that was not verified still says where the page was opened.
    [Test]
    public async Task AnUnverifiedYouTubePlaybackSaysWhereItsPageWasOpened()
    {
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserPlaybackSession(
            temporary.Path,
            new(false, true, "gatos", string.Empty, string.Empty, "page-9", "youtube_playback_not_verified_video_missing"));
        using var http = new HttpClient(new StubHttpHandler(
            "{\"videoRenderer\":{\"videoId\":\"abcdefghijk\"}}"));
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.youtube", Json("""{"query":"gatos"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo("youtube_playback_not_verified_video_missing"));
            Assert.That(receipt.Result?.GetProperty("browser").GetString(), Is.EqualTo("product"));
            Assert.That(receipt.Result?.GetProperty("openedUrl").GetString(), Does.EndWith("/watch?v=abcdefghijk"));
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
                ["Merlina", "Wednesday Addams: la serie", "Faro Norte: T1:E3 Wednesday"]));
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
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result?.GetProperty("candidates").GetArrayLength(), Is.EqualTo(3));
            Assert.That(receipt.Result?.GetProperty("candidates")[0].GetProperty("title").GetString(),
                Is.EqualTo("Merlina"));
            Assert.That(receipt.Result?.GetProperty("candidates")[1].TryGetProperty("kind", out _), Is.False);
            // Uso real 02-11: an episode of another series holding the title is said as an episode.
            Assert.That(receipt.Result?.GetProperty("candidates")[2].GetProperty("kind").GetString(),
                Is.EqualTo("episode"));
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

    // FT/proveedores goal (review of receipts): a cancel at a clock time with no kind (most the model writes) looks
    // among alarms and reminders: the one alarm at that time is canceled (before, only reminders were looked at).
    [Test]
    public async Task AClockCancelWithNoKindFindsTheAlarmAtThatTime()
    {
        using TemporaryDirectory temporary = new();
        const string taskName = "BAXY-Alarm-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
        string due = DateTimeOffset.UtcNow.AddHours(2).ToString("O");
        var backend = ScriptedNotificationBackend.Lines([
            $$"""{"ok":true,"effectObserved":false,"matchCount":1,"taskName":"{{taskName}}","nextRunUtc":"{{due}}"}""",
            "{\"ok\":false,\"effectObserved\":false,\"effectBoundaryCrossed\":false,\"matchCount\":0}",
            $$"""{"ok":true,"effectObserved":true,"effectBoundaryCrossed":true,"canceled":true,"taskName":"{{taskName}}","nextRunUtc":"{{due}}","authority":"windows_task_scheduler_exact_identity_absence_postread"}""",
        ]);
        var adapter = new WindowsScheduledNotificationAdapter(temporary.Path, backend);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms", Json("""{"action":"cancel","at":"17:00"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("kind").GetString(), Is.EqualTo("alarm"));
            Assert.That(receipt.Result?.GetProperty("taskName").GetString(), Is.EqualTo(taskName));
            Assert.That(backend.Requests.Select(static request => $"{request.Mode}:{request.Kind}"),
                Is.EqualTo(new[] { "resolve-at:alarm", "resolve-at:reminder", "cancel-exact:alarm" }));
        });
    }

    // One alarm and one reminder at that time, and no kind: ambiguous, nothing canceled.
    [Test]
    public async Task AClockCancelWithNoKindAndOneOfEachIsAmbiguous()
    {
        using TemporaryDirectory temporary = new();
        string due = DateTimeOffset.UtcNow.AddHours(2).ToString("O");
        var backend = new ScriptedNotificationBackend(request => new ExternalProcessResult(0,
            $$"""{"ok":true,"effectObserved":false,"matchCount":1,"taskName":"BAXY-{{(request.Kind == "alarm" ? "Alarm" : "Reminder")}}-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","nextRunUtc":"{{due}}"}""",
            string.Empty));
        var adapter = new WindowsScheduledNotificationAdapter(temporary.Path, backend);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "schedule.alarms", Json("""{"action":"cancel","at":"17:00"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("notification_clock_ambiguous"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(backend.Requests.Select(static request => request.Mode), Is.All.EqualTo("resolve-at"));
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
        string output = $$"""{"ok":true,"schedulerRunning":true,"tasks":[{"taskName":"{{own}}","state":"Ready","nextRunUtc":"{{next}}"},{"taskName":"{{other}}","state":"Ready","nextRunUtc":"{{next}}"}]}""";
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
            "\"StateFlags\" \"4\" \"installdir\" \"Fall Guys\" }");
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

    // Ronda final 32 (regla 3): an install still queued or downloading (Steam without FullyInstalled, Epic with
    // bIsIncompleteInstall) already has its folder, and is never said installed.
    [Test]
    public async Task AnInstallNotFinishedIsNeverSaidInstalled()
    {
        using TemporaryDirectory temporary = new();
        string steamApps = Path.Combine(temporary.Path, "steamapps");
        string epicManifests = Path.Combine(temporary.Path, "epic-manifests");
        string epicInstall = Path.Combine(temporary.Path, "Fall Guys Epic");
        Directory.CreateDirectory(Path.Combine(steamApps, "common", "Hollow Knight"));
        Directory.CreateDirectory(epicManifests);
        Directory.CreateDirectory(epicInstall);
        await File.WriteAllTextAsync(
            Path.Combine(steamApps, "appmanifest_367520.acf"),
            "\"AppState\" { \"appid\" \"367520\" \"name\" \"Hollow Knight\" " +
            "\"StateFlags\" \"1026\" \"installdir\" \"Hollow Knight\" }");
        await File.WriteAllTextAsync(
            Path.Combine(epicManifests, "fallguys.item"),
            JsonSerializer.Serialize(new
            {
                DisplayName = "Fall Guys",
                InstallLocation = epicInstall,
                CatalogItemId = "fallguys-catalog-id",
                bIsIncompleteInstall = true,
            }));
        var adapter = new WindowsGameInstallationAdapter([steamApps], [epicManifests]);

        ExternalCapabilityReceipt steam = await adapter.InvokeAsync(
            "game.installed.named", Json("""{"provider":"steam","title":"Hollow Knight"}"""), CancellationToken.None);
        ExternalCapabilityReceipt epic = await adapter.InvokeAsync(
            "game.installed.named", Json("""{"provider":"epic","title":"Fall Guys"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(steam.Result?.TryGetProperty("installed", out _), Is.False);
            Assert.That(steam.Result?.GetProperty("state").GetString(), Is.EqualTo("install_not_finished"));
            Assert.That(steam.Result?.GetProperty("games")[0].GetProperty("installFinished").GetBoolean(), Is.False);
            Assert.That(epic.Result?.TryGetProperty("installed", out _), Is.False);
            Assert.That(epic.Result?.GetProperty("state").GetString(), Is.EqualTo("install_not_finished"));
        });
    }

    // Renew al máximo (w8): a corrupt Epic manifest (or one its store is rewriting) failed the whole check, Steam's
    // games included. It is left aside and counted: the Steam game is still found; a name not found is not said absent.
    [Test]
    public async Task OneUnreadableManifestLeavesTheOthersRead()
    {
        using TemporaryDirectory temporary = new();
        string steamApps = Path.Combine(temporary.Path, "steamapps");
        string epicManifests = Path.Combine(temporary.Path, "epic");
        Directory.CreateDirectory(Path.Combine(steamApps, "common", "Hollow Knight"));
        Directory.CreateDirectory(epicManifests);
        await File.WriteAllTextAsync(
            Path.Combine(steamApps, "appmanifest_367520.acf"),
            "\"AppState\" { \"appid\" \"367520\" \"name\" \"Hollow Knight\" " +
            "\"StateFlags\" \"4\" \"installdir\" \"Hollow Knight\" }");
        await File.WriteAllTextAsync(Path.Combine(epicManifests, "broken.item"), "{ \"DisplayName\": ");
        var adapter = new WindowsGameInstallationAdapter([steamApps], [epicManifests]);

        ExternalCapabilityReceipt found = await adapter.InvokeAsync(
            "game.installed.named", Json("""{"provider":"any","title":"Hollow Knight"}"""), CancellationToken.None);
        ExternalCapabilityReceipt other = await adapter.InvokeAsync(
            "game.installed.named", Json("""{"provider":"any","title":"Fall Guys"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(found.ErrorCode, Is.Null);
            Assert.That(found.Result?.GetProperty("installed").GetBoolean(), Is.True);
            Assert.That(found.Result?.GetProperty("manifestsUnread").GetInt32(), Is.EqualTo(1));
            Assert.That(other.ErrorCode, Is.Null);
            Assert.That(other.Result?.GetProperty("state").GetString(), Is.EqualTo("install_state_not_read"));
        });
    }

    // Renew al máximo (w8): «¿tengo instalado assassins creed origins?» against the manifest «Assassin's Creed Origins»:
    // the apostrophe folded to a space and the game was said not installed.
    [Test]
    public async Task AnInstalledTitleWithAnApostropheIsFoundAsItIsSaid()
    {
        using TemporaryDirectory temporary = new();
        string steamApps = Path.Combine(temporary.Path, "steamapps");
        Directory.CreateDirectory(Path.Combine(steamApps, "common", "ACOrigins"));
        await File.WriteAllTextAsync(
            Path.Combine(steamApps, "appmanifest_582160.acf"),
            "\"AppState\" { \"appid\" \"582160\" \"name\" \"Assassin's Creed Origins\" " +
            "\"StateFlags\" \"4\" \"installdir\" \"ACOrigins\" }");
        var adapter = new WindowsGameInstallationAdapter([steamApps], []);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.installed.named", Json("""{"provider":"any","title":"assassins creed origins"}"""), CancellationToken.None);

        Assert.That(receipt.Result?.GetProperty("installed").GetBoolean(), Is.True);
    }

    // Renew al máximo (auditoría de flujos, decision2): a name no manifest bears exactly names the closest ones read.
    [Test]
    public async Task ANameNoManifestBearsNamesTheClosestOnes()
    {
        using TemporaryDirectory temporary = new();
        string steamApps = Path.Combine(temporary.Path, "steamapps");
        Directory.CreateDirectory(Path.Combine(steamApps, "common", "WormsWMD"));
        await File.WriteAllTextAsync(
            Path.Combine(steamApps, "appmanifest_327030.acf"),
            "\"AppState\" { \"appid\" \"327030\" \"name\" \"Worms W.M.D\" " +
            "\"StateFlags\" \"4\" \"installdir\" \"WormsWMD\" }");
        var adapter = new WindowsGameInstallationAdapter([steamApps], []);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.installed.named", Json("""{"provider":"any","title":"worms"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result?.GetProperty("state").GetString(),
                Is.EqualTo("no_steam_or_epic_manifest_with_that_name"));
            Assert.That(receipt.Result?.GetProperty("closestTitles")[0].GetString(), Is.EqualTo("Worms W.M.D"));
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

    // Renew al máximo (8.3): an emptying whose receipt was lost (the process ended with nothing read) left the model not
    // knowing whether the bin was emptied; one read of the bins after it says what is there, the failure kept.
    [TestCase(0L, true)]
    [TestCase(3L, false)]
    public async Task RecycleBinEmptyWithItsReceiptLostSaysWhatTheBinHoldsAfter(long items, bool reached)
    {
        var adapter = new WindowsRecycleBinAdapter(
            new ThrowingProcessRunner(new IOException("simulated receipt loss after process dispatch")), () => items);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.recyclebin.empty", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo("recycle_bin_empty_failed"));
            JsonElement? state = receipt.Result?.GetProperty("stateAfter");
            Assert.That(state?.GetProperty("itemCount").GetInt64(), Is.EqualTo(items));
            Assert.That(state?.GetProperty("requestedStateReached").GetBoolean(), Is.EqualTo(reached));
            Assert.That(state?.GetProperty("authority").GetString(), Is.EqualTo("windows_recycle_bin_query_postread"));
        });
    }

    // Renew al máximo (8.3): the script's own post-read found items still there; that count is the state after, never
    // dropped, and no second read is made.
    [Test]
    public async Task RecycleBinEmptyWhosePostreadStillFoundItemsSaysHowMany()
    {
        int reads = 0;
        var adapter = new WindowsRecycleBinAdapter(
            new StubProcessRunner("{\"ok\":false,\"beforeCount\":3,\"afterCount\":2,\"effectObserved\":true}"),
            () => { reads++; return 0; });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.recyclebin.empty", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("recycle_bin_empty_postread_failed"));
            JsonElement? state = receipt.Result?.GetProperty("stateAfter");
            Assert.That(state?.GetProperty("itemCount").GetInt64(), Is.EqualTo(2));
            Assert.That(state?.GetProperty("requestedStateReached").GetBoolean(), Is.False);
            Assert.That(state?.GetProperty("authority").GetString(), Is.EqualTo("windows_recycle_bin_empty_postread"));
            Assert.That(reads, Is.Zero);
        });
    }

    // Renew al máximo (8.3): a read of the bins that fails adds nothing: the ambiguous failure stays as it was.
    [Test]
    public async Task RecycleBinEmptyWhoseRereadFailsAddsNoState()
    {
        var adapter = new WindowsRecycleBinAdapter(
            new ThrowingProcessRunner(new TimeoutException("simulated")), () => -1);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.recyclebin.empty", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo("recycle_bin_empty_failed"));
            Assert.That(receipt.Result, Is.Null);
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
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_opened_window_not_shown"));
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
    // On the click's own clock: the five fronts asked 20 ms apart are well inside the 400 ms the launch settles in,
    // however slowly a loaded machine runs them (on the wall clock the fourth one, late, looked at the blank page).
    [Test]
    public async Task VisibleClickAfterALaunchDoesNotLookWhileThePageIsBlank()
    {
        var time = new VirtualTime();
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var focus = new ScriptedFocus(launched: true, windowAfter: 1, drawnAfter: 4, time: time);
        var ocr = new CountingLocator("ocr", hit: true);
        var adapter = new WindowsVisibleControlAdapter(
            worker, ocr, vision: null, focus, ShortTiming, time: time);

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
            worker, ocr, vision: null, focus, ShortTiming)
        {
            WindowInFront = ComputerUsePerceptionTests.TestFront,
        };

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
        var adapter = new WindowsVisibleControlAdapter(worker, ocr, vision: null)
        {
            WindowInFront = ComputerUsePerceptionTests.TestFront,
        };
        var clock = Stopwatch.StartNew();

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"crash bandicoot"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_not_found"));
            // Looks every Interval (1.5 s) until SettledLabel (3 s) from the first: the third look lands on that edge,
            // so a fourth one comes when the timer returns a few milliseconds short (int6 Providers whole, 2026-10-22:
            // 4 under load, 3 alone). The bound that matters for M132 is the time, below.
            Assert.That(worker.Commands.Count, Is.InRange(2, 4));
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
            surfaceHash: (_, _) => { samples++; return ValueTask.FromResult<string?>("same"); })
        {
            WindowInFront = ComputerUsePerceptionTests.TestFront,
        };
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

    // e2e c3-final4/5 dv6 (a label not in Configuración, 2.0 s): the look's own press probed the window and found it
    // still; when the window still shows that same image after a look that pressed nothing, it has been still since
    // that probe, and «not found» comes at the first image of the watch. Another image is watched from zero, as before.
    [TestCase("same", true)]
    [TestCase("other", false)]
    public async Task VisibleClickOnAWindowItsLookFoundStillCountsFromThatProbe(string shownAfter, bool fromProbe)
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        int samples = 0;
        var adapter = new WindowsVisibleControlAdapter(
            worker, new CountingLocator("ocr", hit: false), vision: null, timing: StillTiming,
            surfaceHash: (_, _) => { samples++; return ValueTask.FromResult<string?>(shownAfter); },
            capture: (window, _, _) => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(
                new VisibleControlSurface.CapturedWindow(window, [], 0, 0, 10, 10, "same")))
        {
            WindowInFront = ComputerUsePerceptionTests.TestFront,
        };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"crash bandicoot"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_button_not_found"));
            Assert.That(worker.Commands.Count, Is.EqualTo(1));
            Assert.That(samples, fromProbe ? Is.EqualTo(1) : Is.GreaterThanOrEqualTo(2));
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
            surfaceHash: (_, _) => ValueTask.FromResult<string?>("frame" + samples++))
        {
            WindowInFront = ComputerUsePerceptionTests.TestFront,
        };

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
            surfaceHash: (_, _) => ValueTask.FromResult<string?>(null))
        {
            WindowInFront = ComputerUsePerceptionTests.TestFront,
        };
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
    // On the click's own clock: a look that takes longer than the label's budget on a loaded machine, or a still
    // watch whose samples come late, does not change how many looks the wait makes.
    [Test]
    public async Task VisibleClickAfterAScreenChangeKeepsTheFullWait()
    {
        var worker = new ComputerUsePerceptionTests.ScriptedUiaWorker(NotFoundByUia);
        var adapter = new WindowsVisibleControlAdapter(
            worker, new CountingLocator("ocr", hit: true, hitFromCall: 1) { HitsUpTo = 1 }, vision: null,
            timing: StillTiming, surfaceHash: (_, _) => ValueTask.FromResult<string?>("same"), time: new VirtualTime());

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

    // Revisión de calidad (archivos): the working folder's backups are the filesystem provider's own; a move by name put
    // a file and a recorded hash there as backup_<id>.bin and .sha256, which the provider then lists as a verified backup.
    [Test]
    public async Task ANamedSandboxMoveNeverReachesTheBackups()
    {
        using TemporaryDirectory temporary = new();
        string sandbox = Path.Combine(temporary.Path, "filesystem-sandbox");
        Directory.CreateDirectory(Path.Combine(sandbox, ".backups"));
        await File.WriteAllTextAsync(Path.Combine(sandbox, "falso.txt"), "payload");
        var adapter = new WindowsSandboxNamedFileAdapter(temporary.Path);
        string id = "backup_" + new string('a', 32);

        ExternalCapabilityReceipt moved = await adapter.InvokeAsync(
            "filesystem.sandbox.move.named",
            Json($$"""{"sourceFileName":"falso.txt","destinationRelativePath":".backups/{{id}}.bin"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt copied = await adapter.InvokeAsync(
            "filesystem.sandbox.move.named",
            Json("""{"sourceFileName":"falso.txt","destinationRelativePath":"logs/../.Backups/sub/x.bin","copy":true}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(moved.ErrorCode, Is.EqualTo("sandbox_move_destination_invalid"));
            Assert.That(copied.ErrorCode, Is.EqualTo("sandbox_move_destination_invalid"));
            Assert.That(moved.EffectMayHaveOccurred || copied.EffectMayHaveOccurred, Is.False);
            Assert.That(Directory.EnumerateFileSystemEntries(Path.Combine(sandbox, ".backups")), Is.Empty);
            Assert.That(File.ReadAllText(Path.Combine(sandbox, "falso.txt")), Is.EqualTo("payload"));
        });
    }

    // Holdout v5 V5E032/V5E040: moving a file of the person's by its name (BAXY-bench\presupuesto_v2.xlsx to archivo-2025)
    // or copying it (contrato.txt as contrato-respaldo.txt) had no call: the move by name reached only BAXY's working
    // folder. With folder (and subdirectory) it acts inside that folder: never over a file, never into a folder it would
    // have to make, never outside it.
    [Test]
    public async Task ANamedFileOfThePersonsIsMovedOrCopiedInsideTheFolderNamed()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "perfil");
        string bench = Path.Combine(home, "BAXY-bench");
        Directory.CreateDirectory(Path.Combine(bench, "archivo-2025"));
        await File.WriteAllTextAsync(Path.Combine(bench, "presupuesto_v2.xlsx"), "hoja");
        await File.WriteAllTextAsync(Path.Combine(bench, "contrato.txt"), "texto");
        var adapter = new WindowsSandboxNamedFileAdapter(temporary.Path, folder => folder == "home" ? home : null, []);
        Task<ExternalCapabilityReceipt> Run(string arguments) => adapter.InvokeAsync(
            "filesystem.sandbox.move.named", Json(arguments), CancellationToken.None).AsTask();

        // A folder alone as the destination is that folder, with the file's own name.
        ExternalCapabilityReceipt moved = await Run("""
            {"path":"BAXY-bench","sourceFileName":"presupuesto_v2.xlsx","destinationRelativePath":"archivo-2025"}
            """);
        ExternalCapabilityReceipt copied = await Run("""
            {"copy":true,"path":"BAXY-bench","sourceFileName":"contrato.txt","destinationRelativePath":"contrato-respaldo.txt"}
            """);
        ExternalCapabilityReceipt over = await Run("""
            {"copy":true,"path":"BAXY-bench","sourceFileName":"contrato.txt","destinationRelativePath":"contrato-respaldo.txt"}
            """);
        ExternalCapabilityReceipt unmade = await Run("""
            {"path":"BAXY-bench","sourceFileName":"contrato.txt","destinationRelativePath":"viejos/contrato.txt"}
            """);
        ExternalCapabilityReceipt outside = await Run("""
            {"path":"BAXY-bench","sourceFileName":"contrato.txt","destinationRelativePath":"../../fuera.txt"}
            """);
        // Holdout v5 V5E040 (int11): a destination that repeats the subfolder, with no such folder inside it, is inside it.
        ExternalCapabilityReceipt repeated = await Run("""
            {"copy":true,"path":"BAXY-bench","sourceFileName":"contrato.txt","destinationRelativePath":"BAXY-bench/contrato-copia.txt"}
            """);

        Assert.Multiple(() =>
        {
            Assert.That(moved.Verified, Is.True, moved.ErrorCode);
            Assert.That(File.ReadAllText(Path.Combine(bench, "archivo-2025", "presupuesto_v2.xlsx")), Is.EqualTo("hoja"));
            Assert.That(File.Exists(Path.Combine(bench, "presupuesto_v2.xlsx")), Is.False);
            Assert.That(moved.Result?.GetProperty("destinationRelativePath").GetString(),
                Is.EqualTo("archivo-2025/presupuesto_v2.xlsx"));
            Assert.That(moved.Result?.GetProperty("sourceAbsent").GetBoolean(), Is.True);
            Assert.That(copied.Verified, Is.True, copied.ErrorCode);
            Assert.That(File.ReadAllText(Path.Combine(bench, "contrato-respaldo.txt")), Is.EqualTo("texto"));
            Assert.That(copied.Result?.GetProperty("sourceKept").GetBoolean(), Is.True);
            Assert.That(over.ErrorCode, Is.EqualTo("named_file_destination_exists"));
            Assert.That(over.EffectMayHaveOccurred, Is.False);
            Assert.That(unmade.ErrorCode, Is.EqualTo("named_file_destination_folder_not_found"));
            Assert.That(outside.ErrorCode, Is.EqualTo("named_file_destination_invalid"));
            Assert.That(repeated.Verified, Is.True, repeated.ErrorCode);
            Assert.That(File.ReadAllText(Path.Combine(bench, "contrato-copia.txt")), Is.EqualTo("texto"));
            Assert.That(repeated.Result?.GetProperty("destinationRelativePath").GetString(),
                Is.EqualTo("contrato-copia.txt"));
            Assert.That(File.Exists(Path.Combine(bench, "contrato.txt")), Is.True);
            Assert.That(Directory.Exists(Path.Combine(bench, "viejos")), Is.False);
        });
    }

    // Holdout v6 (V6F010): a name said with its words otherwise separated («lista invitados» for lista_invitados.txt)
    // found no file to move, and the answer was that it did not exist. It is that file, in the person's folder and in
    // BAXY's working folder; a name spelled exactly is still the one meant first, and two that only have its words are
    // candidates: nothing is moved by choosing one.
    [Test]
    public async Task ANamedFileSaidWithOtherSeparatorsIsMovedAndTwoSuchAreAmbiguous()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "perfil");
        string sandbox = Path.Combine(temporary.Path, "filesystem-sandbox");
        Directory.CreateDirectory(Path.Combine(home, "archivo"));
        Directory.CreateDirectory(Path.Combine(home, "viejos"));
        Directory.CreateDirectory(sandbox);
        await File.WriteAllTextAsync(Path.Combine(home, "lista_invitados.txt"), "Ana");
        await File.WriteAllTextAsync(Path.Combine(home, "plan viaje.txt"), "exacto");
        await File.WriteAllTextAsync(Path.Combine(home, "viejos", "plan_viaje.txt"), "parecido");
        await File.WriteAllTextAsync(Path.Combine(home, "notas_reunion.txt"), "uno");
        await File.WriteAllTextAsync(Path.Combine(home, "viejos", "notas-reunion.txt"), "dos");
        await File.WriteAllTextAsync(Path.Combine(sandbox, "Informe_Final.md"), "uno\ndos\n");
        await File.WriteAllTextAsync(Path.Combine(sandbox, "informe-final.copia.md"), "uno\ntres\n");
        var adapter = new WindowsSandboxNamedFileAdapter(temporary.Path, folder => folder == "home" ? home : null, []);
        Task<ExternalCapabilityReceipt> Run(string operation, string arguments) => adapter.InvokeAsync(
            operation, Json(arguments), CancellationToken.None).AsTask();

        ExternalCapabilityReceipt moved = await Run("filesystem.sandbox.move.named",
            """{"path":"home","sourceFileName":"lista invitados.txt","destinationRelativePath":"archivo"}""");
        ExternalCapabilityReceipt copied = await Run("filesystem.sandbox.move.named",
            """{"path":"home","copy":true,"sourceFileName":"plan viaje.txt","destinationRelativePath":"archivo"}""");
        ExternalCapabilityReceipt two = await Run("filesystem.sandbox.move.named",
            """{"path":"home","sourceFileName":"notas reunion.txt","destinationRelativePath":"archivo"}""");
        ExternalCapabilityReceipt diff = await Run("filesystem.sandbox.diff.named",
            """{"leftFileName":"informe final.md","rightFileName":"informe final copia.md"}""");
        ExternalCapabilityReceipt work = await Run("filesystem.sandbox.move.named",
            """{"sourceFileName":"informe final.md","destinationRelativePath":"logs/informe.md"}""");

        Assert.Multiple(() =>
        {
            Assert.That(moved.Verified, Is.True, moved.ErrorCode);
            Assert.That(moved.Result?.GetProperty("sourceRelativePath").GetString(), Is.EqualTo("lista_invitados.txt"));
            Assert.That(File.ReadAllText(Path.Combine(home, "archivo", "lista_invitados.txt")), Is.EqualTo("Ana"));
            Assert.That(File.Exists(Path.Combine(home, "lista_invitados.txt")), Is.False);
            Assert.That(copied.Verified, Is.True, copied.ErrorCode);
            Assert.That(File.ReadAllText(Path.Combine(home, "archivo", "plan viaje.txt")), Is.EqualTo("exacto"));
            Assert.That(two.ErrorCode, Is.EqualTo("named_file_ambiguous"));
            Assert.That(two.EffectMayHaveOccurred, Is.False);
            Assert.That(two.Result?.GetProperty("candidates").EnumerateArray().Select(item => item.GetString()).Order(),
                Is.EqualTo(new[] { "notas_reunion.txt", "viejos/notas-reunion.txt" }));
            Assert.That(File.Exists(Path.Combine(home, "notas_reunion.txt")), Is.True);
            Assert.That(File.Exists(Path.Combine(home, "viejos", "notas-reunion.txt")), Is.True);
            Assert.That(diff.Verified, Is.True, diff.ErrorCode);
            Assert.That(diff.Result?.GetProperty("leftName").GetString(), Is.EqualTo("Informe_Final.md"));
            Assert.That(diff.Result?.GetProperty("rightName").GetString(), Is.EqualTo("informe-final.copia.md"));
            Assert.That(work.Verified, Is.True, work.ErrorCode);
            Assert.That(work.Result?.GetProperty("sourceFileName").GetString(), Is.EqualTo("Informe_Final.md"));
            Assert.That(File.Exists(Path.Combine(sandbox, "logs", "informe.md")), Is.True);
        });
    }

    // Revisión de nb-w11-revision: a walk the time limit stopped after one file of that name may have left another one
    // unseen; the one seen is not «the file of that name» to move (file.edit refuses the same, known_file_search_incomplete).
    [Test]
    public async Task ANamedFileOfThePersonsSeenByAWalkCutShortIsNotMoved()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "perfil");
        Directory.CreateDirectory(Path.Combine(home, "viejos"));
        Directory.CreateDirectory(Path.Combine(home, "destino"));
        await File.WriteAllTextAsync(Path.Combine(home, "contrato.txt"), "nuevo");
        await File.WriteAllTextAsync(Path.Combine(home, "viejos", "contrato.txt"), "viejo");
        // The walk's clock: the start and the first file within the limit, every later file past it.
        int read = 0;
        DateTime start = new(2026, 10, 25, 12, 0, 0, DateTimeKind.Utc);
        var adapter = new WindowsSandboxNamedFileAdapter(
            temporary.Path, folder => folder == "home" ? home : null, [], () => read++ < 2 ? start : start.AddHours(1));

        ExternalCapabilityReceipt moved = await adapter.InvokeAsync(
            "filesystem.sandbox.move.named",
            Json("""{"path":"home","sourceFileName":"contrato.txt","destinationRelativePath":"destino"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(moved.Verified, Is.False);
            Assert.That(moved.ErrorCode, Is.EqualTo("named_file_search_incomplete"));
            Assert.That(moved.EffectMayHaveOccurred, Is.False);
            Assert.That(File.Exists(Path.Combine(home, "contrato.txt")), Is.True);
            Assert.That(Directory.EnumerateFiles(Path.Combine(home, "destino")), Is.Empty);
        });
    }

    // Revisión de nb-w11-revision: «otro.txt:oculto» is no file of the folder but a hidden stream of the person's otro.txt;
    // a copy there writes inside a file of theirs that the explorer shows unchanged. It is refused before any effect.
    [TestCase("otro.txt:oculto")]
    [TestCase("destino/otro.txt:oculto")]
    public async Task ANamedFileOfThePersonsIsNeverCopiedIntoAStreamOfAnother(string destination)
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "perfil");
        Directory.CreateDirectory(Path.Combine(home, "destino"));
        await File.WriteAllTextAsync(Path.Combine(home, "contrato.txt"), "texto");
        await File.WriteAllTextAsync(Path.Combine(home, "otro.txt"), "suyo");
        await File.WriteAllTextAsync(Path.Combine(home, "destino", "otro.txt"), "suyo");
        var adapter = new WindowsSandboxNamedFileAdapter(temporary.Path, folder => folder == "home" ? home : null, []);

        ExternalCapabilityReceipt copied = await adapter.InvokeAsync(
            "filesystem.sandbox.move.named",
            Json("{\"copy\":true,\"path\":\"home\",\"sourceFileName\":\"contrato.txt\",\"destinationRelativePath\":\""
                + destination + "\"}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(copied.Verified, Is.False);
            Assert.That(copied.ErrorCode, Is.EqualTo("named_file_destination_invalid"));
            Assert.That(copied.EffectMayHaveOccurred, Is.False);
            Assert.That(File.Exists(Path.Combine(home, destination)), Is.False, "no stream was written");
        });
    }

    // Revisión de fase 3: a file of the person's is not moved nor copied into the Startup folder (Windows runs it at
    // sign-in), named by its path inside the folder, by its full path or as the subdirectory's own destination.
    [Test]
    public async Task ANamedFileIsNeverMovedOrCopiedWhereWindowsRunsItAtSignIn()
    {
        using TemporaryDirectory temporary = new();
        string home = Path.Combine(temporary.Path, "perfil");
        const string programs = "AppData/Roaming/Microsoft/Windows/Start Menu/Programs";
        string startup = Path.Combine(home, programs.Replace('/', Path.DirectorySeparatorChar), "Startup");
        Directory.CreateDirectory(startup);
        await File.WriteAllTextAsync(Path.Combine(home, "nota.cmd"), "calc");
        await File.WriteAllTextAsync(Path.Combine(Path.GetDirectoryName(startup)!, "otra.cmd"), "calc");
        var adapter = new WindowsSandboxNamedFileAdapter(temporary.Path, folder => folder == "home" ? home : null, [],
            autostartRoots: [startup]);
        Task<ExternalCapabilityReceipt> Run(object arguments) => adapter.InvokeAsync(
            "filesystem.sandbox.move.named", Json(JsonSerializer.Serialize(arguments)), CancellationToken.None).AsTask();

        ExternalCapabilityReceipt moved = await Run(new
        {
            path = "home", sourceFileName = "nota.cmd", destinationRelativePath = programs + "/Startup",
        });
        ExternalCapabilityReceipt copied = await Run(new
        {
            copy = true, path = "home", sourceFileName = "nota.cmd",
            destinationRelativePath = Path.Combine(startup, "x.cmd"),
        });
        ExternalCapabilityReceipt inside = await Run(new
        {
            copy = true, path = programs, sourceFileName = "otra.cmd",
            destinationRelativePath = "Startup/x.cmd",
        });

        Assert.Multiple(() =>
        {
            foreach (ExternalCapabilityReceipt receipt in (ExternalCapabilityReceipt[])[moved, copied, inside])
            {
                Assert.That(receipt.ErrorCode, Is.EqualTo("path_autostart"));
                Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            }
            Assert.That(Directory.EnumerateFileSystemEntries(startup), Is.Empty);
            Assert.That(File.ReadAllText(Path.Combine(home, "nota.cmd")), Is.EqualTo("calc"));
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
            Json("""{"path":"downloads"}"""),
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
                "\"folder\":\"downloads\",\"fileName\":\"report.pdf\",\"windowTitle\":\"report.pdf - Adobe Acrobat\"," +
                "\"authority\":\"known_folder_latest_safe_file_window_title_postread\"}"),
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

    // Ronda B: an empty clipboard stops the script before any key: its own cause, before the effect, never
    // «clipboard_paste_sendinput_failed» with an uncertain effect.
    [TestCase("{\"version\":1,\"ok\":false,\"effectObserved\":false,\"beforeInput\":true,\"error\":\"clipboard_empty\"}",
        "clipboard_empty", false)]
    [TestCase("{\"version\":1,\"ok\":false,\"effectObserved\":false,\"beforeInput\":false,\"error\":\"clipboard_paste_sendinput_failed\"}",
        "clipboard_paste_sendinput_failed", true)]
    public async Task ClipboardPasteStoppedBeforeAnyKeyKeepsItsCauseBeforeTheEffect(
        string output, string errorCode, bool mayHaveOccurred)
    {
        using TemporaryDirectory temporary = new();
        string folderScript = Path.Combine(temporary.Path, "KnownFolderOpen.ps1");
        string fileScript = Path.Combine(temporary.Path, "KnownFileOpen.ps1");
        string selectScript = Path.Combine(temporary.Path, "DesktopSelectAll.ps1");
        string keyScript = Path.Combine(temporary.Path, "DesktopKeyPress.ps1");
        foreach (string path in new[] { folderScript, fileScript, selectScript, keyScript })
            await File.WriteAllTextAsync(path, "# test fixture");
        var adapter = new WindowsDesktopInteractionAdapter(
            new CapturingProcessRunner(output), folderScript, fileScript, selectScript, keyScript);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "clipboard.paste", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(errorCode));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.EqualTo(mayHaveOccurred));
        });
    }

    // Every check the key script throws comes before any input: each one is in the list the script says was before it.
    [Test]
    public void EveryCauseTheKeyScriptThrowsIsToldAsBeforeInput()
    {
        string script = File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "DesktopKeyPress.ps1"));
        string[] thrown = System.Text.RegularExpressions.Regex.Matches(script, @"throw '([a-z_]+)'")
            .Select(static match => match.Groups[1].Value).ToArray();
        string list = script.Split('\n').Single(static line => line.Contains("$beforeInput=$cause -in", StringComparison.Ordinal));

        Assert.Multiple(() =>
        {
            Assert.That(thrown, Is.EquivalentTo(new[]
                { "foreground_window_missing", "sendinput_layout_invalid", "clipboard_empty", "on_screen_keyboard_missing" }));
            foreach (string cause in thrown)
                Assert.That(list, Does.Contain("'" + cause + "'"));
        });
    }

    // Renew al máximo (w5): clipboard.copy looks for the copy every 50 ms for 1 s, as input.key.press ctrl_c does (one
    // look after a fixed 120 ms failed a slower application's copy), and a Ctrl+C accepted in the same window that left
    // the clipboard as it was is said as clipboard_not_changed, not as an input not verified.
    [Test]
    public void TheCopyIsLookedForOftenAndACopyOfNothingIsSaidSo()
    {
        string script = File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "DesktopKeyPress.ps1"));
        int copyWait = script.IndexOf("$deadline=(Get-Date).AddMilliseconds(1000)", StringComparison.Ordinal);

        Assert.Multiple(() =>
        {
            Assert.That(copyWait, Is.GreaterThan(0));
            Assert.That(script, Does.Contain("do{Start-Sleep -Milliseconds 50}while($verified -and ([BaxyKeyInput]::GetClipboardSequenceNumber() -eq $clipboardSequenceBefore"));
            Assert.That(script, Does.Contain("} else { Start-Sleep -Milliseconds 120 }"), "the fixed wait is only for the other acts");
            Assert.That(script, Does.Contain("{'clipboard_not_changed'}else{'input_effect_not_verified'}"));
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

    // Banco de uso 03-11 (U27, «copia todo lo que dice el bloc de notas»): clipboard.copy with nothing selected failed as
    // clipboard_not_changed alone. The failure says the selection's length and the focused field's text length in the
    // window in front (lengths only, nothing of the text).
    [Test]
    public async Task ACopyOfNothingSaysTheSelectionAndTheFieldLengths()
    {
        using TemporaryDirectory temporary = new();
        string keyScript = Path.Combine(temporary.Path, "DesktopKeyPress.ps1");
        await File.WriteAllTextAsync(keyScript, "# test fixture");
        var runner = new CapturingProcessRunner(
            "{\"version\":1,\"ok\":false,\"effectObserved\":false,\"error\":\"clipboard_not_changed\"," +
            "\"acceptedEvents\":4,\"expectedEvents\":4}");
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            CaretAnswer = () => """{"ok":true,"processId":4242,"text":"lista de prueba","unit":"line","bounded":false,"selectionLength":0}""",
            ValueAnswer = () => """{"ok":true,"text":"lista de prueba","bounded":false,"id":"7"}""",
        };
        var adapter = new WindowsDesktopInteractionAdapter(
            runner, keyScript, keyScript, keyScript, keyScript, new FakeDesktopKeyboard(), fields);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("clipboard.copy", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("clipboard_not_changed"));
            Assert.That(receipt.Result?.GetProperty("selectionLength").GetInt32(), Is.Zero);
            Assert.That(receipt.Result?.GetProperty("focusedTextLength").GetInt32(), Is.EqualTo("lista de prueba".Length));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("lista de prueba"));
        });
    }

    // Encargo 17 (banco uso-cf8d, U27): Windows 11's Notepad's text area is a Document with no value, so the focused value
    // read gave no length and the failure said only the empty selection. The length of its text, read by its TextPattern
    // («focusvalue» with lengthOnly), is said instead; nothing of the text.
    [Test]
    public async Task ACopyOfNothingInADocumentWithNoValueSaysItsTextLength()
    {
        using TemporaryDirectory temporary = new();
        string keyScript = Path.Combine(temporary.Path, "DesktopKeyPress.ps1");
        await File.WriteAllTextAsync(keyScript, "# test fixture");
        var runner = new CapturingProcessRunner(
            "{\"version\":1,\"ok\":false,\"effectObserved\":false,\"error\":\"clipboard_not_changed\"," +
            "\"acceptedEvents\":4,\"expectedEvents\":4}");
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            CaretAnswer = () => """{"ok":true,"processId":4242,"text":"","unit":"line","bounded":false,"selectionLength":0}""",
            ValueAnswer = () => """{"ok":false,"error":"focus_not_a_field"}""",
            LengthAnswer = () => """{"ok":true,"kind":"Document","length":42,"bounded":false}""",
        };
        var adapter = new WindowsDesktopInteractionAdapter(
            runner, keyScript, keyScript, keyScript, keyScript, new FakeDesktopKeyboard(), fields);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("clipboard.copy", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("clipboard_not_changed"));
            Assert.That(receipt.Result?.GetProperty("selectionLength").GetInt32(), Is.Zero);
            Assert.That(receipt.Result?.GetProperty("focusedTextLength").GetInt32(), Is.EqualTo(42));
            Assert.That(receipt.Result?.TryGetProperty("focusedTextBounded", out _), Is.False);
            Assert.That(fields.LengthRequests, Has.Count.EqualTo(1));
        });
    }

    // Encargo 27 (banco uso-d4bd, U27): «copia todo lo que dice el bloc de notas» failed with focusedTextLength 7 for a
    // document of 35. A copy goes to the window in front, and a Notepad started by a process that is not in front does
    // not take it (SetForegroundWindow's rules; measured on two bench VMs: started from the bench's task it stayed behind
    // Program Manager, and the worker read the focus of the desktop). The lengths were of another window's focus, and
    // nothing said whose: the failure names the window the keys went to, as a paste and a typed text do (sentTo).
    [Test]
    public async Task ACopyOfNothingNamesTheWindowTheKeysWentTo()
    {
        using TemporaryDirectory temporary = new();
        string keyScript = Path.Combine(temporary.Path, "DesktopKeyPress.ps1");
        await File.WriteAllTextAsync(keyScript, "# test fixture");
        var runner = new CapturingProcessRunner(
            "{\"version\":1,\"ok\":false,\"effectObserved\":false,\"error\":\"clipboard_not_changed\"," +
            "\"acceptedEvents\":4,\"expectedEvents\":4,\"foregroundProcessIdBefore\":4242," +
            "\"foregroundProcessIdAfter\":4242,\"foregroundTitleBefore\":\"Documento - Editor\"}");
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            CaretAnswer = () => """{"ok":true,"processId":4242,"text":"","unit":"line","bounded":false,"selectionLength":0}""",
            ValueAnswer = () => """{"ok":false,"error":"focus_not_a_field"}""",
            LengthAnswer = () => """{"ok":true,"kind":"Document","length":7,"bounded":false}""",
        };
        var adapter = new WindowsDesktopInteractionAdapter(
            runner, keyScript, keyScript, keyScript, keyScript, new FakeDesktopKeyboard(), fields);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("clipboard.copy", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("clipboard_not_changed"));
            Assert.That(receipt.Result?.GetProperty("sentTo").GetProperty("title").GetString(),
                Is.EqualTo("Documento - Editor"));
            Assert.That(receipt.Result?.GetProperty("sentTo").GetProperty("process").GetString(), Is.EqualTo("Editor"));
            Assert.That(receipt.Result?.GetProperty("focusedTextLength").GetInt32(), Is.EqualTo(7));
        });
    }

    // Encargo 35 (bancos ab-d4-1d y uso-8ded, U27, 0 of 6): «copia todo lo que dice el bloc de notas» got selectionLength 0
    // and focusedTextLength 35 and answered «no había nada seleccionado», never selecting. With nothing selected and text
    // in the field, the failure's next leads with the call that selects it, then the copy (encargos 20, 28 and 34).
    [Test]
    public async Task ACopyOfNothingFromAFieldWithTextLeadsWithTheCallThatSelectsIt()
    {
        using TemporaryDirectory temporary = new();
        string keyScript = Path.Combine(temporary.Path, "DesktopKeyPress.ps1");
        await File.WriteAllTextAsync(keyScript, "# test fixture");
        var runner = new CapturingProcessRunner(
            "{\"version\":1,\"ok\":false,\"effectObserved\":false,\"error\":\"clipboard_not_changed\"," +
            "\"acceptedEvents\":4,\"expectedEvents\":4,\"foregroundProcessIdBefore\":4242," +
            "\"foregroundProcessIdAfter\":4242,\"foregroundTitleBefore\":\"Documento - Editor\"}");
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            CaretAnswer = () => """{"ok":true,"processId":4242,"text":"","unit":"line","bounded":false,"selectionLength":0}""",
            ValueAnswer = () => """{"ok":false,"error":"focus_not_a_field"}""",
            LengthAnswer = () => """{"ok":true,"kind":"Document","length":35,"bounded":false}""",
        };
        var adapter = new WindowsDesktopInteractionAdapter(
            runner, keyScript, keyScript, keyScript, keyScript, new FakeDesktopKeyboard(), fields);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("clipboard.copy", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("clipboard_not_changed"));
            Assert.That(receipt.Result?.GetProperty("next").GetString(), Is.EqualTo(
                "if the person asked for all of its text: input_select_all {} and then clipboard_copy {} copy all 35 "
                + "characters of the text in Documento - Editor; this call copied nothing: nothing was selected"));
        });
    }

    // Encargo 45 (banco ab-93-ce, U27, 0 of 2): with the route above the model asked «¿Quieres que seleccione todo y lo
    // copie?» although the person had asked to copy it all: the failure said its effect was uncertain. It is not: the
    // clipboard was read again unchanged and the window that took Ctrl+C, still in front, had nothing selected, where the
    // copy does nothing (WM_COPY copies the selection). The effect is known, so the failure is not ambiguous. A console is
    // apart: there Ctrl+C is an interrupt, an effect of its own; and a window that left the front was not read.
    [Test]
    public async Task ACopyOfNothingFromTheWindowInFrontIsAFailureWhoseEffectIsKnown()
    {
        using TemporaryDirectory temporary = new();
        string keyScript = Path.Combine(temporary.Path, "DesktopKeyPress.ps1");
        await File.WriteAllTextAsync(keyScript, "# test fixture");
        const string Copied = "{\"version\":1,\"ok\":false,\"effectObserved\":false,\"error\":\"clipboard_not_changed\","
            + "\"acceptedEvents\":4,\"expectedEvents\":4,\"foregroundProcessIdBefore\":4242,"
            + "\"foregroundProcessIdAfter\":4242,\"foregroundTitleBefore\":\"Documento - Editor\"}";
        FakeViewedFields Fields() => new("""{"ok":true}""")
        {
            CaretAnswer = () => """{"ok":true,"processId":4242,"text":"","unit":"line","bounded":false,"selectionLength":0}""",
            ValueAnswer = () => """{"ok":false,"error":"focus_not_a_field"}""",
            LengthAnswer = () => """{"ok":true,"kind":"Document","length":35,"bounded":false}""",
        };

        ExternalCapabilityReceipt field = await new WindowsDesktopInteractionAdapter(
                new CapturingProcessRunner(Copied), keyScript, keyScript, keyScript, keyScript, new FakeDesktopKeyboard(),
                Fields())
            .InvokeAsync("clipboard.copy", Json("{}"), CancellationToken.None);
        ExternalCapabilityReceipt console = await new WindowsDesktopInteractionAdapter(
                new CapturingProcessRunner(Copied), keyScript, keyScript, keyScript, keyScript,
                new FakeDesktopKeyboard { FrontClass = "ConsoleWindowClass" }, Fields())
            .InvokeAsync("clipboard.copy", Json("{}"), CancellationToken.None);
        ExternalCapabilityReceipt moved = await new WindowsDesktopInteractionAdapter(
                new CapturingProcessRunner(Copied.Replace("\"foregroundProcessIdBefore\":4242", "\"foregroundProcessIdBefore\":777",
                    StringComparison.Ordinal)),
                keyScript, keyScript, keyScript, keyScript, new FakeDesktopKeyboard(), Fields())
            .InvokeAsync("clipboard.copy", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(field.ErrorCode, Is.EqualTo("clipboard_not_changed"));
            Assert.That(field.EffectMayHaveOccurred, Is.False);
            Assert.That(console.ErrorCode, Is.EqualTo("clipboard_not_changed"));
            Assert.That(console.EffectMayHaveOccurred, Is.True);
            Assert.That(moved.EffectMayHaveOccurred, Is.True);
        });
    }

    // Encargo 94: the last resort's Ctrl+A raised a dialog (it is «Abrir» in a language): the receipt says so, closed or
    // not, with the state: nothing selected.
    [TestCase(true, "which was closed again")]
    [TestCase(false, "which is still open")]
    public async Task ADialogSelectAllRaisedIsSaidInItsReceipt(bool closed, string said)
    {
        using TemporaryDirectory temporary = new();
        string script = Path.Combine(temporary.Path, "DesktopSelectAll.ps1");
        await File.WriteAllTextAsync(script, "# test fixture");
        var runner = new CapturingProcessRunner(
            "{\"version\":1,\"ok\":false,\"effectObserved\":true,\"error\":\"select_all_opened_dialog\","
            + "\"dialogOpened\":{\"title\":\"Ventana Lumbre\",\"closed\":" + (closed ? "true" : "false") + "}}");

        ExternalCapabilityReceipt receipt = await new WindowsDesktopInteractionAdapter(
                runner, script, script, script, script, new FakeDesktopKeyboard())
            .InvokeAsync("input.select.all", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("select_all_opened_dialog"));
            Assert.That(receipt.Result?.GetProperty("dialogOpened").GetProperty("title").GetString(), Is.EqualTo("Ventana Lumbre"));
            Assert.That(receipt.Result?.GetProperty("next").GetString(),
                Does.Contain("selected nothing").And.Contain("Ventana Lumbre").And.Contain(said));
        });
    }

    // Encargo 61 (banco de uso U45, diag-f11d c2 and c4): in a console the failure offered select all and copy, a route that
    // fails there (select_all_postcondition_not_verified), and the model gave up with the command's output already read.
    // Both ways to Ctrl+C, the copy and the key: Windows Terminal sends it to the shell when nothing is selected.
    [TestCase("clipboard.copy", """{}""")]
    [TestCase("input.key.press", """{"key":"ctrl_c","window":4660}""")]
    public async Task ACopyOfNothingFromAConsoleSaysWhatWritesTheTextItShowed(string operation, string arguments)
    {
        using TemporaryDirectory temporary = new();
        string keyScript = Path.Combine(temporary.Path, "DesktopKeyPress.ps1");
        await File.WriteAllTextAsync(keyScript, "# test fixture");
        var runner = new CapturingProcessRunner(
            "{\"version\":1,\"ok\":false,\"effectObserved\":false,\"error\":\"clipboard_not_changed\","
            + "\"acceptedEvents\":4,\"expectedEvents\":4}");
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            CaretAnswer = () => """{"ok":true,"processId":4242,"text":"","unit":"line","bounded":false,"selectionLength":0}""",
            ValueAnswer = () => """{"ok":false,"error":"focus_not_a_field"}""",
            LengthAnswer = () => """{"ok":true,"kind":"Document","length":35,"bounded":false}""",
        };
        var keyboard = new FakeDesktopKeyboard
        {
            FrontClass = "CASCADIA_HOSTING_WINDOW_CLASS", Clipboard = 7, CopyChanges = false,
        };

        ExternalCapabilityReceipt receipt = await new WindowsDesktopInteractionAdapter(
                runner, keyScript, keyScript, keyScript, keyScript, keyboard, fields)
            .InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("clipboard_not_changed"));
            Assert.That(receipt.Result?.GetProperty("next").GetString(), Is.EqualTo(
                "file_write {\"path\":\"<the file>\",\"text\":\"<what it showed>\"} writes what input_visible_controls "
                + "with includeText read from this console; this call copied nothing: a console has no selection here "
                + "and its Ctrl+C is its interrupt"));
        });
    }

    // Encargo 35: a selection that was there (the copy failed for another reason) or a field with no text has nothing a
    // select-all would add: no next.
    [TestCase(3, 35)]
    [TestCase(0, 0)]
    public async Task ACopyWithASelectionOrNoTextHasNoSelectAllNext(int selection, int length)
    {
        using TemporaryDirectory temporary = new();
        string keyScript = Path.Combine(temporary.Path, "DesktopKeyPress.ps1");
        await File.WriteAllTextAsync(keyScript, "# test fixture");
        var runner = new CapturingProcessRunner(
            "{\"version\":1,\"ok\":false,\"effectObserved\":false,\"error\":\"clipboard_not_changed\"," +
            "\"acceptedEvents\":4,\"expectedEvents\":4,\"foregroundProcessIdBefore\":4242," +
            "\"foregroundProcessIdAfter\":4242,\"foregroundTitleBefore\":\"Documento - Editor\"}");
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            CaretAnswer = () => "{\"ok\":true,\"processId\":4242,\"text\":\"\",\"unit\":\"line\",\"bounded\":false," +
                "\"selectionLength\":" + selection + "}",
            ValueAnswer = () => """{"ok":false,"error":"focus_not_a_field"}""",
            LengthAnswer = () => "{\"ok\":true,\"kind\":\"Document\",\"length\":" + length + ",\"bounded\":false}",
        };
        var adapter = new WindowsDesktopInteractionAdapter(
            runner, keyScript, keyScript, keyScript, keyScript, new FakeDesktopKeyboard(), fields);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("clipboard.copy", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("clipboard_not_changed"));
            Assert.That(receipt.Result?.TryGetProperty("next", out _), Is.False);
        });
    }

    // Encargo 27: the lengths are read after the keys, in the window then in front. When that is no longer the window the
    // keys went to (the script read its process before them), they would be another window's: none is said, and the
    // window named is the one that took the keys.
    [Test]
    public async Task ACopyWhoseWindowLeftTheFrontSaysNoLengthOfAnotherWindow()
    {
        using TemporaryDirectory temporary = new();
        string keyScript = Path.Combine(temporary.Path, "DesktopKeyPress.ps1");
        await File.WriteAllTextAsync(keyScript, "# test fixture");
        int tookTheKeys = Environment.ProcessId;
        string program = System.Diagnostics.Process.GetCurrentProcess().ProcessName;
        var runner = new CapturingProcessRunner(
            "{\"version\":1,\"ok\":false,\"effectObserved\":false,\"error\":\"clipboard_not_changed\"," +
            "\"acceptedEvents\":4,\"expectedEvents\":4,\"foregroundProcessIdBefore\":" + tookTheKeys + "," +
            "\"foregroundProcessIdAfter\":" + tookTheKeys + ",\"foregroundTitleBefore\":\"Program Manager\"}");
        var fields = new FakeViewedFields("""{"ok":true}""")
        {
            CaretAnswer = () => """{"ok":true,"processId":4242,"text":"","unit":"line","bounded":false,"selectionLength":0}""",
            ValueAnswer = () => """{"ok":true,"text":"hola","bounded":false,"id":"7"}""",
            LengthAnswer = () => """{"ok":true,"kind":"Document","length":7,"bounded":false}""",
        };
        var adapter = new WindowsDesktopInteractionAdapter(
            runner, keyScript, keyScript, keyScript, keyScript, new FakeDesktopKeyboard(), fields);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("clipboard.copy", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("clipboard_not_changed"));
            Assert.That(receipt.Result?.GetProperty("sentTo").GetProperty("title").GetString(),
                Is.EqualTo("Program Manager"));
            Assert.That(receipt.Result?.GetProperty("sentTo").GetProperty("process").GetString(), Is.EqualTo(program));
            Assert.That(receipt.Result?.TryGetProperty("focusedTextLength", out _), Is.False);
            Assert.That(receipt.Result?.TryGetProperty("selectionLength", out _), Is.False);
            Assert.That(fields.LengthRequests, Is.Empty);
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

    // noche P1.1 (d): whether the microphone is muted is read, not found out by the call that changes it.
    [TestCase(true)]
    [TestCase(false)]
    public async Task MicrophoneStatusReadsTheCaptureEndpointWithoutChangingIt(bool muted)
    {
        var endpoint = new FakeAudioEndpoint("capture-private", muted: muted);
        var adapter = new WindowsMicrophoneAdapter(() => endpoint);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.microphone.status", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(adapter.CanHandle("audio.microphone.status"), Is.True);
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(receipt.Result?.GetProperty("muted").GetBoolean(), Is.EqualTo(muted));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("windows_core_audio_capture_endpoint_read"));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("capture-private"));
            Assert.That(endpoint.ReadMuted(), Is.EqualTo(muted));
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

    // BAXY Renew cu (C14, aid microphone_scope): the state already there, and a change, say they are Windows' switch of
    // the default microphone, not an application's own mute; with BAXY_AYUDAS=none the receipts are what they were.
    [TestCase("all", true)]
    [TestCase("none", false)]
    public async Task MicrophoneReceiptsSayTheyAreWindowsSwitchNotAnApplicationsMute(string aids, bool hint)
    {
        using IDisposable setting = ModelAids.Use(aids);
        var already = new WindowsMicrophoneAdapter(() => new FakeAudioEndpoint("capture-private", muted: false));
        var changed = new WindowsMicrophoneAdapter(() => new FakeAudioEndpoint("capture-private", muted: false));

        ExternalCapabilityReceipt same = await already.InvokeAsync(
            "audio.microphone.mute", Json("""{"state":false}"""), CancellationToken.None);
        ExternalCapabilityReceipt muted = await changed.InvokeAsync(
            "audio.microphone.mute", Json("""{"state":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(same.ErrorCode, Is.EqualTo("microphone_already_unmuted"));
            Assert.That(same.EffectMayHaveOccurred, Is.False);
            Assert.That(same.Result is { } result && result.TryGetProperty("next", out _), Is.EqualTo(hint));
            Assert.That(muted.Result?.TryGetProperty("next", out _), Is.EqualTo(hint));
            if (hint)
            {
                Assert.That(same.Result?.GetProperty("muted").GetBoolean(), Is.False);
                Assert.That(same.Result?.GetProperty("next").GetString(), Does.Contain("an application's own mute"));
            }
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

    // Renew al máximo (8.3): the output did not take the new level and the post-read that saw it was dropped; the level
    // and mute read after are the state, the failure kept.
    [Test]
    public async Task VolumeAdjustWhosePostreadMismatchedSaysTheLevelReadAfter()
    {
        var endpoint = new StuckAudioEndpoint("output-private", 0.40f);
        var adapter = new WindowsAudioAdjustmentAdapter(() => endpoint);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.volume.adjust", Json("""{"direction":"up","amount":10}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo("volume_adjustment_postread_mismatch"));
            JsonElement? state = receipt.Result?.GetProperty("stateAfter");
            Assert.That(state?.GetProperty("level").GetInt32(), Is.EqualTo(40));
            Assert.That(state?.GetProperty("muted").GetBoolean(), Is.False);
            Assert.That(state?.GetProperty("requestedLevel").GetInt32(), Is.EqualTo(50));
            Assert.That(state?.GetProperty("requestedStateReached").GetBoolean(), Is.False);
            Assert.That(state?.GetProperty("authority").GetString(),
                Is.EqualTo("windows_core_audio_output_endpoint_postread"));
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("output-private"));
        });
    }

    // Renew al máximo (8.3): the level was set and its post-read threw; one more read of the same output says the level
    // it has. Another output in its place (the default changed) is not that state, and adds nothing.
    [TestCase("post-dispatch-failure", true)]
    [TestCase("another-output", false)]
    public async Task VolumeAdjustWhosePostreadThrewReadsTheSameOutputOnceMore(string rereadEndpoint, bool added)
    {
        var opened = new Queue<IWindowsAudioEndpoint>(
        [
            new PostDispatchFailingAudioEndpoint(),
            new FakeAudioEndpoint(rereadEndpoint, muted: false, volume: 0.5f),
        ]);
        var adapter = new WindowsAudioAdjustmentAdapter(opened.Dequeue);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.volume.adjust", Json("""{"direction":"up","amount":10}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo("audio_output_endpoint_unavailable"));
            if (!added)
            {
                Assert.That(receipt.Result, Is.Null);
                return;
            }
            JsonElement? state = receipt.Result?.GetProperty("stateAfter");
            Assert.That(state?.GetProperty("level").GetInt32(), Is.EqualTo(50));
            Assert.That(state?.GetProperty("requestedLevel").GetInt32(), Is.EqualTo(50));
            Assert.That(state?.GetProperty("requestedStateReached").GetBoolean(), Is.True);
        });
    }

    // Renew al máximo (8.3): an application's level read after a set that did not take is the state after.
    [Test]
    public async Task AppVolumeSetWhosePostreadMismatchedSaysTheLevelReadAfter()
    {
        var adapter = new WindowsAppVolumeSetAdapter((_, _, beforeEffect, _) =>
        {
            beforeEffect?.Invoke();
            return new ApplicationSessionAdjustment("Spotify", 1, 30, 30, false, "endpoint-1", Changed: false);
        });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "audio.app.volume.set", Json("""{"app":"Spotify","level":60}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("volume_postread_mismatch"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            JsonElement? state = receipt.Result?.GetProperty("stateAfter");
            Assert.That(state?.GetProperty("level").GetInt32(), Is.EqualTo(30));
            Assert.That(state?.GetProperty("requestedLevel").GetInt32(), Is.EqualTo(60));
            Assert.That(state?.GetProperty("requestedStateReached").GetBoolean(), Is.False);
            Assert.That(state?.GetProperty("authority").GetString(), Is.EqualTo("windows_core_audio_session_postread"));
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
            // Renew al máximo (w8): the level the last read saw goes with the failure.
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.Result?.GetProperty("stateAfter").GetProperty("values")[0].GetInt32(), Is.EqualTo(30));
            Assert.That(receipt.Result?.GetProperty("stateAfter").GetProperty("requestedLevel").GetInt32(), Is.EqualTo(40));
        });
    }

    [TestCase("system.settings.set", """{"setting":"brightness","value":30}""", "changed")]
    [TestCase("system.settings.adjust", """{"setting":"brightness","direction":"down","amount":10}""", "changed")]
    [TestCase("system.settings.status", """{"setting":"brightness"}""", "read")]
    public async Task BrightnessOnAMonitorThatDoesNotExposeItIsTheComputersLimit(string operation, string arguments,
        string done)
    {
        // Encargo H2 (development PC, estado_antes «Brightness []»: WMI answers its brightness classes with «not supported»): the
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
            // Encargo 28 (U24): the page where Windows keeps the screen's settings comes first, written as its call.
            Assert.That(receipt.Result?.GetProperty("next").GetString(), Is.EqualTo(
                "app_open {\"appId\":\"Settings\",\"place\":\"display\"} opens the Display page of Settings; this call "
                + $"{done} nothing: no screen of this PC gives Windows its brightness"));
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

    // Ronda B: Do Not Disturb already at the asked value toggles nothing: the request already reached, not unobserved.
    [Test]
    public async Task DoNotDisturbAlreadyAtTheValueIsAlreadyReached()
    {
        using TemporaryDirectory temporary = new();
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path, temporary.Path,
            new StubProcessRunner("{\"ok\":true,\"effectObserved\":false,\"before\":1,\"value\":1}"));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "system.settings.set",
            Json("""{"setting":"do_not_disturb","value":1}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.StateAlreadyReached, Is.True);
            Assert.That(receipt.Result?.GetProperty("before").GetInt32(), Is.EqualTo(1));
        });
    }

    [Test]
    public async Task NamedWifiResolvesOneSavedProfileBeforeVerifiedConnect()
    {
        using TemporaryDirectory temporary = new();
        var delays = new RecordingDelay();
        var runner = new SequencedProcessRunner([
            "{\"ok\":true,\"profiles\":[\"Galaxy A34 5G C6CC\",\"Other\"]}",
            "{\"ok\":true,\"profiles\":[\"Galaxy A34 5G C6CC\",\"Other\"]}",
            "{\"ok\":true,\"connected\":false,\"profile\":\"\"}",
            "",
            "{\"ok\":true,\"connected\":true,\"profile\":\"Galaxy A34 5G C6CC\"}",
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
            Json("""{"profileName":"galaxy a34 5g c6cc"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(partial.Verified, Is.False);
            Assert.That(partial.ErrorCode, Is.EqualTo("wifi_profile_not_found"));
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("connected").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetRawText(), Does.Not.Contain("Galaxy"));
            Assert.That(runner.Calls, Is.EqualTo(5));
            Assert.That(delays.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task WifiAlreadyConnectedToTheProfileIsTheStateAlreadyReachedWithoutConnecting()
    {
        using TemporaryDirectory temporary = new();
        var delays = new RecordingDelay();
        var runner = new SequencedProcessRunner([
            "{\"ok\":true,\"profiles\":[\"Casa\"]}",
            "{\"ok\":true,\"connected\":true,\"profile\":\"Casa\"}",
        ]);
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path, temporary.Path, runner, delays.DelayAsync);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "wifi.connect.named",
            Json("""{"profileName":"Casa"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.StateAlreadyReached, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(runner.Calls, Is.EqualTo(2));
        });
    }

    [Test]
    public async Task WifiDisconnectVerifiesImmediatePostreadWithoutDelay()
    {
        using TemporaryDirectory temporary = new();
        var delays = new RecordingDelay();
        var runner = new SequencedProcessRunner([
            "{\"ok\":true,\"connected\":true,\"profile\":\"Casa\"}",
            "",
            "{\"ok\":true,\"connected\":false,\"profile\":\"\"}",
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
            Assert.That(runner.Calls, Is.EqualTo(3));
            Assert.That(delays.Calls, Is.Zero);
        });
    }

    // Round A: with the Wi-Fi already disconnected, «desconectá el wifi» ran netsh and answered an observed
    // disconnection. It is read first: the request is done, nothing changed, and netsh is not run.
    [Test]
    public async Task WifiDisconnectWhenAlreadyDisconnectedChangesNothingAndSaysSo()
    {
        using TemporaryDirectory temporary = new();
        var runner = new SequencedProcessRunner(["{\"ok\":true,\"connected\":false,\"profile\":\"\"}"]);
        var adapter = new WindowsDeviceControlAdapter(
            temporary.Path,
            temporary.Path,
            runner,
            new RecordingDelay().DelayAsync);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "wifi.disconnect",
            Json("{}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.StateAlreadyReached, Is.True);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result?.GetProperty("connected").GetBoolean(), Is.False);
            Assert.That(runner.Calls, Is.EqualTo(1), "only the read; no netsh wlan disconnect");
        });
    }

    [Test]
    public async Task WifiConnectFailureRetainsFifteenSecondRetryHorizon()
    {
        using TemporaryDirectory temporary = new();
        var delays = new RecordingDelay();
        var runner = new SequencedProcessRunner([
            "{\"ok\":true,\"profiles\":[\"Casa\"]}",
            "{\"ok\":true,\"connected\":false,\"profile\":\"\"}",
            "",
            "{\"ok\":true,\"connected\":false,\"profile\":\"\"}",
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
            Assert.That(runner.Calls, Is.EqualTo(34));
            AssertRetryHorizon(delays, expectedIntervals: 30, intervalMilliseconds: 500);
        });
    }

    [Test]
    public async Task WifiDisconnectFailureRetainsSixSecondRetryHorizon()
    {
        using TemporaryDirectory temporary = new();
        var delays = new RecordingDelay();
        var runner = new SequencedProcessRunner([
            "{\"ok\":true,\"connected\":true,\"profile\":\"Casa\"}",
            "",
            "{\"ok\":true,\"connected\":true,\"profile\":\"Casa\"}",
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
            Assert.That(runner.Calls, Is.EqualTo(23));
            AssertRetryHorizon(delays, expectedIntervals: 20, intervalMilliseconds: 300);
        });
    }

    [Test]
    public async Task EnsureWifiConnectedReturnsOnlyAnObservedCurrentSavedProfile()
    {
        using TemporaryDirectory temporary = new();
        var runner = new WifiProcessRunner(startsConnected: true);
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
            "{\"ok\":true,\"connected\":true,\"profile\":\"Private WiFi\"}",
            "{\"ok\":true,\"connected\":true,\"profile\":\"Private WiFi\"}",
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
            "{\"ok\":true,\"connected\":false,\"profile\":\"\"}",
            "{\"ok\":true,\"connected\":true,\"profile\":\"Private WiFi\"}",
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

    // Renew al máximo (w8): a Wi-Fi status netsh did not give says why (the WLAN service stopped, or not read), never the
    // adapter's generic failure; after a disconnection was sent, one unanswered look does not end the wait.
    [Test]
    public async Task AnUnreadWifiStatusSaysWhyAndOneUnansweredLookDoesNotEndTheWait()
    {
        using TemporaryDirectory temporary = new();
        var stopped = new WindowsDeviceControlAdapter(temporary.Path, temporary.Path, new SequencedProcessRunner([
            "{\"ok\":false,\"error\":\"wlan_service_not_running\"}",
        ]));
        var unread = new WindowsDeviceControlAdapter(temporary.Path, temporary.Path, new SequencedProcessRunner([
            "{\"ok\":false,\"error\":\"wifi_status_not_read\"}",
        ]));
        var none = new WindowsDeviceControlAdapter(temporary.Path, temporary.Path, new SequencedProcessRunner([
            "{\"ok\":false,\"error\":\"wifi_radio_not_found\"}",
        ]));
        var delay = new RecordingDelay();
        var disconnecting = new SequencedProcessRunner([
            "{\"ok\":true,\"connected\":true,\"profile\":\"Private WiFi\"}",
            "",
            "{\"ok\":false,\"error\":\"wifi_status_not_read\"}",
            "{\"ok\":true,\"connected\":false,\"profile\":\"\"}",
        ]);
        var disconnect = new WindowsDeviceControlAdapter(temporary.Path, temporary.Path, disconnecting, delay.DelayAsync);

        ExternalCapabilityReceipt stoppedReceipt = await stopped.InvokeAsync("wifi.status", Json("{}"), CancellationToken.None);
        ExternalCapabilityReceipt unreadReceipt = await unread.InvokeAsync("wifi.status", Json("{}"), CancellationToken.None);
        ExternalCapabilityReceipt noneReceipt = await none.InvokeAsync("wifi.ensure.connected", Json("{}"), CancellationToken.None);
        ExternalCapabilityReceipt disconnected = await disconnect.InvokeAsync("wifi.disconnect", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(stoppedReceipt.ErrorCode, Is.EqualTo("wlan_service_not_running"));
            Assert.That(stoppedReceipt.EffectMayHaveOccurred, Is.False);
            Assert.That(unreadReceipt.ErrorCode, Is.EqualTo("wifi_status_not_read"));
            Assert.That(noneReceipt.ErrorCode, Is.EqualTo("wifi_radio_not_found"));
            Assert.That(disconnected.Verified, Is.True, disconnected.ErrorCode);
            Assert.That(disconnecting.Calls, Is.EqualTo(4));
            Assert.That(delay.Calls, Is.EqualTo(1));
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
    private const string ProjectUserAgent = @"^BAXY/\d+\.\d+\.\d+ \(https://github\.com/REDSOULTM/BAXY\)$";

    private static WebBrowserAdapter SearchAdapter(
        TemporaryDirectory temporary, HttpClient http, ScriptedHiddenPages? pages = null, string? homeRegion = null,
        Func<TimeSpan, CancellationToken, Task>? engineWait = null) =>
        new(new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused")), http, homeRegion: homeRegion,
            hiddenPages: pages ?? new ScriptedHiddenPages(), engineWait: engineWait ?? (static (_, _) => Task.CompletedTask));

    // The general engine's page as its html endpoint gives it: an ad first (the engine's own link), then each result's
    // title link through the engine's redirect (//duckduckgo.com/l/?uddg=<the target>) or straight, and its snippet.
    private const string EngineResultsPage = """
        <html><body><div class="results">
        <div class="result results_links result--ad"><a rel="nofollow" class="result__a"
          href="https://duckduckgo.com/y.js?ad_domain=shop.example&amp;u3=x">Sponsored</a></div>
        <div class="result results_links"><h2 class="result__title"><a rel="nofollow" class="result__a"
          href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fguide%3Fa%3D1%26b%3D2&amp;rut=abc">An <b>example</b> guide</a></h2>
          <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fguide">How to <b>use</b> it</a></div>
        <div class="result results_links"><h2 class="result__title"><a rel="nofollow" class="result__a"
          href="ftp://files.example.com/calc">Not a web page</a></h2></div>
        <div class="result results_links"><h2 class="result__title"><a rel="nofollow" class="result__a"
          href="https://example.org/plain">Plain</a></h2></div>
        <div class="result results_links"><h2 class="result__title"><a rel="nofollow" class="result__a"
          href="https://example.net/third">Third</a></h2></div>
        </div></body></html>
        """;

    private const string EngineEmptyPage = """
        <html><body><div class="results"><div class="no-results">No results.</div></div>
        <form class="search--adv" action="/html/"><input name="q"></form></body></html>
        """;

    private const string EngineCheckPage = """<html><body><form id="challenge-form" action="//duckduckgo.com/anomaly.js">"""
        + "Unfortunately, bots use DuckDuckGo too.</form></body></html>";

    // LIC2 (2026-11-08): DuckDuckGo's partnerships page says «We simply don't have the rights to allow framing based on how
    // we generate our search results» (duckduckgo.com/duckduckgo-help-pages/company/partnerships), and the projects that
    // read its results pace them (duckduckgo-mcp-server: «30 requests per minute by default»): BAXY asks the engine at most
    // once every three seconds, as a person typing would, and a refusal is not asked again.
    [Test]
    public async Task TheEngineIsAskedAtMostOnceEveryThreeSeconds()
    {
        int asked = 0;
        var pages = new ScriptedHiddenPages
        {
            Answer = _ => ++asked == 2
                ? new(HiddenPageOutcome.Loaded, 202, EngineCheckPage)
                : new(HiddenPageOutcome.Loaded, 200, EngineResultsPage),
        };
        var waits = new List<TimeSpan>();
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(new SearchSourcesHttpHandler());
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http, pages,
            engineWait: (wait, _) => { waits.Add(wait); return Task.CompletedTask; });

        ExternalCapabilityReceipt first = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"example guide"}"""), CancellationToken.None);
        ExternalCapabilityReceipt second = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"another guide"}"""), CancellationToken.None);
        ExternalCapabilityReceipt third = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"a third guide"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.Verified, Is.True, first.ErrorCode);
            Assert.That(second.ErrorCode, Is.EqualTo("web_search_unavailable"));
            Assert.That(third.Verified, Is.True, third.ErrorCode);
            Assert.That(pages.Asked, Has.Count.EqualTo(3), "a refusal is not asked again");
            Assert.That(waits, Has.Count.EqualTo(2), "the first search waits for nothing; each next one, for its turn");
            Assert.That(waits, Has.All.InRange(TimeSpan.FromSeconds(2), TimeSpan.FromSeconds(3)));
        });
    }

    // The general engine's results come back in its order, title, url and snippet as it gave them (its markup
    // removed), bounded by limit; only what is structurally no result is left out: the engine's own links and
    // addresses that are not http or https. A result that shares no word with the query is still a result.
    [Test]
    public async Task AWebSearchReturnsTheEnginesResultsAsItGaveThem()
    {
        var pages = new ScriptedHiddenPages { Answer = _ => new(HiddenPageOutcome.Loaded, 200, EngineResultsPage) };
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(new SearchSourcesHttpHandler());
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http, pages);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"example guide","limit":2}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.EffectObserved, Is.False);
            JsonElement result = receipt.Result!.Value;
            Assert.That(result.GetProperty("version").GetInt32(), Is.EqualTo(1));
            Assert.That(result.GetProperty("source").GetString(), Is.EqualTo("web"));
            Assert.That(result.GetProperty("query").GetString(), Is.EqualTo("example guide"));
            Assert.That(result.GetProperty("authority").GetString(), Is.EqualTo("duckduckgo_html_hidden_webview2"));
            // BAXY Renew cu (C06): the source by its known name, which the model sees («authority» it does not).
            Assert.That(result.GetProperty("answeredBy").GetString(), Is.EqualTo("DuckDuckGo"));
            Assert.That(result.GetProperty("resultCount").GetInt32(), Is.EqualTo(2));
            Assert.That(result.TryGetProperty("sent", out _), Is.False);
            JsonElement results = result.GetProperty("results");
            Assert.That(results[0].GetProperty("title").GetString(), Is.EqualTo("An example guide"));
            Assert.That(results[0].GetProperty("url").GetString(), Is.EqualTo("https://example.com/guide?a=1&b=2"));
            Assert.That(results[0].GetProperty("snippet").GetString(), Is.EqualTo("How to use it"));
            Assert.That(results[1].GetProperty("url").GetString(), Is.EqualTo("https://example.org/plain"));
            Assert.That(results[1].GetProperty("snippet").GetString(), Is.Empty);
        });
    }

    // SRCH1 (owner, 2026-11-07 17:35): a web search is read by the browser BAXY embeds, never seen, from this machine;
    // nothing is asked of the engine by BAXY's own HTTP client (which presented itself as Chrome, WEB3 §5), no page opens
    // in the person's browser nor in BAXY's CDP one, and the page read is the engine's results page for the query, in
    // the region it is asked in.
    [Test]
    public async Task AWebSearchIsReadWhereNobodySeesItAndNeverOverHttp()
    {
        var pages = new ScriptedHiddenPages { Answer = _ => new(HiddenPageOutcome.Loaded, 200, EngineResultsPage) };
        var handler = new SearchSourcesHttpHandler();
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using WebBrowserAdapter adapter = new(browser, http, homeRegion: "CL", hiddenPages: pages);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"receta de lentejas & arroz","language":"es"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.EffectObserved || receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(pages.Asked.Select(static asked => asked.AbsoluteUri), Is.EqualTo(new[]
            {
                "https://html.duckduckgo.com/html/?q=receta%20de%20lentejas%20%26%20arroz&kl=cl-es",
            }));
            Assert.That(handler.Asked, Is.Empty);
            Assert.That(browser.Navigations, Is.Zero);
        });
    }

    // Noche 2026-10-27 (P1.3): a one-word local name searched with no region came back as the English word it also is.
    // The engine is asked in the person's Windows home region when it has that country in the search language (its own
    // code: Britain is «uk»), and the receipt says the region; any other pair, or no home region, asks the whole world.
    [TestCase("CL", "es", "?q=Savory&kl=cl-es", "CL")]
    [TestCase("GB", "en", "?q=Savory&kl=uk-en", "GB")]
    [TestCase("CL", "en", "?q=Savory", null)]
    [TestCase(null, "es", "?q=Savory", null)]
    public async Task AWebSearchAsksTheEngineInTheHomeRegionAndSaysIt(
        string? homeRegion, string language, string query, string? region)
    {
        var pages = new ScriptedHiddenPages { Answer = _ => new(HiddenPageOutcome.Loaded, 200, EngineResultsPage) };
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(new SearchSourcesHttpHandler());
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http, pages, homeRegion);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json($$"""{"query":"Savory","language":"{{language}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result!.Value.TryGetProperty("region", out JsonElement said) ? said.GetString() : null,
                Is.EqualTo(region));
            Assert.That(pages.Asked.Single().Query, Is.EqualTo(query));
        });
    }

    [Test]
    public async Task AWebSearchSaysABlockPageIsUnavailableAndAnEmptyResultsPageHasNoResults()
    {
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(new SearchSourcesHttpHandler());
        using WebBrowserAdapter blockedAdapter = SearchAdapter(temporary, http, new ScriptedHiddenPages
        {
            Answer = _ => new(HiddenPageOutcome.Loaded, 200, "<html><body><form>Please verify you are a human</form></body></html>"),
        });
        using WebBrowserAdapter emptyAdapter = SearchAdapter(temporary, http, new ScriptedHiddenPages
        {
            Answer = _ => new(HiddenPageOutcome.Loaded, 200, EngineEmptyPage),
        });
        using WebBrowserAdapter unreachableAdapter = SearchAdapter(temporary, http);

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
            Assert.That(none.Verified, Is.False);
            Assert.That(none.ErrorCode, Is.EqualTo("web_search_no_results"));
            Assert.That(down.ErrorCode, Is.EqualTo("web_search_unavailable"));
            Assert.That(new[] { block, none, down }, Has.All.Matches<ExternalCapabilityReceipt>(
                receipt => !receipt.EffectObserved && !receipt.EffectMayHaveOccurred));
        });
    }

    // SRCH1 (owner, 2026-11-07 17:35): when the engine asks to check that a person is asking, the honest answer is that
    // the search could not be read, and nothing opens: no next that would put the search in front of the person (the
    // route of encargo 41 and uso 80, browser_navigate_set in their browser). The receipt still says the query and what
    // the page answered.
    [Test]
    public async Task ACheckThatAPersonIsAskingOpensNothingAndSaysTheSearchWasNotRead()
    {
        var pages = new ScriptedHiddenPages { Answer = _ => new(HiddenPageOutcome.Loaded, 202, EngineCheckPage) };
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(new SearchSourcesHttpHandler());
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http, pages, "CL");

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"receta de lentejas & arroz","language":"es"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("web_search_unavailable"));
            Assert.That(receipt.EffectObserved || receipt.EffectMayHaveOccurred, Is.False);
            JsonElement result = receipt.Result!.Value;
            Assert.That(result.GetProperty("query").GetString(), Is.EqualTo("receta de lentejas & arroz"));
            Assert.That(Asked(result), Is.EqualTo(new[] { "html.duckduckgo.com challenge 202" }));
            Assert.That(result.TryGetProperty("next", out _), Is.False);
            Assert.That(result.TryGetProperty("searchPageUrl", out _), Is.False);
            Assert.That(result.GetRawText(), Does.Not.Contain("browser_"));
        });
    }

    // Uso 80: a refusal says what the engine's page answered, as it answered: a status that is no check (429), a page
    // that did not arrive in time, and no reader at all (no WebView2 on this machine); none of them opens anything.
    [TestCase("Loaded", 429, "html.duckduckgo.com refused 429")]
    [TestCase("Timeout", null, "html.duckduckgo.com no_answer -")]
    [TestCase("Failed", null, "html.duckduckgo.com unreachable -")]
    [TestCase("Unavailable", null, "html.duckduckgo.com unreachable -")]
    public async Task ASearchRefusalSaysWhatThePageAnsweredAndOpensNothing(string outcome, int? status, string asked)
    {
        HiddenPageOutcome answered = Enum.Parse<HiddenPageOutcome>(outcome);
        var pages = new ScriptedHiddenPages { Answer = _ => new(answered, status, status is null ? "" : "Too Many Requests") };
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(new SearchSourcesHttpHandler());
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http, pages);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"capital de Australia"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("web_search_unavailable"));
            Assert.That(Asked(receipt.Result!.Value), Is.EqualTo(new[] { asked }));
            Assert.That(receipt.Result!.Value.TryGetProperty("next", out _), Is.False);
            Assert.That(receipt.EffectObserved || receipt.EffectMayHaveOccurred, Is.False);
        });
    }

    // Each page of the engine a refused search asked, as «endpoint outcome status» («-» without one).
    private static string[] Asked(JsonElement result) => result.GetProperty("asked").EnumerateArray()
        .Select(static asked => string.Join(' ', asked.GetProperty("endpoint").GetString(),
            asked.GetProperty("outcome").GetString(),
            asked.TryGetProperty("httpStatus", out JsonElement status) ? status.GetInt32().ToString(CultureInfo.InvariantCulture) : "-"))
        .ToArray();

    // Uso real tanda 4c «en qué lugares puedo pedir comida para llevar cerca»: with nearby, this PC's city and its
    // country (M81: Valparaiso is also in Indiana), read from its public address, join the query; no coordinates
    // leave, and the receipt says the query as it was sent.
    [Test]
    public async Task ASearchNearbyCarriesThisPcsCityAndCountryAndNothingElse()
    {
        var pages = new ScriptedHiddenPages { Answer = _ => new(HiddenPageOutcome.Loaded, 200, EngineResultsPage) };
        var handler = new RoutingHttpHandler("",
            """{"success":true,"country":"Chile","region":"Valparaiso","city":"Valparaiso","latitude":-33.0363,"longitude":-71.6297}""");
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http, pages);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"comida para llevar","nearby":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("query").GetString(), Is.EqualTo("comida para llevar Valparaiso, Chile"));
            Assert.That(pages.Asked.Concat(handler.Asked.Where(uri => !uri.Host.Contains("ipwho", StringComparison.Ordinal))),
                Has.All.Matches<Uri>(uri => !uri.Query.Contains("33.03", StringComparison.Ordinal)
                    && !uri.Query.Contains("71.62", StringComparison.Ordinal)));
        });
    }

    [Test]
    public async Task ASearchNearbyWithoutThisPcsPlaceIsAnHonestAbsenceNotAGenericSearch()
    {
        var pages = new ScriptedHiddenPages { Answer = _ => new(HiddenPageOutcome.Loaded, 200, EngineResultsPage) };
        var handler = new RoutingHttpHandler("", """{"success":false}""");
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http, pages);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"farmacias","nearby":true}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("web_search_place_unavailable"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(handler.Asked, Has.All.Matches<Uri>(uri => uri.Host.Contains("ipwho", StringComparison.Ordinal)));
            Assert.That(pages.Asked, Is.Empty);
        });
    }

    // Renew al máximo (auditoría de flujos, web): «farmacias cerca» without network is the search not answering
    // (web_search_unavailable); it was web_search_place_unavailable, as if the PC's place were unknown.
    [Test]
    public async Task ASearchNearbyWithoutNetworkIsTheSearchNotAnswering()
    {
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(new SearchSourcesHttpHandler());
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);

        ExternalCapabilityReceipt web = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"farmacias","nearby":true}"""), CancellationToken.None);
        ExternalCapabilityReceipt places = await adapter.InvokeAsync(
            "web.search", Json("""{"query":"farmacias","source":"places","kind":"pharmacy","nearby":true}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(web.ErrorCode, Is.EqualTo("web_search_unavailable"));
            Assert.That(places.ErrorCode, Is.EqualTo("web_search_unavailable"));
            Assert.That(web.EffectMayHaveOccurred | places.EffectMayHaveOccurred, Is.False);
        });
    }

    // Without nearby nothing asks where this PC is; neither does a source nearby does not apply to (currency).
    [Test]
    public async Task ASearchWithoutNearbyNeverAsksWhereThisPcIs()
    {
        var pages = new ScriptedHiddenPages { Answer = _ => new(HiddenPageOutcome.Loaded, 200, EngineResultsPage) };
        var handler = new RoutingHttpHandler("", """{"success":true}""");
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http, pages);

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

    // The pages of a web search as the hidden reader would answer them, and the addresses asked.
    private sealed class ScriptedHiddenPages : IHiddenPageSource
    {
        internal Func<Uri, HiddenPage> Answer { get; init; } = static _ => new(HiddenPageOutcome.Unavailable, null, "");

        internal List<Uri> Asked { get; } = [];

        public Task<HiddenPage> ReadAsync(Uri address, TimeSpan within, TimeSpan settle, CancellationToken cancellationToken)
        {
            Asked.Add(address);
            return Task.FromResult(Answer(address));
        }
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

    // WEB1 (2026-11-07, LIC1 R3): BAXY is sold. Google News' feed is «solely for ... a personal feed reader for personal,
    // non-commercial use» (the feed's own terms) and Disney's terms forbid ESPN's pages to «robot, spider, script, or
    // other automated means» (https://disneytermsofuse.com/english/): neither is asked anything.
    [TestCase("""{"query":"noticias de hoy","source":"news"}""")]
    [TestCase("""{"query":"boca","source":"sports","team":"Boca Juniors","wants":"next"}""")]
    public async Task NeitherGoogleNewsNorEspnIsAskedAnything(string json)
    {
        var handler = new SearchSourcesHttpHandler();
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);

        try
        {
            await adapter.InvokeAsync("web.search", Json(json), CancellationToken.None);
        }
        catch (InvalidDataException)
        {
            // A source the catalog does not offer is refused before anything is asked.
        }

        Assert.That(handler.Asked.Select(asked => asked.Uri.Host),
            Has.None.Contains("google").And.None.Contains("espn"));
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

    // ARR1 (INT12 6/6, DEP5 2/2 with the stock Qwen): a places search without «kind» came back to the model as a bare
    // web_argument_invalid, and it called again without it. Anthropic's tool-use guide (platform.claude.com/docs/en/
    // agents-and-tools/tool-use/handle-tool-calls, read 2026-11-08): «Write instructive error messages», and for a call
    // «missing required parameters» a result that says which one lets the model «use the tool again with the missing
    // information filled in». The schema cannot require it only for places: llama.cpp's grammars skip «if / then /
    // else» (grammars/README.md). The kernel's refusal of arguments says each one and what it takes (P5.3); this one too,
    // from the adapter through the engine's handler to what the model reads, and nothing is asked of any service.
    [TestCase("""{"query":"farmacias","source":"places","place":"Plaza Mayor, Madrid, España"}""", new[] { "kind" })]
    [TestCase("""{"query":"farmacias","source":"places","kind":"  ","nearby":true}""", new[] { "kind" })]
    [TestCase("""{"query":"farmacias","source":"places","kind":"pharmacy"}""", new[] { "place" })]
    [TestCase("""{"query":"farmacias","source":"places"}""", new[] { "kind", "place" })]
    public async Task APlacesSearchWithoutItsArgumentsSaysWhichOnesToTheModel(string arguments, string[] missing)
    {
        var handler = new SearchSourcesHttpHandler();
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);
        var engine = new Baxy.Core.Operations.ExternalCapabilityHandler("web.search", new AdapterProvider(adapter));

        Baxy.Kernel.Operations.OperationOutcome outcome = await engine.ExecuteAsync(
            new Baxy.Kernel.Operations.OperationInvocation("request", "mission", "invocation", Json(arguments)),
            CancellationToken.None);
        using JsonDocument read = JsonDocument.Parse(
            Baxy.Kernel.Operations.OperationVisibleFacts.FromOutcome("web.search", outcome));

        Assert.Multiple(() =>
        {
            Assert.That(read.RootElement.GetProperty("status").GetString(), Is.EqualTo("failed"));
            Assert.That(read.RootElement.GetProperty("error").GetString(), Is.EqualTo("invalid_arguments"));
            Assert.That(read.RootElement.TryGetProperty("effectUncertain", out _), Is.False);
            JsonElement problems = read.RootElement.GetProperty("argumentProblems");
            Assert.That(problems.EnumerateArray().Select(static p => p.GetProperty("argument").GetString()),
                Is.EqualTo(missing));
            Assert.That(problems.EnumerateArray().Select(static p => p.GetProperty("problem").GetString()),
                Has.All.StartWith("required with source places"));
            // ARR2: after this refusal the model wrote one of the kinds it listed for sites of another kind (pharmacy
            // for a tyre repair shop or a liquor shop, restaurant for tapas bars): 11 of 62 «kind» written after it. The
            // problem says what «kind» is and that only sites of that value come back, and names no kind.
            if (missing.Contains("kind"))
            {
                string kind = problems.EnumerateArray().First(static p => p.GetProperty("argument").GetString() == "kind")
                    .GetProperty("problem").GetString()!;
                Assert.That(kind, Does.Contain("only sites"));
                Assert.That(kind, Does.Not.Contain("pharmacy").And.Not.Contain("restaurant").And.Not.Contain("("));
            }
            Assert.That(handler.Asked, Is.Empty);
        });
    }

    // M51 F-p05-t1 «Encuentra aparcamiento en Plaza del Polvorista»: source=places asks for the place the model wrote
    // (the first answer is the place), then for the sites whose OpenStreetMap value is the kind, in English, nearest to
    // its centre, both with the project's User-Agent. Each site comes back with its name, address and page as
    // OpenStreetMap has them and its distance from the place's centre, nearest first; the receipt says the place found.
    // LIC2 (2026-11-08): BAXY is sold, and Nominatim's policy caps «the sum of traffic by all your users» at «an absolute
    // maximum of 1 request per second» (operations.osmfoundation.org/policies/nominatim): both are asked of Photon, which
    // reads the same OpenStreetMap data and asks only to «be fair» (photon.komoot.io), and Nominatim is never asked.
    [Test]
    public async Task APlacesSearchAsksTheKindOfSiteNearestThePlace()
    {
        var handler = new SearchSourcesHttpHandler();
        handler.Routes.Add(("q=Plaza del Polvorista, El Puerto de Santa María", new(HttpStatusCode.OK,
            """{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"osm_type":"W","osm_id":29451697,"osm_key":"leisure","osm_value":"park","name":"Plaza del Polvorista","district":"Valdelagrana","city":"El Puerto de Santa María","state":"Andalucía","country":"España","extent":[-6.2334,36.5988,-6.2326,36.5982]},"geometry":{"type":"Point","coordinates":[-6.2330,36.5985]}}]}""",
            "application/json")));
        handler.Routes.Add(("osm_tag=:parking", new(HttpStatusCode.OK,
            """{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"osm_type":"W","osm_id":123,"osm_key":"amenity","osm_value":"parking","name":"Aparcamiento Polvorista","street":"Calle Larga","housenumber":"4","city":"El Puerto de Santa María","country":"España"},"geometry":{"type":"Point","coordinates":[-6.2330,36.6010]}},{"type":"Feature","properties":{"osm_type":"N","osm_id":456,"osm_key":"amenity","osm_value":"parking","street":"Calle Ganado","city":"El Puerto de Santa María","country":"España"},"geometry":{"type":"Point","coordinates":[-6.2330,36.5986]}},{"type":"Feature","properties":{"osm_type":"X","osm_id":789,"osm_value":"parking","name":"Nada"},"geometry":{"type":"Point","coordinates":[-6.2330,36.5986]}}]}""",
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
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("openstreetmap_photon"));
            Assert.That(receipt.Result?.GetProperty("answeredBy").GetString(), Is.EqualTo("OpenStreetMap"));
            JsonElement sent = receipt.Result!.Value.GetProperty("sent");
            Assert.That(sent.GetProperty("kind").GetString(), Is.EqualTo("parking"));
            Assert.That(sent.GetProperty("place").GetString(), Is.EqualTo("Plaza del Polvorista, El Puerto de Santa María"));
            Assert.That(sent.GetProperty("placeFound").GetString(),
                Is.EqualTo("Plaza del Polvorista, Valdelagrana, El Puerto de Santa María, Andalucía, España"));
            Assert.That(sent.GetProperty("categoryAsked").GetString(), Is.EqualTo("parking"));
            Assert.That(sent.GetProperty("matchedBy").GetString(), Is.EqualTo("category"));
            JsonElement results = receipt.Result!.Value.GetProperty("results");
            Assert.That(results.GetArrayLength(), Is.EqualTo(2));
            Assert.That(results.EnumerateArray().Select(static r => r.GetProperty("category").GetString()),
                Is.EqualTo(new[] { "amenity=parking", "amenity=parking" }));
            Assert.That(results[0].GetProperty("name").GetString(), Is.EqualTo("parking"));
            Assert.That(results[0].GetProperty("address").GetString(), Is.EqualTo("Calle Ganado, El Puerto de Santa María, España"));
            Assert.That(results[0].GetProperty("url").GetString(), Is.EqualTo("https://www.openstreetmap.org/node/456"));
            Assert.That(results[0].GetProperty("distanceMeters").GetInt32(), Is.EqualTo(10));
            Assert.That(results[1].GetProperty("name").GetString(), Is.EqualTo("Aparcamiento Polvorista"));
            Assert.That(results[1].GetProperty("address").GetString(),
                Is.EqualTo("Aparcamiento Polvorista, Calle Larga 4, El Puerto de Santa María, España"));
            Assert.That(results[1].GetProperty("url").GetString(), Is.EqualTo("https://www.openstreetmap.org/way/123"));
            Assert.That(results[1].GetProperty("distanceMeters").GetInt32(), Is.InRange(270, 290));
            Assert.That(handler.Asked, Has.Count.EqualTo(2));
            Assert.That(handler.Asked, Has.All.Matches<AskedRequest>(asked => asked.Uri.Host == "photon.komoot.io"
                && asked.UserAgent.Contains("(https://github.com/REDSOULTM/BAXY)", StringComparison.Ordinal)));
            Assert.That(handler.Asked[0].Uri.AbsolutePath, Is.EqualTo("/api/"));
            Assert.That(Uri.UnescapeDataString(handler.Asked[0].Uri.Query), Does.Contain("limit=1&"));
            Assert.That(handler.Asked[1].Uri.AbsolutePath, Is.EqualTo("/reverse"));
            Assert.That(Uri.UnescapeDataString(handler.Asked[1].Uri.Query),
                Does.Contain("lat=36.5985&lon=-6.233&radius=1.4&limit=10&osm_tag=:parking"));
        });
    }

    // A kind that is no OpenStreetMap value («gas station» is «fuel» there) finds no site by its value; then the sites
    // whose name holds it are asked inside the place's box, and the receipt lists them the same way.
    [Test]
    public async Task AKindThatIsNoOpenStreetMapValueIsAskedByNameInsideThePlace()
    {
        var handler = new SearchSourcesHttpHandler();
        handler.Routes.Add(("q=Rancagua, Chile", new(HttpStatusCode.OK,
            """{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"osm_type":"R","osm_id":1,"name":"Rancagua","country":"Chile","extent":[-70.80,-34.12,-70.68,-34.20]},"geometry":{"type":"Point","coordinates":[-70.74,-34.16]}}]}""",
            "application/json")));
        handler.Routes.Add(("osm_tag=:gas_station", new(HttpStatusCode.OK,
            """{"type":"FeatureCollection","features":[]}""", "application/json")));
        handler.Routes.Add(("q=gas station", new(HttpStatusCode.OK,
            """{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"osm_type":"N","osm_id":9,"osm_value":"fuel","name":"Gas Station Sur","city":"Rancagua","country":"Chile"},"geometry":{"type":"Point","coordinates":[-70.74,-34.17]}}]}""",
            "application/json")));
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.search",
            Json("""{"query":"bencineras en Rancagua","source":"places","kind":"gas station","place":"Rancagua, Chile"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            JsonElement results = receipt.Result!.Value.GetProperty("results");
            Assert.That(results.GetArrayLength(), Is.EqualTo(1));
            Assert.That(results[0].GetProperty("name").GetString(), Is.EqualTo("Gas Station Sur"));
            Assert.That(results[0].GetProperty("distanceMeters").GetInt32(), Is.InRange(1100, 1130));
            JsonElement sent = receipt.Result!.Value.GetProperty("sent");
            Assert.That(sent.GetProperty("kind").GetString(), Is.EqualTo("gas station"));
            Assert.That(sent.GetProperty("categoryAsked").GetString(), Is.EqualTo("gas_station"));
            Assert.That(sent.GetProperty("matchedBy").GetString(), Is.EqualTo("name"));
            Assert.That(results[0].GetProperty("category").GetString(), Is.EqualTo("fuel"));
            Assert.That(handler.Asked, Has.Count.EqualTo(3));
            Assert.That(handler.Asked[2].Uri.AbsolutePath, Is.EqualTo("/api/"));
            Assert.That(Uri.UnescapeDataString(handler.Asked[2].Uri.Query),
                Does.Contain("limit=10&bbox=-70.8,-34.2,-70.68,-34.12&q=gas station"));
            Assert.That(handler.Asked, Has.None.Matches<AskedRequest>(asked => asked.Uri.Host.Contains("nominatim", StringComparison.Ordinal)));
        });
    }

    // With nearby and no place, the place is this PC's city and country; a place the source does not find is said so
    // (ronda final 11: never «no results», since no site was looked for), and no site is asked.
    [Test]
    public async Task APlacesSearchNearbyIsInThisPcsCityAndAnUnknownPlaceHasNoResults()
    {
        var handler = new SearchSourcesHttpHandler();
        handler.Routes.Add(("ipwho.is", new(HttpStatusCode.OK,
            """{"success":true,"country":"Chile","region":"Valparaiso","city":"Valparaiso","latitude":-33.0363,"longitude":-71.6297}""",
            "application/json")));
        handler.Routes.Add(("q=Valparaiso, Chile", new(HttpStatusCode.OK,
            """{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"osm_type":"R","osm_id":2,"name":"Valparaíso","country":"Chile","extent":[-71.70,-33.00,-71.55,-33.10]},"geometry":{"type":"Point","coordinates":[-71.62,-33.05]}}]}""",
            "application/json")));
        handler.Routes.Add(("osm_tag=:pharmacy", new(HttpStatusCode.OK,
            """{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"osm_type":"N","osm_id":1,"osm_value":"pharmacy","name":"Farmacia Central","city":"Valparaíso","country":"Chile"}}]}""",
            "application/json")));
        handler.Routes.Add(("q=Nowhere Land", new(HttpStatusCode.OK, """{"type":"FeatureCollection","features":[]}""", "application/json")));
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
            Assert.That(near.Result?.GetProperty("sent").GetProperty("place").GetString(), Is.EqualTo("Valparaiso, Chile"));
            JsonElement first = near.Result!.Value.GetProperty("results")[0];
            Assert.That(first.GetProperty("name").GetString(), Is.EqualTo("Farmacia Central"));
            Assert.That(first.TryGetProperty("distanceMeters", out _), Is.False);
            Assert.That(unknown.ErrorCode, Is.EqualTo("place_area_not_resolved"));
            Assert.That(handler.Asked.Count(asked => asked.Uri.Query.Contains("pharmacy", StringComparison.Ordinal)), Is.EqualTo(1));
            Assert.That(handler.Asked.Where(asked => asked.Uri.Host != "ipwho.is"),
                Has.All.Matches<AskedRequest>(asked => !asked.Uri.Query.Contains("33.03", StringComparison.Ordinal)));
        });
    }

    // M63 (v3f-final F-p05-t1), with Photon's answers of 2026-11-08 (LIC2): the place is the first answer, and the car
    // parks around it are said with their distances from its centre, nearest first. Photon keeps only the sites that
    // have a name (Nominatim listed 10 here, 6 of them without one).
    [Test]
    public void ThePlazaDelPolvoristaIsWhereOpenStreetMapHasIt()
    {
        OpenStreetMapPlaceSource.Area? anchor = OpenStreetMapPlaceSource.AreaOf(PolvoristaCandidates);
        Assert.That(anchor, Is.Not.Null);
        List<OpenStreetMapPlaceSource.Place> parks =
            OpenStreetMapPlaceSource.Places(PolvoristaParking, anchor!.Value.Latitude, anchor.Value.Longitude);
        Assert.Multiple(() =>
        {
            Assert.That(anchor.Value.Name, Does.StartWith("Plaza del Polvorista, Valdelagrana, El Puerto de Santa María"));
            Assert.That(anchor.Value.Latitude, Is.EqualTo(36.5950).Within(0.0005));
            Assert.That(anchor.Value.Longitude, Is.EqualTo(-6.2273).Within(0.0005));
            Assert.That(parks.Select(static place => place.DistanceMeters), Is.EqualTo(new int?[] { 540, 610, 1040, 1300 }));
            Assert.That(parks[0].Name, Is.EqualTo("Parking Calderón"));
            Assert.That(parks[0].Address, Does.StartWith("Parking Calderón, Calle Curva, Sudamérica, El Puerto de Santa María"));
            Assert.That(OpenStreetMapPlaceSource.AreaOf("""{"type":"FeatureCollection","features":[]}"""), Is.Null);
        });
    }

    // INT12 (2026-11-08): Photon makes one document per house number of an OSM object that has several («Photon has been
    // able for a long time to create multiple ES documents from a single Nominatim place. This is used when OSM objects
    // reference multiple addresses», komoot/photon#884), and Nominatim splits «house number lists into individual
    // numbers» (nominatim.org, Tokenizers, clean-housenumbers). Measured: a barber shop at «11;13;15;17;19» came back five
    // times and left no room for the other shops. Each site is said once, at its nearest point.
    [Test]
    public void ASiteWithSeveralHouseNumbersIsSaidOnce()
    {
        const string body =
            """{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"osm_type":"N","osm_id":7100,"osm_key":"shop","osm_value":"hairdresser","name":"Barbería de Prueba","street":"Calle Uno","housenumber":"13","city":"Ciudad de Prueba","country":"País"},"geometry":{"type":"Point","coordinates":[-71.0010,-33.0000]}},{"type":"Feature","properties":{"osm_type":"N","osm_id":7100,"osm_key":"shop","osm_value":"hairdresser","name":"Barbería de Prueba","street":"Calle Uno","housenumber":"11","city":"Ciudad de Prueba","country":"País"},"geometry":{"type":"Point","coordinates":[-71.0010,-33.0000]}},{"type":"Feature","properties":{"osm_type":"W","osm_id":7200,"osm_key":"shop","osm_value":"hairdresser","name":"Peluquería Otra","street":"Calle Dos","city":"Ciudad de Prueba","country":"País"},"geometry":{"type":"Point","coordinates":[-71.0050,-33.0000]}},{"type":"Feature","properties":{"osm_type":"N","osm_id":7100,"osm_key":"shop","osm_value":"hairdresser","name":"Barbería de Prueba","street":"Calle Uno","housenumber":"15","city":"Ciudad de Prueba","country":"País"},"geometry":{"type":"Point","coordinates":[-71.0010,-33.0000]}}]}""";

        List<OpenStreetMapPlaceSource.Place> places = OpenStreetMapPlaceSource.Places(body, -33.0000, -71.0000);

        Assert.Multiple(() =>
        {
            Assert.That(places.Select(static place => place.Url), Is.EqualTo(new[]
            {
                "https://www.openstreetmap.org/node/7100", "https://www.openstreetmap.org/way/7200",
            }));
            Assert.That(places[0].Address, Does.StartWith("Barbería de Prueba, Calle Uno 13"));
        });
    }

    private const string PolvoristaCandidates =
        """{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"osm_type":"W","osm_id":29451697,"osm_key":"leisure","osm_value":"park","type":"other","name":"Plaza del Polvorista","district":"Valdelagrana","city":"El Puerto de Santa María","county":"Bahía de Cádiz","state":"Andalucía","country":"España","countrycode":"ES","extent":[-6.2277549,36.5953921,-6.2268937,36.5947017]},"geometry":{"type":"Point","coordinates":[-6.2273243,36.595047]}}]}""";

    private const string PolvoristaParking =
        """{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"osm_type":"W","osm_id":237016675,"osm_key":"amenity","osm_value":"parking","type":"house","name":"Parking Calderón","street":"Calle Curva","district":"Sudamérica","city":"El Puerto de Santa María","county":"Bahía de Cádiz","state":"Andalucía","country":"España","postcode":"11500","countrycode":"ES","extent":[-6.2240088,36.5992081,-6.2225388,36.5975102]},"geometry":{"type":"Point","coordinates":[-6.2231281,36.5985212]}},{"type":"Feature","properties":{"osm_type":"N","osm_id":1703329617,"osm_key":"amenity","osm_value":"parking","type":"house","name":"Centro","street":"Calle Descalzos","district":"Sudamérica","city":"El Puerto de Santa María","county":"Bahía de Cádiz","state":"Andalucía","country":"España","postcode":"11500","countrycode":"ES"},"geometry":{"type":"Point","coordinates":[-6.2250539,36.6002543]}},{"type":"Feature","properties":{"osm_type":"W","osm_id":429688699,"osm_key":"amenity","osm_value":"parking","type":"house","name":"Glorieta de San Francisco de Sales","street":"Calle Atalaya","district":"Sudamérica","city":"El Puerto de Santa María","county":"Bahía de Cádiz","state":"Andalucía","country":"España","postcode":"11500","countrycode":"ES","extent":[-6.2392854,36.5964225,-6.2385214,36.5961038]},"geometry":{"type":"Point","coordinates":[-6.2388839,36.5962767]}},{"type":"Feature","properties":{"osm_type":"W","osm_id":1423300837,"osm_key":"amenity","osm_value":"parking","type":"house","name":"Vehículos Autorizados","street":"Avenida del Monasterio","locality":"El Tejar","district":"Sudamérica","city":"El Puerto de Santa María","county":"Bahía de Cádiz","state":"Andalucía","country":"España","postcode":"11500","countrycode":"ES","extent":[-6.2184758,36.6043648,-6.2178253,36.6039593]},"geometry":{"type":"Point","coordinates":[-6.2182015,36.6041595]}}]}""";

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
    // Uso real 04-11 (F40): a page whose text was all skipped came back «completed» with text "": nothing was read, and
    // the result says so, how much was left out and how the page is seen in the browser.
    [TestCase("<html><head><title>Solo menú</title></head><body><nav>Inicio Tienda Comunidad</nav></body></html>", 23)]
    [TestCase("<html><head><title>Solo menú</title><script>app()</script></head><body><div id=\"root\"></div></body></html>", 0)]
    public async Task APageWithNoTextLeftIsNoCompletedRead(string page, int skipped)
    {
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(new RoutingHttpHandler(page, "{}"));
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt read = await adapter.InvokeAsync(
            "web.fetch", Json("""{"url":"https://tienda.example.com/juego"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(read.Verified, Is.False);
            Assert.That(read.ErrorCode, Is.EqualTo("web_fetch_no_text"));
            Assert.That(read.Result?.GetProperty("title").GetString(), Is.EqualTo("Solo menú"));
            Assert.That(read.Result?.GetProperty("finalUrl").GetString(), Is.EqualTo("https://tienda.example.com/juego"));
            Assert.That(read.Result?.GetProperty("skippedSectionCharacters").GetInt32(), Is.EqualTo(skipped));
            // SRCH1 (owner, 2026-11-07 17:35): no window opens to read it (the next opened it in the person's browser:
            // 4 of 4 such readings in SRCH1's held-out ended with browser.navigate, a window in front of them).
            Assert.That(read.Result?.TryGetProperty("next", out _), Is.False);
            Assert.That(read.Result?.GetRawText(), Does.Not.Contain("browser_"));
        });
    }

    // SRCH1: a page whose text is drawn by its scripts is read where nobody sees it, in the hidden browser BAXY embeds,
    // after its scripts drew it; what it shows then is the page's text, said as read that way.
    [Test]
    public async Task APageDrawnByItsScriptsIsReadInTheHiddenBrowser()
    {
        const string shell = "<html><head><title>Resultados</title><script>app()</script></head><body><div id=\"root\"></div></body></html>";
        const string drawn = "<html><head><title>Resultados</title></head><body><main><article>"
            + "<p>Ganó el Gran Premio la piloto de prueba Ana Ejemplo, con el auto número 7.</p></article></main></body></html>";
        var pages = new ScriptedHiddenPages
        {
            Answer = address => new(HiddenPageOutcome.Loaded, 200, drawn) { Final = address },
        };
        using TemporaryDirectory temporary = new();
        var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(new RoutingHttpHandler(shell, "{}"));
        using var adapter = new WebBrowserAdapter(browser, http, hiddenPages: pages);

        ExternalCapabilityReceipt read = await adapter.InvokeAsync(
            "web.fetch", Json("""{"url":"https://carreras.example.com/resultados"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(read.Verified, Is.True, read.ErrorCode);
            Assert.That(read.Result?.GetProperty("text").GetString(), Does.Contain("Ana Ejemplo"));
            Assert.That(read.Result?.GetProperty("finalUrl").GetString(), Is.EqualTo("https://carreras.example.com/resultados"));
            Assert.That(read.Result?.GetProperty("authority").GetString(), Is.EqualTo("hidden_webview2_rendered_text"));
            Assert.That(pages.Asked.Select(static asked => asked.AbsoluteUri),
                Is.EqualTo(new[] { "https://carreras.example.com/resultados" }));
            Assert.That(browser.Navigations, Is.Zero);
        });
    }

    // A page the hidden browser ended on that is no public address (a redirect into this network) is not read, and one
    // that is still empty when drawn is no reading either; neither opens anything.
    [TestCase("http://192.168.1.1/admin", "<html><body><p>Router admin: contraseña del wifi</p></body></html>")]
    [TestCase("https://carreras.example.com/resultados", "<html><body><div id=\"root\"></div></body></html>")]
    public async Task APageTheHiddenBrowserCannotReadAsPublicTextIsNoReading(string final, string drawn)
    {
        const string shell = "<html><head><title>Resultados</title><script>app()</script></head><body><div id=\"root\"></div></body></html>";
        var pages = new ScriptedHiddenPages
        {
            Answer = _ => new(HiddenPageOutcome.Loaded, 200, drawn) { Final = new Uri(final) },
        };
        using TemporaryDirectory temporary = new();
        var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        using var http = new HttpClient(new RoutingHttpHandler(shell, "{}"));
        using var adapter = new WebBrowserAdapter(browser, http, hiddenPages: pages);

        ExternalCapabilityReceipt read = await adapter.InvokeAsync(
            "web.fetch", Json("""{"url":"https://carreras.example.com/resultados"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(read.Verified, Is.False);
            Assert.That(read.ErrorCode, Is.EqualTo("web_fetch_no_text"));
            Assert.That(read.Result?.GetRawText(), Does.Not.Contain("contraseña").And.Not.Contain("browser_"));
            Assert.That(browser.Navigations, Is.Zero);
        });
    }

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

    // Revisión de calidad: a page is cut on a character. Cut between the two halves of an emoji, the half left alone
    // was written as U+FFFD (Utf8JsonWriter) and the emoji was in neither page; the next page starts at the emoji.
    [Test]
    public async Task WebFetchNeverCutsAnEmojiInTwo()
    {
        using TemporaryDirectory temporary = new();
        using var browser = new StubBrowserSession(temporary.Path, new(false, false, "", "", "", "unused"));
        var pages = new RoutingHttpHandler(
            "<html><body><p>" + new string('a', 499) + "😀" + new string('b', 300) + "</p></body></html>", "{}");
        using var http = new HttpClient(pages);
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt first = await adapter.InvokeAsync(
            "web.fetch", Json("""{"url":"https://largo.example.com/","maximumCharacters":500}"""), CancellationToken.None);
        ExternalCapabilityReceipt inside = await adapter.InvokeAsync(
            "web.fetch", Json("""{"url":"https://largo.example.com/","maximumCharacters":500,"offset":500}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.Result?.GetProperty("text").GetString(), Is.EqualTo(new string('a', 499)));
            Assert.That(first.Result?.GetProperty("nextOffset").GetInt32(), Is.EqualTo(499));
            Assert.That(inside.Result?.GetProperty("offset").GetInt32(), Is.EqualTo(499));
            Assert.That(inside.Result?.GetProperty("text").GetString(), Does.StartWith("😀b"));
            Assert.That(inside.Result?.GetProperty("text").GetString(), Does.Not.Contain("�"));
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

    // Renew al máximo (auditoría de flujos, web): a page that does not answer in time, before its headers or in the
    // middle of its body, is a page that took too long (web_fetch_timeout); the client's timeout escaped the adapter
    // (external_provider_exception) and a body that trickled held the turn until the operation's own deadline.
    [Test]
    public async Task AWebFetchThatTakesTooLongSaysSo()
    {
        using TemporaryDirectory temporary = new();
        using var silent = new HttpClient(new LambdaHttpHandler((_, _) =>
            throw new TaskCanceledException("timeout", new TimeoutException())));
        using var trickling = new HttpClient(new LambdaHttpHandler((_, _) =>
        {
            var content = new StreamContent(new StalledStream());
            content.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("text/html");
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK) { Content = content });
        }))
        { Timeout = TimeSpan.FromMilliseconds(300) };
        using WebBrowserAdapter beforeHeaders = SearchAdapter(temporary, silent);
        using WebBrowserAdapter midBody = SearchAdapter(temporary, trickling);
        using var turn = new CancellationTokenSource(TimeSpan.FromSeconds(10));

        ExternalCapabilityReceipt headers = await beforeHeaders.InvokeAsync(
            "web.fetch", Json("""{"url":"https://lenta.example.com/"}"""), turn.Token);
        ExternalCapabilityReceipt body = await midBody.InvokeAsync(
            "web.fetch", Json("""{"url":"https://lenta.example.com/"}"""), turn.Token);

        Assert.Multiple(() =>
        {
            Assert.That(headers.ErrorCode, Is.EqualTo("web_fetch_timeout"));
            Assert.That(body.ErrorCode, Is.EqualTo("web_fetch_timeout"));
            Assert.That(turn.IsCancellationRequested, Is.False);
            Assert.That(headers.EffectMayHaveOccurred | body.EffectMayHaveOccurred, Is.False);
        });
    }

    // Renew al máximo (auditoría de flujos, web): the client that asks the search sources (and the place by this PC's
    // address), the weather and a place's time zone keeps no cookie: one jar lived as long as BAXY and sent back what
    // each service set (Wikipedia's, Google's), so the person's searches went out tied to one another.
    [Test]
    public void ThePublicServicesClientKeepsNoCookie()
    {
        using SocketsHttpHandler handler = SearchPageReader.StrangerHandler();

        Assert.That(handler.UseCookies, Is.False);
    }

    // Renew al máximo (auditoría de flujos, web): an address said without its scheme («es.wikipedia.org/wiki/Arroz», as
    // the person dictates it and web.download takes it) is read over https; it was refused as not public.
    [Test]
    public async Task AWebFetchOfAnAddressWithoutSchemeReadsItOverHttps()
    {
        var handler = new SearchSourcesHttpHandler
        {
            ["es.wikipedia.org"] = new(HttpStatusCode.OK,
                "<html><head><title>Arroz</title></head><body><p>El arroz es una semilla.</p></body></html>", "text/html"),
        };
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(handler);
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);

        ExternalCapabilityReceipt read = await adapter.InvokeAsync(
            "web.fetch", Json("""{"url":"es.wikipedia.org/wiki/Arroz"}"""), CancellationToken.None);
        ExternalCapabilityReceipt local = await adapter.InvokeAsync(
            "web.fetch", Json("""{"url":"192.168.1.10/admin"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(read.Verified, Is.True, read.ErrorCode);
            Assert.That(read.Result?.GetProperty("requestedUrl").GetString(), Is.EqualTo("https://es.wikipedia.org/wiki/Arroz"));
            Assert.That(read.Result?.GetProperty("text").GetString(), Does.Contain("El arroz es una semilla."));
            Assert.That(local.ErrorCode, Is.EqualTo("web_fetch_address_not_public"));
            Assert.That(handler.Asked.Select(asked => asked.Uri.Host), Is.EqualTo(new[] { "es.wikipedia.org" }));
        });
    }

    // Renew al máximo (auditoría de flujos, web): an address whose host does not exist (an invented URL), no network,
    // and a host that resolves into the local network each say so; all three were web_adapter_unavailable, read as the
    // web tool itself being broken.
    [Test]
    public async Task AWebFetchThatReachesNoPageSaysWhy()
    {
        using TemporaryDirectory temporary = new();
        using var http = new HttpClient(new LambdaHttpHandler((request, _) => throw (request.RequestUri!.Host switch
        {
            "inventada.example.com" => new HttpRequestException(HttpRequestError.NameResolutionError, "no such host"),
            "lan.example.com" => new HttpRequestException(
                "connect refused", new SearchPageReader.AddressNotPublicException()),
            _ => new HttpRequestException(HttpRequestError.ConnectionError, "no network"),
        })));
        using WebBrowserAdapter adapter = SearchAdapter(temporary, http);

        ExternalCapabilityReceipt invented = await adapter.InvokeAsync(
            "web.fetch", Json("""{"url":"https://inventada.example.com/"}"""), CancellationToken.None);
        ExternalCapabilityReceipt offline = await adapter.InvokeAsync(
            "web.fetch", Json("""{"url":"https://recetas.example.com/"}"""), CancellationToken.None);
        ExternalCapabilityReceipt lan = await adapter.InvokeAsync(
            "web.fetch", Json("""{"url":"https://lan.example.com/"}"""), CancellationToken.None);
        // The same two causes as the production client's connection step raises them (no socket is opened).
        using var unresolved = new HttpClient(new SocketsHttpHandler
        {
            ConnectCallback = (_, _) => throw new System.Net.Sockets.SocketException(
                (int)System.Net.Sockets.SocketError.HostNotFound),
        });
        using var refused = new HttpClient(new SocketsHttpHandler
        {
            ConnectCallback = (_, _) => throw new HttpRequestException(
                "connect refused", new SearchPageReader.AddressNotPublicException()),
        });
        using WebBrowserAdapter unresolvedAdapter = SearchAdapter(temporary, unresolved);
        using WebBrowserAdapter refusedAdapter = SearchAdapter(temporary, refused);
        ExternalCapabilityReceipt unresolvedRead = await unresolvedAdapter.InvokeAsync(
            "web.fetch", Json("""{"url":"https://inventada.example.com/"}"""), CancellationToken.None);
        ExternalCapabilityReceipt refusedRead = await refusedAdapter.InvokeAsync(
            "web.fetch", Json("""{"url":"https://lan.example.com/"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(invented.ErrorCode, Is.EqualTo("web_fetch_host_not_found"));
            Assert.That(offline.ErrorCode, Is.EqualTo("web_fetch_unreachable"));
            Assert.That(lan.ErrorCode, Is.EqualTo("web_fetch_address_not_public"));
            Assert.That(unresolvedRead.ErrorCode, Is.EqualTo("web_fetch_host_not_found"));
            Assert.That(refusedRead.ErrorCode, Is.EqualTo("web_fetch_address_not_public"));
            Assert.That(invented.EffectMayHaveOccurred | offline.EffectMayHaveOccurred | lan.EffectMayHaveOccurred,
                Is.False);
        });
    }

    private sealed class LambdaHttpHandler(
        Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> answer) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken) => answer(request, cancellationToken);
    }

    // A body whose bytes never come: each read waits until it is cancelled.
    private sealed class StalledStream : Stream
    {
        public override bool CanRead => true;
        public override bool CanSeek => false;
        public override bool CanWrite => false;
        public override long Length => throw new NotSupportedException();
        public override long Position { get => 0; set => throw new NotSupportedException(); }
        public override void Flush() { }
        public override int Read(byte[] buffer, int offset, int count) => throw new NotSupportedException();
        public override async ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken cancellationToken = default)
        {
            await Task.Delay(Timeout.InfiniteTimeSpan, cancellationToken).ConfigureAwait(false);
            return 0;
        }
        public override Task<int> ReadAsync(byte[] buffer, int offset, int count, CancellationToken cancellationToken) =>
            ReadAsync(buffer.AsMemory(offset, count), cancellationToken).AsTask();
        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
        public override void SetLength(long value) => throw new NotSupportedException();
        public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
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

    // M98: a body of raw bytes (a page in another charset) and a redirect's Location.
    private sealed record HttpAnswer(
        HttpStatusCode Status, string Body, string ContentType, byte[]? Raw = null, string? Location = null);

    private sealed record AskedRequest(Uri Uri, string UserAgent, string[] Headers, string? Body);

    // Answers each host with its own reply; a host it does not know is unreachable.
    // The engine's way to an adapter: its calls, as they come.
    private sealed class AdapterProvider(WebBrowserAdapter adapter) : IExternalCapabilityProvider
    {
        public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
            string operation, JsonElement arguments, CancellationToken cancellationToken) =>
            adapter.InvokeAsync(operation, arguments, cancellationToken);
    }

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

        // Hosts that never answer: the request ends as HttpClient's own timeout does.
        internal HashSet<string> Silent { get; } = new(StringComparer.OrdinalIgnoreCase);

        protected override async Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Uri uri = request.RequestUri!;
            Asked.Add(new AskedRequest(uri, request.Headers.UserAgent.ToString(),
                request.Headers.Select(static header => header.Key).ToArray(),
                request.Content is null ? null : await request.Content.ReadAsStringAsync(cancellationToken)));
            if (Silent.Contains(uri.Host))
                throw new TaskCanceledException("timed out", new TimeoutException());
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
            return response;
        }
    }

    // Feria 2026-10-27: a Word document with a text in it had no tool (only its title was written), so a long text was
    // typed key by key into whatever field Word had in front. The body goes in as paragraphs (an entry's line breaks
    // make paragraphs of their own), the reread package must hold title and paragraphs as asked, and the receipt counts
    // them and names the file.
    [Test]
    public async Task AWordDocumentIsWrittenWithItsParagraphsAndTheRereadCountsThem()
    {
        using TemporaryDirectory temporary = new();
        var adapter = new MicrosoftAccountAdapter(temporary.Path, new StubProcessRunner("{}"));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "office.document.create",
            Json("""{"format":"docx","title":"Cuento","paragraphs":["Había una vez un faro \"azul\" y un barco.","Llegó la noche.\r\n\n  Y amaneció 🌙.  \rFin."]}"""),
            CancellationToken.None);

        string path = Directory.GetFiles(temporary.Path, "*.docx").Single();
        string text = (await adapter.InvokeAsync(
            "office.document.read",
            Json($$"""{"documentId":"{{receipt.Result?.GetProperty("documentId").GetString()}}"}"""),
            CancellationToken.None)).Result?.GetProperty("text").GetString() ?? string.Empty;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("paragraphCount").GetInt32(), Is.EqualTo(4));
            Assert.That(receipt.Result?.GetProperty("wordCount").GetInt32(), Is.EqualTo(16));
            Assert.That(receipt.Result?.GetProperty("name").GetString(), Is.EqualTo(Path.GetFileName(path)));
            Assert.That(text, Is.EqualTo("Cuento\nHabía una vez un faro \"azul\" y un barco.\nLlegó la noche.\nY amaneció 🌙.\nFin."));
        });
    }

    // Encargo 75 (U43): the file went to the documents' own folder under a name with a suffix; it was then looked for in
    // the folder the person named, by that name alone. The receipt says where it really is.
    [Test]
    public async Task ADocumentsReceiptSaysTheWholePathOfTheFileItWrote()
    {
        using TemporaryDirectory temporary = new();
        var adapter = new MicrosoftAccountAdapter(temporary.Path, new StubProcessRunner("{}"));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "office.document.create", Json("""{"format":"docx","title":"Acta"}"""), CancellationToken.None);

        string path = Directory.GetFiles(temporary.Path, "*.docx").Single();
        Assert.That(receipt.Result?.GetProperty("fullPath").GetString(), Is.EqualTo(path));
    }

    // file.open shows the document by «BAXY\» and the receipt's name, and refuses a name with «..» in it: a title ending
    // in an ellipsis («Había una vez...») must not leave one there.
    [Test]
    public async Task ADocumentNameKeepsNoDoubleDotFileOpenWouldRefuse()
    {
        using TemporaryDirectory temporary = new();
        var adapter = new MicrosoftAccountAdapter(temporary.Path, new StubProcessRunner("{}"));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "office.document.create",
            Json("""{"format":"docx","title":"Había una vez... el faro..","paragraphs":["Fin."]}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("name").GetString(), Does.StartWith("Había una vez. el faro.-"));
            Assert.That(receipt.Result?.GetProperty("title").GetString(), Is.EqualTo("Había una vez... el faro.."));
        });
    }

    // A control character XML cannot hold would leave a file Word cannot open: refused before anything is written.
    [Test]
    public async Task AParagraphXmlCannotHoldIsRefusedBeforeAnythingIsWritten()
    {
        using TemporaryDirectory temporary = new();
        var adapter = new MicrosoftAccountAdapter(temporary.Path, new StubProcessRunner("{}"));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "office.document.create",
            Json("""{"format":"docx","title":"Cuento","paragraphs":["uno\u0001dos"]}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("office_text_invalid_character"));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(Directory.GetFiles(temporary.Path), Is.Empty);
        });
    }

    // A spreadsheet has no paragraphs: asked for one with them, nothing is written and the refusal names it.
    [Test]
    public async Task ParagraphsForASpreadsheetAreRefusedBeforeAnythingIsWritten()
    {
        using TemporaryDirectory temporary = new();
        var adapter = new MicrosoftAccountAdapter(temporary.Path, new StubProcessRunner("{}"));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "office.document.create",
            Json("""{"format":"xlsx","title":"Gastos","paragraphs":["Luz"]}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("office_paragraphs_docx_only"));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(Directory.GetFiles(temporary.Path), Is.Empty);
        });
    }

    // Banco de entorno del NB (U44, 2 of 3): the table sent as a workbook's paragraphs was refused bare and the model
    // gave up. The refusal leads with the app.open call of the program Windows opens .xlsx files with (by its file
    // name, which app.open resolves), a new blank workbook in front; with no program registered it says that instead,
    // and with the aid off it is bare as before.
    [TestCase("all", "\"C:\\Program Files\\Office Suite\\root\\SHEETS.EXE\" \"%1\"",
        """app_open {"appId":"SHEETS.EXE","newDocument":true,"foreground":true,"forControl":true} opens a new blank workbook""")]
    [TestCase("all", null, "this call wrote nothing")]
    [TestCase("none", "\"C:\\Program Files\\Office Suite\\root\\SHEETS.EXE\" \"%1\"", null)]
    public async Task ParagraphsForASpreadsheetLeadWithTheProgramThatOpensWorkbooks(
        string aids, string? command, string? next)
    {
        using IDisposable setting = ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        var asked = new List<string>();
        var adapter = new MicrosoftAccountAdapter(temporary.Path, new StubProcessRunner("{}"),
            associatedCommand: extension => { asked.Add(extension); return command; });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "office.document.create",
            Json("""{"format":"xlsx","title":"precios","paragraphs":["Producto\nPrecio\nPan\n100"]}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("office_paragraphs_docx_only"));
            Assert.That(Directory.GetFiles(temporary.Path), Is.Empty);
            if (next is null)
                Assert.That(receipt.Result, Is.Null);
            else
                Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.StartWith(next));
            if (command is null && next is not null)
                Assert.That(receipt.Result!.Value.GetProperty("next").GetString(),
                    Does.EndWith("no program on this PC opens .xlsx files"));
            if (next is not null)
                Assert.That(asked, Is.EqualTo(new[] { ".xlsx" }));
        });
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
            // Encargo 65: the application whose calendar it read, weighed against the tabs the person names.
            Assert.That(receipt.Result?.GetProperty("readFrom").GetString(), Is.EqualTo("Outlook"));
        });
    }

    // Banco de uso 05-11 (F12): an event at 11:20 here was read as «14:20Z» and said as «2:20 PM»: the reader was
    // right and the model read the UTC out as the hour. Each instant also comes in this PC's own hour, as an alarm's does
    // (dueLocal), at that instant's own offset: a date across a daylight change keeps its own.
    [Test]
    public async Task ACalendarEventSaysItsHourHereBesideItsUtc()
    {
        const string output = """
            {"ok":true,"effectObserved":false,"events":[{"entryId":"e","title":"Reunión de prueba","startUtc":"2026-11-09T14:20:00.0000000Z","endUtc":"2026-11-09T15:40:00.0000000Z"},{"entryId":"f","title":"Otra","startUtc":"2026-07-09T14:20:00.0000000Z","endUtc":"2026-07-09T15:40:00.0000000Z"}]}
            """;
        using TemporaryDirectory temporary = new();
        var adapter = new MicrosoftAccountAdapter(temporary.Path, new StubProcessRunner(output));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "calendar.event.list",
            Json("""{"startUtc":"2026-07-01T00:00:00Z","endUtc":"2026-12-01T00:00:00Z"}"""),
            CancellationToken.None);

        JsonElement first = receipt.Result!.Value.GetProperty("events")[0];
        JsonElement second = receipt.Result!.Value.GetProperty("events")[1];
        Assert.Multiple(() =>
        {
            Assert.That(first.GetProperty("startLocal").GetString(), Is.EqualTo(HourHere("2026-11-09T14:20:00Z")));
            Assert.That(first.GetProperty("endLocal").GetString(), Is.EqualTo(HourHere("2026-11-09T15:40:00Z")));
            Assert.That(second.GetProperty("startLocal").GetString(), Is.EqualTo(HourHere("2026-07-09T14:20:00Z")));
            Assert.That(first.GetProperty("startUtc").GetString(), Is.EqualTo("2026-11-09T14:20:00.0000000Z"));
        });
    }

    // The same with the event a create read back, and with a mail's arrival: «te llegó a las 14:20» is the same mistake.
    [Test]
    public async Task ACreatedEventAndAMailSayTheirHourHere()
    {
        const string created = """
            {"ok":true,"effectObserved":true,"entryId":"e","title":"Dentista","startUtc":"2026-11-09T18:00:00.0000000Z","endUtc":"2026-11-09T19:00:00.0000000Z"}
            """;
        const string mail = """
            {"ok":true,"effectObserved":false,"entryId":"m","subject":"Aviso","sender":"a@example.test","receivedUtc":"2026-11-02T10:26:00Z","body":"hola","bodyLength":4}
            """;
        using TemporaryDirectory temporary = new();
        ExternalCapabilityReceipt made = await new MicrosoftAccountAdapter(temporary.Path, new StubProcessRunner(created)).InvokeAsync(
            "calendar.event.create",
            Json("""{"startUtc":"2026-11-09T18:00:00Z","endUtc":"2026-11-09T19:00:00Z","title":"Dentista"}"""),
            CancellationToken.None);
        ExternalCapabilityReceipt read = await new MicrosoftAccountAdapter(temporary.Path, new StubProcessRunner(mail)).InvokeAsync(
            "email.latest.read", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(made.Result?.GetProperty("startLocal").GetString(), Is.EqualTo(HourHere("2026-11-09T18:00:00Z")));
            Assert.That(made.Result?.GetProperty("endLocal").GetString(), Is.EqualTo(HourHere("2026-11-09T19:00:00Z")));
            Assert.That(read.Result?.GetProperty("receivedLocal").GetString(), Is.EqualTo(HourHere("2026-11-02T10:26:00Z")));
        });
    }

    private static string HourHere(string utc) =>
        DateTimeOffset.Parse(utc, System.Globalization.CultureInfo.InvariantCulture).ToLocalTime()
            .ToString("dddd yyyy-MM-dd HH:mm", System.Globalization.CultureInfo.InvariantCulture);

    // Renew al máximo (w5): a time with its own offset is that instant, sent to Outlook in UTC; it came back
    // «microsoft_desktop_adapter_failed», read as Outlook failing. One with no offset is refused before anything runs,
    // naming the argument and (aid calendar_time_next) why.
    [Test]
    public async Task ACalendarTimeWithItsOffsetIsTakenAndOneWithoutIsNamed()
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use("all");
        const string output = """{"ok":true,"effectObserved":false,"events":[]}""";
        using TemporaryDirectory temporary = new();
        var runner = new StubProcessRunner(output);
        var adapter = new MicrosoftAccountAdapter(temporary.Path, runner);

        ExternalCapabilityReceipt offset = await adapter.InvokeAsync(
            "calendar.event.list",
            Json("""{"startUtc":"2026-07-17T00:00:00-03:00","endUtc":"2026-07-18T00:00:00-03:00"}"""),
            CancellationToken.None);
        string sent = Encoding.UTF8.GetString(Convert.FromBase64String(runner.LastArguments[^1]));
        ExternalCapabilityReceipt local = await adapter.InvokeAsync(
            "calendar.event.create",
            Json("""{"startUtc":"2026-07-17T18:00:00","endUtc":"2026-07-17T19:00:00Z","title":"Dentista"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(offset.Verified, Is.True, offset.ErrorCode);
            Assert.That(JsonDocument.Parse(sent).RootElement.GetProperty("startUtc").GetString(),
                Is.EqualTo("2026-07-17T03:00:00.0000000+00:00"));
            Assert.That(local.ErrorCode, Is.EqualTo("calendar_time_not_exact"));
            Assert.That(local.EffectObserved || local.EffectMayHaveOccurred, Is.False);
            Assert.That(local.Result?.GetProperty("argument").GetString(), Is.EqualTo("startUtc"));
            Assert.That(local.Result?.GetProperty("next").GetString(), Does.EndWith("no event was created"));
        });
    }

    // Renew al máximo (w8): Outlook keeps an event's times to the minute: a create with seconds is refused before
    // anything runs; and an event saved whose read-back differs is named by the failure, so it is not made twice.
    [Test]
    public async Task ACalendarCreateWithSecondsIsRefusedAndAMismatchNamesTheEventMade()
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use("all");
        const string mismatch = "{\"ok\":false,\"effectObserved\":true,\"error\":\"outlook_calendar_postread_mismatch\"," +
            "\"entryId\":\"private-entry\",\"title\":\"Dentista\",\"startUtc\":\"2026-07-17T18:00:00.0000000Z\"," +
            "\"endUtc\":\"2026-07-17T19:00:00.0000000Z\"}";
        using TemporaryDirectory temporary = new();
        var runner = new StubProcessRunner(mismatch);
        var adapter = new MicrosoftAccountAdapter(temporary.Path, runner);

        ExternalCapabilityReceipt seconds = await adapter.InvokeAsync(
            "calendar.event.create",
            Json("""{"startUtc":"2026-07-17T18:00:30Z","endUtc":"2026-07-17T19:00:00Z","title":"Dentista"}"""),
            CancellationToken.None);
        bool ranForSeconds = runner.LastArguments.Length > 0;
        ExternalCapabilityReceipt made = await adapter.InvokeAsync(
            "calendar.event.create",
            Json("""{"startUtc":"2026-07-17T18:00:00Z","endUtc":"2026-07-17T19:00:00Z","title":"Dentista"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(ranForSeconds, Is.False);
            Assert.That(seconds.ErrorCode, Is.EqualTo("calendar_time_not_whole_minute"));
            Assert.That(seconds.Result?.GetProperty("argument").GetString(), Is.EqualTo("startUtc"));
            Assert.That(seconds.EffectObserved || seconds.EffectMayHaveOccurred, Is.False);
            Assert.That(made.ErrorCode, Is.EqualTo("outlook_calendar_postread_mismatch"));
            Assert.That(made.EffectObserved, Is.True);
            Assert.That(made.Result?.GetProperty("eventId").GetString(), Does.StartWith("event_"));
            Assert.That(made.Result?.GetProperty("startUtc").GetString(), Is.EqualTo("2026-07-17T18:00:00.0000000Z"));
            Assert.That(made.Result?.GetRawText(), Does.Not.Contain("private-entry"));
            Assert.That(made.Result?.GetProperty("next").GetString(), Does.Contain("second event"));
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

    // Round A: Spotify with sessions at 40 and 20 set to 40: the loudest stays at 40 (the level read before and after)
    // and the quieter one rises. That is an observed effect, not «external_effect_unobserved».
    [Test]
    public async Task AnAppVolumeChangeInAQuieterSessionIsAnObservedEffect()
    {
        var set = new WindowsAppVolumeSetAdapter((_, level, beforeEffect, _) =>
        {
            beforeEffect?.Invoke();
            return new ApplicationSessionAdjustment("Spotify", 2, 40, level, false, "endpoint-1", Changed: true);
        });
        var adjust = new WindowsAppVolumeAdapter((_, _, beforeEffect, _) =>
        {
            beforeEffect?.Invoke();
            return new ApplicationSessionAdjustment("Spotify", 2, 100, 100, false, "endpoint-1", Changed: true);
        });
        var unchanged = new WindowsAppVolumeSetAdapter((_, level, beforeEffect, _) =>
        {
            beforeEffect?.Invoke();
            return new ApplicationSessionAdjustment("Spotify", 2, 40, level, false, "endpoint-1", Changed: false);
        });

        ExternalCapabilityReceipt raised = await set.InvokeAsync(
            "audio.app.volume.set", Json("""{"app":"Spotify","level":40}"""), CancellationToken.None);
        ExternalCapabilityReceipt upAtTheTop = await adjust.InvokeAsync(
            "audio.app.volume.adjust", Json("""{"app":"Spotify","direction":"up","amount":10}"""), CancellationToken.None);
        ExternalCapabilityReceipt already = await unchanged.InvokeAsync(
            "audio.app.volume.set", Json("""{"app":"Spotify","level":40}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(raised.Verified, Is.True, raised.ErrorCode);
            Assert.That(raised.EffectObserved, Is.True);
            Assert.That(upAtTheTop.Verified, Is.True, upAtTheTop.ErrorCode);
            Assert.That(upAtTheTop.EffectObserved, Is.True);
            Assert.That(already.Verified, Is.True);
            Assert.That(already.EffectObserved, Is.False);
            Assert.That(already.StateAlreadyReached, Is.True, "already at the level is the request done");
            Assert.That(raised.StateAlreadyReached, Is.False);
        });
    }

    // FT/proveedores goal (review): an application already at 100 raised (or at 0 lowered), no session changed, says it
    // is already at that end, as the system volume does; it was a success with no observed effect.
    [TestCase("up", 100, false, "volume_already_at_maximum")]
    [TestCase("up", 100, true, "volume_already_at_maximum_muted")]
    [TestCase("down", 0, false, "volume_already_at_minimum")]
    public async Task AnAppVolumeAlreadyAtTheEndSaysSo(string direction, int level, bool muted, string error)
    {
        var adjust = new WindowsAppVolumeAdapter((_, _, beforeEffect, _) =>
        {
            beforeEffect?.Invoke();
            return new ApplicationSessionAdjustment("Spotify", 1, level, level, muted, "endpoint-1", Changed: false);
        });

        ExternalCapabilityReceipt receipt = await adjust.InvokeAsync(
            "audio.app.volume.adjust",
            Json($$"""{"app":"Spotify","direction":"{{direction}}","amount":10}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(error));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
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
            return new ApplicationSessionAdjustment("Spotify", 2, 85, level, false, "endpoint-1", Changed: true);
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
            Assert.That(noSession.ErrorCode, Is.EqualTo("app_audio_session_not_found_on_default_output"));
        });
    }

    // Renew al máximo (auditoría de flujos, P257: «deja el volumen en 20» chose audio.app.volume.set {app:"volumen"} in
    // 7 of 27 runs): an application with no audio session failed with the bare code, so the next step had nothing to go
    // on. The failure names the applications that do have one (few, short) and that the PC's own volume is another
    // operation; a model aid, off with the others. Holdout v6 V6E064 («el volumen déjamelo en treinta mientras veo la
    // serie» set Netflix's own volume): with that operation only named, the model answered in words in 4 of 4 runs; the
    // PC's own call is said with the person's level or amount, as said_folder says its call.
    [TestCase("audio.app.volume.set", """{"app":"volumen","level":20}""", "all", "audio_volume_set", "level 20")]
    [TestCase("audio.app.volume.adjust", """{"app":"volumen","amount":10,"direction":"down"}""", "all",
        "audio_volume_adjust", "amount 10 and direction \"down\"")]
    [TestCase("audio.app.volume.set", """{"app":"volumen","level":20}""", "none", null, null)]
    public async Task AnAppWithNoAudioSessionNamesTheAppsThatHaveOne(
        string operation, string arguments, string aids, string? systemOperation, string? systemArguments)
    {
        using IDisposable setting = ModelAids.Use(aids);
        string[] withAudio = ["Spotify", "chrome", "Discord", "mpv", "steam", "opera", "Teams", "zoom", "vlc", "obs64"];
        AudioSessionProgram[] programs = [.. withAudio.Select(static name => new AudioSessionProgram(name, null))];
        IExternalOperationAdapter adapter = operation == "audio.app.volume.set"
            ? new WindowsAppVolumeSetAdapter((_, _, _, _) => null, () => programs)
            : new WindowsAppVolumeAdapter((_, _, _, _) => null, () => programs);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("app_audio_session_not_found_on_default_output"));
            if (systemOperation is null)
            {
                Assert.That(receipt.Result, Is.Null);
                return;
            }

            string[] named = receipt.Result!.Value.GetProperty("appsWithAudio").EnumerateArray()
                .Select(item => item.GetString()!).ToArray();
            Assert.That(named, Is.EqualTo(withAudio.Take(8).ToArray()));
            Assert.That(receipt.Result.Value.GetProperty("next").GetString(), Does.Contain(" is " + systemOperation + ",")
                .And.EndWith($"if the person meant the whole PC, call {systemOperation} with {systemArguments}"));
            Assert.That(receipt.Result.Value.TryGetProperty("personBrowser", out _), Is.False, "no browser known");
        });
    }

    // Banco de uso 03-11 (R09, «baja el volumen del navegador a 20»): the model took «el navegador» as one browser, the
    // failure named the processes with audio (another browser among them) and the model asked. The failure says which
    // browser is the person's own (Windows' default), as a window's failure does (WindowControlHandlers).
    [TestCase("audio.app.volume.set", """{"app":"navegadorx","level":20}""")]
    [TestCase("audio.app.volume.adjust", """{"app":"navegadorx","amount":10,"direction":"down"}""")]
    public async Task AnAppWithNoAudioSessionSaysThePersonsBrowser(string operation, string arguments)
    {
        using IDisposable setting = ModelAids.Use("all");
        AudioSessionProgram[] withAudio = [new("reproductorx", null), new("navegadory", null)];
        (string Name, string Process)? browser = ("Navegador Y", "navegadory");
        IExternalOperationAdapter adapter = operation == "audio.app.volume.set"
            ? new WindowsAppVolumeSetAdapter((_, _, _, _) => null, () => withAudio, () => browser)
            : new WindowsAppVolumeAdapter((_, _, _, _) => null, () => withAudio, () => browser);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("app_audio_session_not_found_on_default_output"));
            JsonElement own = receipt.Result!.Value.GetProperty("personBrowser");
            Assert.That(own.GetProperty("name").GetString(), Is.EqualTo("Navegador Y"));
            Assert.That(own.GetProperty("process").GetString(), Is.EqualTo("navegadory"));
        });
    }

    // Encargo 82 (vivo del 81): the application said is the one on the list and its session did not take the call. The
    // next led with that same call («no application with audio is named X, and X is the one…»); the model tried it,
    // failed again, and moved the whole PC's volume, which nobody asked for. It says so and writes no call.
    [TestCase("""{"app":"Contoso.Sound.Deck","level":40}""")]
    [TestCase("""{"app":"contoso sound deck","level":40}""")]
    public async Task ANextNeverLeadsWithTheCallThatJustFailed(string arguments)
    {
        using IDisposable setting = ModelAids.Use("all");
        AudioSessionProgram[] withAudio = [new("python", null), new("Contoso.Sound.Deck", null)];
        var adapter = new WindowsAppVolumeSetAdapter((_, _, _, _) => null, () => withAudio);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("audio.app.volume.set", Json(arguments), CancellationToken.None);

        string next = receipt.Result!.Value.GetProperty("next").GetString()!;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("app_audio_session_not_found_on_default_output"));
            Assert.That(next, Does.Not.Contain("audio_app_volume_set {"));
            Assert.That(next, Does.Not.Contain("audio_volume_set"));
            Assert.That(next, Does.Contain("Contoso.Sound.Deck"));
        });
    }

    // Uso 81 (banco de decisiones e35-H-R09a, 16/20 -> 9/20 with a new catalog): after the failure the model answered in
    // words instead of trying again with the application that does play. A failure whose next leads with the exact call
    // is followed (encargos 28, 48). So when one application with audio, and only one, has a name that matches what was
    // said by form (a word said inside one of its names, or one of its names inside what was said), the next leads with
    // the same call naming that application's process, with the same level or amount. Its names: its process, the name
    // Windows shows for it (its session's display name, else its executable's description) and that name's forms in the
    // name-equivalence data («navegador de microsoft» for Microsoft Edge: R09). A name no application has, or that two
    // have, gets no call.
    [TestCase("audio.app.volume.set", """{"app":"el discord","level":20}""", false,
        """audio_app_volume_set {"app":"DiscordPTB","level":20} sets the volume of DiscordPTB to 20; """)]
    [TestCase("audio.app.volume.adjust", """{"app":"discord","amount":10,"direction":"down"}""", false,
        """audio_app_volume_adjust {"app":"DiscordPTB","amount":10,"direction":"down"} turns the volume of DiscordPTB """
        + "down by 10; ")]
    [TestCase("audio.app.volume.set", """{"app":"Elden","level":35}""", false,
        """audio_app_volume_set {"app":"eldenring","level":35} sets the volume of eldenring to 35; """)]
    [TestCase("audio.app.volume.set", """{"app":"navegador","level":20}""", false,
        """audio_app_volume_set {"app":"msedge","level":20} sets the volume of msedge (Microsoft Edge) to 20; this """
        + "call changed nothing: no application with audio is named \"navegador\", and msedge is the one whose names "
        + "match it")]
    [TestCase("audio.app.volume.set", """{"app":"navegador","level":20}""", true, null)]
    [TestCase("audio.app.volume.set", """{"app":"el juego","level":20}""", false, null)]
    [TestCase("audio.app.volume.set", """{"app":"microsoft","level":20}""", false, null)]
    public async Task AnAppWithNoAudioSessionLeadsWithTheCallOfTheOneAppWhoseNameMatches(
        string operation, string arguments, bool chromeToo, string? leads)
    {
        using IDisposable setting = ModelAids.Use("all");
        AudioSessionProgram[] withAudio =
        [
            new("python", "Python"),
            new("DiscordPTB", "Discord PTB"),
            new("eldenring", "ELDEN RING™"),
            new("msedge", "Microsoft Edge"),
            new("ms-teams", "Microsoft Teams"),
            .. chromeToo ? new AudioSessionProgram[] { new("chrome", "Google Chrome") } : [],
        ];
        IExternalOperationAdapter adapter = operation == "audio.app.volume.set"
            ? new WindowsAppVolumeSetAdapter((_, _, _, _) => null, () => withAudio)
            : new WindowsAppVolumeAdapter((_, _, _, _) => null, () => withAudio);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(operation, Json(arguments), CancellationToken.None);
        using IDisposable off = ModelAids.Use("app_volume_candidates");
        ExternalCapabilityReceipt aidOff = await adapter.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("app_audio_session_not_found_on_default_output"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            JsonElement result = receipt.Result!.Value;
            Assert.That(result.GetProperty("appsWithAudio").EnumerateArray().Select(static item => item.GetString()),
                Is.EqualTo(withAudio.Select(static program => program.Process)));
            Assert.That(result.TryGetProperty("shownAs", out _), Is.False, "the shown names are said in the next only");
            string next = result.GetProperty("next").GetString()!;
            if (leads is null)
                Assert.That(next, Does.StartWith("only these applications have a volume of their own"));
            else
                Assert.That(next, Does.StartWith(leads));
            Assert.That(aidOff.Result!.Value.GetProperty("next").GetString(),
                Does.StartWith("only these applications have a volume of their own"), "aid off");
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

    // Encargo 65 (cosecha F2, uso real 03-11): a request for the newest mail of one sender in a webmail read Outlook's
    // newest mail (another sender) and the answer said there was no mail from that sender. The receipt says what it read: the application
    // (readFrom), the account whose Inbox it is, and that it is that one newest mail, searched by no sender.
    [Test]
    public async Task TheLatestMailReadSaysWhoseInboxItReadAndThatItSearchesNoSender()
    {
        const string output = "{\"ok\":true,\"effectObserved\":false,\"entryId\":\"private-inbox-entry\"," +
            "\"subject\":\"Aviso\",\"sender\":\"avisos@example.test\",\"receivedUtc\":\"2026-11-02T10:26:00Z\"," +
            "\"body\":\"hola\",\"bodyLength\":4,\"account\":\"persona@example.test\"}";
        using TemporaryDirectory temporary = new();
        var runner = new StubProcessRunner(output);
        var adapter = new MicrosoftAccountAdapter(temporary.Path, runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "email.latest.read", Json("{}"), CancellationToken.None);

        string script = runner.LastArguments.Single(argument => argument.Contains("GetDefaultFolder(6)", StringComparison.Ordinal));
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("readFrom").GetString(), Is.EqualTo("Outlook"));
            Assert.That(receipt.Result?.GetProperty("account").GetString(), Is.EqualTo("persona@example.test"));
            Assert.That(receipt.Result?.GetProperty("covers").GetString(), Does.Contain("newest mail")
                .And.Contain("no sender"));
            Assert.That(script, Does.Contain("account=$account"));
        });
    }

    // Renew al máximo (w8): the reply is bound to the mail its yes named. The script compares the newest mail's opaque
    // id with expectedMessageId before Reply(); a newer mail sends nothing, and the receipt says so with no uncertainty.
    [Test]
    public async Task AReplyNamingAMailThatIsNoLongerTheNewestSendsNothingAndNamesTheNewest()
    {
        string named = OpaqueMail("inbox-entry-read-before");
        const string output = "{\"ok\":false,\"effectObserved\":false,\"error\":\"email_latest_changed\"," +
            "\"entryId\":\"inbox-entry-arrived-after\",\"subject\":\"Otro asunto\"," +
            "\"sender\":\"other@example.test\",\"receivedUtc\":\"2026-07-17T10:05:00Z\"}";
        using TemporaryDirectory temporary = new();
        var runner = new StubProcessRunner(output);
        var adapter = new MicrosoftAccountAdapter(temporary.Path, runner);

        ExternalCapabilityReceipt receipt;
        using (ModelAids.Use("all"))
        {
            receipt = await adapter.InvokeAsync(
                "email.latest.reply",
                Json("{\"text\":\"ok\",\"expectedMessageId\":\"" + named + "\"}"),
                CancellationToken.None);
        }

        string script = runner.LastArguments.Single(argument => argument.Contains(".Reply()", StringComparison.Ordinal));
        using JsonDocument input = JsonDocument.Parse(
            Encoding.UTF8.GetString(Convert.FromBase64String(runner.LastArguments[^1])));
        Assert.Multiple(() =>
        {
            Assert.That(input.RootElement.GetProperty("expectedMessageId").GetString(), Is.EqualTo(named));
            Assert.That(script.IndexOf("email_latest_changed", StringComparison.Ordinal),
                Is.LessThan(script.IndexOf(".Reply()", StringComparison.Ordinal)));
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("email_latest_changed"));
            JsonElement latest = receipt.Result!.Value.GetProperty("latest");
            Assert.That(latest.GetProperty("messageId").GetString(), Is.EqualTo(OpaqueMail("inbox-entry-arrived-after")));
            Assert.That(latest.GetProperty("sender").GetString(), Is.EqualTo("other@example.test"));
            Assert.That(receipt.Result.Value.GetProperty("expectedMessageId").GetString(), Is.EqualTo(named));
            Assert.That(receipt.Result.Value.GetProperty("next").GetString(), Does.StartWith("nothing was sent"));
            Assert.That(receipt.Result.Value.GetRawText(), Does.Not.Contain("inbox-entry-arrived-after"));
        });
    }

    // Renew al máximo (w8): before the yes, a reply that names no mail, or one that is not the newest, fails with the
    // newest mail's id; the one that names the newest goes on to ask.
    [TestCase(null, "email_reply_message_id_required")]
    [TestCase("inbox-entry-old", "email_latest_changed")]
    [TestCase("inbox-entry-newest", null)]
    public async Task AReplyIsBoundToTheNewestMailBeforeThePersonIsAsked(string? namedEntry, string? failure)
    {
        const string read = "{\"ok\":true,\"effectObserved\":false," +
            "\"entryId\":\"inbox-entry-newest\",\"subject\":\"Informe\"," +
            "\"sender\":\"sender@example.test\",\"receivedUtc\":\"2026-07-17T10:00:00Z\"," +
            "\"body\":\"Contenido privado\",\"bodyLength\":17}";
        using TemporaryDirectory temporary = new();
        var runner = new StubProcessRunner(read);
        var adapter = new MicrosoftAccountAdapter(temporary.Path, runner);
        string arguments = namedEntry is null
            ? "{\"text\":\"ok\"}"
            : "{\"text\":\"ok\",\"expectedMessageId\":\"" + OpaqueMail(namedEntry) + "\"}";

        ExternalCapabilityReceipt? found = await ((IExternalOperationAdapter)adapter).PreflightAsync(
            "email.latest.reply", Json(arguments), CancellationToken.None);

        using JsonDocument input = JsonDocument.Parse(
            Encoding.UTF8.GetString(Convert.FromBase64String(runner.LastArguments[^1])));
        Assert.Multiple(() =>
        {
            Assert.That(input.RootElement.GetProperty("action").GetString(), Is.EqualTo("read"));
            if (failure is null)
            {
                Assert.That(found, Is.Null);
                return;
            }

            Assert.That(found, Is.Not.Null);
            Assert.That(found!.ErrorCode, Is.EqualTo(failure));
            Assert.That(found.Verified || found.EffectObserved || found.EffectMayHaveOccurred, Is.False);
            Assert.That(found.Result!.Value.GetProperty("latest").GetProperty("messageId").GetString(),
                Is.EqualTo(OpaqueMail("inbox-entry-newest")));
            Assert.That(found.Result.Value.GetRawText(), Does.Not.Contain("Contenido privado"));
        });
    }

    [Test]
    public async Task AReplyWhoseExpectedMessageIdIsNotAMessageIdRunsNothing()
    {
        using TemporaryDirectory temporary = new();
        var runner = new ThrowingProcessRunner(new InvalidOperationException("must not run"));
        var adapter = new MicrosoftAccountAdapter(temporary.Path, runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "email.latest.reply",
            Json("""{"text":"ok","expectedMessageId":"the last one"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(runner.Calls, Is.Zero);
            Assert.That(receipt.ErrorCode, Is.EqualTo("email_message_id_invalid"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result!.Value.GetProperty("argument").GetString(), Is.EqualTo("expectedMessageId"));
            // Encargo 34: the read that gives it comes first, as the call the model makes.
            Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Is.EqualTo(
                "email_latest_read {} gives the messageId that expectedMessageId takes (email_ and 24 hex digits); this "
                + "call sent nothing"));
        });
    }

    private static string OpaqueMail(string entryId) => "email_"
        + Convert.ToHexStringLower(System.Security.Cryptography.SHA256.HashData(Encoding.UTF8.GetBytes(entryId)))[..24];

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

    // Renew al máximo (w5): an id no list of this Core gave (an older session's, or made up) was a bare «expired»; with
    // the aid identity_relist it says nothing was done and which list gives the ids. BAXY_AYUDAS=none: the code alone.
    // Encargo 34: the list that gives the ids comes first, as the call the model makes.
    [TestCase("all", "bluetooth.device.pair", """{"deviceId":"bluetooth_0000"}""", "bluetooth_identity_expired",
        "bluetooth_device_list {} gives the ids to use; this deviceId is not one bluetooth_device_list gave since BAXY "
        + "started, and nothing was paired")]
    [TestCase("all", "wifi.connect", """{"profileId":"wifi_0000"}""", "wifi_profile_identity_expired",
        "wifi_profile_list {} gives the ids to use; this profileId is not one wifi_profile_list gave since BAXY "
        + "started, and nothing was connected")]
    [TestCase("none", "bluetooth.device.pair", """{"deviceId":"bluetooth_0000"}""", "bluetooth_identity_expired", null)]
    public async Task AnIdNoListGaveSaysNothingWasDoneAndWhichListGivesOne(
        string aids, string operation, string arguments, string code, string? next)
    {
        using IDisposable setting = Baxy.Providers.Windows.Infrastructure.ModelAids.Use(aids);
        using TemporaryDirectory temporary = new();
        var runner = new StubProcessRunner("{}");
        var adapter = new WindowsDeviceControlAdapter(temporary.Path, temporary.Path, runner);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(code));
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(runner.LastArguments, Is.Empty, "nothing was run");
            Assert.That(receipt.Result is { } result && result.TryGetProperty("next", out JsonElement written)
                ? written.GetString() : null, Is.EqualTo(next));
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

    // Banco de uso 2026-11-03 (U05): with no Spotify on the PC the script launched «spotify:» and waited for a window that
    // never came, twice, about a minute. A PC where Windows has no handler for the client's protocol fails at once, before
    // anything runs, with its code and the fact that an audio file is opened with file_open.
    // Encargo 28 (U05): the calls that play it come first, the search written with the words asked; nothing ran, after.
    [TestCase("media.play.exact", """{"provider":"spotify","title":"Canción Inventada"}""",
        """file_find {"query":"Canción Inventada"} finds an audio file of this PC by that name and file_open plays it""")]
    [TestCase("media.play.query", """{"provider":"spotify","query":"canciones inventadas"}""",
        """file_find {"query":"canciones inventadas"} finds an audio file of this PC by those words and file_open plays it""")]
    public async Task SpotifyNotInstalledFailsAtOnceAndSaysHowAnAudioFileOpens(string operation, string arguments,
        string route)
    {
        var runner = new ThrowingProcessRunner(new InvalidOperationException("the script must not run"));
        var adapter = new SpotifyDesktopAdapter(runner, clientInstalled: static () => false);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(operation, Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("spotify_not_installed"));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(runner.Calls, Is.Zero);
            Assert.That(receipt.Result?.GetProperty("next").GetString(), Does.StartWith(route)
                .And.EndWith("; this call ran nothing: Spotify is not installed on this PC"));
        });
    }

    // Renew al máximo (auditoría de flujos): a search whose playback holds none of the words searched says so as a field
    // of its own (queryMatched:false), never only in the titles; a playback that holds one carries no such field.
    [TestCase("romeo santos propuesta indecente", "Propuesta Indecente - Spotify", false)]
    [TestCase("los bunkers bailando solo", "Los Bunkers - Spotify", true)]
    public async Task ASpotifySearchSaysWhenWhatPlaysHoldsNoneOfItsWords(
        string nowPlaying, string windowTitle, bool matched)
    {
        var adapter = new SpotifyDesktopAdapter(new StubProcessRunner(JsonSerializer.Serialize(new Dictionary<string, object>
        {
            ["ok"] = true,
            ["effectObserved"] = true,
            ["title"] = windowTitle,
            ["selectedControl"] = "Reproducir Bachata Clásica",
            ["observedNowPlaying"] = nowPlaying,
            ["playbackEvidence"] = "now_playing_changed",
            ["processId"] = 42,
        })));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.play.query", Json("""{"provider":"spotify","query":"otra de los Bunkers"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result!.Value.TryGetProperty("queryMatched", out JsonElement field), Is.EqualTo(!matched));
            if (!matched)
                Assert.That(field.ValueKind, Is.EqualTo(JsonValueKind.False));
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
    // Uso real 2026-10-26 («Pon una canción de Queen»): that same observation is
    // what a press that only resumed the loaded track shows. A now-playing line
    // unchanged by the press and holding no word of the search is not confirmed:
    // effect observed, what plays carried, never a success.
    [Test]
    public async Task SpotifyQueryPlaybackOfTheLineShownBeforeThePressIsNotConfirmed()
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
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo("spotify_query_result_not_confirmed"));
            Assert.That(receipt.Result?.GetProperty("title").GetString(),
                Is.EqualTo("Conep - After (feat. Young Miko)"));
            Assert.That(receipt.Result?.GetProperty("observedNowPlaying").GetString(),
                Is.EqualTo("after feat young miko de conep young miko"));
            Assert.That(receipt.Result?.TryGetProperty("playbackStatus", out _), Is.False);
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

    // Renew al máximo (auditoría de flujos): «siguiente canción» with nothing playing ended in
    // youtube_tab_action_unsupported, though there was no tab: the tab's refusal of a skip replaced the system's
    // «no session». With no tab of its own it stands aside for any action; with one, it says the skip is not its own
    // with the state it read, and nothing is sent.
    [TestCase(false, false, "youtube_tab_not_found", false, 0)]
    [TestCase(true, false, "youtube_tab_not_found", false, 1)]
    [TestCase(true, true, "youtube_tab_action_unsupported", true, 1)]
    public async Task ASkipTheTabCannotDoSaysWhetherThereIsATab(
        bool hasEndpoint, bool hasTab, string error, bool readState, int reads)
    {
        using TemporaryDirectory temporary = new();
        var browser = new StubYouTubeTabSession(
            temporary.Path,
            hasTab
                ? new CdpMediaControlResult(true, false, "status", "Lofi - YouTube",
                    "https://www.youtube.com/watch?v=abc", "t1", "playing", string.Empty)
                : null,
            hasEndpoint);
        using var http = new HttpClient();
        using var adapter = new WebBrowserAdapter(browser, http);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "media.control", Json("""{"action":"next"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(error));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result?.GetProperty("playbackStatus").GetString(),
                Is.EqualTo(readState ? "playing" : null));
            Assert.That(browser.Calls, Is.EqualTo(reads));
            Assert.That(browser.LastAction, Is.Null);
        });
    }

    [Test]
    public async Task ASkipWithNothingPlayingKeepsTheSystemSessionRead()
    {
        using TemporaryDirectory temporary = new();
        var session = new StubExternalAdapter(new ExternalCapabilityReceipt(
            "media.control", false, false, null, "media_session_not_found"));
        var browser = new StubYouTubeTabSession(temporary.Path, result: null, hasEndpoint: false);
        using var http = new HttpClient();
        var tab = new WebBrowserAdapter(browser, http);
        using var provider = new WindowsExternalCapabilityProvider([session, tab]);

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "media.control", Json("""{"action":"next"}"""), CancellationToken.None);

        Assert.That(receipt.ErrorCode, Is.EqualTo("media_session_not_found"));
    }

    // Banco ciego c3 (C3-078 s0/s2, «abre con foobar2000 … y ponlo a sonar»): media.control play with sourceApp
    // foobar2000 ended in the tab's «not the YouTube tab», which replaced what the system media session answered, and
    // the reply said foobar2000 was no YouTube player. The tab is not that source's player: what the session read stays.
    [TestCase("media_session_not_found")]
    [TestCase("smtc_session_access_failed")]
    [TestCase("media_control_action_invalid")]
    public async Task ANamedDesktopSourceKeepsTheSystemSessionAnswerOverTheTabsRefusal(string sessionError)
    {
        using TemporaryDirectory temporary = new();
        var session = new StubExternalAdapter(new ExternalCapabilityReceipt(
            "media.control", false, false, null, sessionError));
        var browser = new StubYouTubeTabSession(temporary.Path, result: null, hasEndpoint: true);
        using var http = new HttpClient();
        var tab = new WebBrowserAdapter(browser, http);
        using var provider = new WindowsExternalCapabilityProvider([session, tab]);

        ExternalCapabilityReceipt receipt = await provider.InvokeAsync(
            "media.control", Json("""{"action":"play","sourceApp":"foobar2000"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(sessionError));
            Assert.That(session.Calls, Is.EqualTo(1));
            Assert.That(browser.Calls, Is.Zero);
        });
    }

    // media.control's sourceApp names a player by the id media.status gave it, compared whole (BAXY Renew audit
    // 2026-10-15): the tab stands aside before any effect for any other, so «pausa Spotify» never pauses it, and a word
    // of the id is not the id.
    [TestCase("spotify", "media_source_app_not_youtube_tab")]
    [TestCase("youtube", "media_source_app_not_youtube_tab")]
    [TestCase(WindowsExternalCapabilityProvider.YouTubeTabMediaSource, "youtube_tab_not_found")]
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
        internal int Navigations { get; private set; }

        internal override ValueTask<CdpNavigationResult> NavigateAsync(
            Uri target, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            Navigations++;
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

    // A CDP socket that takes every command and never answers (a page held by alert()).
    private sealed class SilentWebSocket : System.Net.WebSockets.WebSocket
    {
        internal int Sent { get; private set; }

        internal bool Aborted { get; private set; }

        public override System.Net.WebSockets.WebSocketCloseStatus? CloseStatus => null;
        public override string? CloseStatusDescription => null;
        public override System.Net.WebSockets.WebSocketState State =>
            Aborted ? System.Net.WebSockets.WebSocketState.Aborted : System.Net.WebSockets.WebSocketState.Open;
        public override string? SubProtocol => null;
        public override void Abort() => Aborted = true;
        public override Task CloseAsync(System.Net.WebSockets.WebSocketCloseStatus closeStatus,
            string? statusDescription, CancellationToken cancellationToken) => Task.CompletedTask;
        public override Task CloseOutputAsync(System.Net.WebSockets.WebSocketCloseStatus closeStatus,
            string? statusDescription, CancellationToken cancellationToken) => Task.CompletedTask;
        public override void Dispose() { }

        public override async Task<System.Net.WebSockets.WebSocketReceiveResult> ReceiveAsync(
            ArraySegment<byte> buffer, CancellationToken cancellationToken)
        {
            await Task.Delay(Timeout.Infinite, cancellationToken);
            throw new InvalidOperationException("unreachable");
        }

        public override Task SendAsync(ArraySegment<byte> buffer, System.Net.WebSockets.WebSocketMessageType messageType,
            bool endOfMessage, CancellationToken cancellationToken)
        {
            Sent++;
            return Task.CompletedTask;
        }
    }

    private sealed class ThrowingPageSession(string profile, Exception failure) : CdpBrowserSession(profile)
    {
        internal override ValueTask<CdpPageReadResult> ReadPageAsync(
            int maximumCharacters, CancellationToken cancellationToken) => ValueTask.FromException<CdpPageReadResult>(failure);
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

        internal int NavigateCalls { get; private set; }

        // APP_MISSING952 (d2cf40e0c): a named navigation verifies the browser's
        // identity by the observed executable; a stub without one stays unverified.
        internal override string? ObservedExecutablePath => observedExecutablePath;

        internal override ValueTask<CdpNavigationResult> NavigateAsync(
            Uri target,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            NavigateCalls++;
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
        TimeSpan noted = default,
        TimeProvider? time = null) : IOpenedApplicationFocus
    {
        private bool _taken;

        internal int FrontCalls { get; private set; }

        internal List<bool> JudgedDrawn { get; } = [];

        public VisibleControlSurface.OpenedApplication? TakeOpened()
        {
            if (_taken)
                return null;
            _taken = true;
            DateTime at = (time ?? TimeProvider.System).GetUtcNow().UtcDateTime - noted;
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

    // A clock that moves only when the code under test waits on it: each wait advances it by its own length and ends
    // at once, so what the code decides from the time depends on its waits, never on how fast the machine runs it.
    private sealed class VirtualTime : TimeProvider
    {
        private DateTimeOffset _now = new(2026, 10, 25, 12, 0, 0, TimeSpan.Zero);

        public override DateTimeOffset GetUtcNow() => _now;

        public override long TimestampFrequency => TimeSpan.TicksPerSecond;

        public override long GetTimestamp() => _now.UtcTicks;

        public override ITimer CreateTimer(TimerCallback callback, object? state, TimeSpan dueTime, TimeSpan period)
        {
            Assert.That(period, Is.EqualTo(Timeout.InfiniteTimeSpan), "only one-shot waits");
            if (dueTime != Timeout.InfiniteTimeSpan)
            {
                _now += dueTime;
                callback(state);
            }

            return new Elapsed();
        }

        private sealed class Elapsed : ITimer
        {
            public bool Change(TimeSpan dueTime, TimeSpan period) => false;

            public void Dispose()
            {
            }

            public ValueTask DisposeAsync() => ValueTask.CompletedTask;
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

    // Renew al máximo (8.3): an output that keeps its level whatever it is set to.
    private sealed class StuckAudioEndpoint(string endpointId, float volume) : IWindowsAudioEndpoint
    {
        public string EndpointId { get; } = endpointId;
        public string? ReadDisplayName() => "Test stuck endpoint";
        public float ReadVolumeScalar() => volume;
        public bool ReadMuted() => false;
        public void SetVolumeScalar(float scalar, Guid eventContext) { }
        public void SetMuted(bool value, Guid eventContext) { }
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

    // Renew al máximo (8.3): the post-read after the kill throws; the read after it throws too, or finds the instance
    // still there, or not.
    private sealed class FlakyProcessTerminationPlatform(
        WindowsProcessIdentity identity, bool rereadThrows, bool stillThere) : IWindowsProcessTerminationPlatform
    {
        private int _snapshots;

        public IReadOnlyList<WindowsProcessIdentity> Snapshot(string processName) => ++_snapshots switch
        {
            1 => [identity],
            2 => throw new InvalidOperationException("simulated post-read failure"),
            _ when rereadThrows => throw new InvalidOperationException("simulated re-read failure"),
            _ => stillThere ? [identity] : [],
        };

        public WindowsProcessTermination Terminate(string processName, WindowsProcessIdentity identity) =>
            WindowsProcessTermination.KillSent;
    }

    private sealed class StubPowerTransitionPlatform(string authority, bool accepted, bool alreadyPending = false)
        : IWindowsPowerTransitionPlatform
    {
        internal string? RequestedAction { get; private set; }

        public WindowsPowerTransitionResult Request(string action)
        {
            RequestedAction = action;
            return new WindowsPowerTransitionResult(accepted, authority, alreadyPending);
        }
    }

    private sealed class WifiProcessRunner(bool startsConnected = false) : IExternalProcessRunner
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
            // Disconnected until this runner's connect ran (the adapter reads first).
            string output = script.Contains("show profiles", StringComparison.Ordinal)
                ? "{\"ok\":true,\"profiles\":[\"Casa\"]}"
                : startsConnected || ConnectCalls > 0 ? "{\"ok\":true,\"connected\":true,\"profile\":\"Casa\"}" : "{\"ok\":true,\"connected\":false,\"profile\":\"\"}";
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
                Assert.That(body, Does.Contain("vision-test"));
                // P2.17: the question goes as the click's does: a PNG at most 1280 wide (the projector reads it on the
                // CPU) and no thinking before the answer.
                Assert.That(body, Does.Contain("\"enable_thinking\":false"));
                using JsonDocument sent = JsonDocument.Parse(body);
                string url = sent.RootElement.GetProperty("messages")[0].GetProperty("content")[1]
                    .GetProperty("image_url").GetProperty("url").GetString()!;
                Assert.That(url, Does.StartWith("data:image/png;base64,"));
                byte[] png = Convert.FromBase64String(url["data:image/png;base64,".Length..]);
                Assert.That(System.Buffers.Binary.BinaryPrimitives.ReadInt32BigEndian(png.AsSpan(16, 4)),
                    Is.LessThanOrEqualTo(1280));
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
