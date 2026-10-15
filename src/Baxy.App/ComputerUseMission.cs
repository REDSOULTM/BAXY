using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.Contracts;

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
/// success check and budget; the whole mission is reached
/// when every sub-goal is.
/// </summary>
internal static partial class ComputerUseMission
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

    // Revision 1 of r21 (B4): the desktop's windows are listed under the provider's own budget
    // (WindowsVisibleControlAdapter.DestinationBudget); this is only the backstop past it.
    private static readonly TimeSpan DestinationTimeout = TimeSpan.FromSeconds(8);
    private static readonly TimeSpan ActionTimeout = TimeSpan.FromSeconds(45);

    // fable/cu-v3-reintento-pausa (banco r6 with the simulated user, 2 s typing and 1 s still: s12, g1, n5, n7, x10 and
    // y10 ended on «empezaste a usar el PC»): an act stopped by the person's input is tried again after their next
    // pause, at most this many times and while this long has not passed since the act began; only then is the cause
    // said. Each try waits for the pause in the foreground lease itself.
    internal const int PersonPauseRetries = 3;
    internal const long PersonPauseRetryMs = 8000;

    // An act stopped by the person after it pressed (its post-read cut short): the mission's window is looked at again
    // this many times, PersonEffectLookInterval apart, for the act's effect (with the act's own first look, about the
    // 1.5 s a post-read looks).
    internal const int PersonEffectLooks = 3;
    internal static readonly TimeSpan PersonEffectLookInterval = TimeSpan.FromMilliseconds(400);

    // After an act the window redraws: a short settle, not a fixed wait. After
    // app.open the next look waits, bounded, only until a view shows the
    // application's window (measured: GetForegroundWindow returned nothing
    // right after app.open on the Calculator; a fixed 1.2 s was paid always).
    internal static readonly TimeSpan Settle = TimeSpan.FromMilliseconds(150);
    private static readonly TimeSpan WindowWait = TimeSpan.FromSeconds(3);
    // Measured: the Epic Games launcher still showed its «EPIC GAMES» splash 11 s after its window appeared.
    internal static readonly TimeSpan StartWait = TimeSpan.FromSeconds(20);
    // Encargo CS (banco fz1 s12, Steam cold after a restart): an application that opened on a progress window of its own
    // (an updater, an installation check) gets this long, in all, to replace it with its main window (ProgressSplash).
    internal static readonly TimeSpan ColdStartWait = TimeSpan.FromSeconds(60);
    // Two looks of a starting window are compared only this far apart (v3 point 1).
    internal static readonly TimeSpan StartSettle = TimeSpan.FromMilliseconds(400);
    // A blank document created from a start page replaces it in a moment (the mind marks that act
    // «expects_title_change»): the next look waits, bounded, for the window's title to change.
    internal static readonly TimeSpan TitleChangeWait = TimeSpan.FromSeconds(8);

    // What belongs to the sub-goal being worked on and starts again with the next one.
    private static readonly string[] SubgoalFields =
    [
        "baselineText", "focusAtStart", "focusBeforeStep", "textBeforeClick", "selectedBeforeClick", "chosenBeforeClick", "controlsBeforeClick", "countsBeforeClick", "clickedBefore", "lastText", "lastSignature", "lastSignatureStep", "lastFocusSeen", "lastSignatureText", "unchangedViews", "waitForLabel", "awaitWindow", "awaitTitleChange",
        "viewBeforeTyping", "viewBeforeEnter", "newTextAfterClick", "newTextAfterClickStep",
        "subgoalFirstText", "subgoalFirstIds", "subgoalFirstTabs", "subgoalFirstWindows", "selectedAtStart", "alreadyThereLook", "alreadyThereLooks", "alreadyChosen",
        ViewWantedField,
    ];

    // Ronda 21: the goal's words the mind ranked the last view by (MindComputerUseStep.Wanted); the sub-goal's next looks
    // carry them («wanted» of input.visible.controls) and a new sub-goal starts without them.
    internal const string ViewWantedField = "viewWanted";

    // The closed repertoire: what a person does with keyboard and mouse over
    // what they see, plus bringing the application to the front and (cu-v3-abrir-archivo) opening a file of the
    // person's with it by the shell, the typed file.open: never through the window's own dialog.
    internal static readonly IReadOnlySet<string> Primitives = new HashSet<string>(StringComparer.Ordinal)
    {
        "app.open",
        "file.open",
        "input.key.press",
        "input.scroll",
        "input.text.type",
        "input.visible.click",
    };

    /// <summary>
    /// Whether the outbox entry of <paramref name="operationName"/> belongs to a mission:
    /// the mission itself or one of its primitives. They act on the screen of the session
    /// that decided them, so a later session never retries them.
    /// </summary>
    internal static bool Prepares(string operationName) =>
        operationName == OperationName || Primitives.Contains(operationName);

    internal sealed class Context
    {
        /// <summary>Sends one prepared operation through the core (kernel, provider, post-read).</summary>
        internal required Func<PreparedOperation, TimeSpan, CancellationToken, Task<OperationResponse>> Execute { get; init; }

        /// <summary>Sends it again with the Kernel's confirmation token for that invocation (<see cref="ExecuteAsync"/>).</summary>
        internal Func<PreparedOperation, string, TimeSpan, CancellationToken, Task<OperationResponse>>? ExecuteConfirmed { get; init; }

        /// <summary>Asks the mind for one step over the compact view.</summary>
        internal required Func<ComputerUseStepRequest, CancellationToken, Task<MindComputerUseStep?>> Decide { get; init; }

        internal required RetryableOperationRegistry Registry { get; init; }
        internal required Func<RetryableOperationRegistry, PreparedOperation, bool> MarkResolved { get; init; }
        internal required Action<string> SetStatus { get; init; }

        /// <summary>The labels the mind translated (§4.4.1): each request carries its goal's entry only.</summary>
        internal ComputerUseLabelTranslations? LabelTranslations { get; init; }

        /// <summary>What BAXY typed in earlier missions of this session: never proof of a later one's act (M1).</summary>
        internal ComputerUseTypedLedger? TypedInSession { get; init; }

        internal Func<TimeSpan, CancellationToken, Task> Delay { get; init; } = Task.Delay;

        /// <summary>The mission's clock in milliseconds (tests advance a fake one): what the retries after a person's
        /// pause count against their ceiling (<see cref="PersonPauseRetryMs"/>).</summary>
        internal Func<long> NowMs { get; init; } = static () => Environment.TickCount64;

        /// <summary>The mission's whole time (tests shorten it); null: 90 s, 180 s for a chained mission.</summary>
        internal TimeSpan? MissionTime { get; init; }

        /// <summary>
        /// What the Core is told of this mission (<see cref="Providers.Windows.External.IMissionFrontSignal"/>): it runs
        /// while the loop does, and ends at every end, so the Core gives the person's window the front back; null (the
        /// loop's tests) reads and gives back nothing.
        /// </summary>
        internal Providers.Windows.External.IMissionFrontSignal? Front { get; init; }
    }

    /// <summary>What the loop ended with: a synthesized response for the mission step, or a pending confirmation of one primitive.</summary>
    internal sealed record Result(
        OperationResponse? Response,
        PreparedOperation MissionPrepared,
        PendingOperationConfirmation? Confirmation);

    /// <summary>
    /// r30 (bancos Br28 y Bb3tb: arguments.end→computer_use.start 213 ms p50 in the first mission of a process, 65 of
    /// 65, and 54 ms in the next ones; v2 paid 94): what a mission pays once before its first look (the catalog's
    /// schema of its arguments, its state and the compiling of the loop's asynchronous methods) is paid when the
    /// start-up begins, on the pool, as the shell's readers are (MissionInputPipeline.WarmReadersAsync). Nothing is
    /// dispatched, looked at, journaled, kept or sent to the mind.
    /// </summary>
    internal static Task WarmAsync() => Task.Run(static () =>
    {
        var arguments = new JsonObject { ["goal"] = UserMessagePhrases.ReadersWarmupRequest };
        _ = MindPlanBoundary.ArgumentsSatisfyExactSchema(OperationName, arguments);
        _ = Begin(arguments, UserMessagePhrases.ReadersWarmupRequest);
        foreach (Type machine in typeof(ComputerUseMission).GetNestedTypes(System.Reflection.BindingFlags.NonPublic))
        {
            if (!machine.IsGenericTypeDefinition && typeof(System.Runtime.CompilerServices.IAsyncStateMachine).IsAssignableFrom(machine)
                && machine.GetMethod("MoveNext", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic) is { } loop)
            {
                System.Runtime.CompilerServices.RuntimeHelpers.PrepareMethod(loop.MethodHandle);
            }
        }
    });

    internal static async Task<Result> RunAsync(
        Context context,
        PendingMindPlanExecution execution,
        JsonObject arguments,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(context);
        ArgumentNullException.ThrowIfNull(execution);
        ArgumentNullException.ThrowIfNull(arguments);
        execution.ComputerUse ??= Begin(arguments, execution.Objective, context.LabelTranslations);
        context.Front?.MissionBegins();
        try
        {
            return await RunLoopAsync(context, execution, arguments, cancellationToken).ConfigureAwait(true);
        }
        finally
        {
            // Every end: reached, failed, out of time, waiting for a confirmation, cancelled or thrown. The Core gives the
            // person's window the front back, behind an act it may still be doing.
            context.Front?.MissionEnds();
        }
    }

    private static async Task<Result> RunLoopAsync(
        Context context,
        PendingMindPlanExecution execution,
        JsonObject arguments,
        CancellationToken cancellationToken)
    {
        PreparedOperation missionPrepared = execution.PendingOperation is { OperationName: OperationName } same
            ? same
            : context.Registry.GetOrAdd(new RoutedOperation(OperationName, arguments));
        JsonObject state = execution.ComputerUse!;
        string traceId = ShellTraceSink.TurnId;
        var stopwatch = Stopwatch.StartNew();
        long alreadyElapsed = (long?)state["elapsedMs"] ?? 0;
        JsonArray steps = state["steps"] as JsonArray ?? new JsonArray();
        state["steps"] = steps;
        JsonArray plan = (JsonArray)state["subgoals"]!;
        bool chained = (bool?)state["chained"] == true;
        int budget = (int?)state["budgetSteps"] ?? DefaultBudgetSteps;
        long missionTimeMs = (long)(context.MissionTime ?? (chained ? ChainTimeBudget : TimeBudget)).TotalMilliseconds;
        string? errorCode = null;
        bool reached = false;
        string? evidence = null;
        string? satisfiedBy = null;
        JsonObject? lastView = null;
        // The last view of the sub-goal at hand: what decides whether the next look needs the OCR text.
        JsonObject? subgoalView = null;
        // r8: the look that proved a sub-goal reached is, untouched, the next sub-goal's first look when nothing was done
        // in between and it reads the same application (measured live: 11 of 27 transitions looked again at once,
        // ~600 ms each).
        JsonObject? reusableView = null;
        string? reusableApplication = null;
        bool reusableHasText = false;
        ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.start",
            $"budget.{budget}.steps_done.{steps.Count}.subgoals.{plan.Count}");
        for (int item = 0; item < plan.Count; item++)
        {
            // How many alternatives each sub-goal's check carries («none»: only the model's cited evidence can end it).
            string? planned = (string?)plan[item]?["successCheck"];
            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.plan",
                $"subgoal.{item + 1}.check.{(string.IsNullOrWhiteSpace(planned) ? "none" : "terms." + planned.Split('|').Length)}");
        }

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
            // Estabilización L (límites de partida): a sub-goal the mind marked as a declared limit («limit»: a right
            // click, the ribbon's formatting) is never tried, and nothing is looked at or pressed for it; the sub-goals
            // before it, the safe part, were done.
            if ((string?)current["limit"] is { Length: > 0 } limit)
            {
                errorCode = LimitStop + limit;
                break;
            }

            // A place that needs a device the computer does not have (the mind's «requires»: «ir a Wi-Fi» on a PC with no
            // Wi-Fi adapter) is said as that limit, read once from the computer before the sub-goal's first look.
            if (done == 0 && (string?)current["requires"] is { Length: > 0 } device && current["deviceRead"] is null)
            {
                current["deviceRead"] = true;
                if (await DeviceAbsentAsync(context, device, cancellationToken).ConfigureAwait(true))
                {
                    state["absentDevice"] = device;
                    errorCode = DeviceStop;
                    break;
                }
            }

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
            // A goal that carries a question is never closed on receipts alone: the look decides whether it shows the
            // datum asked for (QuestionDatumUnread, pasada r15b C1).
            if (done > 0 && !CarriesQuestion(goal) && ComputerUseSuccessCheck.EvaluateReceipts(
                    successCheck, SubgoalSteps(steps, start), out subgoalBy, state["aliases"] as JsonObject,
                    ComputerUseSuccessCheck.SubgoalStarted(state)))
            {
                // The check holds on the receipts of verified steps alone (a step done, a file): no new
                // look is needed to know it. The mission's last sub-goal still reads the controls once, without OCR,
                // so the final quotes the screen as it is now.
                subgoalReached = true;
                subgoalBy = WeakenedBySimilarity(state, successCheck, subgoalBy);
                if (index + 1 >= plan.Count)
                {
                    JsonObject? seen = await LookAsync(context, state, application, includeText: false, cancellationToken, successCheck)
                        .ConfigureAwait(true);
                    lastView = seen ?? lastView;
                }
            }
            else
            {
                // Ronda 21, destino por contenido (pasada r18: t-file-1, t-file-3, t-menu-4, t-form-4, t-drag-2): a
                // mission with no application and no window of its own looks for the one window that shows what its
                // request names before its first look, never reading the person's window in front in its place.
                if (application is not { Length: > 0 } && state["referent"] is JsonObject
                    && state["destinationResolved"] is null && !ComputerUseMissionWindow.Tied(state))
                {
                    string? unbound = await ResolveDestinationAsync(context, state, steps, cancellationToken).ConfigureAwait(true);
                    if (unbound is not null)
                    {
                        errorCode = unbound;
                        lastView = null;
                        break;
                    }

                    if (ComputerUseMissionWindow.Tied(state))
                    {
                        reusableView = null;
                    }
                }

                bool lastLook = done >= subgoalBudget || steps.Count >= budget;
                bool reusable = reusableView is not null && done == 0
                    && string.Equals(reusableApplication, application, StringComparison.Ordinal);
                // Whether the text is needed is judged, as for any later look, on the controls already seen.
                bool includeText = NeedsText(goal, application, successCheck, subgoalView ?? (reusable ? reusableView : null));
                bool lookedWithText = includeText;
                if (reusable && (!includeText || reusableHasText))
                {
                    lastView = reusableView;
                    lookedWithText = reusableHasText;
                    ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.view_reused", $"subgoal.{index + 1}");
                }
                else
                {
                    context.SetStatus("Mirando la pantalla");
                    lastView = await LookAsync(context, state, application, includeText, cancellationToken, successCheck).ConfigureAwait(true);
                }

                reusableView = null;
                if (lastView is null && ViewMayComeBack(state)
                    && alreadyElapsed + stopwatch.ElapsedMilliseconds + (long)ViewRetryPause.TotalMilliseconds < missionTimeMs)
                {
                    // Ronda 21 (pasada r18 v3-63): a window this mission already read well whose look failed as unreadable
                    // (the worker answered nothing in time) is looked at once more after a short pause, within the
                    // mission's time, before the mission says it could not read it. Never a window that closed, one
                    // not found or one that was never read: those stop at once, as before.
                    ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.view_retry", $"subgoal.{index + 1}");
                    await context.Delay(ViewRetryPause, cancellationToken).ConfigureAwait(true);
                    lastView = await LookAsync(context, state, application, includeText, cancellationToken, successCheck).ConfigureAwait(true);
                }

                if (lastView is null)
                {
                    errorCode = NoViewStop(state);
                    break;
                }

                // Goal v3 ventana-misión (t-menu-1, t-form-4): with no application named, the window the person works in
                // (their input went there while the mission works) is never read for it nor named in its final. Review
                // of the branch (finding 5): the model is still asked, over a blank view, and may open an application or
                // a file from it (the way back a mission with no application had); any other answer ends it as before.
                bool hidesPersonsWindow = ComputerUseMissionWindow.PersonsWindowWithoutApplication(
                    state, application, lastView, ShowsTheApplication(state, lastView), DateTimeOffset.UtcNow);
                if (hidesPersonsWindow)
                {
                    ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.window", "person_window_no_application");
                    lastView = ComputerUseMissionWindow.HiddenPersonsWindow();
                }

                // The view as read, before this sub-goal's notes are added to it: what the next sub-goal may start from.
                JsonObject? pristineView = index + 1 < plan.Count ? lastView.DeepClone() as JsonObject : null;

                subgoalView = lastView;
                // Review 1 of r20 P8 (finding 1): every window that came during the mission (its look says born),
                // whatever sub-goal saw it, so a later sub-goal knows it was there before its first look.
                if ((bool?)lastView["window"]?["born"] == true && lastView["window"]?["hwnd"] is JsonNode bornHwnd)
                {
                    JsonArray bornWindows = state["bornWindows"] as JsonArray ?? [];
                    bornWindows.Add(bornHwnd.DeepClone());
                    state["bornWindows"] = bornWindows;
                }

                if (state["subgoalFirstText"] is null && !hidesPersonsWindow
                    && (application is null || (bool?)lastView["window"]?["requested"] == true)
                    && SubgoalSteps(steps, start).OfType<JsonObject>().All(
                        step => (string?)step["operation"] == "app.open" && !MayHaveActed(step)))
                {
                    // What the sub-goal saw before any act of its own: a citation of it proves no act (M1). The
                    // application's own first look, as «the page changed» (baselineText) takes it: the window in front
                    // read before app.open (the editor the person works in) is not what the application showed. An
                    // opening that made the new document asked for is an act: what it shows is its effect (review of
                    // cu-v3-documento-nuevo, finding 7: «Libro1» cited for «crear un blank workbook»).
                    state["subgoalFirstText"] = ComputerUseSuccessCheck.LookText(lastView);
                    // Ronda 20 P4 (v3-08): who the empty parts and the focused one of that look were (their UIA ids):
                    // a part of the same name with another id is a new one.
                    state["subgoalFirstIds"] = ComputerUseSuccessCheck.FirstIds(lastView);
                    // Ronda 20 P8: the tabs it showed then, so a new one is told by difference (atom born:).
                    state["subgoalFirstTabs"] = ComputerUseSuccessCheck.TabNames(lastView);
                    // Review 1 of r20 P8 (finding 1): and the windows it knew then (the one it read, those born
                    // earlier in the mission), so a window born: is one that came after this first look.
                    state["subgoalFirstWindows"] = ComputerUseSuccessCheck.KnownWindows(state["bornWindows"] as JsonArray, lastView);
                    // The entries shown selected then: where the window already was (pasada r18, check atom
                    // control:X:current); an entry selected later is the place only when the act that chose it moved it.
                    state["selectedAtStart"] = ComputerUseSuccessCheck.SelectedNames(lastView);
                }

                if (!hidesPersonsWindow)
                {
                    state["window"] = lastView["window"]?.DeepClone();
                    AdoptWindow(state, application, lastView);
                    ComputerUseMissionWindow.Tie(state, application, lastView, ShowsTheApplication(state, lastView), steps);
                }

                // Whether this look is the window the mission works on: the named application's own (its process, its
                // title), or the one in front when none is named. When the named one has no window the adapter reads
                // the front one instead, and a place marked there (mark:) is another application's.
                lastView["onTheApplication"] = application is not { Length: > 0 } || ShowsTheApplication(state, lastView);
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

                // Where the keyboard was at the application's own first look: a field that had it before any step is
                // not one this mission brought it to (check atom focus:). Ronda 24b (x7): a look behind the person's
                // window tells it too (the worker reads HasKeyboardFocus behind; measured, the focus moved Group ->
                // Button -> ComboBox there), so it is taken from the first look, behind or in front. It is only a
                // guard: what the step that arrived moved is told by the focus before it (focusBeforeStep). Review 1 of
                // r24b (B2): a look behind that names no focused element (a native window without the front has none
                // with HasKeyboardFocus; a partial read) does not know it, and its empty signature is no start.
                // Review 2 of r24b (B2): the start is only a look before any step of the sub-goal; a later look
                // (after the mission's own acts moved the keyboard) is no start, so when the first looks did not know
                // it there is no start guard and the arrival rests on focusBeforeStep alone.
                if (done == 0 && (application is null || (bool?)lastView["window"]?["requested"] == true) && !hidesPersonsWindow
                    && !ComputerUseSuccessCheck.FocusUnread(lastView))
                {
                    state["focusAtStart"] ??= ComputerUseSuccessCheck.FocusSignature(lastView);
                }

                if (state["focusAtStart"] is JsonNode focusAtStart)
                {
                    lastView["focusAtStart"] = focusAtStart.DeepClone();
                }

                if (state["focusBeforeStep"] is JsonObject focusBefore)
                {
                    lastView["focusBeforeStep"] = focusBefore.DeepClone();
                }

                if (state["textBeforeClick"] is JsonObject beforeClicks)
                {
                    lastView["textBeforeClick"] = beforeClicks.DeepClone();
                }

                if (state["viewBeforeTyping"] is JsonObject beforeTyping)
                {
                    lastView["viewBeforeTyping"] = beforeTyping.DeepClone();
                }

                if (state["viewBeforeEnter"] is JsonObject beforeEnter)
                {
                    lastView["viewBeforeEnter"] = beforeEnter.DeepClone();
                }

                // What the sub-goal's application showed before any act of its own: a result that cannot be evaluated
                // is a number it did not show then (check atom result:).
                if ((string?)state["subgoalFirstText"] is { Length: > 0 } firstText)
                {
                    lastView["subgoalFirstText"] = firstText;
                }

                if (state["subgoalFirstTabs"] is JsonArray firstTabs)
                {
                    lastView["subgoalFirstTabs"] = firstTabs.DeepClone();
                }

                if (state["subgoalFirstWindows"] is JsonArray firstWindows)
                {
                    lastView["subgoalFirstWindows"] = firstWindows.DeepClone();
                }

                if (state["selectedAtStart"] is JsonArray selectedAtStart)
                {
                    lastView["selectedAtStart"] = selectedAtStart.DeepClone();
                }

                if (state["selectedBeforeClick"] is JsonObject chosenBefore)
                {
                    lastView["selectedBeforeClick"] = chosenBefore.DeepClone();
                }

                if (state["chosenBeforeClick"] is JsonObject optionsBefore)
                {
                    lastView["chosenBeforeClick"] = optionsBefore.DeepClone();
                }

                if (state["controlsBeforeClick"] is JsonObject namedBefore)
                {
                    lastView["controlsBeforeClick"] = namedBefore.DeepClone();
                }

                if (state["countsBeforeClick"] is JsonObject countedBefore)
                {
                    lastView["countsBeforeClick"] = countedBefore.DeepClone();
                }

                if (state["clickedBefore"] is JsonObject clickedBefore)
                {
                    lastView["clickedBefore"] = clickedBefore.DeepClone();
                }

                // Whether the look after the last click shows a control the look before it did not (falsos éxitos v3
                // M2): what tells a result that navigated from the suggestion of the query that only closed its list.
                ComputerUseSuccessCheck.NoteWhatTheClickBrought(lastView, steps);
                // Ronda 24 (pasada r23 v3-11): a document that click created in the mission's window is the mission's.
                if (!hidesPersonsWindow)
                {
                    ComputerUseMissionWindow.NoteCreatedDocument(state, lastView, steps);
                }

                NoteWhatAppeared(state, lastView, currentText, steps, start);
                NoteTranslationsSeen(state, lastView);
                // What the last act made appear is marked before the check reads it (appeared:).
                MarkAppeared(state, steps, start, lastView);

                // The blank view shown instead of the person's window proves nothing.
                // Ronda 26: a look that says only who is in front (the provider's «identityOnly») was not read: it holds no
                // check (so it is never reused), and only an opening is decided on it.
                bool frontOnly = (bool?)lastView["identityOnly"] == true;
                bool checkHolds = !hidesPersonsWindow && !frontOnly && ComputerUseSuccessCheck.Evaluate(
                    successCheck, lastView, SubgoalSteps(steps, start), out subgoalBy, state["aliases"] as JsonObject,
                    ComputerUseSuccessCheck.SubgoalStarted(state), context.TypedInSession?.Entries);
                subgoalBy = WeakenedBySimilarity(state, successCheck, subgoalBy);
                if (checkHolds && QuestionUnlookedFor(goal, subgoalBy, SubgoalSteps(steps, start)))
                {
                    // Lectura-ruta (r9 v3-61): the window opened is no answer to the question it carries; the model
                    // looks for it (done citing it, or the step to the page that shows it).
                    checkHolds = false;
                    subgoalBy = null;
                    ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.question", $"subgoal.{index + 1}.unlooked");
                }
                else if (checkHolds && QuestionDatumUnread(goal, subgoalBy, lastView, SubgoalSteps(steps, start), LastAppeared(steps, start), successCheck))
                {
                    // Pasada r15b C1 (v3-43, v3-18): a term that reads no value held on a look that shows none (or is
                    // still loading); the model reads the answer or takes the step to it. Ronda 20b: the view says so
                    // (questionPending), so the mind never hunts again for the place the check already found.
                    checkHolds = false;
                    subgoalBy = null;
                    lastView["questionPending"] = true;
                    ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.question", $"subgoal.{index + 1}.datum_unread");
                }

                // Pasada r15b (t-form-1, t-long-3): a free sub-goal (no check of its own: an order said before a form, a
                // route or a file dialog) is done once an act of it brought up the control the next sub-goal checks,
                // which its first look did not show; the model is not asked to do the next one inside it. Review of
                // cierre-de-subobjetivos (finding 3): only a sub-goal whose goal is to bring something up (opening or
                // going to a place); one with an effect of its own (a drawing, a sort) is never done by what appeared.
                if (!checkHolds && !hidesPersonsWindow && string.IsNullOrWhiteSpace(successCheck) && index + 1 < plan.Count
                    && ComputerUseSuccessCheck.BringsUpGoal(goal)
                    && ComputerUseSuccessCheck.NextSubgoalBroughtUp(
                        (string?)plan[index + 1]?["successCheck"], lastView, SubgoalSteps(steps, start),
                        (string?)state["subgoalFirstText"]) is { } brought)
                {
                    checkHolds = true;
                    subgoalBy = brought;
                    ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.subgoal", $"subgoal.{index + 1}.next_brought_up");
                }

                if (checkHolds && IsStale(lastView))
                {
                    // Ronda 21: a look kept from before a read that failed (IsStale) never proves the check: the window
                    // is looked at afresh, and only that look may hold it (or the mission says it could not read it).
                    ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.view_stale", $"subgoal.{index + 1}.check");
                    continue;
                }

                if (checkHolds)
                {
                    subgoalReached = true;
                    reusableView = pristineView;
                    reusableApplication = application;
                    reusableHasText = lookedWithText || TextCount(lastView) > 0;
                }
                else if (lastLook)
                {
                    errorCode = "computer_use_budget_exhausted";
                    break;
                }
                else
                {
                    if (frontOnly && (int?)state["processId"] is > 0)
                    {
                        // r29 (pasada r27 v3-20, v3-22, v3-72; bancos r27 y cd s06: 5 de 5 veces, 0 logradas): the
                        // application this mission opened (its process is known) still shows no window of its own after
                        // the opening's wait. The window in front is not read whole in its place (it was, and the final
                        // blamed «a control not found» on the person's window): the mission stops with the cause, the
                        // raised process the provider names (applicationElevated) or, estabilización D2 (banco h1 s11,
                        // u1), an application whose window never showed (it never came to be read: no «the window would
                        // not let itself be read»), and says nothing of the window in front.
                        errorCode = (bool?)lastView["applicationElevated"] == true
                            ? "computer_use_window_elevated"
                            : "computer_use_app_not_shown";
                        state.Remove("window");
                        lastView = null;
                        break;
                    }

                    // A window another process draws over (window.coveredBy) is read all the same: its accessible
                    // tree and its own drawing are the window's, and neither waits for it to come up (v3 point 0: the
                    // application opens and is looked at behind the person's window). The cover matters only to an
                    // act by coordinates, which takes the front for itself.
                    if ((bool?)lastView["window"]?["elevated"] == true
                        && !ElevatedElsewhere(lastView, application, ShowsTheApplication(state, lastView))
                        && !ReopensUnraisedFirst(lastView, steps.Count, application))
                    {
                        // The application runs as administrator: Windows does not let a lower process read or press
                        // its controls (measured on Task Manager). Said as such instead of clicking without effect.
                        // Ronda 19b (r17 t2-c03): only of the mission's application; a raised window of another program
                        // in front (the person's Task Manager before «abre configuración») leaves the opening to go on.
                        errorCode = ElevatedStop(lastView);
                        break;
                    }

                    // Regresiones r2 M3 (live v8): on a window with an accessible tree, a verified click on the
                    // navigation control named as the place left the window as it was (no page, no menu): the window
                    // was probably there already. Said honestly as «parece que ya estabas», instead of going on to type
                    // the place's name into the window's search; but only once the page had its time to draw (review
                    // r4: a slow window still on the old page reads the same). The click is looked at again PageLooks
                    // times, PageLookInterval apart, with the loop's own look and its whole check, and a look that is no
                    // longer as it was goes on as usual.
                    // r30 (banco Br28, y8): the other half of the same wait. The verified click on the place changed
                    // the window and the first look after it does not show the place yet (176 ms after the click the
                    // panel was listed and its button not yet renamed): the window is still being drawn, and it is
                    // looked at once more, Settle later, before another step is decided. Once per click, on the same
                    // count of looks: a window that never stops changing gets that one look and no more.
                    string signature = ViewSignature(lastView);
                    string placeAsked = ArrivalPlace(goal, chained);
                    int arrivalLooks = (int?)state["alreadyThereLook"] == steps.Count ? (int?)state["alreadyThereLooks"] ?? 0 : 0;
                    // Estabilización, encargo C (banco f2c y10: «tienda» y luego «biblioteca», the library drew 4 s after
                    // its address and the click rule pressed «BIBLIOTECA» on the first look, still the store): a place
                    // just opened by its address is looked at again while the window is as it was before the opening
                    // (PageLooks times, PageLookInterval apart), and once more after it first changes, before any act.
                    bool placeDrawing = steps.Count > start && steps[^1] is JsonObject placing
                        && (string?)placing["operation"] == "app.open" && (bool?)placing["placeOpened"] == true
                        && arrivalLooks < PageLooks && state["lastSignature"] is JsonValue
                        && (arrivalLooks == 0 || string.Equals(signature, (string?)state["lastSignature"], StringComparison.Ordinal));
                    if (placeDrawing)
                    {
                        state["alreadyThereLook"] = steps.Count;
                        state["alreadyThereLooks"] = arrivalLooks + 1;
                        ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.view",
                            $"step.{steps.Count}.place_still_drawn.look.{arrivalLooks + 1}");
                        await context.Delay(PageLookInterval, cancellationToken).ConfigureAwait(true);
                        continue;
                    }

                    bool stillDrawn = arrivalLooks == 0 && state["lastSignature"] is JsonValue
                        && !string.Equals(signature, (string?)state["lastSignature"], StringComparison.Ordinal)
                        && ComputerUseSuccessCheck.ClickedThePlace(placeAsked, SubgoalSteps(steps, start), lastView);
                    if (stillDrawn || (placeAsked.Length > 0 && !ComputerUseSuccessCheck.MissionMovedTheWindow(steps)
                        && ComputerUseSuccessCheck.ClickedPlaceLeftTreeAsIs(placeAsked, SubgoalSteps(steps, start), lastView)))
                    {
                        if (arrivalLooks >= PageLooks)
                        {
                            errorCode = "computer_use_already_there_unconfirmed";
                            break;
                        }

                        state["alreadyThereLook"] = steps.Count;
                        state["alreadyThereLooks"] = arrivalLooks + 1;
                        ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.view",
                            $"step.{steps.Count}.{(stillDrawn ? "arrival_still_drawn" : "place_as_it_was")}.look.{arrivalLooks + 1}");
                        await context.Delay(stillDrawn ? Settle : PageLookInterval, cancellationToken).ConfigureAwait(true);
                        continue;
                    }

                    // A step that never pressed anything changed nothing by nature: it is no act that «stopped changing
                    // the screen» (live e2: «blue» and «azul» not found ended the mission before the palette's «Añil»;
                    // pasada r15b, v3-28: an act refused as going round is never sent). A step that was sent and failed
                    // after it (its post-read unchanged, its effect uncertain) did press: it counts, or a model pressing
                    // one control after another on a window that does not answer would never stop (review of
                    // paro-campo, finding 3).
                    bool lastFoundNothing = steps.Count > start && steps[^1] is JsonObject lastStep
                        && (bool?)lastStep["ok"] != true
                        && (string?)lastStep["error"] is "visible_button_not_found" or "visible_control_label_mismatch"
                            or "visible_control_needs_confirmation" or "computer_use_no_progress";
                    // Review 4 of ronda 24: the written text read with the signature, so a key whose effect lands on
                    // it (a command an Enter ran in a console no control's value holds) is never «as it was» on the
                    // signature alone.
                    string signatureText = string.Join('\n', currentText.Select(line => (string?)line));
                    // r4a M2 (g1), kept by revisión D (H4): the mission's window holds the front for its acts, but the
                    // person may bring theirs up, or the Core gave it back at their input or after a text. A key or a
                    // text sent by the keyboard and then looked at behind: the focus a key gave a box drawn by the window
                    // itself (CEF) shows only while the window is active, so the look cannot tell whether it changed
                    // anything. A key or a text delivered by a message or a field's value reaches the window behind as
                    // well, and its look is as good as any.
                    bool lookedBehind = steps.Count > start && steps[^1] is JsonObject keyed
                        && (bool?)keyed["ok"] == true
                        && (string?)keyed["operation"] is "input.key.press" or "input.text.type"
                        && (string?)keyed["method"] == "keyboard"
                        && ComputerUseSuccessCheck.LookedBehind(lastView);
                    MarkSameView(state, steps, start, signature, lookedBehind, signatureText);
                    state["lastSignatureText"] = signatureText;
                    // Ronda 25: a look with no act sent since the last one (a refused «done», s01) is no unchanged act, nor
                    // one whose act sent the keyboard to a known place other than before and other than the control it
                    // pressed (r24b: ctrl_f into the box). A click that only focused what it pressed still counts.
                    bool acted = (int?)state["lastSignatureStep"] != steps.Count;
                    JsonObject? held = lastView["window"]?["focused"] as JsonObject;
                    string? focus = held is null ? null : $"{(string?)held["kind"]}|{(string?)held["name"]}";
                    bool focusMoved = focus is not null && focus != (string?)state["lastFocusSeen"]
                        && !(steps.Count > 0 && steps[^1] is JsonObject act && (string?)act["operation"] == "input.visible.click"
                            && ComputerUseSuccessCheck.Fold((string?)held!["name"]).Trim()
                                == ComputerUseSuccessCheck.Fold((string?)act["name"] ?? (string?)act["label"]).Trim());
                    int unchanged = string.Equals(signature, (string?)state["lastSignature"], StringComparison.Ordinal)
                        ? ((int?)state["unchangedViews"] ?? 0) + (lastFoundNothing || lookedBehind || !acted || focusMoved ? 0 : 1)
                        : 0;
                    state["lastSignature"] = signature;
                    state["lastSignatureStep"] = steps.Count;
                    state["lastFocusSeen"] = focus;
                    state["unchangedViews"] = unchanged;
                    // Two acts in a row without the screen changing: the loop stops and
                    // says what it sees instead of going round (diseño §3).
                    // Ronda 25 (libro §4.2): no «one more step» (pasada r15b C2, 0 of 4 in the bench: c7, u9, x7).
                    if (unchanged >= 2 && done > 0)
                    {
                        errorCode = "computer_use_surface_unchanged";
                        break;
                    }

                    ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.view",
                        $"step.{steps.Count + 1}.controls.{ControlCount(lastView)}.text.{TextCount(lastView)}");
                    if (SurfaceTrace(lastView, steps.Count + 1) is { } surfaceTrace)
                    {
                        // Ronda 20 P6: a frame showing only its chrome, read through its family's content window or not
                        // and why (recorded only).
                        ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.surface", surfaceTrace);
                    }

                    if (ControlCount(lastView) >= ViewControlLimit && (int?)lastView["controlCount"] is int total)
                    {
                        // Pasada r15b (v3-01, v3-04): the whole tree's count past the view's cap, recorded only (never
                        // shown to the model): whether what the look did not list was there at all.
                        ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.view_total",
                            $"step.{steps.Count + 1}.listed.{ControlCount(lastView)}.of.{total.ToString(CultureInfo.InvariantCulture)}");
                    }

                    // Revision 1 of r24b (finding 2): a search whose query shows only where the view showed it before
                    // the search started is told to the model on the sub-goal's last step («searchNothingNew»).
                    if (steps.Count > start && steps[^1] is JsonObject searchedStep)
                    {
                        ComputerUseSuccessCheck.MarkSearchNothingNew(searchedStep, lastView, SubgoalSteps(steps, start));
                    }

                    context.SetStatus($"Paso {steps.Count + 1}: decidiendo");
                    var modelWatch = Stopwatch.StartNew();
                    // Encargo U1 (a): a rule's click pressed behind without effect is taken once more, now in front.
                    MindComputerUseStep? inFrontAgain = AgainInFront(state, steps, start, lastView);
                    MindComputerUseStep? decision = inFrontAgain ?? await context.Decide(
                        new ComputerUseStepRequest(
                            execution.Objective, goal, application, successCheck,
                            ForTheJudge(CompactForTheMind(lastView), state, context.TypedInSession, lastView, steps), HistoryForMind(steps, start),
                            Math.Min(subgoalBudget - done, budget - steps.Count), index, plan.Count,
                            context.LabelTranslations?.EntryFor(goal) ?? NotedEntryFor(state, goal),
                            (string?)current["formCheck"]),
                        cancellationToken).ConfigureAwait(true);
                    // lat-e5: the mind's time in the encoder (waiting for it, encoding) is not the model's.
                    (long modelMs, long encoderMs) = SplitDecideTime(modelWatch.ElapsedMilliseconds, decision);
                    state["modelMs"] = ((long?)state["modelMs"] ?? 0) + modelMs;
                    state["encoderMs"] = ((long?)state["encoderMs"] ?? 0) + encoderMs;
                    if (encoderMs > 0)
                    {
                        ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.decide_time",
                            $"step.{steps.Count + 1}.encoder_ms.{encoderMs}.model_ms.{modelMs}");
                    }

                    if (decision is null)
                    {
                        errorCode = "computer_use_decision_unavailable";
                        break;
                    }

                    if (inFrontAgain is not null)
                    {
                        ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.again_in_front", $"step.{steps.Count + 1}");
                    }

                    NoteTranslation(state, decision, lastView, steps.Count + 1, index);
                    NoteViewWanted(state, decision);

                    if (frontOnly && !OpensTheWindow(decision.Operation)
                        && steps.OfType<JsonObject>().LastOrDefault(step => OpensTheWindow((string?)step["operation"] ?? string.Empty))
                            is { } opening)
                    {
                        // r29, review (tandas b2/c28u t4 t17, v3-50): the mission's own opening left no process (it
                        // failed, or its receipt names none) and the look still says only who is in front: there is no
                        // window of the mission to look at. It stops with the cause of that opening (the mind's own
                        // word for a file not opened, the failed step, or a window that never let itself be read); the
                        // window in front is not read whole in its place. An opening whose window does come (Office's
                        // start screen after an app.open that said false) never reaches here: its look is the
                        // application's.
                        if (decision.Operation == "none"
                            && decision.Code.StartsWith(FileNotOpened + ":", StringComparison.Ordinal))
                        {
                            errorCode = "computer_use_file_not_opened";
                            state["fileNotOpened"] = decision.Code[(FileNotOpened.Length + 1)..];
                            state["stopReason"] = decision.Reason;
                        }
                        else
                        {
                            // Estabilización D2: an opening that held whose window never showed is no unreadable window.
                            errorCode = (bool?)opening["ok"] == true ? "computer_use_app_not_shown" : "computer_use_step_failed";
                        }

                        state.Remove("window");
                        lastView = null;
                        break;
                    }

                    if (frontOnly && !OpensTheWindow(decision.Operation))
                    {
                        state[FrontLookedWholeField] = true;
                        ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.view", "front_only.looked_whole");
                        continue;
                    }

                    ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.decision",
                        $"step.{steps.Count + 1}.{ShellTrace.SanitizeLabel(decision.Operation)}.{DecisionSource(decision)}");
                    if (IsStale(lastView) && EndsOnTheView(decision.Operation))
                    {
                        // Ronda 21, review 1 (finding 2): a final says something of the screen (done, nothing to do, a
                        // gate, no document, a protected window): never on a kept look. The window is looked at afresh
                        // and decided on again; when that look fails the mission says it could not read the window.
                        ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.view_stale",
                            $"subgoal.{index + 1}.{(decision.Operation == "done" ? "done" : "final")}");
                        continue;
                    }

                    if (hidesPersonsWindow && !OpensTheWindow(decision.Operation))
                    {
                        // Over the blank view only an opening goes on: nothing is done, cited or said of the person's
                        // window, and the final names no window.
                        errorCode = "computer_use_no_application";
                        lastView = null;
                        break;
                    }

                    bool decidedOnTheApplication = ShowsTheApplication(state, lastView);
                    if (!ElevatedViewAllows(lastView, steps.Count, application, decision.Operation, decidedOnTheApplication))
                    {
                        // Review of cu-v3-elevacion (finding 5): on a raised window the only step taken is reopening
                        // the application with the person's rights; a «done» citing what OCR read there, or an act
                        // Windows would swallow, stops with the elevated limit as before. On a raised window of another
                        // program (ronda 19b) the limit is not the application's: nothing was done there.
                        errorCode = ElevatedElsewhere(lastView, application, decidedOnTheApplication)
                            ? "computer_use_window_not_application"
                            : ElevatedStop(lastView);
                        break;
                    }

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

                        // What this sub-goal typed is on screen because it was typed (the search box's echo), never
                        // proof of arriving (measured on Steam: «Cuphead» typed in the store search cited as found).
                        // Revisión 1 de r24 (B2, v3-08): the text the goal puts in a part it names, typed into the field
                        // of that part and shown as its whole value, is the act done, never an echo nor «typed by BAXY».
                        // Held only when the mind says so («written») and the view and the steps show it (SlotWritten).
                        bool written = (bool?)decision.Arguments["written"] == true
                            && ComputerUseSuccessCheck.SlotWritten(
                                cited, goal, lastView, SubgoalSteps(steps, start), (string?)state["subgoalFirstText"]);
                        bool echo = !written && ComputerUseSuccessCheck.CitationEchoesQuery(
                            cited, lastView, SubgoalSteps(steps, start), ComputerUseSuccessCheck.SearchResultsProve(successCheck));
                        // Pasada v3 r9 (v3-13): the mind says the option cited was chosen before any act touched it.
                        // Held only when the view shows it chosen and no act of the sub-goal chose it: then it is
                        // told as it already was, and no act is claimed (the mind's judge judges claimed acts).
                        // Ronda 24b (u5, n6): or the new blank document asked for is the one already in front.
                        bool already = (bool?)decision.Arguments["already"] == true
                            && (ComputerUseSuccessCheck.AlreadyChosen(cited, lastView, SubgoalSteps(steps, start))
                                || ComputerUseMissionWindow.BlankDocumentAlready(cited, lastView, SubgoalSteps(steps, start)));
                        // Ronda 23 (v2-s01): a «done» over a planned check whose exact atoms (a result, a value, a
                        // count, a file) the screen or the disk contradicts is never a close. Once per sub-goal the model
                        // decides again with the cause on the sub-goal's last step («checkUnmet»), after a fresh look;
                        // a second such «done» stops: the screen did not show the proof.
                        bool contradicts = !hidesPersonsWindow && ComputerUseSuccessCheck.ExactCheckContradicts(
                            successCheck, lastView, SubgoalSteps(steps, start), ComputerUseSuccessCheck.SubgoalStarted(state));
                        // Ronda 24 (v3-59): a «done» for a place whose planned check does not hold and whose citation
                        // names nothing of the place is no arrival either; the same one retry, then a stop.
                        bool offPlace = !hidesPersonsWindow && !contradicts && ComputerUseSuccessCheck.CitationOffThePlace(
                            cited, goal, successCheck, lastView, SubgoalSteps(steps, start), TranslatedNames(state),
                            state["aliases"] as JsonObject, ComputerUseSuccessCheck.SubgoalStarted(state));
                        contradicts |= offPlace;
                        if (contradicts)
                        {
                            JsonObject? unmetStep = (int?)state["checkUnmetSubgoal"] != index && steps.Count > start
                                ? steps[^1] as JsonObject
                                : null;
                            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.evidence",
                                $"refused.{(offPlace ? "off_the_place" : "check_contradicts")}.{(unmetStep is null ? "stop" : "retry")}");
                            if (unmetStep is not null)
                            {
                                state["checkUnmetSubgoal"] = index;
                                unmetStep["checkUnmet"] = true;
                                continue;
                            }
                        }

                        // Falsos éxitos v3 M1: whether the citation proves a goal of doing something (a verified act of
                        // the sub-goal, not on the first look, no text BAXY typed) is the mind's judge (cu_validate
                        // _checked_act), fed by ForTheJudge. Estabilización R16: the App's twin of it, which judged the
                        // same done again, is gone (one refusal in every trace with a verdict, v3-11, and a wrong one).
                        if (cited.Length > 0 && !echo && !contradicts && ComputerUseSuccessCheck.ViewContains(lastView, cited))
                        {
                            subgoalReached = true;
                            subgoalEvidence = cited;
                            subgoalBy = "model_evidence";
                            if (already)
                            {
                                state["alreadyChosen"] = cited;
                            }
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
                            // Estabilización L: the mind found the sub-goal reached a limit while acting (a list that does
                            // not end after the wheel scrolls it may spend): it stops with that limit, whatever the view.
                            if (decision.Operation == "none" && decision.Code.StartsWith(LimitCode, StringComparison.Ordinal))
                            {
                                errorCode = LimitStop + decision.Code[LimitCode.Length..];
                                state["stopReason"] = decision.Reason;
                                break;
                            }

                            // Encargo IMP2 (imp1 imp-wa-abrir, imp-wa-leer): the name typed into a search whose results
                            // were not drawn yet (measured on a chat client's search: 750 to 880 ms after the text, the
                            // look after typing came at 550 ms) is looked at again once, a moment later, instead of
                            // closing the search; the step carries «awaited» so the mind never asks twice.
                            if (decision.Operation == "none" && decision.Code == SearchPending
                                && steps.Count > start && steps[^1] is JsonObject typed && (bool?)typed["awaited"] != true)
                            {
                                typed["awaited"] = true;
                                ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.search_pending", $"step.{steps.Count}");
                                await context.Delay(SearchResultsWait, cancellationToken).ConfigureAwait(true);
                                continue;
                            }

                            if (PartialHoldsNoFinal(decision, lastView))
                            {
                                // Review 1 of ronda 21 (finding 3, v3-63): the worker's walk ran out of its time before
                                // the whole window was read; what the model did not see may be in the part not walked.
                                // No absence and no final is said on it: the mission could not read the window whole.
                                ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.view_partial",
                                    $"step.{steps.Count + 1}.{ShellTrace.SanitizeLabel(decision.Code)}");
                                errorCode = "computer_use_view_unavailable";
                                lastView = null;
                                break;
                            }

                            // A screen torn down by the act just taken and not built again yet is no screen without a
                            // step (measured 2026-10-07 on a store: 185 ms after Enter its results page listed 17 of
                            // 52 controls, a placeholder layout, and the model rightly saw nothing to press). Once
                            // per act, looked at again, bounded, while it is redrawn; then the loop decides anew and
                            // checks the goal on the new look. Encargo V1 (banco fin1, fin2: a «done» citing the typed
                            // query, refused twice, came as «evidence_not_visible» and the page that arrived 2 s later
                            // was never looked at): any «none» whose stop would say no control was seen waits the same.
                            if (decision.Operation == "none" && NoneStop(decision.Code, gateSeen: false) == NoStepVisible
                                && await RedrawnAfterActAsync(context, state, steps, start, application, lastView, signature, cancellationToken)
                                    .ConfigureAwait(true))
                            {
                                ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.redrawn", $"step.{steps.Count}");
                                continue;
                            }

                            // Ronda 20b, palanca 8 (v3-51, v3-62): a «none» on a look that shows only the window's
                            // frame (nothing to act on, nothing written) taken at the opening, or a look the provider
                            // read as frame alone even under the owner window, is no screen without a step: the window
                            // has not shown its content yet. It is looked at again, bounded; still empty, the stop says so.
                            if (decision.Operation == "none" && decision.Code is "" or "no_step_visible"
                                && ShowsOnlyTheFrame(lastView)
                                && (state["openingWaitedMs"] is not null
                                    || ((bool?)lastView["frameOnly"] == true && (int?)state["notShownStep"] != steps.Count)))
                            {
                                // Review of palanca 8 (finding 2): «no pulsé nada en ella» holds only at the opening, with
                                // no act of the mission yet (openingWaitedMs goes with the first act). A window the
                                // provider read as frame alone later on (a dialog an act brought up) has its own cause,
                                // which claims nothing about the acts taken.
                                bool atOpening = state["openingWaitedMs"] is not null;
                                state["notShownStep"] = steps.Count;
                                if (await NotShownYetAsync(context, state, application, cancellationToken).ConfigureAwait(true))
                                {
                                    ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.shown_late", $"step.{steps.Count}");
                                    continue;
                                }

                                errorCode = atOpening ? "computer_use_app_not_shown" : "computer_use_window_not_shown";
                                state["stopReason"] = decision.Reason;
                                break;
                            }

                            // The application is on its start page with no document open and the place asked lives in
                            // one (measured on Excel and Word: their tabs exist only with a document): said as such.
                            // A search box written on screen that did not prove it took the keyboard: nothing was typed.
                            // A gate screen (an account to add, a sign-in, an update, a resource not found: v3 limits,
                            // M2) is said with the text it writes, once that text is checked on the view.
                            JsonObject? gate = GateSeen(decision, lastView);
                            // Encargo U1 (b): after the V1 wait above, a «none» on a view that still shows the control
                            // the rule just pressed without effect says that press, never «no vi un control».
                            errorCode = NoneStop(decision.Code, gate is not null);
                            if (errorCode == NoStepVisible && steps.Count > start && steps[^1] is JsonObject pressed
                                && PressedWithoutEffect(state, pressed, lastView))
                            {
                                errorCode = NoneStop("click_without_effect", gateSeen: false);
                            }
                            if (gate is not null)
                                state["gate"] = gate;
                            if (errorCode == "computer_use_file_not_opened")
                                state["fileNotOpened"] = decision.Code[(FileNotOpened.Length + 1)..];
                            state["stopReason"] = decision.Reason;
                            break;
                        }

                        // An act is taken: the opening's look is behind (NotShownYetAsync no longer applies).
                        state.Remove("openingWaitedMs");
                        JsonObject stepArguments = decision.Arguments.DeepClone() as JsonObject ?? new JsonObject();
                        stepArguments.Remove("evidence");
                        if (KeyLeavesTheWindow(decision.Operation, stepArguments))
                        {
                            errorCode = "computer_use_key_outside_window";
                            break;
                        }

                        if (!BindToMissionWindow(decision.Operation, stepArguments, lastView, state, application, SubgoalSteps(steps, start)))
                        {
                            bool guarded = ProtectedWindow(lastView);
                            bool foreign = !guarded
                                && !NoApplicationActs(decision.Operation, application, state, lastView?["window"] as JsonObject)
                                && ComputerUseMissionWindow.ForeignDocumentAct(decision.Operation, stepArguments, lastView, state);
                            errorCode = guarded
                                ? "computer_use_window_protected"
                                : NoApplicationActs(decision.Operation, application, state, lastView?["window"] as JsonObject)
                                    ? "computer_use_no_application"
                                    : foreign
                                        ? ForeignDocumentCause(decision.Operation, stepArguments,
                                            ComputerUseMissionWindow.Restored(state, lastView))
                                        : "computer_use_window_not_application";
                            // Ronda 21 (pasada r18 v3-36, v3-59): a rule's key that alters nothing of the
                            // content (a search or tab shortcut) refused on a document the mission may not touch is not
                            // pressed and does not end the mission: it is kept as a failed step with its cause and the
                            // model takes the next one with it in front. The model's own act refused, or one that
                            // selects, erases or writes, still ends it.
                            if (foreign && RefusalForTheModel(decision.Operation, stepArguments, decision.Source,
                                    SubgoalSteps(steps, start), steps.Count + 1) is JsonObject refused)
                            {
                                // The key is spent on that application for the rest of the mission (revisión 1,
                                // hallazgo b): the mind never presses it there again (SpentKey).
                                if (lastView?["window"]?["process"] is JsonNode refusedOn)
                                {
                                    refused["process"] = refusedOn.DeepClone();
                                }

                                steps.Add(refused);
                                ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.refused_to_model",
                                    $"step.{steps.Count}.{ShellTrace.SanitizeLabel((string?)refused["key"] ?? string.Empty)}");
                                errorCode = null;
                                continue;
                            }

                            break;
                        }

                        MarkOpeningForControl(decision.Operation, stepArguments);
                        if (!MindPlanBoundary.ArgumentsSatisfyExactSchema(decision.Operation, stepArguments))
                        {
                            // Ronda 23 (índices de vista y esquema, t-menu-2 r21): a rule's act the schema
                            // refuses is not taken and does not end the mission: it is kept as a failed step with its
                            // cause (the arguments refused) and the model takes the next one with it in front. The
                            // model's own act refused, or a second refusal in the sub-goal, still ends it.
                            if (SchemaRefusalForTheModel(decision.Operation, stepArguments, decision.Source,
                                    SubgoalSteps(steps, start), steps.Count + 1) is JsonObject outside)
                            {
                                steps.Add(outside);
                                ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.refused_to_model",
                                    $"step.{steps.Count}.{ShellTrace.SanitizeLabel((string?)outside["error"] ?? string.Empty)}");
                                continue;
                            }

                            errorCode = "computer_use_step_arguments_invalid";
                            break;
                        }

                        // The same act on the same control that just failed is not tried
                        // again: the model is asked for another step (§4.2).
                        if (done > 0 && inFrontAgain is null && steps[^1] is JsonObject previous
                            && (bool?)previous["ok"] == false
                            && SameStep(previous, decision.Operation, stepArguments))
                        {
                            // An act refused as going round on a screen that already stayed the same, asked once more
                            // after the mind saw that refusal: the screen stopped changing (pasada r15b: the refusal no
                            // longer counts as an unchanged act by itself, so the mind reads it first).
                            errorCode = (string?)previous["error"] == "computer_use_no_progress"
                                && ((int?)state["unchangedViews"] ?? 0) > 0
                                    ? "computer_use_surface_unchanged"
                                    : "computer_use_repeated_step";
                            break;
                        }

                        // A click refused twice in this sub-goal is not tried a third time, whatever came between
                        // (measured 2026-10-07: a read-only field clicked four times between other steps, 41 s spent).
                        if (decision.Operation == "input.visible.click"
                            && ComputerUseSuccessCheck.RefusedClicks(SubgoalSteps(steps, start), stepArguments) >= 2)
                        {
                            errorCode = "computer_use_repeated_step";
                            break;
                        }

                        var record = new JsonObject
                        {
                            ["step"] = steps.Count + 1,
                            ["operation"] = decision.Operation,
                            ["source"] = "model",
                        };
                        // The entries shown selected right before every act, a click, a key or a typing: what tells the
                        // act that chose an entry from a later one that found it chosen (review 1 of ronda 20b: an arrow
                        // that only selected the archive after Enter opened its folder; a second click on a section).
                        var chosen = state["selectedBeforeClick"] as JsonObject ?? new JsonObject();
                        chosen[(steps.Count + 1).ToString(CultureInfo.InvariantCulture)] = ComputerUseSuccessCheck.SelectedNames(lastView);
                        state["selectedBeforeClick"] = chosen;
                        // The title of the look this act was decided on: a key's reread title is measured against it,
                        // never against an older receipt's (review 3 of ronda 20b: clicks carry no title, so a key that
                        // did nothing after a click that changed the window passed for the arrival).
                        if ((string?)lastView["window"]?["title"] is { } decidedOn)
                        {
                            record["titleBefore"] = decidedOn;
                        }

                        // Ronda 24b (x7): where the keyboard was on the look this act was decided on, in front or
                        // behind: «focus:search» holds only when the act moved it (a click on «Buscar» with the box
                        // focused before and after brought nothing).
                        // Review 1 of r24b (B2): a look behind that names no focused element does not know where the
                        // keyboard was, and nothing is noted (the proof stays unknown). In front, an empty signature is
                        // a fact: the keyboard is on the document, which the list does not carry (ctrl_f moves it).
                        if (!ComputerUseSuccessCheck.FocusUnread(lastView))
                        {
                            var keyboardBefore = state["focusBeforeStep"] as JsonObject ?? new JsonObject();
                            keyboardBefore[(steps.Count + 1).ToString(CultureInfo.InvariantCulture)] =
                                ComputerUseSuccessCheck.FocusSignature(lastView);
                            state["focusBeforeStep"] = keyboardBefore;
                        }

                        if (decision.Operation == "app.open" && stepArguments[PlaceArgument] is not null
                            && (bool?)lastView["onTheApplication"] == true)
                        {
                            // Estabilización, encargo C (review H1): what the application's own window showed right before
                            // its place was opened by its address; «opened:» holds only on a line born after it.
                            var lookBefore = state["textBeforeClick"] as JsonObject ?? new JsonObject();
                            lookBefore[(steps.Count + 1).ToString(CultureInfo.InvariantCulture)] =
                                new JsonArray([.. ComputerUseSuccessCheck.ShownLines(lastView).Select(line => (JsonNode?)line)]);
                            state["textBeforeClick"] = lookBefore;
                        }

                        if (decision.Operation == "input.visible.click")
                        {
                            // What was written on screen right before this click: «the page changed» (check atom page:)
                            // is measured against it, not against a start-up window seen earlier (measured on Steam:
                            // the login splash was the baseline and the store passed for the library).
                            var clickTexts = state["textBeforeClick"] as JsonObject ?? new JsonObject();
                            clickTexts[(steps.Count + 1).ToString(CultureInfo.InvariantCulture)] =
                                ComputerUseSuccessCheck.TextLines(lastView);
                            state["textBeforeClick"] = clickTexts;
                            // Every option shown chosen right before the click (a radio button, a toggle on too): what
                            // tells a click that chose the option from one on an option already chosen (pasada v3 r9).
                            var options = state["chosenBeforeClick"] as JsonObject ?? new JsonObject();
                            options[(steps.Count + 1).ToString(CultureInfo.InvariantCulture)] = ComputerUseSuccessCheck.ChosenNames(lastView);
                            state["chosenBeforeClick"] = options;
                            RecordControlsBeforeClick(state, lastView, steps.Count + 1);
                            // Revisión 2 de r22 (bloqueante 1): the control this click presses, by its identity, as it
                            // showed right before: what tells the control the click renamed or switched
                            // (ComputerUseSuccessCheck.ChangedByClick).
                            var clicked = state["clickedBefore"] as JsonObject ?? new JsonObject();
                            if (ComputerUseSuccessCheck.ClickedControl(lastView, stepArguments) is { } target)
                            {
                                clicked[(steps.Count + 1).ToString(CultureInfo.InvariantCulture)] = target;
                            }

                            state["clickedBefore"] = clicked;
                        }
                        if (decision.Operation == "input.text.type"
                            || (decision.Operation == "input.key.press"
                                && ComputerUseSuccessCheck.PasteKey((string?)stepArguments["key"])))
                        {
                            // What the view showed right before the typing (ronda 24: or a paste key): text already
                            // there proves nothing.
                            var typings = state["viewBeforeTyping"] as JsonObject ?? new JsonObject();
                            typings[(steps.Count + 1).ToString(CultureInfo.InvariantCulture)] =
                                ComputerUseSuccessCheck.ViewBeforeTyping(lastView);
                            state["viewBeforeTyping"] = typings;
                        }

                        if (decision.Operation == "input.text.type")
                        {
                            NoteWhereTheTextGoes(record, stepArguments, lastView);
                        }

                        if (decision.Operation == "input.key.press" && ComputerUseSuccessCheck.Fold((string?)stepArguments["key"]) == "enter")
                        {
                            // Ronda 24b (banco r23 c6): what the view showed right before an Enter, for the check atom
                            // sent: (ComputerUseSuccessCheck.Sent): the field that held the text and the written text.
                            var enters = state["viewBeforeEnter"] as JsonObject ?? new JsonObject();
                            enters[(steps.Count + 1).ToString(CultureInfo.InvariantCulture)] =
                                ComputerUseSuccessCheck.ViewBeforeEnter(lastView, steps);
                            state["viewBeforeEnter"] = enters;
                        }

                        if (decision.Operation == "input.key.press" && (string?)lastView?["window"]?["process"] is { Length: > 0 } keyedProcess)
                        {
                            // The application a key was pressed on: a search key that brought up something not sought
                            // is spent there for the rest of the mission (SpentKey).
                            record["process"] = keyedProcess;
                        }

                        if (decision.Source == "rule" && decision.Operation is "input.key.press" or "input.visible.click")
                        {
                            // A key the mind's routine pressed, not the model: only the routine's own Escape after its
                            // search key lets it close what that key left open (review finding 2 of menus-teclas).
                            // Encargo U1: a click of the routine, and whether its look was behind (PressedWithoutEffect).
                            record["rule"] = true;
                            if (decision.Operation == "input.visible.click" && ComputerUseSuccessCheck.LookedBehind(lastView))
                            {
                                record[DecidedBehindField] = true;
                            }
                        }

                        if (chained)
                        {
                            record["subgoal"] = index;
                        }

                        foreach (string key in new[] { "label", "index", "text", "key", "target", "direction", "amount", "appId",
                            "field", "replace", "entry", "consequence", "search", "choose", "manner", PlaceArgument,
                            PlaceValueArgument })
                        {
                            if (stepArguments[key] is JsonNode value)
                            {
                                record[key] = value.DeepClone();
                            }
                        }

                        if ((string?)stepArguments["manner"] == "menu" && ComputerUseSuccessCheck.MenuTargetKind(lastView, stepArguments["index"]) is { } targetKind)
                        {
                            // Revisión 1 de la ronda 21 (hallazgo 3): what the menu was opened on, by the view it was
                            // decided on: «menuOpened:» with no name is an empty space's, a container's menu only.
                            record["targetKind"] = targetKind;
                        }

                        if (decision.Operation == "file.open" && stepArguments["name"] is JsonNode fileName)
                        {
                            // The file asked, for the final to name a file.open that failed (its post-read names it
                            // when it opened).
                            record["name"] = Path.GetFileName((string?)fileName ?? string.Empty);
                        }

                        string viewHash = Hash(signature);
                        record[ViewHashField] = viewHash;
                        if (ClicksAnOpener(decision.Operation, stepArguments, lastView))
                        {
                            record[OpenerField] = true;
                        }

                        if (RepeatsAnActThatCycled(SubgoalSteps(steps, start), decision.Operation, stepArguments, viewHash, out bool reopens))
                        {
                            // The same act already succeeded from this very screen and the screen came back to it:
                            // taking it again goes round. It is recorded as failed so the mind picks another step.
                            record["ok"] = false;
                            record["error"] = "computer_use_no_progress";
                            steps.Add(record);
                            state["elapsedMs"] = alreadyElapsed + stopwatch.ElapsedMilliseconds;
                            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer.use.step",
                                $"step.{steps.Count}.{ShellTrace.SanitizeLabel(decision.Operation)}.no_progress");
                            continue;
                        }

                        if (reopens)
                        {
                            // What it opened closed when the front went back to the person, not by its own hand: it is
                            // opened again, once per opener in the sub-goal (menus-efímeros, pasada r15b).
                            record[ReopensField] = true;
                            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer.use.step",
                                $"step.{steps.Count + 1}.{ShellTrace.SanitizeLabel(decision.Operation)}.reopens");
                        }

                        // How much the screen listed when this act was taken: a look after it that lists less shows a
                        // screen torn down (RedrawnAfterActAsync).
                        state["actFromControls"] = lastView is null ? 0 : ControlCount(lastView);
                        context.SetStatus($"Paso {steps.Count + 1}: {Describe(decision.Operation, stepArguments)}");
                        PreparedOperation prepared = context.Registry.GetOrAdd(new RoutedOperation(decision.Operation, stepArguments));
                        var stepWatch = Stopwatch.StartNew();
                        long stepStartedMs = context.NowMs();
                        OperationResponse response;
                        // When the act is sent: a window that comes after it is measured against the person's input since.
                        ComputerUseMissionWindow.NoteAct(state, DateTimeOffset.UtcNow);
                        // Review of lat-apertura-clic (finding 1): the act is never cut at the mission's time. The Core
                        // answers its requests one at a time and has no way to stop one already sent: a wait cut here
                        // stops nothing, the act may still land after the turn said its time was out, and the next
                        // request (this mission's or the next turn's) queues behind it. The act's own answer is what
                        // is waited for; the mission's time is checked again as soon as it comes.
                        try
                        {
                            response = await ExecuteAsync(context, state, prepared, traceId, cancellationToken).ConfigureAwait(true);
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

                        // The step as decided, before its answer: what a try after the person's pause answers anew.
                        var unanswered = (JsonObject)record.DeepClone();
                        RecordResponse(record, response);
                        _ = context.MarkResolved(context.Registry, prepared);
                        steps.Add(record);
                        NoteTranslatedClick(state, record);
                        if (FollowHandedWindow(state, record, steps, DateTimeOffset.UtcNow, out string handedWhy))
                        {
                            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.window",
                                $"handed.step.{steps.Count}");
                        }
                        else if (handedWhy.Length > 0)
                        {
                            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.window",
                                $"handed.refused.{handedWhy}.step.{steps.Count}");
                        }

                        if (OpensTheWindow(decision.Operation) && (int?)record["processId"] is > 0 and int opened)
                        {
                            // From here on the mission looks at that application's window; another process's windows
                            // are no longer the mission's (goal v3 ventana-misión).
                            if ((int?)state["processId"] != opened)
                            {
                                ComputerUseMissionWindow.Untie(state);
                            }

                            state["processId"] = opened;
                        }

                        int personTries = 0;
                        while ((string?)record["error"] is { } stopped && PersonInputStops.Contains(stopped)
                            && personTries < PersonPauseRetries
                            && context.NowMs() - stepStartedMs < PersonPauseRetryMs)
                        {
                            // fable/cu-v3-reintento-pausa: stopping for the person is right, giving up is not. An act
                            // refused before it pressed is tried again; the foreground lease waits for their next
                            // pause. One that pressed and whose post-read their input cut short is never pressed again
                            // blind: the mission's window is looked at again, and a change there is its effect (the
                            // window behind the person's, so their keys went into their own window); only a window
                            // that still shows what the act was decided on says the act did nothing, and it is tried
                            // again. Review of the branch: only a click is one press. A text, keys or a scroll
                            // cut short partway left part of their effect (the first letters typed: the field changed,
                            // and a look would verify a text that was never typed whole, and the session would count
                            // it as typed); they are neither verified by a look nor sent again, and the cause is said.
                            if ((bool?)record["effectUncertain"] == true)
                            {
                                // A search burst cut short typed part of its destination: like a text, never verified by
                                // a look nor sent again.
                                if (decision.Operation != "input.visible.click" || stepArguments["search"] is not null)
                                {
                                    break;
                                }

                                bool? shown = await EffectShownAfterPersonStopAsync(
                                    context, state, application, lookedWithText, signature, cancellationToken).ConfigureAwait(true);
                                if (shown == true)
                                {
                                    record["ok"] = true;
                                    record["changed"] = true;
                                    record["surfaceChanged"] = true;
                                    record["verifiedBy"] = "look_after_person_pause";
                                    record.Remove("error");
                                    record.Remove("effectUncertain");
                                    NoteTranslatedClick(state, record);
                                    ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer.use.step",
                                        $"step.{steps.Count}.{ShellTrace.SanitizeLabel(decision.Operation)}.effect_seen_after_pause");
                                    break;
                                }

                                if (shown is null)
                                {
                                    break;
                                }
                            }

                            personTries++;
                            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer.use.step",
                                $"step.{steps.Count}.{ShellTrace.SanitizeLabel(decision.Operation)}.{stopped}.retry.{personTries}");
                            PreparedOperation again = context.Registry.GetOrAdd(new RoutedOperation(decision.Operation, stepArguments));
                            OperationResponse retried;
                            try
                            {
                                ComputerUseMissionWindow.NoteAct(state, DateTimeOffset.UtcNow);
                                retried = await ExecuteAsync(context, state, again, traceId, cancellationToken).ConfigureAwait(true);
                            }
                            catch (Exception exception) when (exception is TimeoutException or IOException or InvalidOperationException)
                            {
                                _ = context.MarkResolved(context.Registry, again);
                                break;
                            }

                            if (PendingOperationConfirmation.TryCreate(retried, again, TimeProvider.System,
                                    out PendingOperationConfirmation? retriedConfirmation) && retriedConfirmation is not null)
                            {
                                steps.RemoveAt(steps.Count - 1);
                                state["pendingStep"] = unanswered;
                                state["elapsedMs"] = alreadyElapsed + stopwatch.ElapsedMilliseconds;
                                ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.confirm",
                                    $"step.{steps.Count + 1}.{ShellTrace.SanitizeLabel(decision.Operation)}");
                                return new Result(null, missionPrepared, retriedConfirmation);
                            }

                            record = (JsonObject)unanswered.DeepClone();
                            RecordResponse(record, retried);
                            _ = context.MarkResolved(context.Registry, again);
                            steps[steps.Count - 1] = record;
                            NoteTranslatedClick(state, record);
                        }

                        record = ExpandSearchBurst(steps, record);
                        if ((string?)record["error"] is { } personStop && PersonInputStops.Contains(personStop))
                        {
                            // The person is using the PC (v3 point 0, fix 3): the act needed the real input and either
                            // no pause came within the wait, or the person acted during the burst and it stopped, and
                            // its tries after their pauses (above) ran out or could not be made. Going on would act
                            // over them, and nothing about the screen is at fault: the mission
                            // stops with that cause, said in the person's words.
                            state["elapsedMs"] = alreadyElapsed + stopwatch.ElapsedMilliseconds;
                            errorCode = personStop;
                            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer.use.step",
                                $"step.{steps.Count}.{ShellTrace.SanitizeLabel(decision.Operation)}.{personStop}");
                            break;
                        }

                        state["elapsedMs"] = alreadyElapsed + stopwatch.ElapsedMilliseconds;
                        ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer.use.step",
                            $"step.{steps.Count}.{ShellTrace.SanitizeLabel(decision.Operation)}.ok.{((bool?)record["ok"] == true ? "true" : "false")}.ms.{stepWatch.ElapsedMilliseconds}");
                        if (RestartsSubgoalClock(decision.Operation, decision.Source,
                                (bool?)record["ok"] == true, SubgoalSteps(steps, start).Count, goal))
                        {
                            // Ronda 21 (pasada r18 v3-26): the opening the engine put first in a sub-goal that is not about
                            // opening is not the sub-goal's work; its clock starts once the application is there. The
                            // mission's own time does not change.
                            state["subgoalStartMs"] = state["elapsedMs"]!.DeepClone();
                            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.subgoal", $"subgoal.{index + 1}.clock_after_opening");
                        }
                        if (OpensTheWindow(decision.Operation))
                        {
                            // The next look waits, bounded, for the application's window; an application launched
                            // now also gets time to replace its start-up window (measured: Steam's «Iniciar sesión en
                            // Steam» splash was searched for the library until every way to find it was spent).
                            state["awaitWindow"] = true;
                            state["openedCold"] = (bool?)record["alreadyRunning"] != true;
                        }
                        else if (decision.Code == "expects_title_change" && (bool?)record["ok"] == true)
                        {
                            state["awaitTitleChange"] = (string?)lastView?["window"]?["title"] ?? string.Empty;
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
            if (index + 1 < plan.Count && lastView is not null
                && ScreenExcerpt(lastView, (string?)current["goal"])["numbers"] is JsonArray { Count: > 0 } shownThere)
            {
                // Regresiones r4 (live v2-c2): what carried a number in this part's window when it was reached (a
                // calculator's display) is its own fact; the chain's last window (the editor it pasted into) never shows it.
                current["numbers"] = shownThere.DeepClone();
            }

            if (lastView is not null)
            {
                // Ronda 24b (x10): how the window wrote the place the term that held read (the mark «BIBLIOTECA», the
                // page's title), and whether any act of the part got it there: a part reached on its first look is
                // told as it was found, never left out of the final for want of the window's spelling.
                current["acted"] = SubgoalSteps(steps, start).OfType<JsonObject>().Any(MayHaveActed);
                if (ComputerUseSuccessCheck.ArrivedAs(subgoalBy, lastView, SubgoalSteps(steps, start)) is { Length: > 0 } arrivedAs)
                {
                    current["arrivedAs"] = arrivedAs;
                }
            }

            CloseSubgoal(context, state, current, steps, start, reached: true, subgoalBy);
            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.subgoal",
                $"subgoal.{index + 1}.of.{plan.Count}.reached.steps.{steps.Count - start}");
            // Pasada v3 r9 (v3-42): which term of the check held, so a false arrival is diagnosed from the live trace.
            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.satisfied",
                $"subgoal.{index + 1}.{SatisfiedLabel(successCheck, subgoalBy)}");
            // Ronda 24b (banco r23, e1): what the exact atom that closed it read (the value and the control or line
            // that showed it) goes with the sub-goal to the audit; the trace keeps only where it was read.
            if (ComputerUseSuccessCheck.Witness(subgoalBy, lastView) is { } witness)
            {
                current["witness"] = witness;
                ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.witness",
                    $"subgoal.{index + 1}.{ComputerUseSuccessCheck.WitnessLabel(witness)}");
            }

            if (index + 1 < plan.Count)
            {
                EnterSubgoal(state, index + 1, context.LabelTranslations);
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
            // Every way to find the place was spent and none named it (live n5: «Wi-Fi» on a PC without Wi-Fi, the
            // window's own search typed it and listed no item called so): the window does not have it, said as such
            // instead of «the screen stopped changing».
            if (errorCode is not null && ScreenStops.Contains(errorCode) && errorCode != "computer_use_time_exhausted"
                && lastView is not null
                && ArrivalPlace((string?)plan[failedIndex]?["goal"], chained) is { Length: > 0 } asked
                && ComputerUseSuccessCheck.SearchedAndNotFound(
                    asked, SubgoalSteps(steps, (int?)state["subgoalStart"] ?? 0), lastView))
            {
                errorCode = "computer_use_place_not_found";
                state["missingPlace"] = SpelledAsSeen(asked, steps);
            }
            else if (errorCode is "computer_use_no_step_visible" or "computer_use_click_without_effect" or "computer_use_surface_unchanged"
                    or "computer_use_evidence_not_visible" or "computer_use_repeated_step" or "computer_use_budget_exhausted"
                && lastView is not null
                && ArrivalPlace((string?)plan[failedIndex]?["goal"], chained) is { Length: > 0 } there
                && !ComputerUseSuccessCheck.MissionMovedTheWindow(steps)
                && ComputerUseSuccessCheck.ClickedPlaceLeftPageAsIs(
                    there, SubgoalSteps(steps, (int?)state["subgoalStart"] ?? 0), lastView, state))
            {
                // The click on the place's own name left the page as it was (live v2-s12: Steam already on its
                // library, the click only opened its menu): said as probably there, never as arrived.
                errorCode = "computer_use_already_there_unconfirmed";
            }

            CloseSubgoal(context, state, (JsonObject)plan[failedIndex]!, steps, (int?)state["subgoalStart"] ?? 0,
                reached: false, satisfiedBy: null);
            await CollapseListsLeftOpenAsync(
                context, state, steps, lastView, (string?)plan[failedIndex]?["application"], traceId, cancellationToken)
                .ConfigureAwait(true);
        }

        foreach (JsonObject typedStep in steps.OfType<JsonObject>())
        {
            if ((bool?)typedStep["ok"] == true && (string?)typedStep["operation"] == "input.text.type")
            {
                context.TypedInSession?.Add((string?)typedStep["text"], (string?)typedStep["into"], (string?)typedStep["typedOn"]);
            }
        }

        if (reached && lastView is not null && !IsStale(lastView) && CarriesQuestion((string?)state["goal"]))
        {
            await NoteTheTailAsync(context, state, lastView, (string?)plan[^1]?["application"], cancellationToken)
                .ConfigureAwait(true);
            await NoteTheChatLinesAsync(context, state, lastView, (string?)plan[^1]?["application"], cancellationToken)
                .ConfigureAwait(true);
        }

        JsonObject observed = Observed(state, steps, reached, satisfiedBy, evidence, errorCode, lastView);
        // v3 point 1: what moved the person's front is an annoyance, never zero, even when it was handed back: a
        // delivery that brought the window up (UI Automation's SetValue on a Chromium/WebView2 field activates it)
        // and a front the application took by itself while it started.
        int frontChanges = steps.Count(step => (bool?)step?["frontChanged"] == true);
        int frontReturned = (int?)state["frontReturnedAtStart"] ?? 0;
        if (frontChanges + frontReturned > 0)
        {
            // Restored among the changed ones (an opening's receipt says frontRestored of its own hand-back too).
            int frontRestored = steps.Count(step => (bool?)step?["frontChanged"] == true && (bool?)step?["frontRestored"] == true);
            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.front",
                $"changed.{frontChanges}.restored.{frontRestored}.returned_at_start.{frontReturned}");
        }

        ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.end", EndTraceDetail(
            reached, steps.Count, (long?)state["elapsedMs"] ?? 0, (long?)state["modelMs"] ?? 0, errorCode,
            (long?)state["encoderMs"] ?? 0));
        if (errorCode is not null)
        {
            // The stop code on a line of its own: appended to the end line it passed the trace's 64 characters
            // («…computer_use_window_elevated») and the whole line was written «invalid» (v3 limits, M3).
            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.stop", ShellTrace.SanitizeLabel(errorCode));
        }
        execution.ComputerUse = null;
        return new Result(Synthesize(missionPrepared, reached, errorCode, observed), missionPrepared, null);
    }

    /// <summary>
    /// Ronda 20b, palanca 6, review finding 1 (v3-40 b): the lists this mission opened that its last look still shows
    /// open, as the collapse of each ({label, index, manner «collapse»}). Only a control the mission itself opened (an
    /// ok click with manner «open», or one the worker pressed by its ExpandCollapse, method «expand») and that the look
    /// marks «expanded» under that same name; never a tree's item (an expanded branch is where the person navigates),
    /// never one the person opened. Empty when the look is not the mission's window (another application's, the
    /// person's hidden one, a protected window).
    /// Review 2, finding 3: a popup born in the mission has no «expanded» to read (a tab's context menu opened with
    /// manner «menu», a split button's flyout opened by its arrow with the pointer, the click's receipt saying
    /// <c>popupBorn</c>): the control that opened it, still in the look under that name (a tree's item too: its menu is
    /// no branch), gets the same collapse, which the worker sends as Escape to the popup's own window only while a popup
    /// is open beside it, and reads closed after.
    /// Review 3, finding 1: the popup's close is its own manner, «dismiss», which never touches the control's
    /// ExpandCollapse (a tree branch or a list the person had open beside the menu stays as it is): only the popup's own
    /// window gets the Escape. Each step is paired with one control of the look by its name and its kind (the receipt's
    /// kind; without it, the step's index): a right click on the item «Fotos» never reaches a branch «Fotos» of the
    /// tree, and the list path still never takes a tree's item.
    /// </summary>
    internal static JsonArray ListsLeftOpen(JsonArray steps, JsonObject? view)
    {
        var collapses = new JsonArray();
        if (view is null || (bool?)view["onTheApplication"] == false || ProtectedWindow(view)
            || view["controls"] is not JsonArray controls)
        {
            return collapses;
        }

        var opened = new List<JsonObject>();
        var popups = new List<JsonObject>();
        foreach (JsonObject step in steps.OfType<JsonObject>())
        {
            if ((string?)step["operation"] != "input.visible.click" || (bool?)step["ok"] != true
                || ComputerUseSuccessCheck.Fold((string?)step["label"]) is not { Length: > 0 })
            {
                continue;
            }

            if ((string?)step["manner"] == "open" || (string?)step["method"] == "expand")
            {
                opened.Add(step);
            }
            else if ((string?)step["manner"] == "menu" || (bool?)step["popupBorn"] == true)
            {
                popups.Add(step);
            }
        }

        foreach (JsonObject control in controls.OfType<JsonObject>())
        {
            string name = (string?)control["name"] ?? string.Empty;
            if (control["i"] is not JsonValue index || !index.TryGetValue(out int position))
            {
                continue;
            }

            string? manner = null;
            if ((string?)control["kind"] != "TreeItem"
                && ((string?)control["state"] ?? string.Empty).Split(' ').Contains("expanded", StringComparer.Ordinal)
                && TakeStepOf(opened, control, name, position))
            {
                manner = "collapse";
            }
            else if (TakeStepOf(popups, control, name, position))
            {
                manner = "dismiss";
            }

            if (manner is not null)
            {
                collapses.Add(new JsonObject { ["label"] = name, ["index"] = position, ["manner"] = manner });
            }
        }

        return collapses;
    }

    // Review 3 of palanca 6, finding 1: the step that acted on this control of the look, by the same name and the same
    // kind as its receipt read (a step with no kind in its receipt, by the index it was sent to); taken once.
    private static bool TakeStepOf(List<JsonObject> steps, JsonObject control, string name, int position)
    {
        string folded = ComputerUseSuccessCheck.Fold(name);
        string? kind = (string?)control["kind"];
        int found = steps.FindIndex(step =>
            ComputerUseSuccessCheck.Fold((string?)step["label"]) == folded
            && ((string?)step["kind"] is { Length: > 0 } stepKind
                ? string.Equals(stepKind, kind, StringComparison.Ordinal)
                : (int?)step["index"] == position));
        if (found < 0)
        {
            return false;
        }

        steps.RemoveAt(found);
        return true;
    }

    /// <summary>
    /// A mission that did not arrive closes, by each control's own ExpandCollapse and with no pointer or key, the lists
    /// it opened and left open (<see cref="ListsLeftOpen"/>): the font list Word showed open after a failed mission stays
    /// in the person's window otherwise. Each collapse is bound to the mission's window like any click, fits the
    /// catalog, and the worker hands the front back after it (its pattern acted); one the policy holds for a confirmation
    /// is left as it is, never asked. Not steps of the mission: the final never tells them, the trace counts them.
    /// </summary>
    private static async Task CollapseListsLeftOpenAsync(
        Context context,
        JsonObject state,
        JsonArray steps,
        JsonObject? lastView,
        string? application,
        string traceId,
        CancellationToken cancellationToken)
    {
        int sent = 0;
        int closed = 0;
        foreach (JsonObject arguments in ListsLeftOpen(steps, lastView).OfType<JsonObject>())
        {
            if (cancellationToken.IsCancellationRequested
                || !BindToMissionWindow("input.visible.click", arguments, lastView, state, application, steps)
                || !MindPlanBoundary.ArgumentsSatisfyExactSchema("input.visible.click", arguments))
            {
                continue;
            }

            PreparedOperation prepared = context.Registry.GetOrAdd(new RoutedOperation("input.visible.click", arguments));
            sent++;
            try
            {
                OperationResponse response = await context.Execute(prepared, ActionTimeout, cancellationToken).ConfigureAwait(true);
                if (response.Status == OperationStatuses.Completed && response.Verified)
                {
                    closed++;
                }
            }
            catch (Exception exception) when (exception is TimeoutException or IOException or InvalidOperationException
                or OperationCanceledException)
            {
            }
            finally
            {
                _ = context.MarkResolved(context.Registry, prepared);
            }
        }

        if (sent > 0)
        {
            state["collapsedOnFailure"] = closed;
            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.collapse", $"sent.{sent}.closed.{closed}");
        }
    }

    /// <summary>
    /// The gate a «none» names (code <c>app_gate</c>, arguments {evidence, gate, pressed?}): {kind, text, pressed?} when
    /// its text is on the view the decision was taken on and its kind is one the floor says (the keys of data
    /// «computerUse.appGate»: account, updating, missing, dialog); null otherwise, and the stop is then said as no step (v3 limits, M2). <c>pressed</c> is the control
    /// pressed on the gate to pass it without giving anything («Ahora no»), when one was: the final then never says
    /// nothing was pressed.
    /// </summary>
    internal static JsonObject? GateSeen(MindComputerUseStep decision, JsonObject? view)
    {
        if (decision.Operation != "none" || decision.Code != "app_gate" || view is null
            || (string?)decision.Arguments["evidence"] is not { Length: > 0 } text
            || (string?)decision.Arguments["gate"] is not { } kind
            || OperationFloor.ComputerUseData["appGate"]?[kind] is not JsonObject
            || !ComputerUseSuccessCheck.ViewContains(view, text))
        {
            return null;
        }

        JsonObject gate = new() { ["kind"] = kind, ["text"] = text };
        if ((string?)decision.Arguments["pressed"] is { Length: > 0 } pressed)
        {
            gate["pressed"] = pressed;
        }

        return gate;
    }

    /// <summary>
    /// The end line of a mission in the trace: reached, steps, time and model time, the encoder's time apart when there
    /// was any and it fits (lat-e5; each step's «computer_use.decide_time» line carries it too), then the stop code
    /// while the whole line fits the trace's label (a longer one would be written «invalid»); the code always has its
    /// own «computer_use.stop» line.
    /// </summary>
    internal static string EndTraceDetail(
        bool reached, int steps, long elapsedMs, long modelMs, string? errorCode, long encoderMs = 0)
    {
        string bare = $"reached.{(reached ? "true" : "false")}.steps.{steps}.ms.{elapsedMs}.model_ms.{modelMs}";
        string withEncoder = encoderMs > 0 ? $"{bare}.encoder_ms.{encoderMs}" : bare;
        // Review of lat-e5 (finding 4): 30 steps, 312 s, 104 s of model and 10 s of encoder made the counts alone 65
        // characters; then the encoder's time is left to the step lines.
        string counts = withEncoder.Length <= ShellTrace.MaximumLabelLength ? withEncoder : bare;
        string whole = $"{counts}.{ShellTrace.SanitizeLabel(errorCode ?? "ok")}";
        return whole.Length <= ShellTrace.MaximumLabelLength ? whole : counts;
    }

    /// <summary>
    /// A decision's time split in the model's and the encoder's (lat-e5, r13a: «model_ms» summed 728 s where the model
    /// took 188 s, the rest was the wait for a loading E5): the mind's own count of its encoder time, never more than
    /// the whole decision took.
    /// </summary>
    internal static (long ModelMs, long EncoderMs) SplitDecideTime(long decideMs, MindComputerUseStep? decision)
    {
        long whole = Math.Max(0, decideMs);
        long encoderMs = Math.Clamp(decision?.EncoderMs ?? 0, 0, whole);
        return (whole - encoderMs, encoderMs);
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
        // The confirmed act was just sent (goal v3 ventana-misión: what a window that comes later is measured against).
        ComputerUseMissionWindow.NoteAct(state, DateTimeOffset.UtcNow);
        RecordResponse(record, response);
        steps.Add(record);
        NoteTranslatedClick(state, record);
        // A confirmed search burst (its result named by choose) is said sub-act by sub-act.
        record = ExpandSearchBurst(steps, record);
        if (Kernel.Policy.RiskPolicy.WorldActOf(prepared.OperationName, prepared.Arguments) is not { } act)
        {
            return;
        }

        // Encargo VZ: the act the person confirmed is theirs for the rest of this mission (ExecuteAsync). A click, a
        // burst's result or Enter on a voice channel or a call that went through joined it (Revisión de V, H1).
        if (state["confirmedActs"] is not JsonArray acts)
        {
            state["confirmedActs"] = acts = new JsonArray();
        }

        acts.Add(act.Key);
        if (act.Joins && (bool?)record["ok"] == true)
        {
            state["joined"] = true;
        }
    }

    /// <summary>
    /// Encargo VZ (imp3d imp-dc-voz, Normal: «sí» to joining «Cotele!!!😎, Canal de voz, Choche», then the same mission
    /// pressed «Cotele!!!😎 (canal de voz), RED, …» and asked a second time). One step sent through the Core; when the
    /// Kernel asks for an act the person already confirmed in this mission (<see cref="Kernel.Policy.WorldAct.Key"/>:
    /// the same family and name), the step is sent again with the token the Kernel gave this very invocation. Any other
    /// act keeps its own question; in bypass the Kernel never asks.
    /// </summary>
    private static async Task<OperationResponse> ExecuteAsync(
        Context context, JsonObject state, PreparedOperation prepared, string traceId, CancellationToken cancellationToken)
    {
        OperationResponse response = await context.Execute(prepared, ActionTimeout, cancellationToken).ConfigureAwait(true);
        if (context.ExecuteConfirmed is { } confirmed
            && state["confirmedActs"] is JsonArray acts
            && Kernel.Policy.RiskPolicy.WorldActOf(prepared.OperationName, prepared.Arguments) is { } act
            && acts.Any(node => (string?)node == act.Key)
            && PendingOperationConfirmation.TryCreate(response, prepared, TimeProvider.System, out PendingOperationConfirmation? asked)
            && asked is not null)
        {
            ShellTraceSink.Record(ShellTraceScopes.Turn, traceId, "computer_use.confirmed_before", ShellTrace.SanitizeLabel(act.Family));
            response = await confirmed(prepared, asked.Token, ActionTimeout, cancellationToken).ConfigureAwait(true);
        }

        return response;
    }

    private static JsonObject Begin(
        JsonObject arguments, string objective, ComputerUseLabelTranslations? translations = null)
    {
        string goal = (string?)arguments["goal"] is { Length: > 0 } text ? text.Trim() : objective;
        string? application = (string?)arguments["application"];
        string? successCheck = (string?)arguments["successCheck"];
        int? requested = arguments["budgetSteps"] is JsonValue budgetValue && budgetValue.TryGetValue(out int asked)
            ? Math.Clamp(asked, 1, MaximumBudgetSteps)
            : null;
        var plan = new JsonArray();
        // Estabilización L (H7): a mission of one goal the mind marked (a declared limit, a device its place needs) comes
        // as that one marked step and keeps a single goal's budget and time; any other «steps» is a chain, however many.
        bool chained = arguments["steps"] is JsonArray { Count: > 0 } listed
            && !(listed.Count == 1
                && ((string?)listed[0]?["requires"] is { Length: > 0 } || (string?)listed[0]?["limit"] is { Length: > 0 }));
        if (arguments["steps"] is JsonArray { Count: > 0 } given)
        {
            // Contract «steps»: each sub-goal at most ten steps and thirty seconds;
            // the whole chain at most thirty steps and three minutes.
            foreach (JsonNode? node in given)
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
                    // Ronda 20b, revisión 2: the check of the whole form this sub-goal belongs to, for the mind.
                    ["formCheck"] = (string?)item["formCheck"],
                    // Estabilización L: the declared limit this sub-goal is, and the device its place needs.
                    ["limit"] = (string?)item["limit"],
                    ["requires"] = (string?)item["requires"],
                    ["budgetSteps"] = chained ? SubgoalBudgetSteps : requested ?? DefaultBudgetSteps,
                    ["timeMs"] = (long)(chained ? SubgoalTimeBudget : TimeBudget).TotalMilliseconds,
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
            // The request as the person said it: what names a window the mission may go to (ComputerUseMissionWindow).
            ["objective"] = objective,
            ["application"] = application,
            // The person named the window in front as the destination of a mission with no application.
            ["frontWindow"] = !chained && application is not { Length: > 0 } && (bool?)arguments["frontWindow"] == true,
            ["successCheck"] = successCheck,
            ["budgetSteps"] = chained ? requested ?? MaximumBudgetSteps : requested ?? DefaultBudgetSteps,
            ["chained"] = chained,
            ["subgoals"] = plan,
            ["startedUtc"] = DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
            ["steps"] = new JsonArray(),
            ["elapsedMs"] = 0L,
            ["modelMs"] = 0L,
            ["encoderMs"] = 0L,
        };
        // Ronda 21, destino por contenido: what the request names of the window where it happens, when it names no
        // application; the window that shows it is looked for before the first look (ComputerUseDestination).
        if (!chained && application is not { Length: > 0 } && ComputerUseDestination.ReferentOf(arguments) is { } referent)
        {
            state["referent"] = ComputerUseDestination.ToState(referent);
        }

        EnterSubgoal(state, 0, translations);
        return state;
    }

    /// <summary>
    /// Starts sub-goal <paramref name="index"/>: what the previous one saw is
    /// forgotten, and when it names another application the adopted window is
    /// too, so the mission looks for the new one (and opens it if it is not
    /// in front). The translations of its label that an earlier mission reached through are loaded (§4.4.1): a click
    /// on «Fecha y hora» proves «date and time» as the first did.
    /// </summary>
    internal static void EnterSubgoal(
        JsonObject state, int index, ComputerUseLabelTranslations? translations = null)
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
            state.Remove("family");
            ComputerUseMissionWindow.Untie(state);
        }

        foreach (string field in SubgoalFields)
        {
            state.Remove(field);
        }

        state["subgoal"] = index;
        state["subgoalStart"] = (state["steps"] as JsonArray)?.Count ?? 0;
        state["subgoalStartedUtc"] = DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture);
        state["subgoalStartMs"] = (long?)state["elapsedMs"] ?? 0;
        string goal = (string?)subgoal["goal"] ?? string.Empty;
        ArmConfirmedTranslations(translations, state, goal, index);
    }

    /// <summary>
    /// Whether a step may have changed the screen: verified, or failed after it pressed (its post-read did not hold,
    /// <c>effectUncertain</c>). Opening the application is no act on the way to a place, and a step refused before any
    /// press (a label not found, an act that would go round) did nothing. Twin of OperationFloor.PlaceSaid and the
    /// mind's cu_history._may_have_acted. Estabilización, encargo C: an opening that also opened a place of the
    /// application by its address («placeOpened») went there: the window was not «already» in it.
    /// </summary>
    internal static bool MayHaveActed(JsonObject step) =>
        ((string?)step["operation"] != "app.open" || MadeNewDocument(step) || (bool?)step["placeOpened"] == true)
        && ((bool?)step["ok"] == true || (bool?)step["effectUncertain"] == true);

    // Review of cu-v3-documento-nuevo (finding 7): an opening that made the new document asked for («crea un blank
    // workbook») is an act with its effect, seen made by the provider (OpenApplicationResult.NewDocument).
    internal static bool MadeNewDocument(JsonObject step) =>
        (string?)step["operation"] == "app.open" && (bool?)step["ok"] == true && (bool?)step["newDocument"] == true;

    // Records how a sub-goal ended, and settles the translations of its label (§4.4.1).
    private static void CloseSubgoal(
        Context context, JsonObject state, JsonObject subgoal, JsonArray steps, int start, bool reached, string? satisfiedBy)
    {
        JsonArray own = SubgoalSteps(steps, start);
        subgoal["reached"] = reached;
        subgoal["stepCount"] = own.Count;
        subgoal["satisfiedBy"] = satisfiedBy;
        SettleTranslations(context.LabelTranslations, state, (string?)subgoal["successCheck"], reached, satisfiedBy);
    }

    // Why an act failed that says the person is using the PC, not that the screen or the step was wrong: the
    // foreground lease found no pause of theirs within its wait, or their input arrived during the burst.
    internal static readonly IReadOnlySet<string> PersonInputStops = new HashSet<string>(StringComparer.Ordinal)
    {
        "input_user_not_paused", "input_user_interrupted",
    };

    // Why a sub-goal stopped that says the screen did not answer (it stopped changing, showed no step, did not show the
    // evidence, went round, or the budget ran out on it).
    private static readonly HashSet<string> ScreenStops = new(StringComparer.Ordinal)
    {
        "computer_use_surface_unchanged", "computer_use_no_step_visible", "computer_use_click_without_effect",
        "computer_use_evidence_not_visible", "computer_use_repeated_step", "computer_use_budget_exhausted", "computer_use_time_exhausted",
        "computer_use_place_not_found", "computer_use_app_not_shown", "computer_use_window_not_shown",
    };

    // The place's name as a step of the mission read it on screen («Wi-Fi»), or as the person said it.
    private static string SpelledAsSeen(string asked, JsonArray steps)
    {
        string folded = ComputerUseSuccessCheck.Fold(asked);
        return steps.OfType<JsonObject>()
            .Select(step => (string?)step["name"])
            .FirstOrDefault(name => name is { Length: > 0 } && ComputerUseSuccessCheck.Fold(name) == folded) ?? asked;
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

    /// <summary>
    /// Where a step came from, for the trace: the mind's own word
    /// (<c>model</c>, <c>rule</c>, <c>semantic</c>), with <c>.e5_cold</c> or <c>.e5_failed</c> when the step asked an
    /// encoder that was still loading or did not answer (pasada v3 05:40: every step read «model» and a cold E5 that
    /// left v3-14 literal could not be told from a literal choice). A mind that says nothing is «model», as before.
    /// </summary>
    internal static string DecisionSource(MindComputerUseStep decision)
    {
        string source = decision.Source is { Length: > 0 } said ? said : "model";
        return decision.Encoder is "cold" or "failed" ? $"{source}.e5_{decision.Encoder}" : source;
    }

    private static double Area(JsonObject rect) => Math.Max(Number(rect["w"]), 0) * Math.Max(Number(rect["h"]), 0);

    // A rectangle read from the provider holds JSON numbers; one built in memory may hold ints.
    private static double Number(JsonNode? node)
    {
        if (node is not JsonValue value)
        {
            return 0;
        }

        if (value.TryGetValue(out double real))
        {
            return real;
        }

        return value.TryGetValue(out int whole) ? whole : 0;
    }

    private static TimeSpan Max(TimeSpan first, TimeSpan second) => first > second ? first : second;

    /// <summary>
    /// Ronda 21 (pasada r18 v3-26): whether the step just taken restarts its sub-goal's clock: an opening that went
    /// well, put by the engine (source «rule», never the model's) as the sub-goal's first step,
    /// in a sub-goal whose goal is not opening (data «evidence.openGoal»): that one keeps the opening in its time.
    /// </summary>
    internal static bool RestartsSubgoalClock(string operation, string? source, bool ok, int subgoalSteps, string? goal) =>
        ok && operation == "app.open" && source == "rule" && subgoalSteps == 1
        && !Regex.IsMatch(
            ComputerUseSuccessCheck.Fold(goal).Trim(), (string)OperationFloor.EvidenceRules["openGoal"]!, RegexOptions.CultureInvariant);

    // Estabilización L: the decision code of a step that stops on a limit («limit:long_list») and the stops of the
    // limits («computer_use_limit_<id>», a device the computer does not have among them); the floor says each (mind's
    // cu_finals.limit_final, data «computerUse.limits»).
    internal const string LimitCode = "limit:";
    // Encargo IMP2: the mind's word for a search whose results are still being drawn, and the wait before looking again.
    internal const string SearchPending = "search_pending";
    internal static readonly TimeSpan SearchResultsWait = TimeSpan.FromMilliseconds(600);
    internal const string LimitStop = "computer_use_limit_";
    internal const string DeviceStop = LimitStop + "device";
    internal const string NoStepVisible = "computer_use_no_step_visible";

    /// <summary>
    /// The stop a «none» of the mind ends the mission with, by its code: the causes said as such, and any other (the
    /// model's own «none», a refusal it had its retry for) as «no vi un control». Encargo V1: one table for the stop and for
    /// whether a screen torn down by the act is awaited first (<see cref="RedrawnAfterActAsync"/>).
    /// </summary>
    internal static string NoneStop(string code, bool gateSeen) => code switch
    {
        "no_document_open" => "computer_use_no_document_open",
        "search_focus_unproven" => "computer_use_search_focus_unproven",
        // Ronda 24b (banco r23 c6): the message box clicked did not take the keyboard, still in the search; or the text
        // sat in the search and an Enter there would send nothing.
        "field_not_focused" => "computer_use_field_not_focused",
        // Estabilización y5 (banco h1): the control was seen and pressed and the window stayed where it was (a tree node
        // chosen whose folder did not open); never «no vi el control».
        "click_without_effect" => "computer_use_click_without_effect",
        "text_not_in_composer" => "computer_use_text_not_in_composer",
        "window_protected" => "computer_use_window_protected",
        // Ronda 20b (pasada r18 t-long-3): a form whose fields the window changed again after they were set is left
        // unaccepted, said as such.
        "linked_fields" => "computer_use_linked_fields",
        "app_gate" when gateSeen => "computer_use_app_gate",
        // Review of cu-v3-abrir-archivo (finding 4): a file not opened stops with its cause («file_not_opened:file_ambiguous»),
        // which the final says.
        _ when code.StartsWith(FileNotOpened + ":", StringComparison.Ordinal) => "computer_use_file_not_opened",
        _ => NoStepVisible,
    };

    /// <summary>
    /// Estabilización L: whether the computer lacks <paramref name="device"/> (data «computerUse.limits.devices»): its
    /// read operation answered one of the codes that say it is absent. Any other answer, a timeout or a device the data
    /// does not know is no absence, and the sub-goal is tried as before.
    /// </summary>
    internal static async Task<bool> DeviceAbsentAsync(Context context, string device, CancellationToken cancellationToken)
    {
        if (OperationFloor.ComputerUseData["limits"]?["devices"]?[device] is not JsonObject entry
            || (string?)entry["read"] is not { Length: > 0 } read
            || entry["absent"] is not JsonArray absent)
        {
            return false;
        }

        // Encargo H2: a read that needs its arguments (the brightness's «setting») takes them from the data.
        JsonObject arguments = entry["readArguments"]?.DeepClone() as JsonObject ?? new JsonObject();
        PreparedOperation prepared = context.Registry.GetOrAdd(new RoutedOperation(read, arguments));
        try
        {
            OperationResponse response = await context.Execute(prepared, ViewTimeout, cancellationToken).ConfigureAwait(true);
            return response.Status != OperationStatuses.Completed
                && response.ErrorCode is { Length: > 0 } code
                && absent.Any(node => string.Equals((string?)node, code, StringComparison.Ordinal));
        }
        catch (Exception exception) when (exception is TimeoutException or IOException or InvalidOperationException)
        {
            return false;
        }
        finally
        {
            _ = context.MarkResolved(context.Registry, prepared);
        }
    }
}
