using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;

namespace Baxy.App;

/// <summary>
/// How the view presents a call the model made (design v4: the step chips, the face's families, the Sí/No card and
/// «Qué puedo hacer»). The words are presentation data (Assets/operation-labels.v1.json, one per catalog operation);
/// the status is the call's own outcome, never improved: <c>ok</c> only for a call completed and verified by its
/// provider, <c>maybe</c> for one that may have run, <c>fail</c> for a failure and <c>skip</c> for one that did not run.
/// What the provider observed is shown as its facts, as they came.
/// </summary>
internal static class FieldStepProjection
{
    private const int MaximumTargetCharacters = 48;
    private const int MaximumFactCharacters = 72;

    private static readonly Lazy<(JsonObject Groups, JsonObject Operations)> Labels = new(() =>
    {
        using Stream stream = typeof(FieldStepProjection).Assembly.GetManifestResourceStream("Baxy.App.OperationLabels.json")
            ?? throw new InvalidOperationException("The operation labels are not embedded.");
        JsonObject root = JsonNode.Parse(stream) as JsonObject
            ?? throw new InvalidDataException("The operation labels are not an object.");
        var groups = (JsonObject)root["groups"]!;
        var operations = (JsonObject)root["operations"]!;
        // One entry per catalog operation, no more: a missing title would show a raw name, an extra one is dead data.
        string[] catalog = [.. ProductCatalog.ToolDescriptors.Select(static d => d.Name)];
        string[] missing = [.. catalog.Where(name => !operations.ContainsKey(name))];
        string[] extra = [.. operations.Select(static p => p.Key).Where(name => !catalog.Contains(name, StringComparer.Ordinal))];
        if (missing.Length > 0 || extra.Length > 0)
        {
            throw new InvalidDataException(
                $"operation-labels.v1.json does not match the catalog (missing: {string.Join(", ", missing)}; extra: {string.Join(", ", extra)}).");
        }

        return (groups, operations);
    });

    // Arguments that name what a call is about, in the order they are read for the chip's and the card's target.
    private static readonly string[] TargetKeys =
    [
        "appId", "title", "name", "application", "query", "url", "location", "place", "host", "command", "label",
        "key", "setting", "folder", "packageId", "to", "subject", "text",
    ];

    // Facts of a result that only describe the reply itself, never what was observed.
    private static readonly HashSet<string> PlumbingFacts = new(StringComparer.Ordinal)
    {
        "status", "verified", "version", "authority", "next", "effectStarted", "error", "operation", "argumentsGiven",
        "arguments", "argumentProblems", "detail", "waiting", "effectUncertain", "replayed",
    };

    // The codes BAXY itself writes when a call did not reach its provider, said in one line.
    private static readonly Dictionary<string, string> Reasons = new(StringComparer.Ordinal)
    {
        ["declined_by_person"] = "No se ejecutó: dijiste que no",
        ["confirmation_expired"] = "No se ejecutó: la confirmación venció",
        ["engine_unavailable"] = "No se ejecutó: el motor local no estaba listo",
        ["engine_no_answer"] = "El motor no respondió a tiempo: puede haber corrido",
        ["invalid_arguments"] = "No se ejecutó: los datos de la llamada no eran válidos",
        ["unknown_operation"] = "No se ejecutó: esa acción no existe",
        ["web_disabled_by_owner"] = "No se ejecutó: la búsqueda web está apagada en Ajustes",
        ["weather_disabled_by_owner"] = "No se ejecutó: el clima está apagado en Ajustes",
        ["screen_disabled_by_owner"] = "No se ejecutó: mirar la pantalla está apagado en Ajustes",
        ["outbox_unavailable"] = "No se ejecutó: BAXY no estaba listo",
        ["memory_protection_unavailable"] = "No se ejecutó: la memoria privada no estaba lista",
        ["memory_value_needs_sensitive_channel"] = "No se guardó: parece un dato secreto",
    };

    internal static string Title(string operation) =>
        (string?)Labels.Value.Operations[operation]?["t"] ?? operation;

    internal static string Family(string operation) =>
        (string?)Labels.Value.Operations[operation]?["f"] ?? "apps";

    internal static string Group(string operation) =>
        (string?)Labels.Value.Groups[(string?)Labels.Value.Operations[operation]?["g"] ?? string.Empty] ?? "Otras";

    /// <summary>Checks the labels against the catalog now, so a mismatch stops the start instead of a turn.</summary>
    internal static void Validate() => _ = Labels.Value;

    /// <summary>What a call is about, from its arguments (a memory call's are sealed and never reach here).</summary>
    internal static string Target(JsonObject arguments)
    {
        foreach (string key in TargetKeys)
        {
            if (arguments[key] is JsonValue value && value.TryGetValue(out string? text) && !string.IsNullOrWhiteSpace(text))
            {
                return Clip(text.Trim(), MaximumTargetCharacters);
            }
        }

        return string.Empty;
    }

    /// <summary>The chip's label: the operation's title and, when the arguments name it, what it is about.</summary>
    internal static string Label(string operation, JsonObject arguments)
    {
        string target = Target(arguments);
        return target.Length == 0 ? Title(operation) : Title(operation) + " · " + target;
    }

    internal static JsonObject Started(string id, string operation, JsonObject arguments) => new()
    {
        ["id"] = id,
        ["label"] = Label(operation, arguments),
        ["fam"] = Family(operation),
        ["status"] = "run",
    };

    /// <summary>The step as the view shows it, or null for a call that is not a step of its own: a call held for the
    /// person's «sí» (the card shows it) and the person's answer itself.</summary>
    internal static JsonObject? Finished(string id, NativeTurnStep step, string? net)
    {
        JsonObject? facts = Parse(step.Observation);
        string raw = step.Status;
        if (raw == "needs_confirmation" || step.Operation == MindStep.ConfirmationAnswer)
        {
            return null;
        }

        bool uncertain = facts?["effectUncertain"] is JsonValue u && u.TryGetValue(out bool yes) && yes;
        string code = step.ErrorCode ?? (string?)facts?["error"] ?? string.Empty;
        var view = new JsonObject
        {
            ["id"] = id,
            ["label"] = Label(step.Operation, step.Arguments),
            ["fam"] = Family(step.Operation),
        };

        if (raw == OperationStatuses.Completed && step.Verified && !uncertain)
        {
            view["status"] = "ok";
            string observed = Facts(facts);
            view["obs"] = observed.Length == 0 ? "Verificado por el proveedor" : "Verificado · " + observed;
        }
        else if (raw == OperationStatuses.Completed || uncertain || raw == OperationStatuses.Pending || raw == "unknown")
        {
            view["status"] = "maybe";
            view["reason"] = uncertain || raw != OperationStatuses.Completed
                ? Reason(code, "No se pudo confirmar si se hizo")
                : "Terminó, pero no se pudo verificar";
        }
        else if (raw is OperationStatuses.Rejected or "cancelled")
        {
            view["status"] = "skip";
            view["reason"] = Reason(code, "No se ejecutó");
        }
        else
        {
            view["status"] = "fail";
            view["reason"] = Reason(code, "Falló");
        }

        if (net is not null && (string?)view["status"] != "skip")
        {
            view["net"] = net;
        }

        return view;
    }

    /// <summary>The Sí/No card of a call waiting for the person (design: {risk, title, target, expires}).</summary>
    internal static JsonObject Card(string id, string kind, string operation, JsonObject arguments, string risk,
        DateTimeOffset expiresUtc, string? context) => new()
    {
        ["who"] = "card",
        ["id"] = id,
        ["ts"] = DateTimeOffset.Now.ToString("HH:mm", CultureInfo.InvariantCulture),
        ["kind"] = kind,
        ["risk"] = RiskLabel(operation, risk, arguments),
        ["title"] = Title(operation),
        ["target"] = Target(arguments),
        ["context"] = context,
        ["expires"] = expiresUtc.ToUnixTimeMilliseconds(),
        ["status"] = "pending",
    };

    /// <summary>What leaves the PC with a call that reaches the internet (NativeTurnLoop.ReachesTheNetwork).</summary>
    internal static string NetWhat(string operation, JsonObject arguments)
    {
        string Arg(string key) => arguments[key] is JsonValue v && v.TryGetValue(out string? s) && !string.IsNullOrWhiteSpace(s)
            ? Clip(s.Trim(), MaximumTargetCharacters) : string.Empty;
        string Host(string key) => Uri.TryCreate(Arg(key), UriKind.Absolute, out Uri? uri) ? uri.Host : Arg(key);
        return operation switch
        {
            "web.search" => "búsqueda «" + Arg("query") + "»",
            "web.fetch" => "página de " + Host("url"),
            "web.download" => "descarga de " + Host("url"),
            "weather.current" => "clima · " + (Arg("location") is { Length: > 0 } place ? place : "este lugar"),
            "network.ping" => "ping a " + Arg("host"),
            "game.entitlement.named" => "tienda de juegos · " + Arg("title"),
            "shell.command.run" => "comando de consola",
            "peripheral.print" => "impresión",
            "system.time" => "hora de " + Arg("place"),
            _ => Title(operation),
        };
    }

    /// <summary>«Qué puedo hacer»: every catalog operation by theme, and whether normal mode always confirms it.</summary>
    internal static JsonObject Catalog()
    {
        var groups = new Dictionary<string, JsonArray>(StringComparer.Ordinal);
        foreach (ProductOperationDescriptor descriptor in ProductCatalog.ToolDescriptors)
        {
            string group = Group(descriptor.Name);
            if (!groups.TryGetValue(group, out JsonArray? items))
            {
                groups[group] = items = [];
            }

            items.Add(new JsonObject
            {
                ["name"] = descriptor.Name,
                ["title"] = Title(descriptor.Name),
                ["confirm"] = ConfirmationOf(descriptor),
            });
        }

        // The design's order of themes, then each theme's actions alphabetically by their title.
        string[] order = [.. Labels.Value.Groups.Select(static p => (string)p.Value!)];
        return new JsonObject
        {
            ["total"] = ProductCatalog.ToolDescriptors.Count,
            ["groups"] = new JsonArray([.. groups
                .OrderBy(g => Array.IndexOf(order, g.Key) is var i && i < 0 ? int.MaxValue : i)
                .Select(static g => (JsonNode)new JsonObject
                {
                    ["name"] = g.Key,
                    ["items"] = new JsonArray([.. g.Value.OrderBy(static i => (string?)i!["title"], StringComparer.CurrentCulture)
                        .Select(static i => i!.DeepClone())]),
                })]),
        };
    }

    // RiskPolicy in normal mode, without arguments: always asks, or asks only with some arguments (a click on «Enviar»,
    // Ctrl+W, a console command that changes something, closing every tab), or never.
    private static string ConfirmationOf(ProductOperationDescriptor descriptor)
    {
        if (RiskPolicy.Evaluate(ProductCatalog.ToPolicyRisk(descriptor.Risk), ConfirmationMode.Normal, descriptor.Name)
            == PolicyDecision.RequireConfirmation)
        {
            return "always";
        }

        return descriptor.Name is "shell.command.run" or "input.visible.click" or "input.key.press" or "browser.control"
            ? "sometimes"
            : "never";
    }

    /// <summary>Whether normal mode would have asked for this exact call (bypass ran it without a card).</summary>
    internal static bool NormalModeAsks(string operation, JsonObject arguments)
    {
        if (!ProductCatalog.TryGet(operation, out ProductOperationDescriptor? descriptor) || descriptor is null)
        {
            return false;
        }

        using JsonDocument document = JsonDocument.Parse(arguments.ToJsonString());
        return RiskPolicy.Evaluate(ProductCatalog.ToPolicyRisk(descriptor.Risk), ConfirmationMode.Normal, operation,
            document.RootElement.Clone()) == PolicyDecision.RequireConfirmation;
    }

    private static string? RiskLabel(string operation, string risk, JsonObject arguments) => risk switch
    {
        OperationRisks.RecoverableDelete => "borra datos",
        OperationRisks.WorkLoss => operation == "system.process.terminate.named" ? "fuerza el cierre" : "puede perder trabajo",
        OperationRisks.ExternalCommunication => "llega a otra persona",
        OperationRisks.Installation => "instala o desinstala",
        OperationRisks.PrivacySensitive => "toca datos privados",
        _ when operation == "shell.command.run" => "cambia el sistema",
        _ when operation is "input.visible.click" or "input.key.press" && Target(arguments).Length > 0 => "sale al mundo o no se deshace",
        _ => null,
    };

    private static string Reason(string code, string fallback) =>
        code.Length == 0 ? fallback
        : Reasons.TryGetValue(code, out string? said) ? said
        : fallback + " · " + code;

    private static string Facts(JsonObject? facts)
    {
        if (facts is null)
        {
            return string.Empty;
        }

        var shown = new List<string>(4);
        foreach ((string key, JsonNode? value) in facts)
        {
            if (shown.Count == 4 || PlumbingFacts.Contains(key) || value is not JsonValue scalar)
            {
                continue;
            }

            string? text = scalar.TryGetValue(out string? s) ? s
                : scalar.TryGetValue(out bool b) ? (b ? "sí" : "no")
                : scalar.TryGetValue(out double d) ? d.ToString("0.##", CultureInfo.InvariantCulture)
                : null;
            if (!string.IsNullOrWhiteSpace(text))
            {
                shown.Add(key + ": " + Clip(text.Trim(), MaximumFactCharacters));
            }
        }

        return string.Join(" · ", shown);
    }

    private static JsonObject? Parse(string observation)
    {
        try
        {
            return JsonNode.Parse(observation) as JsonObject;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static string Clip(string text, int maximum) =>
        text.Length <= maximum ? text : text[..(maximum - 1)].TrimEnd() + "…";
}
