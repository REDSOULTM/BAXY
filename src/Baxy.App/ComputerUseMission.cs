using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
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
/// invocation; the mission resumes with the person's «sí». A chained mission
/// («steps») runs its sub-goals in order, each with its own application,
/// success check, budget and learned procedure; the whole mission is reached
/// when every sub-goal is.
/// </summary>
internal static class ComputerUseMission
{
    internal const string OperationName = "mission.computer.use";
    internal const int DefaultBudgetSteps = 12;
    internal const int MaximumBudgetSteps = 30;
    internal const int SubgoalBudgetSteps = 10;
    private const int HistoryForTheMind = 6;
    private static readonly TimeSpan TimeBudget = TimeSpan.FromSeconds(90);
    private static readonly TimeSpan SubgoalTimeBudget = TimeSpan.FromSeconds(30);
    private static readonly TimeSpan ChainTimeBudget = TimeSpan.FromSeconds(180);
    private static readonly TimeSpan ViewTimeout = TimeSpan.FromSeconds(30);
    private static readonly TimeSpan ActionTimeout = TimeSpan.FromSeconds(45);
    private const int CoveredLooks = 4;
    private static readonly TimeSpan CoveredLookInterval = TimeSpan.FromMilliseconds(2500);

    // After an act the window redraws: a short settle, not a fixed wait. After
    // app.open the next look waits, bounded, only until a view shows the
    // application's window (measured: GetForegroundWindow returned nothing
    // right after app.open on the Calculator; a fixed 1.2 s was paid always).
    internal static readonly TimeSpan Settle = TimeSpan.FromMilliseconds(150);
    private static readonly TimeSpan WindowWait = TimeSpan.FromSeconds(3);
    private static readonly TimeSpan StartWait = TimeSpan.FromSeconds(10);

    // What belongs to the sub-goal being worked on and starts again with the next one.
    private static readonly string[] SubgoalFields =
    [
        "baselineText", "textBeforeClick", "lastText", "lastSignature", "unchangedViews", "coveredLooks", "waitForLabel", "awaitWindow",
        "procedureKey", "procedureIndex", "procedureSteps", "procedureDeviated",
    ];

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
        /// <summary>Sends one prepared operation through the core (kernel, provider, post-read).</summary>
        internal required Func<PreparedOperation, TimeSpan, CancellationToken, Task<OperationResponse>> Execute { get; init; }

        /// <summary>Asks the mind for one step over the compact view.</summary>
        internal required Func<ComputerUseStepRequest, CancellationToken, Task<MindComputerUseStep?>> Decide { get; init; }

        internal required RetryableOperationRegistry Registry { get; init; }
        internal required Func<RetryableOperationRegistry, PreparedOperation, bool> MarkResolved { get; init; }
        internal required Action<string> SetStatus { get; init; }
        internal ComputerUseProcedures? Procedures { get; init; }
        internal Func<TimeSpan, CancellationToken, Task> Delay { get; init; } = Task.Delay;
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
        JsonArray plan = (JsonArray)state["subgoals"]!;
        bool chained = (bool?)state["chained"] == true;
        int budget = (int?)state["budgetSteps"] ?? DefaultBudgetSteps;
        long missionTimeMs = (long)(chained ? ChainTimeBudget : TimeBudget).TotalMilliseconds;
        string? errorCode = null;
        bool reached = false;
        string? evidence = null;
        string? satisfiedBy = null;
        JsonObject? lastView = null;
        // The last view of the sub-goal at hand: what decides whether the next look needs the OCR text.
        JsonObject? subgoalView = null;
        ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.start",
            $"budget.{budget}.steps_done.{steps.Count}.subgoals.{plan.Count}");

        while (true)
        {
            cancellationToken.ThrowIfCancellationRequested();
            int index = (int?)state["subgoal"] ?? 0;
            JsonObject current = (JsonObject)plan[index]!;
            string goal = (string?)current["goal"] ?? execution.Objective;
            string? application = (string?)current["application"];
            string? successCheck = (string?)current["successCheck"];
            int subgoalBudget = (int?)current["budgetSteps"] ?? budget;
            int start = (int?)state["subgoalStart"] ?? 0;
            int done = steps.Count - start;
            long elapsedMs = alreadyElapsed + stopwatch.ElapsedMilliseconds;
            if (elapsedMs > missionTimeMs
                || elapsedMs - ((long?)state["subgoalStartMs"] ?? 0) > ((long?)current["timeMs"] ?? missionTimeMs))
            {
                errorCode = "computer_use_time_exhausted";
                break;
            }

            bool subgoalReached = false;
            string? subgoalBy = null;
            string? subgoalEvidence = null;
            if (done > 0 && ComputerUseSuccessCheck.EvaluateReceipts(successCheck, SubgoalSteps(steps, start), out subgoalBy))
            {
                // The check holds on the receipts of verified steps alone (a step done, a file, a manifest): no new
                // look is needed to know it. The mission's last sub-goal still reads the controls once, without OCR,
                // so the final quotes the screen as it is now.
                subgoalReached = true;
                if (index + 1 >= plan.Count)
                {
                    lastView = await LookAsync(context, state, application, includeText: false, cancellationToken)
                        .ConfigureAwait(true) ?? lastView;
                }
            }
            else
            {
                bool lastLook = done >= subgoalBudget || steps.Count >= budget;
                context.SetStatus("Mirando la pantalla");
                bool includeText = NeedsText(goal, application, successCheck, subgoalView);
                lastView = await LookAsync(context, state, application, includeText, cancellationToken).ConfigureAwait(true);
                if (lastView is null)
                {
                    errorCode = "computer_use_view_unavailable";
                    break;
                }

                subgoalView = lastView;
                state["window"] = lastView["window"]?.DeepClone();
                AdoptWindow(state, application, lastView);
                JsonArray currentText = ComputerUseSuccessCheck.TextLines(lastView);
                // The text of the application's own first look is what «the page changed» is measured against
                // (check atom page:); the editor seen before app.open is not the application.
                if (currentText.Count > 0
                    && (application is null || (bool?)lastView["window"]?["requested"] == true))
                {
                    state["baselineText"] ??= currentText.DeepClone();
                }

                if (state["baselineText"] is JsonArray baseline)
                {
                    lastView["baselineText"] = baseline.DeepClone();
                }

                if (state["textBeforeClick"] is JsonObject beforeClicks)
                {
                    lastView["textBeforeClick"] = beforeClicks.DeepClone();
                }

                // What the last act made appear (a menu it opened, a page it loaded): the mind reads it apart.
                if (currentText.Count > 0)
                {
                    if (done > 0 && state["lastText"] is JsonArray previousText)
                    {
                        var before = new HashSet<string>(previousText.Select(line => (string?)line ?? string.Empty), StringComparer.Ordinal);
                        lastView["newText"] = new JsonArray([.. currentText
                            .Select(line => (string?)line ?? string.Empty)
                            .Where(line => !before.Contains(line))
                            .Take(12)
                            .Select(line => (JsonNode?)JsonValue.Create(line))]);
                    }

                    state["lastText"] = currentText;
                }

                if (ComputerUseSuccessCheck.Evaluate(successCheck, lastView, SubgoalSteps(steps, start), out subgoalBy))
                {
                    subgoalReached = true;
                }
                else if (lastLook)
                {
                    errorCode = "computer_use_budget_exhausted";
                    break;
                }
                else
                {
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
                            await context.Delay(CoveredLookInterval, cancellationToken).ConfigureAwait(true);
                            continue;
                        }

                        errorCode = "computer_use_window_covered";
                        break;
                    }

                    if ((bool?)lastView["window"]?["elevated"] == true)
                    {
                        // The application runs as administrator: Windows does not let a lower process read or press
                        // its controls (measured on Task Manager). Said as such instead of clicking without effect.
                        errorCode = "computer_use_window_elevated";
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
                    if (unchanged >= 2 && done > 0 && (int?)state["procedureIndex"] is >= 0 && (bool?)state["procedureDeviated"] != true)
                    {
                        // A learned sequence that stopped changing the screen is abandoned, not the mission: from
                        // here the routine and the model decide (measured: a stale Steam procedure ended the mission).
                        state["procedureDeviated"] = true;
                        state["procedureIndex"] = -1;
                        state["unchangedViews"] = 0;
                        unchanged = 0;
                    }

                    if (unchanged >= 2 && done > 0)
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
                        ? NextProcedureStep(state, done)
                        : null;
                    bool fromProcedure = decision is not null;
                    if (decision is null)
                    {
                        context.SetStatus($"Paso {steps.Count + 1}: decidiendo");
                        var modelWatch = Stopwatch.StartNew();
                        decision = await context.Decide(
                            new ComputerUseStepRequest(
                                execution.Objective, goal, application, successCheck,
                                CompactForTheMind(lastView), HistoryForMind(steps, start),
                                Math.Min(subgoalBudget - done, budget - steps.Count), index, plan.Count),
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
                        // be on the screen it was shown. A look taken without the OCR text
                        // is read again with it before the citation is judged.
                        string cited = (string?)decision.Arguments["evidence"] ?? string.Empty;
                        if (cited.Length > 0 && !ComputerUseSuccessCheck.ViewContains(lastView, cited) && TextCount(lastView) == 0)
                        {
                            lastView = await LookAsync(context, state, application, includeText: true, cancellationToken)
                                .ConfigureAwait(true) ?? lastView;
                        }

                        if (cited.Length > 0 && ComputerUseSuccessCheck.ViewContains(lastView, cited))
                        {
                            subgoalReached = true;
                            subgoalEvidence = cited;
                            subgoalBy = "model_evidence";
                        }
                        else
                        {
                            errorCode = "computer_use_evidence_not_visible";
                            break;
                        }
                    }
                    else
                    {
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
                        if (done > 0 && steps[^1] is JsonObject previous
                            && (bool?)previous["ok"] == false
                            && SameStep(previous, decision.Operation, stepArguments))
                        {
                            errorCode = "computer_use_repeated_step";
                            break;
                        }

                        var record = new JsonObject
                        {
                            ["step"] = steps.Count + 1,
                            ["operation"] = decision.Operation,
                            ["source"] = fromProcedure ? "procedure" : "model",
                        };
                        if (decision.Operation == "input.visible.click")
                        {
                            // What was written on screen right before this click: «the page changed» (check atom page:)
                            // is measured against it, not against a start-up window seen earlier (measured on Steam:
                            // the login splash was the baseline and the store passed for the library).
                            var clickTexts = state["textBeforeClick"] as JsonObject ?? new JsonObject();
                            clickTexts[(steps.Count + 1).ToString(CultureInfo.InvariantCulture)] =
                                ComputerUseSuccessCheck.TextLines(lastView);
                            state["textBeforeClick"] = clickTexts;
                        }
                        if (chained)
                        {
                            record["subgoal"] = index;
                        }

                        foreach (string key in new[] { "label", "index", "text", "key", "target", "direction", "amount", "appId" })
                        {
                            if (stepArguments[key] is JsonNode value)
                            {
                                record[key] = value.DeepClone();
                            }
                        }

                        string viewHash = Hash(signature);
                        record[ViewHashField] = viewHash;
                        if (RepeatsAnActThatCycled(SubgoalSteps(steps, start), decision.Operation, stepArguments, viewHash))
                        {
                            // The same act already succeeded from this very screen and the screen came back to it:
                            // taking it again goes round. It is recorded as failed so the mind picks another step.
                            record["ok"] = false;
                            record["error"] = "computer_use_no_progress";
                            steps.Add(record);
                            state["elapsedMs"] = alreadyElapsed + stopwatch.ElapsedMilliseconds;
                            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer.use.step",
                                $"step.{steps.Count}.{ShellTrace.SanitizeLabel(decision.Operation)}.no_progress");
                            if (fromProcedure)
                            {
                                state["procedureDeviated"] = true;
                                state["procedureIndex"] = -1;
                            }

                            continue;
                        }

                        context.SetStatus($"Paso {steps.Count + 1}: {Describe(decision.Operation, stepArguments)}");
                        PreparedOperation prepared = context.Registry.GetOrAdd(new RoutedOperation(decision.Operation, stepArguments));
                        var stepWatch = Stopwatch.StartNew();
                        OperationResponse response;
                        try
                        {
                            response = await context.Execute(prepared, ActionTimeout, cancellationToken)
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
                        if (decision.Operation == "app.open")
                        {
                            // The next look waits, bounded, for the application's window; an application launched
                            // now also gets time to replace its start-up window (measured: Steam's «Iniciar sesión en
                            // Steam» splash was searched for the library until every way to find it was spent).
                            state["awaitWindow"] = true;
                            state["openedCold"] = (bool?)record["alreadyRunning"] != true;
                        }
                        else
                        {
                            await context.Delay(Settle, cancellationToken).ConfigureAwait(true);
                        }

                        continue;
                    }
                }
            }

            if (!subgoalReached)
            {
                continue;
            }

            state["elapsedMs"] = alreadyElapsed + stopwatch.ElapsedMilliseconds;
            CloseSubgoal(context, state, current, steps, start, reached: true, subgoalBy);
            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.subgoal",
                $"subgoal.{index + 1}.of.{plan.Count}.reached.steps.{steps.Count - start}");
            if (index + 1 < plan.Count)
            {
                EnterSubgoal(state, index + 1, context.Procedures);
                subgoalView = null;
                continue;
            }

            reached = true;
            satisfiedBy = subgoalBy;
            evidence = subgoalEvidence;
            break;
        }

        _ = context.MarkResolved(context.Registry, missionPrepared);
        state["elapsedMs"] = alreadyElapsed + stopwatch.ElapsedMilliseconds;
        if (!reached)
        {
            int failedIndex = (int?)state["subgoal"] ?? 0;
            CloseSubgoal(context, state, (JsonObject)plan[failedIndex]!, steps, (int?)state["subgoalStart"] ?? 0,
                reached: false, satisfiedBy: null);
        }

        JsonObject observed = Observed(state, steps, reached, satisfiedBy, evidence, errorCode, lastView);
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
        if ((bool?)record["ok"] == true
            && prepared.OperationName == "input.visible.click"
            && prepared.Arguments.ValueKind == JsonValueKind.Object
            && prepared.Arguments.TryGetProperty("label", out JsonElement label)
            && label.ValueKind == JsonValueKind.String
            && Kernel.Policy.RiskPolicy.LabelJoins(label.GetString()))
        {
            state["joined"] = true;
        }
    }

    private static JsonObject Begin(JsonObject arguments, string objective, ComputerUseProcedures? procedures)
    {
        string goal = (string?)arguments["goal"] is { Length: > 0 } text ? text.Trim() : objective;
        string? application = (string?)arguments["application"];
        string? successCheck = (string?)arguments["successCheck"];
        int? requested = arguments["budgetSteps"] is JsonValue budgetValue && budgetValue.TryGetValue(out int asked)
            ? Math.Clamp(asked, 1, MaximumBudgetSteps)
            : null;
        var plan = new JsonArray();
        bool chained = arguments["steps"] is JsonArray { Count: > 0 };
        if (chained)
        {
            // Contract «steps»: each sub-goal at most ten steps and thirty seconds;
            // the whole chain at most thirty steps and three minutes.
            foreach (JsonNode? node in (JsonArray)arguments["steps"]!)
            {
                if (node is not JsonObject item || (string?)item["goal"] is not { } subgoal || string.IsNullOrWhiteSpace(subgoal))
                {
                    continue;
                }

                plan.Add((JsonNode?)new JsonObject
                {
                    ["goal"] = subgoal.Trim(),
                    ["application"] = (string?)item["application"],
                    ["successCheck"] = (string?)item["successCheck"],
                    ["budgetSteps"] = SubgoalBudgetSteps,
                    ["timeMs"] = (long)SubgoalTimeBudget.TotalMilliseconds,
                });
            }
        }

        if (plan.Count == 0)
        {
            chained = false;
            plan.Add((JsonNode?)new JsonObject
            {
                ["goal"] = goal,
                ["application"] = application,
                ["successCheck"] = successCheck,
                ["budgetSteps"] = requested ?? DefaultBudgetSteps,
                ["timeMs"] = (long)TimeBudget.TotalMilliseconds,
            });
        }

        var state = new JsonObject
        {
            ["goal"] = goal,
            ["application"] = application,
            ["successCheck"] = successCheck,
            ["budgetSteps"] = chained ? requested ?? MaximumBudgetSteps : requested ?? DefaultBudgetSteps,
            ["chained"] = chained,
            ["subgoals"] = plan,
            ["startedUtc"] = DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
            ["steps"] = new JsonArray(),
            ["elapsedMs"] = 0L,
            ["modelMs"] = 0L,
        };
        EnterSubgoal(state, 0, procedures);
        return state;
    }

    /// <summary>
    /// Starts sub-goal <paramref name="index"/>: what the previous one saw is
    /// forgotten, and when it names another application the adopted window is
    /// too, so the mission looks for the new one (and opens it if it is not
    /// in front). Its learned procedure, if any, is loaded.
    /// </summary>
    internal static void EnterSubgoal(JsonObject state, int index, ComputerUseProcedures? procedures)
    {
        JsonArray plan = (JsonArray)state["subgoals"]!;
        JsonObject subgoal = (JsonObject)plan[index]!;
        string? application = (string?)subgoal["application"];
        if (index > 0
            && application is { Length: > 0 }
            && !string.Equals(
                ComputerUseSuccessCheck.Fold(application),
                ComputerUseSuccessCheck.Fold((string?)plan[index - 1]?["application"]),
                StringComparison.Ordinal))
        {
            state.Remove("processId");
        }

        foreach (string field in SubgoalFields)
        {
            state.Remove(field);
        }

        state["subgoal"] = index;
        state["subgoalStart"] = (state["steps"] as JsonArray)?.Count ?? 0;
        state["subgoalStartMs"] = (long?)state["elapsedMs"] ?? 0;
        state["subgoalStartModelMs"] = (long?)state["modelMs"] ?? 0;
        string goal = (string?)subgoal["goal"] ?? string.Empty;
        if (procedures?.Find(application, goal) is { } procedure)
        {
            state["procedureKey"] = ComputerUseProcedures.Key(application, goal);
            state["procedureIndex"] = 0;
            state["procedureSteps"] = procedure.DeepClone();
            if ((string?)subgoal["successCheck"] is null && (string?)procedure["successCheck"] is { Length: > 0 } learnedCheck)
            {
                subgoal["successCheck"] = learnedCheck;
                if ((bool?)state["chained"] != true)
                {
                    state["successCheck"] = learnedCheck;
                }
            }
        }
    }

    // Records how a sub-goal ended and lets the procedure memory take part:
    // a reached sub-goal is learned (or counted as replayed) under its own key.
    private static void CloseSubgoal(
        Context context, JsonObject state, JsonObject subgoal, JsonArray steps, int start, bool reached, string? satisfiedBy)
    {
        JsonArray own = SubgoalSteps(steps, start);
        subgoal["reached"] = reached;
        subgoal["stepCount"] = own.Count;
        subgoal["satisfiedBy"] = satisfiedBy;
        if (context.Procedures is null)
        {
            return;
        }

        if (reached)
        {
            var learning = new JsonObject
            {
                ["goal"] = subgoal["goal"]?.DeepClone(),
                ["application"] = subgoal["application"]?.DeepClone(),
                ["successCheck"] = subgoal["successCheck"]?.DeepClone(),
                ["procedureKey"] = state["procedureKey"]?.DeepClone(),
                ["procedureDeviated"] = state["procedureDeviated"]?.DeepClone(),
                ["elapsedMs"] = ((long?)state["elapsedMs"] ?? 0) - ((long?)state["subgoalStartMs"] ?? 0),
                ["modelMs"] = ((long?)state["modelMs"] ?? 0) - ((long?)state["subgoalStartModelMs"] ?? 0),
            };
            subgoal["procedure"] = context.Procedures.Learn(learning, own);
        }
        else if ((string?)state["procedureKey"] is { Length: > 0 })
        {
            subgoal["procedure"] = (bool?)state["procedureDeviated"] == true ? "deviated" : "abandoned";
        }
    }

    private static JsonArray SubgoalSteps(JsonArray steps, int start)
    {
        var own = new JsonArray();
        for (int index = Math.Max(0, start); index < steps.Count; index++)
        {
            own.Add(steps[index]?.DeepClone());
        }

        return own;
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
    /// Once a view shows the window the provider resolved as the sub-goal's
    /// application (titled like it, or the person's browser for «the
    /// browser»), the mission keeps looking at that process (a later
    /// foreground change does not move the surface).
    /// </summary>
    internal static void AdoptWindow(JsonObject state, string? application, JsonObject view)
    {
        if ((int?)state["processId"] is > 0 || application is not { Length: > 0 })
            return;
        if (view["window"] is JsonObject window && (bool?)window["requested"] == true
            && (int?)window["processId"] is > 0 and int owner)
            state["processId"] = owner;
    }

    /// <summary>
    /// Whether the next look must carry the OCR text (≈1 s): the first look of
    /// a sub-goal, a window drawn without an accessible tree (≤ 1 control), a
    /// success check that reads written text (text:, page:), or a goal whose
    /// target is not among the controls. Otherwise the controls are enough.
    /// </summary>
    internal static bool NeedsText(string goal, string? application, string? successCheck, JsonObject? previousView)
    {
        if (previousView is null || ControlCount(previousView) <= 1)
        {
            return true;
        }

        if (successCheck is { Length: > 0 }
            && successCheck.Split(['|', '&'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Any(atom => atom.StartsWith("text:", StringComparison.OrdinalIgnoreCase)
                    || atom.StartsWith("page:", StringComparison.OrdinalIgnoreCase)))
        {
            return true;
        }

        return !TargetAmongControls(goal, application, previousView);
    }

    // A word of the goal (four letters or more, not the application's name) that
    // names a listed control: what the goal is about is reachable by the tree.
    private static bool TargetAmongControls(string goal, string? application, JsonObject view)
    {
        if (view["controls"] is not JsonArray controls)
        {
            return false;
        }

        var applicationWords = new HashSet<string>(
            ComputerUseSuccessCheck.Fold(application).Split(' ', StringSplitOptions.RemoveEmptyEntries),
            StringComparer.Ordinal);
        string[] words = [.. ComputerUseSuccessCheck.Fold(goal)
            .Split([' ', ',', '.', ';', ':', '«', '»', '"', '\'', '(', ')', '¿', '?', '¡', '!'], StringSplitOptions.RemoveEmptyEntries)
            .Where(word => word.Length >= 4 && !applicationWords.Contains(word))];
        if (words.Length == 0)
        {
            return false;
        }

        foreach (JsonNode? node in controls)
        {
            string name = ComputerUseSuccessCheck.Fold((string?)node?["name"]);
            if (name.Length > 0 && words.Any(word => name.Contains(word, StringComparison.Ordinal)))
            {
                return true;
            }
        }

        return false;
    }

    private static async Task<JsonObject?> LookAsync(
        Context context,
        JsonObject state,
        string? application,
        bool includeText,
        CancellationToken cancellationToken)
    {
        if ((bool?)state["awaitWindow"] == true)
        {
            // Right after app.open: look without OCR until a view shows the
            // application's window, bounded; then read it as asked.
            state.Remove("awaitWindow");
            var watch = Stopwatch.StartNew();
            while (true)
            {
                JsonObject? early = await ReadViewAsync(context, state, application, includeText: false, cancellationToken)
                    .ConfigureAwait(true);
                if (early is not null && ShowsTheApplication(state, early))
                {
                    // A window without an accessible tree (CEF) is judged by what is written on it.
                    bool cold = (bool?)state["openedCold"] == true;
                    JsonObject seen = (includeText || cold) && TextCount(early) == 0 && (ControlCount(early) > 1 || cold)
                        ? await ReadViewAsync(context, state, application, includeText: true, cancellationToken)
                            .ConfigureAwait(true) ?? early
                        : early;
                    if (!cold || !StillStarting(state, seen, watch.Elapsed))
                    {
                        state.Remove("openedCold");
                        state.Remove("startingWindow");
                        return seen;
                    }
                }

                if (watch.Elapsed >= ((bool?)state["openedCold"] == true ? StartWait : WindowWait))
                {
                    break;
                }

                await context.Delay(Settle, cancellationToken).ConfigureAwait(true);
            }
        }

        return await ReadViewAsync(context, state, application, includeText, cancellationToken).ConfigureAwait(true);
    }

    // A window of an application launched moment ago is still starting while it is not the same window for a second
    // look or still reads like a splash (≤1 control and ≤5 written lines, read with OCR).
    private static bool StillStarting(JsonObject state, JsonObject view, TimeSpan waited)
    {
        long hwnd = (long?)view["window"]?["hwnd"] ?? 0;
        bool sameWindow = hwnd == 0 || hwnd == ((long?)state["startingWindow"] ?? 0);
        state["startingWindow"] = hwnd;
        if (waited >= StartWait)
        {
            return false;
        }

        if (!sameWindow)
        {
            return true;
        }

        return ControlCount(view) <= 1 && TextCount(view) <= 5;
    }

    private static bool ShowsTheApplication(JsonObject state, JsonObject view) =>
        view["window"] is JsonObject window
        && ((bool?)window["requested"] == true
            || (int?)state["processId"] is > 0 and int owner && (int?)window["processId"] == owner);

    private static async Task<JsonObject?> ReadViewAsync(
        Context context,
        JsonObject state,
        string? application,
        bool includeText,
        CancellationToken cancellationToken)
    {
        var arguments = new JsonObject { ["includeText"] = includeText, ["limit"] = 60 };
        if ((int?)state["processId"] is > 0 and int owner)
        {
            arguments["processId"] = owner;
        }

        if (application is { Length: > 0 })
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
            OperationResponse response = await context.Execute(prepared, ViewTimeout, cancellationToken)
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

    // The view a step was taken from, by hash: what tells a cycle (the screen came back) from progress.
    private const string ViewHashField = "viewHash";

    /// <summary>
    /// The no-progress guard: this act already succeeded in this sub-goal from
    /// this very screen, so the screen went round back to it (a menu opened and
    /// closed, a toggle flipped twice) and taking it again would loop.
    /// </summary>
    internal static bool RepeatsAnActThatCycled(JsonArray subgoalSteps, string operation, JsonObject arguments, string viewHash) =>
        subgoalSteps.Any(node => node is JsonObject step
            && (bool?)step["ok"] == true
            && string.Equals((string?)step[ViewHashField], viewHash, StringComparison.Ordinal)
            && SameStep(step, operation, arguments));

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
        var told = new JsonArray();
        foreach (JsonNode? node in steps)
        {
            if (node?.DeepClone() is JsonObject step)
            {
                step.Remove(ViewHashField);
                told.Add((JsonNode?)step);
            }
        }

        var observed = new JsonObject
        {
            ["goal"] = state["goal"]?.DeepClone(),
            ["application"] = state["application"]?.DeepClone(),
            ["reached"] = reached,
            ["successCheck"] = state["successCheck"]?.DeepClone(),
            ["stepCount"] = steps.Count,
            ["steps"] = told,
            ["window"] = state["window"]?.DeepClone(),
            ["joined"] = (bool?)state["joined"] == true,
            ["elapsedMs"] = (long?)state["elapsedMs"] ?? 0,
            ["modelMs"] = (long?)state["modelMs"] ?? 0,
            ["authority"] = "shell_loop_over_uia_ocr_postread",
        };
        JsonArray plan = state["subgoals"] as JsonArray ?? [];
        if ((bool?)state["chained"] == true)
        {
            var subgoals = new JsonArray();
            foreach (JsonNode? node in plan)
            {
                subgoals.Add((JsonNode?)new JsonObject
                {
                    ["goal"] = node?["goal"]?.DeepClone(),
                    ["application"] = node?["application"]?.DeepClone(),
                    ["reached"] = (bool?)node?["reached"] == true,
                    ["stepCount"] = (int?)node?["stepCount"] ?? 0,
                    ["satisfiedBy"] = node?["satisfiedBy"]?.DeepClone(),
                });
            }

            observed["subgoals"] = subgoals;
        }
        else if (plan.Count == 1 && (string?)plan[0]?["procedure"] is { Length: > 0 } procedure)
        {
            observed["procedure"] = procedure;
        }

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

    // Only the sub-goal at hand: the mind reasons about the steps toward the goal it is given.
    private static JsonArray HistoryForMind(JsonArray steps, int subgoalStart)
    {
        var history = new JsonArray();
        int start = Math.Max(Math.Max(0, subgoalStart), steps.Count - HistoryForTheMind);
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

    // What the screen shows for «did it change»: the title and the controls; the
    // written text only on a window drawn without an accessible tree (≤ 1
    // control), where the provider reads it always. So a look taken with the
    // OCR text and one taken without it compare equal when nothing moved.
    internal static string ViewSignature(JsonObject view)
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

        if (ControlCount(view) <= 1 && view["text"] is JsonObject text)
        {
            parts.Append(text.ToJsonString());
        }

        return parts.ToString();
    }

    private static string Hash(string signature) =>
        Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(signature)), 0, 8);

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

    // Atoms that read verified receipts and the disk, never the screen.
    private static readonly HashSet<string> ReceiptAtoms = new(StringComparer.Ordinal) { "stepdone", "file", "manifest" };

    /// <summary>
    /// The check evaluated on receipts alone: a term holds only when every atom
    /// in it reads a verified step, a file or a manifest. Such a term needs no
    /// new look at the screen to be known.
    /// </summary>
    internal static bool EvaluateReceipts(string? check, JsonArray steps, out string? satisfiedBy)
    {
        satisfiedBy = null;
        if (string.IsNullOrWhiteSpace(check))
        {
            return false;
        }

        var nothingSeen = new JsonObject();
        foreach (string term in check.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            string[] atoms = term.Split('&', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
            if (atoms.Length > 0
                && atoms.All(atom => ReceiptAtoms.Contains(AtomKind(atom)) && Atom(atom, nothingSeen, steps)))
            {
                satisfiedBy = term;
                return true;
            }
        }

        return false;
    }

    private static string AtomKind(string atom)
    {
        int colon = atom.IndexOf(':', StringComparison.Ordinal);
        return colon <= 0 ? string.Empty : atom[..colon].Trim().ToLowerInvariant();
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

                    // What BAXY itself typed (a search box, its suggestion echoing the query) never proves arriving
                    // (measured: the Explorer search echo passed for a folder that was never created).
                    var typed = new HashSet<string>(
                        steps.OfType<JsonObject>()
                            .Where(step => (string?)step["operation"] == "input.text.type")
                            .Select(step => Fold((string?)step["text"])),
                        StringComparer.Ordinal);
                    return FindControls(view, name).Any(control =>
                        (string?)control["kind"] is not ("Edit" or "ComboBox" or "Document")
                        && !typed.Contains(Fold((string?)control["name"]))
                        && (state is null || Fold((string?)control["state"]).Split(' ').Contains(state)));
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
    // screen, a verified click went there, and most of the written text is new against the first look of the
    // application's own window. A menu the click opened changes a few lines (Steam: 3 of 25); the page reached
    // changes most of them.
    private static bool PageAtom(string rest, JsonObject view, JsonArray steps)
    {
        // Only a window without an accessible tree (CEF, canvas) is judged by its written text; where controls exist,
        // arriving is the place selected or titled (measured on Discord: «Cotele» written in an activity card passed
        // for the channel while the Friends page was open).
        int? click = AClickWentTo(rest, steps);
        if ((view["controls"] as JsonArray)?.Count > 1 || !ViewContains(view, rest) || click is null)
        {
            return false;
        }

        // The view right before the click that reached the place; the mission's first look only when that is unknown.
        JsonArray before = view["textBeforeClick"]?[click.Value.ToString(CultureInfo.InvariantCulture)] as JsonArray
            ?? view["baselineText"] as JsonArray
            ?? [];
        var baseline = new HashSet<string>(before.Select(line => (string?)line ?? string.Empty), StringComparer.Ordinal);
        JsonArray current = TextLines(view);
        if (baseline.Count < 5 || current.Count < 5)
        {
            return false;
        }

        int kept = current.Count(line => baseline.Contains((string?)line ?? string.Empty));
        return kept * 2 < current.Count;
    }

    // A verified click whose label names the place, or the entry picked right after
    // a click on it (the menu that click opened: measured on Steam, the click on
    // «BIBLIOTECA» opened its menu and did not verify; «Inicio» in it did). Any
    // other verified click (a tab, a field) does not reach the place.
    private static int? AClickWentTo(string place, JsonArray steps)
    {
        string target = Fold(place);
        bool previousNamedIt = false;
        int? namedClick = null;
        int position = 0;
        foreach (JsonNode? node in steps)
        {
            position++;
            if (node is not JsonObject step || (string?)step["operation"] != "input.visible.click")
            {
                previousNamedIt = false;
                continue;
            }

            string label = Fold((string?)step["label"]);
            bool namesIt = target.Length > 0 && label.Length >= 3
                && (label.Contains(target, StringComparison.Ordinal) || target.Contains(label, StringComparison.Ordinal));
            if (namesIt)
            {
                namedClick = (int?)step["step"] ?? position;
            }

            if ((bool?)step["ok"] == true && (namesIt || previousNamedIt))
            {
                // Measured against the view before the click on the place itself (a menu entry picked after it
                // still counts from before the menu opened).
                return namedClick ?? (int?)step["step"] ?? position;
            }

            previousNamedIt = namesIt;
        }

        return null;
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
