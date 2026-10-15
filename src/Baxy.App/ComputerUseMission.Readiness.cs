using System.Globalization;
using System.Text;
using System.Text.Json.Nodes;

namespace Baxy.App;

// Whether a window is ready to act on: loading, only its frame, still starting, settled, what can be acted on.
internal static partial class ComputerUseMission
{
    /// <summary>
    /// Whether the look shows a loading indicator: a ProgressBar named as one (data «computerUse.loadingBar»:
    /// «Cargando», «Ocupado», «Loading», «Busy»). Its value says nothing (a page's «Cargando» bar read 0); its name says
    /// the window is not drawn yet, and the final never quotes it (<see cref="ScreenExcerpt"/>).
    /// </summary>
    /// Ronda 20 P8 (v3-29, a notes application opening on «Cargando Notas rápidas...», a Group and a Text, no bar): a
    /// written loading indicator counts too where it is what the view is, never beside its content: a Group or a Pane
    /// named as one (data «computerUse.loading», never «Ocupado»/«Busy»), or a Text so named in the middle of the
    /// window, while the view has no field and nothing a person could act on but its caption buttons.
    internal static bool ShowsLoading(JsonObject view) =>
        view["controls"] is JsonArray controls
        && (controls.OfType<JsonObject>().Any(IsLoadingBar) || ShowsOnlyALoadingText(controls));

    private static bool ShowsOnlyALoadingText(JsonArray controls)
    {
        List<JsonObject> all = [.. controls.OfType<JsonObject>()];
        return all.Any(control => ((string?)control["kind"] is "Group" or "Pane"
                    || ((string?)control["kind"] == "Text" && (string?)control["zone"] == "C"))
                && OperationFloor.NamesLoading(ComputerUseSuccessCheck.Fold((string?)control["name"])))
            && !all.Any(control => (string?)control["kind"] is "Edit" or "ComboBox" or "Document" || IsActionable(control));
    }

    // Ronda 20b (v3-43): a bar so named that stands still (StillLoadingBars) is furniture of the window, not loading.
    private static bool IsLoadingBar(JsonObject control) =>
        NamedLoadingBar(control) && (bool?)control[StillMark] != true;

    private static bool NamedLoadingBar(JsonObject control) =>
        (string?)control["kind"] == "ProgressBar"
        && OperationFloor.NamesLoadingBar(ComputerUseSuccessCheck.Fold((string?)control["name"]));

    // The mark LookAsync leaves on a loading bar that stood still through the reads again.
    private const string StillMark = "still";

    /// <summary>
    /// Ronda 20b (v3-43): the loading bars of a look, each as «name=value», in the view's order; null when one of them
    /// exposes no value (an indeterminate bar, which is loading for as long as it shows).
    /// </summary>
    internal static string? LoadingBarsSignature(JsonObject view)
    {
        var parts = new List<string>();
        foreach (JsonObject control in (view["controls"] as JsonArray ?? []).OfType<JsonObject>().Where(NamedLoadingBar))
        {
            if ((string?)control["value"] is not { Length: > 0 } value
                || !double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out _))
            {
                return null;
            }

            parts.Add(ComputerUseSuccessCheck.Fold((string?)control["name"]) + "=" + value);
        }

        return parts.Count == 0 ? null : string.Join('\n', parts);
    }

    /// <summary>
    /// Ronda 20b (v3-43): marks the loading bars of a look as standing still: the Explorer's and the Control Panel's
    /// «Cargando» bar shows value 0 on every page, and never goes away. They stop counting as loading
    /// (<see cref="ShowsLoading"/>, so a question's check reads the page) and stay out of what the final quotes.
    /// </summary>
    internal static void MarkLoadingBarsStill(JsonObject view)
    {
        foreach (JsonObject control in (view["controls"] as JsonArray ?? []).OfType<JsonObject>().Where(NamedLoadingBar))
        {
            control[StillMark] = true;
        }
    }

    // Where a still bar is remembered: the window's process (its name and id), never its title, which every navigation
    // of an Explorer window changes.
    private static string WindowKey(JsonObject view) =>
        $"{(string?)view["window"]?["process"]}|{view["window"]?["processId"]?.ToJsonString()}";

    // The model saw no step on a look taken right after a verified act that changed the screen, and that look lists
    // fewer controls than the screen the act was taken from: the act tore the screen down (a page being replaced) and
    // it may not be drawn yet. Once per act, it is looked at again every PageLookInterval, at most PageLooks times,
    // until it changes and then holds still; true when it changed, so the loop looks and decides again.
    /// <summary>
    /// Ronda 20b, palanca 8: a look showing only the window's frame: nothing to act on (<see cref="ActionableCount"/>:
    /// no title bar, caption button or system menu) and at most a title's worth of written text. A splash or a game's
    /// canvas that writes its page is read as today.
    /// </summary>
    internal static bool ShowsOnlyTheFrame(JsonObject view) =>
        ActionableCount(view) == 0 && TextCount(view) <= 2 && !CloseIsTheWayOut(view);

    /// <summary>
    /// Review 3 of palanca 8 (B2), twin of the mind's <c>_frame_off_goal</c>: a close caption button in a title bar is
    /// the way out of what the view shows when that title bar is a dialog's drawn over the window (narrower than the
    /// view's widest one), or when the view shows content outside its title bars and none of it is to act on (a
    /// notice that only writes): such a view is a window to leave, not a frame still waiting for its content.
    /// </summary>
    internal static bool CloseIsTheWayOut(JsonObject view)
    {
        JsonObject[] controls = [.. (view["controls"] as JsonArray ?? []).OfType<JsonObject>()];
        JsonObject[] bars = [.. controls.Where(control => (string?)control["kind"] == "TitleBar" && control["rect"] is JsonObject)
            .Select(control => (JsonObject)control["rect"]!)];
        if (bars.Length == 0)
        {
            return false;
        }

        double widest = bars.Max(bar => Number(bar["w"]));
        JsonObject[] closes = [.. controls.Where(control => CaptionInTitleBar(control, bars)
            && ComputerUseSuccessCheck.Fold((string?)control["name"]).Split(' ', StringSplitOptions.RemoveEmptyEntries)
                is [("cerrar" or "close"), ..])];
        if (closes.Length == 0)
        {
            return false;
        }

        if (closes.Any(close => bars.Where(bar => Holds(bar, (JsonObject)close["rect"]!)).All(bar => Number(bar["w"]) < widest)))
        {
            return true;
        }

        JsonObject[] content = [.. controls.Where(control =>
            (string?)control["kind"] is not ("Pane" or "Window" or "Document" or "Group" or "Custom" or "TitleBar")
            && (bool?)control["systemMenu"] != true
            && !(control["rect"] is JsonObject rect && bars.Any(bar => Holds(bar, rect))))];
        return content.Length > 0 && content.All(control => (string?)control["kind"] is "Text" or "Image"
            || ((string?)control["state"] ?? string.Empty).Contains("readonly", StringComparison.Ordinal));
    }

    // Whether a title bar holds the centre of a rectangle.
    private static bool Holds(JsonObject bar, JsonObject rect)
    {
        double x = Number(rect["x"]) + Number(rect["w"]) / 2;
        double y = Number(rect["y"]) + Number(rect["h"]) / 2;
        return Number(bar["x"]) <= x && x <= Number(bar["x"]) + Number(bar["w"])
            && Number(bar["y"]) <= y && y <= Number(bar["y"]) + Number(bar["h"]);
    }

    internal static readonly System.Text.RegularExpressions.Regex WebAddress = new(
        @"^(?:https?://)?(?:[\w-]+\.)+[^\W\d_]{2,}(?::\d+)?(?:[/?#]|$)",
        System.Text.RegularExpressions.RegexOptions.CultureInvariant);

    // A browser showing a site (a field named as the address holds a web address) whose page is not exposed yet: no
    // document the size of a page (a quarter of the window) in the view.
    internal static bool PageNotExposed(JsonObject view)
    {
        if (view["controls"] is not JsonArray controls || view["window"]?["rect"] is not JsonObject windowRect)
        {
            return false;
        }

        bool browser = controls.Any(node => node is JsonObject control
            && (string?)control["kind"] is "Edit" or "ComboBox"
            && ComputerUseSuccessCheck.Fold((string?)control["name"]).Split(' ', StringSplitOptions.RemoveEmptyEntries)
                .Any(word => word.StartsWith("direccion", StringComparison.Ordinal) || word is "address" or "url")
            && WebAddress.IsMatch(((string?)control["value"] ?? string.Empty).Trim()));
        if (!browser)
        {
            return false;
        }

        double windowArea = Area(windowRect);
        return windowArea > 0 && !controls.Any(node => node is JsonObject control
            && (string?)control["kind"] == "Document"
            && control["rect"] is JsonObject rect
            && Area(rect) >= windowArea / 4);
    }

    /// <summary>
    /// A window of an application launched moment ago is still starting, up to <see cref="StartWait"/>, while it
    /// reads like a splash (≤1 control to act on and ≤5 written lines, read with OCR) or while it is still changing:
    /// a look is compared with the last one taken at least <see cref="StartSettle"/> before it (its window, controls
    /// and written text, and the image of a window that shows neither), and the application has started when two
    /// such looks coincide. v3 point 1, measured on a game launcher with no accessible tree: 2 written lines at 4.5 s,
    /// 16 at 8.2 s, 35 from 11.8 s on; the old rule (same window, more than 5 lines) took the half-drawn 16-line page.
    /// A window that never changes and never shows anything is taken at <see cref="StartWait"/>.
    /// </summary>
    internal static bool StillStarting(JsonObject state, JsonObject view, TimeSpan waited)
    {
        if (waited >= StartWait)
        {
            return false;
        }

        string look = StartingLook(view);
        long at = (long)waited.TotalMilliseconds;
        string? previous = (string?)state["startingLook"];
        if (previous is null || !string.Equals(previous, look, StringComparison.Ordinal))
        {
            // Changed (or the first look): this look is what the next ones are compared with.
            state["startingLook"] = look;
            state["startingLookAt"] = at;
            return true;
        }

        // The same as a look taken less than StartSettle before: not two looks apart yet.
        if (at - ((long?)state["startingLookAt"] ?? 0) < (long)StartSettle.TotalMilliseconds)
        {
            return true;
        }

        return ActionableCount(view) <= 1 && TextCount(view) <= 5;
    }

    // lat-apertura-clic: a window showing this many controls to act on is an interface that is up, not a splash or a
    // blank web view (the click's own rule, WindowsVisibleControlAdapter's VisibleClickTiming.InterfaceUp, analysis
    // r3a M7).
    internal const int InterfaceUp = 20;

    // Ronda 22 (r18 t2-c10, t4-c06: a document window already drawn waited the whole StartWait because a status line or
    // a ribbon count kept changing between looks): how close two opening trees are to read as the same interface.
    internal const double SettledShare = 0.9;
    internal const double SettledCountDrift = 0.05;

    // Review 1 of motor-listas-abiertas (finding 2): the whole tree may gain at most one control between two looks (a
    // status line or a tooltip that comes and goes); more is a tree still loading past the view's cap, whose shown
    // controls (always the same first 60) say nothing of it. Only a shrink takes the wider drift.
    internal const int SettledGrowth = 1;

    /// <summary>
    /// Ronda 22 (r18 t2-c10 Word, t4-c06 Excel: 35.8 s and 33.9 s waiting for a start that had happened): a window
    /// opened cold has started when it shows at least <see cref="InterfaceUp"/> controls to act on and its tree
    /// reads almost as the previous look's: the same window, a whole-tree count that gained at most
    /// <see cref="SettledGrowth"/> control and lost at most <see cref="SettledCountDrift"/> of it (two controls at
    /// least), and at least <see cref="SettledShare"/> of the controls to act on in common (by kind and name, over both
    /// looks). A tree that grows by more than one control between looks (past the view's cap too, where the shown
    /// controls stay the same), another window, or one whose controls were mostly replaced is still starting.
    /// </summary>
    internal static bool InterfaceUpAndSettled(JsonObject view, string? previousTree)
    {
        if (ActionableCount(view) < InterfaceUp || previousTree is null)
        {
            return false;
        }

        // Each line of a tree ends in a line break: the last piece is empty (a look without a handle keeps its first).
        string[] now = OpeningTree(view).Split('\n')[..^1];
        string[] before = previousTree.Split('\n')[..^1];
        if (now.Length < 2 || before.Length < 2 || !string.Equals(now[0], before[0], StringComparison.Ordinal)
            || !int.TryParse(now[1], out int countNow) || !int.TryParse(before[1], out int countBefore))
        {
            return false;
        }

        if (countNow - countBefore > SettledGrowth
            || countBefore - countNow > Math.Max(2, (int)Math.Ceiling(countBefore * SettledCountDrift)))
        {
            return false;
        }

        var controlsNow = new HashSet<string>(now.Skip(2), StringComparer.Ordinal);
        var controlsBefore = new HashSet<string>(before.Skip(2), StringComparer.Ordinal);
        int shared = controlsNow.Count(controlsBefore.Contains);
        int union = controlsNow.Count + controlsBefore.Count - shared;
        return union > 0 && shared >= SettledShare * union;
    }

    /// <summary>What two looks at a starting window compare: its handle, the whole tree's count of controls (past
    /// the view's cap) and the controls to act on by kind and name, in order of name (a list re-sorted by its values
    /// still reads the same), never their values.</summary>
    internal static string OpeningTree(JsonObject view)
    {
        var tree = new StringBuilder();
        tree.Append(view["window"]?["hwnd"]?.ToJsonString()).Append('\n')
            .Append((int?)view["controlCount"] ?? ControlCount(view)).Append('\n');
        IEnumerable<string> named = Actionable(view)
            .Select(control => (string?)control["kind"] + "|" + (string?)control["name"])
            .Order(StringComparer.Ordinal);
        foreach (string control in named)
        {
            tree.Append(control).Append('\n');
        }

        return tree.ToString();
    }

    // Function words a target says that name no control («cerrar esta pestaña», «para», «with»).
    private static readonly HashSet<string> GoalFunctionWords = new(StringComparer.Ordinal)
    {
        "esta", "este", "esto", "estas", "estos", "esa", "ese", "eso", "aquella", "aquel", "para", "pero", "como",
        "donde", "cuando", "desde", "hasta", "sobre", "entre", "hacia", "todo", "toda", "todos", "todas", "otra",
        "otro", "algo", "luego", "despues", "ahora", "mismo", "misma", "aplicacion", "ventana", "pantalla", "boton",
        "this", "that", "these", "those", "with", "from", "into", "onto", "over", "then", "there", "here", "some",
        "what", "when", "where", "which", "while", "after", "before", "window", "screen", "button", "please",
    };

    /// <summary>
    /// Review of lat-apertura-clic (finding 3): the opening's wait ends at its first look only on a control the
    /// sub-goal's target names that a person could act on (<see cref="ActionableCount"/>'s kinds, never a caption
    /// button, a pane or a written text such as «Cargando tu biblioteca»), by one of the target's words as a whole word
    /// of its name (four letters or more, not a function word, not the application's name): «esta» is not inside
    /// «pestaña». Estabilización N1 (banco h2 n1, «seleccionar lapiz» in Paint): the target is what the planned check
    /// names (<see cref="CheckNames"/>), never the goal's verb: «seleccionar» named Paint's «Seleccionar» tool on a
    /// ribbon still loading without «Lápiz», and that partial look was decided on. No check, no target to wait for.
    /// </summary>
    internal static bool TargetActionable(string? successCheck, string? application, JsonObject view)
    {
        if (view["controls"] is not JsonArray controls)
        {
            return false;
        }

        var applicationWords = new HashSet<string>(
            ComputerUseSuccessCheck.Fold(application).Split(' ', StringSplitOptions.RemoveEmptyEntries),
            StringComparer.Ordinal);
        char[] separators = [' ', ',', '.', ';', ':', '«', '»', '"', '\'', '(', ')', '¿', '?', '¡', '!', '-', '/', '|', '='];
        string[] words = [.. CheckNames(successCheck)
            .SelectMany(name => name.Split(separators, StringSplitOptions.RemoveEmptyEntries))
            .Where(word => word.Length >= 4 && !applicationWords.Contains(word) && !GoalFunctionWords.Contains(word))];
        if (words.Length == 0)
        {
            return false;
        }

        foreach (JsonObject control in Actionable(view))
        {
            string[] named = ComputerUseSuccessCheck.Fold((string?)control["name"])
                .Split(separators, StringSplitOptions.RemoveEmptyEntries);
            if (named.Any(word => words.Contains(word, StringComparer.Ordinal)))
            {
                return true;
            }
        }

        return false;
    }

    // The folded names a planned check reads, atom by atom (AtomPlaceName: a control's without its state); of a step
    // done, only a click's label is a name (as AliasAtom reads it), never a key or what was typed.
    private static IEnumerable<string> CheckNames(string? successCheck) =>
        (successCheck ?? string.Empty).Split(['|', '&'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Select(atom => AtomKindOf(atom) != "stepdone" ? AtomPlaceName(atom)
                : atom[(atom.IndexOf(':', StringComparison.Ordinal) + 1)..].Split(':', 2) is [var operation, var label]
                    && operation.Trim() == "input.visible.click" ? ComputerUseSuccessCheck.Fold(label) : string.Empty);

    // What a starting window shows: the window, its controls and its written text, and the image's hash only when
    // the window shows neither controls nor text (a caret blinking in a loaded editor changes the image of a window
    // that is already still, and every cold opening would wait the whole StartWait).
    private static string StartingLook(JsonObject view)
    {
        var look = new StringBuilder();
        look.Append(view["window"]?["hwnd"]?.ToJsonString()).Append('\n').Append(ViewSignature(view));
        // Review of lat-apertura-clic (finding 2): the whole tree's count, past the view's cap of 60 controls; a tree
        // that still grows beyond what the view shows is still being built.
        if ((int?)view["controlCount"] is { } counted)
        {
            look.Append("\ncount ").Append(counted);
        }
        // A window with a tree to act on is compared by its tree, never by its text (the OCR's own jitter).
        if (ActionableCount(view) <= 1 && view["text"] is JsonObject text)
        {
            look.Append(OcrSteady(text.ToJsonString()));
        }

        if (ControlCount(view) <= 1 && TextCount(view) == 0)
        {
            look.Append('\n').Append((string?)view["surface"]);
        }

        return look.ToString();
    }

    /// <summary>
    /// Ronda 22 (r18 t2-c10: «Documentol» one look, «Documento1» the next): the written text of a starting window as
    /// two looks compare it, without the letters OCR reads one for another (l, i, | and ! as 1; o as 0) nor case and
    /// spaces. What a window writes anew (more lines, other words) still changes the look.
    /// </summary>
    internal static string OcrSteady(string text)
    {
        var steady = new StringBuilder(text.Length);
        foreach (char letter in text.ToLowerInvariant())
        {
            switch (letter)
            {
                case 'l' or 'i' or '|' or '!':
                    steady.Append('1');
                    break;
                case 'o':
                    steady.Append('0');
                    break;
                case ' ' or '\t':
                    break;
                default:
                    steady.Append(letter);
                    break;
            }
        }

        return steady.ToString();
    }

    // Controls a person could act on: a frame, a pane or a read-only address bar is the shell an application draws
    // before its content (measured on Spotify starting: an address bar and two panes, «x» the only written line).
    // The window's caption buttons are not content either (measured on WhatsApp: Minimize, Maximize, Close and two
    // panes were all its tree exposed).
    internal static int ActionableCount(JsonObject view) => Actionable(view).Count();

    // The view's controls to act on (IsActionable), without the caption buttons drawn inside one of its title bars
    // whatever their name says after the act (ronda 20b, palanca 8, pasada r18 v3-62: a packaged application's frame
    // names them «Minimizar Seguridad de Windows», four words, and its frame alone counted as five controls to act on).
    private static IEnumerable<JsonObject> Actionable(JsonObject view)
    {
        JsonObject[] controls = [.. (view["controls"] as JsonArray ?? []).OfType<JsonObject>()];
        JsonObject[] bars = [.. controls.Where(control => (string?)control["kind"] == "TitleBar" && control["rect"] is JsonObject)
            .Select(control => (JsonObject)control["rect"]!)];
        return controls.Where(control => IsActionable(control) && !CaptionInTitleBar(control, bars));
    }

    private static bool CaptionInTitleBar(JsonObject control, JsonObject[] bars)
    {
        if (bars.Length == 0 || (string?)control["kind"] != "Button" || control["rect"] is not JsonObject rect)
        {
            return false;
        }

        string[] words = ComputerUseSuccessCheck.Fold((string?)control["name"]).Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (words.Length == 0 || !CaptionWords.Contains(words[0], StringComparer.Ordinal))
        {
            return false;
        }

        double x = Number(rect["x"]) + Number(rect["w"]) / 2;
        double y = Number(rect["y"]) + Number(rect["h"]) / 2;
        return bars.Any(bar => Number(bar["x"]) <= x && x <= Number(bar["x"]) + Number(bar["w"])
            && Number(bar["y"]) <= y && y <= Number(bar["y"]) + Number(bar["h"]));
    }

    // Ronda 20b, palanca 8 (pasada r18, v3-62): the window's system menu chain under its title bar (the provider marks
    // it «systemMenu») is the frame too: an application showing only its frame and that menu had «2 controls to act on»
    // and was taken as started before its content came.
    private static bool IsActionable(JsonObject control) =>
        (string?)control["kind"] is not ("Pane" or "Window" or "Document" or "Group" or "Custom" or "TitleBar" or "Image" or "Text")
        && !((string?)control["state"] ?? string.Empty).Contains("readonly", StringComparison.Ordinal)
        && (bool?)control["systemMenu"] != true
        && !IsCaptionButton(control);

    private static readonly string[] CaptionWords =
        ["minimizar", "maximizar", "restaurar", "cerrar", "minimize", "maximize", "restore", "close"];

    private static bool IsCaptionButton(JsonObject control)
    {
        if ((string?)control["kind"] != "Button")
        {
            return false;
        }

        string[] words = ComputerUseSuccessCheck.Fold((string?)control["name"]).Split(' ', StringSplitOptions.RemoveEmptyEntries);
        return words.Length is > 0 and <= 3 && CaptionWords.Contains(words[0], StringComparer.Ordinal);
    }

    /// <summary>
    /// Encargo CS (banco fz1 s12, Steam cold after a restart: «Actualizando Steam...» at 0, «Verificando instalación...»
    /// and «Cancelar» alone): the progress window an application shows while it starts (an updater, an installation
    /// check) before its main window replaces it. A progress bar of any name, at most one control to act on besides the
    /// bars, and no control the planned check names (a mission that asks to cancel the update has its target there).
    /// </summary>
    internal static bool ProgressSplash(JsonObject view, string? successCheck, string? application) =>
        view["controls"] is JsonArray controls
        && controls.OfType<JsonObject>().Any(control => (string?)control["kind"] == "ProgressBar")
        && Actionable(view).Count(control => (string?)control["kind"] != "ProgressBar") <= 1
        && !TargetActionable(successCheck, application, view);

    /// <summary>
    /// Review 1 of ronda 21 (finding 1, v3-34): a look of the opening that may be handed on stale when the reads after it
    /// fail: an interface that is up (more than one control to act on) showing no loading indicator. A splash or a
    /// loading view never reaches the model as the window kept.
    /// </summary>
    internal static bool KeptWhileOpening(JsonObject view) => ActionableCount(view) > 1 && !ShowsLoading(view);

    /// <summary>
    /// Review 1 of ronda 21 (finding 1, v3-34): while an application opened cold is within <see cref="StartWait"/> and
    /// its look shows a loading indicator (<see cref="ShowsLoading"/>), the look is not handed to the model: the wait
    /// goes on. A loading bar that stood still between two looks of the same tree is the window's furniture (ronda 20b,
    /// v3-43), and the look goes on as before.
    /// </summary>
    internal static bool LoadingWhileStarting(
        JsonObject view, string tree, string? previousTree, string? bars, string? previousBars, TimeSpan waited) =>
        waited < StartWait && ShowsLoading(view)
        && (bars is null || !string.Equals(tree, previousTree, StringComparison.Ordinal)
            || !string.Equals(bars, previousBars, StringComparison.Ordinal));
}
