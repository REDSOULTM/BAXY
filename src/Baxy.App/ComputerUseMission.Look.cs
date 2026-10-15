using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Operations;

namespace Baxy.App;

// Looking at the screen: the look after an act, its retries, a window tied again, a stale look kept.
internal static partial class ComputerUseMission
{
    /// <summary>
    /// Whether the next look must carry the OCR text (≈1 s): the first look of
    /// a sub-goal, a window drawn without an accessible tree (≤ 1 control), a
    /// success check that reads written text (text:, page:), or a goal whose
    /// target is not among the controls. Otherwise the controls are enough.
    /// </summary>
    internal static bool NeedsText(string goal, string? application, string? successCheck, JsonObject? previousView)
    {
        // Ronda 23 (v3-46): a question is answered by what the window writes; its look reads the text too.
        if (previousView is null || ActionableCount(previousView) <= 1 || CarriesQuestion(goal))
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

    /// <summary>
    /// fable/cu-v3-reintento-pausa: after an act that pressed and whose post-read the person's input cut short (the
    /// person's input can end it before its first look), whether the mission's window shows the act's effect, looked at
    /// <see cref="PersonEffectLooks"/> times, <see cref="PersonEffectLookInterval"/> apart. True when a look no longer
    /// reads as the view the act was decided on and the window is behind the person's (their keys went into their own
    /// window, never into it); false when every look still reads as it (the act did nothing: it may be tried again);
    /// null when the window cannot be read, or changed while it holds the front or without saying where it is (the
    /// change could be the person's): the act is not pressed again and the cause is said. Review of the branch: a
    /// window without an accessible tree (≤ 1 control) reads only as its text, which does not show what a press there
    /// often changes alone (a toggle, a play button's icon, a check, a selection): its text unchanged says nothing of
    /// the press, and pressing again would undo it; null as well.
    /// </summary>
    private static async Task<bool?> EffectShownAfterPersonStopAsync(
        Context context,
        JsonObject state,
        string? application,
        bool includeText,
        string decidedOn,
        CancellationToken cancellationToken)
    {
        bool stateShown = false;
        for (int look = 0; look < PersonEffectLooks; look++)
        {
            await context.Delay(PersonEffectLookInterval, cancellationToken).ConfigureAwait(true);
            JsonObject? view = await LookAsync(context, state, application, includeText, cancellationToken).ConfigureAwait(true);
            if (view is null)
            {
                return null;
            }

            if (!string.Equals(ViewSignature(view), decidedOn, StringComparison.Ordinal))
            {
                return (bool?)view["window"]?["foreground"] == false ? true : null;
            }

            stateShown = ControlCount(view) > 1;
        }

        return stateShown ? false : null;
    }

    private static async Task<JsonObject?> LookAsync(
        Context context,
        JsonObject state,
        string? application,
        bool includeText,
        CancellationToken cancellationToken,
        string? successCheck = null)
    {
        JsonObject? view = await LookOnceAsync(context, state, application, includeText, successCheck, cancellationToken)
            .ConfigureAwait(true);
        // Pasada r15b (v3-16, v3-43, v3-01): a look that is not ready yet is read again, ReadyInterval apart, at most
        // ReadyLooks times (about 1.2 s), before anything is judged or decided on it: a window that shows a loading
        // indicator (an image editor's «Ocupado», a page's «Cargando»: the check closed v3-43 on the page still loading
        // and its plan was never read), or the first look at a window just born, read with its text, where none came
        // (the OCR of PowerPoint's new presentation read nothing on its first look, v3-01 and v3-04).
        // Review of fable/cu-v3-carga-preguntas (finding 5): a window whose loading indicator outlived the reads again
        // once (a bar that never goes away) is not read again on every later look of the mission: the window is
        // remembered (state «loadingPersists», by its title, as «pageNotExposed» is) while it keeps showing it.
        // Ronda 20b (v3-43): a bar with a value that did not move through every read again stands still: it is furniture
        // of the window (the Explorer's «Cargando» at 0), remembered by the window's process with its values, so a later
        // look of that window showing the same bar takes it as furniture at once. A bar that moves, or exposes no value
        // (indeterminate), is loading as before. «loadingPersists» is kept by the window's process too, not its title.
        if (view is not null && ShowsLoading(view)
            && string.Equals(WindowKey(view) + "\n" + LoadingBarsSignature(view), (string?)state["loadingStill"], StringComparison.Ordinal))
        {
            MarkLoadingBarsStill(view);
        }

        bool loadingPaid = view is not null && ShowsLoading(view)
            && string.Equals(WindowKey(view), (string?)state["loadingPersists"], StringComparison.Ordinal);
        bool blankBorn = view is not null && includeText && (bool?)view["window"]?["born"] == true && TextCount(view) == 0;
        string? barsSeen = view is not null && ShowsLoading(view) && !loadingPaid ? LoadingBarsSignature(view) : null;
        bool barsMoved = false;
        int loadingReads = 0;
        for (int again = 1; view is not null && again <= ReadyLooks; again++)
        {
            string? why = ShowsLoading(view) && !loadingPaid ? "loading"
                : blankBorn && TextCount(view) == 0 ? "blank_born" : null;
            if (why is null)
            {
                break;
            }

            ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, "computer_use.view_unready",
                $"{why}.look.{again.ToString(CultureInfo.InvariantCulture)}");
            await context.Delay(ReadyInterval, cancellationToken).ConfigureAwait(true);
            view = await ReadViewAsync(context, state, application, includeText, cancellationToken).ConfigureAwait(true) ?? view;
            if (why == "loading")
            {
                loadingReads++;
                string? barsNow = LoadingBarsSignature(view);
                barsMoved |= barsNow is null || !string.Equals(barsNow, barsSeen, StringComparison.Ordinal);
                barsSeen = barsNow;
            }
        }

        if (view is not null && ShowsLoading(view) && loadingReads == ReadyLooks && !barsMoved && barsSeen is not null)
        {
            ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, "computer_use.view_unready", "loading.still");
            state["loadingStill"] = WindowKey(view) + "\n" + barsSeen;
            MarkLoadingBarsStill(view);
        }

        if (view is not null && ShowsLoading(view))
        {
            state["loadingPersists"] = WindowKey(view);
        }
        else
        {
            state.Remove("loadingPersists");
        }

        return view;
    }

    /// <summary>How many times a look that is not ready yet is read again (<see cref="LookAsync"/>).</summary>
    internal const int ReadyLooks = 3;

    /// <summary>The wait before each read again of a look that is not ready yet.</summary>
    internal static readonly TimeSpan ReadyInterval = TimeSpan.FromMilliseconds(400);

    private static async Task<JsonObject?> LookOnceAsync(
        Context context,
        JsonObject state,
        string? application,
        bool includeText,
        string? successCheck,
        CancellationToken cancellationToken)
    {
        // Ronda 21 (pasada r18 v3-63): the last good look of the application's window while waiting for it after an
        // opening, and whether the read after it failed: a good look is never thrown away for a later read that did not
        // come (it is handed on marked stale, IsStale).
        JsonObject? lastGood = null;
        bool lastReadFailed = false;
        if ((bool?)state["awaitWindow"] == true)
        {
            // Right after app.open: look until a view shows the application's window started, bounded.
            state.Remove("awaitWindow");
            var watch = Stopwatch.StartNew();
            // The time the loop waited on purpose: the elapsed time is never less than it (it is what passes when the
            // waits are not real).
            TimeSpan paced = TimeSpan.Zero;
            // Ronda 26 (banco c24b: 39 of 55 openings read the window without text and at once again with it): one read
            // per look, with the text when the look asked for it or the window showed nothing to act on (CEF, a splash, a
            // shell of panes: judged by what is written on it; a window with a tree, by its tree: StartingLook).
            bool readWithText = includeText;
            string? previousTree = null;
            string? previousBars = null;
            // Encargo CS: whether the last look of the application was its progress window (ProgressSplash).
            bool splashLast = false;
            while (true)
            {
                bool cold = (bool?)state["openedCold"] == true;
                bool settlesByTree = false;
                splashLast = false;
                JsonObject? seen = await ReadViewAsync(context, state, application, readWithText, cancellationToken, starting: cold)
                    .ConfigureAwait(true);
                NoteFrontReturned(state, seen);
                lastReadFailed = seen is null;
                if (seen is null && WindowClosed(state))
                {
                    // Ronda 19b (r15b v3-34: ten looks of 2 s on a closed window until StartWait): a window that closed
                    // and could not be tied again does not come back by waiting for it.
                    state.Remove("openedCold");
                    state.Remove("startingLook");
                    state.Remove("startingLookAt");
                    return null;
                }

                if (seen is not null)
                {
                    // The family of the application's window is learned on its first look (v3 point 1).
                    AdoptWindow(state, application, seen);
                    ComputerUseMissionWindow.Tie(
                        state, application, seen, ShowsTheApplication(state, seen), state["steps"] as JsonArray ?? []);
                }

                if (seen is not null && ShowsTheApplication(state, seen))
                {
                    int actionable = ActionableCount(seen);
                    // Review 1 of ronda 21 (finding 1): only an interface that is up is kept to be handed on; a splash
                    // or a loading view is never handed on stale (a later good look replaces it, a loading one clears it).
                    lastGood = KeptWhileOpening(seen) ? seen : null;
                    readWithText = includeText || actionable <= 1;
                    string tree = OpeningTree(seen);
                    string? bars = LoadingBarsSignature(seen);
                    // Encargo CS (banco fz1 s12): a progress window of the application just started (an updater with
                    // only «Cancelar») is loading whatever its bar is named and whether it moves, up to ColdStartWait:
                    // it is never handed to the model, whose «open» on its only control cancelled Steam's start.
                    splashLast = cold && ProgressSplash(seen, successCheck, application);
                    if (splashLast)
                    {
                        state[ProgressSplashField] = true;
                    }

                    bool stillLoading = cold
                        && (splashLast || LoadingWhileStarting(seen, tree, previousTree, bars, previousBars, Max(watch.Elapsed, paced)));
                    settlesByTree = !stillLoading && actionable >= InterfaceUp;
                    bool started = !cold
                        || (!stillLoading
                            && (InterfaceUpAndSettled(seen, previousTree)
                                || (actionable > 1 && TargetActionable(successCheck, application, seen))
                                || !StillStarting(state, seen, Max(watch.Elapsed, paced))));
                    previousTree = tree;
                    previousBars = bars;
                    if (started)
                    {
                        // Ronda 20b, palanca 8: how long the opening waited; a «none» on this look showing only the
                        // window's frame is looked at again up to StartWait (NotShownYetAsync).
                        state["openingWaitedMs"] = (long)Max(watch.Elapsed, paced).TotalMilliseconds;
                        if (state.Remove(ProgressSplashField))
                        {
                            // Encargo CS: the wait for an application's own progress window is not the sub-goal's work
                            // (as the opening itself, clock_after_opening): its clock starts once the window is up.
                            state["subgoalStartMs"] = ((long?)state["subgoalStartMs"] ?? 0) + (long)Max(watch.Elapsed, paced).TotalMilliseconds;
                        }

                        state.Remove("openedCold");
                        state.Remove("startingLook");
                        state.Remove("startingLookAt");
                        return seen;
                    }
                }

                TimeSpan elapsed = Max(watch.Elapsed, paced);
                if (elapsed >= ((bool?)state["openedCold"] == true ? StartCap(state) : WindowWait))
                {
                    state.Remove("startingLook");
                    state.Remove("startingLookAt");
                    if (splashLast)
                    {
                        // Encargo CS: still its progress window at ColdStartWait: the mission says the application did
                        // not finish showing itself (computer_use_app_not_shown) and presses nothing in it.
                        state.Remove("openedCold");
                        state.Remove(ProgressSplashField);
                        state[StillStartingField] = true;
                        return null;
                    }

                    if (lastReadFailed && lastGood is not null && !WindowClosed(state))
                    {
                        // The wait ran out on a read that failed after a good one: that one is not read a third time.
                        return Stale(lastGood, "opening.timed_out");
                    }

                    break;
                }

                // The next look comes when the one it is compared with is StartSettle old (a look before that can only
                // change the reference or be too close to it), at least Settle later. r29 (bancos r27, cd y c24b: 40
                // openings showed their interface whole at the first look and waited StartSettle for a second one that
                // read the same, or one control apart, in all 40): an interface that is up and not loading is judged by
                // its tree against the next look (InterfaceUpAndSettled), whatever the time between them: Settle later.
                TimeSpan left = settlesByTree || (long?)state["startingLookAt"] is not long at
                    ? Settle : StartSettle - (elapsed - TimeSpan.FromMilliseconds(at));
                // Encargo CS: a progress window is looked at as a window that is waited for once its splash closed
                // (RetiePause), not read with its text every Settle for up to a minute while its application updates.
                TimeSpan pause = splashLast ? RetiePause : left > Settle ? left : Settle;
                await context.Delay(pause, cancellationToken).ConfigureAwait(true);
                paced += pause;
            }
        }

        if ((string?)state["awaitTitleChange"] is { } titleBefore)
        {
            // Right after an act that creates a document from a start page: look without OCR until the window's
            // title changes (the new document's window), bounded; then read it as asked.
            state.Remove("awaitTitleChange");
            var watch = Stopwatch.StartNew();
            while (watch.Elapsed < TitleChangeWait)
            {
                await context.Delay(Settle, cancellationToken).ConfigureAwait(true);
                JsonObject? early = await ReadViewAsync(context, state, application, includeText: false, cancellationToken)
                    .ConfigureAwait(true);
                if ((string?)early?["window"]?["title"] is { Length: > 0 } titleNow
                    && !string.Equals(titleNow, titleBefore, StringComparison.Ordinal))
                {
                    break;
                }
            }
        }

        JsonObject? view = await ReadViewAsync(context, state, application, includeText, cancellationToken).ConfigureAwait(true);
        if (view is null && lastGood is not null && !WindowClosed(state))
        {
            return Stale(lastGood, "opening.reread_failed");
        }

        // A web page still loading shows only the browser's frame (measured on Opera right after Enter: the tab
        // strip's search was taken for the page's): the look is repeated, bounded, until the page is exposed. A page
        // that did not come once is not waited for again while the title stays the same.
        string? title = (string?)view?["window"]?["title"];
        if (view is null || !PageNotExposed(view) || string.Equals(title, (string?)state["pageNotExposed"], StringComparison.Ordinal))
        {
            return view;
        }

        for (int looks = 0; looks < PageLooks && PageNotExposed(view); looks++)
        {
            await context.Delay(PageLookInterval, cancellationToken).ConfigureAwait(true);
            view = await ReadViewAsync(context, state, application, includeText, cancellationToken).ConfigureAwait(true) ?? view;
        }

        if (PageNotExposed(view))
        {
            state["pageNotExposed"] = (string?)view["window"]?["title"];
        }

        return view;
    }

    internal const int PageLooks = 6;

    // How many controls a look lists at most (the worker lists the actionable ones first, in the tree's order): a look
    // that reached it does not cover the whole window.
    internal const int ViewControlLimit = VisibleViewNumbering.Cap;
    internal static readonly TimeSpan PageLookInterval = TimeSpan.FromMilliseconds(400);

    /// <summary>
    /// Ronda 20b, palanca 8: a look showed only the window's frame and the model saw no step. The window is looked at
    /// again every <see cref="PageLookInterval"/>: after the opening, while the opening's wait and these looks stay
    /// within <see cref="StartWait"/>; otherwise (a dialog the provider read as frame alone), <see cref="PageLooks"/>
    /// times. At least one look more. True as soon as a look shows more than the frame. Once per opening or act.
    /// </summary>
    internal static async Task<bool> NotShownYetAsync(
        Context context, JsonObject state, string? application, CancellationToken cancellationToken)
    {
        TimeSpan waited;
        TimeSpan limit;
        if ((long?)state["openingWaitedMs"] is long waitedMs)
        {
            state.Remove("openingWaitedMs");
            waited = TimeSpan.FromMilliseconds(waitedMs);
            limit = StartWait;
        }
        else
        {
            waited = TimeSpan.Zero;
            limit = PageLookInterval * PageLooks;
        }

        do
        {
            await context.Delay(PageLookInterval, cancellationToken).ConfigureAwait(true);
            waited += PageLookInterval;
            JsonObject? view = await ReadViewAsync(context, state, application, includeText: true, cancellationToken)
                .ConfigureAwait(true);
            if (view is not null && !ShowsOnlyTheFrame(view))
            {
                return true;
            }
        }
        while (waited < limit);

        return false;
    }

    private static async Task<bool> RedrawnAfterActAsync(
        Context context,
        JsonObject state,
        JsonArray steps,
        int start,
        string? application,
        JsonObject seen,
        string seenSignature,
        CancellationToken cancellationToken)
    {
        if (steps.Count <= start || steps[^1] is not JsonObject act
            || (bool?)act["ok"] != true || (bool?)act["changed"] != true
            || (int?)state["redrawnAfterStep"] == steps.Count
            || ControlCount(seen) >= ((int?)state["actFromControls"] ?? 0))
        {
            return false;
        }

        state["redrawnAfterStep"] = steps.Count;
        // The signature of a window without an accessible tree is its text: it is read the same way here.
        bool includeText = ControlCount(seen) <= 1;
        string previous = seenSignature;
        bool changed = false;
        for (int looks = 0; looks < PageLooks; looks++)
        {
            await context.Delay(PageLookInterval, cancellationToken).ConfigureAwait(true);
            JsonObject? view = await ReadViewAsync(context, state, application, includeText, cancellationToken).ConfigureAwait(true);
            if (view is null)
            {
                break;
            }

            string signature = ViewSignature(view);
            if (string.Equals(signature, previous, StringComparison.Ordinal))
            {
                if (changed)
                {
                    break;
                }

                continue;
            }

            changed = true;
            previous = signature;
        }

        return changed;
    }

    private static bool ShowsTheApplication(JsonObject state, JsonObject view) =>
        view["window"] is JsonObject window
        && ((bool?)window["requested"] == true || OfTheMissionFamily(state, window));

    /// <summary>Ronda 21: the goal's words of the step the mind just decided, kept for the sub-goal's next looks; a step
    /// that brings none (a rule) leaves the last ones.</summary>
    internal static void NoteViewWanted(JsonObject state, MindComputerUseStep decision)
    {
        if (decision.Wanted is { Count: > 0 } wanted)
        {
            state[ViewWantedField] = wanted.DeepClone();
        }
    }

    // Encargo IMP3: the state's mark for the one look that keeps the last entries of the window's tree.
    internal const string TailLookField = "tailLook";

    // Encargo IMP4: the state's mark for the one look that reads the written lines with their places.
    internal const string LinesLookField = "linesLook";

    /// <summary>
    /// Encargo IMP4 (imp3 imp-wa-leer: «Llegué a «musica», pero no pude leer…»: a chat client whose accessible tree holds
    /// no message text, and a screen copy of it behind another window that read the other window): a mission reached that
    /// answers a question, in an application whose data declare where it draws its conversation (app_places
    /// «conversation»), reads the window's own drawing once with each line's place; the mind tells the last bubble not
    /// the person's own from them (semantic.chat_lines), or says it could not read one.
    /// </summary>
    internal static async Task NoteTheChatLinesAsync(
        Context context, JsonObject state, JsonObject lastView, string? application, CancellationToken cancellationToken)
    {
        if (!ApplicationPlaces.HasConversation(application))
        {
            return;
        }

        state[LinesLookField] = true;
        JsonObject? read;
        try
        {
            read = await ReadViewAsync(context, state, application, includeText: true, cancellationToken).ConfigureAwait(true);
        }
        finally
        {
            state.Remove(LinesLookField);
        }

        if (read?["textLines"] is JsonArray lines)
        {
            lastView["chatLines"] = lines.DeepClone();
        }
    }

    /// <summary>
    /// Encargo IMP3 (imp2 imp-dc-leer: «Llegué a «ron92», pero no pude leer…», the chat open, 169 controls and its messages
    /// past the first 60 the look keeps): a mission reached that answers a question, on a look cut short, reads the window
    /// once more keeping the last entries of its tree, where a conversation draws its newest messages; their named
    /// groups («autor , texto , hora») are what the final reads (<see cref="ScreenExcerpt"/>). Nothing else changes.
    /// </summary>
    internal static async Task NoteTheTailAsync(
        Context context, JsonObject state, JsonObject lastView, string? application, CancellationToken cancellationToken)
    {
        if (ControlCount(lastView) < ViewControlLimit || (int?)lastView["controlCount"] is not int total
            || total <= ControlCount(lastView))
        {
            return;
        }

        state[TailLookField] = true;
        JsonObject? tail;
        try
        {
            tail = await ReadViewAsync(context, state, application, includeText: false, cancellationToken).ConfigureAwait(true);
        }
        finally
        {
            state.Remove(TailLookField);
        }

        if (tail?["controls"] is JsonArray controls)
        {
            lastView["tailGroups"] = new JsonArray([.. controls.OfType<JsonObject>()
                .Where(control => (string?)control["kind"] == "Group" && ((string?)control["name"] ?? string.Empty).Length > 0)
                .Select(control => (JsonNode?)JsonValue.Create((string?)control["name"]))]);
        }
    }

    /// <summary>The look's first arguments: the text when asked, the view's bound and, within a sub-goal the mind
    /// already ranked, its goal's words («wanted»).</summary>
    internal static JsonObject LookArguments(JsonObject state, bool includeText)
    {
        var arguments = new JsonObject { ["includeText"] = includeText, ["limit"] = ViewControlLimit };
        if ((bool?)state[TailLookField] == true)
        {
            // Encargo IMP3: the look that keeps the tree's last entries, without the goal's words.
            arguments["tail"] = true;
            return arguments;
        }

        if ((bool?)state[LinesLookField] == true)
        {
            // Encargo IMP4: the look that reads the window's own drawing with each line's place.
            arguments["lines"] = true;
            arguments["includeText"] = true;
            return arguments;
        }

        if (state[ViewWantedField] is JsonArray { Count: > 0 } wanted)
        {
            arguments["wanted"] = wanted.DeepClone();
        }

        return arguments;
    }

    private static async Task<JsonObject?> ReadViewAsync(
        Context context,
        JsonObject state,
        string? application,
        bool includeText,
        CancellationToken cancellationToken,
        bool starting = false)
    {
        var arguments = LookArguments(state, includeText);
        if (starting)
        {
            // The application opened cold is starting: a front it takes by itself goes back to the person (v3 point 1).
            arguments["starting"] = true;
        }

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
            // Ronda 26 (banco c24b: 54 first looks of 1.2 s read the person's window before an opening already decided):
            // until a window of the application was read, a look says only who is in front while it has none (no tree
            // nor text of a window that is not the mission's), unless that window was to be decided on.
            if ((bool?)state[ViewReadField] != true && (bool?)state[FrontLookedWholeField] != true)
            {
                arguments["identityIfAbsent"] = true;
            }
        }

        if ((string?)state["waitForLabel"] is { Length: > 0 } waited)
        {
            arguments["waitForLabel"] = waited;
            state.Remove("waitForLabel");
        }

        // Goal v3 ventana-misión: a window that came during the mission (the look says so, or it is none of the windows
        // the mission is tied to) is kept as one of its windows or refused, and a refused one is never read again: the
        // look is taken anew, bounded. The judge and the acts only ever see the mission's windows.
        state.Remove(WindowClosedField);
        state.Remove(ViewFailureField);
        if ((bool?)state[WindowLostField] == true)
        {
            // Review of ronda 19b: the mission's window closed and no window was its own again; no later look reads
            // whatever the process or the front shows instead.
            state[WindowClosedField] = true;
            return null;
        }

        // Review 2 of ronda 21 (objective e, v3-34): how long the look after tying again waited, on purpose and in all,
        // for a window of the application that the mission started.
        Stopwatch? retieWatch = null;
        TimeSpan retiePaced = TimeSpan.Zero;
        // Encargo W: the owner of a window that does not hold the keyboard is looked at once per look.
        bool ownerLooked = false;
        for (int refused = 0; ; refused++)
        {
            arguments.Remove("windows");
            arguments.Remove("known");
            ComputerUseMissionWindow.AddLookArguments(state, arguments);
            (JsonObject? view, string? failure) = await ReadOneViewAsync(context, arguments, cancellationToken).ConfigureAwait(false);
            if (view is null)
            {
                state[ViewFailureField] = failure;
            }
            else
            {
                state.Remove(ViewFailureField);
            }

            if (view is not null && (application is null || (bool?)view["window"]?["requested"] == true))
            {
                // A window of the mission read well (never the person's window in front before an opening).
                state[ViewReadField] = true;
            }

            if (view is null && string.Equals(failure, MissionWindowClosed, StringComparison.Ordinal))
            {
                // Ronda 19b (r15b v3-34, v3-35): every window the mission is tied to closed (the first window of an
                // application it just started gave way to another). Tied again once, by a look of the application
                // that names no window; otherwise the look says the window closed, and nobody waits on it again.
                bool retied = ComputerUseMissionWindow.Retie(state, state["steps"] as JsonArray ?? []);
                ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, "computer_use.window",
                    retied ? "closed.retie" : "closed.stop");
                if (retied)
                {
                    continue;
                }

                state[WindowClosedField] = true;
                return null;
            }

            if (ComputerUseMissionWindow.TakeRetieLook(state))
            {
                // Review of ronda 19b: the look that names no window may read the person's window of the same process
                // (refused before), one titled like the application, or the window in front. Judged as a born window:
                // kept, it ties the mission again; else the mission's window closed, and the person's is never shown.
                JsonArray retieSteps = state["steps"] as JsonArray ?? [];
                string retieWhy = "no_view";
                bool kept = view is not null && ComputerUseMissionWindow.KeepsRetied(
                    state, view, ShowsTheApplication(state, view), retieSteps, DateTimeOffset.UtcNow, out retieWhy);
                retieWatch ??= Stopwatch.StartNew();
                if (!kept && RetieMayWait(view, retieWhy) && Max(retieWatch.Elapsed, retiePaced) < StartCap(state))
                {
                    // Review 2 of ronda 21 (objective e, v3-34): the application the mission started showed no window
                    // of its own yet (its splash closed before its window came), so the provider read another program's
                    // window in front, or none. That look is never shown nor kept: the application's window is waited
                    // for, bounded by StartWait, and looked for again naming no window. The person's own window (one
                    // the mission refused, or one they work in) still stops the mission at once.
                    ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, "computer_use.window", $"retie.wait.{retieWhy}");
                    ComputerUseMissionWindow.LookAgainForRetie(state);
                    await context.Delay(RetiePause, cancellationToken).ConfigureAwait(false);
                    retiePaced += RetiePause;
                    continue;
                }

                ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, "computer_use.window",
                    $"retie.{(kept ? "kept" : "refused")}.{retieWhy}");
                if (!kept)
                {
                    state[WindowLostField] = true;
                    state[WindowClosedField] = true;
                    return null;
                }

                ComputerUseMissionWindow.TieAgain(state, view!, retieWhy, retieSteps);
                ComputerUseMissionWindow.NoteItems(state, view);
                return view;
            }

            if (view is not null && !ownerLooked
                && ComputerUseMissionWindow.OwnerMayHoldTheKeyboard(state, view) is long keyboardOwner
                && ComputerUseMissionWindow.Root(view) is long floating)
            {
                // Encargo W (t-scroll-4): a pop-up the mission's window owns, in front, with the keyboard on none of its
                // controls (the suggestions under the address bar Ctrl+L focused). Its owner is looked at: when the
                // keyboard is there, the owner is the look, and the pop-up is neither kept nor refused. Otherwise the
                // pop-up is read again (the provider's last view, what a click by index acts on, is now the owner's)
                // and judged as before: kept when it came of the mission's act.
                ownerLooked = true;
                (JsonObject? ownerView, _) = await ReadOneViewAsync(
                        context, ComputerUseMissionWindow.OwnerLookArguments(state, arguments, keyboardOwner, floating), cancellationToken)
                    .ConfigureAwait(false);
                bool onOwner = ownerView is not null && (bool?)ownerView["window"]?["born"] != true
                    && ComputerUseMissionWindow.Root(ownerView) == keyboardOwner && ComputerUseMissionWindow.HoldsTheKeyboard(ownerView);
                ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, "computer_use.window",
                    onOwner ? "owner.keyboard" : "owner.no_keyboard");
                if (onOwner)
                {
                    ComputerUseMissionWindow.NoteItems(state, ownerView);
                    return ownerView;
                }

                continue;
            }

            if (view is null || ((bool?)view["window"]?["born"] != true && ComputerUseMissionWindow.OnTheTiedWindow(state, view)))
            {
                // The items it lists: a window that comes later titled by one of them is that item, opened.
                ComputerUseMissionWindow.NoteItems(state, view);
                return view;
            }

            JsonArray steps = state["steps"] as JsonArray ?? [];
            bool keeps = ComputerUseMissionWindow.KeepsBorn(state, view, steps, DateTimeOffset.UtcNow, out string why);
            ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, "computer_use.window",
                $"born.{(keeps ? "kept" : "refused")}.{why}");
            if (keeps)
            {
                ComputerUseMissionWindow.Keep(state, view, why);
                ComputerUseMissionWindow.NoteItems(state, view);
                return view;
            }

            ComputerUseMissionWindow.Refuse(state, view);
            if (refused >= BornRefusals)
            {
                return null;
            }
        }
    }

    // How many windows that came during a mission one look refuses before it gives up.
    private const int BornRefusals = 3;

    /// <summary>The pause between the looks that wait for the window of an application tied again (review 2 of ronda 21).</summary>
    internal static readonly TimeSpan RetiePause = TimeSpan.FromSeconds(1);

    /// <summary>
    /// Review 2 of ronda 21 (objective e, v3-34): whether the look after tying again, not kept, leaves the window of the
    /// application to be waited for: it read no window, or one that is not the application's (another program's window in
    /// front, <c>not_application</c>). A window of the application refused (the person's, one they work in or brought)
    /// stops the mission at once.
    /// </summary>
    internal static bool RetieMayWait(JsonObject? view, string why) => view is null || why == "not_application";

    // The look's failure when every window the mission is tied to closed (input.visible.controls, the provider).
    private const string MissionWindowClosed = "mission_window_closed";

    // The state's mark of a last look that failed because the mission's windows closed.
    private const string WindowClosedField = "windowClosed";

    // The state's mark of a mission whose windows closed and whose look after tying it again was none of its own.
    private const string WindowLostField = "windowLost";

    /// <summary>
    /// The stop of a mission left without a look: «the window closed» when its windows closed and it could not be tied
    /// again (ronda 19b), «the window could not be read» otherwise.
    /// </summary>
    internal static string NoViewStop(JsonObject state) =>
        (bool?)state[WindowClosedField] == true ? "computer_use_window_closed"
        : (bool?)state[StillStartingField] == true ? "computer_use_app_not_shown"
        : "computer_use_view_unavailable";

    // Encargo CS: the state's marks of an opening that showed the application's progress window, and of one whose wait
    // for it ran out (NoViewStop).
    private const string ProgressSplashField = "progressSplash";
    private const string StillStartingField = "stillStarting";

    /// <summary>
    /// Encargo CS: how long an application opened cold gets to show its window: <see cref="ColdStartWait"/> once it showed
    /// a progress window of its own (its look, and the look for the window that replaces it), else <see cref="StartWait"/>.
    /// </summary>
    internal static TimeSpan StartCap(JsonObject state) =>
        (bool?)state[ProgressSplashField] == true ? ColdStartWait : StartWait;

    // A look that failed and must not be looked for again: the mission's windows closed.
    private static bool WindowClosed(JsonObject state) => (bool?)state[WindowClosedField] == true;

    // Ronda 21: why the last read failed (the provider's code), and whether this mission ever read a window.
    private const string ViewFailureField = "viewFailure";
    private const string ViewReadField = "viewRead";
    private const string FrontLookedWholeField = "frontLookedWhole";

    // The provider's code of a window whose tree did not come in time (the worker gave no answer), as against one
    // closed, not found or raised above the person's rights.
    private const string ViewUnreadable = "visible_controls_unavailable";

    /// <summary>The pause before the one read again of a window that did not let itself be read (ronda 21).</summary>
    internal static readonly TimeSpan ViewRetryPause = TimeSpan.FromMilliseconds(1500);

    /// <summary>
    /// Ronda 21 (pasada r18 v3-63): whether a look that failed may be read once more: it failed as unreadable, the
    /// mission's window did not close, and this mission already read a window well. A window never read (a hung one,
    /// its first look failed) stops at once, as before.
    /// </summary>
    internal static bool ViewMayComeBack(JsonObject state) =>
        !WindowClosed(state)
        && string.Equals((string?)state[ViewFailureField], ViewUnreadable, StringComparison.Ordinal)
        && (bool?)state[ViewReadField] == true;

    // The mark of a look kept from before a read that failed: it may be shown to the model, never prove anything.
    private const string StaleMark = "stale";

    /// <summary>Ronda 21: whether a look is one kept from before a read that failed (<see cref="LookOnceAsync"/>).</summary>
    internal static bool IsStale(JsonObject? view) => (bool?)view?[StaleMark] == true;

    /// <summary>
    /// Review 1 of ronda 21 (finding 3): a look the worker cut at its own deadline (<c>partial</c>) holds no «none»: an
    /// absence (no step, no document, linked fields, a protected window) may lie in what was not walked. Only a gate the
    /// view does write (<see cref="GateSeen"/>) is said on it, as it is something seen, not something missing.
    /// </summary>
    internal static bool PartialHoldsNoFinal(MindComputerUseStep decision, JsonObject? view) =>
        (bool?)view?["partial"] == true
        && !(decision.Code == "app_gate" && GateSeen(decision, view) is not null);

    /// <summary>
    /// Review 1 of ronda 21 (finding 2): whether a decision ends the mission on what the view shows («done», «none» with
    /// its cause, or anything that is no act), so it needs a fresh look under it.
    /// </summary>
    internal static bool EndsOnTheView(string operation) =>
        operation is "done" or "none" || !Primitives.Contains(operation);

    private static JsonObject Stale(JsonObject view, string why)
    {
        view[StaleMark] = true;
        ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, "computer_use.view_stale", why);
        return view;
    }

    private static async Task<(JsonObject? View, string? Failure)> ReadOneViewAsync(
        Context context, JsonObject arguments, CancellationToken cancellationToken, TimeSpan? timeout = null)
    {
        PreparedOperation prepared = context.Registry.GetOrAdd(new RoutedOperation("input.visible.controls", (JsonObject)arguments.DeepClone()));
        try
        {
            OperationResponse response = await context.Execute(prepared, timeout ?? ViewTimeout, cancellationToken)
                .ConfigureAwait(false);
            if (response.Status != OperationStatuses.Completed
                || !response.Verified
                || response.Result is not { ValueKind: JsonValueKind.Object } result)
            {
                return (null, response.ErrorCode);
            }

            JsonObject? read = JsonNode.Parse(result.GetRawText()) as JsonObject;
            if (read is not null)
            {
                // Revision 1 of ronda 24b (B4): the mission id the journal records this read under, so a witness quoted
                // from this look names the read it came from (ComputerUseSuccessCheck.Witness).
                read["readMission"] = prepared.MissionId;
            }

            return (read, null);
        }
        catch (Exception exception) when (exception is TimeoutException or IOException or InvalidOperationException)
        {
            return (null, null);
        }
        finally
        {
            _ = context.MarkResolved(context.Registry, prepared);
        }
    }
}
