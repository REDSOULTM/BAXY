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
/// o interrumpe (work_loss, session_disruption, monetary) sigue preguntando. Las
/// etiquetas de riesgo del catálogo no cambian: los sellos históricos las citan.
///
/// Motor de computer use (CONTRATO_VISTA_ACCION.md §2.1, D15): un paso del bucle
/// lleva el riesgo de su primitiva evaluado con los argumentos exactos delante.
/// Un clic cuya etiqueta nombra un canal de voz o una llamada (alguien te oye),
/// o un botón de enviar, publicar, responder, comentar, compartir o unirse, y un
/// Enter declarado sobre un compositor de mensajes, llegan a una persona; un clic
/// que compra, paga, elimina o desinstala no se deshace. Ambos piden confirmación
/// en modo normal, ligada a esa misma invocación. Igual una invocación cuyo argumento cierra de una vez todo lo
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
        string? operation = null) =>
        Evaluate(risk, mode, operation, arguments: null);

    public static PolicyDecision Evaluate(
        OperationRisk risk,
        ConfirmationMode mode,
        string? operation,
        JsonElement? arguments)
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
                || LosesTheSession(operation, invocation)))
        {
            return PolicyDecision.RequireConfirmation;
        }

        return risk switch
        {
            OperationRisk.ReadOnly => PolicyDecision.Allow,
            OperationRisk.Reversible => PolicyDecision.Allow,
            // privacy_sensitive e installation: leer, copiar, capturar, escribir,
            // radios, ajustes e instalar no destruyen nada (D3).
            OperationRisk.Sensitive => PolicyDecision.Allow,
            OperationRisk.External => operation is not null && ExternalRequiringConfirmation.Contains(operation)
                ? PolicyDecision.RequireConfirmation
                : PolicyDecision.Allow,
            OperationRisk.Irreversible => PolicyDecision.RequireConfirmation,
            _ => PolicyDecision.Deny,
        };
    }

    /// <summary>
    /// Whether this exact invocation of a computer-use primitive reaches another
    /// person: joining a voice channel or a call, pressing «enviar/send»,
    /// «publicar/post», «responder/reply», «comentar/comment»,
    /// «compartir/share» or «unirse/join», or Enter over a message composer
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
                return arguments.TryGetProperty("label", out JsonElement label)
                    && label.ValueKind == JsonValueKind.String
                    && LabelReachesAPerson(label.GetString());
            case "input.key.press":
                // Enter, and space on a focused send or reply control, hand what was written to someone when the
                // step declares it lands on a message composer (the mind labels it from the focused control).
                return KeyOf(arguments) is "enter" or "space"
                    && TargetOf(arguments) is "message_composer";
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
        if (string.Equals(operation, "input.key.press", StringComparison.Ordinal))
        {
            return KeyOf(arguments) is "delete" && TargetOf(arguments) is not "text_field";
        }

        return string.Equals(operation, "input.visible.click", StringComparison.Ordinal)
            && arguments.TryGetProperty("label", out JsonElement label)
            && label.ValueKind == JsonValueKind.String
            && LabelCannotBeUndone(label.GetString());
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
            || (folded.Split(' ', StringSplitOptions.RemoveEmptyEntries).Length <= 6 && DestructiveVerb().IsMatch(folded));
    }

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

    internal static bool LabelReachesAPerson(string? label)
    {
        if (string.IsNullOrWhiteSpace(label))
        {
            return false;
        }

        string folded = Fold(label);
        return VoiceOrCall().IsMatch(folded) || SendAct().IsMatch(folded) || PublicAct().IsMatch(folded);
    }

    /// <summary>A click whose label joins a voice channel, a call or a meeting: others hear or see the person from then on.</summary>
    public static bool LabelJoins(string? label)
    {
        if (string.IsNullOrWhiteSpace(label))
        {
            return false;
        }

        string folded = Fold(label);
        return VoiceOrCall().IsMatch(folded) || JoinVerb().IsMatch(folded);
    }

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
        return ShortcutHint().Replace(folded, string.Empty).Trim();
    }

    [GeneratedRegex(
        @"\s*[(\[](?:ctrl|control|ctl|alt|shift|mayus|mayusculas|supr|del|enter|intro|cmd|win)\b[^)\]]*[)\]]$",
        RegexOptions.CultureInvariant)]
    private static partial Regex ShortcutHint();

    // «canal de voz», «voice channel», «llamar», «llamada», «call», «unirse a la
    // llamada», «join call», «join voice», «videollamada», «video call».
    [GeneratedRegex(
        @"\b(?:canal\s+de\s+voz|voice\s+channel|voice\s+call|video\s*llamada|video\s+call|llamar|llamada|join\s+(?:the\s+)?(?:call|voice)|unirse\s+a\s+(?:la\s+)?(?:llamada|voz)|start\s+(?:a\s+)?call|iniciar\s+(?:una\s+)?llamada)\b|\bcall\b",
        RegexOptions.CultureInvariant)]
    private static partial Regex VoiceOrCall();

    // The control that hands something to someone, named by its verb as the first word whatever follows: «Enviar»,
    // «Send», «Enviar a Ron92», «Send Friend Request», «Reenviar», «Forward», «Invitar», «Invite», «Responder»,
    // «Reply all». A noun that only shares the stem («Enviados», «Invitaciones», «Forwarding») does not.
    [GeneratedRegex(
        @"^(?:enviar|envia|enviale|mandar|manda|send|reenviar|reenvia|forward|invitar|invita|invite|responder|responde|reply)\b",
        RegexOptions.CultureInvariant)]
    private static partial Regex SendAct();

    // The control that puts the person's words or presence in front of others,
    // named by its verb as the first word of the label and at most three more
    // («Publicar», «Post», «Responder a todos», «Reply», «Comentar», «Comment»,
    // «Compartir», «Share», «Unirse», «Join», «Join meeting»). A label that only
    // mentions the noun («Comentarios (12)», «Shared with me») does not.
    [GeneratedRegex(
        @"^(?:publicar|publica|post|tweet|twittear|responder|responde|reply|comentar|comenta|comment|compartir|comparte|share|unirse|unirme|unete|join)(?:\s+\S+){0,3}$",
        RegexOptions.CultureInvariant)]
    private static partial Regex PublicAct();

    [GeneratedRegex(@"^(?:unirse|unirme|unete|join)\b", RegexOptions.CultureInvariant)]
    private static partial Regex JoinVerb();

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
