using System.Globalization;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Routines;

namespace Baxy.Core.Operations;

/// <summary>
/// RUT1 (owner, 2026-11-10; documentacion/RUTINAS.md §3): baxy.routines keeps the person's routines in
/// <see cref="LocalRoutineStore"/>. A routine is fired by a phrase of the person and its steps are operations of this
/// catalog with their arguments, or a text to say. Every step is checked against the catalog when it is saved (the
/// operation exists, its arguments pass its schema), so nothing is kept that could not run: the routine.* tools retired
/// on 2026-10-15 kept phrases that nothing fired (4574604aa). <c>run</c> runs nothing itself: it returns the steps of an
/// active routine and the mind proposes each one as a call of its own, which the kernel authorizes as any other, its
/// «sí» included.
/// <para>RUT4 (RUTINAS.md §4): a routine at a time (<c>at</c>, <c>repeat</c>, <c>days</c>) only says texts, and is kept
/// only with its Task Scheduler task set and read back (<see cref="RoutineSayTasks"/>): the task goes first and the
/// store after, and turning it off or deleting it takes the task away first. One said once leaves the list when its
/// time has passed.</para>
/// <para>A step that names a device of the PC (<see cref="RoutineStepTargets"/>: a sound output or input by its name)
/// is looked up when the routine is saved: with no such device, or several, nothing is saved and the devices there are
/// go back, so a routine is not kept blind for a device the PC does not have.</para>
/// </summary>
/// <param name="missing">What a step's target is instead of being there once, or null (RoutineStepTargets.MissingAsync
/// over the core's providers; none in a test that has no devices).</param>
internal sealed class RoutinesHandler(
    string? dataRoot, TimeProvider? time = null, RoutineSayTasks? tasks = null,
    Func<string, JsonObject, CancellationToken, ValueTask<JsonObject?>>? missing = null)
    : IOperationHandler
{
    internal const string Operation = "baxy.routines";

    /// <summary>How a step that says a text is written: «say: …».</summary>
    internal const string SayPrefix = "say:";

    private const int SayMaximumLength = 400;

    // How long after its time a routine said once still shows in the list (it may be saying it now).
    private static readonly TimeSpan OnceKept = TimeSpan.FromMinutes(2);

    private static readonly string[] DayNames = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];

    private readonly TimeProvider _time = time ?? TimeProvider.System;

    private readonly RoutineSayTasks? _tasks =
        tasks ?? (string.IsNullOrWhiteSpace(dataRoot) ? null : new RoutineSayTasks(dataRoot));

    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition(Operation);

    public async ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken) =>
        await Unfound(invocation.Arguments, cancellationToken).ConfigureAwait(false) ?? Execute(invocation.Arguments);

    // create and change: the first step whose device is not there once refuses the routine, with what there is.
    private async ValueTask<OperationOutcome?> Unfound(JsonElement arguments, CancellationToken cancellationToken)
    {
        if (missing is null || Text(arguments, "action") is not ("create" or "change")
            || !arguments.TryGetProperty("steps", out JsonElement given) || given.ValueKind != JsonValueKind.Array)
        {
            return null;
        }

        int number = 0;
        foreach (JsonElement step in given.EnumerateArray())
        {
            number++;
            string text = step.ValueKind == JsonValueKind.String ? step.GetString() ?? string.Empty : string.Empty;
            if (Step(text).Step is not { } parsed || (string?)parsed["op"] is not { } operation
                || parsed["arguments"] is not JsonObject stepArguments
                || await missing(operation, stepArguments, cancellationToken).ConfigureAwait(false) is not { } found)
            {
                continue;
            }

            bool none = (string?)found["problem"] == "audio_device_not_matched";
            found["step"] = number;
            found["text"] = text;
            found["saved"] = false;
            found["next"] = none
                ? "nothing was saved: no active sound device has every word of that name. devices are the ones there "
                    + "are now: ask the person which one and save the routine with its name; one that is switched off or "
                    + "unplugged has to be connected first"
                : "nothing was saved: those devices all match that name: ask the person which one and save the routine "
                    + "with the words that tell it apart";
            return Refused("routine_invalid_step", found);
        }

        return null;
    }

    private OperationOutcome Execute(JsonElement arguments)
    {
        if (string.IsNullOrWhiteSpace(dataRoot))
        {
            return OperationOutcome.Failure("routines_unavailable");
        }

        var store = new LocalRoutineStore(Path.Combine(dataRoot, LocalRoutineStore.FolderName));
        List<JsonObject> routines;
        try
        {
            routines = [.. store.Read()];
        }
        catch (InvalidDataException)
        {
            return Damaged();
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return OperationOutcome.Failure("routines_unreadable");
        }

        // A routine said once whose time has passed is no longer one (its task said it, or says it when the PC is next
        // on); it leaves the file with the next write. RUT9 (REV9 H10): its task goes once it said it (its receipt is
        // there); one not said yet keeps it, to say it some minutes after the PC is on again.
        DateTime nowLocal = _time.GetLocalNow().DateTime;
        foreach (JsonObject spent in routines.Where(routine => Once(routine) is { } once && once + OnceKept < nowLocal))
        {
            if (Str(spent, "id") is { Length: > 0 } id && _tasks is { } tasks && tasks.Said(id))
            {
                _ = tasks.Remove(id);
            }
        }

        routines.RemoveAll(routine => Once(routine) is { } once && once + OnceKept < nowLocal);

        string? action = Text(arguments, "action");
        return action switch
        {
            "list" => Listed(routines),
            "create" => Create(arguments, store, routines),
            "change" or "enable" or "disable" or "delete" or "run" when Text(arguments, "name") is null =>
                OperationOutcome.InvalidArguments(Definition, arguments, ArgumentProblem.Missing("name")),
            "change" or "enable" or "disable" or "delete" or "run" => Named(action, arguments, store, routines),
            _ => OperationOutcome.InvalidArguments(Definition, arguments),
        };
    }

    // RUT9 (REV9 H5): a file that is not a routines list. Nothing is moved or deleted here: the panel lists the routines
    // by itself when it opens, and a file set aside then would have emptied the list with nobody told (second blind
    // review). The receipt says it is damaged and the way out BAXY has: «Olvidar todo» deletes it and the tasks of
    // this data root's routines (FieldProductChannel.ForgetStoredRoutines), and they can be made again.
    private static OperationOutcome Damaged() =>
        Refused("routines_unreadable", new JsonObject
        {
            ["damaged"] = true,
            ["saved"] = false,
            ["next"] = "the routines file is damaged and cannot be read; nothing was changed. Tell the person their "
                + "routines cannot be read, and that «Olvidar todo» in BAXY's memory panel deletes them (with their tasks "
                + "in Windows) so they can make them again",
        });

    private OperationOutcome Create(JsonElement arguments, LocalRoutineStore store, List<JsonObject> routines)
    {
        if (Text(arguments, "phrase") is null && Text(arguments, "at") is null)
        {
            return OperationOutcome.InvalidArguments(Definition, arguments, ArgumentProblem.Missing("phrase"));
        }

        // RUT6: a routine of a phrase is its order, in the person's words; one at a time, its «say» steps.
        if (!arguments.TryGetProperty("steps", out _) && Text(arguments, "order") is null)
        {
            return OperationOutcome.InvalidArguments(
                Definition, arguments, ArgumentProblem.Missing(Text(arguments, "at") is null ? "order" : "steps"));
        }

        if (routines.Count >= LocalRoutineStore.MaximumRoutines)
        {
            return Refused("routines_full", new JsonObject { ["count"] = routines.Count });
        }

        DateTimeOffset now = _time.GetUtcNow();
        var routine = new JsonObject
        {
            ["id"] = NewId(routines),
            ["name"] = Text(arguments, "name") ?? Text(arguments, "phrase"),
            ["active"] = true,
            ["createdUtc"] = Utc(now),
        };
        return Saved(arguments, store, routines, routine, now, routines.Count);
    }

    private OperationOutcome Named(string action, JsonElement arguments, LocalRoutineStore store, List<JsonObject> routines)
    {
        string name = Text(arguments, "name")!;
        // RUT9 (second blind review): by its own name, phrase or clock first; the clock without its leading zero only
        // after, and only a routine at a time («8:00» named after nothing else is not «08:00»).
        // REM4 (REV14 A-R2): over the whole list, its own name first, then its phrase, then its clock. In one pass the
        // first routine of the list that had the name said as any of them was acted on: «07:00», the name of a routine
        // at 07:00 with none of its own, deleted «despertar», saved before it at that clock.
        // REM6 (REV15 B-2): after the person's «sí» the mind names the routine it asked about by its id (NewId's form):
        // that one, or none when it is gone (a «once» pruned two minutes after its time, one deleted meanwhile); never
        // another routine that answers to the name, phrase or clock it was asked by.
        int index = routines.FindIndex(routine => Str(routine, "id") == name);
        bool byId = index >= 0 || IsId(name);
        foreach (Func<JsonObject, string?> part in byId ? [] : NamedBy)
        {
            index = index >= 0 ? index : routines.FindIndex(routine => Names(routine, name, part));
        }

        index = index >= 0 || byId ? index : routines.FindIndex(routine => Names(routine, name, part: null));
        if (index < 0)
        {
            // RUT4 (held-out th11 and th12): the person names a routine by what it says or by its time («la de por las
            // mañanas», «la de las cinco y diez»), and with the names alone the model asked instead of choosing: each
            // one goes with what runs it, and what to do next.
            return Refused("routine_not_found", new JsonObject
            {
                ["name"] = name,
                ["routines"] = new JsonArray(routines.Select(static routine => (JsonNode?)new JsonObject
                {
                    ["name"] = Str(routine, "name"),
                    ["trigger"] = routine["trigger"]?.DeepClone(),
                }).ToArray()),
                ["next"] = "no routine has that name, phrase or time. routines are the ones there are: call again with the "
                    + "name of the one the person means; ask them only when none or several could be it",
            });
        }

        JsonObject routine = routines[index];
        DateTimeOffset now = _time.GetUtcNow();
        switch (action)
        {
            case "run":
                if (routine["active"]?.GetValue<bool>() != true)
                {
                    return Refused("routine_inactive", new JsonObject { ["routine"] = routine.DeepClone() });
                }

                var ran = new JsonObject { ["run"] = routine.DeepClone() };
                if (Str(routine, "order") is not null)
                {
                    // RUT6: an order has no steps for the mind to propose: the model does it from the person's words.
                    ran["next"] = "this routine is an order kept in the person's words: do order now as if the person "
                        + "had just said it, with the tools it needs";
                }

                return OperationOutcome.Success(Element(ran));
            case "delete":
                // The task first: a routine gone from the list that still spoke at its time would be a lie.
                if (At(routine) is not null && Untimed(routine) is { } kept)
                {
                    return kept;
                }

                routines.RemoveAt(index);
                return Reconciled(
                    Written(store, routines, new JsonObject { ["deleted"] = routine.DeepClone() }), store,
                    At(routine) is null ? null : Str(routine, "id"));
            case "enable" or "disable":
                if ((action == "enable") && Clash(routines, routine, Phrase(routine), index) is { } clash)
                {
                    return clash;
                }

                var switched = (JsonObject)routine.DeepClone();
                switched["active"] = action == "enable";
                switched["changedUtc"] = Utc(now);
                var receipt = new JsonObject();
                if (At(switched) is not null
                    && (action == "enable" ? Timed(switched, receipt) : Untimed(switched)) is { } refused)
                {
                    return refused;
                }

                routines[index] = switched;
                receipt["routine"] = switched.DeepClone();
                return Reconciled(Written(store, routines, receipt), store, At(switched) is null ? null : Str(switched, "id"));
            default:
                var changed = (JsonObject)routine.DeepClone();
                return Saved(arguments, store, routines, changed, now, index);
        }
    }

    // create and change: the trigger and the steps the arguments give (change keeps what they leave out), checked, then
    // written at `index` (routines.Count: a new one).
    private OperationOutcome Saved(
        JsonElement arguments, LocalRoutineStore store, List<JsonObject> routines, JsonObject routine, DateTimeOffset now,
        int index)
    {
        bool wasTimed = At(routine) is not null;
        string? phrase = Text(arguments, "phrase");
        bool timeGiven = Text(arguments, "at") is not null || Text(arguments, "repeat") is not null
            || arguments.TryGetProperty("days", out _);
        if (timeGiven)
        {
            // RUT4 (held-out th02 and th05, Esencial seed 0): with a time the model also wrote a «phrase» (the time as
            // the person said it, or the words to say) and the refusal cost it two repeated calls. A routine at a time
            // has no phrase: the time rules, the phrase is left out and the receipt says so (ignored), with what runs it.
            (JsonObject? trigger, ArgumentProblem? problem) = TimeTrigger(arguments, routine["trigger"] as JsonObject);
            if (trigger is null || problem is not null)
            {
                return OperationOutcome.InvalidArguments(Definition, arguments, problem ?? ArgumentProblem.Missing("at"));
            }

            string? before = At(routine);
            routine["trigger"] = trigger;
            if (At(routine) is { } clock
                && (Str(routine, "name") is not { } named || (before is not null && IsFreeName(named, before))))
            {
                // REM2 (REV13 B-3): a name that was only its clock follows the new clock; kept, «08:00» moved to 22:00
                // took the name a new routine at 8 needed, and «borra la rutina 08:00» deleted the one at 22:00.
                routine["name"] = FreeName([.. routines.Where((_, other) => other != index)], clock);
            }
        }
        else if (phrase is not null)
        {
            if (LocalRoutineStore.Folded(phrase).Length == 0)
            {
                return OperationOutcome.InvalidArguments(
                    Definition, arguments, new ArgumentProblem("phrase", "has no letters or digits"));
            }

            routine["trigger"] = new JsonObject { ["phrase"] = phrase };
        }

        // RUT6 (RUTINAS.md §5 c): the order of a routine with a phrase: what the person asked for, in their words. It
        // is kept as text and nothing of it is checked here (which tools it needs is the model's to decide when the
        // person says the phrase); never beside steps, never at a time.
        string? order = Text(arguments, "order");
        if (order is not null && arguments.TryGetProperty("steps", out _))
        {
            return OperationOutcome.InvalidArguments(Definition, arguments, new ArgumentProblem(
                "steps", "a routine with a phrase takes its order alone, in words; steps are only for a routine at a time"));
        }

        if (order is not null && At(routine) is not null)
        {
            return OperationOutcome.InvalidArguments(Definition, arguments, new ArgumentProblem(
                "order", "a routine at a time only says texts: write «say: text» steps, with no order"));
        }

        if (order is not null)
        {
            routine["order"] = order;
            routine["steps"] = new JsonArray();
        }

        if (arguments.TryGetProperty("steps", out JsonElement given))
        {
            routine.Remove("order");
            JsonArray steps = [];
            int number = 0;
            foreach (JsonElement step in given.EnumerateArray())
            {
                number++;
                (JsonObject? parsed, string? problem) = Step(step.GetString() ?? string.Empty);
                if (parsed is null)
                {
                    return Refused("routine_invalid_step", new JsonObject
                    {
                        ["step"] = number,
                        ["text"] = step.GetString(),
                        ["problem"] = problem,
                        ["saved"] = false,
                    });
                }

                steps.Add((JsonNode)parsed);
            }

            routine["steps"] = steps;
        }

        // RUT4: at its time nobody is there to be asked: a routine at a time only says texts.
        if (At(routine) is not null && routine["steps"] is JsonArray timedSteps)
        {
            int tool = timedSteps.ToList().FindIndex(static step => step?["say"] is null);
            if (tool >= 0)
            {
                return Refused("routine_invalid_step", new JsonObject
                {
                    ["step"] = tool + 1,
                    ["problem"] = "a routine at a time only says texts: write each step as «say: text». A tool cannot "
                        + "run by itself at a time; a routine with a phrase can run tools",
                    ["saved"] = false,
                });
            }
        }

        string name = Str(routine, "name") ?? string.Empty;
        if (routines.Where((_, at) => at != index).Any(other => LocalRoutineStore.Folded(Str(other, "name")) == LocalRoutineStore.Folded(name)))
        {
            return Refused("routine_duplicate_name", new JsonObject { ["name"] = name, ["saved"] = false });
        }

        if (routine["active"]?.GetValue<bool>() == true && Clash(routines, routine, Phrase(routine), index) is { } clash)
        {
            return clash;
        }

        routine["changedUtc"] = Utc(now);
        // The task before the store: a routine at a time is kept only with its task set and read back; one that had a
        // time and no longer has it (or is off) loses its task.
        var receipt = new JsonObject();
        bool timed = At(routine) is not null && routine["active"]?.GetValue<bool>() == true;
        if ((timed ? Timed(routine, receipt) : wasTimed ? Untimed(routine) : null) is { } refused)
        {
            return refused;
        }

        bool created = index == routines.Count;
        if (created)
        {
            routines.Add(routine);
        }
        else
        {
            routines[index] = routine;
        }

        receipt["routine"] = routine.DeepClone();
        receipt["saved"] = true;
        if (At(routine) is null)
        {
            receipt["runsWhen"] = Str(routine, "order") is null ? RunsWhen(Phrase(routine)) : DoesWhen(Phrase(routine));
        }
        else if (phrase is not null)
        {
            receipt["ignored"] = "phrase: a routine at a time has no phrase; nothing the person says runs it";
        }

        return Reconciled(Written(store, routines, receipt), store, timed || wasTimed ? Str(routine, "id") : null);
    }

    // RUT9 (REV9 H3): the store was not written after this routine's task was set or taken away (the cleanup there was
    // asked for !EffectMayHaveOccurred, which a failed write never is, so it never ran, and a new routine's task spoke
    // every day with no routine in the list). The task is made to be as the list the store still has: set again from
    // the store's own routine when it is there, on and at a time; taken away otherwise (a new one, one turned on that
    // was not kept, one that is off there). Null id: the routine has no task to mind.
    private OperationOutcome Reconciled(OperationOutcome written, LocalRoutineStore store, string? id)
    {
        if (written.Succeeded || id is null || _tasks is null)
        {
            return written;
        }

        JsonObject? kept;
        try
        {
            kept = store.Read().FirstOrDefault(routine => Str(routine, "id") == id);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or InvalidDataException)
        {
            kept = null;
        }

        if (kept is not null && At(kept) is not null && kept["active"]?.GetValue<bool>() == true)
        {
            _ = Timed(kept, new JsonObject());
        }
        else
        {
            _ = _tasks.Remove(id);
        }

        return written;
    }

    // Sets the task of an active routine at a time and writes into the receipt what the scheduler read back: when it
    // says it next, in the person's local time and relative to today, and what happens at that time. Null when set.
    private OperationOutcome? Timed(JsonObject routine, JsonObject receipt)
    {
        if (_tasks is null || routine["trigger"] is not JsonObject trigger || At(routine) is not { } clock
            || Str(routine, "id") is not { } id)
        {
            return Refused("routine_scheduler_unavailable", new JsonObject { ["saved"] = false });
        }

        DateTime now = _time.GetLocalNow().DateTime;
        TimeSpan at = TimeSpan.ParseExact(clock, "hh\\:mm", CultureInfo.InvariantCulture);
        string repeat = Str(trigger, "repeat") ?? "once";
        DayOfWeek[] days = repeat == "days"
            ? [.. (trigger["days"] as JsonArray ?? []).Select(static day => (DayOfWeek)Array.IndexOf(DayNames, (string?)day))]
            : [];
        DateTime first;
        if (repeat == "once" && Str(trigger, "date") is { } date)
        {
            first = DateTime.ParseExact(date, "yyyy-MM-dd", CultureInfo.InvariantCulture) + at;
            if (first <= now.AddSeconds(5))
            {
                return Refused("routine_time_passed", new JsonObject
                {
                    ["at"] = Local(first),
                    ["nowLocal"] = Local(now),
                    ["saved"] = false,
                    ["next"] = $"nothing is saved or turned on: {Local(first)} has already passed (it is {Local(now)} "
                        + "here). Give at as HH:mm alone for the next time that clock comes, or a date and time still to come",
                });
            }
        }
        else
        {
            first = now.Date + at;
            while (first <= now.AddSeconds(5) || (days.Length > 0 && !days.Contains(first.DayOfWeek)))
            {
                first = first.AddDays(1);
            }

            if (repeat == "once")
            {
                trigger["date"] = first.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
            }
        }

        string text = string.Join(" ", (routine["steps"] as JsonArray ?? []).Select(static step => (string?)step?["say"])
            .Where(static said => !string.IsNullOrWhiteSpace(said)));
        RoutineSayTask set = _tasks.Set(
            id, text, new DateTimeOffset(first, _time.LocalTimeZone.GetUtcOffset(first)), repeat == "daily", days);
        if (!set.Ok || set.NextRun is not { } next)
        {
            return Refused(set.Error ?? "routine_task_not_verified", new JsonObject { ["saved"] = false });
        }

        DateTime nextLocal = TimeZoneInfo.ConvertTime(next, _time.LocalTimeZone).DateTime;
        receipt["nextRunLocal"] = Local(nextLocal);
        receipt["scheduledFor"] = (nextLocal.Date - now.Date).Days switch
        {
            0 => "today",
            1 => "tomorrow",
            _ => nextLocal.ToString("dddd yyyy-MM-dd", CultureInfo.InvariantCulture),
        };
        receipt["runsWhen"] = SaysWhen(clock, repeat, trigger["days"] as JsonArray);
        return null;
    }

    // Takes away the task of a routine that had a time (deleted, turned off, or changed to a phrase). Null when gone.
    private OperationOutcome? Untimed(JsonObject routine)
    {
        RoutineSayTask? removed = Str(routine, "id") is { } id ? _tasks?.Remove(id) : null;
        return removed is { Ok: true }
            ? null
            : Refused(removed?.Error ?? "routine_scheduler_unavailable", new JsonObject
            {
                ["routine"] = Str(routine, "name"),
                ["changed"] = false,
            });
    }

    /// <summary>
    /// The time trigger the arguments give, over the one the routine had (change keeps what they leave out): at as
    /// HH:mm, or a local date and time for one said once; repeat once (the default), daily or days with its days.
    /// </summary>
    internal static (JsonObject? Trigger, ArgumentProblem? Problem) TimeTrigger(JsonElement arguments, JsonObject? had)
    {
        string? clock = Text(arguments, "at") ?? (had is null ? null : Str(had, "at"));
        if (clock is null)
        {
            return (null, ArgumentProblem.Missing("at"));
        }

        string? date = null;
        if (DateTime.TryParseExact(clock, ["H:mm", "HH:mm"], CultureInfo.InvariantCulture, DateTimeStyles.None, out DateTime time))
        {
            clock = time.ToString("HH:mm", CultureInfo.InvariantCulture);
        }
        else if (DateTime.TryParseExact(
            clock, ["yyyy-MM-ddTHH:mm", "yyyy-MM-dd HH:mm", "yyyy-MM-ddTHH:mm:ss"], CultureInfo.InvariantCulture,
            DateTimeStyles.None, out DateTime day))
        {
            clock = day.ToString("HH:mm", CultureInfo.InvariantCulture);
            date = day.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
        }
        else
        {
            return (null, new ArgumentProblem("at", "expected the local time in 24 hours, HH:mm, or YYYY-MM-DDTHH:mm"));
        }

        bool daysGiven = arguments.TryGetProperty("days", out JsonElement dayList) && dayList.ValueKind == JsonValueKind.Array;
        string repeat = Text(arguments, "repeat") ?? (daysGiven ? "days" : had is null ? null : Str(had, "repeat")) ?? "once";
        var trigger = new JsonObject { ["at"] = clock, ["repeat"] = repeat };
        if (repeat == "days")
        {
            string?[] names = daysGiven
                ? [.. dayList.EnumerateArray().Select(static day => day.GetString()?.Trim().ToLowerInvariant())]
                : [.. (had?["days"] as JsonArray ?? []).Select(static day => (string?)day)];
            if (names.Length == 0)
            {
                return (null, ArgumentProblem.Missing("days"));
            }

            if (names.Any(static name => Array.IndexOf(DayNames, name) < 0))
            {
                return (null, new ArgumentProblem("days", "expected mon, tue, wed, thu, fri, sat or sun"));
            }

            // In the week's order, each once; all seven is every day.
            string[] ordered = [.. DayNames.Skip(1).Append(DayNames[0]).Where(names.Contains)];
            if (ordered.Length == DayNames.Length)
            {
                trigger["repeat"] = "daily";
            }
            else
            {
                trigger["days"] = new JsonArray(ordered.Select(static name => (JsonNode?)name).ToArray());
            }
        }
        else if (daysGiven)
        {
            return (null, new ArgumentProblem("days", "days goes with repeat days"));
        }

        if (date is not null)
        {
            if ((string?)trigger["repeat"] != "once")
            {
                return (null, new ArgumentProblem("at", "a date goes only with repeat once: give HH:mm alone"));
            }

            trigger["date"] = date;
        }

        return (trigger, null);
    }

    /// <summary>
    /// RUT4: what a routine at a time does, as the receipt says it so the model promises nothing else (owner,
    /// 2026-11-10: «una vez y listo»; it is not an alarm nor a reminder). With BAXY open, AlarmRinger says the text once
    /// and leaves a line in the conversation; with BAXY closed the task's script shows Windows' notification, with no
    /// voice (ScheduledRingScript); with the PC off or asleep the task is set to run once the PC is on again
    /// (StartWhenAvailable, which Task Scheduler starts «after a delay. The default delay is 10 minutes», Microsoft Learn,
    /// TaskSettings.StartWhenAvailable; and no WakeToRun).
    /// </summary>
    internal static string SaysWhen(string clock, string repeat, JsonArray? days) =>
        "By itself at " + clock + (repeat switch
        {
            "daily" => " every day",
            "days" => " every " + string.Join(", ", (days ?? []).Select(static day => (string?)day)),
            _ => ", one time only (then the routine is gone)",
        })
        + " (nextRunLocal is the next time): BAXY says the text aloud once and leaves a line in the conversation; nothing "
        + "rings and there is nothing to stop or snooze. If BAXY is closed at that time it has no voice: Windows shows the "
        + "text once as a notification. If the PC is off or asleep at that time, Windows is set to do it some minutes "
        + "after the PC is on again.";

    // Another active routine with the same phrase (compared folded): the phrase would fire two.
    private static OperationOutcome? Clash(List<JsonObject> routines, JsonObject routine, string? phrase, int index)
    {
        string folded = LocalRoutineStore.Folded(phrase);
        JsonObject? other = folded.Length == 0
            ? null
            : routines.Where((_, at) => at != index).FirstOrDefault(other =>
                other["active"]?.GetValue<bool>() == true && LocalRoutineStore.Folded(Phrase(other)) == folded);
        return other is null
            ? null
            : Refused("routine_duplicate_phrase", new JsonObject
            {
                ["phrase"] = phrase,
                ["routine"] = Str(other, "name"),
                ["name"] = Str(routine, "name"),
                ["saved"] = false,
            });
    }

    /// <summary>
    /// One step as the model writes it: «say: &lt;text&gt;», or «&lt;operation&gt; &lt;arguments JSON&gt;» (the mind has put
    /// the operation's catalog name where the model wrote the tool's). The operation must be in the catalog and not this
    /// one, and its arguments must pass its schema; the problem says why not.
    /// </summary>
    internal static (JsonObject? Step, string? Problem) Step(string text)
    {
        string written = text.Trim();
        if (written.StartsWith(SayPrefix, StringComparison.OrdinalIgnoreCase))
        {
            string said = written[SayPrefix.Length..].Trim();
            return said.Length is > 0 and <= SayMaximumLength
                ? (new JsonObject { ["say"] = said }, null)
                : (null, $"say needs a text of 1 to {SayMaximumLength} characters");
        }

        int split = written.IndexOfAny([' ', '{']);
        string operation = split < 0 ? written : written[..split];
        string json = split < 0 ? "{}" : written[split..].Trim();
        if (!ProductCatalog.TryGet(operation, out ProductOperationDescriptor? descriptor))
        {
            return (null, $"«{operation}» is not one of BAXY's tools");
        }

        if (operation == Operation)
        {
            return (null, "a routine cannot manage or run routines");
        }

        JsonObject? arguments;
        try
        {
            arguments = JsonNode.Parse(json.Length == 0 ? "{}" : json) as JsonObject;
        }
        catch (JsonException)
        {
            arguments = null;
        }

        if (arguments is null)
        {
            return (null, "the arguments after the tool's name must be one JSON object");
        }

        using JsonDocument document = JsonDocument.Parse(arguments.ToJsonString());
        IReadOnlyList<ArgumentProblem> problems = OperationArgumentValidator.Problems(document.RootElement, descriptor.ArgumentsSchema);
        if (problems.Count > 0)
        {
            return (null, string.Join("; ", problems.Select(static problem => $"{problem.Name}: {problem.Problem}")));
        }

        return (new JsonObject { ["op"] = operation, ["arguments"] = arguments }, null);
    }

    /// <summary>
    /// RUT1 (held-out ch01, Esencial seed 0): «todos los días a las 10 dime…» was saved as a routine whose phrase was the
    /// time, and the model told it as one said every day. What fires a saved routine is a fact of the store: only its
    /// phrase said alone; nothing at a time.
    /// </summary>
    internal static string RunsWhen(string? phrase) =>
        $"Only when the person says «{phrase}» alone, with or without BAXY's name; never inside a longer sentence, and "
        + "never by itself at a time or a day (this routine has a phrase, not a time).";

    /// <summary>
    /// RUT6: what a routine kept as an order does and when, and that saving it tried nothing: «guardada» is a fact of
    /// the store, whether the order can be done is not known until the person says the phrase.
    /// </summary>
    internal static string DoesWhen(string? phrase) =>
        $"Only when the person says «{phrase}» alone, with or without BAXY's name; never inside a longer sentence, and "
        + "never by itself at a time or a day. BAXY then does the order as if the person had just said it, with the "
        + "tools and the questions it needs then. Nothing of the order was done, looked up or tried now: whether it can "
        + "be done is known when they say the phrase.";

    private static OperationOutcome Listed(List<JsonObject> routines) =>
        OperationOutcome.Success(Element(new JsonObject
        {
            ["routines"] = new JsonArray(routines.Select(static routine => (JsonNode)routine.DeepClone()).ToArray()),
            ["count"] = routines.Count,
        }));

    private static OperationOutcome Written(LocalRoutineStore store, List<JsonObject> routines, JsonObject receipt)
    {
        try
        {
            if (!store.Write(routines))
            {
                return OperationOutcome.Failure("routines_postread_failed", effectMayHaveOccurred: true);
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or InvalidDataException)
        {
            return OperationOutcome.Failure(
                "routines_write_failed", effectMayHaveOccurred: true, causeCode: "external_effect_ambiguous");
        }

        return OperationOutcome.Success(Element(receipt));
    }

    private static OperationOutcome Refused(string code, JsonObject result) =>
        OperationOutcome.Failure(code, Element(result));

    // What a routine is named by, in the order Named looks for them: its name, its phrase, its clock.
    private static readonly Func<JsonObject, string?>[] NamedBy = [static routine => Str(routine, "name"), Phrase, At];

    // A routine is named by its name, by its phrase or by its time, as the person says any of them (compared folded).
    // RUT9 (REV9 H9): a clock with or without its hour's leading zero («9:55», «9 55» for one kept as «09:55»).
    // REM4 (REV14 A-R2): ``part`` the one compared (Named looks for each over the whole list, NamedBy's order); null, the
    // clock without its leading zero, after all of them.
    private static bool Names(JsonObject routine, string name, Func<JsonObject, string?>? part)
    {
        string folded = LocalRoutineStore.Folded(name);
        if (folded.Length == 0)
        {
            return false;
        }

        if (part is not null)
        {
            return LocalRoutineStore.Folded(part(routine)) == folded;
        }

        string clock = Unpadded(folded);
        return At(routine) is not null
            && (Unpadded(LocalRoutineStore.Folded(Str(routine, "name"))) == clock
                || Unpadded(LocalRoutineStore.Folded(At(routine))) == clock);
    }

    // «09 55» as «9 55»: the hour of a folded clock without its leading zero; any other text as it is.
    private static string Unpadded(string folded) =>
        folded.Length == 5 && folded[0] == '0' && char.IsAsciiDigit(folded[1]) && folded[2] == ' '
            && char.IsAsciiDigit(folded[3]) && char.IsAsciiDigit(folded[4])
            ? folded[1..]
            : folded;

    // The clock of a routine at a time (HH:mm), or null for one with a phrase.
    private static string? At(JsonObject routine) =>
        routine["trigger"]?["at"] is JsonValue value && value.TryGetValue(out string? at) ? at : null;

    // When a routine said once is said (its date and clock, local), or null for any other.
    private static DateTime? Once(JsonObject routine) =>
        At(routine) is { } at && routine["trigger"] is JsonObject trigger && Str(trigger, "repeat") == "once"
        && DateTime.TryParseExact(
            Str(trigger, "date") + " " + at, "yyyy-MM-dd HH:mm", CultureInfo.InvariantCulture, DateTimeStyles.None,
            out DateTime once)
            ? once
            : null;

    // The name of a routine at a time the person did not name: its clock, or «clock (2)» when another has it.
    private static string FreeName(List<JsonObject> routines, string clock)
    {
        string name = clock;
        for (int number = 2;
            routines.Any(other => LocalRoutineStore.Folded(Str(other, "name")) == LocalRoutineStore.Folded(name));
            number++)
        {
            name = $"{clock} ({number})";
        }

        return name;
    }

    // Whether a routine's name is one FreeName gave it at that clock: the clock, or «clock (n)».
    private static bool IsFreeName(string name, string clock) =>
        name == clock || (name.StartsWith(clock + " (", StringComparison.Ordinal) && name.EndsWith(')')
            && int.TryParse(name.AsSpan(clock.Length + 2, name.Length - clock.Length - 3), NumberStyles.None,
                CultureInfo.InvariantCulture, out _));

    private static string Local(DateTime local) => local.ToString("yyyy-MM-dd HH:mm", CultureInfo.InvariantCulture);

    private static string? Phrase(JsonObject routine) =>
        routine["trigger"]?["phrase"] is JsonValue value && value.TryGetValue(out string? phrase) ? phrase : null;

    private static string? Str(JsonObject routine, string key) =>
        routine[key] is JsonValue value && value.TryGetValue(out string? text) ? text : null;

    // NewId's form: «r-» and six lowercase hex digits.
    private static bool IsId(string name) =>
        name.Length == 8 && name.StartsWith("r-", StringComparison.Ordinal) && name[2..].All(char.IsAsciiHexDigitLower);

    private static string NewId(List<JsonObject> routines)
    {
        string id;
        do
        {
            id = "r-" + Convert.ToHexStringLower(RandomNumberGenerator.GetBytes(3));
        }
        while (routines.Any(routine => Str(routine, "id") == id));
        return id;
    }

    private static string Utc(DateTimeOffset now) =>
        now.UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'", CultureInfo.InvariantCulture);

    private static string? Text(JsonElement arguments, string name) =>
        arguments.ValueKind == JsonValueKind.Object
        && arguments.TryGetProperty(name, out JsonElement value)
        && value.ValueKind == JsonValueKind.String
        && !string.IsNullOrWhiteSpace(value.GetString())
            ? value.GetString()!.Trim()
            : null;

    private static JsonElement Element(JsonObject result)
    {
        using JsonDocument document = JsonDocument.Parse(result.ToJsonString());
        return document.RootElement.Clone();
    }
}
