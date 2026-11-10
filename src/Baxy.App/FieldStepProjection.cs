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
/// the status is the call's own outcome, never improved: <c>ok</c> only for a call completed whose effect was read back,
/// <c>same</c> for one that found the asked state already there, <c>sent</c> for one delivered without reading its
/// effect, <c>read</c> for a read whose output is its result, <c>maybe</c> for one that may have run or whose completion
/// could not be verified, <c>fail</c> for a failure and <c>skip</c> for one that did not run.
/// What the provider observed is shown as its facts, as they came.
/// </summary>
internal static class FieldStepProjection
{
    private const int MaximumTargetCharacters = 48;
    private const int MaximumFactCharacters = 72;

    private static readonly Lazy<(JsonObject Groups, JsonObject GroupsEn, JsonObject Operations)> Labels = new(() =>
    {
        using Stream stream = typeof(FieldStepProjection).Assembly.GetManifestResourceStream("Baxy.App.OperationLabels.json")
            ?? throw new InvalidOperationException("The operation labels are not embedded.");
        JsonObject root = JsonNode.Parse(stream) as JsonObject
            ?? throw new InvalidDataException("The operation labels are not an object.");
        var groups = (JsonObject)root["groups"]!;
        var groupsEn = (JsonObject)root["groupsEn"]!;
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

        // Steam (2026-11-04): every title and theme in both languages, so an English view never shows a Spanish one.
        string[] untitled = [.. operations.Where(static p => !Named(p.Value?["t"]) || !Named(p.Value?["en"]))
            .Select(static p => p.Key)];
        string[] themes = [.. groups.Select(static p => p.Key).Order(StringComparer.Ordinal)];
        if (untitled.Length > 0 || !themes.SequenceEqual(groupsEn.Select(static p => p.Key).Order(StringComparer.Ordinal))
            || groupsEn.Any(static p => !Named(p.Value)))
        {
            throw new InvalidDataException(
                $"operation-labels.v1.json lacks a title or theme in a language (untitled: {string.Join(", ", untitled)}).");
        }

        // Perfiles de herramientas: every operation says the first profile that has it, so a new one is never left out
        // of every profile but Completo by omission.
        string[] unleveled = [.. operations.Where(static p => LevelOf(p.Value) is null).Select(static p => p.Key)];
        if (unleveled.Length > 0)
        {
            throw new InvalidDataException(
                $"operation-labels.v1.json lacks a tool profile level 0-{ToolProfile.Highest} (p): {string.Join(", ", unleveled)}.");
        }

        return (groups, groupsEn, operations);
    });

    // Arguments that name what a call is about, in the order they are read for the chip's and the card's target. A
    // title comes before an id (auditoría de la App, 2026-10-23: game.launch's card, held because the person did not
    // name that game, showed its Steam id «252950», not «Rocket League»). P2.4: a file tool's path, as the person said it.
    private static readonly string[] TargetKeys =
    [
        "title", "appId", "name", "path", "application", "query", "url", "location", "place", "host", "command", "label",
        "key", "setting", "folder", "packageId", "to", "subject", "text",
    ];

    // Facts of a result that only describe the reply itself, never what was observed, and the App's notes written for
    // the model (auditoría de la App, 2026-10-23: the chip of a read routed into the folder the person named showed
    // «saidFolder: the person named «proyecto» (C:\Users\…», English meant for the model, with the path).
    private static readonly HashSet<string> PlumbingFacts = new(StringComparer.Ordinal)
    {
        "status", "verified", "version", "authority", "next", "effectStarted", "error", "operation", "argumentsGiven",
        "arguments", "argumentProblems", "detail", "waiting", "effectUncertain", "replayed", "saidFolder",
        // ARR1: how the engine fitted a long result in its message (a search's ten results: «observedLimit: projected»).
        OperationVisibleFacts.VerificationKey, OperationVisibleFacts.ObservedLimitKey,
    };

    // How a completed call was verified (OperationVisibleFacts' table), as the chip's status and its first words.
    private static readonly Dictionary<string, (string Status, string Said, string SaidEn)> Verifications = new(StringComparer.Ordinal)
    {
        [OperationVisibleFacts.VerificationReadback] = ("ok", "Verificado", "Verified"),
        [OperationVisibleFacts.VerificationUnchanged] = ("same", "Ya estaba así", "Already set"),
        [OperationVisibleFacts.VerificationDeliveredOnly] = ("sent", "Enviado, sin comprobar", "Sent, not verified"),
        [OperationVisibleFacts.VerificationOutputOnly] = ("read", "Leído", "Read"),
    };

    // The codes BAXY itself writes when a call did not reach its provider, said in one line.
    private static readonly Dictionary<string, (string Es, string En)> Reasons = new(StringComparer.Ordinal)
    {
        ["declined_by_person"] = ("No se ejecutó: dijiste que no", "Not run: you said no"),
        ["confirmation_expired"] = ("No se ejecutó: la confirmación venció", "Not run: the confirmation expired"),
        ["engine_unavailable"] = ("No se ejecutó: el motor local no estaba listo", "Not run: the local engine was not ready"),
        ["engine_no_answer"] = ("El motor no respondió a tiempo: puede haber corrido", "The engine did not answer in time: it may have run"),
        ["operation_unexpected_failure"] = ("Falló de forma inesperada: puede haber corrido", "Failed unexpectedly: it may have run"),
        ["invalid_arguments"] = ("No se ejecutó: los datos de la llamada no eran válidos", "Not run: the call's data was not valid"),
        ["unknown_operation"] = ("No se ejecutó: esa acción no existe", "Not run: that action does not exist"),
        ["web_disabled_by_owner"] = ("No se ejecutó: la búsqueda web está apagada en Ajustes", "Not run: web search is off in Settings"),
        ["weather_disabled_by_owner"] = ("No se ejecutó: el clima está apagado en Ajustes", "Not run: weather is off in Settings"),
        ["screen_disabled_by_owner"] = ("No se ejecutó: mirar la pantalla está apagado en Ajustes", "Not run: looking at the screen is off in Settings"),
        ["tool_off_in_profile"] = ("No se ejecutó: esa herramienta está apagada en tu perfil", "Not run: that tool is off in your profile"),
        ["outbox_unavailable"] = ("No se ejecutó: BAXY no estaba listo", "Not run: BAXY was not ready"),
        ["memory_protection_unavailable"] = ("No se ejecutó: la memoria privada no estaba lista", "Not run: private memory was not ready"),
        ["memory_value_needs_sensitive_channel"] = ("No se guardó: parece un dato secreto", "Not saved: it looks like a secret"),
        ["query_not_said"] = ("No se ejecutó: la búsqueda no llevaba tus palabras", "Not run: the search didn't use your words"),
        ["channel_not_said"] = ("No se ejecutó: no nombraste ese canal", "Not run: you did not name that channel"),
        ["application_not_said"] = ("No se ejecutó: no nombraste esa aplicación", "Not run: you did not name that app"),
    };

    // VIS3 (VIVO6 fila 4, 10-11-2026: «Actualízate» on the latest version showed «✕ No pude · Falló ·
    // baxy_update_already_latest»): the codes of a call that ended before any effect with nothing to do, because its provider
    // read the asked state already there (same) or read why there was nothing it could do (skip). The model still reads the
    // failure and its code as they came; only the chip says it in plain words. « ({installed})» is the version the call read.
    private static readonly Dictionary<string, (string Status, string Es, string En)> NothingToDo = new(StringComparer.Ordinal)
    {
        ["baxy_update_already_latest"] = ("same", "Ya tienes la última versión ({installed})", "You have the latest version ({installed})"),
        // the PC's volume or an app's (audio.volume.adjust and audio.app.volume.adjust give the same codes)
        ["volume_already_at_minimum"] = ("same", "Ya estaba al mínimo", "It was already at its lowest"),
        ["volume_already_at_maximum"] = ("same", "Ya estaba al máximo", "It was already at its highest"),
        // UIA's ExpandCollapse: a list, a tree's branch, a menu or a split button
        ["visible_control_already_open"] = ("same", "Ya estaba desplegado", "It was already expanded"),
        // at its highest but muted: what the person wanted to hear louder is not heard, so it is not «already like that»
        ["volume_already_at_maximum_muted"] = ("skip", "No se subió: ya estaba al máximo, pero silenciado", "Not raised: it was already at its highest, but muted"),
        // the process's name is what was looked for (GetProcessesByName), not the program the person named
        ["process_not_running"] = ("skip", "No se cerró nada: no había ningún proceso llamado así", "Nothing closed: no process by that name was running"),
    };

    /// <summary>The operation's short title in the interface's language (<see cref="UiLanguage"/>).</summary>
    internal static string Title(string operation) => Title(operation, UiLanguage.IsEnglish);

    internal static string Title(string operation, bool english) =>
        (string?)Labels.Value.Operations[operation]?[english ? "en" : "t"] ?? operation;

    /// <summary>Settings → Tools: the themes a profile still offers as what BAXY can do (mind.py CAN_DO_AREAS): those
    /// that keep at least half of their tools, BAXY's own (level 0) not counted. VIVO1 F8, 2.ª vuelta (09-11): Esencial
    /// told «Memoria» for the conversations alone and «Alarmas, notas y tareas» for the clock alone, and the 4B promised
    /// to remember and to set alarms.</summary>
    internal static IReadOnlySet<string> ShownThemes(IReadOnlySet<string> withheld)
    {
        ArgumentNullException.ThrowIfNull(withheld);
        return ProductCatalog.ToolDescriptors.Select(static d => d.Name)
            .Where(static name => ProfileLevel(name) > 0)
            .GroupBy(static name => Group(name))
            .Where(g => 2 * g.Count(name => !withheld.Contains(name)) >= g.Count() && g.Any(name => !withheld.Contains(name)))
            .Select(static g => g.Key)
            .ToHashSet(StringComparer.Ordinal);
    }

    /// <summary>Settings → Tools: whether a tool off in a profile is shown to the model as a stub (operation-labels
    /// «ficha», true unless it says false). VIVO1 F8, 2.ª vuelta (09-11, foco 16 casos × 3 semillas, juez ciego): with the
    /// memory tools' stubs the 4B claimed to have saved or to remember (13 high falsehoods; 6 without them, as the base).</summary>
    internal static bool HasStub(string operation) =>
        Labels.Value.Operations[operation]?["ficha"] is not JsonValue value || !value.TryGetValue(out bool stub) || stub;

    /// <summary>The operation's English title, whatever the interface's language: a withheld tool's stub for the model
    /// reads it, as the tools' descriptions are in English (MindSidecarClient.CreateCatalogConfigureRequest).</summary>
    internal static string EnglishTitle(string operation) => Title(operation, english: true);

    internal static string Family(string operation) =>
        (string?)Labels.Value.Operations[operation]?["f"] ?? "apps";

    /// <summary>The operation's theme in Spanish: what the model reads of what it can do (catalog.configure), whatever
    /// the interface's language.</summary>
    internal static string Group(string operation) => Group(operation, english: false);

    private static string Group(string operation, bool english) =>
        (string?)(english ? Labels.Value.GroupsEn : Labels.Value.Groups)[(string?)Labels.Value.Operations[operation]?["g"] ?? string.Empty]
        ?? (english ? "Other" : "Otras");

    /// <summary>The first tool profile that has this operation (ToolProfile): 0 always, up to <see cref="ToolProfile.Highest"/>,
    /// only in Completo; an operation of no catalog, the highest.</summary>
    internal static int ProfileLevel(string operation) =>
        LevelOf(Labels.Value.Operations[operation]) ?? ToolProfile.Highest;

    private static int? LevelOf(JsonNode? entry) =>
        entry?["p"] is JsonValue value && value.TryGetValue(out int level) && level >= 0 && level <= ToolProfile.Highest
            ? level : null;

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
    internal static string Label(string operation, JsonObject arguments) => Label(operation, arguments, UiLanguage.IsEnglish);

    internal static string Label(string operation, JsonObject arguments, bool english)
    {
        string target = OwnBrakes.Shown(operation, arguments, english) ?? Target(arguments);
        return target.Length == 0 ? Title(operation, english) : Title(operation, english) + " · " + target;
    }

    internal static JsonObject Started(string id, string operation, JsonObject arguments) => new()
    {
        ["id"] = id,
        ["label"] = Label(operation, arguments),
        ["fam"] = Family(operation),
        ["status"] = "run",
    };

    /// <summary>The step as the view shows it, or null for a call that is not a step of its own: a call held for the
    /// person's «sí» (the card shows it) and the person's answer itself. Its words are all in one language,
    /// <paramref name="english"/> or Spanish, as the caller read it once.</summary>
    internal static JsonObject? Finished(string id, NativeTurnStep step, string? net, bool english)
    {
        JsonObject? facts = Parse(step.Observation);
        string raw = step.Status;
        // A call the kernel challenged (or a heartbeat held) did not run: its card stands for it, never a chip.
        if (raw == "needs_confirmation" || (string?)facts?["status"] == "needs_confirmation"
            || step.Operation == MindStep.ConfirmationAnswer)
        {
            return null;
        }

        bool uncertain = facts?["effectUncertain"] is JsonValue u && u.TryGetValue(out bool yes) && yes;
        string code = step.ErrorCode ?? (string?)facts?["error"] ?? string.Empty;
        var view = new JsonObject
        {
            ["id"] = id,
            ["label"] = Label(step.Operation, step.Arguments, english),
            ["fam"] = Family(step.Operation),
        };

        // A completed call is shown as it was verified (OperationVisibleFacts' typed «verification»): only a read-back
        // effect is «Verificado»; an asked state already in place, an input delivered without reading its effect and a
        // read's output are said as such, and a completion without that fact (none, or none written) is not verified.
        string? verification = facts?[OperationVisibleFacts.VerificationKey] is JsonValue v
            && v.TryGetValue(out string? said) ? said : null;
        if (raw == OperationStatuses.Completed
            && (facts?["replayed"] is not null || facts?["observed"] is JsonObject { } kept && kept["replayed"] is not null))
        {
            // The journal's recorded result of this same call made earlier (OperationResponseProjection.Replay; a
            // memory call's, inside what it observed): it did not run again now, so nothing is said done now.
            view["status"] = "skip";
            view["reason"] = UiLanguage.Say(english, "No se repitió: ya había corrido antes", "Not repeated: it had already run");
        }
        else if (raw == OperationStatuses.Completed && step.Verified && !uncertain
            && Verifications.TryGetValue(verification ?? string.Empty, out (string Status, string Said, string SaidEn) shown))
        {
            view["status"] = shown.Status;
            string observed = Facts(facts, english);
            string first = UiLanguage.Say(english, shown.Said, shown.SaidEn);
            view["obs"] = observed.Length == 0 ? first : first + " · " + observed;
        }
        else if (raw == OperationStatuses.Completed || uncertain || raw == "unknown")
        {
            view["status"] = "maybe";
            view["reason"] = uncertain || raw != OperationStatuses.Completed
                ? Reason(code, english, UiLanguage.Say(english, "No se pudo confirmar si se hizo", "Could not confirm whether it was done"))
                : UiLanguage.Say(english, "Terminó, pero no se pudo verificar", "Finished, but could not be verified");
        }
        else if (raw == OperationStatuses.Pending)
        {
            // A retryable outcome whose effect did not happen (the engine says effectUncertain when it may have): it
            // did not complete and can be tried again, never «may have run».
            view["status"] = "fail";
            view["reason"] = Reason(code, english,
                UiLanguage.Say(english, "No se completó, se puede reintentar", "Not completed, it can be retried"));
        }
        else if (raw is OperationStatuses.Rejected or "cancelled")
        {
            view["status"] = "skip";
            view["reason"] = Reason(code, english, UiLanguage.Say(english, "No se ejecutó", "Not run"));
        }
        else if (NothingToDo.TryGetValue(code, out (string Status, string Es, string En) settled))
        {
            string? installed = (string?)(facts?["observed"] as JsonObject)?["installed"];
            view["status"] = settled.Status;
            view[settled.Status == "same" ? "obs" : "reason"] = UiLanguage.Say(english, settled.Es, settled.En)
                .Replace(" ({installed})", installed is null ? string.Empty : $" ({installed})", StringComparison.Ordinal);
        }
        else
        {
            view["status"] = "fail";
            view["reason"] = Reason(code, english, UiLanguage.Say(english, "Falló", "Failed"));
        }

        if (net is not null && (string?)view["status"] != "skip")
        {
            view["net"] = net;
        }

        // COR1 (VIVO3 A3: the setting changed inside «Qué hice · 3 pasos», folded): a change of one of BAXY's own
        // settings that was read back, or that may have happened (a write that failed past its start), is shown with the
        // steps open (Chat.tsx's HowChecked), not only behind their fold.
        if (step.Operation == OwnBrakes.Operation && (string?)view["status"] is "ok" or "maybe")
        {
            view["pin"] = true;
        }

        return view;
    }

    /// <summary>The Sí/No card of a call waiting for the person (design: {risk, title, target, expires}), and whether
    /// an earlier attempt of it may already have happened (the kernel asks again: <paramref name="effectStarted"/>).
    /// <paramref name="cause"/>: why the person's turn held it (NetworkEgress), said before its risk. Its words, and the
    /// caller's <paramref name="context"/>, are in the one language the caller read (<paramref name="english"/>).</summary>
    internal static JsonObject Card(string id, string kind, string operation, JsonObject arguments, string risk,
        DateTimeOffset expiresUtc, string? context, bool english, bool effectStarted = false, string? cause = null) => new()
    {
        ["who"] = "card",
        ["id"] = id,
        ["ts"] = DateTimeOffset.Now.ToString("HH:mm", CultureInfo.InvariantCulture),
        ["kind"] = kind,
        // Uso real 02-11: a page held for a host nobody gave said «llega a otra persona» too, which a page does not; a
        // held call says why it was held, and only an unheld one its risk.
        ["risk"] = cause is not null ? CauseLabel(cause, english) : RiskLabel(operation, risk, arguments, english),
        ["title"] = Title(operation, english),
        // COR1: a change of one of BAXY's own settings says which one and to what («Búsqueda web: activar»).
        ["target"] = OwnBrakes.Shown(operation, arguments, english) ?? Target(arguments),
        ["context"] = context,
        ["expires"] = expiresUtc.ToUnixTimeMilliseconds(),
        ["effectStarted"] = effectStarted,
        ["status"] = "pending",
    };

    /// <summary>What leaves the PC with a call that reaches the internet (the catalog's OperationEffects.Network), in
    /// English or in Spanish: the Spanish one is also what assistant.status reads to the model (OwnReadings.Internet).</summary>
    internal static string NetWhat(string operation, JsonObject arguments, bool english)
    {
        string Arg(string key) => arguments[key] is JsonValue v && v.TryGetValue(out string? s) && !string.IsNullOrWhiteSpace(s)
            ? Clip(s.Trim(), MaximumTargetCharacters) : string.Empty;
        string Host(string key) => Uri.TryCreate(Arg(key), UriKind.Absolute, out Uri? uri) ? uri.Host : Arg(key);
        if (english)
        {
            return operation switch
            {
                "web.search" => "search «" + Arg("query") + "»",
                "web.fetch" or "browser.navigate" or "browser.navigate.named" => "page on " + Host("url"),
                "web.download" => "download from " + Host("url"),
                "weather.current" => "weather · " + (Arg("location") is { Length: > 0 } place ? place : "this place"),
                "network.ping" => "ping to " + Arg("host"),
                "shell.command.run" => "console command",
                "peripheral.print" => "printing",
                "system.time" => "time in " + Arg("place"),
                _ => Title(operation, english),
            };
        }

        return operation switch
        {
            "web.search" => "búsqueda «" + Arg("query") + "»",
            "web.fetch" or "browser.navigate" or "browser.navigate.named" => "página de " + Host("url"),
            "web.download" => "descarga de " + Host("url"),
            "weather.current" => "clima · " + (Arg("location") is { Length: > 0 } place ? place : "este lugar"),
            "network.ping" => "ping a " + Arg("host"),
            "shell.command.run" => "comando de consola",
            "peripheral.print" => "impresión",
            "system.time" => "hora de " + Arg("place"),
            _ => Title(operation, english),
        };
    }

    /// <summary>«Qué puedo hacer»: every catalog operation by theme, and whether normal mode always confirms it, in the
    /// interface's language.</summary>
    internal static JsonObject Catalog()
    {
        bool english = UiLanguage.IsEnglish;
        var groups = new Dictionary<string, JsonArray>(StringComparer.Ordinal);
        foreach (ProductOperationDescriptor descriptor in ProductCatalog.ToolDescriptors)
        {
            string group = Group(descriptor.Name, english);
            if (!groups.TryGetValue(group, out JsonArray? items))
            {
                groups[group] = items = [];
            }

            items.Add(new JsonObject
            {
                ["name"] = descriptor.Name,
                ["title"] = Title(descriptor.Name, english),
                ["confirm"] = ConfirmationOf(descriptor),
                ["level"] = ProfileLevel(descriptor.Name),
            });
        }

        // The design's order of themes, then each theme's actions alphabetically by their title.
        string[] order = [.. (english ? Labels.Value.GroupsEn : Labels.Value.Groups).Select(static p => (string)p.Value!)];
        StringComparer byTitle = StringComparer.Create(UiLanguage.CultureOf(english), ignoreCase: false);
        return new JsonObject
        {
            ["total"] = ProductCatalog.ToolDescriptors.Count,
            ["groups"] = new JsonArray([.. groups
                .OrderBy(g => Array.IndexOf(order, g.Key) is var i && i < 0 ? int.MaxValue : i)
                .Select(g => (JsonNode)new JsonObject
                {
                    ["name"] = g.Key,
                    ["items"] = new JsonArray([.. g.Value.OrderBy(static i => (string?)i!["title"], byTitle)
                        .Select(static i => i!.DeepClone())]),
                })]),
        };
    }

    // RiskPolicy in normal mode, without arguments: always asks, or asks only with some arguments (a click on «Enviar»,
    // Ctrl+W, a console command that changes something, closing every tab, a click under the pointer (K-1), shutting the
    // PC down, a replacement under a version only a refusal told: ToldVersions), or never.
    private static string ConfirmationOf(ProductOperationDescriptor descriptor)
    {
        if (RiskPolicy.Evaluate(ProductCatalog.ToPolicyRisk(descriptor.Risk), ConfirmationMode.Normal, descriptor.Name)
            == PolicyDecision.RequireConfirmation)
        {
            return "always";
        }

        return descriptor.Name is "shell.command.run" or "input.visible.click" or "input.key.press" or "browser.control"
                or "input.pointer.control" or "system.power"
            || ToldVersions.ExpectsAVersion(descriptor.Name)
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

    private static string? RiskLabel(string operation, string risk, JsonObject arguments, bool english) => risk switch
    {
        OperationRisks.RecoverableDelete => UiLanguage.Say(english, "borra datos", "deletes data"),
        _ when operation == "system.recyclebin.empty" => UiLanguage.Say(english, "borra datos", "deletes data"),
        OperationRisks.WorkLoss => operation == "system.process.terminate.named"
            ? UiLanguage.Say(english, "fuerza el cierre", "forces it to close")
            : UiLanguage.Say(english, "puede perder trabajo", "may lose work"),
        OperationRisks.ExternalCommunication => UiLanguage.Say(english, "llega a otra persona", "reaches another person"),
        OperationRisks.Installation => UiLanguage.Say(english, "instala o desinstala", "installs or uninstalls"),
        OperationRisks.PrivacySensitive => UiLanguage.Say(english, "toca datos privados", "touches private data"),
        _ when operation == "shell.command.run" => UiLanguage.Say(english, "cambia el sistema", "changes the system"),
        _ when operation is "input.visible.click" or "input.key.press" && Target(arguments).Length > 0
            => UiLanguage.Say(english, "sale al mundo o no se deshace", "acts outside the PC or can't be undone"),
        _ => null,
    };

    // Auditoría de la App (2026-10-23): a call the person's turn held (a read of a page, a game) has no risk of its own
    // to show, and its card said nothing of why it asked; the cause NetworkEgress gave the model is said.
    private static string? CauseLabel(string? cause, bool english) => cause switch
    {
        "host_not_from_session" => UiLanguage.Say(english, "va a un sitio que nadie dio", "goes to a site no one mentioned"),
        "game_title_not_said" => UiLanguage.Say(english, "un juego que no nombraste", "a game you did not name"),
        OwnBrakes.Cause => UiLanguage.Say(english, "cambia un ajuste que no pediste", "changes a setting you did not ask for"),
        PendingOperationConfirmation.SystemChangeCause => UiLanguage.Say(english, "cambia un ajuste del sistema", "changes a system setting"),
        _ => null,
    };

    private static string Reason(string code, bool english, string fallback) =>
        code.Length == 0 ? fallback
        : Reasons.TryGetValue(code, out (string Es, string En) said) ? UiLanguage.Say(english, said.Es, said.En)
        : fallback + " · " + code;

    private static string Facts(JsonObject? facts, bool english)
    {
        if (facts is null)
        {
            return string.Empty;
        }

        var shown = new List<string>(4);
        // LIC2 (2026-11-08): the source that answered («answeredBy») is credited first: DuckDuckGo («Please give us
        // attribution where it makes sense»), OpenStreetMap («credit OpenStreetMap») and Wikipedia (CC BY-SA) ask it of
        // whoever shows their results. ARR1 (DEP5, the App on the owner's PC: 0 of 2 searches credited): a provider's
        // result reaches the step inside «observed» (OperationVisibleFacts.FromOutcome), so the credit is read there too.
        if ((AnsweredBy(facts) ?? AnsweredBy(facts["observed"] as JsonObject)) is { } answeredBy)
        {
            shown.Add(UiLanguage.Say(english, "Fuente: ", "Source: ") + Clip(answeredBy, MaximumFactCharacters));
        }
        foreach ((string key, JsonNode? value) in facts)
        {
            if (shown.Count == 4 || PlumbingFacts.Contains(key) || key == "answeredBy" || value is not JsonValue scalar)
            {
                continue;
            }

            string? text = scalar.TryGetValue(out string? s) ? s
                : scalar.TryGetValue(out bool b) ? (b ? UiLanguage.Say(english, "sí", "yes") : "no")
                : scalar.TryGetValue(out double d) ? d.ToString("0.##", CultureInfo.InvariantCulture)
                : null;
            if (!string.IsNullOrWhiteSpace(text))
            {
                shown.Add(key + ": " + Clip(text.Trim(), MaximumFactCharacters));
            }
        }

        return string.Join(" · ", shown);
    }

    private static string? AnsweredBy(JsonObject? facts) =>
        facts?["answeredBy"] is JsonValue source && source.TryGetValue(out string? answeredBy)
            && !string.IsNullOrWhiteSpace(answeredBy) ? answeredBy.Trim() : null;

    private static bool Named(JsonNode? title) =>
        title is JsonValue value && value.TryGetValue(out string? text) && !string.IsNullOrWhiteSpace(text);

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
