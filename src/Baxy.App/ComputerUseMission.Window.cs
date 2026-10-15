using System.Globalization;
using System.Text.Json.Nodes;

namespace Baxy.App;

// The mission's window: the one it adopts, the one a click hands it, its process family and the destination the
// request points at.
internal static partial class ComputerUseMission
{
    internal static void AdoptWindow(JsonObject state, string? application, JsonObject view)
    {
        if (application is not { Length: > 0 } || view["window"] is not JsonObject window)
            return;
        // v3 point 1: the content of the application's window drawn by a process it started (WebView2, CEF) names the
        // application's process first; the mission keeps the application's process and learns the family from it.
        int[] family = Family(window);
        if ((int?)state["processId"] is > 0 and int known)
        {
            if (family.Length > 0 && family[0] == known)
                state["family"] = new JsonArray([.. family.Select(member => (JsonNode?)member)]);
            return;
        }

        if ((bool?)window["requested"] != true)
            return;
        if (family.Length > 0)
        {
            state["processId"] = family[0];
            state["family"] = new JsonArray([.. family.Select(member => (JsonNode?)member)]);
            return;
        }

        if ((int?)window["processId"] is > 0 and int owner
            && !string.Equals((string?)window["process"], "ApplicationFrameHost", StringComparison.OrdinalIgnoreCase))
            state["processId"] = owner;
    }

    /// <summary>
    /// Ronda 20b, palanca 8, objetivo 3 (pasada r18, v3-44): a click done whose receipt says it handed its effect to a
    /// window of another process (<c>handedTo</c>: in the Control Panel «Ver dispositivos e impresoras» opens Settings in
    /// the packaged apps' frame) makes that process the mission's: its windows are forgotten and the next look is bound
    /// to that process, so the view reads that window as the requested one (<c>window.requested</c>) and
    /// <see cref="AdoptWindow"/> and the tie take it. Never the frame host shared by the packaged apps (the provider names
    /// the hosted app's process), never a click that did not hold. The windows handed so far are kept in
    /// <c>handedWindows</c>. True when the mission now follows another process.
    /// Review 3 of palanca 8 (B1): the handed window passes the guard of every window that comes during a mission
    /// (<see cref="ComputerUseMissionWindow.KeepsBorn"/>): never one the person works in or may have brought, never an
    /// item the mission saw listed; one already open before the click (<c>born</c> false) only when the request names
    /// it. A refused one is not followed and the click is told as it was before the handoff was read (its window
    /// unchanged), <paramref name="why"/> saying why.
    /// </summary>
    internal static bool FollowHandedWindow(JsonObject state, JsonObject record, JsonArray steps, DateTimeOffset now, out string why)
    {
        why = string.Empty;
        if ((bool?)record["ok"] != true || record["handedTo"] is not JsonObject handed
            || (int?)handed["processId"] is not (> 0 and int process)
            || string.Equals((string?)handed["process"], "ApplicationFrameHost", StringComparison.OrdinalIgnoreCase)
            || (int?)state["processId"] == process)
            return false;
        var seen = new JsonObject
        {
            ["window"] = new JsonObject
            {
                ["root"] = handed["hwnd"]?.DeepClone(),
                ["title"] = handed["title"]?.DeepClone(),
                ["personInputAgoMs"] = handed["personInputAgoMs"]?.DeepClone(),
                ["personNearAgoMs"] = handed["personNearAgoMs"]?.DeepClone(),
            },
        };
        bool keeps = ComputerUseMissionWindow.KeepsBorn(state, seen, steps, now, out why);
        if (keeps && (bool?)handed["born"] != true && why != "named")
        {
            keeps = false;
            why = "already_open";
        }

        if (!keeps)
        {
            RefuseHanded(record, why);
            return false;
        }

        why = string.Empty;
        ComputerUseMissionWindow.Untie(state);
        state.Remove("family");
        state["processId"] = process;
        var handedWindows = state["handedWindows"] as JsonArray ?? new JsonArray();
        handedWindows.Add(handed.DeepClone());
        state["handedWindows"] = handedWindows;
        return true;
    }

    // A handed window the mission does not follow: the click is told as its own window read it, unchanged (what the
    // receipt said before the handoff was read), and why it was not followed.
    private static void RefuseHanded(JsonObject record, string why)
    {
        record.Remove("handedTo");
        record.Remove("changed");
        record["ok"] = false;
        record["error"] = "visible_button_postread_unchanged";
        record["effectUncertain"] = true;
        record["handedRefused"] = why;
    }

    // The application's process and the processes it started, as the view names them (empty: the window is its own).
    private static int[] Family(JsonObject window) =>
        window["family"] is JsonArray members
            ? [.. members.Select(member => member is JsonValue value && value.TryGetValue(out int id) ? id : 0).Where(id => id > 0)]
            : [];

    /// <summary>
    /// The view's window belongs to the mission's application: its process, or a process of the family the provider
    /// read for it (v3 point 1, the application's process first: the content a WebView2 or CEF child draws over the
    /// application's window). Never another process: a family is kept only when it starts with the mission's process.
    /// </summary>
    internal static bool OfTheMissionFamily(JsonObject state, JsonObject? window)
    {
        if ((int?)state["processId"] is not (> 0 and int owner) || (int?)window?["processId"] is not (> 0 and int process))
            return false;
        if (process == owner)
            return true;
        return state["family"] is JsonArray family && family.Count > 0 && (int?)family[0] == owner
            && family.Any(member => (int?)member == process);
    }

    // A look while the application started handed back a front it took by itself: counted, it is an annoyance.
    private static void NoteFrontReturned(JsonObject state, JsonObject? view)
    {
        if ((bool?)view?["window"]?["frontReturned"] == true)
        {
            state["frontReturnedAtStart"] = ((int?)state["frontReturnedAtStart"] ?? 0) + 1;
            ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, "computer_use.front_returned",
                $"start.{(int?)state["frontReturnedAtStart"]}");
        }
    }

    /// <summary>
    /// Ronda 21, destino por contenido: the desktop's windows weighed against the request's referent
    /// (<see cref="ComputerUseDestination"/>). One window clearly ahead ties the mission to it (as the mission's window,
    /// never a document the request names: revision 3, B1), and the window in front is no longer the destination (<c>frontWindow</c>); several equal stop the mission
    /// with the question naming them, none with an honest limit, before anything is looked at or done. A provider that
    /// lists no windows leaves the mission as it was. Null when the mission goes on.
    /// Revision 1 of r21: the window in front the person pointed at, when it shows the referent, is the destination as
    /// before and nothing is bound (B1); the person's own window fitting as well stops with that said (B3); a listing that
    /// failed or ran out of time stops honestly, never falls back to the window in front (B4). Revision 2 of r21: a
    /// mission whose request points at the window in front lists nothing and binds nothing (B2); without Raw Input the
    /// window in front is the person's while the session's last input is recent (B1).
    /// </summary>
    private static async Task<string?> ResolveDestinationAsync(
        Context context, JsonObject state, JsonArray steps, CancellationToken cancellationToken)
    {
        state["destinationResolved"] = true;
        if (ComputerUseDestination.FromState(state) is not { } referent)
        {
            return null;
        }

        if ((bool?)state["frontWindow"] == true)
        {
            // Revision 2 of r21 (B2): the person pointed at the window in front («esto», «esta página»); the mission goes
            // on in it as before and no window behind is weighed, let alone bound in its place.
            ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, "computer_use.destination", "front.pointed");
            return null;
        }

        (JsonObject? listed, _) = await ReadOneViewAsync(
                context, new JsonObject { ["candidates"] = true, ["limit"] = ViewControlLimit }, cancellationToken,
                DestinationTimeout)
            .ConfigureAwait(false);
        if (listed is null)
        {
            // Revision 1 of r21 (B4): the windows could not be listed in time; the window in front (the person's) is
            // never read in their place.
            ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, "computer_use.destination", "unlisted");
            return "computer_use_destination_unlisted";
        }

        if (listed["candidateWindows"] is not JsonArray candidates)
        {
            // A provider that does not list the desktop's windows: the mission goes on as it was.
            ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, "computer_use.destination", "unsupported");
            return null;
        }

        ComputerUseDestination.Choice choice = ComputerUseDestination.Choose(
            referent, candidates, frontWindow: false, ComputerUseMissionWindow.PersonRecentMs,
            // Revision 2 of r21 (B1): without Raw Input, how long ago the session's last input came; the window in
            // front is the person's while it is recent (ComputerUseMissionWindow.PersonMayWorkInFront on a look).
            ComputerUseDestination.LongOf(listed["personInputUnknownAgoMs"]));
        ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, "computer_use.destination",
            $"{choice.Outcome.ToString().ToLowerInvariant()}.candidates.{candidates.Count.ToString(CultureInfo.InvariantCulture)}");
        switch (choice.Outcome)
        {
            case ComputerUseDestination.Outcome.Bound:
                ComputerUseDestination.Bind(state, choice.Window!, steps.Count);
                state["frontWindow"] = false;
                return null;
            case ComputerUseDestination.Outcome.PersonsWindow:
                return "computer_use_destination_persons_window";
            case ComputerUseDestination.Outcome.Ambiguous:
                state["destinationCandidates"] = new JsonArray([.. choice.Titles.Select(title => (JsonNode?)title)]);
                return "computer_use_destination_ambiguous";
            default:
                // Nothing that could be looked at shows it: asked about; the final says only what was looked at
                // (revision 1, B2).
                return "computer_use_destination_not_found";
        }
    }

    /// <summary>
    /// Ronda 24: whether the window the mission's last look read is one asked for — an application said (the mission's
    /// or a sub-goal's), the window the mission was tied or bound to (<c>processId</c>, <c>windows</c>,
    /// <c>destinationBound</c>), the window in front the person pointed at (<c>frontWindow</c>), or a look the provider
    /// resolved for the request (<c>requested</c>).
    /// </summary>
    internal static bool WindowAsked(JsonObject state) =>
        (string?)state["application"] is { Length: > 0 }
        || (bool?)state["chained"] == true
        || (bool?)state["frontWindow"] == true
        || state["destinationBound"] is JsonObject
        || (int?)state["processId"] is > 0
        || state["windows"] is JsonArray { Count: > 0 }
        || (bool?)state["window"]?["requested"] == true;
}
