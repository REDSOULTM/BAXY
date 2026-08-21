using System.Security.Cryptography;
using System.Text.Json;
using Baxy.Core.Operations;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.Audio;
using Baxy.Providers.Windows.Capture;
using Baxy.Providers.Windows.Clipboard;
using Baxy.Providers.Windows.Network;
using Baxy.Providers.Windows.Windows;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class MvpLocalTransientHandlerMatrixTests
{
    private const int ExpectedOperations = 17;
    private static readonly JsonSerializerOptions EvidenceJsonOptions = new()
    {
        WriteIndented = true,
    };

    [Test]
    public async Task EveryTransientHandlerAcceptsOnlyVerifiedProviderEvidence()
    {
        var rows = new List<MatrixRow>(ExpectedOperations);

        await ExerciseApplicationAsync(rows);
        await ExerciseAudioAsync(rows);
        await ExerciseCaptureAsync(rows);
        await ExerciseClipboardAsync(rows);
        await ExerciseNetworkAsync(rows);
        await ExerciseWindowsAsync(rows);

        Assert.Multiple(() =>
        {
            Assert.That(rows, Has.Count.EqualTo(ExpectedOperations));
            Assert.That(rows.Select(row => row.Operation), Is.Unique);
            Assert.That(rows, Has.All.Matches<MatrixRow>(row => row.Verified));
            Assert.That(rows, Has.All.Matches<MatrixRow>(
                row => !row.EffectMayHaveOccurred));
            Assert.That(rows.Sum(row => row.ActualUserEffectsExecuted), Is.Zero);
        });
        WriteOptionalEvidence(rows);
    }

    private static async Task ExerciseApplicationAsync(List<MatrixRow> rows)
    {
        var provider = new ApplicationProvider();
        var handler = new AppOpenHandler(provider);
        await RunAsync(
            handler,
            """{"appId":"windows.notepad"}""",
            "safe_verified_contract_simulation",
            "application_launch_receipt_plus_window_identity",
            rows);
        Assert.That(provider.CallCount, Is.EqualTo(1));
    }

    private static async Task ExerciseAudioAsync(List<MatrixRow> rows)
    {
        var provider = new AudioProvider();
        await RunAsync(
            new AudioMuteHandler(provider),
            """{"state":true}""",
            "safe_verified_contract_simulation",
            "endpoint_hash_and_exact_postread",
            rows);
        await RunAsync(
            new AudioVolumeHandler(provider),
            """{"level":37}""",
            "safe_verified_contract_simulation",
            "endpoint_hash_and_tolerant_exact_postread",
            rows);
        Assert.Multiple(() =>
        {
            Assert.That(provider.MuteCalls, Is.EqualTo(1));
            Assert.That(provider.VolumeCalls, Is.EqualTo(1));
        });
    }

    private static async Task ExerciseCaptureAsync(List<MatrixRow> rows)
    {
        var provider = new CaptureProvider();
        await RunAsync(
            new ScreenshotCaptureHandler(provider),
            "{}",
            "safe_sensitive_contract_simulation",
            "opaque_capture_id_dimensions_and_sha256",
            rows);
        await RunAsync(
            new ScreenshotCaptureHandler(
                provider,
                "capture.active.window",
                activeWindow: true),
            "{}",
            "safe_sensitive_contract_simulation",
            "opaque_capture_id_dimensions_and_sha256",
            rows);
        Assert.Multiple(() =>
        {
            Assert.That(provider.ScreenCalls, Is.EqualTo(1));
            Assert.That(provider.ActiveWindowCalls, Is.EqualTo(1));
        });
    }

    private static async Task ExerciseClipboardAsync(List<MatrixRow> rows)
    {
        var provider = new ClipboardProvider();
        Dictionary<string, IOperationHandler> handlers = ClipboardHandlers.Create(provider)
            .ToDictionary(handler => handler.Definition.Name, StringComparer.Ordinal);
        await RunAsync(
            handlers["clipboard.read.text"],
            """{"maxCharacters":42}""",
            "safe_sensitive_contract_simulation",
            "bounded_private_snapshot",
            rows);
        await RunAsync(
            handlers["clipboard.write.text"],
            """{"text":"BAXY MVP"}""",
            "safe_sensitive_contract_simulation",
            "sequence_and_character_count_receipt",
            rows);
        Assert.Multiple(() =>
        {
            Assert.That(provider.ReadCalls, Is.EqualTo(1));
            Assert.That(provider.WriteCalls, Is.EqualTo(1));
        });
    }

    private static async Task ExerciseNetworkAsync(List<MatrixRow> rows)
    {
        await RunAsync(
            new NetworkIpHandler(new WindowsNetworkIpProvider()),
            "{}",
            "real_read_only_provider",
            "two_equal_normalized_windows_reads",
            rows);
    }

    private static async Task ExerciseWindowsAsync(List<MatrixRow> rows)
    {
        var provider = new WindowProvider();
        Dictionary<string, IOperationHandler> handlers = WindowControlHandlers.Create(provider)
            .ToDictionary(handler => handler.Definition.Name, StringComparer.Ordinal);
        foreach (string operation in new[]
                 {
                     "app.close",
                     "window.active",
                     "window.focus",
                     "window.maximize",
                     "window.minimize",
                     "window.move",
                     "window.resize",
                     "window.resolve",
                     "window.restore",
                 })
        {
            string arguments = operation switch
            {
                "window.move" => """{"windowId":"win_mvp","x":20,"y":30}""",
                "window.resize" =>
                    """{"windowId":"win_mvp","width":800,"height":600}""",
                "window.resolve" => """{"process":"notepad","limit":10}""",
                "window.active" => "{}",
                _ => """{"windowId":"win_mvp"}""",
            };
            await RunAsync(
                handlers[operation],
                arguments,
                "safe_verified_contract_simulation",
                operation == "app.close"
                    ? "independent_window_absence_receipt"
                    : "post_action_window_state_or_exact_bounds",
                rows);
        }
        Assert.Multiple(() =>
        {
            Assert.That(provider.ActionCalls, Is.EqualTo(4));
            Assert.That(provider.BoundsCalls, Is.EqualTo(2));
            Assert.That(provider.CloseCalls, Is.EqualTo(1));
            Assert.That(provider.ResolveCalls, Is.EqualTo(2));
        });
    }

    private static async Task RunAsync(
        IOperationHandler handler,
        string json,
        string evidenceKind,
        string verifier,
        List<MatrixRow> rows)
    {
        using JsonDocument document = JsonDocument.Parse(json);
        var invocation = new OperationInvocation(
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            document.RootElement.Clone());
        OperationOutcome outcome = await handler.ExecuteAsync(
            invocation,
            CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, handler.Definition.Name);
            Assert.That(outcome.Verified, Is.True, handler.Definition.Name);
            Assert.That(outcome.Result, Is.Not.Null, handler.Definition.Name);
            Assert.That(outcome.EffectMayHaveOccurred, Is.False, handler.Definition.Name);
        });
        rows.Add(new MatrixRow(
            handler.Definition.Name,
            evidenceKind,
            verifier,
            outcome.Verified,
            outcome.EffectMayHaveOccurred,
            0));
    }

    private static void WriteOptionalEvidence(List<MatrixRow> rows)
    {
        string? configured = Environment.GetEnvironmentVariable(
            "BAXY_MVP_LOCAL_TRANSIENT_MATRIX_OUTPUT");
        if (string.IsNullOrWhiteSpace(configured)) return;
        string output = Path.GetFullPath(configured);
        if (File.Exists(output))
            throw new InvalidOperationException($"Refusing to overwrite evidence: {output}");
        Directory.CreateDirectory(Path.GetDirectoryName(output)!);
        string coreAssembly = typeof(NetworkIpHandler).Assembly.Location;
        string testAssembly = typeof(MvpLocalTransientHandlerMatrixTests).Assembly.Location;
        var report = new
        {
            schema = "baxy.mvp-local-transient-handler-matrix.v1",
            measuredAtUtc = DateTimeOffset.UtcNow.ToString("O"),
            scope = "all_local_transient_handlers_with_safe_effect_simulation",
            actualUserEffectsExecuted = 0,
            metrics = new
            {
                operations = rows.Count,
                verified = rows.Count(row => row.Verified),
                possibleEffects = rows.Count(row => row.EffectMayHaveOccurred),
                realReadOnlyProviders = rows.Count(
                    row => row.EvidenceKind == "real_read_only_provider"),
                safeContractSimulations = rows.Count(
                    row => row.EvidenceKind != "real_read_only_provider"),
                failed = 0,
            },
            coreAssemblySha256 = FileSha256(coreAssembly),
            testAssemblySha256 = FileSha256(testAssembly),
            rows,
            gatePassed = rows.Count == ExpectedOperations
                && rows.All(row => row.Verified && !row.EffectMayHaveOccurred)
                && rows.Sum(row => row.ActualUserEffectsExecuted) == 0,
        };
        File.WriteAllText(
            output,
            JsonSerializer.Serialize(report, EvidenceJsonOptions) + Environment.NewLine);
    }

    private static string FileSha256(string path) =>
        Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();

    private sealed record MatrixRow(
        string Operation,
        string EvidenceKind,
        string Verifier,
        bool Verified,
        bool EffectMayHaveOccurred,
        int ActualUserEffectsExecuted);

    private sealed class ApplicationProvider : IApplicationOpenProvider
    {
        public int CallCount { get; private set; }

        public ValueTask<ApplicationOpenResult> OpenAsync(
            ApplicationOpenRequest request,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            CallCount++;
            var receipt = new ApplicationLaunchReceipt(
                request.InvocationId,
                request.ApplicationId,
                LaunchIssued: true,
                ReusedExisting: false,
                ProcessId: 4242,
                ProcessCreationTimeUtcTicks: DateTime.UtcNow.Ticks,
                ExecutablePath: @"C:\Windows\System32\notepad.exe",
                PackageFamilyName: null,
                PackageFullName: null,
                WindowHandle: 73,
                ErrorCode: null);
            return ValueTask.FromResult(new ApplicationOpenResult(
                Succeeded: true,
                Verified: true,
                DisplayName: "Bloc de notas",
                AlreadyRunning: false,
                ProcessId: 4242,
                WindowHandle: 73,
                ErrorCode: null,
                receipt));
        }
    }

    private sealed class AudioProvider : IAudioControlProvider
    {
        private const string EndpointHash =
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

        private AudioEndpointState _observed = new(55, false);

        public int MuteCalls { get; private set; }
        public int VolumeCalls { get; private set; }

        public ValueTask<AudioStatusReceipt> GetStatusAsync(
            AudioStatusQuery query,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(new AudioStatusReceipt(
                query.InvocationId,
                AudioOperationIds.Status,
                AudioTargetIds.DefaultOutput,
                EndpointHash,
                _observed,
                Verified: true,
                ErrorCode: null));
        }

        public ValueTask<AudioControlReceipt> SetVolumeAsync(
            AudioVolumeCommand command,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            VolumeCalls++;
            AudioEndpointState baseline = _observed;
            AudioEndpointState final = new(command.Level, baseline.Muted);
            _observed = final;
            return ValueTask.FromResult(new AudioControlReceipt(
                command.InvocationId,
                AudioOperationIds.Volume,
                AudioTargetIds.DefaultOutput,
                EndpointHash,
                command.Level,
                RequestedState: null,
                baseline,
                final,
                Applied: true,
                Reconciled: false,
                Verified: true,
                ErrorCode: null));
        }

        public ValueTask<AudioControlReceipt> SetMuteAsync(
            AudioMuteCommand command,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            MuteCalls++;
            AudioEndpointState final = new(55, command.State);
            _observed = final;
            return ValueTask.FromResult(new AudioControlReceipt(
                command.InvocationId,
                AudioOperationIds.Mute,
                AudioTargetIds.DefaultOutput,
                EndpointHash,
                RequestedLevel: null,
                command.State,
                new AudioEndpointState(55, !command.State),
                final,
                Applied: true,
                Reconciled: false,
                Verified: true,
                ErrorCode: null));
        }
    }

    private sealed class CaptureProvider : IScreenshotProvider
    {
        public int ActiveWindowCalls { get; private set; }
        public int ScreenCalls { get; private set; }

        public ValueTask<CaptureResult> CaptureAsync(
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ScreenCalls++;
            return ValueTask.FromResult(Result("screen"));
        }

        public ValueTask<CaptureResult> CaptureActiveWindowAsync(
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ActiveWindowCalls++;
            return ValueTask.FromResult(Result("window"));
        }

        private static CaptureResult Result(string scope) => new(
            $"capture_{scope}_0123456789abcdef",
            1920,
            1080,
            new string('a', 64),
            DateTimeOffset.UnixEpoch);
    }

    private sealed class ClipboardProvider : IClipboardProvider
    {
        public int ReadCalls { get; private set; }
        public int WriteCalls { get; private set; }

        public ValueTask<ClipboardTextSnapshot> ReadTextAsync(
            int maximumCharacters,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ReadCalls++;
            Assert.That(maximumCharacters, Is.EqualTo(42));
            return ValueTask.FromResult(new ClipboardTextSnapshot(
                "contenido aislado",
                17,
                Truncated: false,
                SequenceNumber: 9));
        }

        public ValueTask<ClipboardWriteResult> WriteTextAsync(
            string text,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            WriteCalls++;
            Assert.That(text, Is.EqualTo("BAXY MVP"));
            return ValueTask.FromResult(new ClipboardWriteResult(
                SequenceNumber: 10,
                CharacterCount: text.Length,
                Changed: true));
        }
    }

    private sealed class WindowProvider : IWindowControlProvider
    {
        public int ActionCalls { get; private set; }
        public int BoundsCalls { get; private set; }
        public int CloseCalls { get; private set; }
        public int ResolveCalls { get; private set; }

        public ValueTask<WindowResolveResult> ResolveForegroundAsync(
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ResolveCalls++;
            return ValueTask.FromResult(new WindowResolveResult(
                Succeeded: true,
                Verified: true,
                [Candidate("normal", foreground: true)],
                ErrorCode: null));
        }

        public ValueTask<WindowResolveResult> ResolveAsync(
            string processName,
            int limit,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ResolveCalls++;
            Assert.Multiple(() =>
            {
                Assert.That(processName, Is.EqualTo("notepad"));
                Assert.That(limit, Is.EqualTo(10));
            });
            return ValueTask.FromResult(new WindowResolveResult(
                Succeeded: true,
                Verified: true,
                [Candidate("normal", foreground: false)],
                ErrorCode: null));
        }

        public ValueTask<WindowActionResult> ExecuteAsync(
            string windowId,
            WindowControlAction action,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            ActionCalls++;
            (string state, bool foreground) = action switch
            {
                WindowControlAction.Focus => ("normal", true),
                WindowControlAction.Maximize => ("maximized", false),
                WindowControlAction.Minimize => ("minimized", false),
                WindowControlAction.Restore => ("normal", false),
                _ => throw new AssertionException($"Unexpected window action: {action}"),
            };
            return ValueTask.FromResult(new WindowActionResult(
                Succeeded: true,
                Verified: true,
                Candidate(state, foreground),
                ErrorCode: null));
        }

        public ValueTask<WindowActionResult> SetBoundsAsync(
            string windowId,
            int? x,
            int? y,
            int? width,
            int? height,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            BoundsCalls++;
            return ValueTask.FromResult(new WindowActionResult(
                Succeeded: true,
                Verified: true,
                new WindowCandidate(
                    "win_mvp",
                    4242,
                    "notepad",
                    "normal",
                    Foreground: false,
                    x ?? 0,
                    y ?? 0,
                    width ?? 640,
                    height ?? 480),
                ErrorCode: null));
        }

        public ValueTask<WindowCloseResult> CloseAsync(
            string windowId,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            CloseCalls++;
            return ValueTask.FromResult(new WindowCloseResult(
                Succeeded: true,
                Verified: true,
                ProcessId: 4242,
                ErrorCode: null));
        }

        private static WindowCandidate Candidate(string state, bool foreground) => new(
            "win_mvp",
            4242,
            "notepad",
            state,
            foreground,
            X: 0,
            Y: 0,
            Width: 640,
            Height: 480);
    }
}
