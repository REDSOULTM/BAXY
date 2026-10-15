using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Kernel.Policy;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// The acts a search burst is made of, on the mission's window while the burst holds its front: the opener pressed by
/// its identity, a look at the controls (the keyboard focus is known, the window being in front), the text typed where
/// the opening put the keyboard, and the result pressed by its identity.
/// </summary>
internal interface ISearchBurstActs
{
    ValueTask<ExternalCapabilityReceipt> OpenAsync(nint window, string label, string controlId, CancellationToken cancellationToken);

    ValueTask<IReadOnlyList<WindowsVisibleControlAdapter.ViewControl>?> LookAsync(nint window, CancellationToken cancellationToken);

    ValueTask<ExternalCapabilityReceipt> TypeAsync(nint window, string text, CancellationToken cancellationToken);

    ValueTask<ExternalCapabilityReceipt> ChooseAsync(nint window, string label, string controlId, CancellationToken cancellationToken);

    /// <summary>
    /// The window's own popups now (<see cref="VisibleControlSurface.PopupsOf"/>: its process family's surfaces next to
    /// it, a menu's popup host): where an opener's items live when they are drawn outside its window.
    /// </summary>
    IReadOnlyList<nint> PopupsOfWindow(nint window) => [];

    /// <summary>
    /// Ronda 20 (P7): a control pressed by its identity in a manner (its arrow, its context menu, a double click), as the
    /// act that showed or asked for it was. None by default: a burst that has no such press presses nothing.
    /// </summary>
    ValueTask<ExternalCapabilityReceipt> PressInMannerAsync(
        nint window, string label, string controlId, string manner, CancellationToken cancellationToken) =>
        ValueTask.FromResult(ExternalJson.FailureBeforeEffect("input.visible.click", "visible_click_argument_invalid"));
}

/// <summary>
/// GOAL_COMPUTER_USE_V3 point 0, fix 3, the compound operation of the review: a search or a drop-down that lives only
/// while its window is active (measured live: a chat application's channel search, opened by a click, closed 32 ms after
/// the front went back) cannot be opened in one decision and typed into in the next, since the front goes back before
/// every decision of the mind. When the mind already knows the whole sequence (open the field or the drop-down, type the
/// destination, choose the result that names it), it goes in ONE burst inside a pause of the person: the lease waits for
/// their pause and takes the front, the opener is pressed, the text is typed where the opening put the keyboard, the view
/// is read inside the burst and the result that names the destination is pressed by its identity (never an Enter
/// blind). The front and the cursor go back exactly as they were, at the end, at the person's first input or when the
/// burst's ceiling (<see cref="CapMs"/>) runs out. A result whose press reaches a person or cannot be undone (a voice
/// channel, a removal) is not pressed unless the invocation names it (<c>choose</c>, which RiskPolicy confirmed): the
/// receipt says so and the mind asks for that exact invocation. The receipt says every sub-act (<c>acts</c>).
/// </summary>
internal sealed class SearchBurst(IForegroundLease lease, ILeaseClock clock, ISearchBurstActs acts)
{
    /// <summary>The ceiling of the whole burst, from the moment the front was taken (the review's ~1.5–2 s).</summary>
    internal const int CapMs = 2000;

    /// <summary>The time between two looks for the result while the search fills its list.</summary>
    internal const int ResultLookMs = 100;

    /// <summary>The result is there and its press would reach a person or not be undone: the invocation must name it.</summary>
    internal const string ResultNeedsConfirmation = "visible_search_result_needs_confirmation";

    /// <summary>No result named the destination before the ceiling: nothing was pressed after the text.</summary>
    internal const string ResultNotFound = "visible_search_result_not_found";

    /// <summary>The opening did not show that it took the keyboard (nothing opened, or an earlier field kept it).</summary>
    internal const string FocusUnproven = "visible_search_focus_unproven";

    /// <summary>The burst's ceiling ran out before the next sub-act.</summary>
    internal const string CapReached = "visible_search_cap_reached";

    // What a search shows its results as, best first (the mind's _RESULT_KINDS); a field is never a result.
    private static readonly string[] ResultKinds = ["ListItem", "TreeItem", "Button", "Hyperlink", "DataItem", "MenuItem", "TabItem"];
    private static readonly HashSet<string> FieldKinds = new(StringComparer.Ordinal) { "Edit", "ComboBox", "Document" };
    private static readonly HashSet<string> SwitchKinds = new(StringComparer.Ordinal) { "CheckBox", "RadioButton", "Slider" };
    // Ronda 25, the mind's _ENTRY_KINDS (a result may hold the name among other words) and _DESCRIPTIVE_KINDS.
    private static readonly HashSet<string> EntryKinds = new(StringComparer.Ordinal) { "ListItem", "TreeItem", "DataItem", "Hyperlink", "MenuItem" };
    private static readonly HashSet<string> DescriptiveKinds = new(StringComparer.Ordinal) { "Text", "Group", "Pane", "Custom", "Document" };

    internal async ValueTask<ExternalCapabilityReceipt> RunAsync(
        string operation,
        nint window,
        string label,
        string controlId,
        IReadOnlyList<WindowsVisibleControlAdapter.ViewControl> before,
        string search,
        string? choose,
        CancellationToken cancellationToken)
    {
        IInputBurst burst = await lease.AcquireAsync(window, cancellationToken).ConfigureAwait(false);
        if (!burst.MayAct)
        {
            _ = burst.Restore();
            return ExternalJson.FailureBeforeEffect(operation, burst.Refusal ?? "input_user_interrupted");
        }

        long began = clock.NowMs;
        var done = new JsonArray();
        bool effect = false;
        string? stopped = null;
        WindowsVisibleControlAdapter.ViewControl? chosen = null;
        bool restored;
        try
        {
            stopped = await RunInBurstAsync().ConfigureAwait(false);
        }
        finally
        {
            restored = burst.Restore();
        }

        // Nothing pressed: the opener's own refusal, as a plain click says it.
        if (!effect && stopped is not null)
            return ExternalJson.FailureBeforeEffect(operation, stopped);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("ok", stopped is null);
            writer.WriteBoolean("effectObserved", effect);
            writer.WriteString("error", stopped ?? string.Empty);
            writer.WriteString("method", "search_burst");
            writer.WriteString("searched", search);
            if (chosen is not null)
            {
                writer.WriteString("name", chosen.Name);
                writer.WriteString("kind", chosen.Kind);
                writer.WriteBoolean("surfaceChanged", true);
            }

            writer.WriteNumber("waitedMs", burst.WaitedMs);
            writer.WriteNumber("burstMs", Math.Max(0, clock.NowMs - began));
            writer.WriteBoolean("restored", restored);
            writer.WritePropertyName("acts");
            using (JsonDocument listed = JsonDocument.Parse(done.ToJsonString()))
                listed.RootElement.WriteTo(writer);
            writer.WriteEndObject();
        });
        return stopped is null
            ? ExternalJson.Success(operation, result, effectObserved: true)
            : new ExternalCapabilityReceipt(operation, effect, false, result, stopped) { EffectMayHaveOccurred = true };

        async ValueTask<string?> RunInBurstAsync()
        {
            const string Click = "input.visible.click";
            const string Text = "input.text.type";

            // 1. The opener, by its identity.
            ExternalCapabilityReceipt opened = await acts.OpenAsync(window, label, controlId, cancellationToken)
                .ConfigureAwait(false);
            effect |= opened.EffectObserved || opened.EffectMayHaveOccurred;
            done.Add((JsonNode?)Act(Click, "label", label, opened));
            if (!opened.Verified || opened.ErrorCode is not null)
                return opened.ErrorCode ?? "visible_click_failed";
            if (Interrupted() is { } afterOpen)
                return Refused(afterOpen, Text, "text", search);

            // 2. The keyboard must be where the opening put it: something opened, no password has it, and no field that
            // already had it before the opener (a message box) keeps it.
            IReadOnlyList<WindowsVisibleControlAdapter.ViewControl>? shown = await acts.LookAsync(window, cancellationToken)
                .ConfigureAwait(false);
            if (shown is null || !TookTheKeyboard(shown, before, controlId))
                return Refused(FocusUnproven, Text, "text", search);
            if (Interrupted() is { } afterLook)
                return Refused(afterLook, Text, "text", search);

            // 3. The destination, typed there (the receipt says into what, when the look named the focus).
            ExternalCapabilityReceipt typed = await acts.TypeAsync(window, search, cancellationToken).ConfigureAwait(false);
            effect |= typed.EffectObserved || typed.EffectMayHaveOccurred;
            JsonObject typedAct = Act(Text, "text", search, typed);
            if (shown.FirstOrDefault(control => HasState(control, "focused")) is { } into)
                typedAct["into"] = into.Name;
            done.Add((JsonNode?)typedAct);
            if (!typed.Verified || typed.ErrorCode is not null)
                return typed.ErrorCode ?? "input_effect_not_verified";

            // 4. The result that names it, read inside the burst while the search fills its list.
            HashSet<string> shownIds = shown.Select(control => control.Id).ToHashSet(StringComparer.Ordinal);
            HashSet<string> shownNames = shown.Select(control => Words(control.Name)).ToHashSet(StringComparer.Ordinal);
            WindowsVisibleControlAdapter.ViewControl? result = null;
            while (true)
            {
                if (Interrupted() is { } whileLooking)
                    return Refused(whileLooking == CapReached ? ResultNotFound : whileLooking, Click, "label", search);
                IReadOnlyList<WindowsVisibleControlAdapter.ViewControl>? listed = await acts.LookAsync(window, cancellationToken)
                    .ConfigureAwait(false);
                result = listed is null ? null : ResultNaming(listed, search, choose, controlId, shownIds, shownNames);
                if (result is not null)
                    break;
                await clock.DelayAsync(ResultLookMs, cancellationToken).ConfigureAwait(false);
            }

            // A press that reaches a person or cannot be undone goes only when this invocation names it (RiskPolicy
            // confirmed it bound to that name).
            if (NeedsConfirmation(result.Name) && !SameName(result.Name, choose))
                return Refused(ResultNeedsConfirmation, Click, "label", result.Name);
            if (Interrupted() is { } beforeChoosing)
                return Refused(beforeChoosing, Click, "label", result.Name);

            // 5. The result, by its identity.
            ExternalCapabilityReceipt picked = await acts.ChooseAsync(window, result.Name, result.Id, cancellationToken)
                .ConfigureAwait(false);
            effect |= picked.EffectObserved || picked.EffectMayHaveOccurred;
            done.Add((JsonNode?)Act("input.visible.click", "label", result.Name, picked));
            if (!picked.Verified || picked.ErrorCode is not null)
                return picked.ErrorCode ?? "visible_click_failed";
            chosen = result;
            return null;
        }

        // The person's first input, the window that lost the front, or the burst's ceiling: the burst ends here.
        string? Interrupted() =>
            burst.UserActed ? "input_user_interrupted"
            : !burst.HoldsWindow ? "input_window_changed"
            : clock.NowMs - began >= CapMs ? CapReached
            : null;

        // The sub-act the burst stopped before, said in the receipt with its cause: every stop names what was not done.
        string Refused(string code, string act, string key, string named)
        {
            done.Add((JsonNode?)new JsonObject
            {
                ["operation"] = act,
                [key] = named,
                ["ok"] = false,
                ["error"] = code,
            });
            return code;
        }
    }

    /// <summary>The item was not there again before the ceiling, after its opener was pressed once more.</summary>
    internal const string ItemNotReopened = "visible_reopened_item_not_found";

    /// <summary>
    /// Pasada r15b (v3-09, OneNote's ribbon gallery): an item that a click on its opener showed (a gallery of a collapsed
    /// ribbon, a drop-down) closed between the look that showed it and its press, because the window lost the activation
    /// to the person's. In ONE burst inside their pause: the window is looked at; when the item is not there its opener is
    /// pressed again by its identity (once), the item is read on a look inside the burst and pressed by its identity
    /// while the window still holds the front. The front and the cursor go back as they were, at the end, at the
    /// person's first input or at the ceiling. The receipt says every sub-act (<c>acts</c>). Menus-efímeros (t-form-2,
    /// t-file-4): the item is looked for in the window and in the popups of its own that the burst can vouch for (a menu
    /// bar's popup host), and pressed in the one that shows it; the lease holds the window while a popup it owns is in
    /// front. Review of the branch (finding 1): a popup vouched for is <paramref name="shownIn"/>, the window the mission's
    /// look saw the item in while it is still one of the window's popups, or one born inside the burst (absent when the
    /// burst took the front); a window of the same process the person already had open over it (another document of a
    /// single-process editor, another browser window) is never looked into nor pressed.
    /// </summary>
    internal async ValueTask<ExternalCapabilityReceipt> ReopenAsync(
        string operation,
        nint window,
        string openerLabel,
        string openerId,
        string label,
        CancellationToken cancellationToken,
        nint shownIn = 0,
        string? openerManner = null,
        string? itemManner = null)
    {
        IInputBurst burst = await lease.AcquireAsync(window, cancellationToken).ConfigureAwait(false);
        if (!burst.MayAct)
        {
            _ = burst.Restore();
            return ExternalJson.FailureBeforeEffect(operation, burst.Refusal ?? "input_user_interrupted");
        }

        long began = clock.NowMs;
        // The window's popups when the burst took the front: none of them is the burst's, unless the mission saw the item
        // in it (shownIn).
        HashSet<nint> popupsBefore = [.. acts.PopupsOfWindow(window)];
        var done = new JsonArray();
        bool effect = false;
        string? stopped;
        WindowsVisibleControlAdapter.ViewControl? chosen = null;
        bool restored;
        try
        {
            stopped = await InBurstAsync().ConfigureAwait(false);
        }
        finally
        {
            restored = burst.Restore();
        }

        if (!effect && stopped is not null)
            return ExternalJson.FailureBeforeEffect(operation, stopped);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("ok", stopped is null);
            writer.WriteBoolean("effectObserved", effect);
            writer.WriteString("error", stopped ?? string.Empty);
            writer.WriteString("method", "reopen_burst");
            if (chosen is not null)
            {
                writer.WriteString("name", chosen.Name);
                writer.WriteString("kind", chosen.Kind);
                writer.WriteBoolean("surfaceChanged", true);
            }

            writer.WriteNumber("waitedMs", burst.WaitedMs);
            writer.WriteNumber("burstMs", Math.Max(0, clock.NowMs - began));
            writer.WriteBoolean("restored", restored);
            writer.WritePropertyName("acts");
            using (JsonDocument listed = JsonDocument.Parse(done.ToJsonString()))
                listed.RootElement.WriteTo(writer);
            writer.WriteEndObject();
        });
        return stopped is null
            ? ExternalJson.Success(operation, result, effectObserved: true)
            : new ExternalCapabilityReceipt(operation, effect, false, result, stopped) { EffectMayHaveOccurred = true };

        async ValueTask<string?> InBurstAsync()
        {
            const string Click = "input.visible.click";
            bool reopened = false;
            WindowsVisibleControlAdapter.ViewControl? item = null;
            nint itemWindow = window;
            while (true)
            {
                string? interrupted = burst.UserActed ? "input_user_interrupted"
                    : !burst.HoldsWindow ? "input_window_changed"
                    : clock.NowMs - began >= CapMs ? ItemNotReopened
                    : null;
                if (interrupted is not null)
                {
                    done.Add((JsonNode?)new JsonObject { ["operation"] = Click, ["label"] = label, ["ok"] = false, ["error"] = interrupted });
                    return interrupted;
                }

                // The window, then the popups vouched for (menus-efímeros, t-form-2: a menu bar's items live in a popup
                // host of the window's process): never a window of another process, one elsewhere on the screen, nor
                // one of the same process that was already up when the burst began (review, finding 1).
                nint[] surfaces = [window, .. acts.PopupsOfWindow(window)
                    .Where(popup => popup != window && (popup == shownIn || !popupsBefore.Contains(popup)))];
                foreach (nint surface in surfaces)
                {
                    IReadOnlyList<WindowsVisibleControlAdapter.ViewControl>? listed = await acts.LookAsync(surface, cancellationToken)
                        .ConfigureAwait(false);
                    item = listed?.FirstOrDefault(control => control.Id.Length > 0 && !(surface == window && control.Id == openerId)
                        && SameName(control.Name, label) && !HasState(control, "disabled"));
                    if (item is not null)
                    {
                        itemWindow = surface;
                        break;
                    }
                }

                if (item is not null)
                    break;
                if (!reopened)
                {
                    // The opener, by its identity, once: a second press of a tab or a toggle would close what it opened.
                    reopened = true;
                    // Ronda 20 (P7, v3-37): an opener pressed by its arrow is pressed by its arrow again, never by its
                    // own action (a split button's Invoke opened another tab).
                    ExternalCapabilityReceipt opened = openerManner is null
                        ? await acts.OpenAsync(window, openerLabel, openerId, cancellationToken).ConfigureAwait(false)
                        : await acts.PressInMannerAsync(window, openerLabel, openerId, openerManner, cancellationToken)
                            .ConfigureAwait(false);
                    effect |= opened.EffectObserved || opened.EffectMayHaveOccurred;
                    done.Add((JsonNode?)Act(Click, "label", openerLabel, opened));
                    if (!opened.Verified || opened.ErrorCode is not null)
                        return opened.ErrorCode ?? "visible_click_failed";
                    continue;
                }

                await clock.DelayAsync(ResultLookMs, cancellationToken).ConfigureAwait(false);
            }

            // Ronda 20 (P7, v3-09): the item in the manner the act asked for (its arrow), never its ordinary press instead.
            ExternalCapabilityReceipt picked = itemManner is null
                ? await acts.ChooseAsync(itemWindow, item.Name, item.Id, cancellationToken).ConfigureAwait(false)
                : await acts.PressInMannerAsync(itemWindow, item.Name, item.Id, itemManner, cancellationToken)
                    .ConfigureAwait(false);
            effect |= picked.EffectObserved || picked.EffectMayHaveOccurred;
            done.Add((JsonNode?)Act(Click, "label", item.Name, picked));
            if (!picked.Verified || picked.ErrorCode is not null)
                return picked.ErrorCode ?? "visible_click_failed";
            chosen = item;
            return null;
        }
    }

    // A sub-act as the receipt says it: what it was, on what, and its own answer.
    private static JsonObject Act(string operation, string key, string named, ExternalCapabilityReceipt receipt)
    {
        var act = new JsonObject
        {
            ["operation"] = operation,
            [key] = named,
            ["ok"] = receipt.Verified && receipt.ErrorCode is null,
        };
        if (receipt.ErrorCode is { } error)
            act["error"] = error;
        if (receipt.Result is { ValueKind: JsonValueKind.Object } result)
        {
            foreach (string name in new[] { "method", "kind", "surfaceChanged", "selected", "focused" })
            {
                if (result.TryGetProperty(name, out JsonElement value)
                    && value.ValueKind is JsonValueKind.String or JsonValueKind.True or JsonValueKind.False)
                    act[name] = JsonNode.Parse(value.GetRawText());
            }
        }

        return act;
    }

    /// <summary>
    /// Whether the opening took the keyboard, read on the look right after it with the window in front: something the
    /// look before did not show appeared (a box, a list), no password field has the focus, and the focus is not on a
    /// field the window already showed before the opener (a message box would get the destination), unless it is the
    /// opener itself (a combo box).
    /// </summary>
    internal static bool TookTheKeyboard(
        IReadOnlyList<WindowsVisibleControlAdapter.ViewControl> shown,
        IReadOnlyList<WindowsVisibleControlAdapter.ViewControl> before,
        string openerId)
    {
        var earlierIds = before.Where(control => control.Id.Length > 0).Select(control => control.Id).ToHashSet(StringComparer.Ordinal);
        var earlierNames = before.Select(control => control.Name).ToHashSet(StringComparer.Ordinal);
        bool opened = shown.Any(control => !earlierNames.Contains(control.Name));
        foreach (WindowsVisibleControlAdapter.ViewControl control in shown.Where(control => HasState(control, "focused")))
        {
            if (HasState(control, "password"))
                return false;
            if (FieldKinds.Contains(control.Kind) && control.Id != openerId && earlierIds.Contains(control.Id))
                return false;
        }

        return opened;
    }

    /// <summary>
    /// The result that names the destination (the mind's <c>_result_naming</c>): no field, no switch, never the opener;
    /// a result kind before any other, the exact name before one that only contains it. With <paramref name="choose"/>,
    /// only the control of exactly that name.
    /// </summary>
    internal static WindowsVisibleControlAdapter.ViewControl? ResultNaming(
        IReadOnlyList<WindowsVisibleControlAdapter.ViewControl> controls,
        string search,
        string? choose,
        string openerId,
        IReadOnlyCollection<string>? shownBefore = null,
        IReadOnlyCollection<string>? namesBefore = null)
    {
        string wanted = Words(search);
        // What only repeats the search or a field's value (Discord's «cotele» drawn as a Text, c7).
        HashSet<string> echoes = [.. controls.Where(control => control.Kind is "Edit" or "ComboBox")
            .Select(control => Echo(control.Value ?? string.Empty)).Append(Echo(search)).Where(echo => echo.Length > 0)];
        WindowsVisibleControlAdapter.ViewControl[] listed = [.. controls.Where(control => control.Id.Length > 0
            && control.Id != openerId && !FieldKinds.Contains(control.Kind) && !IsSwitch(control)
            && (choose is null || SameName(control.Name, choose)))];
        WindowsVisibleControlAdapter.ViewControl[] named = [.. listed.Where(control => NamesResult(wanted, control, echoes, namesBefore))];
        WindowsVisibleControlAdapter.ViewControl[] near = [.. listed.Where(control => EntryKinds.Contains(control.Kind) && OneTypo(control.Name, wanted))];
        return (named.Length > 0 ? named : near.Length == 1 ? near : [])
            // What the search listed after the text before what the window already showed (a server of the same name
            // in its side bar, measured on a chat application).
            .OrderBy(control => shownBefore is not null && shownBefore.Contains(control.Id))
            .ThenBy(control => Array.IndexOf(ResultKinds, control.Kind) < 0)
            .ThenBy(control => Words(control.Name) != wanted)
            .ThenBy(control => Array.IndexOf(ResultKinds, control.Kind) is var rank && rank >= 0 ? rank : ResultKinds.Length)
            .FirstOrDefault();
    }

    // The mind's _result_naming, ronda 25: never an echo; the exact name, or whole words in a short entry, or in a short
    // control the search brought (no name of the look before the text: the mind's newText); never «Comprimir …» (u1).
    private static bool NamesResult(
        string wanted, WindowsVisibleControlAdapter.ViewControl control, HashSet<string> echoes, IReadOnlyCollection<string>? namesBefore)
    {
        string name = Words(control.Name);
        if (wanted.Length == 0 || (echoes.Contains(Echo(control.Name)) && (DescriptiveKinds.Contains(control.Kind) || name != wanted)))
            return false;
        return name == wanted || (!DescriptiveKinds.Contains(control.Kind) && control.Kind != "TabItem"
            && (EntryKinds.Contains(control.Kind) || namesBefore is null || !namesBefore.Contains(name))
            && name.Split(' ').Length <= wanted.Split(' ').Length + 6
            && System.Text.RegularExpressions.Regex.IsMatch(name, $@"(?<!\w){System.Text.RegularExpressions.Regex.Escape(wanted)}(?!\w)"));
    }

    // The mind's _one_typo, _field_echo («Q fonts») and its folded words.
    private static bool OneTypo(string name, string wanted) => Words(name) is var seen && wanted.Length / 5 > 0 && seen != wanted
        && WindowsVisibleControlAdapter.EditDistance(wanted, seen, wanted.Length / 5) <= wanted.Length / 5;
    private static string Echo(string text) => string.Join(' ', Words(text).Split(' ').SkipWhile(word => word.Length == 1)
        .Reverse().SkipWhile(word => word.Length == 1).Reverse());
    private static string Words(string text) =>
        string.Join(' ', WindowsVisibleOcrLocator.Fold(text).Split(' ', StringSplitOptions.RemoveEmptyEntries));

    // Pressing it would reach a person (a voice channel, a call, send) or could not be undone (a removal, a purchase):
    // the one question the adapter asks of any control it is about to press (ronda 29), here with no label judged.
    private static bool NeedsConfirmation(string name) => RiskPolicy.PressedNameAsksMoreThanItsLabel(null, name);

    private static bool SameName(string name, string? other) =>
        other is not null && string.Equals(WindowsVisibleOcrLocator.Fold(name), WindowsVisibleOcrLocator.Fold(other), StringComparison.Ordinal);

    private static bool IsSwitch(WindowsVisibleControlAdapter.ViewControl control) =>
        SwitchKinds.Contains(control.Kind)
        || control.State.Split(' ', StringSplitOptions.RemoveEmptyEntries)
            .Any(word => word is "on" or "off" or "checked" or "unchecked");

    private static bool HasState(WindowsVisibleControlAdapter.ViewControl control, string state) =>
        control.State.Split(' ', StringSplitOptions.RemoveEmptyEntries).Contains(state, StringComparer.Ordinal);
}
