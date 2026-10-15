using System.Text.Json;
using System.Text.RegularExpressions;
using Baxy.Kernel.Operations;

namespace Baxy.Kernel.Policy;

/// <summary>
/// Confirmation policy per mode. Decisión del dueño 2026-09-20 (D3,
/// artifacts/comprobaciones/C03/DECISIONES_DUENO_2026-09-20.md): «lo que debe
/// pedir permisos sólo deben ser cosas destructivas o irreparables». Reproducir,
/// navegar, copiar, capturar, pulsar, escribir, radios y ajustes van directos en
/// modo normal; lo que llega a otra persona (mensajes y correo) y lo que destruye
/// o interrumpe (work_loss, session_disruption, monetary) sigue preguntando, e
/// instalar también (decisión 8 del dueño, 2026-10-10). Las etiquetas de riesgo
/// del catálogo no cambian: los sellos históricos las citan.
///
/// Motor de computer use (CONTRATO_VISTA_ACCION.md §2.1, D15): un paso del bucle
/// lleva el riesgo de su primitiva evaluado con los argumentos exactos delante.
/// Un clic cuya etiqueta nombra un canal de voz o una llamada (alguien te oye),
/// o un botón de enviar, publicar, responder, comentar, compartir, unirse o emitir
/// en directo (ronda 29, v3-53: «Iniciar Transmisión»), y cualquier Enter o Espacio
/// (el kernel no ve qué tiene el foco), salen al mundo o llegan a una persona; un clic que
/// compra, paga, elimina o desinstala no se deshace. Ambos piden confirmación en
/// modo normal, ligada a esa misma invocación. Las palabras de lo que sale al mundo
/// son dato (<see cref="WorldActs"/>). Igual una invocación cuyo argumento cierra de una vez todo lo
/// que la persona tiene abierto en una superficie (todas las pestañas de su
/// navegador): pierde su sesión, aunque la operación con otro argumento no.
/// Revisión de seguridad 2026-10-07: el verbo de enviar, reenviar, invitar o
/// responder abre la etiqueta sea lo que sea lo que siga; un verbo destructivo
/// (no guardar, descartar, mover a la papelera, quitar, vaciar, limpiar,
/// eliminar, desinstalar) cuenta en cualquier lugar de una etiqueta corta; y
/// Suprimir fuera de un campo de texto borra lo seleccionado, así que pregunta.
/// </summary>
public static partial class RiskPolicy
{
    // External communication that reaches another person: the only external
    // operations that keep asking in normal mode.
    private static readonly HashSet<string> ExternalRequiringConfirmation = new(StringComparer.Ordinal)
    {
        "message.send",
        "message.send.test",
        "email.latest.reply",
        "email.send",
    };

    public static PolicyDecision Evaluate(
        OperationRisk risk,
        ConfirmationMode mode = ConfirmationMode.Normal,
        string? operation = null,
        JsonElement? arguments = null)
    {
        if (risk == OperationRisk.Forbidden)
        {
            return PolicyDecision.Deny;
        }

        if (mode == ConfirmationMode.Bypass)
        {
            return PolicyDecision.Allow;
        }

        // Identity: apagar / cerrar sesión van directos. The catalog still
        // labels system.power as work_loss so historical seals do not move.
        if (string.Equals(operation, "system.power", StringComparison.Ordinal))
        {
            return PolicyDecision.Allow;
        }

        if (arguments is { } invocation
            && (ReachesAPerson(operation, invocation)
                || CannotBeUndone(operation, invocation)
                || LosesTheSession(operation, invocation)
                || ShellMayChange(operation, invocation)))
        {
            return PolicyDecision.RequireConfirmation;
        }

        return risk switch
        {
            OperationRisk.ReadOnly => PolicyDecision.Allow,
            OperationRisk.Reversible => PolicyDecision.Allow,
            // privacy_sensitive: leer, copiar, capturar, escribir, radios y ajustes no
            // destruyen nada (D3); instalar pregunta desde la decisión 8 del dueño.
            OperationRisk.Sensitive => PolicyDecision.Allow,
            OperationRisk.External => operation is not null && ExternalRequiringConfirmation.Contains(operation)
                ? PolicyDecision.RequireConfirmation
                : PolicyDecision.Allow,
            OperationRisk.Irreversible => PolicyDecision.RequireConfirmation,
            _ => PolicyDecision.Deny,
        };
    }

    /// <summary>
    /// BAXY Renew (2026-10-15; identity: confirm what destroys data and what goes out to the world): a console command
    /// runs directly only when it provably just reads. Every stage of its pipeline starts with a reading cmdlet, and
    /// nothing redirects, chains another command, calls .NET or a method, or runs a script block, a variable or a
    /// sub-expression. Anything else (writing, deleting, installing, sending over the network, running a program) asks
    /// first with the exact command, as Claude Code and OpenClaw's exec approvals do. Fail-closed: when in doubt it asks.
    /// </summary>
    public static bool ShellMayChange(string? operation, JsonElement arguments)
    {
        if (!string.Equals(operation, "shell.command.run", StringComparison.Ordinal))
        {
            return false;
        }

        if (arguments.ValueKind != JsonValueKind.Object
            || !arguments.TryGetProperty("command", out JsonElement value)
            || value.ValueKind != JsonValueKind.String
            || value.GetString() is not { Length: > 0 } command
            || command.IndexOfAny(['>', '<', '&', ';', '`', '{', '}', '$', '(', ')', '[', ']', '@', '\n', '\r']) >= 0)
        {
            return true;
        }

        foreach (string stage in command.Split('|'))
        {
            string[] words = stage.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (words.Length == 0)
            {
                return true;
            }

            string head = words[0].ToLowerInvariant();
            bool reads = head == "git"
                ? words.Length >= 2 && ReadingGit.Contains(words[1].ToLowerInvariant())
                : ReadingCommands.Contains(head);
            if (!reads)
            {
                return true;
            }
        }

        return false;
    }

    // Cmdlets, their built-in aliases and programs that only read and print, with no parameter that writes or sends.
    private static readonly HashSet<string> ReadingCommands = new(StringComparer.Ordinal)
    {
        "get-childitem", "gci", "dir", "ls", "get-content", "gc", "cat", "type", "get-item", "gi",
        "get-itemproperty", "gp", "get-location", "gl", "pwd", "get-process", "gps", "ps", "get-service", "gsv",
        "get-date", "get-command", "gcm", "get-help", "get-volume", "get-psdrive", "gdr", "get-computerinfo",
        "get-netadapter", "get-netipaddress", "get-filehash", "get-ciminstance", "gcim", "get-disk",
        "get-physicaldisk", "get-printer", "get-hotfix", "get-culture", "get-timezone", "get-host", "get-winevent",
        "get-uptime", "select-string", "sls", "select-object", "select", "where-object", "where", "sort-object",
        "sort", "group-object", "group", "measure-object", "measure", "compare-object", "compare", "format-table",
        "ft", "format-list", "fl", "format-wide", "fw", "out-string", "convertto-json", "convertfrom-json",
        "convertto-csv", "convertfrom-csv", "resolve-path", "rvpa", "split-path", "join-path", "test-path",
        "write-output", "echo", "write", "hostname", "whoami", "systeminfo", "tasklist",
    };

    private static readonly HashSet<string> ReadingGit = new(StringComparer.Ordinal) { "status", "log", "diff", "show" };

    /// <summary>
    /// Whether this exact invocation of a computer-use primitive leaves the
    /// computer or reaches another person: joining a voice channel or a call,
    /// pressing «enviar/send», «publicar/post», «responder/reply»,
    /// «comentar/comment», «compartir/share», «unirse/join» or going live
    /// («iniciar transmisión», «go live»), or pressing Enter or Space, which may
    /// send what is written. Bilingual, general, and never naming an application.
    /// </summary>
    public static bool ReachesAPerson(string? operation, JsonElement arguments)
    {
        if (arguments.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        switch (operation)
        {
            case "input.visible.click":
                // The result a search burst chooses (choose) is pressed too: read as its label is.
                return ClickLabels(arguments).Any(LabelReachesAPerson);
            case "input.key.press":
                // Enter, and Space on a focused send or reply control, hand what was written to someone, or press a
                // control that reaches someone (a voice channel highlighted in a search). The kernel does not see what
                // holds the focus, and a label the step gave it would be the model's own word about its own act:
                // fail-closed, both always ask (auditoría K8).
                return KeyOf(arguments) is "enter" or "space";
            default:
                return false;
        }
    }

    /// <summary>
    /// Whether this exact click commits what cannot be taken back: buying or
    /// paying (checkout, place order) and deleting or uninstalling. Read from
    /// the label the step names, bilingual, never naming an application.
    /// </summary>
    public static bool CannotBeUndone(string? operation, JsonElement arguments)
    {
        if (arguments.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        // The Delete key outside a text field deletes what is selected (a file to the bin, a message, an item of a
        // list). Fail-closed: it asks unless the step declares the keyboard is on a text field, where it only
        // erases characters. (Enter and Space already ask: ReachesAPerson.)
        if (string.Equals(operation, "input.key.press", StringComparison.Ordinal))
        {
            return KeyOf(arguments) is "delete" && TargetOf(arguments) is not "text_field";
        }

        if (!string.Equals(operation, "input.visible.click", StringComparison.Ordinal))
        {
            return false;
        }

        // Goal v3 point 2: the click that confirms writing over a file that already exists («Sí» under «¿Desea
        // reemplazarlo?») loses that file.
        if (arguments.TryGetProperty("consequence", out JsonElement consequence)
            && consequence.ValueKind == JsonValueKind.String
            && string.Equals(consequence.GetString(), "overwrite", StringComparison.Ordinal))
        {
            return true;
        }

        return ClickLabels(arguments).Any(LabelCannotBeUndone);
    }

    // What a click presses, by name: its label and, in a search burst (goal v3 point 0, fix 3), the result it chooses.
    private static IEnumerable<string?> ClickLabels(JsonElement arguments)
    {
        foreach (string name in new[] { "label", "choose" })
        {
            if (arguments.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String)
            {
                yield return value.GetString();
            }
        }
    }

    /// <summary>
    /// A label that commits what cannot be taken back: buying or paying anywhere, or a destructive verb anywhere in
    /// a short label (six words or fewer: a button or a menu entry, not a sentence that mentions deleting).
    /// </summary>
    internal static bool LabelCannotBeUndone(string? label)
    {
        if (string.IsNullOrWhiteSpace(label))
        {
            return false;
        }

        string folded = Fold(label);
        return IrreversibleAct().IsMatch(folded)
            || (folded.Split(' ', StringSplitOptions.RemoveEmptyEntries).Length <= ShortLabelWords && DestructiveVerb().IsMatch(folded));
    }

    // A button or a menu entry, not a sentence that mentions deleting.
    private const int ShortLabelWords = 6;

    private static string? KeyOf(JsonElement arguments) =>
        arguments.TryGetProperty("key", out JsonElement key) && key.ValueKind == JsonValueKind.String
            ? key.GetString()
            : null;

    private static string? TargetOf(JsonElement arguments) =>
        arguments.TryGetProperty("target", out JsonElement target) && target.ValueKind == JsonValueKind.String
            ? target.GetString()
            : null;

    /// <summary>
    /// Whether this exact invocation closes, in one step, everything the person
    /// has open on a surface: every tab of their browser (unsaved forms,
    /// signed-in pages). The same operation with another argument does not.
    /// </summary>
    public static bool LosesTheSession(string? operation, JsonElement arguments) =>
        arguments.ValueKind == JsonValueKind.Object
        && operation is not null
        && SessionClosingArguments.TryGetValue(operation, out (string Name, string Value) closing)
        && arguments.TryGetProperty(closing.Name, out JsonElement value)
        && value.ValueKind == JsonValueKind.String
        && string.Equals(value.GetString(), closing.Value, StringComparison.Ordinal);

    // Operation → the argument value that closes all at once.
    private static readonly Dictionary<string, (string Name, string Value)> SessionClosingArguments =
        new(StringComparer.Ordinal)
        {
            ["browser.control"] = ("action", "close_all"),
        };

    // The words are data (WorldActs): a voice channel or a call, a control that sends, publishes, shares or joins, and
    // one that goes live. A noun that only shares the stem («Enviados», «Comentarios (12)», «Shared with me») does not.
    internal static bool LabelReachesAPerson(string? label) =>
        !string.IsNullOrWhiteSpace(label) && WorldActs.Reaches(Fold(label));

    /// <summary>
    /// Whether pressing a control of this name would need the person's word (it leaves the computer, reaches a person
    /// or cannot be undone) when the label a click was judged by does not: the policy read another name than the one
    /// about to be pressed, so nothing is pressed (ronda 29: a label that names its control by a part of its name).
    /// </summary>
    public static bool PressedNameAsksMoreThanItsLabel(string? label, string? pressedName) =>
        LabelAsks(pressedName) && !LabelAsks(label);

    /// <summary>
    /// Encargo V (banco e2, c7): the policy judges a click's label and the UIA worker resolves the control it presses,
    /// at times one the view never listed, by its name holding the label («cotele» pressed «Cotele!!!😎, Canal de voz,
    /// Choche» and joined the channel unasked). The worker refuses, before any press, a control whose name asks more
    /// than its label (<see cref="PressedNameAsksMoreThanItsLabel"/>), so the step names it and this policy asks. It is
    /// handed this one pattern over a folded name (<see cref="FoldHint"/> dropped): this policy's own words and verbs.
    /// </summary>
    public static string AsksPattern => Asks.Value.ToString();

    /// <summary>The trailing shortcut hint a fold drops («Enviar (Ctrl+Enter)»), for the worker's fold.</summary>
    public static string FoldHint => WorldActs.ShortcutHint.ToString();

    // Leaves the computer, reaches a person or cannot be undone: LabelReachesAPerson or LabelCannotBeUndone, as one.
    internal static bool LabelAsks(string? label) => !string.IsNullOrWhiteSpace(label) && Asks.Value.IsMatch(Fold(label));

    private static readonly Lazy<Regex> Asks = new(() => new Regex(
        "^(?:" + string.Join('|', WorldActs.Rules.Select(rule => Rule(rule.Pattern, rule.Unless, 0))
            .Append(Rule(IrreversibleAct().ToString(), null, 0))
            .Append(Rule(DestructiveVerb().ToString(), null, ShortLabelWords))) + ")",
        RegexOptions.CultureInvariant));

    // A rule as lookaheads from the start of a folded name: its pattern somewhere, its exception nowhere, and at most so
    // many words when it counts only in a short label.
    private static string Rule(string pattern, string? unless, int words) =>
        (unless is null ? string.Empty : $"(?!.*?(?:{unless}))")
        + (words > 0 ? $"(?=\\S+(?: \\S+){{0,{words - 1}}}$)" : string.Empty)
        + $"(?=.*?(?:{pattern}))";

    // Lower case, without accents, without format characters (a zero-width space or a direction mark inside a label
    // must not hide its verb) and without a trailing shortcut hint («Enviar (Ctrl+Enter)», «Delete (Supr)»).
    private static string Fold(string value)
    {
        string form = value.Normalize(System.Text.NormalizationForm.FormD).ToLowerInvariant();
        var builder = new System.Text.StringBuilder(form.Length);
        foreach (char character in form)
        {
            System.Globalization.UnicodeCategory category = System.Globalization.CharUnicodeInfo.GetUnicodeCategory(character);
            if (category is not (System.Globalization.UnicodeCategory.NonSpacingMark
                or System.Globalization.UnicodeCategory.Format))
            {
                builder.Append(character);
            }
        }

        string folded = string.Join(' ', builder.ToString().Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
        return WorldActs.ShortcutHint.Replace(folded, string.Empty).Trim();
    }

    // What cannot be taken back once clicked: buying and paying («Comprar ahora»,
    // «Buy now», «Pagar», «Pay», «Checkout», «Proceed to checkout», «Realizar
    // pedido», «Place order») and deleting or uninstalling («Eliminar», «Borrar»,
    // «Delete», «Desinstalar», «Uninstall»). The verb opens the label; checkout
    // and placing the order count wherever they appear.
    [GeneratedRegex(
        @"^(?:comprar|buy|pagar|pay|eliminar|elimina|borrar|borra|delete|desinstalar|desinstala|uninstall)(?:\s+\S+){0,3}$|\b(?:checkout|check\s+out|finalizar\s+(?:la\s+)?compra|realizar\s+(?:el\s+)?pedido|place\s+(?:your\s+)?order|confirmar\s+(?:la\s+)?compra|confirm\s+purchase)\b",
        RegexOptions.CultureInvariant)]
    private static partial Regex IrreversibleAct();

    // A destructive verb anywhere in a short label: not saving, discarding, closing without saving, moving to the
    // bin, removing, emptying, clearing, deleting, uninstalling («No guardar», «Don't save», «Descartar cambios»,
    // «Mover a la papelera», «Vaciar papelera de reciclaje», «Empty Recycle Bin», «Quitar de la biblioteca»,
    // «Remove», «Limpiar historial», «Clear all»). Only verb forms count: «Eliminados», «Deleted items» or
    // «Papelera de reciclaje» name a place, not an act.
    [GeneratedRegex(
        @"\b(?:no\s+guardar|no\s+guardes|don'?t\s+save|do\s+not\s+save|descartar|descarta|discard|cerrar\s+sin\s+guardar|close\s+without\s+saving|mover\s+a\s+(?:la\s+)?papelera|move\s+to\s+(?:the\s+)?(?:trash|bin|recycle\s+bin)|quitar|quita|remove|vaciar|vacia|empty|limpiar|limpia|clear|eliminar|elimina|delete|borrar|borra|desinstalar|desinstala|uninstall)\b",
        RegexOptions.CultureInvariant)]
    private static partial Regex DestructiveVerb();
}
