using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Baxy.App;

// Forms and created things: a field written and committed, a part new by identity, a button the sub-goal brought.
internal static partial class ComputerUseSuccessCheck
{
    /// <summary>
    /// Revisión 1 de r24 (B2, v3-08: «ponele de título Lista del super» typed into «Título de página»): the citation is
    /// the whole value of a field of the view (Edit, Document, ComboBox, never a search box) whose name shares a word
    /// with the goal besides the citation's own words (the part the goal names: «título»), and a verified typing step
    /// of the sub-goal typed exactly that text into that field. Never in a search goal: its proof is a result. Twin of
    /// the structural half of the mind's cu_evidence._slot_written, which reads the part and the text from the goal.
    /// Revisión 3 de r24 (B1: «Gym» typed into «Nombre» of the dialog «Editar detalles» brought, «Guardar» unpressed):
    /// a field of a form still to save holds a text, not the act (<see cref="FormLeftUnsaved"/>). Revisión 4 de r24 (B1:
    /// «ponele de título «pruebas» a la pestaña» typed «pruebas» into «Título de la pestaña», the rename box the click on
    /// «Cambiar nombre de pestaña» brought, with no Enter and the tab still named the old way): a field the sub-goal
    /// itself brought (<see cref="FieldBrought"/>) is a passing box until a verified click on a button that saves or
    /// confirms came after the typing; until then the proof is what shows the name outside a field (the item named so).
    /// </summary>
    internal static bool SlotWritten(string? cited, string? goal, JsonObject view, JsonArray subgoalSteps, string? firstLook)
    {
        string citation = Bare(cited);
        if (citation.Length == 0 || SearchGoal(goal))
        {
            return false;
        }

        var ownWords = Regex.Matches(citation, @"[a-z0-9]+").Select(match => match.Value).ToHashSet(StringComparer.Ordinal);
        var goalWords = Regex.Matches(Fold(goal), @"[a-z0-9]+").Select(match => match.Value)
            .Where(word => word.Length >= 3 && !ownWords.Contains(word)).ToHashSet(StringComparer.Ordinal);
        var fields = new Dictionary<string, JsonObject>(StringComparer.Ordinal);
        foreach (JsonObject control in (view["controls"] as JsonArray ?? []).OfType<JsonObject>()
            .Where(control => (string?)control["kind"] is "Edit" or "Document" or "ComboBox"
                && !IsSearchBox((string?)control["name"])
                && Bare((string?)control["value"]) == citation
                && Regex.Matches(Fold((string?)control["name"]), @"[a-z0-9]+").Any(match => goalWords.Contains(match.Value))))
        {
            fields.TryAdd(Bare((string?)control["name"]), control);
        }

        var steps = subgoalSteps.OfType<JsonObject>().ToList();
        int typedAt = steps.FindLastIndex(step => (bool?)step["ok"] == true
            && (string?)step["operation"] == "input.text.type"
            && Bare((string?)step["text"]) == citation
            && fields.ContainsKey(Bare((string?)step["field"] ?? (string?)step["into"])));
        if (typedAt < 0)
        {
            return false;
        }

        var after = steps.Skip(typedAt + 1).ToList();
        JsonObject field = fields[Bare((string?)steps[typedAt]["field"] ?? (string?)steps[typedAt]["into"])];
        if (FieldBrought(field, view, firstLook) && !CommitClicked(after))
        {
            return false;
        }

        return !FormLeftUnsaved(view, after, firstLook);
    }

    /// <summary>
    /// Revisión 4 de r24 (B1): a field the sub-goal brought, never one already on its first look (v3-08's «Título de
    /// página»): its name is among the lines the last verified click made appear (<c>newTextAfterClick</c>), or parts with
    /// its name, whatever value they hold (the typing changed it), show more times than on the sub-goal's first look
    /// (Explorer's rename box «Nombre» beside the column «Nombre»). Without either look, nothing counts as brought. Twin
    /// of the mind's <c>_field_brought</c>.
    /// </summary>
    internal static bool FieldBrought(JsonObject control, JsonObject view, string? firstLook)
    {
        string name = Fold((string?)control["name"]).Trim();
        if (name.Length == 0)
        {
            return false;
        }

        if (view["newTextAfterClick"] is JsonArray appeared && appeared.Any(line =>
                line is JsonValue text && text.TryGetValue(out string? written) && Fold(written).Trim() == name))
        {
            return true;
        }

        if (string.IsNullOrWhiteSpace(firstLook))
        {
            return false;
        }

        string key = Fold((string?)control["name"]).Replace('\n', ' ').Replace('\r', ' ');
        static int Named(IEnumerable<string> parts, string wanted) => parts.Count(part => part.Split('\t', 2)[0] == wanted);
        return Named(LookText(view).Split('\n'), key) > Named(firstLook.Split('\n'), key);
    }

    /// <summary>
    /// A verified click that changed something on a button that saves or confirms (data «evidence.commitControl») among
    /// <paramref name="after"/>. Twin of the mind's <c>_commit_clicked</c>.
    /// </summary>
    internal static bool CommitClicked(IEnumerable<JsonObject> after)
    {
        var commit = new Regex((string)OperationFloor.EvidenceRules["commitControl"]!, RegexOptions.CultureInvariant);
        return after.Any(step => (bool?)step["ok"] == true && (bool?)step["changed"] != false
            && (string?)step["operation"] == "input.visible.click"
            && commit.IsMatch(Fold((string?)step["label"]).Trim()));
    }

    /// <summary>
    /// Revisión 3 de r24 (B1): a button that saves or confirms (data «evidence.commitControl») that this sub-goal brought
    /// (<see cref="BroughtThisSubgoal"/>: the form the sub-goal opened, never a «Guardar» on screen all along) is on
    /// offer, and no verified click on such a button came after the typing (<paramref name="after"/>): what was typed
    /// sits in a form still to save, so nothing is set yet. The rule of <see cref="FormButtonCited"/>. Twin of the
    /// mind's <c>_form_left_unsaved</c>.
    /// </summary>
    internal static bool FormLeftUnsaved(JsonObject view, IEnumerable<JsonObject> after, string? firstLook)
    {
        var commit = new Regex((string)OperationFloor.EvidenceRules["commitControl"]!, RegexOptions.CultureInvariant);
        if (!(view["controls"] as JsonArray ?? []).OfType<JsonObject>().Any(control =>
                (string?)control["kind"] is "Button" or "SplitButton"
                && commit.IsMatch(Fold((string?)control["name"]).Trim())
                && BroughtThisSubgoal(control, view, firstLook)))
        {
            return false;
        }

        return !CommitClicked(after);
    }

    /// <summary>
    /// Revisión 3 de P4: a control the sub-goal brought, never one that was already on screen (Office's «Guardar» of the
    /// quick access bar is on every look): its name is among the lines the last verified click made appear
    /// (<c>newTextAfterClick</c>), or its part (the name, with its value, as <see cref="LookText"/> writes it) shows more
    /// times than on the sub-goal's first look (<paramref name="firstLook"/>). Without either look, nothing counts as
    /// brought. Twin of the mind's <c>_brought_this_subgoal</c>.
    /// </summary>
    internal static bool BroughtThisSubgoal(JsonObject control, JsonObject view, string? firstLook)
    {
        string name = Fold((string?)control["name"]).Trim();
        if (name.Length == 0)
        {
            return false;
        }

        if (view["newTextAfterClick"] is JsonArray appeared && appeared.Any(line =>
                line is JsonValue text && text.TryGetValue(out string? written) && Fold(written).Trim() == name))
        {
            return true;
        }

        if (string.IsNullOrWhiteSpace(firstLook))
        {
            return false;
        }

        string value = Fold((string?)control["value"]);
        string part = (Fold((string?)control["name"]) + (value.Length > 0 ? "\t" + value : string.Empty))
            .Replace('\n', ' ').Replace('\r', ' ');
        int now = LookText(view).Split('\n').Count(shown => shown == part);
        return now > firstLook.Split('\n').Count(shown => shown == part);
    }

}
