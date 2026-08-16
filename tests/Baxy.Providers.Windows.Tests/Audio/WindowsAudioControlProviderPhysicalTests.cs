using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Providers.Windows.Audio;
using Microsoft.Win32.SafeHandles;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests.Audio;

[TestFixture]
[NonParallelizable]
public sealed class WindowsAudioControlProviderPhysicalTests
{
    [Test]
    [Explicit("Modifica y restaura el endpoint real mediante el baxy-core.exe NativeAOT indicado por BAXY_PHYSICAL_AUDIO_CORE_PATH.")]
    [Category("Physical")]
    public void NativeAotCoreAudioJsonlRoundTripReplaysWithoutAnotherEffectAndRestoresBaseline()
    {
        int endpointThreadId = Environment.CurrentManagedThreadId;
        string corePath = ResolveNativeAotCorePath();
        AssertNativeAotLifecyclePreflight(corePath);
        string dataDirectory = Path.Combine(
            Environment.GetFolderPath(
                Environment.SpecialFolder.LocalApplicationData,
                Environment.SpecialFolderOption.DoNotVerify),
            "BAXY",
            "physical-nativeaot-audio-" + Guid.NewGuid().ToString("N"));
        var platform = new WindowsCoreAudioPlatform();
        var endpointGuards = new List<EndpointRestoreGuard>();
        string missionId = NewId();
        string volumeInvocationId = NewId();
        string muteInvocationId = NewId();
        NativeAotCoreSession? core = null;
        EndpointRestoreGuard? baselineGuard = null;
        EndpointRestoreGuard? volumeGuard = null;
        EndpointRestoreGuard? muteGuard = null;
        string rawBaselineEndpointId = string.Empty;
        string baselineHash = string.Empty;
        float baselineScalar = float.NaN;
        bool baselineMuted = false;
        bool affectedEndpointCouldNotBeGuarded = false;
        bool coreTerminationCorroborated = true;
        var cleanupErrors = new List<Exception>();
        Exception? testFailure = null;

        try
        {
            baselineGuard = EndpointRestoreGuard.CaptureDefault(platform, endpointThreadId);
            endpointGuards.Add(baselineGuard);
            rawBaselineEndpointId = baselineGuard.RawEndpointId;
            baselineHash = baselineGuard.EndpointHash;
            baselineScalar = baselineGuard.RestoreScalar;
            baselineMuted = baselineGuard.RestoreMuted;
            int baselinePercent = PercentFromScalar(baselineScalar);
            int requestedPercent = baselinePercent <= 85
                ? baselinePercent + 10
                : baselinePercent - 10;
            bool requestedMuted = !baselineMuted;
            JsonElement volumeArguments = Parse($"{{\"level\":{requestedPercent}}}");
            JsonElement muteArguments = Parse(
                $"{{\"state\":{requestedMuted.ToString().ToLowerInvariant()}}}");

            TestContext.Progress.WriteLine(
                $"NativeAOT baseline endpointHash={baselineHash}, scalarR={baselineScalar:R}, volumePercent={baselinePercent}, muted={baselineMuted}.");

            core = NativeAotCoreSession.Start(
                corePath,
                dataDirectory,
                ref coreTerminationCorroborated);
            OperationDescriptor? volumeCapability = core.Hello.Capabilities.SingleOrDefault(
                static capability => capability.Name == AudioOperationIds.Volume);
            OperationDescriptor? muteCapability = core.Hello.Capabilities.SingleOrDefault(
                static capability => capability.Name == AudioOperationIds.Mute);
            Assert.Multiple(() =>
            {
                Assert.That(core.Hello.Type, Is.EqualTo(ProtocolTypes.Hello));
                Assert.That(core.Hello.Protocol, Is.EqualTo(ProtocolVersion.Current));
                Assert.That(volumeCapability, Is.Not.Null);
                Assert.That(volumeCapability?.Risk, Is.EqualTo(OperationRisks.LowReversible));
                Assert.That(muteCapability, Is.Not.Null);
                Assert.That(muteCapability?.Risk, Is.EqualTo(OperationRisks.LowReversible));
            });

            volumeGuard = EndpointRestoreGuard.CaptureDefault(platform, endpointThreadId);
            endpointGuards.Add(volumeGuard);
            Assert.That(
                volumeGuard.EndpointHash,
                Is.EqualTo(baselineHash),
                "The default output changed before volume; no audio operation was sent.");
            OperationRequest volumeRequest = Request(
                missionId,
                volumeInvocationId,
                AudioOperationIds.Volume,
                volumeArguments);
            OperationResponse volume = core.Send(volumeRequest);
            if (!TryGuardDurableAffectedEndpoint(
                    platform,
                    dataDirectory,
                    volumeInvocationId,
                    endpointGuards,
                    endpointThreadId))
            {
                affectedEndpointCouldNotBeGuarded = true;
                Assert.Fail(
                    "The default output changed during volume and the affected endpoint could not be retained for exact restoration; mute was not attempted.");
            }

            AudioInvocationState? volumeState = LoadDurableAudioState(
                dataDirectory,
                volumeInvocationId);
            Assert.That(volumeState, Is.Not.Null, "Volume did not persist its exact baseline.");
            Assert.That(
                volumeState!.EndpointIdHash,
                Is.EqualTo(volumeGuard.EndpointHash),
                "The default output changed during volume; mute was not attempted.");
            AssertCompletedAudioResponse(
                volume,
                AudioOperationIds.Volume,
                baselineHash,
                requestedPercent,
                baselineMuted,
                replayed: false);

            float scalarAfterVolume = volumeGuard.ReadVolumeScalar();
            bool mutedAfterVolume = volumeGuard.ReadMuted();
            Assert.Multiple(() =>
            {
                Assert.That(
                    Math.Abs(PercentFromScalar(scalarAfterVolume) - requestedPercent),
                    Is.LessThanOrEqualTo(WindowsAudioControlProvider.VolumeTolerancePoints));
                Assert.That(mutedAfterVolume, Is.EqualTo(baselineMuted));
            });
            TestContext.Progress.WriteLine(
                $"NativeAOT volume endpointHash={volumeState.EndpointIdHash}, baselineScalarR={volumeState.BaselineVolumeScalar:R}, baselinePercent={volumeState.Baseline.VolumePercent}, baselineMuted={volumeState.Baseline.Muted}, requested={requestedPercent}, final={RequiredFinalVolume(volume)}, applied={RequiredApplied(volume)}, replayed={volume.Replayed}. Physical scalarR={scalarAfterVolume:R}, percent={PercentFromScalar(scalarAfterVolume)}, muted={mutedAfterVolume}.");

            muteGuard = EndpointRestoreGuard.CaptureDefault(platform, endpointThreadId);
            endpointGuards.Add(muteGuard);
            Assert.Multiple(() =>
            {
                Assert.That(
                    muteGuard.EndpointHash,
                    Is.EqualTo(baselineHash),
                    "The default output changed before mute; mute was not sent.");
                Assert.That(
                    muteGuard.RestoreScalar,
                    Is.EqualTo(scalarAfterVolume).Within(0.0001f),
                    "Volume changed independently before mute; mute was not sent.");
                Assert.That(
                    muteGuard.RestoreMuted,
                    Is.EqualTo(baselineMuted),
                    "Mute changed independently before mute; mute was not sent.");
            });
            OperationRequest muteRequest = Request(
                missionId,
                muteInvocationId,
                AudioOperationIds.Mute,
                muteArguments);
            OperationResponse mute = core.Send(muteRequest);
            if (!TryGuardDurableAffectedEndpoint(
                    platform,
                    dataDirectory,
                    muteInvocationId,
                    endpointGuards,
                    endpointThreadId))
            {
                affectedEndpointCouldNotBeGuarded = true;
                Assert.Fail(
                    "The default output changed during mute and the affected endpoint could not be retained for exact restoration; replay was not attempted.");
            }

            AudioInvocationState? muteState = LoadDurableAudioState(
                dataDirectory,
                muteInvocationId);
            Assert.That(muteState, Is.Not.Null, "Mute did not persist its exact baseline.");
            Assert.That(
                muteState!.EndpointIdHash,
                Is.EqualTo(muteGuard.EndpointHash),
                "The default output changed during mute; replay was not attempted.");
            AssertCompletedAudioResponse(
                mute,
                AudioOperationIds.Mute,
                baselineHash,
                requestedPercent,
                requestedMuted,
                replayed: false);

            float scalarBeforeReplay = muteGuard.ReadVolumeScalar();
            bool mutedBeforeReplay = muteGuard.ReadMuted();
            Assert.Multiple(() =>
            {
                Assert.That(scalarBeforeReplay, Is.EqualTo(scalarAfterVolume).Within(0.0001f));
                Assert.That(mutedBeforeReplay, Is.EqualTo(requestedMuted));
            });
            TestContext.Progress.WriteLine(
                $"NativeAOT mute endpointHash={muteState.EndpointIdHash}, baselineScalarR={muteState.BaselineVolumeScalar:R}, baselinePercent={muteState.Baseline.VolumePercent}, baselineMuted={muteState.Baseline.Muted}, requested={requestedMuted}, final={RequiredFinalMuted(mute)}, applied={RequiredApplied(mute)}, replayed={mute.Replayed}. Physical scalarR={scalarBeforeReplay:R}, percent={PercentFromScalar(scalarBeforeReplay)}, muted={mutedBeforeReplay}.");

            using (EndpointRestoreGuard replayDefault = EndpointRestoreGuard.CaptureDefault(
                       platform,
                       endpointThreadId))
            {
                Assert.That(
                    replayDefault.EndpointHash,
                    Is.EqualTo(baselineHash),
                    "The default output changed before replay; replay was not sent.");
            }

            OperationResponse volumeReplay = core.Send(
                volumeRequest with { RequestId = NewId() });
            OperationResponse muteReplay = core.Send(
                muteRequest with { RequestId = NewId() });
            Assert.Multiple(() =>
            {
                Assert.That(volumeReplay.Status, Is.EqualTo(OperationStatuses.Completed));
                Assert.That(volumeReplay.Verified, Is.True);
                Assert.That(volumeReplay.Replayed, Is.True);
                Assert.That(volumeReplay.ErrorCode, Is.Null);
                Assert.That(
                    volumeReplay.Result?.GetRawText(),
                    Is.EqualTo(volume.Result?.GetRawText()));
                Assert.That(muteReplay.Status, Is.EqualTo(OperationStatuses.Completed));
                Assert.That(muteReplay.Verified, Is.True);
                Assert.That(muteReplay.Replayed, Is.True);
                Assert.That(muteReplay.ErrorCode, Is.Null);
                Assert.That(
                    muteReplay.Result?.GetRawText(),
                    Is.EqualTo(mute.Result?.GetRawText()));
                Assert.That(
                    muteGuard.ReadVolumeScalar(),
                    Is.EqualTo(scalarBeforeReplay).Within(0.0001f));
                Assert.That(muteGuard.ReadMuted(), Is.EqualTo(mutedBeforeReplay));
            });
            TestContext.Progress.WriteLine(
                $"NativeAOT replay endpointHash={baselineHash}, volumeReplayed={volumeReplay.Replayed}, muteReplayed={muteReplay.Replayed}, unchangedScalarR={muteGuard.ReadVolumeScalar():R}, unchangedPercent={PercentFromScalar(muteGuard.ReadVolumeScalar())}, unchangedMuted={muteGuard.ReadMuted()}.");

            using (IWindowsAudioEndpoint currentDefault = platform.OpenDefaultOutput())
            {
                AssertEndpointThread(endpointThreadId);
                Assert.Multiple(() =>
                {
                    Assert.That(
                        AudioEndpointIdentity.Hash(currentDefault.EndpointId),
                        Is.EqualTo(baselineHash));
                    Assert.That(
                        currentDefault.ReadVolumeScalar(),
                        Is.EqualTo(scalarBeforeReplay).Within(0.0001f));
                    Assert.That(currentDefault.ReadMuted(), Is.EqualTo(requestedMuted));
                });
            }

            core.Stop();
            AssertRawEndpointIdWasNotEmitted(core.StandardOutput, rawBaselineEndpointId);
            AssertRawEndpointIdWasNotEmitted(core.StandardError, rawBaselineEndpointId);
            string safeStandardError = SanitizeDiagnostic(
                core.StandardError,
                rawBaselineEndpointId);
            Assert.Multiple(() =>
            {
                Assert.That(
                    core.ExitCode,
                    Is.Zero,
                    $"NativeAOT core exit was not clean. stderr: {safeStandardError}");
                Assert.That(
                    core.StandardError,
                    Is.Empty,
                    $"NativeAOT core wrote stderr: {safeStandardError}");
            });
        }
        catch (Exception exception)
        {
            testFailure = exception;
        }
        finally
        {
            if (core is not null)
            {
                TryCleanup(core.Dispose, cleanupErrors);
                coreTerminationCorroborated = core.TerminationCorroborated;
            }

            try
            {
                if (!coreTerminationCorroborated)
                {
                    string stateDirectoryHash = AudioEndpointIdentity.Hash(dataDirectory);
                    cleanupErrors.Add(new InvalidOperationException(
                        "NativeAOT core termination was not corroborated; endpoint restoration "
                        + "and durable-state cleanup were intentionally skipped. "
                        + $"stateDirectoryHash={stateDirectoryHash}."));
                    TestContext.Progress.WriteLine(
                        "NativeAOT termination uncorroborated; restoration skipped, "
                        + $"stateDirectoryHash={stateDirectoryHash}.");
                }
                else
                {
                    int restorationErrorStart = cleanupErrors.Count;
                    if (!TryGuardDurableAffectedEndpointSafely(
                            platform,
                            dataDirectory,
                            volumeInvocationId,
                            endpointGuards,
                            endpointThreadId,
                            cleanupErrors)
                        || !TryGuardDurableAffectedEndpointSafely(
                            platform,
                            dataDirectory,
                            muteInvocationId,
                            endpointGuards,
                            endpointThreadId,
                            cleanupErrors))
                    {
                        affectedEndpointCouldNotBeGuarded = true;
                    }

                    for (int index = endpointGuards.Count - 1; index >= 0; index--)
                    {
                        EndpointRestoreGuard guard = endpointGuards[index];
                        TryCleanup(guard.Restore, cleanupErrors);
                    }

                    if (baselineGuard is not null)
                    {
                        try
                        {
                            float restoredScalar = baselineGuard.ReadVolumeScalar();
                            bool restoredMuted = baselineGuard.ReadMuted();
                            using IWindowsAudioEndpoint finalDefault = platform.OpenDefaultOutput();
                            AssertEndpointThread(endpointThreadId);
                            string finalHash = AudioEndpointIdentity.Hash(finalDefault.EndpointId);
                            float finalScalar = finalDefault.ReadVolumeScalar();
                            bool finalMuted = finalDefault.ReadMuted();
                            Assert.Multiple(() =>
                            {
                                Assert.That(
                                    restoredScalar,
                                    Is.EqualTo(baselineScalar).Within(0.0001f));
                                Assert.That(restoredMuted, Is.EqualTo(baselineMuted));
                                Assert.That(finalHash, Is.EqualTo(baselineHash));
                                Assert.That(
                                    finalScalar,
                                    Is.EqualTo(baselineScalar).Within(0.0001f));
                                Assert.That(finalMuted, Is.EqualTo(baselineMuted));
                            });
                            TestContext.Progress.WriteLine(
                                $"NativeAOT restore endpointHash={finalHash}, scalarR={finalScalar:R}, volumePercent={PercentFromScalar(finalScalar)}, muted={finalMuted}.");
                        }
                        catch (Exception exception)
                        {
                            cleanupErrors.Add(exception);
                        }
                    }

                    bool restorationCorroborated = !affectedEndpointCouldNotBeGuarded
                        && cleanupErrors.Count == restorationErrorStart;
                    if (restorationCorroborated)
                    {
                        try
                        {
                            if (Directory.Exists(dataDirectory))
                            {
                                Directory.Delete(dataDirectory, recursive: true);
                            }
                        }
                        catch (Exception exception)
                        {
                            cleanupErrors.Add(exception);
                        }
                    }
                    else
                    {
                        string stateDirectoryHash = AudioEndpointIdentity.Hash(dataDirectory);
                        cleanupErrors.Add(new InvalidOperationException(
                            "Durable audio state was retained because exact endpoint restoration "
                            + $"was not corroborated. stateDirectoryHash={stateDirectoryHash}."));
                    }
                }
            }
            finally
            {
                for (int index = endpointGuards.Count - 1; index >= 0; index--)
                {
                    EndpointRestoreGuard guard = endpointGuards[index];
                    TryCleanup(guard.Dispose, cleanupErrors);
                }
            }

            if (affectedEndpointCouldNotBeGuarded)
            {
                cleanupErrors.Add(new InvalidOperationException(
                    "An affected endpoint could not be retained for exact restoration."));
            }
        }

        if (cleanupErrors.Count > 0)
        {
            if (testFailure is not null)
            {
                cleanupErrors.Insert(0, testFailure);
            }

            throw new AggregateException(
                "NativeAOT physical audio cleanup was not fully corroborated.",
                cleanupErrors);
        }

        if (testFailure is not null)
        {
            System.Runtime.ExceptionServices.ExceptionDispatchInfo
                .Capture(testFailure)
                .Throw();
        }
    }

    private static void AssertNativeAotLifecyclePreflight(string corePath)
    {
        string dataDirectory = Path.Combine(
            Environment.GetFolderPath(
                Environment.SpecialFolder.LocalApplicationData,
                Environment.SpecialFolderOption.DoNotVerify),
            "BAXY",
            "physical-nativeaot-preflight-" + Guid.NewGuid().ToString("N"));
        NativeAotCoreSession? core = null;
        bool terminationCorroborated = true;
        Exception? preflightFailure = null;
        var cleanupErrors = new List<Exception>();
        try
        {
            core = NativeAotCoreSession.Start(
                corePath,
                dataDirectory,
                ref terminationCorroborated);
            core.Stop();
        }
        catch (Exception exception)
        {
            preflightFailure = exception;
        }
        finally
        {
            if (core is not null)
            {
                TryCleanup(core.Dispose, cleanupErrors);
                terminationCorroborated = core.TerminationCorroborated;
            }

            if (terminationCorroborated)
            {
                try
                {
                    if (Directory.Exists(dataDirectory))
                    {
                        Directory.Delete(dataDirectory, recursive: true);
                    }
                }
                catch (Exception exception)
                {
                    cleanupErrors.Add(exception);
                }
            }
            else
            {
                cleanupErrors.Add(new InvalidOperationException(
                    "NativeAOT termination preflight was not corroborated; no audio was touched. "
                    + $"stateDirectoryHash={AudioEndpointIdentity.Hash(dataDirectory)}."));
            }
        }

        if (preflightFailure is not null)
        {
            cleanupErrors.Insert(0, preflightFailure);
        }

        if (cleanupErrors.Count > 0)
        {
            throw new AggregateException(
                "NativeAOT termination preflight failed before physical audio access.",
                cleanupErrors);
        }

        TestContext.Progress.WriteLine(
            "NativeAOT termination preflight completed before physical audio access.");
    }

    private static void AssertCompletedAudioResponse(
        OperationResponse response,
        string operation,
        string endpointHash,
        int expectedVolume,
        bool expectedMuted,
        bool replayed)
    {
        Assert.That(response.Result, Is.Not.Null);
        JsonElement result = response.Result!.Value;
        JsonElement final = result.GetProperty("final");
        Assert.Multiple(() =>
        {
            Assert.That(response.Status, Is.EqualTo(OperationStatuses.Completed));
            Assert.That(response.Verified, Is.True);
            Assert.That(response.Replayed, Is.EqualTo(replayed));
            Assert.That(response.ErrorCode, Is.Null);
            Assert.That(result.GetProperty("operation").GetString(), Is.EqualTo(operation));
            Assert.That(
                result.GetProperty("targetId").GetString(),
                Is.EqualTo(AudioTargetIds.DefaultOutput));
            Assert.That(
                result.GetProperty("endpointIdHash").GetString(),
                Is.EqualTo(endpointHash));
            Assert.That(
                Math.Abs(final.GetProperty("volumePercent").GetInt32() - expectedVolume),
                Is.LessThanOrEqualTo(WindowsAudioControlProvider.VolumeTolerancePoints));
            Assert.That(final.GetProperty("muted").GetBoolean(), Is.EqualTo(expectedMuted));
            Assert.That(result.GetProperty("applied").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("reconciled").GetBoolean(), Is.False);
        });
    }

    private static int RequiredFinalVolume(OperationResponse response) =>
        response.Result!.Value
            .GetProperty("final")
            .GetProperty("volumePercent")
            .GetInt32();

    private static bool RequiredFinalMuted(OperationResponse response) =>
        response.Result!.Value
            .GetProperty("final")
            .GetProperty("muted")
            .GetBoolean();

    private static bool RequiredApplied(OperationResponse response) =>
        response.Result!.Value.GetProperty("applied").GetBoolean();

    private static AudioInvocationState? LoadDurableAudioState(
        string dataDirectory,
        string invocationId)
    {
        string stateDirectory = Path.Combine(
            dataDirectory,
            "audio",
            "control-state");
        return Directory.Exists(stateDirectory)
            ? new AudioInvocationStore(stateDirectory).Load(invocationId)
            : null;
    }

    private static bool TryGuardDurableAffectedEndpoint(
        WindowsCoreAudioPlatform platform,
        string dataDirectory,
        string invocationId,
        List<EndpointRestoreGuard> endpointGuards,
        int endpointThreadId)
    {
        AssertEndpointThread(endpointThreadId);
        AudioInvocationState? state = LoadDurableAudioState(dataDirectory, invocationId);
        if (state is null
            || endpointGuards.Any(guard =>
                string.Equals(
                    guard.EndpointHash,
                    state.EndpointIdHash,
                    StringComparison.Ordinal)))
        {
            return true;
        }

        IWindowsAudioEndpoint? affectedEndpoint = platform.OpenDefaultOutput();
        try
        {
            string affectedHash = AudioEndpointIdentity.Hash(affectedEndpoint.EndpointId);
            if (!string.Equals(
                    affectedHash,
                    state.EndpointIdHash,
                    StringComparison.Ordinal))
            {
                return false;
            }

            endpointGuards.Add(EndpointRestoreGuard.FromDurableBaseline(
                affectedEndpoint,
                affectedHash,
                state.BaselineVolumeScalar,
                state.Baseline.Muted,
                endpointThreadId));
            affectedEndpoint = null;
            return true;
        }
        finally
        {
            affectedEndpoint?.Dispose();
        }
    }

    private static bool TryGuardDurableAffectedEndpointSafely(
        WindowsCoreAudioPlatform platform,
        string dataDirectory,
        string invocationId,
        List<EndpointRestoreGuard> endpointGuards,
        int endpointThreadId,
        List<Exception> cleanupErrors)
    {
        try
        {
            return TryGuardDurableAffectedEndpoint(
                platform,
                dataDirectory,
                invocationId,
                endpointGuards,
                endpointThreadId);
        }
        catch (Exception exception)
        {
            cleanupErrors.Add(exception);
            return false;
        }
    }

    private static void TryCleanup(Action cleanup, List<Exception> cleanupErrors)
    {
        try
        {
            cleanup();
        }
        catch (Exception exception)
        {
            cleanupErrors.Add(exception);
        }
    }

    private static void AssertEndpointThread(int endpointThreadId)
    {
        if (Environment.CurrentManagedThreadId != endpointThreadId)
        {
            throw new InvalidOperationException(
                "Physical Core Audio access left its owning test thread.");
        }
    }

    private static string ResolveNativeAotCorePath()
    {
        string? configuredPath = Environment.GetEnvironmentVariable(
            "BAXY_PHYSICAL_AUDIO_CORE_PATH");
        Assert.That(
            configuredPath,
            Is.Not.Null.And.Not.Empty,
            "Set BAXY_PHYSICAL_AUDIO_CORE_PATH to the published baxy-core.exe before explicitly running this test.");
        string fullPath = Path.GetFullPath(configuredPath!);
        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(fullPath), Is.True, "The configured NativeAOT core does not exist.");
            Assert.That(
                Path.GetExtension(fullPath),
                Is.EqualTo(".exe").IgnoreCase,
                "BAXY_PHYSICAL_AUDIO_CORE_PATH must identify baxy-core.exe.");
        });
        return fullPath;
    }

    private static OperationRequest Request(
        string missionId,
        string invocationId,
        string operation,
        JsonElement arguments) =>
        new(
            ProtocolTypes.OperationRequest,
            NewId(),
            missionId,
            invocationId,
            operation,
            arguments);

    private static JsonElement Parse(string json) =>
        JsonDocument.Parse(json).RootElement.Clone();

    private static string NewId() => Guid.NewGuid().ToString("D");

    private static void AssertRawEndpointIdWasNotEmitted(
        string output,
        string rawEndpointId)
    {
        if (output.Contains(rawEndpointId, StringComparison.Ordinal))
        {
            Assert.Fail("NativeAOT core exposed the raw endpoint id in its redirected output.");
        }
    }

    private static string SanitizeDiagnostic(string diagnostic, string rawEndpointId)
    {
        string safe = diagnostic.Replace(
            rawEndpointId,
            "[raw-endpoint-id-redacted]",
            StringComparison.Ordinal);
        const int maximumDiagnosticCharacters = 2048;
        return safe.Length <= maximumDiagnosticCharacters
            ? safe
            : safe[..maximumDiagnosticCharacters] + "[truncated]";
    }

    private static int PercentFromScalar(float scalar) =>
        Math.Clamp(
            (int)Math.Round(scalar * 100f, MidpointRounding.AwayFromZero),
            0,
            100);

    private sealed class EndpointRestoreGuard : IDisposable
    {
        private IWindowsAudioEndpoint? _endpoint;
        private readonly int _endpointThreadId;

        private EndpointRestoreGuard(
            IWindowsAudioEndpoint endpoint,
            string endpointHash,
            float restoreScalar,
            bool restoreMuted,
            int endpointThreadId)
        {
            _endpoint = endpoint;
            EndpointHash = endpointHash;
            RestoreScalar = restoreScalar;
            RestoreMuted = restoreMuted;
            _endpointThreadId = endpointThreadId;
        }

        public string EndpointHash { get; }

        public string RawEndpointId => RequiredEndpoint().EndpointId;

        public float RestoreScalar { get; }

        public bool RestoreMuted { get; }

        public static EndpointRestoreGuard CaptureDefault(
            WindowsCoreAudioPlatform platform,
            int endpointThreadId)
        {
            AssertEndpointThread(endpointThreadId);
            IWindowsAudioEndpoint? endpoint = platform.OpenDefaultOutput();
            try
            {
                var guard = new EndpointRestoreGuard(
                    endpoint,
                    AudioEndpointIdentity.Hash(endpoint.EndpointId),
                    endpoint.ReadVolumeScalar(),
                    endpoint.ReadMuted(),
                    endpointThreadId);
                endpoint = null;
                return guard;
            }
            finally
            {
                endpoint?.Dispose();
            }
        }

        public static EndpointRestoreGuard FromDurableBaseline(
            IWindowsAudioEndpoint endpoint,
            string endpointHash,
            float restoreScalar,
            bool restoreMuted,
            int endpointThreadId)
        {
            AssertEndpointThread(endpointThreadId);
            return new EndpointRestoreGuard(
                endpoint,
                endpointHash,
                restoreScalar,
                restoreMuted,
                endpointThreadId);
        }

        public float ReadVolumeScalar()
        {
            AssertEndpointThread(_endpointThreadId);
            return RequiredEndpoint().ReadVolumeScalar();
        }

        public bool ReadMuted()
        {
            AssertEndpointThread(_endpointThreadId);
            return RequiredEndpoint().ReadMuted();
        }

        public void Restore()
        {
            AssertEndpointThread(_endpointThreadId);
            IWindowsAudioEndpoint endpoint = RequiredEndpoint();
            Guid restoreContext = Guid.NewGuid();
            endpoint.SetMuted(true, restoreContext);
            endpoint.SetVolumeScalar(RestoreScalar, restoreContext);
            endpoint.SetMuted(RestoreMuted, restoreContext);

            float restoredScalar = endpoint.ReadVolumeScalar();
            bool restoredMuted = endpoint.ReadMuted();
            Assert.Multiple(() =>
            {
                Assert.That(
                    restoredScalar,
                    Is.EqualTo(RestoreScalar).Within(0.0001f));
                Assert.That(restoredMuted, Is.EqualTo(RestoreMuted));
            });
        }

        public void Dispose()
        {
            AssertEndpointThread(_endpointThreadId);
            IWindowsAudioEndpoint? endpoint = Interlocked.Exchange(ref _endpoint, null);
            endpoint?.Dispose();
        }

        private IWindowsAudioEndpoint RequiredEndpoint() =>
            _endpoint
            ?? throw new ObjectDisposedException(nameof(EndpointRestoreGuard));
    }

    private sealed class KillOnCloseJob : IDisposable
    {
        private const uint JobObjectLimitActiveProcess = 0x00000008;
        private const uint JobObjectLimitKillOnJobClose = 0x00002000;
        private const int JobObjectExtendedLimitInformation = 9;
        private SafeFileHandle? _handle;

        private KillOnCloseJob(SafeFileHandle handle)
        {
            _handle = handle;
        }

        public static KillOnCloseJob Create()
        {
            SafeFileHandle handle = CreateJobObjectW(IntPtr.Zero, null);
            if (handle.IsInvalid)
            {
                throw new System.ComponentModel.Win32Exception(
                    Marshal.GetLastWin32Error(),
                    "The physical-test kill-on-close Job could not be created.");
            }

            var information = new JobObjectExtendedLimitInformationNative
            {
                BasicLimitInformation = new JobObjectBasicLimitInformationNative
                {
                    LimitFlags = JobObjectLimitActiveProcess
                        | JobObjectLimitKillOnJobClose,
                    ActiveProcessLimit = 1,
                },
            };
            uint length = checked((uint)Marshal.SizeOf<JobObjectExtendedLimitInformationNative>());
            if (!SetInformationJobObject(
                    handle,
                    JobObjectExtendedLimitInformation,
                    ref information,
                    length))
            {
                int error = Marshal.GetLastWin32Error();
                handle.Dispose();
                throw new System.ComponentModel.Win32Exception(
                    error,
                    "The physical-test kill-on-close Job could not be configured.");
            }

            return new KillOnCloseJob(handle);
        }

        public void Assign(Process process)
        {
            ArgumentNullException.ThrowIfNull(process);
            SafeFileHandle handle = _handle
                ?? throw new ObjectDisposedException(nameof(KillOnCloseJob));
            if (!AssignProcessToJobObject(handle, process.Handle))
            {
                throw new System.ComponentModel.Win32Exception(
                    Marshal.GetLastWin32Error(),
                    "NativeAOT core could not be assigned to the physical-test Job.");
            }
        }

        public void Dispose() =>
            Interlocked.Exchange(ref _handle, null)?.Dispose();

        [DllImport("kernel32.dll", EntryPoint = "CreateJobObjectW", SetLastError = true)]
        private static extern SafeFileHandle CreateJobObjectW(
            IntPtr jobAttributes,
            [MarshalAs(UnmanagedType.LPWStr)] string? name);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool SetInformationJobObject(
            SafeFileHandle job,
            int informationClass,
            ref JobObjectExtendedLimitInformationNative information,
            uint informationLength);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool AssignProcessToJobObject(
            SafeFileHandle job,
            IntPtr process);

        [StructLayout(LayoutKind.Sequential)]
        private struct JobObjectBasicLimitInformationNative
        {
            public long PerProcessUserTimeLimit;
            public long PerJobUserTimeLimit;
            public uint LimitFlags;
            public UIntPtr MinimumWorkingSetSize;
            public UIntPtr MaximumWorkingSetSize;
            public uint ActiveProcessLimit;
            public UIntPtr Affinity;
            public uint PriorityClass;
            public uint SchedulingClass;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct IoCountersNative
        {
            public ulong ReadOperationCount;
            public ulong WriteOperationCount;
            public ulong OtherOperationCount;
            public ulong ReadTransferCount;
            public ulong WriteTransferCount;
            public ulong OtherTransferCount;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct JobObjectExtendedLimitInformationNative
        {
            public JobObjectBasicLimitInformationNative BasicLimitInformation;
            public IoCountersNative IoInfo;
            public UIntPtr ProcessMemoryLimit;
            public UIntPtr JobMemoryLimit;
            public UIntPtr PeakProcessMemoryUsed;
            public UIntPtr PeakJobMemoryUsed;
        }
    }

    private sealed class NativeAotCoreSession : IDisposable
    {
        private static readonly TimeSpan IoTimeout = TimeSpan.FromSeconds(10);
        private static readonly TimeSpan ShutdownTimeout = TimeSpan.FromSeconds(5);
        private readonly Process _process;
        private readonly Task<string> _standardError;
        private readonly StringBuilder _standardOutput = new();
        private KillOnCloseJob? _job;
        private Task<string>? _standardOutputTail;
        private bool _inputClosed;
        private bool _stopped;

        private NativeAotCoreSession(
            Process process,
            KillOnCloseJob job,
            Task<string> standardError,
            ProtocolHello hello,
            string helloLine)
        {
            _process = process;
            _job = job;
            _standardError = standardError;
            Hello = hello;
            AppendOutput(helloLine);
        }

        public ProtocolHello Hello { get; }

        public int? ExitCode { get; private set; }

        public bool TerminationCorroborated { get; private set; }

        public string StandardError { get; private set; } = string.Empty;

        public string StandardOutput => _standardOutput.ToString();

        public static NativeAotCoreSession Start(
            string corePath,
            string dataDirectory,
            ref bool terminationCorroboratedOnFailure)
        {
            terminationCorroboratedOnFailure = true;
            var startInfo = new ProcessStartInfo
            {
                FileName = corePath,
                WorkingDirectory = Path.GetDirectoryName(corePath)!,
                UseShellExecute = false,
                RedirectStandardInput = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
                StandardInputEncoding = new UTF8Encoding(false, true),
                StandardOutputEncoding = new UTF8Encoding(false, true),
                StandardErrorEncoding = new UTF8Encoding(false, true),
            };
            startInfo.Environment["BAXY_DATA_DIR"] = dataDirectory;
            startInfo.Environment["DOTNET_NOLOGO"] = "1";

            KillOnCloseJob startupJob = KillOnCloseJob.Create();
            var process = new Process { StartInfo = startInfo };
            Task<string>? standardError = null;
            bool processStarted = false;
            try
            {
                processStarted = process.Start();
                Assert.That(processStarted, Is.True, "NativeAOT core did not start.");
                terminationCorroboratedOnFailure = false;
                startupJob.Assign(process);
                standardError = process.StandardError.ReadToEndAsync();
                string helloLine = ReadRequiredLine(process);
                ProtocolHello hello = ProtocolJson.DeserializeHello(
                    Encoding.UTF8.GetBytes(helloLine));
                return new NativeAotCoreSession(
                    process,
                    startupJob,
                    standardError,
                    hello,
                    helloLine);
            }
            catch
            {
                if (processStarted)
                {
                    try
                    {
                        process.StandardInput.Close();
                    }
                    catch (Exception exception) when (
                        exception is InvalidOperationException
                            or IOException
                            or ObjectDisposedException)
                    {
                    }
                }

                startupJob.Dispose();
                terminationCorroboratedOnFailure = !processStarted
                    || TerminateProcessAndCorroborate(process);
                if (standardError is not null)
                {
                    try
                    {
                        _ = standardError
                            .WaitAsync(IoTimeout)
                            .GetAwaiter()
                            .GetResult();
                    }
                    catch (Exception exception) when (
                        exception is TimeoutException
                            or IOException
                            or ObjectDisposedException)
                    {
                    }
                }

                if (terminationCorroboratedOnFailure)
                {
                    process.Dispose();
                }

                throw;
            }
        }

        public OperationResponse Send(OperationRequest request)
        {
            byte[] payload = ProtocolJson.SerializeToUtf8Bytes(request);
            string line = Encoding.UTF8.GetString(payload);
            _process.StandardInput
                .WriteLineAsync(line)
                .WaitAsync(IoTimeout)
                .GetAwaiter()
                .GetResult();
            _process.StandardInput
                .FlushAsync()
                .WaitAsync(IoTimeout)
                .GetAwaiter()
                .GetResult();

            string responseLine = ReadRequiredLine(_process);
            AppendOutput(responseLine);
            using JsonDocument document = JsonDocument.Parse(responseLine);
            if (!document.RootElement.TryGetProperty("type", out JsonElement type)
                || type.GetString() != ProtocolTypes.OperationResponse)
            {
                Assert.Fail("NativeAOT core emitted a non-response JSONL record.");
            }

            OperationResponse response = ProtocolJson.DeserializeResponse(
                Encoding.UTF8.GetBytes(responseLine));
            Assert.Multiple(() =>
            {
                Assert.That(response.RequestId, Is.EqualTo(request.RequestId));
                Assert.That(response.MissionId, Is.EqualTo(request.MissionId));
                Assert.That(response.InvocationId, Is.EqualTo(request.InvocationId));
            });
            return response;
        }

        public void Stop()
        {
            if (_stopped)
            {
                return;
            }

            Exception? outputCaptureError = null;
            try
            {
                _standardOutputTail ??= _process.StandardOutput.ReadToEndAsync();
            }
            catch (Exception exception) when (
                exception is InvalidOperationException
                    or IOException
                    or ObjectDisposedException)
            {
                outputCaptureError = exception;
            }

            if (!_inputClosed)
            {
                _inputClosed = true;
                try
                {
                    _process.StandardInput.Close();
                }
                catch (Exception exception) when (
                    exception is IOException or ObjectDisposedException)
                {
                }
            }

            EnsureProcessExited();
            TerminationCorroborated = true;

            if (_standardOutputTail is null)
            {
                try
                {
                    _standardOutputTail = _process.StandardOutput.ReadToEndAsync();
                }
                catch (Exception exception) when (
                    exception is InvalidOperationException
                        or IOException
                        or ObjectDisposedException)
                {
                    outputCaptureError ??= exception;
                }
            }

            if (_standardOutputTail is not null)
            {
                try
                {
                    string tail = _standardOutputTail
                        .WaitAsync(IoTimeout)
                        .GetAwaiter()
                        .GetResult();
                    if (tail.Length > 0)
                    {
                        _standardOutput.Append(tail);
                    }
                }
                catch (Exception exception) when (
                    exception is InvalidOperationException
                        or IOException
                        or ObjectDisposedException
                        or TimeoutException)
                {
                    outputCaptureError ??= exception;
                }
            }

            StandardError = _standardError
                .WaitAsync(IoTimeout)
                .GetAwaiter()
                .GetResult();
            ExitCode = _process.ExitCode;
            _stopped = true;
            if (outputCaptureError is not null)
            {
                throw new InvalidOperationException(
                    "NativeAOT core stdout could not be captured completely after bounded shutdown.",
                    outputCaptureError);
            }
        }

        public void Dispose()
        {
            try
            {
                Stop();
            }
            finally
            {
                Interlocked.Exchange(ref _job, null)?.Dispose();
                if (!TerminationCorroborated)
                {
                    var finalWaitErrors = new List<Exception>();
                    TerminationCorroborated = WaitForCorroboratedExit(
                        _process,
                        ShutdownTimeout,
                        finalWaitErrors);
                }

                if (TerminationCorroborated)
                {
                    _process.Dispose();
                }
            }
        }

        private void EnsureProcessExited()
        {
            var terminationErrors = new List<Exception>();
            if (WaitForCorroboratedExit(
                    _process,
                    ShutdownTimeout,
                    terminationErrors))
            {
                return;
            }

            TryKill(_process, entireProcessTree: true, terminationErrors);
            if (WaitForCorroboratedExit(
                    _process,
                    ShutdownTimeout,
                    terminationErrors))
            {
                return;
            }

            TryKill(_process, entireProcessTree: false, terminationErrors);
            if (WaitForCorroboratedExit(
                    _process,
                    ShutdownTimeout,
                    terminationErrors))
            {
                return;
            }

            Interlocked.Exchange(ref _job, null)?.Dispose();
            if (WaitForCorroboratedExit(
                    _process,
                    ShutdownTimeout,
                    terminationErrors))
            {
                return;
            }

            terminationErrors.Add(new TimeoutException(
                "NativeAOT core remained alive after graceful shutdown, process kills, "
                + "and kill-on-close Job termination."));
            throw new AggregateException(
                "NativeAOT core termination could not be corroborated.",
                terminationErrors);
        }

        private static bool WaitForCorroboratedExit(
            Process process,
            TimeSpan timeout,
            List<Exception> errors)
        {
            try
            {
                if (process.HasExited)
                {
                    return true;
                }

                int timeoutMilliseconds = checked((int)Math.Ceiling(
                    timeout.TotalMilliseconds));
                return process.WaitForExit(timeoutMilliseconds)
                    && process.HasExited;
            }
            catch (Exception exception) when (
                exception is TimeoutException
                    or InvalidOperationException
                    or System.ComponentModel.Win32Exception)
            {
                errors.Add(exception);
                return false;
            }
        }

        private static void TryKill(
            Process process,
            bool entireProcessTree,
            List<Exception> errors)
        {
            try
            {
                if (!process.HasExited)
                {
                    process.Kill(entireProcessTree);
                }
            }
            catch (Exception exception) when (
                exception is InvalidOperationException
                    or System.ComponentModel.Win32Exception)
            {
                errors.Add(exception);
            }
        }

        private static string ReadRequiredLine(Process process)
        {
            string? line = process.StandardOutput
                .ReadLineAsync()
                .WaitAsync(IoTimeout)
                .GetAwaiter()
                .GetResult();
            if (line is null)
            {
                throw new EndOfStreamException(
                    "NativeAOT core closed stdout before the required JSONL record.");
            }

            return line;
        }

        private static bool TerminateProcessAndCorroborate(Process process)
        {
            var errors = new List<Exception>();
            if (WaitForCorroboratedExit(process, ShutdownTimeout, errors))
            {
                return true;
            }

            TryKill(process, entireProcessTree: true, errors);
            if (WaitForCorroboratedExit(process, ShutdownTimeout, errors))
            {
                return true;
            }

            TryKill(process, entireProcessTree: false, errors);
            return WaitForCorroboratedExit(process, ShutdownTimeout, errors);
        }

        private void AppendOutput(string line)
        {
            _standardOutput.Append(line);
            _standardOutput.Append('\n');
        }
    }

}
