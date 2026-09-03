using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Windows.Threading;

namespace Baxy.App;

/// <summary>
/// Starts the registered BAXY runtime without the product window and drives
/// the same <see cref="FieldProductChannel"/> the UI uses.
/// </summary>
internal static class ProductConductorHost
{
    internal const string Argument = "--conductor";

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = false,
    };

    internal static bool IsRequested(IReadOnlyList<string> arguments)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        foreach (string argument in arguments)
        {
            if (string.Equals(argument, Argument, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return false;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AttachConsole(int dwProcessId);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AllocConsole();

    private const int AttachParentProcess = -1;

    internal static async Task<int> RunAsync(
        IReadOnlyList<string> arguments,
        Dispatcher dispatcher)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        ArgumentNullException.ThrowIfNull(dispatcher);
        EnsureConsole();
        ConductorArguments parsed = ConductorArguments.Parse(arguments);
        Directory.CreateDirectory(parsed.ProfileDirectory);
        if (!string.IsNullOrWhiteSpace(parsed.CaptureDirectory))
        {
            Directory.CreateDirectory(parsed.CaptureDirectory);
        }

        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", parsed.ProfileDirectory);
        Environment.SetEnvironmentVariable("BAXY_VOICE_WAKE_ON_START", "0");

        using var lifetime = new CancellationTokenSource();
        Console.CancelKeyPress += (_, eventArgs) =>
        {
            eventArgs.Cancel = true;
            lifetime.Cancel();
        };

        await using var viewModel = new MainWindowViewModel();
        await using ProductConductor conductor = ProductConductor.Create(
            viewModel,
            lifetime.Token);
        StreamWriter? capture = OpenCapture(parsed.CaptureDirectory, "events.jsonl");
        try
        {
            JsonObject meta = BuildMeta(parsed);
            await EmitAsync(meta, capture, lifetime.Token).ConfigureAwait(true);

            await viewModel.InitializeAsync(lifetime.Token).ConfigureAwait(true);
            await EmitAsync(
                    new JsonObject
                    {
                        ["type"] = "runtime",
                        ["ready"] = viewModel.IsReady,
                        ["startupError"] = viewModel.HasStartupError,
                        ["status"] = viewModel.StatusDescription,
                    },
                    capture,
                    lifetime.Token)
                .ConfigureAwait(true);

            if (!viewModel.IsReady)
            {
                await EmitAsync(
                        new JsonObject
                        {
                            ["type"] = "terminal",
                            ["kind"] = "blocked_environment",
                            ["diagnostic"] = "runtime_not_ready",
                        },
                        capture,
                        lifetime.Token)
                    .ConfigureAwait(true);
                return 2;
            }

            IReadOnlyList<JsonObject> commands = await LoadCommandsAsync(parsed, lifetime.Token)
                .ConfigureAwait(true);
            foreach (JsonObject command in commands)
            {
                lifetime.Token.ThrowIfCancellationRequested();
                await ExecuteCommandAsync(
                        conductor,
                        command,
                        parsed.Timeout,
                        capture,
                        lifetime.Token)
                    .ConfigureAwait(true);
            }

            await EmitAsync(
                    PosteriorJson(conductor.CapturePosterior()),
                    capture,
                    lifetime.Token)
                .ConfigureAwait(true);
            return 0;
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested)
        {
            await EmitAsync(
                    new JsonObject
                    {
                        ["type"] = "terminal",
                        ["kind"] = "cancelled",
                    },
                    capture,
                    CancellationToken.None)
                .ConfigureAwait(true);
            return 130;
        }
        finally
        {
            if (capture is not null)
            {
                await capture.DisposeAsync();
            }
        }
    }

    private static async Task ExecuteCommandAsync(
        ProductConductor conductor,
        JsonObject command,
        TimeSpan timeout,
        StreamWriter? capture,
        CancellationToken cancellationToken)
    {
        string cmd = ((string?)command["cmd"] ?? "turn").Trim().ToLowerInvariant();
        if (cmd is "session.new" or "new-session" or "sessions/new")
        {
            FieldHttpResponse response = await conductor.NewSessionAsync()
                .ConfigureAwait(true);
            await EmitAsync(
                    HttpJson("session.new", response),
                    capture,
                    cancellationToken)
                .ConfigureAwait(true);
            return;
        }

        if (cmd == "upload")
        {
            FieldHttpResponse response = await conductor.UploadAsync()
                .ConfigureAwait(true);
            await EmitAsync(HttpJson("upload", response), capture, cancellationToken)
                .ConfigureAwait(true);
            return;
        }

        if (cmd is "cancel" or "cancelar")
        {
            ProductTurnResult result = await conductor
                .CancelAsync(timeout, cancellationToken)
                .ConfigureAwait(true);
            await EmitTurnAsync(result, capture, cancellationToken).ConfigureAwait(true);
            return;
        }

        string text = ((string?)command["text"] ?? string.Empty).Trim();
        if (text.Length == 0)
        {
            FieldHttpResponse response = await conductor
                .HandleHttpAsync("POST", "/turn", command.ToJsonString())
                .ConfigureAwait(true);
            await EmitAsync(HttpJson("turn", response), capture, cancellationToken)
                .ConfigureAwait(true);
            return;
        }

        ProductTurnResult turn = await conductor
            .TurnAsync(text, timeout, cancellationToken)
            .ConfigureAwait(true);
        await EmitTurnAsync(turn, capture, cancellationToken).ConfigureAwait(true);
    }

    private static async Task EmitTurnAsync(
        ProductTurnResult result,
        StreamWriter? capture,
        CancellationToken cancellationToken)
    {
        await EmitAsync(HttpJson("turn", result.Admission), capture, cancellationToken)
            .ConfigureAwait(true);
        foreach (JsonObject publicEvent in result.PublicEvents)
        {
            await EmitAsync(
                    new JsonObject
                    {
                        ["type"] = "event",
                        ["event"] = publicEvent.DeepClone(),
                    },
                    capture,
                    cancellationToken)
                .ConfigureAwait(true);
        }

        await EmitAsync(
                new JsonObject
                {
                    ["type"] = "terminal",
                    ["kind"] = TerminalName(result.Terminal),
                    ["final"] = result.FinalText,
                    ["diagnostic"] = result.Diagnostic,
                    ["timedOut"] = result.TimedOut,
                    ["admissionStatus"] = result.Admission.Status,
                },
                capture,
                cancellationToken)
            .ConfigureAwait(true);
        await EmitAsync(PosteriorJson(result.Posterior), capture, cancellationToken)
            .ConfigureAwait(true);
    }

    private static string TerminalName(ProductTurnTerminal terminal) => terminal switch
    {
        ProductTurnTerminal.PublishedFinal => "published_final",
        ProductTurnTerminal.Filtered => "filtered",
        ProductTurnTerminal.AcceptedWithoutFinal => "accepted_without_final",
        ProductTurnTerminal.Silence => "silence",
        _ => "rejected",
    };

    private static JsonObject HttpJson(string command, FieldHttpResponse response) =>
        new()
        {
            ["type"] = "admission",
            ["command"] = command,
            ["status"] = response.Status,
            ["body"] = response.Body,
        };

    private static JsonObject PosteriorJson(ProductPosteriorState posterior) =>
        new()
        {
            ["type"] = "posterior",
            ["messageCount"] = posterior.MessageCount,
            ["userMessageCount"] = posterior.UserMessageCount,
            ["isBusy"] = posterior.IsBusy,
            ["isInputEnabled"] = posterior.IsInputEnabled,
            ["hasPendingPlan"] = posterior.HasPendingPlan,
            ["pendingCompositionCount"] = posterior.PendingCompositionCount,
            ["compositionFailure"] = posterior.CompositionFailure,
            ["statusDescription"] = posterior.StatusDescription,
        };

    private static JsonObject BuildMeta(ConductorArguments parsed)
    {
        string? manifestPath = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "BAXYRuntime",
            "mind-runtime-v1.json");
        JsonNode? manifest = null;
        if (File.Exists(manifestPath))
        {
            try
            {
                manifest = JsonNode.Parse(File.ReadAllText(manifestPath));
            }
            catch (JsonException)
            {
                manifest = new JsonObject { ["error"] = "manifest_unreadable" };
            }
        }

        return new JsonObject
        {
            ["type"] = "meta",
            ["commit"] = parsed.Commit,
            ["profile"] = parsed.ProfileDirectory,
            ["capture"] = parsed.CaptureDirectory,
            ["manifestPath"] = File.Exists(manifestPath) ? manifestPath : null,
            ["manifest"] = manifest,
            ["config"] = new JsonObject
            {
                ["BAXY_DATA_DIR"] = Environment.GetEnvironmentVariable("BAXY_DATA_DIR"),
                ["BAXY_MIND_LLM_GGUF"] = Environment.GetEnvironmentVariable("BAXY_MIND_LLM_GGUF"),
                ["BAXY_MIND_PYTHON"] = Environment.GetEnvironmentVariable("BAXY_MIND_PYTHON"),
                ["BAXY_MIND_PYTHONPATH"] = Environment.GetEnvironmentVariable("BAXY_MIND_PYTHONPATH"),
                ["BAXY_MIND_LLAMA_SERVER"] =
                    Environment.GetEnvironmentVariable("BAXY_MIND_LLAMA_SERVER"),
                ["BAXY_MIND_NGL"] = Environment.GetEnvironmentVariable("BAXY_MIND_NGL"),
                ["BAXY_ASSET_DESCRIPTOR"] =
                    Environment.GetEnvironmentVariable("BAXY_ASSET_DESCRIPTOR"),
                ["BAXY_VOICE_WAKE_ON_START"] =
                    Environment.GetEnvironmentVariable("BAXY_VOICE_WAKE_ON_START"),
            },
            ["process"] = Path.GetFileName(Environment.ProcessPath),
            ["pid"] = Environment.ProcessId,
        };
    }

    private static async Task<IReadOnlyList<JsonObject>> LoadCommandsAsync(
        ConductorArguments parsed,
        CancellationToken cancellationToken)
    {
        if (!string.IsNullOrWhiteSpace(parsed.TurnsFile))
        {
            string[] lines = await File.ReadAllLinesAsync(parsed.TurnsFile, cancellationToken)
                .ConfigureAwait(true);
            return [.. lines
                .Select(static line => line.Trim())
                .Where(static line => line.Length > 0 && !line.StartsWith('#'))
                .Select(ParseCommand)];
        }

        if (!string.IsNullOrWhiteSpace(parsed.Text))
        {
            return [new JsonObject { ["cmd"] = "turn", ["text"] = parsed.Text }];
        }

        var commands = new List<JsonObject>();
        using var reader = new StreamReader(Console.OpenStandardInput(), Encoding.UTF8);
        while (await reader.ReadLineAsync(cancellationToken).ConfigureAwait(true) is { } line)
        {
            string trimmed = line.Trim();
            if (trimmed.Length == 0)
            {
                continue;
            }

            commands.Add(ParseCommand(trimmed));
        }

        return commands;
    }

    private static JsonObject ParseCommand(string line)
    {
        JsonNode? node;
        try
        {
            node = JsonNode.Parse(line);
        }
        catch (JsonException)
        {
            return new JsonObject { ["cmd"] = "turn", ["text"] = line };
        }

        if (node is JsonObject obj)
        {
            if (obj["cmd"] is null && obj["text"] is not null)
            {
                obj["cmd"] = "turn";
            }

            return obj;
        }

        return new JsonObject { ["cmd"] = "turn", ["text"] = line };
    }

    private static void EnsureConsole()
    {
        if (!AttachConsole(AttachParentProcess))
        {
            _ = AllocConsole();
        }

        Console.SetOut(new StreamWriter(Console.OpenStandardOutput(), Encoding.UTF8)
        {
            AutoFlush = true,
        });
        Console.SetError(new StreamWriter(Console.OpenStandardError(), Encoding.UTF8)
        {
            AutoFlush = true,
        });
        Console.SetIn(new StreamReader(Console.OpenStandardInput(), Encoding.UTF8));
    }

    private static StreamWriter? OpenCapture(string? directory, string fileName)
    {
        if (string.IsNullOrWhiteSpace(directory))
        {
            return null;
        }

        var writer = new StreamWriter(
            Path.Combine(directory, fileName),
            append: false,
            Encoding.UTF8)
        {
            AutoFlush = true,
        };
        return writer;
    }

    private static async Task EmitAsync(
        JsonObject payload,
        StreamWriter? capture,
        CancellationToken cancellationToken)
    {
        string line = payload.ToJsonString(JsonOptions);
        Console.Out.WriteLine(line);
        await Console.Out.FlushAsync(cancellationToken).ConfigureAwait(true);
        if (capture is not null)
        {
            await capture.WriteLineAsync(line.AsMemory(), cancellationToken).ConfigureAwait(true);
        }
    }

    internal sealed record ConductorArguments(
        string ProfileDirectory,
        string? CaptureDirectory,
        string? TurnsFile,
        string? Text,
        string? Commit,
        TimeSpan Timeout)
    {
        internal static ConductorArguments Parse(IReadOnlyList<string> arguments)
        {
            string profile = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "BAXY",
                "comprobaciones-c01");
            string? capture = null;
            string? turns = null;
            string? text = null;
            string? commit = Environment.GetEnvironmentVariable("BAXY_CONDUCTOR_COMMIT");
            int timeoutMs = 120_000;
            for (int index = 0; index < arguments.Count; index++)
            {
                string argument = arguments[index];
                if (TryTake(arguments, ref index, "--profile", out string? profileValue))
                {
                    profile = profileValue!;
                }
                else if (TryTake(arguments, ref index, "--capture", out string? captureValue))
                {
                    capture = captureValue;
                }
                else if (TryTake(arguments, ref index, "--turns-file", out string? turnsValue))
                {
                    turns = turnsValue;
                }
                else if (TryTake(arguments, ref index, "--text", out string? textValue))
                {
                    text = textValue;
                }
                else if (TryTake(arguments, ref index, "--commit", out string? commitValue))
                {
                    commit = commitValue;
                }
                else if (TryTake(arguments, ref index, "--timeout-ms", out string? timeoutValue)
                    && int.TryParse(timeoutValue, out int parsedTimeout))
                {
                    timeoutMs = Math.Clamp(parsedTimeout, 1_000, 600_000);
                }
            }

            return new ConductorArguments(
                Path.GetFullPath(profile),
                string.IsNullOrWhiteSpace(capture) ? null : Path.GetFullPath(capture),
                string.IsNullOrWhiteSpace(turns) ? null : Path.GetFullPath(turns),
                text,
                commit,
                TimeSpan.FromMilliseconds(timeoutMs));
        }

        private static bool TryTake(
            IReadOnlyList<string> arguments,
            ref int index,
            string expected,
            out string? value)
        {
            string argument = arguments[index];
            if (argument.StartsWith(expected + "=", StringComparison.OrdinalIgnoreCase))
            {
                value = argument[(expected.Length + 1)..];
                return true;
            }

            if (string.Equals(argument, expected, StringComparison.OrdinalIgnoreCase)
                && index + 1 < arguments.Count)
            {
                value = arguments[++index];
                return true;
            }

            value = null;
            return false;
        }
    }
}
