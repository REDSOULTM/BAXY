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
            DateTime mindDeadline = DateTime.UtcNow.AddSeconds(120);
            while (!viewModel.IsMindReady
                && !viewModel.HasStartupError
                && DateTime.UtcNow < mindDeadline)
            {
                await Task.Delay(TimeSpan.FromMilliseconds(200), lifetime.Token)
                    .ConfigureAwait(true);
            }

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
                if (!await ExecuteCommandAsync(
                        conductor,
                        command,
                        parsed.Timeout,
                        parsed.ProfileDirectory,
                        capture,
                        lifetime.Token).ConfigureAwait(true))
                {
                    return 3;
                }
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

    private static async Task<bool> ExecuteCommandAsync(
        ProductConductor conductor,
        JsonObject command,
        TimeSpan timeout,
        string profileDirectory,
        StreamWriter? capture,
        CancellationToken cancellationToken)
    {
        string cmd = ((string?)command["cmd"] ?? "turn").Trim().ToLowerInvariant();
        if (cmd == "turn.confirm-reviewed")
        {
            return await ExecuteReviewedAsync(
                conductor, command, timeout, profileDirectory, capture, cancellationToken)
                .ConfigureAwait(true);
        }
        if (cmd == "turn.memory-confirm")
        {
            return await ExecuteMemoryConfirmAsync(
                conductor, command, timeout, capture, cancellationToken)
                .ConfigureAwait(true);
        }
        if (cmd == "turn.confirm-if-matches")
        {
            string? caseId = command["caseId"] is JsonValue caseValue
                && caseValue.TryGetValue(out string? parsedCase) ? parsedCase : null;
            if (command.Count != 5 || string.IsNullOrWhiteSpace(caseId)
                || command["text"] is not JsonValue textValue
                || !textValue.TryGetValue(out string? requestText)
                || string.IsNullOrWhiteSpace(requestText)
                || command["expectedOperation"] is not JsonValue operationValue
                || !operationValue.TryGetValue(out string? expectedOperation)
                || string.IsNullOrWhiteSpace(expectedOperation)
                || command["expectedArguments"] is not JsonObject expectedArguments
                || conductor.CapturePosterior() is { HasPendingPlan: true } or { IsBusy: true })
            {
                await EmitTurnAsync(
                    conductor.RejectConfirmation("confirmation_command_not_admitted"),
                    capture, cancellationToken, caseId, "final").ConfigureAwait(true);
                return false;
            }

            ProductTurnResult initial = await conductor
                .TurnAsync(requestText, timeout, cancellationToken).ConfigureAwait(true);
            PendingOperationConfirmation? observed =
                conductor.ViewModel.CaptureConductorConfirmation();
            await EmitTurnAsync(initial, capture, cancellationToken, caseId, "request")
                .ConfigureAwait(true);
            ProductTurnResult final = await conductor.ConfirmPendingAsync(
                initial, observed, expectedOperation, expectedArguments,
                timeout, cancellationToken).ConfigureAwait(true);
            await EmitTurnAsync(final, capture, cancellationToken, caseId, "final")
                .ConfigureAwait(true);
            return !final.TimedOut
                && final.Terminal == ProductTurnTerminal.PublishedFinal
                && !final.Posterior.HasPendingPlan && !final.Posterior.HasCompositionError;
        }

        if (cmd is "session.new" or "new-session" or "sessions/new")
        {
            FieldHttpResponse response = await conductor.NewSessionAsync()
                .ConfigureAwait(true);
            await EmitAsync(
                    HttpJson("session.new", response),
                    capture,
                    cancellationToken)
                .ConfigureAwait(true);
            return true;
        }

        if (cmd == "upload")
        {
            FieldHttpResponse response = await conductor.UploadAsync()
                .ConfigureAwait(true);
            await EmitAsync(HttpJson("upload", response), capture, cancellationToken)
                .ConfigureAwait(true);
            return true;
        }

        // R07 pide inyectar el fallo, restaurar el recurso y volver a pedir en
        // el mismo proceso, perfil y sesión. La inyección ya vivía en el shell
        // (`FieldCompositionInjection.Mode`); sólo faltaba poder moverla sin
        // arrancar otra vez, que es lo que dejaba la prueba en dos procesos.
        if (cmd is "inject" or "restore")
        {
            string requested = cmd == "restore"
                ? "none"
                : ((string?)command["mode"] ?? "reject").Trim().ToLowerInvariant();
            FieldCompositionInjection.Mode = requested switch
            {
                "reject" => FieldCompositionInjectionMode.Reject,
                "timeout" => FieldCompositionInjectionMode.Timeout,
                "exhaust" => FieldCompositionInjectionMode.Exhaust,
                _ => FieldCompositionInjectionMode.None,
            };
            await EmitAsync(
                    new JsonObject
                    {
                        ["type"] = "injection",
                        ["mode"] = FieldCompositionInjection.Mode.ToString()
                            .ToLowerInvariant(),
                        ["pid"] = Environment.ProcessId,
                    },
                    capture,
                    cancellationToken)
                .ConfigureAwait(true);
            return true;
        }

        if (cmd is "cancel" or "cancelar")
        {
            ProductTurnResult result = await conductor
                .CancelAsync(timeout, cancellationToken)
                .ConfigureAwait(true);
            await EmitTurnAsync(result, capture, cancellationToken).ConfigureAwait(true);
            return true;
        }

        string text = ((string?)command["text"] ?? string.Empty).Trim();
        if (text.Length == 0)
        {
            FieldHttpResponse response = await conductor
                .HandleHttpAsync("POST", "/turn", command.ToJsonString())
                .ConfigureAwait(true);
            await EmitAsync(HttpJson("turn", response), capture, cancellationToken)
                .ConfigureAwait(true);
            return true;
        }

        ProductTurnResult turn = await conductor
            .TurnAsync(text, timeout, cancellationToken)
            .ConfigureAwait(true);
        await EmitTurnAsync(turn, capture, cancellationToken).ConfigureAwait(true);
        return true;
    }

    private static async Task<bool> ExecuteReviewedAsync(
        ProductConductor conductor,
        JsonObject command,
        TimeSpan timeout,
        string profileDirectory,
        StreamWriter? capture,
        CancellationToken cancellationToken)
    {
        string? caseId = ReviewString(command, "caseId");
        string? text = ReviewString(command, "text");
        string? directory = ReviewString(command, "reviewDirectory");
        async Task<bool> RejectAsync(string diagnostic)
        {
            await EmitTurnAsync(conductor.RejectConfirmation(diagnostic),
                capture, cancellationToken, caseId, "final").ConfigureAwait(true);
            return false;
        }

        if (command.Count != 4 || string.IsNullOrWhiteSpace(caseId)
            || string.IsNullOrWhiteSpace(text) || string.IsNullOrWhiteSpace(directory)
            || conductor.CapturePosterior() is { HasPendingPlan: true } or { IsBusy: true })
        {
            return await RejectAsync("review_command_not_admitted").ConfigureAwait(true);
        }

        var elapsed = System.Diagnostics.Stopwatch.StartNew();
        try
        {
            directory = ValidateReviewDirectory(directory, profileDirectory);
            Directory.CreateDirectory(directory);
            ValidateReviewDirectory(directory, profileDirectory);
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException
            or ArgumentException or NotSupportedException)
        {
            return await RejectAsync("review_directory_invalid").ConfigureAwait(true);
        }

        ProductTurnResult initial = await conductor.TurnAsync(text, timeout, cancellationToken)
            .ConfigureAwait(true);
        PendingOperationConfirmation? observed = conductor.ViewModel
            .CaptureConductorConfirmation(allowVerifiedReadPrefix: true);
        if (observed is null && !initial.Posterior.HasPendingPlan)
        {
            // A genuine non-confirming result has one admission/final, not a
            // fabricated extra rejection just because there is no challenge.
            await EmitTurnAsync(initial, capture, cancellationToken, caseId, "final")
                .ConfigureAwait(true);
            return !initial.TimedOut && !initial.Posterior.HasPendingPlan && !initial.Posterior.IsBusy;
        }

        await EmitTurnAsync(initial, capture, cancellationToken, caseId, "request")
            .ConfigureAwait(true);
        if (observed is null || initial.TimedOut
            || initial.Terminal != ProductTurnTerminal.PublishedFinal
            || initial.Diagnostic is not null
            || observed.Prepared.OperationName is not (
                "browser.navigate" or "browser.navigate.named" or "app.close" or "input.visible.click"
                or "system.settings.set" or "clipboard.write.text" or "clipboard.read.text"
                // SCREEN1399 «sacá un screenshot»: a privacy-sensitive capture is
                // confirmed by the root reviewer like the clipboard operations.
                or "capture.screenshot" or "capture.active.window"))
        {
            return await RejectAsync("review_pending_not_supported").ConfigureAwait(true);
        }

        // Prepared owns its arguments; this independent snapshot never exposes
        // the confirmation token and is never regenerated from reviewer input.
        PreparedOperation prepared = observed.Prepared;
        JsonObject arguments = JsonNode.Parse(prepared.Arguments.GetRawText())!.AsObject();
        string nonce = Guid.NewGuid().ToString("N");
        string reviewPath = Path.Combine(directory, nonce);
        string proposalPath = Path.Combine(reviewPath, "proposal.json");
        string approvalPath = Path.Combine(reviewPath, "approval.json");
        var proposal = new JsonObject
        {
            ["schema"] = "conductor-review-proposal-v1",
            ["nonce"] = nonce,
            ["caseId"] = caseId,
            ["requestText"] = text,
            ["operation"] = prepared.OperationName,
            ["arguments"] = arguments.DeepClone(),
            ["missionId"] = prepared.MissionId,
            ["invocationId"] = prepared.InvocationId,
            ["expiresAtUtc"] = observed.ExpiresAtUtc.ToString("O"),
        };
        proposal[prepared.OperationName == "app.close" ? "windowObservations" : "webSearchObservations"] =
            conductor.ViewModel.CaptureConductorReadEvidence();
        try
        {
            ValidateReviewDirectory(directory, profileDirectory);
            if (Directory.Exists(reviewPath))
            {
                return await RejectAsync("review_directory_already_exists").ConfigureAwait(true);
            }
            Directory.CreateDirectory(reviewPath);
            ValidateReviewDirectory(reviewPath, profileDirectory);
            using (var stream = new FileStream(proposalPath, FileMode.CreateNew,
                FileAccess.Write, FileShare.Read))
            {
                byte[] bytes = Encoding.UTF8.GetBytes(proposal.ToJsonString(JsonOptions));
                await stream.WriteAsync(bytes, cancellationToken).ConfigureAwait(true);
            }

            await EmitAsync(new JsonObject
            {
                ["type"] = "review_required",
                ["caseId"] = caseId,
                ["nonce"] = nonce,
                ["proposalPath"] = proposalPath,
                ["approvalPath"] = approvalPath,
                ["maximumConfirmations"] = 1,
            }, capture, cancellationToken).ConfigureAwait(true);

            while (elapsed.Elapsed < timeout && DateTimeOffset.UtcNow < observed.ExpiresAtUtc)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (!ReferenceEquals(observed, conductor.ViewModel
                    .CaptureConductorConfirmation(allowVerifiedReadPrefix: true)))
                {
                    return await RejectAsync("review_pending_changed").ConfigureAwait(true);
                }
                ValidateReviewDirectory(reviewPath, profileDirectory);
                if (File.Exists(approvalPath))
                {
                    if ((File.GetAttributes(approvalPath) & FileAttributes.ReparsePoint) != 0)
                    {
                        return await RejectAsync("review_approval_invalid").ConfigureAwait(true);
                    }
                    using var stream = new FileStream(approvalPath, FileMode.Open,
                        FileAccess.Read, FileShare.Read);
                    if (stream.Length is <= 0 or > 65_536)
                    {
                        return await RejectAsync("review_approval_invalid").ConfigureAwait(true);
                    }
                    byte[] bytes = new byte[(int)stream.Length];
                    await stream.ReadExactlyAsync(bytes, cancellationToken).ConfigureAwait(true);
                    JsonObject? approval = JsonNode.Parse(bytes) as JsonObject;
                    if (approval is null || approval.Count != 8
                        || ReviewString(approval, "schema") != "conductor-review-approval-v1"
                        || ReviewString(approval, "nonce") != nonce
                        || ReviewString(approval, "caseId") != caseId
                        || ReviewString(approval, "operation") != prepared.OperationName
                        || ReviewString(approval, "missionId") != prepared.MissionId
                        || ReviewString(approval, "invocationId") != prepared.InvocationId
                        || !JsonNode.DeepEquals(approval["arguments"], arguments))
                    {
                        return await RejectAsync("review_approval_mismatch").ConfigureAwait(true);
                    }
                    if (ReviewString(approval, "decision") != "approve")
                    {
                        return await RejectAsync("review_not_approved").ConfigureAwait(true);
                    }
                    if (elapsed.Elapsed >= timeout
                        || DateTimeOffset.UtcNow >= observed.ExpiresAtUtc)
                    {
                        break;
                    }

                    ProductTurnResult final = await conductor.ConfirmPendingAsync(
                        initial, observed, prepared.OperationName, arguments,
                        timeout - elapsed.Elapsed, cancellationToken,
                        allowVerifiedReadPrefix: true).ConfigureAwait(true);
                    await EmitTurnAsync(final, capture, cancellationToken, caseId, "final")
                        .ConfigureAwait(true);
                    // One reviewed effect only. Never auto-approve a suffix.
                    return !final.TimedOut
                        && final.Terminal == ProductTurnTerminal.PublishedFinal
                        && !final.Posterior.HasPendingPlan && !final.Posterior.HasCompositionError;
                }
                await Task.Delay(TimeSpan.FromMilliseconds(200), cancellationToken)
                    .ConfigureAwait(true);
            }
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException
            or JsonException or ArgumentException or InvalidOperationException)
        {
            return await RejectAsync("review_io_or_data_invalid").ConfigureAwait(true);
        }

        return await RejectAsync("review_timed_out").ConfigureAwait(true);
    }

    /// <summary>
    /// One request turn, then — only when the private memory channel itself
    /// left a confirmation pending for the expected operation — the closed
    /// reply «confirmar» as a second turn. On a fresh profile an explicit
    /// «recuerda que me llamo …» ends in memory_disabled and the channel asks
    /// to enable the local memory; enabling continues the original save
    /// (MEMORY1245). Nothing is answered when no memory challenge is pending.
    /// </summary>
    private static async Task<bool> ExecuteMemoryConfirmAsync(
        ProductConductor conductor,
        JsonObject command,
        TimeSpan timeout,
        StreamWriter? capture,
        CancellationToken cancellationToken)
    {
        string? caseId = ReviewString(command, "caseId");
        string? text = ReviewString(command, "text");
        string? expectedOperation = ReviewString(command, "expectedOperation");
        async Task<bool> RejectAsync(string diagnostic)
        {
            await EmitTurnAsync(conductor.RejectConfirmation(diagnostic),
                capture, cancellationToken, caseId, "final").ConfigureAwait(true);
            return false;
        }

        if (command.Count != 4 || string.IsNullOrWhiteSpace(caseId)
            || string.IsNullOrWhiteSpace(text) || string.IsNullOrWhiteSpace(expectedOperation)
            || conductor.CapturePosterior() is { HasPendingPlan: true } or { IsBusy: true })
        {
            return await RejectAsync("memory_confirm_command_not_admitted").ConfigureAwait(true);
        }

        ProductTurnResult initial = await conductor.TurnAsync(text, timeout, cancellationToken)
            .ConfigureAwait(true);
        PendingMemoryConfirmation? observed = conductor.ViewModel.CaptureMemoryConfirmation();
        if (observed is null)
        {
            // No private-memory challenge: one admission, one final, nothing to confirm.
            await EmitTurnAsync(initial, capture, cancellationToken, caseId, "final")
                .ConfigureAwait(true);
            return !initial.TimedOut && !initial.Posterior.HasPendingPlan && !initial.Posterior.IsBusy;
        }

        await EmitTurnAsync(initial, capture, cancellationToken, caseId, "request")
            .ConfigureAwait(true);
        if (initial.TimedOut || initial.Terminal != ProductTurnTerminal.PublishedFinal
            || initial.Diagnostic is not null
            || !string.Equals(observed.Prepared.OperationName, expectedOperation, StringComparison.Ordinal))
        {
            return await RejectAsync("memory_confirmation_mismatch:" + observed.Prepared.OperationName)
                .ConfigureAwait(true);
        }

        // The private channel reads the same closed reply words a person types.
        ProductTurnResult final = await conductor.TurnAsync("confirmar", timeout, cancellationToken)
            .ConfigureAwait(true);
        await EmitTurnAsync(final, capture, cancellationToken, caseId, "final")
            .ConfigureAwait(true);
        return !final.TimedOut
            && final.Terminal == ProductTurnTerminal.PublishedFinal
            && !final.Posterior.HasPendingPlan && !final.Posterior.HasCompositionError;
    }

    private static string? ReviewString(JsonObject value, string key) =>
        value[key] is JsonValue field && field.TryGetValue(out string? text) ? text : null;

    private static string ValidateReviewDirectory(string directory, string profileDirectory)
    {
        string profile = Path.GetFullPath(profileDirectory);
        string path = Path.GetFullPath(directory);
        string localRoot = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "BAXY");
        if (!profile.StartsWith(localRoot + Path.DirectorySeparatorChar,
                StringComparison.OrdinalIgnoreCase)
            || !path.StartsWith(profile.TrimEnd(Path.DirectorySeparatorChar)
                + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
        {
            throw new IOException("Review directory must be inside the private profile.");
        }
        for (DirectoryInfo? current = new(path); current is not null; current = current.Parent)
        {
            if (current.Exists && (current.Attributes & FileAttributes.ReparsePoint) != 0)
            {
                throw new IOException("Review path cannot traverse a reparse point.");
            }
        }
        return path;
    }

    private static async Task EmitTurnAsync(
        ProductTurnResult result,
        StreamWriter? capture,
        CancellationToken cancellationToken,
        string? caseId = null,
        string? phase = null)
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

        var terminal = new JsonObject
        {
            ["type"] = "terminal",
            ["kind"] = TerminalName(result.Terminal),
            ["final"] = result.FinalText,
            ["diagnostic"] = result.Diagnostic,
            ["timedOut"] = result.TimedOut,
            ["admissionStatus"] = result.Admission.Status,
        };
        if (caseId is not null)
        {
            terminal["caseId"] = caseId;
            terminal["phase"] = phase;
        }

        await EmitAsync(terminal, capture, cancellationToken).ConfigureAwait(true);
        await EmitAsync(PosteriorJson(result.Posterior), capture, cancellationToken)
            .ConfigureAwait(true);
    }

    private static string TerminalName(ProductTurnTerminal terminal) => terminal switch
    {
        ProductTurnTerminal.PublishedFinal => "published_final",
        ProductTurnTerminal.Filtered => "filtered",
        ProductTurnTerminal.AcceptedWithoutFinal => "accepted_without_final",
        ProductTurnTerminal.Silence => "silence",
        ProductTurnTerminal.CompositionFailed => "composition_failed",
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
            ["hasCompositionError"] = posterior.HasCompositionError,
            ["statusDescription"] = posterior.StatusDescription,
            ["mindReplyRejection"] = posterior.MindReplyRejection,
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
