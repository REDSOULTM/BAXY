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
/// o pierde trabajo (work_loss) sigue preguntando, e instalar también (decisión 8
/// del dueño, 2026-10-10). Decisión del dueño 2026-10-25 («que Baxy no te moleste
/// todo el tiempo… sino para cosas que realmente son peligrosas»): crear un evento
/// en su propio calendario y Ctrl+W (cierra con gracia; el «No guardar» de la
/// aplicación ya pregunta) van directos. Las etiquetas de riesgo del catálogo no
/// cambian: los sellos históricos las citan.
///
/// Motor de computer use (CONTRATO_VISTA_ACCION.md §2.1, D15): un paso del bucle
/// lleva el riesgo de su primitiva evaluado con los argumentos exactos delante.
/// Un clic cuya etiqueta nombra un canal de voz o una llamada (alguien te oye),
/// o un botón de enviar, publicar, responder, comentar, compartir, unirse o emitir
/// en directo (ronda 29, v3-53: «Iniciar Transmisión»), y un Enter declarado sobre
/// un compositor de mensajes, salen al mundo o llegan a una persona; un clic que
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
    // External communication that reaches another person or sends the owner's content outside the machine: the only
    // external operations that keep asking in normal mode. The test message goes to a saved destination name (a real
    // email by mail). Decisión del dueño 2026-10-25 («que Baxy no te moleste todo el tiempo… sino para cosas que
    // realmente son peligrosas»): an event in the owner's own calendar (calendar.event.create) reaches nobody else and
    // goes directly.
    private static readonly HashSet<string> ExternalRequiringConfirmation = new(StringComparer.Ordinal)
    {
        "message.send",
        "message.send.test",
        "email.latest.reply",
        "email.send",
    };

    // Encargo 76 (banco diag-fd2b, F13 6 of 6: after memory.save failed with memory_disabled the model called
    // memory.enable, which ran unasked, and saved the fact): turning on what the owner switched off to keep their data
    // private changes a setting of theirs nobody asked for in that call. Identity («Memoria y privacidad»: the memory is
    // the person's to see, edit and erase; invariant 6, local and private) and OWASP LLM06 Excessive Agency (a human
    // approves a high-impact action) make it wait for their «sí», bound to this invocation; the memory panel's switch
    // is that «sí» (MemoryPanel). Turning it off keeps more private and goes directly. D3 (2026-09-20) let settings go
    // unasked: Windows' Wi-Fi, Bluetooth and settings, not BAXY's own privacy guard.
    private static readonly HashSet<string> PrivacyGuardsRequiringConfirmation = new(StringComparer.Ordinal)
    {
        "memory.enable",
    };

    // landingRead: the handler's preflight read where this exact invocation lands and lowered its risk; only the
    // undeclared Enter or space rule (K-2, PressesUndeclared), which stands because this policy cannot see that, yields.
    public static PolicyDecision Evaluate(
        OperationRisk risk,
        ConfirmationMode mode = ConfirmationMode.Normal,
        string? operation = null,
        JsonElement? arguments = null,
        bool landingRead = false)
    {
        // Decisión del dueño 2026-11-02 («bypass no debe pedir confirmación nunca… el modo normal ya tendría que
        // pedirla»): Bypass asks nothing, a message to another person included (it asked since 2026-10-21).
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
                || (!landingRead && PressesUndeclared(operation, invocation))
                || CannotBeUndone(operation, invocation)
                || LosesTheSession(operation, invocation)
                || ClicksUnseen(operation, invocation)
                || ShellMayChange(operation, invocation)))
        {
            return PolicyDecision.RequireConfirmation;
        }

        return risk switch
        {
            OperationRisk.ReadOnly => PolicyDecision.Allow,
            OperationRisk.Reversible => PolicyDecision.Allow,
            // privacy_sensitive: leer, copiar, capturar, escribir, radios y ajustes no
            // destruyen nada (D3); instalar pregunta desde la decisión 8 del dueño. Encender una guarda de privacidad
            // de BAXY que el dueño apagó (la memoria) pregunta (encargo 76).
            OperationRisk.Sensitive => operation is not null && PrivacyGuardsRequiringConfirmation.Contains(operation)
                ? PolicyDecision.RequireConfirmation
                : PolicyDecision.Allow,
            OperationRisk.External => operation is not null && ExternalRequiringConfirmation.Contains(operation)
                ? PolicyDecision.RequireConfirmation
                : PolicyDecision.Allow,
            OperationRisk.Irreversible => PolicyDecision.RequireConfirmation,
            _ => throw new ArgumentOutOfRangeException(nameof(risk)),
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

            // git is not among them: «git log --output=f» writes a file and «git diff» runs the external diff or textconv
            // program a repository configures (BAXY Renew audit 2026-10-15).
            if (!ReadingCommands.Contains(words[0].ToLowerInvariant()) || IpconfigChanges(words))
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
        "get-date", "get-command", "gcm", "get-volume", "get-psdrive", "gdr", "get-computerinfo",
        "get-netadapter", "get-netipaddress", "get-filehash", "get-ciminstance", "gcim", "get-disk",
        "get-physicaldisk", "get-printer", "get-hotfix", "get-culture", "get-timezone", "get-host", "get-winevent",
        "get-uptime", "select-string", "sls", "select-object", "select", "where-object", "where", "sort-object",
        "sort", "group-object", "group", "measure-object", "measure", "compare-object", "compare", "format-table",
        "ft", "format-list", "fl", "format-wide", "fw", "out-string", "convertto-json", "convertfrom-json",
        "convertto-csv", "convertfrom-csv", "resolve-path", "rvpa", "split-path", "join-path", "test-path",
        "write-output", "echo", "write", "hostname", "whoami", "systeminfo", "tasklist",
        // Propuesta para el PC (prueba en vivo de la versión final, renew_v6: «revisa BAXY-bench\server-vivo.log y dime
        // si hay errores en todo el archivo» asked the person before a findstr that only looks for a text): Windows'
        // findstr reads files and prints the lines that match; none of its switches writes, deletes or sends.
        "findstr",
        // Decisión del dueño 2026-10-25 («que Baxy no te moleste todo el tiempo»): the network and system readings a
        // person asks for. ipconfig only with a switch that reads (IpconfigChanges); «where» is already Where-Object's
        // alias above.
        "ipconfig", "netstat", "nslookup", "getmac", "ver", "test-connection", "get-nettcpconnection",
    };

    // ipconfig's switches that change the network instead of reading it (they ask): releasing or renewing the address,
    // flushing or registering DNS, setting a class id. Windows takes them with «/» or «-», and the console joins quoted
    // pieces into one argument («"/release"», «/re"new"»), so an argument is read without its quotes and the switch
    // may stand anywhere in it (fail-closed: an adapter whose name holds one asks too).
    private static readonly string[] IpconfigChangingSwitches = ["release", "renew", "flushdns", "registerdns", "setclassid"];

    private static bool IpconfigChanges(string[] words) =>
        string.Equals(words[0], "ipconfig", StringComparison.OrdinalIgnoreCase)
        && words.Skip(1).Any(word =>
        {
            string bare = new(word.Where(character => character is not ('"' or '\'' or '‘' or '’' or '“' or '”')).ToArray());
            return IpconfigChangingSwitches.Any(change => bare.Contains(change, StringComparison.OrdinalIgnoreCase));
        });

    /// <summary>
    /// Whether this exact invocation of a computer-use primitive leaves the
    /// computer or reaches another person: joining a voice channel or a call,
    /// pressing «enviar/send», «publicar/post», «responder/reply»,
    /// «comentar/comment», «compartir/share», «unirse/join» or going live
    /// («iniciar transmisión», «go live»), or Enter over a message composer
    /// that holds text. Bilingual, general, and never naming an application.
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
                // Enter, and space on a focused send or reply control, hand what was written to someone when the
                // step declares it lands on a message composer (the model declares it from the focused control).
                // Revisión de V (H1): or presses a control that reaches someone (a voice channel highlighted in a search).
                return KeyOf(arguments) is "enter" or "space"
                    && (TargetOf(arguments) is "message_composer" || LabelReachesAPerson(OntoOf(arguments)));
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
        // erases characters.
        // Goal v3 point 2: the click that confirms writing over a file that already exists («Sí» under «¿Desea
        // reemplazarlo?»), or Enter/Space on that focused «Sí», loses that file. The model declares it from the view it
        // was decided on.
        bool overwrites = arguments.TryGetProperty("consequence", out JsonElement consequence)
            && consequence.ValueKind == JsonValueKind.String
            && string.Equals(consequence.GetString(), "overwrite", StringComparison.Ordinal);
        if (string.Equals(operation, "input.key.press", StringComparison.Ordinal))
        {
            return overwrites || (KeyOf(arguments) is "delete" && TargetOf(arguments) is not "text_field")
                || (KeyOf(arguments) is "enter" or "space" && LabelCannotBeUndone(OntoOf(arguments)));
        }

        if (!string.Equals(operation, "input.visible.click", StringComparison.Ordinal))
        {
            return false;
        }

        if (overwrites)
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

    // Revisión de calidad del núcleo (final2): an empty or blank «onto» names nothing, as a missing one does (K-2 asks).
    private static string? OntoOf(JsonElement arguments) =>
        arguments.TryGetProperty("onto", out JsonElement onto) && onto.ValueKind == JsonValueKind.String
            && !string.IsNullOrWhiteSpace(onto.GetString())
            ? onto.GetString()
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

    /// <summary>
    /// Revisión 2026-10-22 (K-2): Enter or space whose step declares neither where the keyboard is («target») nor what
    /// it lands on («onto») may send what message.draft left written in a chat, and this policy cannot tell. Fail-closed:
    /// it asks. Declared on a text field it only types; declared onto a named control, that name is judged. Al máximo,
    /// K-2 refinada: the handler's preflight (IInvocationPreflight) reads the window the key goes to and lowers the
    /// press when that window is neither a messaging client nor a console (Evaluate's <c>landingRead</c>); one that is,
    /// or that cannot be read, keeps this question; so does an Enter whose window has a field holding text (auditoría de
    /// falsedades 2026-11-04, P6: the provider's preflight reads it). The windows are the providers' data, never this
    /// policy's.
    /// </summary>
    public static bool PressesUndeclared(string? operation, JsonElement arguments) =>
        string.Equals(operation, "input.key.press", StringComparison.Ordinal)
        && arguments.ValueKind == JsonValueKind.Object
        && KeyOf(arguments) is "enter" or "space"
        && TargetOf(arguments) is null
        && OntoOf(arguments) is null;

    /// <summary>
    /// Revisión 2026-10-22 (K-1): input.pointer.control's click presses whatever lies under the pointer, in a window no
    /// step named and under no label this policy can judge, so it may send, buy or delete. Fail-closed, as Suprimir
    /// outside a text field: it asks. Moving the pointer and scrolling press nothing.
    /// </summary>
    private static bool ClicksUnseen(string? operation, JsonElement arguments) =>
        string.Equals(operation, "input.pointer.control", StringComparison.Ordinal)
        && arguments.ValueKind == JsonValueKind.Object
        && arguments.TryGetProperty("action", out JsonElement action)
        && action.ValueKind == JsonValueKind.String
        && string.Equals(action.GetString(), "click", StringComparison.Ordinal);

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

    /// <summary>
    /// Encargo 83: a click that changes a setting of Windows waits for the person's yes, though no label says so: the
    /// handler reads the control it would press (IInvocationPreflight) and raises it. On a classic panel, whose controls
    /// carry numbers for identity, a button or a link tells by its own words: these, over a folded name, opening it. A Toggle or a
    /// button bound to a setting needs no word (Get-SystemChange).
    /// </summary>
    public static string SystemActsPattern =>
        @"^\W*(?:activar?|desactivar?|cambiar?|habilitar?|deshabilitar?|encender|enciende|apagar?|aplicar?|restablecer?|restaurar?"
        + @"|conectar?|desconectar?|aceptar?|guardar cambios|turn (?:on|off)|switch (?:on|off|to)|change|enable|disable|apply|reset"
        + @"|restore|connect|disconnect|accept|ok|save changes)\b";

    /// <summary>The trailing shortcut hint a fold drops («Enviar (Ctrl+Enter)»), for the worker's fold.</summary>
    public static string FoldHint => WorldActs.ShortcutHint.ToString();

    /// <summary>
    /// Auditoría del núcleo 2026-10-23: the look-alike letters a fold reads as the Latin letter they imitate, as pairs
    /// (look-alike, Latin), for the worker's fold too. A label «Еnviar» with a Cyrillic «Е», or «Εliminar» with a Greek
    /// one, looks like the verb to the person and to the model and asks as the verb does. Cyrillic and Greek lower case
    /// (a fold lowers first), and a few Latin variants the compatibility decomposition keeps.
    /// </summary>
    public static string Confusables => ConfusablePairs;

    private const string ConfusablePairs =
        "аaвbеeһhіiјjкkмmнhоoрpсcтtуyхxѕsԁdӏlԛqԝwүyґr"
        + "αaβbγyεeηnιiκkνvοoρpτtυuχxωw"
        + "ıiɑaɡgɩiſs";

    private static readonly Dictionary<char, char> LatinOf = Pairs(ConfusablePairs);

    private static Dictionary<char, char> Pairs(string pairs)
    {
        var map = new Dictionary<char, char>();
        for (int index = 0; index + 1 < pairs.Length; index += 2)
        {
            map.Add(pairs[index], pairs[index + 1]);
        }

        return map;
    }

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
    // must not hide its verb) and without a trailing shortcut hint («Enviar (Ctrl+Enter)», «Delete (Supr)»). Auditoría
    // del núcleo 2026-10-23: by compatibility (a full-width «Ｅｎｖｉａｒ», a ligature, a mathematical letter) and with
    // look-alike letters read as the Latin they imitate (<see cref="Confusables"/>).
    private static string Fold(string value)
    {
        string form = value.Normalize(System.Text.NormalizationForm.FormKD).ToLowerInvariant();
        var builder = new System.Text.StringBuilder(form.Length);
        foreach (char character in form)
        {
            System.Globalization.UnicodeCategory category = System.Globalization.CharUnicodeInfo.GetUnicodeCategory(character);
            if (category is not (System.Globalization.UnicodeCategory.NonSpacingMark
                or System.Globalization.UnicodeCategory.Format))
            {
                builder.Append(LatinOf.TryGetValue(character, out char latin) ? latin : character);
            }
        }

        string folded = string.Join(' ', builder.ToString().Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
        return WorldActs.ShortcutHint.Replace(folded, string.Empty).Trim();
    }

    // What cannot be taken back once clicked: buying and paying («Comprar ahora»,
    // «Buy now», «Pagar», «Pay», «Checkout», «Proceed to checkout», «Realizar
    // pedido», «Place order») and deleting or uninstalling («Eliminar», «Borrar»,
    // «Delete», «Desinstalar», «Uninstall»). The verb opens the label; checkout
    // and placing the order count wherever they appear. Uso real 2026-10-21 (e2e del notebook): «Cómpralo ya» opened a
    // checkout unasked, so the verb counts in its imperative and with its pronoun («Compra ahora», «Cómpralo ya»,
    // «Págalo»), and as «Purchase», «Adquirir» or «Pre-order»; the noun («Compras», «Historial de compras») does not.
    // Revisión de calidad del núcleo (final2): a sign before the verb or glued after it («¡Comprar!», «🛒 Comprar
    // ahora», «Pagar.») does not hide it.
    [GeneratedRegex(
        @"^\W*(?:compra(?:r(?:l[oa]s?)?|l[oa]s?)?|adquiri(?:r(?:l[oa])?)?|adquiere(?:l[oa])?|buy|purchase|pre-?(?:purchase|order)|paga(?:r(?:l[oa])?|l[oa])?|pay|eliminar|elimina|borrar|borra|delete|desinstalar|desinstala|uninstall)\W*(?:\s+\S+){0,3}$|\b(?:checkout|check\s+out|finalizar\s+(?:la\s+)?compra|realizar\s+(?:el\s+)?pedido|place\s+(?:your\s+)?order|confirmar\s+(?:la\s+)?compra|confirm\s+purchase)\b",
        RegexOptions.CultureInvariant)]
    private static partial Regex IrreversibleAct();

    // A destructive verb anywhere in a short label: not saving, discarding, closing without saving, moving to the
    // bin, removing, emptying, clearing, deleting, uninstalling («No guardar», «Don't save», «Descartar cambios»,
    // «Mover a la papelera», «Vaciar papelera de reciclaje», «Empty Recycle Bin», «Quitar de la biblioteca»,
    // «Remove», «Limpiar historial», «Clear all»). Only verb forms count: «Eliminados», «Deleted items» or
    // «Papelera de reciclaje» name a place, not an act. Incidente del 2026-10-15 (msconfig, «Deshabilitar todos»): turning
    // off everything a list holds at once («Deshabilitar todos», «Desactivar todo», «Disable all») asks too. Auditoría del
    // núcleo 2026-10-23: ending a program without letting it save («Finalizar tarea», «End task», «Forzar cierre», «Force
    // quit») loses what it held, as system.process.terminate.named (work_loss) does. Decisión del dueño 2026-10-25 («que
    // Baxy no te moleste todo el tiempo… sino para cosas que realmente son peligrosas»): quitar, remove, limpiar, clear,
    // vaciar, empty, descartar or discard whose harmless object ends the label (the mute, a filter, a search, a format,
    // a notification, a selection: «Quitar silencio», «Clear filters», «Limpiar búsqueda», «Descartar notificación»)
    // destroy nothing and do not ask. Anything after the object may name what it is taken from, so «Quitar búsqueda del
    // historial», «Remove selection from library» and «Clear search history» ask, as «Vaciar papelera» does.
    [GeneratedRegex(
        @"\b(?:finalizar\s+(?:la\s+)?tarea|finaliza\s+(?:la\s+)?tarea|end\s+task|forzar\s+(?:el\s+)?cierre|fuerza\s+(?:el\s+)?cierre|force\s+(?:quit|close)|deshabilitar\s+tod[oa]s?|deshabilita\s+tod[oa]s?|desactivar\s+tod[oa]s?|desactiva\s+tod[oa]s?|disable\s+all|turn\s+off\s+all|no\s+guardar|no\s+guardes|don'?t\s+save|do\s+not\s+save|cerrar\s+sin\s+guardar|close\s+without\s+saving|mover\s+a\s+(?:la\s+)?papelera|move\s+to\s+(?:the\s+)?(?:trash|bin|recycle\s+bin)|(?:quitar|quita|remove|vaciar|vacia|empty|limpiar|limpia|clear|descartar|descarta|discard)\b(?!(?:\s+(?:el|la|los|las|tu|su|sus|tus|the|all|todo|todos|todas|this|these|esta|este|estas|estos))*\s+(?:silencio|mute|filtros?|filters?|busqueda|search|formato|format|notificacion(?:es)?|notifications?|seleccion|selection)\s*$)|eliminar|elimina|delete|borrar|borra|desinstalar|desinstala|uninstall)\b",
        RegexOptions.CultureInvariant)]
    private static partial Regex DestructiveVerb();
}
