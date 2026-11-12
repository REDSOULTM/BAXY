using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Windows.Threading;

namespace Baxy.App;

/// <summary>
/// The benches' driver: starts the same <see cref="MainWindowViewModel"/> the window uses, without the window, sends the
/// turns of a file (the person's words, or their Sí/No on a pending confirmation) and writes everything that happened as
/// JSON lines: each line BAXY published, each call the model made with its status and verification, the notice of a
/// silent turn once the voice queued it, when the voice started to speak (the notice's utterance marked
/// <c>notice</c>), and how each turn ended.
/// <para>
/// Usage: <c>Baxy.exe --conductor [--profile DIR] [--capture DIR] (--turns-file FILE | --text TEXT | --command-dir DIR)
/// [--timeout-ms N]</c>. A turns file has one JSON object per line: <c>{"text":"…"}</c> or <c>{"confirm":true}</c>
/// (a bare line is text). With a command directory the benches drive one running product case after case: they drop
/// <c>00001.json</c>, <c>00002.json</c>… there (a turn as above, <c>{"beat":{…moment…}}</c>, <c>{"session":"new"}</c> or
/// <c>{"exit":true}</c>) and
/// read the events this writes; each command ends with its <c>command.done</c>.
/// </para>
/// </summary>
internal static class ProductConductorHost
{
    internal const string Argument = "--conductor";

    // After the turn ends, how long the conductor waits for the voice to start saying its response (not the notice).
    private static readonly TimeSpan SpeechWait = TimeSpan.FromSeconds(10);

    // Uso 84 (AMD RX 7600, 2026-11-04): the conductor gave the mind a fixed 180 s, and a cold start that read its prompt
    // prefix in 167.5 s nearly ran it out; a slower GPU would have been a blocked environment. While the App says the
    // mind is preparing (its own start waits as long as the model advances, MindSidecarClient.TryStartAsync), the
    // conductor waits; after it, this grace is left for the App's own retry of a start that failed.
    internal static readonly TimeSpan MindGrace = TimeSpan.FromSeconds(180);

    /// <summary>The conductor's deadline for the mind: <see cref="MindGrace"/> from now while it is preparing.</summary>
    internal static DateTime MindDeadline(DateTime deadline, DateTime now, bool preparing) =>
        preparing ? now + MindGrace : deadline;

    internal static bool IsRequested(IReadOnlyList<string> arguments)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        return arguments.Any(static argument => string.Equals(argument, Argument, StringComparison.OrdinalIgnoreCase));
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AttachConsole(int dwProcessId);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AllocConsole();

    private const int AttachParentProcess = -1;

    internal static async Task<int> RunAsync(IReadOnlyList<string> arguments, Dispatcher dispatcher)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        ArgumentNullException.ThrowIfNull(dispatcher);
        EnsureConsole();
        ConductorArguments parsed = ConductorArguments.Parse(arguments);
        Directory.CreateDirectory(parsed.ProfileDirectory);
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", parsed.ProfileDirectory);
        Environment.SetEnvironmentVariable("BAXY_VOICE_WAKE_ON_START", "0");
        // Steam (2026-11-04): the profile's choice of language, as the window takes it (PresenceHost); a bench writes
        // «es» there so a Windows in English measures what one in Spanish does (bench_e2e.py, pin_spanish).
        UiLanguage.Use(FieldSettings.CreateDefault().Language);
        StreamWriter? capture = null;
        if (!string.IsNullOrWhiteSpace(parsed.CaptureDirectory))
        {
            Directory.CreateDirectory(parsed.CaptureDirectory);
            capture = new StreamWriter(Path.Combine(parsed.CaptureDirectory, "events.jsonl"), append: false,
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: false)) { AutoFlush = true };
        }

        using var lifetime = new CancellationTokenSource();
        Console.CancelKeyPress += (_, eventArgs) =>
        {
            eventArgs.Cancel = true;
            lifetime.Cancel();
        };

        var clock = Stopwatch.StartNew();
        void Emit(JsonObject entry)
        {
            entry["t_ms"] = clock.ElapsedMilliseconds;
            string line = entry.ToJsonString();
            Console.Out.WriteLine(line);
            capture?.WriteLine(line);
        }

        await using MainWindowViewModel viewModel = MainWindowViewModel.ForThisPc();
        await using var telemetry = new FieldTelemetrySampler(() => viewModel.MindProcessId);
        await using FieldProductChannel view = Mount(viewModel, telemetry, lifetime.Token);
        long turnStartedMs = 0;
        // Renew al máximo: the voice says which utterance is the notice (VoiceSounded); the order of the notice's
        // acceptance and the voice's start did not (ConductorUtterances).
        var utterances = new ConductorUtterances();
        viewModel.MessageAdded += message =>
        {
            if (!message.IsUser)
            {
                utterances.Published(message.Body);
            }

            Emit(new JsonObject
            {
            ["type"] = "message",
            ["speaker"] = message.IsUser ? "person" : "baxy",
            ["route"] = message.Route,
            ["body"] = message.Body,
            ["since_turn_ms"] = clock.ElapsedMilliseconds - turnStartedMs,
            });
        };
        viewModel.NoticeQueued += notice => Emit(new JsonObject
        {
            ["type"] = "notice.queued",
            ["text"] = notice,
            ["since_turn_ms"] = clock.ElapsedMilliseconds - turnStartedMs,
        });
        viewModel.StepCompleted += step => Emit(new JsonObject
        {
            ["type"] = "step",
            ["operation"] = step.Operation,
            ["arguments"] = step.Arguments.DeepClone(),
            ["status"] = step.Status,
            ["verified"] = step.Verified,
            ["error"] = step.ErrorCode,
            ["elapsed_ms"] = step.ElapsedMs,
            ["since_turn_ms"] = clock.ElapsedMilliseconds - turnStartedMs,
            // What the model read back: the benches audit every claim against it and the journal.
            ["observation"] = step.Observation,
        });
        // Each utterance's start (its first sound, with the line it says: the notice, or the last one BAXY published)
        // and its end.
        viewModel.VoiceSounded += notice =>
        {
            long since = clock.ElapsedMilliseconds - turnStartedMs;
            (string text, bool isNotice) = utterances.Sounded(since, notice);
            Emit(new JsonObject
            {
                ["type"] = "speech.start",
                ["text"] = text,
                ["notice"] = isNotice,
                ["since_turn_ms"] = since,
            });
        };
        viewModel.PropertyChanged += (_, change) =>
        {
            if (change.PropertyName != nameof(MainWindowViewModel.IsVoiceSpeaking) || viewModel.IsVoiceSpeaking)
            {
                return;
            }

            Emit(new JsonObject
            {
                ["type"] = "speech.end",
                ["text"] = utterances.Current.Text,
                ["notice"] = utterances.Current.Notice,
                ["since_turn_ms"] = clock.ElapsedMilliseconds - turnStartedMs,
            });
        };

        try
        {
            Emit(new JsonObject { ["type"] = "meta", ["profile"] = parsed.ProfileDirectory });
            await viewModel.InitializeAsync(lifetime.Token).ConfigureAwait(true);
            DateTime mindDeadline = DateTime.UtcNow + MindGrace;
            while ((!viewModel.IsMindReady || viewModel.IsMindPreparing) && !viewModel.HasStartupError
                && viewModel.Failure != MainWindowViewModel.NoSupportedGpu
                && DateTime.UtcNow < mindDeadline)
            {
                await Task.Delay(TimeSpan.FromMilliseconds(200), lifetime.Token).ConfigureAwait(true);
                mindDeadline = MindDeadline(mindDeadline, DateTime.UtcNow, viewModel.IsMindPreparing);
            }

            Emit(new JsonObject
            {
                ["type"] = "runtime",
                ["ready"] = viewModel.IsReady,
                ["mindReady"] = viewModel.IsMindReady,
                ["startupError"] = viewModel.HasStartupError,
                ["failure"] = viewModel.Failure,
                ["status"] = viewModel.StatusDescription,
            });
            if (!viewModel.IsReady || !viewModel.IsMindReady)
            {
                Emit(new JsonObject { ["type"] = "terminal", ["kind"] = "blocked_environment" });
                return 2;
            }

            int index = 0;
            await foreach (JsonObject turn in ReadTurnsAsync(parsed, lifetime.Token))
            {
                if (turn["exit"] is not null)
                {
                    break;
                }

                if (turn["beat"] is JsonObject beatMoment)
                {
                    // A heartbeat with a given moment (the scenes' context), spoken per the person's activity.
                    turnStartedMs = clock.ElapsedMilliseconds;
                    utterances.TurnStarted();
                    Emit(new JsonObject { ["type"] = "beat.start", ["moment"] = beatMoment.DeepClone() });
                    await viewModel.RunBeatAsync(
                            (JsonObject)beatMoment.DeepClone(),
                            HeartbeatMoment.Speaks((string?)beatMoment["owner_activity"] ?? string.Empty),
                            lifetime.Token)
                        .ConfigureAwait(true);
                    Emit(new JsonObject
                    {
                        ["type"] = "beat.end",
                        ["pendingConfirmation"] = viewModel.HasPendingConfirmation,
                    });
                    Emit(new JsonObject { ["type"] = "command.done", ["beat"] = true });
                    continue;
                }

                if ((string?)turn["session"] == "new")
                {
                    // As the view's «+» starts one: the conversation that was is kept in the profile.
                    FieldHttpResponse started = await view.HandleHttpAsync("POST", "/sessions/new", null)
                        .ConfigureAwait(true);
                    Emit(new JsonObject { ["type"] = "command.done", ["session"] = "new", ["ok"] = started.Status == 200 });
                    continue;
                }

                turnStartedMs = clock.ElapsedMilliseconds;
                utterances.TurnStarted();
                Emit(new JsonObject { ["type"] = "turn.start", ["index"] = index, ["input"] = turn.DeepClone() });
                using var turnTimeout = CancellationTokenSource.CreateLinkedTokenSource(lifetime.Token);
                turnTimeout.CancelAfter(parsed.TurnTimeout);
                if (turn["confirm"] is JsonValue confirm && confirm.TryGetValue(out bool approve))
                {
                    await viewModel.AnswerConfirmationAsync(approve, Stopwatch.GetTimestamp(), turnTimeout.Token)
                        .ConfigureAwait(true);
                }
                else
                {
                    try
                    {
                        await viewModel.SubmitAsync(
                                new MissionInput((string?)turn["text"] ?? string.Empty, MissionInputSource.Text),
                                Stopwatch.GetTimestamp(),
                                turnTimeout.Token)
                            .ConfigureAwait(true);
                    }
                    catch (MissionInputRejectedException rejected)
                    {
                        Emit(new JsonObject { ["type"] = "input.rejected", ["reason"] = rejected.Reason.ToString() });
                    }
                }

                long endedMs = clock.ElapsedMilliseconds - turnStartedMs;
                var speechDeadline = Stopwatch.StartNew();
                while (viewModel.CanSpeak && utterances.ResponseSpeechStartedMs is null
                    && speechDeadline.Elapsed < SpeechWait && !lifetime.IsCancellationRequested)
                {
                    await Task.Delay(TimeSpan.FromMilliseconds(25), lifetime.Token).ConfigureAwait(true);
                }

                Emit(new JsonObject
                {
                    ["type"] = "turn.end",
                    ["index"] = index,
                    ["ms"] = endedMs,
                    // The turn's first sound, the notice's when it was said first; and its response's first sound.
                    ["speech_start_ms"] = utterances.SpeechStartedMs,
                    ["response_speech_start_ms"] = utterances.ResponseSpeechStartedMs,
                    ["timedOut"] = turnTimeout.IsCancellationRequested && !lifetime.IsCancellationRequested,
                    ["failure"] = viewModel.LastTurnFailure,
                    ["pendingConfirmation"] = viewModel.HasPendingConfirmation,
                });
                Emit(new JsonObject { ["type"] = "command.done", ["index"] = index });
                index++;
            }

            Emit(new JsonObject { ["type"] = "terminal", ["kind"] = "completed", ["turns"] = index });
            return 0;
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested)
        {
            Emit(new JsonObject { ["type"] = "terminal", ["kind"] = "cancelled" });
            return 3;
        }
        finally
        {
            capture?.Dispose();
        }
    }

    /// <summary>
    /// The product as the window mounts it, with no view to show what it publishes: the view's channel serves BAXY's own
    /// readings (assistant.status: the confirmation mode from the profile, the model's from <paramref name="telemetry"/>,
    /// the internet exits from this session's steps) and the conversations asked by voice (conversation.*, kept in the profile's sessions).
    /// </summary>
    internal static FieldProductChannel Mount(MainWindowViewModel viewModel, FieldTelemetrySampler telemetry,
        CancellationToken lifetime) => new(viewModel, new Unseen(), telemetry, lifetime);

    // No view: what the channel publishes for it is seen by none (the benches read the conductor's own events).
    private sealed class Unseen : IFieldEventSink
    {
        public bool Publish(JsonObject eventData) => true;
    }

    private static async IAsyncEnumerable<JsonObject> ReadTurnsAsync(
        ConductorArguments parsed,
        [System.Runtime.CompilerServices.EnumeratorCancellation] CancellationToken cancellationToken)
    {
        if (parsed.Text is { } text)
        {
            yield return new JsonObject { ["text"] = text };
            yield break;
        }

        if (parsed.CommandDirectory is { } commands)
        {
            Directory.CreateDirectory(commands);
            for (int sequence = 1; ; sequence++)
            {
                string path = Path.Combine(commands, sequence.ToString("D5", System.Globalization.CultureInfo.InvariantCulture) + ".json");
                JsonObject? command = null;
                while (command is null)
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    if (File.Exists(path))
                    {
                        try
                        {
                            command = JsonNode.Parse(await File.ReadAllTextAsync(path, cancellationToken)
                                .ConfigureAwait(true)) as JsonObject;
                        }
                        catch (Exception exception) when (exception is IOException or JsonException)
                        {
                            command = null; // still being written
                        }
                    }

                    if (command is null)
                    {
                        await Task.Delay(TimeSpan.FromMilliseconds(25), cancellationToken).ConfigureAwait(true);
                    }
                }

                yield return command;
            }
        }

        if (parsed.TurnsFile is null)
        {
            yield break;
        }

        foreach (string raw in File.ReadLines(parsed.TurnsFile, Encoding.UTF8))
        {
            string line = raw.Trim();
            if (line.Length == 0)
            {
                continue;
            }

            JsonObject? turn = null;
            if (line.StartsWith('{'))
            {
                try
                {
                    turn = JsonNode.Parse(line) as JsonObject;
                }
                catch (JsonException)
                {
                    turn = null;
                }
            }

            yield return turn ?? new JsonObject { ["text"] = line };
        }
    }

    private static void EnsureConsole()
    {
        if (!AttachConsole(AttachParentProcess))
        {
            _ = AllocConsole();
        }

        Console.SetOut(new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)) { AutoFlush = true });
        Console.SetError(new StreamWriter(Console.OpenStandardError(), new UTF8Encoding(false)) { AutoFlush = true });
    }

    internal sealed record ConductorArguments(
        string ProfileDirectory,
        string? CaptureDirectory,
        string? TurnsFile,
        string? Text,
        string? CommandDirectory,
        TimeSpan TurnTimeout)
    {
        internal static ConductorArguments Parse(IReadOnlyList<string> arguments)
        {
            string profile = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "BAXY", "conductor");
            string? capture = null;
            string? turns = null;
            string? text = null;
            string? commands = null;
            int timeoutMs = 180_000;
            for (int index = 0; index < arguments.Count; index++)
            {
                if (TryTake(arguments, ref index, "--profile", out string? value))
                {
                    profile = value!;
                }
                else if (TryTake(arguments, ref index, "--capture", out value))
                {
                    capture = value;
                }
                else if (TryTake(arguments, ref index, "--turns-file", out value))
                {
                    turns = value;
                }
                else if (TryTake(arguments, ref index, "--text", out value))
                {
                    text = value;
                }
                else if (TryTake(arguments, ref index, "--command-dir", out value))
                {
                    commands = value;
                }
                else if (TryTake(arguments, ref index, "--timeout-ms", out value)
                    && int.TryParse(value, out int parsedTimeout))
                {
                    timeoutMs = Math.Clamp(parsedTimeout, 1_000, 900_000);
                }
            }

            return new ConductorArguments(
                Path.GetFullPath(profile),
                string.IsNullOrWhiteSpace(capture) ? null : Path.GetFullPath(capture),
                string.IsNullOrWhiteSpace(turns) ? null : Path.GetFullPath(turns),
                text,
                string.IsNullOrWhiteSpace(commands) ? null : Path.GetFullPath(commands),
                TimeSpan.FromMilliseconds(timeoutMs));
        }

        private static bool TryTake(IReadOnlyList<string> arguments, ref int index, string expected, out string? value)
        {
            string argument = arguments[index];
            if (argument.StartsWith(expected + "=", StringComparison.OrdinalIgnoreCase))
            {
                value = argument[(expected.Length + 1)..];
                return true;
            }

            if (string.Equals(argument, expected, StringComparison.OrdinalIgnoreCase) && index + 1 < arguments.Count)
            {
                value = arguments[++index];
                return true;
            }

            value = null;
            return false;
        }
    }
}
