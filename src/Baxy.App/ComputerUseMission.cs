using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Operations;

namespace Baxy.App;

/// <summary>
/// The general computer-use engine (plan post-goal Fase 4, D21;
/// documentacion/computer-use/CONTRATO_VISTA_ACCION.md §4). A goal inside any
/// application is reached by looking at the foreground window (the compact
/// view), asking the mind for ONE step of the closed repertoire, executing it
/// through the core with its post-read, and looking again, until the success
/// check holds, the budget runs out or the screen stops changing. It knows no
/// application: everything it sees comes from the view and everything it does
/// is a catalog primitive with that primitive's risk, journaled by the Kernel.
/// A primitive that needs confirmation suspends the mission on that exact
/// invocation; the mission resumes with the person's «sí».
/// </summary>
internal static class ComputerUseMission
{
    internal const string OperationName = "mission.computer.use";
    internal const int DefaultBudgetSteps = 12;
    internal const int MaximumBudgetSteps = 12;
    private const int HistoryForTheMind = 6;
    private static readonly TimeSpan TimeBudget = TimeSpan.FromSeconds(90);
    private static readonly TimeSpan ViewTimeout = TimeSpan.FromSeconds(30);
    private static readonly TimeSpan ActionTimeout = TimeSpan.FromSeconds(45);
    private const int CoveredLooks = 4;
    private static readonly TimeSpan CoveredLookInterval = TimeSpan.FromMilliseconds(2500);

    // The closed repertoire: what a person does with keyboard and mouse over
    // what they see, plus bringing the application to the front.
    internal static readonly IReadOnlySet<string> Primitives = new HashSet<string>(StringComparer.Ordinal)
    {
        "app.open",
        "input.key.press",
        "input.scroll",
        "input.text.type",
        "input.visible.click",
    };

    internal sealed class Context
    {
        internal required CoreProcessClient Core { get; init; }
        internal required MindSidecarClient Mind { get; init; }
        internal required RetryableOperationRegistry Registry { get; init; }
        internal required Func<RetryableOperationRegistry, PreparedOperation, bool> MarkResolved { get; init; }
        internal required Action<string> SetStatus { get; init; }
        internal ComputerUseProcedures? Procedures { get; init; }
    }

    /// <summary>What the loop ended with: a synthesized response for the mission step, or a pending confirmation of one primitive.</summary>
    internal sealed record Result(
        OperationResponse? Response,
        PreparedOperation MissionPrepared,
        PendingOperationConfirmation? Confirmation);

    internal static async Task<Result> RunAsync(
        Context context,
        PendingMindPlanExecution execution,
        JsonObject arguments,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(context);
        ArgumentNullException.ThrowIfNull(execution);
        ArgumentNullException.ThrowIfNull(arguments);
        PreparedOperation missionPrepared = execution.PendingOperation is { OperationName: OperationName } same
            ? same
            : context.Registry.GetOrAdd(new RoutedOperation(OperationName, arguments));
        JsonObject state = execution.ComputerUse ?? Begin(arguments, execution.Objective, context.Procedures);
        execution.ComputerUse = state;
        string traceId = ShellTraceSink.TurnId;
        var stopwatch = Stopwatch.StartNew();
        long alreadyElapsed = (long?)state["elapsedMs"] ?? 0;
        JsonArray steps = state["steps"] as JsonArray ?? new JsonArray();
        state["steps"] = steps;
        string goal = (string?)state["goal"] ?? execution.Objective;
        string? application = (string?)state["application"];
        string? successCheck = (string?)state["successCheck"];
        int budget = (int?)state["budgetSteps"] ?? DefaultBudgetSteps;
        string? errorCode = null;
        bool reached = false;
        string? evidence = null;
        string? satisfiedBy = null;
        JsonObject? lastView = null;
        ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.start",
            $"budget.{budget}.steps_done.{steps.Count}");

        while (true)
        {
            cancellationToken.ThrowIfCancellationRequested();
            long elapsedMs = alreadyElapsed + stopwatch.ElapsedMilliseconds;
            if (elapsedMs > TimeBudget.TotalMilliseconds)
            {
                errorCode = "computer_use_time_exhausted";
                break;
            }

            if (steps.Count >= budget)
            {
                // The last look decides whether the final step reached the goal.
                lastView = await LookAsync(context, state, cancellationToken).ConfigureAwait(true);
                if (lastView is not null && ComputerUseSuccessCheck.Evaluate(successCheck, lastView, steps, out satisfiedBy))
                {
                    reached = true;
                    break;
                }

                errorCode = "computer_use_budget_exhausted";
                break;
            }

            context.SetStatus("Mirando la pantalla");
            lastView = await LookAsync(context, state, cancellationToken).ConfigureAwait(true);
            if (lastView is null)
            {
                errorCode = "computer_use_view_unavailable";
                break;
            }

            state["window"] = lastView["window"]?.DeepClone();
            AdoptWindow(state, lastView);
            // The text of the first look is what «the page changed» is measured against (check atom page:).
            state["baselineText"] ??= ComputerUseSuccessCheck.TextLines(lastView);
            lastView["baselineText"] = state["baselineText"]!.DeepClone();
            // What the last act made appear (a menu it opened, a page it loaded): the mind reads it apart.
            JsonArray currentText = ComputerUseSuccessCheck.TextLines(lastView);
            if (steps.Count > 0 && state["lastText"] is JsonArray previousText)
            {
                var before = new HashSet<string>(previousText.Select(line => (string?)line ?? string.Empty), StringComparer.Ordinal);
                lastView["newText"] = new JsonArray([.. currentText
                    .Select(line => (string?)line ?? string.Empty)
                    .Where(line => !before.Contains(line))
                    .Take(12)
                    .Select(line => (JsonNode?)JsonValue.Create(line))]);
            }

            state["lastText"] = currentText;
            if (ComputerUseSuccessCheck.Evaluate(successCheck, lastView, steps, out satisfiedBy))
            {
                reached = true;
                break;
            }

            if (lastView["window"]?["coveredBy"] is JsonObject)
            {
                // Another process draws over the application. Measured live (Steam
                // launched cold): its window was still behind the editor 1.6 s after
                // app.open and came up seconds later. Look again a few times, the
                // way a person waits for an app to finish opening; a cover that
                // does not yield stops the mission and says so.
                int coveredLooks = ((int?)state["coveredLooks"] ?? 0) + 1;
                state["coveredLooks"] = coveredLooks;
                if (coveredLooks <= CoveredLooks)
                {
                    await Task.Delay(CoveredLookInterval, cancellationToken).ConfigureAwait(true);
                    continue;
                }

                errorCode = "computer_use_window_covered";
                break;
            }

            string signature = ViewSignature(lastView);
            int unchanged = string.Equals(signature, (string?)state["lastSignature"], StringComparison.Ordinal)
                ? ((int?)state["unchangedViews"] ?? 0) + 1
                : 0;
            state["lastSignature"] = signature;
            state["unchangedViews"] = unchanged;
            // Two acts in a row without the screen changing: the loop stops and
            // says what it sees instead of going round (diseño §3).
            if (unchanged >= 2 && steps.Count > 0)
            {
                errorCode = "computer_use_surface_unchanged";
                break;
            }

            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.view",
                $"step.{steps.Count + 1}.controls.{ControlCount(lastView)}.text.{TextCount(lastView)}");

            // Remember before deciding: a learned procedure is replayed step by
            // step with each primitive's own verification; the model only comes
            // back when the replay deviates.
            // A learned step is replayed only on the application's own window (or when it opens it): measured, the
            // Calculator's procedure starts by typing, which would land on whatever window is in front.
            bool onTheApplication = (bool?)lastView["window"]?["requested"] == true || (int?)state["processId"] is > 0;
            MindComputerUseStep? decision = onTheApplication || NextProcedureOpens(state)
                ? NextProcedureStep(state, steps.Count)
                : null;
            bool fromProcedure = decision is not null;
            if (decision is null)
            {
                context.SetStatus($"Paso {steps.Count + 1}: decidiendo");
                var modelWatch = Stopwatch.StartNew();
                decision = await context.Mind.DecideComputerUseStepAsync(
                    execution.Objective, goal, application, successCheck,
                    CompactForTheMind(lastView), HistoryForMind(steps), budget - steps.Count,
                    cancellationToken).ConfigureAwait(true);
                state["modelMs"] = ((long?)state["modelMs"] ?? 0) + modelWatch.ElapsedMilliseconds;
                if (decision is null)
                {
                    errorCode = "computer_use_decision_unavailable";
                    break;
                }
            }

            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.decision",
                $"step.{steps.Count + 1}.{ShellTrace.SanitizeLabel(decision.Operation)}.{(fromProcedure ? "procedure" : "model")}");
            if (decision.Operation == "done")
            {
                // «Nada se afirma sin verificar»: the evidence the model cites must
                // be on the screen it was shown.
                string cited = (string?)decision.Arguments["evidence"] ?? string.Empty;
                if (cited.Length > 0 && ComputerUseSuccessCheck.ViewContains(lastView, cited))
                {
                    reached = true;
                    evidence = cited;
                    satisfiedBy = "model_evidence";
                    break;
                }

                errorCode = "computer_use_evidence_not_visible";
                break;
            }

            if (decision.Operation == "none" || !Primitives.Contains(decision.Operation))
            {
                errorCode = "computer_use_no_step_visible";
                state["stopReason"] = decision.Reason;
                break;
            }

            JsonObject stepArguments = decision.Arguments.DeepClone() as JsonObject ?? new JsonObject();
            stepArguments.Remove("evidence");
            if (!MindPlanBoundary.ArgumentsSatisfyExactSchema(decision.Operation, stepArguments))
            {
                errorCode = "computer_use_step_arguments_invalid";
                break;
            }

            // The same act on the same control that just failed is not tried
            // again: the model is asked for another step (§4.2).
            if (steps.Count > 0 && steps[^1] is JsonObject previous
                && (bool?)previous["ok"] == false
                && SameStep(previous, decision.Operation, stepArguments))
            {
                errorCode = "computer_use_repeated_step";
                break;
            }

            context.SetStatus($"Paso {steps.Count + 1}: {Describe(decision.Operation, stepArguments)}");
            var record = new JsonObject
            {
                ["step"] = steps.Count + 1,
                ["operation"] = decision.Operation,
                ["source"] = fromProcedure ? "procedure" : "model",
            };
            foreach (string key in new[] { "label", "index", "text", "key", "target", "direction", "amount", "appId" })
            {
                if (stepArguments[key] is JsonNode value)
                {
                    record[key] = value.DeepClone();
                }
            }

            PreparedOperation prepared = context.Registry.GetOrAdd(new RoutedOperation(decision.Operation, stepArguments));
            var stepWatch = Stopwatch.StartNew();
            OperationResponse response;
            try
            {
                response = await context.Core.SendOperationAsync(prepared, ActionTimeout, cancellationToken)
                    .ConfigureAwait(true);
            }
            catch (Exception exception) when (exception is TimeoutException or IOException or InvalidOperationException)
            {
                _ = context.MarkResolved(context.Registry, prepared);
                record["ok"] = false;
                record["error"] = "computer_use_step_failed";
                steps.Add(record);
                state["elapsedMs"] = alreadyElapsed + stopwatch.ElapsedMilliseconds;
                errorCode = "computer_use_step_failed";
                break;
            }

            if (PendingOperationConfirmation.TryCreate(response, prepared, TimeProvider.System,
                    out PendingOperationConfirmation? confirmation) && confirmation is not null)
            {
                // This exact invocation reaches a person (§2.1): the mission
                // waits on it and resumes with the answer.
                state["pendingStep"] = record;
                state["elapsedMs"] = alreadyElapsed + stopwatch.ElapsedMilliseconds;
                ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.confirm",
                    $"step.{steps.Count + 1}.{ShellTrace.SanitizeLabel(decision.Operation)}");
                return new Result(null, missionPrepared, confirmation);
            }

            RecordResponse(record, response);
            _ = context.MarkResolved(context.Registry, prepared);
            steps.Add(record);
            if (decision.Operation == "app.open" && (int?)record["processId"] is > 0 and int opened)
            {
                // From here on the mission looks at that application's window.
                state["processId"] = opened;
            }

            if ((bool?)record["ok"] != true && fromProcedure)
            {
                // The learned sequence deviated: from here on the model decides.
                state["procedureDeviated"] = true;
                state["procedureIndex"] = -1;
            }

            state["elapsedMs"] = alreadyElapsed + stopwatch.ElapsedMilliseconds;
            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer.use.step",
                $"step.{steps.Count}.{ShellTrace.SanitizeLabel(decision.Operation)}.ok.{((bool?)record["ok"] == true ? "true" : "false")}.ms.{stepWatch.ElapsedMilliseconds}");
            // The window redraws after the act, not during it; an application
            // brought to the front needs a moment more before its window owns
            // the foreground (measured: GetForegroundWindow returned nothing
            // right after app.open on the Calculator).
            await Task.Delay(decision.Operation == "app.open" ? 1200 : 400, cancellationToken).ConfigureAwait(true);
        }

        _ = context.MarkResolved(context.Registry, missionPrepared);
        state["elapsedMs"] = alreadyElapsed + stopwatch.ElapsedMilliseconds;
        JsonObject observed = Observed(state, steps, reached, satisfiedBy, evidence, errorCode, lastView);
        if (reached && context.Procedures is not null)
        {
            observed["procedure"] = context.Procedures.Learn(state, steps);
        }
        else if (context.Procedures is not null && (string?)state["procedureKey"] is { Length: > 0 })
        {
            observed["procedure"] = (bool?)state["procedureDeviated"] == true ? "deviated" : "abandoned";
        }

        ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.end",
            $"reached.{(reached ? "true" : "false")}.steps.{steps.Count}.ms.{(long?)state["elapsedMs"] ?? 0}.model_ms.{(long?)state["modelMs"] ?? 0}.{ShellTrace.SanitizeLabel(errorCode ?? "ok")}");
        execution.ComputerUse = null;
        return new Result(Synthesize(missionPrepared, reached, errorCode, observed), missionPrepared, null);
    }

    /// <summary>The person confirmed (or the core executed) the primitive the mission was waiting on.</summary>
    internal static void RecordConfirmedStep(
        PendingMindPlanExecution execution,
        PreparedOperation prepared,
        OperationResponse response)
    {
        ArgumentNullException.ThrowIfNull(execution);
        ArgumentNullException.ThrowIfNull(prepared);
        ArgumentNullException.ThrowIfNull(response);
        if (execution.ComputerUse is not { } state)
        {
            return;
        }

        JsonArray steps = state["steps"] as JsonArray ?? new JsonArray();
        state["steps"] = steps;
        JsonObject record = state["pendingStep"] as JsonObject ?? new JsonObject
        {
            ["step"] = steps.Count + 1,
            ["operation"] = prepared.OperationName,
            ["source"] = "model",
        };
        state.Remove("pendingStep");
        record = record.DeepClone() as JsonObject ?? record;
        record["confirmed"] = true;
        RecordResponse(record, response);
        steps.Add(record);
        if ((bool?)record["ok"] == true && Kernel.Policy.RiskPolicy.ReachesAPerson(prepared.OperationName, prepared.Arguments))
        {
            state["joined"] = prepared.OperationName == "input.visible.click";
        }
    }

    private static JsonObject Begin(JsonObject arguments, string objective, ComputerUseProcedures? procedures)
    {
        string goal = (string?)arguments["goal"] is { Length: > 0 } text ? text.Trim() : objective;
        string? application = (string?)arguments["application"];
        string? successCheck = (string?)arguments["successCheck"];
        int budget = arguments["budgetSteps"] is JsonValue budgetValue && budgetValue.TryGetValue(out int requested)
            ? Math.Clamp(requested, 1, MaximumBudgetSteps)
            : DefaultBudgetSteps;
        var state = new JsonObject
        {
            ["goal"] = goal,
            ["application"] = application,
            ["successCheck"] = successCheck,
            ["budgetSteps"] = budget,
            ["startedUtc"] = DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
            ["steps"] = new JsonArray(),
            ["elapsedMs"] = 0L,
            ["modelMs"] = 0L,
        };
        if (procedures?.Find(application, goal) is { } procedure)
        {
            state["procedureKey"] = ComputerUseProcedures.Key(application, goal);
            state["procedureIndex"] = 0;
            state["procedureSteps"] = procedure.DeepClone();
            if (successCheck is null && (string?)procedure["successCheck"] is { Length: > 0 } learnedCheck)
            {
                state["successCheck"] = learnedCheck;
            }
        }

        return state;
    }

    private static bool NextProcedureOpens(JsonObject state) =>
        (int?)state["procedureIndex"] is int index && index >= 0
        && state["procedureSteps"]?["steps"] is JsonArray recorded && index < recorded.Count
        && (string?)recorded[index]?["operation"] == "app.open";

    private static MindComputerUseStep? NextProcedureStep(JsonObject state, int stepsDone)
    {
        if ((int?)state["procedureIndex"] is not { } index || index < 0
            || state["procedureSteps"] is not JsonObject procedure
            || procedure["steps"] is not JsonArray recorded
            || index >= recorded.Count
            || index != stepsDone)
        {
            return null;
        }

        if (recorded[index] is not JsonObject step
            || (string?)step["operation"] is not { Length: > 0 } operation
            || step["arguments"] is not JsonObject arguments)
        {
            state["procedureIndex"] = -1;
            return null;
        }

        state["procedureIndex"] = index + 1;
        return new MindComputerUseStep(operation, arguments.DeepClone() as JsonObject ?? new JsonObject(), "procedure");
    }

    /// <summary>
    /// Once a view shows the window the provider resolved as the mission's
    /// application (titled like it, or the person's browser for «the
    /// browser»), the mission keeps looking at that process (a later
    /// foreground change does not move the surface).
    /// </summary>
    internal static void AdoptWindow(JsonObject state, JsonObject view)
    {
        if ((int?)state["processId"] is > 0 || (string?)state["application"] is not { Length: > 0 })
            return;
        if (view["window"] is JsonObject window && (bool?)window["requested"] == true
            && (int?)window["processId"] is > 0 and int owner)
            state["processId"] = owner;
    }

    private static async Task<JsonObject?> LookAsync(
        Context context,
        JsonObject state,
        CancellationToken cancellationToken)
    {
        var arguments = new JsonObject { ["includeText"] = true, ["limit"] = 60 };
        if ((int?)state["processId"] is > 0 and int owner)
        {
            arguments["processId"] = owner;
        }

        if ((string?)state["application"] is { Length: > 0 } application)
        {
            // The window titled like the application is the surface until the
            // process is known, and when that process shows no window (measured:
            // app.open failed to verify under a fullscreen player and the view
            // read the player instead); «the browser» is always the front window
            // of the person's browser.
            arguments["application"] = application;
        }

        if ((string?)state["waitForLabel"] is { Length: > 0 } waited)
        {
            arguments["waitForLabel"] = waited;
            state.Remove("waitForLabel");
        }

        PreparedOperation prepared = context.Registry.GetOrAdd(new RoutedOperation("input.visible.controls", arguments));
        try
        {
            OperationResponse response = await context.Core.SendOperationAsync(prepared, ViewTimeout, cancellationToken)
                .ConfigureAwait(false);
            if (response.Status != OperationStatuses.Completed
                || !response.Verified
                || response.Result is not { ValueKind: JsonValueKind.Object } result)
            {
                return null;
            }

            return JsonNode.Parse(result.GetRawText()) as JsonObject;
        }
        catch (Exception exception) when (exception is TimeoutException or IOException or InvalidOperationException)
        {
            return null;
        }
        finally
        {
            _ = context.MarkResolved(context.Registry, prepared);
        }
    }

    private static void RecordResponse(JsonObject record, OperationResponse response)
    {
        bool ok = response.Status == OperationStatuses.Completed && response.Verified;
        record["ok"] = ok;
        if (!ok)
        {
            record["error"] = response.ErrorCode
                ?? (response.Status == OperationStatuses.Pending ? "computer_use_step_pending" : "computer_use_step_failed");
        }

        if (response.Result is { ValueKind: JsonValueKind.Object } result)
        {
            foreach (string key in new[] { "cascadeStage", "surfaceChanged", "absentOrDisabled", "selected", "toggled", "processId", "name", "alreadyRunning", "windowTitle" })
            {
                if (result.TryGetProperty(key, out JsonElement value)
                    && value.ValueKind is JsonValueKind.String or JsonValueKind.True
                        or JsonValueKind.False or JsonValueKind.Number)
                {
                    record[key] = JsonNode.Parse(value.GetRawText());
                }
            }
        }

        if (ok)
        {
            record["changed"] = (bool?)record["surfaceChanged"] == true
                || (bool?)record["absentOrDisabled"] == true
                || (bool?)record["selected"] == true
                || (bool?)record["toggled"] == true
                || (string?)record["operation"] is "app.open" or "input.key.press" or "input.text.type";
        }
    }

    private static bool SameStep(JsonObject previous, string operation, JsonObject arguments)
    {
        if ((string?)previous["operation"] != operation)
        {
            return false;
        }

        foreach (string key in new[] { "label", "index", "text", "key", "direction", "appId" })
        {
            string? before = previous[key]?.ToJsonString();
            string? now = arguments[key]?.ToJsonString();
            if (!string.Equals(before, now, StringComparison.Ordinal))
            {
                return false;
            }
        }

        return true;
    }

    private static string Describe(string operation, JsonObject arguments) => operation switch
    {
        "input.visible.click" => $"clic en «{(string?)arguments["label"]}»",
        "input.text.type" => "escribiendo",
        "input.key.press" => $"tecla {(string?)arguments["key"]}",
        "input.scroll" => "desplazando",
        "app.open" => "abriendo la aplicación",
        _ => operation,
    };

    private static JsonObject Observed(
        JsonObject state, JsonArray steps, bool reached, string? satisfiedBy, string? evidence, string? errorCode,
        JsonObject? lastView)
    {
        var observed = new JsonObject
        {
            ["goal"] = state["goal"]?.DeepClone(),
            ["application"] = state["application"]?.DeepClone(),
            ["reached"] = reached,
            ["successCheck"] = state["successCheck"]?.DeepClone(),
            ["stepCount"] = steps.Count,
            ["steps"] = steps.DeepClone(),
            ["window"] = state["window"]?.DeepClone(),
            ["joined"] = (bool?)state["joined"] == true,
            ["elapsedMs"] = (long?)state["elapsedMs"] ?? 0,
            ["modelMs"] = (long?)state["modelMs"] ?? 0,
            ["authority"] = "shell_loop_over_uia_ocr_postread",
        };
        if (satisfiedBy is not null)
        {
            observed["satisfiedBy"] = satisfiedBy;
        }

        if (lastView is not null)
        {
            observed["screen"] = ScreenExcerpt(lastView);
        }

        if (evidence is not null)
        {
            observed["evidence"] = evidence;
        }

        if (errorCode is not null)
        {
            observed["stoppedBy"] = errorCode;
        }

        return observed;
    }

    // What was on the screen when the mission ended, for the final to quote:
    // the controls that carry a value (a display, a field) and a few lines.
    private static JsonObject ScreenExcerpt(JsonObject view)
    {
        var values = new JsonArray();
        if (view["controls"] is JsonArray controls)
        {
            foreach (JsonNode? node in controls)
            {
                if (node is JsonObject control && (string?)control["value"] is { Length: > 0 } value && values.Count < 5)
                {
                    values.Add((JsonNode?)new JsonObject
                    {
                        ["name"] = (string?)control["name"],
                        ["value"] = value.Length > 80 ? value[..80] : value,
                    });
                }
            }
        }

        var lines = new JsonArray();
        if (view["text"] is JsonObject text)
        {
            foreach (string zone in new[] { "T", "C", "TL", "TR", "L", "R", "B", "BL", "BR" })
            {
                if (text[zone] is not JsonArray zoneLines)
                {
                    continue;
                }

                foreach (JsonNode? line in zoneLines)
                {
                    if (lines.Count >= 6)
                    {
                        break;
                    }

                    lines.Add((JsonNode?)JsonValue.Create((string?)line ?? string.Empty));
                }
            }
        }

        // What carries a number is usually the answer a person looks for (a
        // display, a counter, a price): named controls and lines with digits.
        var numbers = new JsonArray();
        if (view["controls"] is JsonArray named)
        {
            foreach (JsonNode? node in named)
            {
                if (node is JsonObject control && (string?)control["name"] is { Length: > 0 } name
                    && name.Any(char.IsAsciiDigit) && numbers.Count < 6)
                {
                    numbers.Add((JsonNode?)JsonValue.Create(name.Length > 80 ? name[..80] : name));
                }
            }
        }

        foreach (JsonNode? line in lines)
        {
            if ((string?)line is { Length: > 0 } written && written.Any(char.IsAsciiDigit) && numbers.Count < 6)
            {
                numbers.Add((JsonNode?)JsonValue.Create(written));
            }
        }

        var excerpt = new JsonObject { ["title"] = (string?)view["window"]?["title"] };
        if (values.Count > 0)
        {
            excerpt["values"] = values;
        }

        if (numbers.Count > 0)
        {
            excerpt["numbers"] = numbers;
        }

        if (lines.Count > 0)
        {
            excerpt["lines"] = lines;
        }

        return excerpt;
    }

    private static OperationResponse Synthesize(
        PreparedOperation prepared, bool reached, string? errorCode, JsonObject observed)
    {
        using JsonDocument document = JsonDocument.Parse(observed.ToJsonString());
        JsonElement result = document.RootElement.Clone();
        OperationOutcome outcome = reached
            ? OperationOutcome.Success(result)
            : OperationOutcome.Failure(errorCode ?? "computer_use_failed", result);
        string message = OperationVisibleFacts.FromOutcome(OperationName, outcome);
        return new OperationResponse(
            ProtocolTypes.OperationResponse,
            prepared.InvocationId,
            prepared.MissionId,
            prepared.InvocationId,
            reached ? OperationStatuses.Completed : OperationStatuses.Failed,
            message,
            reached,
            false,
            result,
            reached ? null : errorCode ?? "computer_use_failed");
    }

    // ------------------------------------------------------------ the view

    /// <summary>What the mind receives: indices, kinds, names, states, zones, colours and the text by zone; no rectangles, hashes or identities.</summary>
    internal static JsonObject CompactForTheMind(JsonObject view)
    {
        var compact = new JsonObject();
        if (view["window"] is JsonObject window)
        {
            compact["window"] = new JsonObject
            {
                ["title"] = window["title"]?.DeepClone(),
                ["process"] = window["process"]?.DeepClone(),
                ["focused"] = window["focused"]?.DeepClone(),
            };
        }

        var controls = new JsonArray();
        if (view["controls"] is JsonArray listed)
        {
            foreach (JsonNode? node in listed)
            {
                if (node is not JsonObject control)
                {
                    continue;
                }

                var item = new JsonObject
                {
                    ["i"] = control["i"]?.DeepClone(),
                    ["kind"] = control["kind"]?.DeepClone(),
                    ["name"] = control["name"]?.DeepClone(),
                };
                if ((string?)control["state"] is { Length: > 0 } state)
                {
                    item["state"] = state;
                }

                if ((string?)control["value"] is { Length: > 0 } value)
                {
                    item["value"] = value.Length > 40 ? value[..40] : value;
                }

                if ((string?)control["zone"] is { Length: > 0 } zone)
                {
                    item["zone"] = zone;
                }

                if ((string?)control["color"] is { Length: > 0 } color)
                {
                    item["color"] = color;
                }

                if (control["repeated"] is JsonValue repeated)
                {
                    item["repeated"] = repeated.DeepClone();
                }

                controls.Add((JsonNode?)item);
            }
        }

        compact["controls"] = controls;
        if (view["text"] is JsonObject text)
        {
            compact["text"] = text.DeepClone();
        }

        if (view["newText"] is JsonArray appeared)
        {
            compact["newText"] = appeared.DeepClone();
        }

        return compact;
    }

    private static JsonArray HistoryForMind(JsonArray steps)
    {
        var history = new JsonArray();
        int start = Math.Max(0, steps.Count - HistoryForTheMind);
        for (int index = start; index < steps.Count; index++)
        {
            if (steps[index] is not JsonObject step)
            {
                continue;
            }

            var item = new JsonObject
            {
                ["step"] = step["step"]?.DeepClone(),
                ["operation"] = step["operation"]?.DeepClone(),
                ["ok"] = step["ok"]?.DeepClone(),
            };
            foreach (string key in new[] { "label", "index", "text", "key", "direction", "appId", "error", "changed" })
            {
                if (step[key] is JsonNode value)
                {
                    item[key] = value.DeepClone();
                }
            }

            history.Add((JsonNode?)item);
        }

        return history;
    }

    private static string ViewSignature(JsonObject view)
    {
        var parts = new StringBuilder();
        if (view["window"] is JsonObject window)
        {
            parts.Append((string?)window["title"]).Append('\n');
        }

        if (view["controls"] is JsonArray controls)
        {
            foreach (JsonNode? control in controls)
            {
                if (control is JsonObject item)
                {
                    parts.Append((string?)item["kind"]).Append('|').Append((string?)item["name"])
                        .Append('|').Append((string?)item["state"]).Append('|').Append((string?)item["value"]).Append('\n');
                }
            }
        }

        if (view["text"] is JsonObject text)
        {
            parts.Append(text.ToJsonString());
        }

        return parts.ToString();
    }

    private static int ControlCount(JsonObject view) =>
        view["controls"] is JsonArray controls ? controls.Count : 0;

    private static int TextCount(JsonObject view)
    {
        int count = 0;
        if (view["text"] is JsonObject text)
        {
            foreach ((string _, JsonNode? zone) in text)
            {
                count += zone is JsonArray lines ? lines.Count : 0;
            }
        }

        return count;
    }
}

/// <summary>
/// The deterministic success check of a mission (CONTRATO_VISTA_ACCION.md
/// §4.3), evaluated by the shell over the last view and over independent
/// receipts; never by the model.
/// </summary>
internal static class ComputerUseSuccessCheck
{
    internal static bool Evaluate(string? check, JsonObject view, JsonArray steps, out string? satisfiedBy)
    {
        satisfiedBy = null;
        if (string.IsNullOrWhiteSpace(check))
        {
            return false;
        }

        foreach (string term in check.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            string[] atoms = term.Split('&', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
            if (atoms.Length > 0 && atoms.All(atom => Atom(atom, view, steps)))
            {
                satisfiedBy = term;
                return true;
            }
        }

        return false;
    }

    internal static bool Atom(string atom, JsonObject view, JsonArray steps)
    {
        int colon = atom.IndexOf(':', StringComparison.Ordinal);
        if (colon <= 0)
        {
            return false;
        }

        string kind = atom[..colon].Trim().ToLowerInvariant();
        string rest = atom[(colon + 1)..].Trim();
        switch (kind)
        {
            case "text":
                return ViewContains(view, rest);
            case "title":
                return view["window"] is JsonObject titled
                    && Fold((string?)titled["title"]).Contains(Fold(rest), StringComparison.Ordinal);
            case "process":
                return view["window"] is JsonObject owned
                    && Fold((string?)owned["process"]).Contains(Fold(rest), StringComparison.Ordinal);
            case "control":
                {
                    string name = rest;
                    string? state = null;
                    int split = rest.LastIndexOf(':');
                    if (split > 0 && rest[(split + 1)..] is "selected" or "on" or "off" or "expanded" or "focused" or "collapsed")
                    {
                        name = rest[..split];
                        state = rest[(split + 1)..];
                    }

                    return FindControls(view, name).Any(control => state is null
                        || Fold((string?)control["state"]).Split(' ').Contains(state));
                }
            case "value":
                {
                    int equals = rest.IndexOf('=', StringComparison.Ordinal);
                    if (equals <= 0)
                    {
                        return false;
                    }

                    string needle = Fold(rest[(equals + 1)..]);
                    return FindControls(view, rest[..equals]).Any(control =>
                        Fold((string?)control["value"]).Contains(needle, StringComparison.Ordinal));
                }
            case "count":
                return CountAtom(rest, view);
            case "page":
                return PageAtom(rest, view, steps);
            case "stepdone":
                {
                    string[] parts = rest.Split(':', 2);
                    string operation = parts[0].Trim();
                    string? argument = parts.Length > 1 ? Fold(parts[1]) : null;
                    foreach (JsonNode? node in steps)
                    {
                        if (node is not JsonObject step || (bool?)step["ok"] != true
                            || (string?)step["operation"] != operation)
                        {
                            continue;
                        }

                        if (argument is null
                            || Fold((string?)step["key"]) == argument
                            || Fold((string?)step["label"]).Contains(argument, StringComparison.Ordinal))
                        {
                            return true;
                        }
                    }

                    return false;
                }
            case "file":
                return rest.Length > 0 && Path.IsPathRooted(rest) && File.Exists(rest);
            case "manifest":
                return SteamManifestExists(rest);
            default:
                return false;
        }
    }

    // «ir a X» on a window drawn without an accessible tree (CEF, Electron, canvas; measured on Steam): X is still on
    // screen, a click was verified, and most of the written text is new against the mission's first look. A menu
    // the click opened changes a few lines (Steam: 3 of 25); the page reached changes most of them.
    private static bool PageAtom(string rest, JsonObject view, JsonArray steps)
    {
        if (!ViewContains(view, rest)
            || !steps.Any(node => node is JsonObject step && (bool?)step["ok"] == true
                && (string?)step["operation"] == "input.visible.click"))
        {
            return false;
        }

        var baseline = new HashSet<string>(
            (view["baselineText"] as JsonArray ?? []).Select(line => (string?)line ?? string.Empty),
            StringComparer.Ordinal);
        JsonArray current = TextLines(view);
        if (baseline.Count < 5 || current.Count < 5)
        {
            return false;
        }

        int kept = current.Count(line => baseline.Contains((string?)line ?? string.Empty));
        return kept * 2 < current.Count;
    }

    internal static JsonArray TextLines(JsonObject view)
    {
        var lines = new JsonArray();
        if (view["text"] is JsonObject zones)
        {
            foreach ((string _, JsonNode? zone) in zones)
            {
                if (zone is not JsonArray zoneLines)
                {
                    continue;
                }

                foreach (JsonNode? line in zoneLines)
                {
                    string folded = Fold((string?)line);
                    if (folded.Length > 0)
                    {
                        lines.Add(folded);
                    }
                }
            }
        }

        return lines;
    }

    private static bool CountAtom(string rest, JsonObject view)
    {
        var match = System.Text.RegularExpressions.Regex.Match(
            rest, @"^([A-Za-z]+)\s*(<=|>=|==|<|>|=)\s*(\d+)$");
        if (!match.Success || !int.TryParse(match.Groups[3].Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out int expected))
        {
            return false;
        }

        string kind = match.Groups[1].Value;
        int count = 0;
        if (view["controls"] is JsonArray controls)
        {
            foreach (JsonNode? node in controls)
            {
                if (node is JsonObject control
                    && string.Equals((string?)control["kind"], kind, StringComparison.OrdinalIgnoreCase))
                {
                    count += 1 + ((int?)control["repeated"] ?? 0);
                }
            }
        }

        return match.Groups[2].Value switch
        {
            "<=" => count <= expected,
            ">=" => count >= expected,
            "<" => count < expected,
            ">" => count > expected,
            _ => count == expected,
        };
    }

    private static IEnumerable<JsonObject> FindControls(JsonObject view, string name)
    {
        string needle = Fold(name);
        if (needle.Length == 0 || view["controls"] is not JsonArray controls)
        {
            yield break;
        }

        foreach (JsonNode? node in controls)
        {
            if (node is JsonObject control && Fold((string?)control["name"]).Contains(needle, StringComparison.Ordinal))
            {
                yield return control;
            }
        }
    }

    internal static bool ViewContains(JsonObject view, string needle)
    {
        string folded = Fold(needle);
        if (folded.Length == 0)
        {
            return false;
        }

        if (view["window"] is JsonObject window && Fold((string?)window["title"]).Contains(folded, StringComparison.Ordinal))
        {
            return true;
        }

        if (view["controls"] is JsonArray controls)
        {
            foreach (JsonNode? node in controls)
            {
                if (node is JsonObject control
                    && (Fold((string?)control["name"]).Contains(folded, StringComparison.Ordinal)
                        || Fold((string?)control["value"]).Contains(folded, StringComparison.Ordinal)))
                {
                    return true;
                }
            }
        }

        if (view["text"] is JsonObject text)
        {
            var joined = new StringBuilder();
            foreach ((string _, JsonNode? zone) in text)
            {
                if (zone is JsonArray lines)
                {
                    foreach (JsonNode? line in lines)
                    {
                        joined.Append((string?)line).Append(' ');
                    }
                }
            }

            if (Fold(joined.ToString()).Contains(folded, StringComparison.Ordinal))
            {
                return true;
            }
        }

        return false;
    }

    private static bool SteamManifestExists(string appId)
    {
        if (!appId.All(char.IsAsciiDigit) || appId.Length == 0)
        {
            return false;
        }

        foreach (string library in SteamLibraries())
        {
            if (File.Exists(Path.Combine(library, "steamapps", $"appmanifest_{appId}.acf")))
            {
                return true;
            }
        }

        return false;
    }

    private static IEnumerable<string> SteamLibraries()
    {
        string programs = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);
        string root = Path.Combine(programs, "Steam");
        yield return root;
        string folders = Path.Combine(root, "steamapps", "libraryfolders.vdf");
        if (!File.Exists(folders))
        {
            yield break;
        }

        string[] lines;
        try
        {
            lines = File.ReadAllLines(folders);
        }
        catch (IOException)
        {
            yield break;
        }

        foreach (string line in lines)
        {
            var match = System.Text.RegularExpressions.Regex.Match(line, "\"path\"\\s+\"(.+)\"");
            if (match.Success)
            {
                yield return match.Groups[1].Value.Replace("\\\\", "\\", StringComparison.Ordinal);
            }
        }
    }

    internal static string Fold(string? value)
    {
        if (string.IsNullOrEmpty(value))
        {
            return string.Empty;
        }

        string form = value.Normalize(NormalizationForm.FormD).ToLowerInvariant();
        var builder = new StringBuilder(form.Length);
        foreach (char character in form)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) != UnicodeCategory.NonSpacingMark)
            {
                builder.Append(character);
            }
        }

        return string.Join(' ', builder.ToString().Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
    }
}

/// <summary>
/// Procedure memory (CONTRATO_VISTA_ACCION.md §5): a reached mission stores
/// its verified sequence under application + normalized goal in the private
/// data root; the next time it is replayed step by step and the model only
/// intervenes when the replay deviates. The saving is measured (modelMs of
/// the learning run against the replay's elapsed time).
/// </summary>
internal sealed class ComputerUseProcedures
{
    private const int MaximumProcedures = 256;
    private readonly string _path;
    private JsonObject? _document;

    internal ComputerUseProcedures(string path)
    {
        _path = path ?? throw new ArgumentNullException(nameof(path));
    }

    internal static ComputerUseProcedures CreateDefault() =>
        new(Path.Combine(MemoryOperationProtector.ResolveDataRoot(), "computer-use", "procedures.v1.json"));

    internal static string Key(string? application, string goal) =>
        ComputerUseSuccessCheck.Fold(application) + "|" + NormalizeGoal(goal);

    internal static string NormalizeGoal(string goal)
    {
        string folded = ComputerUseSuccessCheck.Fold(goal);
        folded = System.Text.RegularExpressions.Regex.Replace(
            folded, @"^(?:(?:por favor|please|baxy)[,\s]+)+", string.Empty);
        return folded.Trim(' ', '.', '!', '?');
    }

    internal JsonObject? Find(string? application, string goal)
    {
        JsonObject document = Load();
        return document["procedures"] is JsonObject procedures
            && procedures[Key(application, goal)] is JsonObject procedure
            && procedure["steps"] is JsonArray { Count: > 0 }
                ? procedure
                : null;
    }

    /// <summary>Stores the reached mission; returns how the memory took part: replayed, learned or relearned.</summary>
    internal string Learn(JsonObject state, JsonArray steps)
    {
        string goal = (string?)state["goal"] ?? string.Empty;
        string? application = (string?)state["application"];
        string key = Key(application, goal);
        JsonObject document = Load();
        JsonObject procedures = document["procedures"] as JsonObject ?? new JsonObject();
        document["procedures"] = procedures;
        bool replayed = (string?)state["procedureKey"] == key && (bool?)state["procedureDeviated"] != true
            && steps.All(step => step is JsonObject item && (string?)item["source"] == "procedure");
        string outcome;
        if (replayed && procedures[key] is JsonObject existing)
        {
            existing["replays"] = ((int?)existing["replays"] ?? 0) + 1;
            existing["runs"] = ((int?)existing["runs"] ?? 0) + 1;
            existing["lastReplayMs"] = (long?)state["elapsedMs"] ?? 0;
            existing["lastReplayUtc"] = DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture);
            outcome = "replayed";
        }
        else if (steps.Any(node => node is JsonObject step && (bool?)step["ok"] != true
            && (string?)step["operation"] != "app.open"))
        {
            // Contract §5: only a mission reached without failed steps is learned. Measured on Steam: the failed
            // click had opened the menu and was dropped; the step left («Chrome Legacy Window») was meaningless.
            // An opening that did not verify (a UWP app hosted by its frame) is not a failed step: it is skipped.
            outcome = "none";
        }
        else
        {
            var recorded = new JsonArray();
            foreach (JsonNode? node in steps)
            {
                if (node is not JsonObject step || (bool?)step["ok"] != true)
                {
                    continue;
                }

                var arguments = new JsonObject();
                foreach (string field in new[] { "label", "index", "text", "key", "target", "direction", "amount", "appId" })
                {
                    if (step[field] is JsonNode value && field != "index")
                    {
                        arguments[field] = value.DeepClone();
                    }
                }

                recorded.Add((JsonNode?)new JsonObject
                {
                    ["operation"] = step["operation"]?.DeepClone(),
                    ["arguments"] = arguments,
                    ["expect"] = (bool?)step["surfaceChanged"] == true ? "surfaceChanged"
                        : (bool?)step["absentOrDisabled"] == true ? "controlGone"
                        : (bool?)step["selected"] == true ? "selected"
                        : (bool?)step["toggled"] == true ? "toggled"
                        : "verified",
                });
            }

            if (recorded.Count == 0)
            {
                return "none";
            }

            bool existed = procedures[key] is JsonObject;
            int runs = existed ? ((int?)((JsonObject)procedures[key]!)["runs"] ?? 0) + 1 : 1;
            procedures[key] = new JsonObject
            {
                ["application"] = application,
                ["goal"] = goal,
                ["steps"] = recorded,
                ["successCheck"] = state["successCheck"]?.DeepClone(),
                ["learnedUtc"] = DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
                ["runs"] = runs,
                ["replays"] = 0,
                ["lastModelMs"] = (long?)state["modelMs"] ?? 0,
                ["lastLearnMs"] = (long?)state["elapsedMs"] ?? 0,
            };
            outcome = existed ? "relearned" : "learned";
            while (procedures.Count > MaximumProcedures)
            {
                string oldest = procedures.First().Key;
                procedures.Remove(oldest);
            }
        }

        Save(document);
        return outcome;
    }

    private JsonObject Load()
    {
        if (_document is not null)
        {
            return _document;
        }

        try
        {
            if (File.Exists(_path)
                && new FileInfo(_path).Length <= 4 * 1024 * 1024
                && JsonNode.Parse(File.ReadAllText(_path)) is JsonObject stored
                && (int?)stored["version"] == 1)
            {
                _document = stored;
                return stored;
            }
        }
        catch (Exception exception) when (exception is IOException or JsonException or UnauthorizedAccessException)
        {
        }

        _document = new JsonObject { ["version"] = 1, ["procedures"] = new JsonObject() };
        return _document;
    }

    private void Save(JsonObject document)
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
            string temporary = _path + "." + Guid.NewGuid().ToString("N") + ".tmp";
            File.WriteAllText(temporary, document.ToJsonString(), new UTF8Encoding(false));
            File.Move(temporary, _path, overwrite: true);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
        }
    }
}
