using System.Globalization;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Baxy.App;

/// <summary>
/// Goal v3 ventana-misión (pasada r9: t-long-2, t-menu-1, t-form-4). A mission is tied to the window it opened, created
/// or the request names (its handle and its process), not to its application's process: Word's one process held the
/// document BAXY created and, after a click on a recent file, the owner's thesis, and the look bound to the process
/// took the thesis (Ctrl+A, Escape and ribbon clicks went there, and the arrival was judged on it). The mission's state
/// keeps its windows (<c>windows</c>, the latest first), the windows it knows are not its (<c>known</c>: what its
/// process already showed when the mission took its window, minimized ones too, and the windows it refused), the
/// windows it opened or created (<c>created</c>), the ones the request names (<c>named</c>) and the one window of an
/// application the request names that showed no other (<c>sole</c>, with the document it showed then). A window that
/// came during the mission (the look says <c>born</c>) becomes one of its windows only when its own window owns it (a
/// dialog), the request names it by its title, or an act of the mission brought it, the person did nothing since then
/// that could have brought it, and it is not an existing item the mission saw listed or typed by its name; never a
/// window the person works in. A window the person works in is never the destination of a mission that names no
/// application either («BAXY usuario simulado», the window the simulated person typed in, was read as the mission's).
/// </summary>
internal static class ComputerUseMissionWindow
{
    /// <summary>The person's input this recent (ms) marks the window they work in, also before the mission began.</summary>
    internal const long PersonRecentMs = 3000;

    // The keys of the closed repertoire (ProductCatalog, input.key.press) that change no document's content: moving
    // through it, copying, finding, opening a menu or a dialog, leaving (data «computerUse.contentKeys.keeping»). Any
    // other (Ctrl+A, Supr, Backspace, Ctrl+X, Ctrl+V, Enter, Space or Tab over a selection, Ctrl+Z, a format shortcut,
    // Ctrl+S, Ctrl+W) may select, erase, replace or write it (review of ventana-misión, finding 3). Ronda 21 (pasada r18
    // v3-59): the keys that open a new container or take the keyboard to the window's bar in a browser («container»:
    // a new tab, the address bar) format the text in an editor (a hanging indent, an alignment), so they are never
    // exempt by themselves: they are judged by the control the keyboard is on, and a read-only page is no content.
    internal static bool ContentKeepingKey(string key) => OperationFloor.ContentKeyClass("keeping").Contains(key);

    /// <summary>
    /// Ronda 21 (pasada r18 v3-36): a key that selects, erases, replaces, pastes, undoes or writes at the caret (data
    /// «computerUse.contentKeys.altering»). A rule's or a learned key refused on a document the mission may not touch
    /// hands the step to the model unless it is one of these.
    /// </summary>
    internal static bool AlteringKey(string? key) =>
        OperationFloor.ContentKeyClass("altering").Contains(ComputerUseSuccessCheck.Fold(key).Trim().Replace(' ', '_'));

    // The keys that write at the caret as a text does: what the sole window of a named application takes with its text
    // (with no selection the mission could have made there: Ctrl+A and a select-all click are refused on it).
    private static readonly HashSet<string> WritingKeys = new(StringComparer.Ordinal) { "enter", "space", "tab" };

    // How many names of listed items a mission remembers (the newest kept).
    private const int ItemsSeenLimit = 300;

    // The kinds of control that list an item (a file, a recent document, a row): what is opened by its name.
    private static readonly HashSet<string> ItemKinds = new(StringComparer.Ordinal) { "ListItem", "DataItem", "TreeItem" };

    /// <summary>The top-level window a view is of (the window behind its dialog); null when the view does not say.</summary>
    internal static long? Root(JsonObject? view) =>
        LongOf(view?["window"]?["root"]) is long root and > 0 ? root
        : LongOf(view?["window"]?["hwnd"]) is long hwnd and > 0 ? hwnd
        : null;

    private const int LookWindows = 16;
    private const int LookKnown = 256;

    internal static bool Tied(JsonObject state) => state["windows"] is JsonArray { Count: > 0 };

    /// <summary>A look of a tied mission names its windows and the ones it knows are not its.</summary>
    internal static void AddLookArguments(JsonObject state, JsonObject arguments)
    {
        if (!Tied(state))
            return;
        // Bounded as the catalog's schema of the look declares them (input.visible.controls: 16 and 256), so a
        // process with many windows never turns the look into invalid arguments: the first windows tied (the one the
        // mission opened or was named comes first) and the latest known.
        arguments["windows"] = new JsonArray([.. ((JsonArray)state["windows"]!).Take(LookWindows).Select(node => node?.DeepClone())]);
        if (state["known"] is JsonArray { Count: > 0 } known)
            arguments["known"] = new JsonArray([.. known.TakeLast(LookKnown).Select(node => node?.DeepClone())]);
    }

    /// <summary>
    /// The first look that shows the application's window (resolved for it, or of its process family) ties the
    /// mission to it: the other windows its process shows then are known not to be the mission's. The window is the
    /// mission's own when an opening of this mission started the application (not one already running) or opened a
    /// file in it, and named when the request names its title. When the look says its process showed no other window
    /// (<c>others</c> present and empty), the request that names the application names that window as <c>sole</c>: text
    /// goes to it, nothing that selects, erases or replaces does, and only while it shows the document it showed then
    /// (another tab of it is another document). A look that does not say counts as several windows (finding 6).
    /// </summary>
    internal static void Tie(JsonObject state, string? application, JsonObject view, bool ofTheApplication, JsonArray steps)
    {
        if (Tied(state) || application is not { Length: > 0 } || !ofTheApplication || Root(view) is not long root)
            return;
        state["windows"] = new JsonArray(root);
        JsonArray? others = view["window"]?["others"] as JsonArray;
        state["known"] = others is not null
            ? new JsonArray([.. others.Select(other => LongOf(other)).Where(other => other is > 0 && other != root)
                .Select(other => (JsonNode?)other!.Value)])
            : new JsonArray();
        state["tiedAtStep"] = steps.Count;
        string? title = (string?)view["window"]?["title"];
        // Ronda 24 (pasada r23 v3-34): the document the window showed when the mission took it (what a command the
        // request names may act on: RequestedOnTiedDocument), and whether the mission's own start of the application
        // made it: only when its content is empty or a placeholder. One that already holds text restored the person's
        // work (restored): neither text nor anything that replaces goes there.
        Remember(state, "tiedDocuments", root, DocumentKey(title));
        // Revisión 1 de r24 (B2): what that look listed (a page of the person's that is already there): a document of
        // that name the window shows later is no creation of the mission's (NoteCreatedDocument).
        state["tiedShown"] = ComputerUseSuccessCheck.ControlNames(view);
        bool restored = false;
        if (OpenedByTheMission(steps))
        {
            restored = OpenedTheApplication(steps) && HoldsContent(view);
            Add(state, restored ? "restored" : "created", root);
        }

        if (NamedByObjective(Objective(state), title, application))
        {
            Add(state, "named", root);
        }
        else if (!restored && others is not null && state["known"] is JsonArray { Count: 0 })
        {
            Add(state, "sole", root);
            var documents = state["soleDocuments"] as JsonObject ?? new JsonObject();
            documents[root.ToString(CultureInfo.InvariantCulture)] = DocumentKey(title);
            state["soleDocuments"] = documents;
        }
    }

    /// <summary>Forgets the windows: the mission goes on in another application.</summary>
    internal static void Untie(JsonObject state)
    {
        foreach (string field in new[]
                 {
                     "windows", "known", "refused", "created", "named", "sole", "soleDocuments", "tiedAtStep", "tiedDocuments",
                     "restored", "createdDocuments", "tiedShown",
                 })
            state.Remove(field);
    }

    /// <summary>
    /// Ronda 19b (r15b v3-34, v3-35): every window the mission is tied to closed. When the mission itself started its
    /// application (or opened its file) the windows are forgotten once, so the next look reads the application's window
    /// as its first look did and ties the mission to it again (a launcher's first window giving way to another the
    /// provider does not see born). Never twice, and never for an application that was already running, whose other
    /// windows may be the person's: then the mission stops, its window closed. Review of ronda 19b: the windows the
    /// mission refused (<c>refused</c>: the person's among them) and the ones it opened or created are kept, and the
    /// look that follows is judged as a born window (<see cref="KeepsRetied"/>) before the mission is tied to it.
    /// </summary>
    internal static bool Retie(JsonObject state, JsonArray steps)
    {
        if (!Tied(state) || (bool?)state["retied"] == true || !OpenedByTheMission(steps))
            return false;
        foreach (string field in new[] { "windows", "known", "named", "sole", "soleDocuments", "tiedAtStep", "tiedDocuments" })
            state.Remove(field);
        state["retied"] = true;
        state[RetieLookField] = true;
        return true;
    }

    // The state's mark of a mission whose windows were forgotten to tie it again: its next look is judged.
    private const string RetieLookField = "retieLook";

    /// <summary>Whether this look is the one that follows <see cref="Retie"/> (the mark is taken).</summary>
    internal static bool TakeRetieLook(JsonObject state) => state.Remove(RetieLookField);

    /// <summary>
    /// Review 2 of ronda 21: the look after <see cref="Retie"/> read no window of the application yet; the next look is
    /// judged the same way (still naming no window).
    /// </summary>
    internal static void LookAgainForRetie(JsonObject state) => state[RetieLookField] = true;

    /// <summary>
    /// Review of ronda 19b: the look that follows <see cref="Retie"/> names no window, so the provider reads a window
    /// of the application's process, one titled like it, or the window in front. It is the mission's only when it shows
    /// the application, is no window the mission refused (the person's window of the same process), and is kept as a
    /// born window is (<see cref="KeepsBorn"/>: never one the person works in or brought since the mission's act).
    /// </summary>
    internal static bool KeepsRetied(
        JsonObject state, JsonObject view, bool ofTheApplication, JsonArray steps, DateTimeOffset now, out string why)
    {
        if (!ofTheApplication || Root(view) is not long root)
        {
            why = "not_application";
            return false;
        }

        if (Contains(state["refused"], root))
        {
            why = "refused";
            return false;
        }

        return KeepsBorn(state, view, steps, now, out why);
    }

    /// <summary>
    /// The look kept by <see cref="KeepsRetied"/> ties the mission again: its window, and as known the windows it
    /// refused and the other windows its process shows now.
    /// </summary>
    internal static void TieAgain(JsonObject state, JsonObject view, string why, JsonArray steps)
    {
        if (Root(view) is not long root)
            return;
        state["windows"] = new JsonArray(root);
        var known = new JsonArray();
        IEnumerable<JsonNode?> others = view["window"]?["others"] as JsonArray ?? [];
        foreach (long other in (state["refused"] as JsonArray ?? []).Concat(others).Select(LongOf).OfType<long>())
        {
            if (other > 0 && other != root && !Contains(known, other))
                known.Add(other);
        }

        state["known"] = known;
        state["tiedAtStep"] = steps.Count;
        if (why is "owned" or "created")
            Add(state, "created", root);
        if (why == "named")
            Add(state, "named", root);
    }

    /// <summary>
    /// Whether a window that came during the mission (<c>born</c>) is the mission's: yes when one of its windows owns
    /// it (its dialog, also one the person's stray key reached: finding 7); never one the person works in; yes when the
    /// request names its title; else only when an act of the mission (one since it took its window, or the start of an
    /// application it launched) brought it, the person gave no input since that act to its process or to the shell
    /// (opening a file of theirs, restoring or starting a window of theirs: finding 1), and it is not an item the
    /// mission saw listed, clicked or typed by its name (a recent file opened from a list is that file, the person's,
    /// unless the request names it: finding 2).
    /// </summary>
    internal static bool KeepsBorn(JsonObject state, JsonObject view, JsonArray steps, DateTimeOffset now, out string why)
    {
        JsonObject window = view["window"] as JsonObject ?? new JsonObject();
        string? title = (string?)window["title"];
        if (LongOf(window["owner"]) is long owner && Contains(state["windows"], owner))
        {
            why = "owned";
            return true;
        }

        if (PersonWorksIn(state, view, now))
        {
            why = "person";
            return false;
        }

        if (NamedByObjective(Objective(state), title, (string?)state["application"]))
        {
            why = "named";
            return true;
        }

        // The mission's acts since it took its window, or its own start of the application (a launcher's splash gives
        // way to its main window with no act in between).
        int tiedAt = (int?)state["tiedAtStep"] ?? 0;
        bool acted = state["created"] is JsonArray { Count: > 0 }
            || steps.OfType<JsonObject>().Skip(tiedAt).Any(ComputerUseMission.MayHaveActed);
        if (!acted)
        {
            why = "no_act";
            return false;
        }

        if (PersonMayHaveBroughtIt(state, window, now))
        {
            why = "person_since_act";
            return false;
        }

        if (OpenedItem(state, steps, title))
        {
            why = "item_opened";
            return false;
        }

        why = "created";
        return true;
    }

    /// <summary>The born window becomes the mission's latest window.</summary>
    internal static void Keep(JsonObject state, JsonObject view, string why)
    {
        if (Root(view) is not long root)
            return;
        var windows = new JsonArray(root);
        foreach (JsonNode? node in state["windows"] as JsonArray ?? [])
        {
            if (LongOf(node) is long earlier && earlier != root)
                windows.Add(earlier);
        }

        state["windows"] = windows;
        if (why is "owned" or "created")
            Add(state, "created", root);
        if (why == "named")
            Add(state, "named", root);
    }

    /// <summary>The born window is known not to be the mission's: no look reads it again.</summary>
    internal static void Refuse(JsonObject state, JsonObject view)
    {
        if (Root(view) is not long root)
            return;
        Add(state, "known", root);
        // Kept apart from the windows the process showed when the mission took its window: the ones a closed window
        // tied again never reads (review of ronda 19b).
        Add(state, "refused", root);
    }

    /// <summary>
    /// The mission sends an act now: what a window that comes later is measured against (the person's input since it).
    /// </summary>
    internal static void NoteAct(JsonObject state, DateTimeOffset now) =>
        state["lastActUtc"] = now.ToString("O", CultureInfo.InvariantCulture);

    /// <summary>
    /// The names of the items a look of the mission listed (a recent file, a file of a folder, a row): a window that
    /// comes later titled by one of them is that item, opened. The newest <see cref="ItemsSeenLimit"/> are kept.
    /// </summary>
    internal static void NoteItems(JsonObject state, JsonObject? view)
    {
        if (view?["controls"] is not JsonArray controls)
            return;
        var items = state["itemsSeen"] as JsonArray ?? new JsonArray();
        var have = new HashSet<string>(items.Select(node => (string?)node ?? string.Empty), StringComparer.Ordinal);
        foreach (JsonObject control in controls.OfType<JsonObject>())
        {
            if (!ItemKinds.Contains((string?)control["kind"] ?? string.Empty)
                || string.Join(' ', Words((string?)control["name"])) is not { Length: > 0 } name || !have.Add(name))
                continue;
            items.Add((JsonNode?)name);
        }

        while (items.Count > ItemsSeenLimit)
            items.RemoveAt(0);
        state["itemsSeen"] = items;
    }

    /// <summary>
    /// Whether the view is the mission's window: always when the mission is not tied or the view does not say its
    /// window; else its window, or a window one of them owns, is one of the mission's.
    /// </summary>
    internal static bool OnTheTiedWindow(JsonObject state, JsonObject? view)
    {
        if (!Tied(state) || Root(view) is not long root)
            return true;
        return Contains(state["windows"], root)
            || (LongOf(view?["window"]?["owner"]) is long owner && Contains(state["windows"], owner));
    }

    /// <summary>
    /// Encargo W (t-scroll-4, limites1: after Ctrl+L the folder window's address suggestions came as a pop-up window it
    /// owns; the look read that list and the bar the keyboard was on left the view). A window that came during the
    /// mission (born) and one of the mission's windows owns, read in front with the keyboard on none of its controls,
    /// may float beside its owner (the list under the owner's field) while the keyboard stays on the owner: that owner,
    /// else null. A dialog or a menu in front holds the keyboard itself (its field, its first entry: every owned look of
    /// the banks), and one read behind cannot tell. A window already kept is the mission's and is not weighed again.
    /// </summary>
    internal static long? OwnerMayHoldTheKeyboard(JsonObject state, JsonObject view)
    {
        if (!Tied(state) || view["window"] is not JsonObject window || (bool?)window["born"] != true
            || (bool?)window["foreground"] != true
            || Root(view) is not long root || LongOf(window["owner"]) is not long owner || owner == root
            || !Contains(state["windows"], owner) || HoldsTheKeyboard(view))
            return null;
        return owner;
    }

    /// <summary>Whether a control of the view has the keyboard: the window's focused control, or one marked focused.</summary>
    internal static bool HoldsTheKeyboard(JsonObject view) =>
        view["window"]?["focused"] is JsonObject
        || (view["controls"] as JsonArray ?? []).OfType<JsonObject>().Any(control =>
            ((string?)control["state"] ?? string.Empty).Split(' ', StringSplitOptions.RemoveEmptyEntries).Contains("focused"));

    /// <summary>
    /// The arguments of one look of <paramref name="owner"/> instead of the window it owns: the owner first among the
    /// mission's windows and the owned one known for this look only. It is neither kept nor refused, so a later look
    /// reads it again when it holds the keyboard (a menu that comes in the same pop-up window).
    /// </summary>
    internal static JsonObject OwnerLookArguments(JsonObject state, JsonObject arguments, long owner, long owned)
    {
        var look = (JsonObject)arguments.DeepClone();
        var windows = new JsonArray(owner);
        foreach (long window in (state["windows"] as JsonArray ?? []).Select(LongOf).OfType<long>())
        {
            if (window != owner && window != owned && windows.Count < LookWindows)
                windows.Add(window);
        }

        look["windows"] = windows;
        var known = new JsonArray([.. (state["known"] as JsonArray ?? []).TakeLast(LookKnown - 1).Select(node => node?.DeepClone())]);
        known.Add(owned);
        look["known"] = known;
        return look;
    }

    /// <summary>
    /// The person's last input went to this window while the mission works, or a moment before it (the window they
    /// are typing in): it is theirs.
    /// </summary>
    internal static bool PersonWorksIn(JsonObject state, JsonObject? view, DateTimeOffset now)
    {
        if (LongOf(view?["window"]?["personInputAgoMs"]) is not long ago)
            return false;
        long sinceStart = DateTimeOffset.TryParse(
            (string?)state["startedUtc"], CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out DateTimeOffset started)
            ? (long)(now - started).TotalMilliseconds
            : 0;
        return ago <= Math.Max(sinceStart, PersonRecentMs);
    }

    /// <summary>
    /// A mission with no application named whose look shows a window that is neither resolved for it nor of its
    /// process, the person's window (their last input went there) and not named as the destination: no window of the
    /// mission is in sight, and the person's is never read for it.
    /// </summary>
    internal static bool PersonsWindowWithoutApplication(
        JsonObject state, string? application, JsonObject? view, bool ofTheMission, DateTimeOffset now) =>
        application is not { Length: > 0 }
        && (bool?)state["frontWindow"] != true
        && !ofTheMission
        && (PersonWorksIn(state, view, now) || PersonMayWorkInFront(view));

    /// <summary>
    /// Ronda 20 P2, without Raw Input: no window of the person is known (the look says no <c>personInputAgoMs</c>), only
    /// how long ago the session's last input came (<c>personInputUnknownAgoMs</c>). A look nobody asked for
    /// (<c>requested</c> false) of the window in front (<c>foreground</c>) is taken for the person's only while that
    /// input is recent (<see cref="PersonRecentMs"/>): it may have gone there. Older, the window is shown as before.
    /// </summary>
    internal static bool PersonMayWorkInFront(JsonObject? view) =>
        view?["window"] is JsonObject window
        && window["personInputAgoMs"] is null
        && LongOf(window["personInputUnknownAgoMs"]) is long ago and <= PersonRecentMs
        && (bool?)window["requested"] == false
        && (bool?)window["foreground"] == true;

    /// <summary>
    /// Review of ventana-misión (finding 5): what the model is shown instead of the person's window, when a mission
    /// with no application has no window of its own in sight. Nothing of the person's window: no title, no control,
    /// no text. From it the mission may only open an application or a file (<see cref="HidesThePersonsWindow"/>).
    /// </summary>
    internal static JsonObject HiddenPersonsWindow() => new()
    {
        ["window"] = new JsonObject { ["title"] = string.Empty, ["requested"] = false, ["personsWindowHidden"] = true },
        ["controls"] = new JsonArray(),
    };

    /// <summary>Whether the view is the blank one shown instead of the person's window.</summary>
    internal static bool HidesThePersonsWindow(JsonObject? view) => (bool?)view?["window"]?["personsWindowHidden"] == true;

    /// <summary>
    /// An act on the content of a document the mission neither opened nor created and the request does not name
    /// (another document of the application, already there, or another tab of the one window it showed): never done.
    /// A key that may select, erase, replace or write (every key but <see cref="ContentKeepingKeys"/>), a text, a
    /// click on a command that selects all, cuts, erases, pastes, replaces or undoes (data
    /// «computerUse.contentErasing»). On the <c>sole</c> window of an application the request
    /// names, text and Enter, Space or Tab go at the caret; the rest is refused the same. A field of the window (its
    /// search, a dialog's name box) is no document's content.
    /// </summary>
    internal static bool ForeignDocumentAct(string operation, JsonObject arguments, JsonObject? view, JsonObject state)
    {
        if (!Tied(state) || operation is not ("input.key.press" or "input.text.type" or "input.visible.click")
            || view?["window"] is not JsonObject window)
            return false;
        long? root = Root(view);
        if (root is long mine && (Contains(state["created"], mine) || Contains(state["named"], mine)))
            return false;
        if (LongOf(window["owner"]) is long owner && Contains(state["created"], owner))
            return false;
        string? title = (string?)window["title"];
        if (NamedByObjective(Objective(state), title, (string?)state["application"]))
            return false;
        // Ronda 24 (pasada r23 v3-11): a document the mission created in its window (NoteCreatedDocument) is its own
        // while the window still shows it; another page of that window (one that was there) is not.
        if (root is long here && CreatedDocument(state, here) is { } created && created == DocumentKey(title))
            return false;
        // The sole window still shows its document, or one the mission saved it as (a name it typed).
        bool sole = root is long one && Contains(state["sole"], one)
            && ((string?)state["soleDocuments"]?[one.ToString(CultureInfo.InvariantCulture)] == DocumentKey(title)
                || (state["steps"] as JsonArray ?? []).OfType<JsonObject>()
                    .Any(step => Words(WithoutExtension(DocumentPart(title))) is { Length: > 0 } saved
                        && ContainsRun(Words(WithoutExtension((string?)step["text"])), saved)));
        bool showsContent = (view["controls"] as JsonArray ?? []).OfType<JsonObject>().Any(control => DocumentContent(control, window));
        string key = ComputerUseSuccessCheck.Fold((string?)arguments["key"]).Trim().Replace(' ', '_');
        switch (operation)
        {
            case "input.text.type" when sole:
                return false;
            case "input.key.press" when ContentKeepingKey(key) || (sole && WritingKeys.Contains(key)):
                return false;
            case "input.visible.click":
                return showsContent && ErasingClick(arguments, view, state, root, title);
        }

        JsonObject? target = null;
        if (operation == "input.text.type" && LongOf(arguments["index"]) is long index)
            target = Control(view, index);
        if (target is null && LongOf(window["focused"]?["i"]) is long focused)
            target = Control(view, focused);
        // A target not known: the document's content may take it, when the view shows one, a read-only page as well
        // (a field inside it may hold the keyboard once the window takes the front: a web draft, an editor's small
        // text area). Only a known target that is itself read-only (the keyboard on a web page that takes no text) is
        // no content (ronda 21, revisión 1, hallazgo a).
        return target is null ? showsContent : DocumentContent(target, window, readOnlyCounts: false);
    }

    /// <summary>
    /// Ronda 24 (pasada r23 t-form-2): a click that may select, erase, replace or undo the content. Only a control that
    /// executes something (data «computerUse.contentErasing.commandKinds»: a button, a menu entry, a link) is judged by
    /// its label; a field the view names (the «Reemplazar» box of a find dialog) is never an order. A command of the
    /// class the request itself names («reemplazá casa por hogar» and «Reemplazar todo») is no foreign act on the window
    /// of the named application the mission is tied to while it shows the document it showed then.
    /// </summary>
    private static bool ErasingClick(JsonObject arguments, JsonObject view, JsonObject state, long? root, string? title)
    {
        string label = ComputerUseSuccessCheck.Fold((string?)arguments["label"]).Trim();
        // The control the click names by its index when that one bears the label (a field and a button may share it),
        // else the first of that name.
        JsonObject? pressed = LongOf(arguments["index"]) is long index && Control(view, index) is JsonObject indexed
            && ComputerUseSuccessCheck.Fold((string?)indexed["name"]).Trim() == label
                ? indexed
                : Named(view, label);
        if (pressed is not null && !CommandKinds.Value.Contains((string?)pressed["kind"] ?? string.Empty))
            return false;
        if (!OperationFloor.ContentErasingCommand(label))
            return false;
        return !(root is long tied && RequestedOnTiedDocument(state, view, tied, title, label));
    }

    private static readonly Lazy<HashSet<string>> CommandKinds = new(() => new HashSet<string>(
        (ContentErasing["commandKinds"] as JsonArray ?? []).Select(node => (string?)node ?? string.Empty),
        StringComparer.Ordinal));

    private static JsonObject ContentErasing => (JsonObject)OperationFloor.ComputerUseData["contentErasing"]!;

    // A command of a class the request names, on the tied window of the named application still showing the document
    // it showed when the mission took it (never a window whose opening restored the person's work).
    private static bool RequestedOnTiedDocument(JsonObject state, JsonObject view, long root, string? title, string foldedLabel)
    {
        if (!Contains(state["windows"], root) || Contains(state["restored"], root)
            || (string?)state["application"] is not { Length: > 0 }
            || (string?)state["tiedDocuments"]?[root.ToString(CultureInfo.InvariantCulture)] is not { } tiedDocument
            || tiedDocument != DocumentKey(title))
            return false;
        // Revisión 2 de r24 (B2, sonda A: «reemplazá casa por hogar en la pestaña pendientes» on a window showing
        // «diario»): a request that names another document than the tied one, a tab the window lists now or listed on
        // the sub-goal's first look, asks for the command there, never here.
        string? application = (string?)state["application"];
        IEnumerable<string?> tabs = ComputerUseSuccessCheck.TabNames(view)
            .Concat(state["subgoalFirstTabs"] as JsonArray ?? [])
            .Select(tab => (string?)tab);
        if (tabs.Any(tab => DocumentKey(tab) is { Length: > 0 } other && other != tiedDocument
                && NamedByObjective(Objective(state), tab, application)))
            return false;
        string objective = ComputerUseSuccessCheck.Fold(Objective(state));
        return (ContentErasing["requested"] as JsonObject ?? new JsonObject()).Select(entry => entry.Value).OfType<JsonObject>()
            .Any(kind => Regex.Matches(objective, (string?)kind["request"] ?? "$^", RegexOptions.CultureInvariant)
                    .Any(verb => InCommandPosition(objective[..verb.Index], application, title))
                && Regex.IsMatch(foldedLabel, (string?)kind["label"] ?? "$^", RegexOptions.CultureInvariant));
    }

    // Revisión 3 de r24 (B2: «una nota corta», «a clear note», «hay pega» let a class through): the class's word counts
    // only where an order stands. The folded objective before it ends at a start of order (data «commandPosition»), or
    // at one followed by the place the order happens in (data «commandPlace») whose words, but «placeFillers», are all
    // of the tied window's application or title; any other word there starts another phrase («write down the hair cut»).
    private static bool InCommandPosition(string before, string? application, string? title)
    {
        string start = (string?)ContentErasing["commandPosition"] ?? "$^";
        if (Regex.IsMatch(before, start + "$", RegexOptions.CultureInvariant))
            return true;
        string place = ((string?)ContentErasing["commandPlace"] ?? "$^").Replace("(?P<", "(?<", StringComparison.Ordinal);
        Match located = Regex.Match(before, start + place + "$", RegexOptions.CultureInvariant);
        if (!located.Success)
            return false;
        var known = new HashSet<string>(Words(application).Concat(Words(title))
            .Concat((ContentErasing["placeFillers"] as JsonArray ?? []).Select(word => (string?)word ?? string.Empty)), StringComparer.Ordinal);
        return Words(located.Groups["place"].Value).All(known.Contains);
    }

    /// <summary>
    /// Ronda 24 (pasada r23 v3-11: «Agregar página» made «Sin título - OneNote» and nothing recorded it): on a look of
    /// the mission's tied window after its last step, a verified click on a command that creates (data
    /// «creatingCommand», or one that brought new controls: «broughtNew»), when the window's title now names a
    /// document with no name yet (data «untitledDocument») that neither the look the click was decided on nor the
    /// window's first look showed, and the click did not choose an item of that name: that document is the mission's
    /// (<c>createdDocuments</c>, by window). The click keeps it as <c>createdDocument</c> (what the final says it left).
    /// </summary>
    internal static void NoteCreatedDocument(JsonObject state, JsonObject view, JsonArray steps)
    {
        if (!Tied(state) || Root(view) is not long root || !Contains(state["windows"], root)
            || steps.Count == 0 || steps[^1] is not JsonObject click || (bool?)click["ok"] != true
            || (string?)click["operation"] != "input.visible.click" || click["createdDocument"] is not null)
            return;
        string? title = (string?)view["window"]?["title"];
        string document = DocumentKey(title);
        JsonObject rules = OperationFloor.EvidenceRules;
        string label = ComputerUseSuccessCheck.Fold((string?)click["label"]).Trim();
        // The kind of the control the click pressed: its receipt's, else the first of its name the view lists.
        string? pressedKind = (string?)click["kind"] ?? (string?)Named(view, label)?["kind"];
        // Revisión 2 de r24 (B3, sonda B): a verified click that chooses or navigates (data «choosingKinds»: a tab, a
        // row, a node) on a window where the mission created a document may show the person's page of the same name
        // («Sin título» of another section): the document created there is no longer known to be the one shown.
        if (CreatedDocument(state, root) is not null && pressedKind is not null && ChoosingKinds.Value.Contains(pressedKind))
        {
            ((JsonObject)state["createdDocuments"]!).Remove(root.ToString(CultureInfo.InvariantCulture));
            return;
        }

        // Revisión 1 de r24 (B2): new controls prove a creation only after a command (data «commandKinds»); a click on a
        // control that chooses or navigates (a tab, a row, a node) brings what was already there.
        bool command = pressedKind is null || CommandKinds.Value.Contains(pressedKind);
        // Encargo EX (tanda n5 t4-c06: «Libro en blanco» on Excel's start page made «Libro1 - Excel» and nothing recorded
        // it): a click decided on a start page, whose title named no document, that left the window titled by a document
        // with no name yet (untitled or an editor's default name, UnnamedDocument) made that document, whatever the
        // control's kind; a name its recent files list may share is no document shown before (the window showed none).
        string? before = (string?)click["titleBefore"];
        bool fromStartPage = before is not null && DocumentPart(before).Length == before.Length && UnnamedDocument(title);
        bool creates = fromStartPage || ((bool?)click["broughtNew"] == true && command) || Regex.IsMatch(
            label, ((string)rules["creatingCommand"]!).Replace("(?P<", "(?<", StringComparison.Ordinal), RegexOptions.CultureInvariant);
        if (!creates || document.Length == 0
            || !(fromStartPage || Regex.IsMatch(document, (string?)rules["untitledDocument"] ?? "$^", RegexOptions.CultureInvariant))
            || (string?)state["tiedDocuments"]?[root.ToString(CultureInfo.InvariantCulture)] == document
            || (before is not null && DocumentKey(before) == document)
            || ContainsRun(Words(label), Words(document))
            || (!fromStartPage && ShownBefore(state, view, Words(document)) && !OneMoreAfterCommand(state, view, click, pressedKind, document)))
            return;
        Remember(state, "createdDocuments", root, document);
        click["createdDocument"] = DocumentPart(title).Trim();
    }

    private static readonly Lazy<HashSet<string>> ChoosingKinds = new(() => new HashSet<string>(
        (ContentErasing["choosingKinds"] as JsonArray ?? []).Select(node => (string?)node ?? string.Empty),
        StringComparer.Ordinal));

    // Revisión 2 de r24 (B1, pasada r23 v3-11: the page list showed seven «Sin título» of the person's before «Agregar
    // página» and eight after): a creation proved by count. The click pressed
    // a known command (data «commandKinds») and the look after it lists one more control named exactly as the untitled
    // document than the look right before it (controlsBeforeClick of that step). The same count proves nothing.
    private static bool OneMoreAfterCommand(JsonObject state, JsonObject view, JsonObject click, string? pressedKind, string document)
    {
        if (pressedKind is null || !CommandKinds.Value.Contains(pressedKind))
            return false;
        string key = ((int?)click["step"])?.ToString(CultureInfo.InvariantCulture) ?? string.Empty;
        if ((state["controlsBeforeClick"]?[key] ?? view["controlsBeforeClick"]?[key]) is not JsonArray before)
            return false;
        // Revisión 3 de r24 (B1): the provider lists the controls of one kind and name once and counts the rest in
        // «repeated»; the look before the click kept those counts (countsBeforeClick) beside its names.
        bool Untitled(string? name) => string.Join(' ', Words(name)) == document;
        JsonObject counted = (state["countsBeforeClick"]?[key] ?? view["countsBeforeClick"]?[key]) as JsonObject ?? new JsonObject();
        int earlier = before.Select(name => (string?)name ?? string.Empty).Distinct(StringComparer.Ordinal).Where(Untitled)
            .Sum(name => counted[name] is JsonValue total && total.TryGetValue(out int many)
                ? many : before.Count(listed => (string?)listed == name));
        int now = ComputerUseSuccessCheck.ComparedControls(view)
            .Where(control => Untitled(ComputerUseSuccessCheck.Fold((string?)control["name"])))
            .Sum(ComputerUseSuccessCheck.Copies);
        return now > earlier;
    }

    // Revisión 1 de r24 (B2): a document of that name some earlier look showed (a
    // page listed by the person, «Sin título» among them): the sub-goal's first look (names and values), the look the
    // mission tied the window on, and the look before every click.
    private static bool ShownBefore(JsonObject state, JsonObject view, string[] document)
    {
        IEnumerable<string?> first = ((string?)state["subgoalFirstText"] ?? (string?)view["subgoalFirstText"] ?? string.Empty)
            .Split('\n').SelectMany(line => line.Split('\t'));
        IEnumerable<string?> listed = new[] { state["controlsBeforeClick"], view["controlsBeforeClick"] }
            .OfType<JsonObject>().SelectMany(looks => looks.Select(entry => entry.Value)).OfType<JsonArray>()
            .SelectMany(names => names.Select(name => (string?)name))
            .Concat((state["tiedShown"] as JsonArray ?? []).Select(name => (string?)name));
        return first.Concat(listed).Any(name => ContainsRun(Words(name), document));
    }

    /// <summary>
    /// Ronda 24b (banco r23 u5, n6): the window shows a new blank document: its title's document part is a name no
    /// document is saved under (data «untitledDocument», «defaultDocument»: «Sin título», «Libro1») and what it holds was
    /// read empty (DocumentContentShown false). Revisión 1 (B2, B3): an unread surface is never blank (an editor that gives no
    /// value for its document, a grid that lists no cell, a canvas with no text). Twin of the mind's _blank_document_shown.
    /// </summary>
    internal static bool BlankDocumentShown(JsonObject view)
    {
        return UnnamedDocument((string?)view["window"]?["title"]) && DocumentContentShown(view) == false;
    }

    /// <summary>
    /// Revisión 3 de r24b (B1): the title names a document no document is saved under (evidence «untitledDocument»,
    /// «defaultDocument»: «Sin título», «Documento1»); the person's «Informe» or «Proyectos» never is.
    /// </summary>
    internal static bool UnnamedDocument(string? title)
    {
        string document = DocumentKey(title);
        JsonObject rules = OperationFloor.EvidenceRules;
        return document.Length > 0
            && (Regex.IsMatch(document, (string?)rules["untitledDocument"] ?? "$^", RegexOptions.CultureInvariant)
                || Regex.IsMatch(document, (string?)rules["defaultDocument"] ?? "$^", RegexOptions.CultureInvariant));
    }

    /// <summary>
    /// Revisión 1 de la ronda 24b (B2, B3), twin of the mind's _document_content: true when something shows the document
    /// holds content (a status count above zero, a document's text that is no placeholder nor an address, a cell's
    /// value); false only when it was read empty (every count zero, or a content surface whose value was read and is
    /// empty, none left unread); null when the view does not read it.
    /// </summary>
    internal static bool? DocumentContentShown(JsonObject view)
    {
        bool? counted = StatusCountShowsContent(view);
        if (counted == true || CellHoldsContent(view))
            return true;
        if (view["window"] is not JsonObject window)
            return counted == false ? false : null;
        var placeholder = new Regex((string?)ContentErasing["placeholder"] ?? "$^", RegexOptions.CultureInvariant);
        JsonObject[] surfaces = (view["controls"] as JsonArray ?? []).OfType<JsonObject>().Append(window["focused"] as JsonObject)
            .OfType<JsonObject>().Where(control => DocumentContent(control, window, readOnlyCounts: false)).ToArray();
        if (surfaces.Select(control => ComputerUseSuccessCheck.Fold((string?)control["value"]).Trim())
            .Any(value => value.Length > 0 && !placeholder.IsMatch(value) && !Address.IsMatch(value)))
            return true;
        if (counted == false)
            return false;
        return surfaces.Length > 0 && surfaces.All(control => control["value"] is not null) ? false : null;
    }

    /// <summary>
    /// Revisión 1 de la ronda 24b (B2), twin of the mind's _status_count_shows_content: what an editor's status text
    /// counts of its document (data «contentCount»: «21 caracteres.», «Mensaje de estado Documento1: 13 caracteres»):
    /// true when a count is above zero, false when every count is zero, null when the view shows none.
    /// </summary>
    internal static bool? StatusCountShowsContent(JsonObject view)
    {
        var count = new Regex((string?)OperationFloor.EvidenceRules["contentCount"] ?? "$^", RegexOptions.CultureInvariant);
        bool? shown = null;
        foreach (JsonObject control in (view["controls"] as JsonArray ?? []).OfType<JsonObject>())
        {
            if ((string?)control["kind"] is not ("Text" or "StatusBar"))
                continue;
            foreach (Match found in count.Matches(ComputerUseSuccessCheck.Fold((string?)control["name"])))
            {
                if (found.Groups[1].Value.Any(digit => digit is >= '1' and <= '9'))
                    return true;
                shown = false;
            }
        }

        return shown;
    }

    /// <summary>
    /// Ronda 24b (u5, n6): a «done» that cites the blank document already in front, with no act of the sub-goal, holds as
    /// it already was: the cited name is the title's document part and the window shows it blank.
    /// </summary>
    internal static bool BlankDocumentAlready(string? cited, JsonObject view, JsonArray subgoalSteps) =>
        !subgoalSteps.OfType<JsonObject>().Any(ComputerUseMission.MayHaveActed)
        && string.Join(' ', Words(cited)) is { Length: > 0 } named
        && named == DocumentKey((string?)view["window"]?["title"])
        && BlankDocumentShown(view);

    // A cell of a grid (DataItem) that holds a value, listed or focused: a sheet with something written in it.
    private static bool CellHoldsContent(JsonObject view) =>
        (view["controls"] as JsonArray ?? []).OfType<JsonObject>().Append(view["window"]?["focused"] as JsonObject)
            .OfType<JsonObject>()
            .Any(control => (string?)control["kind"] == "DataItem" && !string.IsNullOrWhiteSpace((string?)control["value"]));

    /// <summary>Whether the view is of a window the mission's opening started that restored the person's content.</summary>
    internal static bool Restored(JsonObject state, JsonObject? view) =>
        Root(view) is long root && Contains(state["restored"], root);

    // The document the mission created in a window, as its title's words; null when it created none there.
    private static string? CreatedDocument(JsonObject state, long root) =>
        (string?)state["createdDocuments"]?[root.ToString(CultureInfo.InvariantCulture)];

    // Whether a window the mission's opening started already shows text of its own in its document: a content control
    // (DocumentContent) whose value holds text that is no placeholder line (data «contentErasing.placeholder»).
    // Revisión 1 de r24 (B1): a control the provider reads as read-only takes no text (the page of a web application,
    // whose Document's value is its address), the same measure as readOnlyCounts false; nor is an address the text of
    // a document (a page that does not say read-only).
    private static bool HoldsContent(JsonObject view)
    {
        if (view["window"] is not JsonObject window)
            return false;
        var placeholder = new Regex((string?)ContentErasing["placeholder"] ?? "$^", RegexOptions.CultureInvariant);
        return (view["controls"] as JsonArray ?? []).OfType<JsonObject>()
            .Where(control => DocumentContent(control, window, readOnlyCounts: false))
            .Select(control => ComputerUseSuccessCheck.Fold((string?)control["value"]).Trim())
            .Any(value => value.Length > 0 && !placeholder.IsMatch(value) && !Address.IsMatch(value));
    }

    // A value that is only an address (scheme and no spaces): what a web view's Document gives as its value.
    private static readonly Regex Address = new(@"^(?:[a-z][a-z0-9+.\-]*://|about:)\S*$", RegexOptions.CultureInvariant);

    private static void Remember(JsonObject state, string field, long root, string document)
    {
        var map = state[field] as JsonObject ?? new JsonObject();
        map[root.ToString(CultureInfo.InvariantCulture)] = document;
        state[field] = map;
    }

    /// <summary>
    /// The request names the window by its title: every word of the title's first segment (the document, the file,
    /// the dialog, before « - Application» or « • state»), its extension aside, is a word of the request. A title of no
    /// word of three letters names nothing, nor a title that is only the application's own name (the application named
    /// is no document of it: finding 8).
    /// </summary>
    internal static bool NamedByObjective(string? objective, string? title, string? application = null)
    {
        string document = DocumentPart(title);
        string[] named = Words(document);
        if (named.Length == 0 || !named.Any(word => word.Length >= 3))
            return false;
        if (application is { Length: > 0 } && named.SequenceEqual(Words(application)))
            return false;
        var said = new HashSet<string>(Words(objective), StringComparer.Ordinal);
        return named.All(said.Contains) || Words(WithoutExtension(document)) is { Length: > 0 } bare
            && bare.Any(word => word.Length >= 3) && bare.All(said.Contains);
    }

    // The content of a document: the document control itself, or a text area that takes a quarter of the window.
    // Ronda 21 (pasada r18 v3-59): the control the keyboard is known to be on that the provider reads as read-only (a
    // web page that takes no text) is no content an act may alter (<paramref name="readOnlyCounts"/> false); a field the
    // person may write in inside it (a draft) is its own control, judged by itself. Every other measure (the view's
    // controls with no known target, a click) still counts it (revisión 1, hallazgo a). Twin of the mind's
    // cu_lookup.document_content.
    private static bool DocumentContent(JsonObject control, JsonObject window, bool readOnlyCounts = true)
    {
        string? kind = (string?)control["kind"];
        if (!readOnlyCounts
            && ((string?)control["state"] ?? string.Empty).Split(' ', StringSplitOptions.RemoveEmptyEntries).Contains("readonly"))
            return false;
        if (kind == "Document")
            return true;
        if (kind != "Edit" || control["rect"] is not JsonObject rect || window["rect"] is not JsonObject frame)
            return false;
        double area = Number(rect["w"]) * Number(rect["h"]);
        double whole = Number(frame["w"]) * Number(frame["h"]);
        return whole > 0 && area >= whole / 4;
    }

    private static JsonObject? Control(JsonObject view, long index) =>
        (view["controls"] as JsonArray ?? []).OfType<JsonObject>().FirstOrDefault(control => LongOf(control["i"]) == index);

    private static JsonObject? Named(JsonObject view, string? label) =>
        ComputerUseSuccessCheck.Fold(label) is not { Length: > 0 } wanted ? null
        : (view["controls"] as JsonArray ?? []).OfType<JsonObject>()
            .FirstOrDefault(control => ComputerUseSuccessCheck.Fold((string?)control["name"]) == wanted);

    // The person gave input, since the mission's last act (or its start), to a window of the born window's process or
    // of the shell (the taskbar, a folder): they may have opened, restored or started that window themselves.
    private static bool PersonMayHaveBroughtIt(JsonObject state, JsonObject window, DateTimeOffset now)
    {
        if (LongOf(window["personNearAgoMs"]) is not long ago)
            return false;
        string? since = (string?)state["lastActUtc"] ?? (string?)state["startedUtc"];
        if (!DateTimeOffset.TryParse(since, CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out DateTimeOffset acted))
            return true;
        return ago <= (long)(now - acted).TotalMilliseconds;
    }

    // The window came from an item the mission saw listed, clicked or typed by its name (an item of a look, the label
    // of a click, a text it typed): it is that item, opened. A name longer than the item (its extension, its folder)
    // still names it.
    private static bool OpenedItem(JsonObject state, JsonArray steps, string? title)
    {
        string[] document = Words(WithoutExtension(DocumentPart(title)));
        if (document.Length == 0 || !document.Any(word => word.Length >= 3)
            || (string?)state["application"] is { Length: > 0 } application && document.SequenceEqual(Words(application)))
            return false;
        IEnumerable<string?> names = steps.OfType<JsonObject>()
            .SelectMany(step => new[] { (string?)step["label"], (string?)step["text"] });
        // Encargo H1 (tandas fin1/fin2 t4-c06: the start page listed the recent «Libro1.xlsx», the click on «Libro en
        // blanco» made «Libro1 - Excel», and the mission refused it and stopped as if its window had closed): a title
        // that names a document the way an editor names a new one (UnnamedDocument: «Libro1», «Sin título») is an item
        // only by what the mission pressed or typed, or after a key, which acts on the item listed in focus.
        if (!UnnamedDocument(title) || steps.OfType<JsonObject>()
                .Any(step => (string?)step["operation"] == "input.key.press" && (bool?)step["ok"] == true))
        {
            names = names
                .Concat((state["controlsBeforeClick"] as JsonObject ?? new JsonObject()).Select(entry => entry.Value)
                    .OfType<JsonArray>().SelectMany(list => list.Select(name => (string?)name)))
                .Concat((state["itemsSeen"] as JsonArray ?? []).Select(name => (string?)name));
        }

        return names.Any(name => ContainsRun(Words(name), document));
    }

    // Whether the words of a name hold the words of a document, in a row.
    private static bool ContainsRun(string[] words, string[] run)
    {
        for (int start = 0; start + run.Length <= words.Length; start++)
        {
            if (words.AsSpan(start, run.Length).SequenceEqual(run))
                return true;
        }

        return false;
    }

    private static bool OpenedByTheMission(JsonArray steps)
    {
        JsonObject? opening = steps.OfType<JsonObject>().LastOrDefault(step => ComputerUseMission.OpensTheWindow((string?)step["operation"] ?? string.Empty));
        return opening is not null && (bool?)opening["ok"] == true
            && ((string?)opening["operation"] == "file.open" || (bool?)opening["alreadyRunning"] != true);
    }

    // The mission's last opening started the application itself (not a file of the person's).
    private static bool OpenedTheApplication(JsonArray steps) =>
        (string?)steps.OfType<JsonObject>()
            .LastOrDefault(step => ComputerUseMission.OpensTheWindow((string?)step["operation"] ?? string.Empty))?["operation"]
        == "app.open";

    private static string? Objective(JsonObject state) => (string?)state["objective"] ?? (string?)state["goal"];

    // A title's first segment: the document or the dialog, before « - » and the application's name, or « • » and its
    // state («Guardado»).
    private static string DocumentPart(string? title) =>
        Regex.Split(title ?? string.Empty, @"\s+[-–—|•·]\s+")[0];

    // The document a title shows, as words (a mark of unsaved changes aside).
    internal static string DocumentKey(string? title) => string.Join(' ', Words(DocumentPart(title)));

    private static string WithoutExtension(string? name)
    {
        string text = (name ?? string.Empty).Trim();
        int dot = text.LastIndexOf('.');
        return dot > 0 && text.Length - dot - 1 is >= 1 and <= 4 && text[(dot + 1)..].All(char.IsLetterOrDigit)
            ? text[..dot]
            : text;
    }

    private static string[] Words(string? text) =>
        ComputerUseSuccessCheck.Fold(text).Split(
            [.. ComputerUseSuccessCheck.Fold(text).Where(character => !char.IsLetterOrDigit(character)).Distinct()],
            StringSplitOptions.RemoveEmptyEntries);

    private static void Add(JsonObject state, string field, long hwnd)
    {
        var list = state[field] as JsonArray ?? new JsonArray();
        if (!Contains(list, hwnd))
            list.Add(hwnd);
        state[field] = list;
    }

    private static bool Contains(JsonNode? list, long hwnd) =>
        list is JsonArray array && array.Any(node => LongOf(node) == hwnd);

    internal static long? LongOf(JsonNode? node)
    {
        if (node is not JsonValue value)
            return null;
        if (value.TryGetValue(out long whole))
            return whole;
        if (value.TryGetValue(out int small))
            return small;
        return value.TryGetValue(out double real) && real == Math.Floor(real) ? (long)real : null;
    }

    private static double Number(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out double real) ? real : LongOf(node) ?? 0;
}
