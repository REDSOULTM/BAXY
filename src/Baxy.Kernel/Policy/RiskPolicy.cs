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
                return arguments.TryGetProperty("key", out JsonElement key)
                    && key.ValueKind == JsonValueKind.String
                    && key.GetString() is "enter"
                    && arguments.TryGetProperty("target", out JsonElement target)
                    && target.ValueKind == JsonValueKind.String
                    && target.GetString() is "message_composer";
            default:
                return false;
        }
    }

    /// <summary>
    /// Whether this exact click commits what cannot be taken back: buying or
    /// paying (checkout, place order) and deleting or uninstalling. Read from
    /// the label the step names, bilingual, never naming an application.
    /// </summary>
    public static bool CannotBeUndone(string? operation, JsonElement arguments) =>
        string.Equals(operation, "input.visible.click", StringComparison.Ordinal)
        && arguments.ValueKind == JsonValueKind.Object
        && arguments.TryGetProperty("label", out JsonElement label)
        && label.ValueKind == JsonValueKind.String
        && !string.IsNullOrWhiteSpace(label.GetString())
        && IrreversibleAct().IsMatch(Fold(label.GetString()!));

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
        return VoiceOrCall().IsMatch(folded) || SendButton().IsMatch(folded) || PublicAct().IsMatch(folded);
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

    private static string Fold(string value)
    {
        string form = value.Normalize(System.Text.NormalizationForm.FormD).ToLowerInvariant();
        var builder = new System.Text.StringBuilder(form.Length);
        foreach (char character in form)
        {
            if (System.Globalization.CharUnicodeInfo.GetUnicodeCategory(character)
                != System.Globalization.UnicodeCategory.NonSpacingMark)
            {
                builder.Append(character);
            }
        }

        return string.Join(' ', builder.ToString().Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
    }

    // «canal de voz», «voice channel», «llamar», «llamada», «call», «unirse a la
    // llamada», «join call», «join voice», «videollamada», «video call».
    [GeneratedRegex(
        @"\b(?:canal\s+de\s+voz|voice\s+channel|voice\s+call|video\s*llamada|video\s+call|llamar|llamada|join\s+(?:the\s+)?(?:call|voice)|unirse\s+a\s+(?:la\s+)?(?:llamada|voz)|start\s+(?:a\s+)?call|iniciar\s+(?:una\s+)?llamada)\b|\bcall\b",
        RegexOptions.CultureInvariant)]
    private static partial Regex VoiceOrCall();

    // The control that hands a written message to someone: «Enviar», «Send»,
    // «Enviar mensaje», «Send message», alone or as the first words.
    [GeneratedRegex(
        @"^(?:enviar|send)(?:\s+(?:mensaje|message|ahora|now))?$",
        RegexOptions.CultureInvariant)]
    private static partial Regex SendButton();

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
}
