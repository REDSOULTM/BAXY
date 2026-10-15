using System.Globalization;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Baxy.App;

// Arriving at a place: the «page:» atom, a click on the place that left the page or the tree as it was, the page's
// title and header, and where a click went.
internal static partial class ComputerUseSuccessCheck
{
    // «ir a X» on a window drawn without an accessible tree (CEF, Electron, canvas; measured on Steam): X is still on
    // screen, a verified click went there, and most of the written text is new against the first look of the
    // application's own window. A menu the click opened changes a few lines (Steam: 3 of 25); the page reached
    // changes most of them.
    private static bool PageAtom(string rest, JsonObject view, JsonArray steps)
    {
        // Only a window without an accessible tree (CEF, canvas) is judged by its written text; where controls exist,
        // arriving is the place selected or titled (measured on Discord: «Cotele» written in an activity card passed
        // for the channel while the Friends page was open).
        // Encargo S13 (banco fq1–fq3 s13 t3 «andá a configuración» in Discord): «Ajustes de usuario» pressed opened the
        // settings over «Amigos - Discord», whose title stays; the heading «Barra lateral de ajustes» it brought is the
        // page reached, as «header:» judges it (HeaderAppeared), and the mission pressed it again until out of steps.
        if (ComputerUseMission.ActionableCount(view) > 1)
        {
            return ALastClickOpened(rest, view, steps) || HeaderNames(view, rest, steps) || HeaderAppeared(rest, view, steps)
                || FocusedIntoThePlace(view, Fold(rest), steps);
        }

        if (AddressNames(view, rest))
        {
            // The page's own address written on screen names the place (measured on Steam, which opens on its store:
            // «https://store.steampowered.com/»): it is that page's title, wherever the mission started.
            return true;
        }

        int? click = AClickWentTo(rest, steps, view);
        if (!ViewContains(view, rest) || click is null)
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

        // A window left exactly as it was is not proof of being there: the page reached may not be drawn yet when the
        // next look comes (≈150 ms); a place already open is told by its address (AddressNames).
        int kept = current.Count(line => baseline.Contains((string?)line ?? string.Empty));
        return kept * 2 < current.Count;
    }

    /// <summary>
    /// A window without an accessible tree whose last verified step in the sub-goal was a click on the place's own name
    /// («BIBLIOTECA» for «ir a biblioteca»), the name still written on screen, and the text kept what it showed right
    /// before that click (at most a menu opened under it, ≥ 80 % of the lines the same): the window was probably on the
    /// place already (live 2026-10-07 v2-s12, v2-c17: Steam on its library, the learned click only opened the menu).
    /// Never proof of arriving (a click that only opens a word's menu on another page reads the same): only the honest
    /// stop «parece que ya estabas en X, pero no pude confirmarlo». A covered window is judged like any other: since v3
    /// point 0 its written text comes from the window's own drawing, never from the screen where the cover is.
    /// </summary>
    internal static bool ClickedPlaceLeftPageAsIs(string place, JsonArray subgoalSteps, JsonObject view, JsonObject state)
    {
        if (ComputerUseMission.ActionableCount(view) > 1)
        {
            return ClickedPlaceLeftTreeAsIs(place, subgoalSteps, view);
        }

        string target = Fold(place);
        if (target.Length < 3 || !ViewContains(view, place))
        {
            return false;
        }

        JsonObject? last = subgoalSteps.OfType<JsonObject>().LastOrDefault(step => (bool?)step["ok"] == true);
        if (last is null || !Pressed(last)
            || PlaceClicked(last, view) != target
            || (int?)last["step"] is not int clickStep
            || state["textBeforeClick"]?[clickStep.ToString(CultureInfo.InvariantCulture)] is not JsonArray before)
        {
            return false;
        }

        var baseline = new HashSet<string>(before.Select(line => (string?)line ?? string.Empty), StringComparer.Ordinal);
        JsonArray current = TextLines(view);
        if (baseline.Count < 5 || current.Count < 5)
        {
            return false;
        }

        // The place's row marking another of its labels (contract §1.7) says the window is on that other page (v3
        // punto 5 contracase: the launcher on its store, «TIENDA» blue, the click on «BIBLIOTECA» only opened its menu).
        if (AnotherLabelMarked(target, view))
        {
            return false;
        }

        int kept = current.Count(line => baseline.Contains((string?)line ?? string.Empty));
        return kept * 10 >= current.Count * 8;
    }

    /// <summary>
    /// Pasada r15b t-scroll-3: the mission itself brought the window where it is — a step before the last one opened
    /// the application, changed what the window showed, typed or scrolled (Settings was found already open; the
    /// mission then went to Personalización and Fuentes, typed, scrolled and clicked «Times New Roman»). A last click
    /// on the place that leaves it as it was then says nothing about the window having been there before: never
    /// «parece que ya estabas». An application found already running and a click that changed nothing do not count
    /// (live v2-s12: Steam already on its library).
    /// Review of the branch (finding 1): RecordResponse marks every ok app.open and input.key.press <c>changed</c>
    /// whatever they did, so for those two <c>changed</c> says nothing. An app.open moved the window only when it
    /// launched the application (<c>alreadyRunning</c> false, the receipt always says it) or made a new document; a key
    /// press only when its receipt saw the surface change. Otherwise almost every mission, which begins with app.open,
    /// would never stop as already there.
    /// </summary>
    internal static bool MissionMovedTheWindow(JsonArray steps)
    {
        List<JsonObject> done = steps.OfType<JsonObject>().Where(step => (bool?)step["ok"] == true).ToList();
        return done.Take(Math.Max(0, done.Count - 1)).Any(step => (string?)step["operation"] switch
        {
            "app.open" => (bool?)step["alreadyRunning"] == false || (bool?)step["newDocument"] == true
                || (bool?)step["placeOpened"] == true,
            "input.key.press" => (bool?)step["surfaceChanged"] == true,
            "input.text.type" or "input.scroll" => true,
            _ => (bool?)step["surfaceChanged"] == true || (bool?)step["changed"] == true,
        });
    }

    // The kinds of control a person clicks to go somewhere: a menu bar's item, a combo box or a split button open
    // something over the page instead.
    private static readonly HashSet<string> NavigationKinds = new(StringComparer.Ordinal)
    {
        "Button", "Hyperlink", "ListItem", "TabItem", "TreeItem", "Text", "Custom", "Group",
    };

    // What a click that opens something over the page brings: a menu, a list or a window of its own.
    private static readonly HashSet<string> OpenedKinds = new(StringComparer.Ordinal)
    {
        "Menu", "MenuItem", "List", "ListItem", "Window", "ToolTip",
    };

    /// <summary>
    /// Regresiones r2 M3 (live v8, a music player already on its home page): the same honest stop as
    /// <see cref="ClickedPlaceLeftPageAsIs"/> on a window with an accessible tree. The sub-goal's last step was a
    /// verified click on a navigation control named as the place («Inicio», «Ir a Inicio»), a control named so is still
    /// there, and the window kept what it listed right before that click: under 10 % of its controls new and under
    /// 10 % gone, no menu, list or window opened (a new menu item, list item or window among them), the clicked control
    /// not left expanded, and no other item chosen instead. Never proof of arriving: only «parece que ya estabas en X».
    /// A click that opened a menu, or a page that changed, never counts. Nor does a click that chose the place itself
    /// (review r4: the place selected now and not before the click, by the view or by the click's own receipt, is a
    /// navigation, the very opposite of being there already), nor a look that listed as many controls as a look lists
    /// (<see cref="ComputerUseMission.ViewControlLimit"/>): the part of the window that changed may be past what it lists.
    /// </summary>
    internal static bool ClickedPlaceLeftTreeAsIs(string place, JsonArray subgoalSteps, JsonObject view)
    {
        string target = Fold(place);
        if (!ClickedThePlace(place, subgoalSteps, view) || ComputerUseMission.ActionableCount(view) <= 1
            || view["controls"] is not JsonArray controls || subgoalSteps[^1] is not JsonObject last
            || ((string?)last["kind"] is { Length: > 0 } kind && !NavigationKinds.Contains(kind)))
        {
            return false;
        }

        string clicked = Fold((string?)last["label"]);
        List<JsonObject> listed = controls.OfType<JsonObject>().ToList();
        if (!listed.Any(control => WithoutAppName(WithoutOpening(Fold((string?)control["name"])), view) == target))
        {
            return false;
        }

        string key = ((int?)last["step"] ?? subgoalSteps.Count).ToString(CultureInfo.InvariantCulture);
        if (view["controlsBeforeClick"]?[key] is not JsonArray earlier)
        {
            return false;
        }

        // A look at its limit is taken as covering the window only when the window's written text, read from its whole
        // drawing, also kept what it showed before the click (regresiones r4, live v8: a music player lists its 60 on
        // every page, so «ya estabas» never held there and the mission stopped with «no vi un control con el que seguir»).
        if ((listed.Count >= ComputerUseMission.ViewControlLimit || earlier.Count >= ComputerUseMission.ViewControlLimit)
            && !TextKeptSinceClick(view, key))
        {
            return false;
        }

        var seenBefore = new HashSet<string>(earlier.Select(node => (string?)node ?? string.Empty), StringComparer.Ordinal);
        var now = new HashSet<string>(ControlNames(view).Select(node => (string?)node ?? string.Empty), StringComparer.Ordinal);
        if (seenBefore.Count < 5 || now.Count < 5)
        {
            return false;
        }

        int fresh = now.Count(name => !seenBefore.Contains(name));
        int gone = seenBefore.Count(name => !now.Contains(name));
        if (fresh * 10 >= now.Count || gone * 10 >= seenBefore.Count)
        {
            return false;
        }

        if (listed.Any(control => (string?)control["kind"] is { } opened && OpenedKinds.Contains(opened)
                && (bool?)control["reserved"] != true
                && Fold((string?)control["name"]) is { Length: > 0 } name && !seenBefore.Contains(name))
            || listed.Any(control => Fold((string?)control["name"]) == clicked
                && ((string?)control["state"] ?? string.Empty).Split(' ').Contains("expanded", StringComparer.Ordinal)))
        {
            return false;
        }

        var chosenBefore = new HashSet<string>(
            (view["selectedBeforeClick"]?[key] as JsonArray ?? []).Select(node => (string?)node ?? string.Empty),
            StringComparer.Ordinal);
        List<string> chosenNow = SelectedNames(view).Select(node => (string?)node ?? string.Empty).ToList();
        bool placeChosenBefore = chosenBefore.Any(name => WithoutAppName(name, view) == target);
        if (!placeChosenBefore
            && ((bool?)last["selected"] == true || chosenNow.Any(name => WithoutAppName(name, view) == target)))
        {
            return false;
        }

        // Recibo del clic por estado (r15b v3-52, los ajustes de un programa Qt: «General» elegida antes y después, la
        // fila «Vídeo» pulsada sin quedar elegida y la imagen cambiada sólo por el foco): en un lugar que se elige, otra
        // fila de su lista elegida y el lugar no es un clic sin efecto, nunca «ya estabas».
        // Revisión de la rama (hallazgos 4 y 5): «selectable» llega del recibo al paso; y «otra fila de su lista» es otro
        // elemento elegido del tipo del lugar y de su zona (una pestaña elegida en otro panel no es de su lista).
        JsonObject? placeShown = listed.FirstOrDefault(control =>
            WithoutAppName(WithoutOpening(Fold((string?)control["name"])), view) == target);
        string placeKind = (string?)last["kind"] is { Length: > 0 } receiptKind ? receiptKind : (string?)placeShown?["kind"] ?? string.Empty;
        if (((bool?)last["selectable"] == true || SelectableKinds.Contains(placeKind))
            && placeKind.Length > 0
            && OthersChosenInItsList(listed, placeShown, placeKind, target, view))
        {
            return false;
        }

        return !chosenNow.Any(name => !chosenBefore.Contains(name));
    }

    // The place a click's label names: folded, without the act of opening it said first or the application's name after.
    private static string PlaceClicked(JsonObject click, JsonObject view) =>
        WithoutAppName(WithoutOpening(Fold((string?)click["label"])), view);

    /// <summary>The sub-goal's last step was a verified press of a control named as the place, or as the act of opening it.</summary>
    internal static bool ClickedThePlace(string place, JsonArray subgoalSteps, JsonObject view) =>
        Fold(place) is { Length: >= 3 } target && subgoalSteps.Count > 0 && subgoalSteps[^1] is JsonObject last
        && Pressed(last) && (bool?)last["ok"] == true && PlaceClicked(last, view) == target;

    // Otro elemento elegido de la lista del lugar: del mismo tipo y, cuando ambos la dicen, de la misma zona.
    private static bool OthersChosenInItsList(
        List<JsonObject> listed, JsonObject? place, string kind, string target, JsonObject view)
    {
        if (place is not null && ((string?)place["state"] ?? string.Empty).Split(' ').Contains("selected", StringComparer.Ordinal))
        {
            return false;
        }

        string? zone = (string?)place?["zone"] is { Length: > 0 } placeZone ? placeZone : null;
        return listed.Any(control => !ReferenceEquals(control, place)
            && (string?)control["kind"] == kind
            && ((string?)control["state"] ?? string.Empty).Split(' ').Contains("selected", StringComparer.Ordinal)
            && WithoutAppName(Fold((string?)control["name"]), view) != target
            && (zone is null || (string?)control["zone"] is not { Length: > 0 } otherZone || otherZone == zone));
    }

    // Lo que una lista, un árbol o unas pestañas eligen al pulsarlo: su estado «selected» dice dónde está la ventana.
    private static readonly HashSet<string> SelectableKinds = new(StringComparer.Ordinal)
    {
        "ListItem", "TreeItem", "TabItem", "DataItem",
    };

    // The written text of the look right before click «key» and of this look, both of at least five lines, with under
    // 10 % of the lines new and under 10 % gone: the measure the controls are judged by.
    private static bool TextKeptSinceClick(JsonObject view, string key)
    {
        if (view["textBeforeClick"]?[key] is not JsonArray before)
        {
            return false;
        }

        var earlier = new HashSet<string>(before.Select(line => (string?)line ?? string.Empty), StringComparer.Ordinal);
        var now = new HashSet<string>(TextLines(view).Select(line => (string?)line ?? string.Empty), StringComparer.Ordinal);
        if (earlier.Count < 5 || now.Count < 5)
        {
            return false;
        }

        return now.Count(line => !earlier.Contains(line)) * 10 < now.Count
            && earlier.Count(line => !now.Contains(line)) * 10 < earlier.Count;
    }

    // Another label than «target» passes mark: on this view (MarkedLabels: the row MarkAtom reads, its one judge).
    private static bool AnotherLabelMarked(string target, JsonObject view) =>
        MarkedLabels(view).Any(label => Fold(label).Trim(LabelEdges) != target);

    // Where controls exist, the last verified click went to a control named as the place itself, or as the act of
    // opening it («Abre Tu biblioteca», «Ir a Inicio», «Open Settings»; data «computerUse.placeToggle.opening»), and the
    // place is still on screen. A control that merely contains the name (an activity card «Choche Cotele!!!» on
    // Discord's Friends page) does not count.
    // A folded label without the act of opening it said first («abre tu biblioteca» is «tu biblioteca»).
    private static string WithoutOpening(string label) =>
        WithoutVerb(label, [.. OperationFloor.PlaceOpeningVerbs, .. OperationFloor.PlaceLeadingVerbs]);

    private static string WithoutVerb(string label, IReadOnlyList<string> verbs)
    {
        foreach (string verb in verbs)
        {
            if (label.StartsWith(verb, StringComparison.Ordinal))
            {
                return label[verb.Length..];
            }
        }

        return label;
    }

    // The place an atom names when it names one: «page:», «title:», «mark:» and «control:X» current or selected.
    private static string? PlaceOfAtom(string kind, string rest)
    {
        if (kind is "page" or "title" or "mark")
        {
            return rest;
        }

        int split = rest.LastIndexOf(':');
        string name = split > 0 && rest[(split + 1)..] is "current" or "selected" ? rest[..split] : rest;
        return kind == "control" && (split <= 0 || name.Length < rest.Length) ? name.TrimStart('=') : null;
    }

    // An article or a possessive said before a place's name («tu biblioteca», «the library»).
    private static readonly Regex PlaceArticle = new(@"^(?:el|la|los|las|tu|tus|the|my|your)\s+", RegexOptions.CultureInvariant);

    /// <summary>
    /// Encargo S (banco e1/e2 u1, y8): a place the window opens and closes with its own button (a player's library is a
    /// panel: «Abre Tu biblioteca» opens it, «Comprimir Tu biblioteca» is there only while it is open) is open or closed
    /// by that button, whatever else on the screen carries its name (a stranger's list «Tu biblioteca» opened from a
    /// search, its page titled so) and whichever step opened it (a press whose post-read did not hold, a panel drawn
    /// after the look that followed the press). True when a Button names the place after a closing verb (data
    /// «computerUse.placeToggle.closing»), false when one names it only after an opening verb, null when the window has
    /// no such button (the place is judged as before). Twin of the mind's cu_lookup.own_place_button.
    /// </summary>
    internal static bool? PlaceToggle(string place, JsonObject view)
    {
        string target = PlaceArticle.Replace(Fold(place).Trim(), string.Empty).Trim();
        if (target.Length < 3 || view["controls"] is not JsonArray controls)
        {
            return null;
        }

        bool? open = null;
        foreach (JsonObject control in controls.OfType<JsonObject>().Where(control => (string?)control["kind"] == "Button"))
        {
            string name = Fold((string?)control["name"]).Trim();
            foreach ((IReadOnlyList<string> verbs, bool said) in new[] { (OperationFloor.PlaceClosingVerbs, true), (OperationFloor.PlaceOpeningVerbs, false) })
            {
                string rest = WithoutVerb(name, verbs);
                if (rest.Length == name.Length)
                {
                    continue;
                }

                if (PlaceArticle.Replace(rest.Trim(), string.Empty).Trim() == target)
                {
                    if (said)
                    {
                        return true;
                    }

                    open = false;
                }

                break;
            }
        }

        return open;
    }

    /// <summary>
    /// Encargo IMP3 (imp2 imp-wa-abrir, notebook: the search result «Música 29/9/2026» pressed opened the group, its
    /// message box «Escribir un mensaje para el grupo Música» took the keyboard, and the mission went on pressing other
    /// results for 12 steps): the latest verified click of the sub-goal put the keyboard into a text field new with it
    /// whose name names the place as whole words, and that is no search box: the place's own box (a chat's message box,
    /// «Mensaje @Ron92»). A search box naming the place, a field that was there before the click and before the
    /// sub-goal's first click, or a keyboard that did not move proves nothing.
    /// </summary>
    internal static bool FocusedIntoThePlace(JsonObject view, string target, JsonArray steps)
    {
        if (target.Length < 3 || view["window"]?["focused"] is not JsonObject focused || (string?)focused["kind"] != "Edit")
        {
            return false;
        }

        string name = Fold((string?)focused["name"]);
        if (IsSearchBox((string?)focused["name"])
            || !Regex.IsMatch(name, $@"(?<!\w){Regex.Escape(target)}(?!\w)", RegexOptions.CultureInvariant))
        {
            return false;
        }

        JsonObject? last = steps.OfType<JsonObject>().LastOrDefault(step => (bool?)step["ok"] == true);
        if (last is null || !Pressed(last) || last["step"] is not JsonValue number || !number.TryGetValue(out int step))
        {
            return false;
        }

        string key = step.ToString(CultureInfo.InvariantCulture);
        // Encargo TZ-DC3 (zt3 imp-wa-abrir): new with the latest click or with the sub-goal. «Abuela» pressed in the chat
        // list opened the chat only after the look that followed (the window, under the person's, drew it late); each
        // later press of «Abuela» put the keyboard into its box, which the look before that press already listed, and the
        // mission went on for 10 steps with the chat open and ended «No pude llegar». A box absent from the look before
        // the sub-goal's first click came with the sub-goal.
        string? first = steps.OfType<JsonObject>()
            .Where(done => Pressed(done) && done["step"] is JsonValue)
            .Select(done => ((JsonValue)done["step"]!).TryGetValue(out int at) ? at.ToString(CultureInfo.InvariantCulture) : null)
            .FirstOrDefault(at => at is not null);
        return view["focusBeforeStep"]?[key] is JsonValue before && before.TryGetValue(out string? focusBefore)
            && focusBefore != FocusSignature(view)
            && new[] { key, first }.Any(at => at is not null && view["controlsBeforeClick"]?[at] is JsonArray earlier
                && !earlier.Any(node => Fold((string?)node) == name));
    }

    private static bool ALastClickOpened(string place, JsonObject view, JsonArray steps)
    {
        string target = Fold(place);
        if (target.Length < 3 || !ViewContains(view, place))
        {
            return false;
        }

        for (int index = steps.Count - 1; index >= 0; index--)
        {
            if (steps[index] is not JsonObject step || (string?)step["operation"] is not "input.visible.click")
            {
                continue;
            }

            if ((bool?)step["ok"] != true || OnlyOpened(step))
            {
                return false;
            }

            string label = PlaceClicked(step, view);
            if (label != target)
            {
                return false;
            }

            // The click made another item the chosen one: it landed elsewhere (measured on Explorer: «Downloads»
            // clicked, «Imágenes» became selected and the mission said it was in Descargas).
            string key = ((int?)step["step"] ?? index + 1).ToString(CultureInfo.InvariantCulture);
            var before = new HashSet<string>(
                (view["selectedBeforeClick"]?[key] as JsonArray ?? []).Select(node => (string?)node ?? string.Empty),
                StringComparer.Ordinal);
            var chosenNow = new HashSet<string>(SelectedNames(view).Select(node => (string?)node ?? string.Empty), StringComparer.Ordinal);
            bool selectionMoved = before.Any(name => !chosenNow.Contains(name));
            HashSet<string>? seenBefore = view["controlsBeforeClick"]?[key] is JsonArray earlier
                ? new HashSet<string>(earlier.Select(node => (string?)node ?? string.Empty), StringComparer.Ordinal)
                : null;
            if (selectionMoved && chosenNow.Any(name => !before.Contains(name) && !name.Contains(target, StringComparison.Ordinal)
                    && (seenBefore is null || seenBefore.Contains(name))))
            {
                // A value chosen inside the page reached («Oscuro» in Colores) is not a move: only a selection that
                // left the item chosen before for another one the click could have landed on (shown before it) is.
                // An item the page reached brings chosen is part of it (measured 2026-10-07 on the Calculator, from
                // Programador to Científica: the new page's «Historial» tab, absent before, came selected).
                return false;
            }

            // And the window shows something else than before the click: most of its controls are new (a panel opened,
            // a page loaded). A click that left the same controls did not go anywhere (measured on Settings: the
            // «Colores» card clicked, Personalización still shown, the mission said it was in Colores).
            if (seenBefore is null)
            {
                return false;
            }

            // A side panel opened beside a full page leaves most controls where they were (measured 2026-10-07 on
            // Spotify after «Inicio»: «Abre Tu biblioteca» clicked, the panel open, 8 of 60 controls new): its own
            // button says it (PlaceToggle, encargo S), not this click.
            JsonArray now = ControlNames(view);
            int fresh = now.Count(node => !seenBefore.Contains((string?)node ?? string.Empty));
            return now.Count > 0 && fresh * 10 >= now.Count * 4;
        }

        return false;
    }

    // The page's own header names the place: a control called exactly that at the top of the window and nowhere in its
    // body or side (measured on Settings: on Colores, «Colores» is the last link of the header «Personalización >
    // Colores»; on Personalización it is a card in the body, which does not count). Only the header's own zone (T, or
    // TL where a lone heading of a maximized window lands; never the toolbars of TR), only the last item of its row (a
    // breadcrumb ends where the window is; a tab strip or a toolbar has more controls to its right), and only once
    // something brought the window there in this sub-goal (a verified click, or an opening of the application on a
    // place by its address: estabilización G2, Settings' sections in app_places.v1.json) or the window's title names
    // the place: the first look of a sub-goal is not an arrival.
    private static bool HeaderNames(JsonObject view, string place, JsonArray steps)
    {
        string target = Fold(place);
        if (target.Length < 3 || view["controls"] is not JsonArray controls)
        {
            return false;
        }

        bool clicked = steps.OfType<JsonObject>().Any(step => (bool?)step["ok"] == true
            && (Pressed(step) || ((string?)step["operation"] == "app.open" && (bool?)step["placeOpened"] == true)));
        bool titled = Fold((string?)view["window"]?["title"]).Contains(target, StringComparison.Ordinal)
            || Fold(PageTitle(view)).Contains(target, StringComparison.Ordinal);
        if (!clicked && !titled)
        {
            return false;
        }

        bool inHeader = false;
        foreach (JsonObject control in controls.OfType<JsonObject>())
        {
            if (Fold((string?)control["name"]) != target)
            {
                continue;
            }

            // A link named as the place leads to it: it is not where the window is (pasada v3 r9, v3-42: on the Control
            // Panel's «Programas» page the link «Programas y características», alone on its row at the top left, passed
            // for that page, which was never opened).
            if ((string?)control["zone"] is not ("T" or "TL") || (string?)control["kind"] is not ("Text" or "Button")
                || !LastOfItsRow(control, controls))
            {
                return false;
            }

            inHeader = true;
        }

        return inHeader;
    }

    /// <summary>
    /// Ronda 24b (x10): the place a reached term named, spelled as the window writes it: the mark's own text, the words
    /// of the window's or the page's title that fold to it, the name of the control or header that bears it. Only the
    /// atoms that name a place (mark, title, control, page, header); empty when the view does not write it.
    /// r30 (bancos Br28 y Bb3tb: e2, v7, x9, y6, «seleccionar eraser» closed on its verified click on «Borrador» and
    /// the model worded the final): the control a verified click of <paramref name="steps"/> pressed, when the term
    /// names that click (stepDone:input.visible.click:=borrador), by the click's own name.
    /// </summary>
    internal static string ArrivedAs(string? satisfiedBy, JsonObject view, JsonArray? steps = null)
    {
        if (string.IsNullOrWhiteSpace(satisfiedBy) || satisfiedBy == "model_evidence")
        {
            return string.Empty;
        }

        const string click = "input.visible.click";
        foreach (string atom in satisfiedBy.Split('&', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            int colon = atom.IndexOf(':', StringComparison.Ordinal);
            string kind = ComputerUseMission.AtomKindOf(atom);
            if (colon <= 0 || kind is not ("mark" or "title" or "control" or "page" or "header" or "stepdone"))
            {
                continue;
            }

            string rest = atom[(colon + 1)..].Trim();
            if (kind == "stepdone")
            {
                if (!rest.StartsWith(click + ":", StringComparison.Ordinal))
                {
                    continue;
                }

                rest = rest[(click.Length + 1)..].TrimStart('=');
            }

            if (kind == "control")
            {
                int split = rest.LastIndexOf(':');
                if (split > 0 && rest[(split + 1)..] is "selected" or "current" or "on" or "off" or "expanded" or "focused" or "collapsed")
                {
                    rest = rest[..split];
                }

                rest = rest.TrimStart('=');
            }

            string target = Fold(rest).Trim(LabelEdges);
            if (target.Length == 0)
            {
                continue;
            }

            var sources = new List<string?>();
            if (kind == "mark" && view["textMarks"] is JsonArray marks)
            {
                sources.AddRange(marks.OfType<JsonObject>().Select(mark => (string?)mark["text"]));
            }

            if (kind is "control" or "page" or "header" && view["controls"] is JsonArray controls)
            {
                sources.AddRange(controls.OfType<JsonObject>()
                    .Where(control => (string?)control["kind"] is not ("Edit" or "ComboBox" or "Document"))
                    .Select(control => (string?)control["name"]));
            }

            if (kind == "stepdone")
            {
                sources.AddRange((steps ?? []).OfType<JsonObject>()
                    .Where(step => (bool?)step["ok"] == true && (string?)step["operation"] == click)
                    .Select(step => (string?)step["name"]));
            }
            else
            {
                sources.Add((string?)view["window"]?["title"]);
                sources.Add(PageTitle(view));
            }

            foreach (string? source in sources)
            {
                if (WordsSpelling(source, target) is { Length: > 0 } spelled)
                {
                    return spelled;
                }
            }
        }

        return string.Empty;
    }

    // The run of whole words of <paramref name="source"/> that folds to <paramref name="target"/>, as written.
    private static string WordsSpelling(string? source, string target)
    {
        string[] words = (source ?? string.Empty).Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
        for (int from = 0; from < words.Length; from++)
        {
            for (int to = from; to < words.Length; to++)
            {
                string run = string.Join(' ', words[from..(to + 1)]).Trim(LabelEdges);
                string folded = Fold(run).Trim(LabelEdges);
                if (folded == target)
                {
                    return run;
                }

                if (folded.Length > target.Length)
                {
                    break;
                }
            }
        }

        return string.Empty;
    }

    /// <summary>
    /// Ronda 24b (u9): the title of the page a window shows, which in a web view embedded in an application (CEF,
    /// Electron, WebView2) is the name of its root document, never the window's title. The root is the document whose
    /// value is the address an address field of the view holds; with no address field, the largest document whose
    /// rectangle covers at least half the window. A document nested inside the page (a frame, a card) is never it.
    /// Empty when the view shows none.
    /// </summary>
    internal static string PageTitle(JsonObject view)
    {
        if (view["controls"] is not JsonArray controls)
        {
            return string.Empty;
        }

        JsonObject[] documents = [.. controls.OfType<JsonObject>()
            .Where(control => (string?)control["kind"] == "Document" && !string.IsNullOrWhiteSpace((string?)control["name"]))];
        if (documents.Length == 0)
        {
            return string.Empty;
        }

        var addresses = new HashSet<string>(
            controls.OfType<JsonObject>().Where(control => (string?)control["kind"] == "Edit")
                .Select(control => WebAddress((string?)control["value"])).Where(address => address.Length > 0),
            StringComparer.Ordinal);
        JsonObject? root;
        if (addresses.Count > 0)
        {
            root = documents.Where(document => addresses.Contains(WebAddress((string?)document["value"])))
                .OrderByDescending(PageArea).FirstOrDefault();
        }
        else
        {
            double window = view["window"]?["rect"] is JsonObject rect ? Number(rect["w"]) * Number(rect["h"]) : 0;
            root = window <= 0 ? null : documents.Where(document => PageArea(document) * 2 >= window)
                .OrderByDescending(PageArea).FirstOrDefault();
        }

        return ((string?)root?["name"])?.Trim() ?? string.Empty;
    }

    private static double PageArea(JsonObject control) =>
        control["rect"] is JsonObject box ? Math.Max(0, Number(box["w"])) * Math.Max(0, Number(box["h"])) : 0;

    // A web address as written in a field or a document's value, without its scheme, «www.» or closing slash; empty
    // for anything that is not one (spaces, no dot).
    private static string WebAddress(string? value)
    {
        string text = (value ?? string.Empty).Trim().ToLowerInvariant();
        int scheme = text.IndexOf("://", StringComparison.Ordinal);
        if (scheme > 0)
        {
            text = text[(scheme + 3)..];
        }

        if (text.StartsWith("www.", StringComparison.Ordinal))
        {
            text = text[4..];
        }

        text = text.TrimEnd('/');
        return text.Length >= 4 && !text.Contains(' ', StringComparison.Ordinal) && text.Contains('.', StringComparison.Ordinal)
            ? text : string.Empty;
    }

    // No other control starts further right on the same row (its vertical middle inside this control's height). A
    // control without a rectangle cannot be placed and is not the last of anything.
    private static bool LastOfItsRow(JsonObject control, JsonArray controls)
    {
        if (control["rect"] is not JsonObject rect || Number(rect["w"]) <= 0 || Number(rect["h"]) <= 0)
        {
            return false;
        }

        double left = Number(rect["x"]);
        double top = Number(rect["y"]);
        double bottom = top + Number(rect["h"]);
        foreach (JsonObject other in controls.OfType<JsonObject>())
        {
            if (ReferenceEquals(other, control) || other["rect"] is not JsonObject otherRect || Number(otherRect["h"]) <= 0)
            {
                continue;
            }

            double middle = Number(otherRect["y"]) + (Number(otherRect["h"]) / 2);
            if (middle >= top && middle <= bottom && Number(otherRect["x"]) > left)
            {
                return false;
            }
        }

        return true;
    }

    private static double Number(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out double number) ? number
        : node is JsonValue integer && integer.TryGetValue(out int whole) ? whole
        : 0;

    // «header:X» (a mode or a page the window shows in its heading, measured on the Calculator: «Modo de calculadora
    // Científica»): the last verified click named X, and a written heading (a Text control at the top: T, TL or TR)
    // naming X is on screen now and was not before that click. A heading already there proves nothing the click did.
    private static bool HeaderAppeared(string place, JsonObject view, JsonArray steps)
    {
        string target = Fold(place);
        if (target.Length == 0 || view["controls"] is not JsonArray)
        {
            return false;
        }

        JsonObject? click = null;
        int position = 0;
        for (int index = steps.Count - 1; index >= 0 && click is null; index--)
        {
            if (steps[index] is JsonObject step && (string?)step["operation"] == "input.visible.click" && (bool?)step["ok"] == true)
            {
                click = step;
                position = index + 1;
            }
        }

        if (click is null || OnlyOpened(click) || !Fold((string?)click["label"]).Contains(target, StringComparison.Ordinal))
        {
            return false;
        }

        string key = ((int?)click["step"] ?? position).ToString(CultureInfo.InvariantCulture);
        if (view["controlsBeforeClick"]?[key] is not JsonArray earlier)
        {
            return false;
        }

        var seenBefore = new HashSet<string>(earlier.Select(node => (string?)node ?? string.Empty), StringComparer.Ordinal);
        // Encargo S13b (bancos fp1–3, war1–3 s13 t3): the settings' heading «Barra lateral de ajustes» is listed past the
        // cap for the goal's words («reserved»). It is compared too when the look before the click listed one of this
        // look's reserved controls: both were read with the words, so a heading not there then is new.
        JsonObject[] listed = [.. (view["controls"] as JsonArray ?? []).OfType<JsonObject>()];
        bool wordsBoth = listed.Any(control => (bool?)control["reserved"] == true && seenBefore.Contains(Fold((string?)control["name"])));
        return (wordsBoth ? listed : ComparedControls(view)).Any(control =>
            (string?)control["kind"] == "Text"
            && (string?)control["zone"] is "T" or "TL" or "TR"
            && Fold((string?)control["name"]) is { Length: > 0 } name
            && name.Contains(target, StringComparison.Ordinal)
            && !seenBefore.Contains(name));
    }

    // An item named «<place> <application>» (WinUI lists: «Científica Calculadora» in the Calculator's navigation) is
    // the place: the window's own name after it is the application's label, not part of the place.
    private static string WithoutAppName(string label, JsonObject view)
    {
        string title = Fold((string?)view["window"]?["title"]);
        if (title.Length < 3)
        {
            return label;
        }

        foreach (string word in title.Split([' ', '-', '|', ':'], StringSplitOptions.RemoveEmptyEntries))
        {
            if (word.Length >= 4 && label.Length > word.Length + 1 && label.EndsWith(" " + word, StringComparison.Ordinal))
            {
                return label[..^(word.Length + 1)];
            }
        }

        return label;
    }

    // The folded names of the listed controls, the window a click is measured against; with <paramref name="reserved"/>,
    // the ones listed for the goal's words too (the look right before a click: RecordControlsBeforeClick).
    internal static JsonArray ControlNames(JsonObject view, bool reserved = false)
    {
        var names = new JsonArray();
        foreach (JsonObject control in reserved ? (view["controls"] as JsonArray ?? []).OfType<JsonObject>() : ComparedControls(view))
        {
            if (Fold((string?)control["name"]) is { Length: > 0 } name)
            {
                names.Add((JsonNode?)JsonValue.Create(name));
            }
        }

        return names;
    }

    /// <summary>
    /// Revisión 3 de r24 (B1): how many listed controls share each name, for the names more than one control has. The
    /// provider gives the controls of one kind and name as one entry and counts the rest in «repeated» (DesktopUiaWorker:
    /// «$seen[$key].repeated++»), so the names list says one «Sin título» where the page list shows seven.
    /// </summary>
    internal static JsonObject ControlCounts(JsonObject view)
    {
        var counts = new Dictionary<string, int>(StringComparer.Ordinal);
        foreach (JsonObject control in ComparedControls(view))
        {
            if (Fold((string?)control["name"]) is { Length: > 0 } name)
            {
                counts[name] = counts.GetValueOrDefault(name) + Copies(control);
            }
        }

        var shared = new JsonObject();
        foreach ((string name, int count) in counts.Where(entry => entry.Value > 1))
        {
            shared[name] = count;
        }

        return shared;
    }

    /// <summary>How many controls one listed entry stands for: itself and the ones the provider counted in «repeated».</summary>
    internal static int Copies(JsonObject control) =>
        1 + (control["repeated"] is JsonValue repeated && repeated.TryGetValue(out int more) && more > 0 ? more : 0);

    /// <summary>
    /// Revision 1 of ronda 21: the listed controls one look is compared with another by. A control the provider listed
    /// past the view's cut only because its name carries the goal's words («reserved», DesktopUiaWorker
    /// Join-ViewControls) is left out: the look before a sub-goal's first act carries no words and the next ones do, so
    /// counting it would make an act that changed nothing (a click that only selected «Informes» in a folder of 200)
    /// look as if it brought «Informes 2023.xlsx» (appeared, broughtNew, a moved place, a changed signature).
    /// </summary>
    internal static IEnumerable<JsonObject> ComparedControls(JsonObject view) =>
        (view["controls"] as JsonArray ?? []).OfType<JsonObject>().Where(control => (bool?)control["reserved"] != true);

    // A written web address (scheme or www.) whose host or path has the place as one of its words.
    private static bool AddressNames(JsonObject view, string place)
    {
        string target = Fold(place);
        if (target.Length < 3 || target.Contains(' ', StringComparison.Ordinal))
        {
            return false;
        }

        foreach (JsonNode? line in TextLines(view))
        {
            string text = (string?)line ?? string.Empty;
            int scheme = text.IndexOf("://", StringComparison.Ordinal);
            string address = scheme >= 0 ? text[(scheme + 3)..] : text.StartsWith("www.", StringComparison.Ordinal) ? text : string.Empty;
            if (address.Length == 0 || address.Contains(' ', StringComparison.Ordinal))
            {
                continue;
            }

            // A word of the address, or a host word that ends or begins with the place («steamcommunity»: community).
            if (address.Split(['.', '/', '-', '_', '?', '=', '&', '#'], StringSplitOptions.RemoveEmptyEntries)
                .Any(word => word == target
                    || (target.Length >= 5 && word.Length > target.Length
                        && (word.EndsWith(target, StringComparison.Ordinal) || word.StartsWith(target, StringComparison.Ordinal)))))
            {
                return true;
            }
        }

        return false;
    }

    // A verified click whose label names the place, or the entry picked right after
    // a click on it (the menu that click opened: measured on Steam, the click on
    // «BIBLIOTECA» opened its menu and did not verify; «Inicio» in it did). An entry
    // is one the menu showed: its label was not written on screen before the click on
    // the place (measured: «BIBLIOTECA» then «TIENDA», both in the header, and the
    // store passed for the library). Any other verified click (a tab, a field) does
    // not reach the place; a click that failed changed nothing and is passed over
    // (a learned «Inicio» that failed between «BIBLIOTECA» and «Página principal»).
    private static int? AClickWentTo(string place, JsonArray steps, JsonObject view)
    {
        string target = Fold(place);
        bool previousNamedIt = false;
        int? namedClick = null;
        int? went = null;
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
            bool ok = (bool?)step["ok"] == true;
            if (namesIt)
            {
                namedClick = (int?)step["step"] ?? position;
            }

            if (ok && OnlyOpened(step))
            {
                // Goal v3 B3 (review, finding 4): opening the place's arrow or menu reaches nothing by itself; the
                // entry picked in what it opened does, and the opening of another control's menu leaves the window
                // where it was.
                previousNamedIt = namesIt;
                continue;
            }

            if (ok && (namesIt || (previousNamedIt && MenuEntry(label, namedClick, view))))
            {
                // Measured against the view before the click on the place itself (a menu entry picked after it
                // still counts from before the menu opened).
                went ??= namedClick ?? (int?)step["step"] ?? position;
            }
            else if (ok)
            {
                // A later verified click went somewhere else (measured on Steam: «BIBLIOTECA», then «TIENDA», and the
                // store passed for the library).
                went = null;
                namedClick = null;
            }
            else if (!namesIt)
            {
                continue;
            }

            previousNamedIt = namesIt;
        }

        return went;
    }

    // An entry of the menu the click on the place opened: its label was not written before that click. Unknown when
    // no text was read before it (the mission's first look stands in for it, as in PageAtom).
    private static bool MenuEntry(string label, int? namedClick, JsonObject view)
    {
        JsonArray? before = (namedClick is int named
                ? view["textBeforeClick"]?[named.ToString(CultureInfo.InvariantCulture)] as JsonArray
                : null)
            ?? view["baselineText"] as JsonArray;
        return label.Length == 0 || before is null
            || !before.Any(line => NamesWhole(Fold((string?)line), label));
    }
}
