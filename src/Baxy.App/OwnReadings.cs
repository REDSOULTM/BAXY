using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;

namespace Baxy.App;

/// <summary>
/// assistant.status (f6 estado, 2026-10-25): what BAXY's view already shows of BAXY itself, read for the person who asks
/// by voice. Scope confirmation: the mode its bypass switch shows. Scope model: the video memory and RAM its model takes, the same reading as Ajustes › Modelo and the rail's
/// meter (FieldTelemetrySampler, nothing measured anew). Scope internet: the session's «Salidas a internet» (Ajustes ›
/// Privacidad), the steps of this session's conversation that reached the internet, each with what went out and when;
/// they are the person's own (the addresses visited), so they are read from this session only and go nowhere but to
/// BAXY's local model. Scope version (VER3, 13-11-2026): the version this App is, its stamp (UpdatePanel.Installed, the
/// one Ajustes › General shows); the system text said it until then and each new number moved the model's answers. The
/// App answers the call itself (NativeTurnLoop): the engine holds none of these readings.
/// </summary>
internal static class OwnReadings
{
    internal const string Operation = "assistant.status";

    /// <summary>The latest internet exits a receipt lists; its total counts them all.</summary>
    internal const int ExitsShown = 20;

    internal const string ModelUnreadable = "model_resources_unreadable";

    internal const string ConfirmationUnreadable = "confirmation_mode_unreadable";

    /// <summary>Nothing in the App holds the view's readings (no view channel).</summary>
    internal const string Unavailable = "own_readings_unavailable";

    /// <summary>A development copy has no stamp: no version is said in its place.</summary>
    internal const string VersionUnknown = "installed_version_unknown";

    /// <summary>A scope the catalog does not list (the schema is checked before).</summary>
    internal const string UnknownScope = "unknown_scope";

    /// <summary>DIAX15: BAXY's own settings as the view shows them: the model it thinks with (Ajustes › Modelo), its tool
    /// profile (Herramientas), whether its language is English (General) and whether its voice is muted (Voz).</summary>
    internal sealed record Settings(string? Model, string? Profile, bool English, bool VoiceMuted);

    /// <summary>The model's video memory and RAM in GB, each left out when the PC did not give it (the view's «—»);
    /// neither readable is a failure, never a zero. DIAX15: with <paramref name="settings"/>, BAXY's own settings too (the
    /// model by name, the tool profile, the language and the voice), and then memory that could not be read is said
    /// (memory «unreadable») beside them instead of failing the reading.</summary>
    internal static OperationOutcome Model(FieldMetricSnapshot metrics, Settings? settings = null)
    {
        ArgumentNullException.ThrowIfNull(metrics);
        double? video = Gigabytes(metrics.ModelVramGb);
        double? memory = Gigabytes(metrics.ModelRamGb);
        if (video is null && memory is null && settings is null)
        {
            return OperationOutcome.Failure(ModelUnreadable);
        }

        var receipt = new JsonObject { ["version"] = 1, ["scope"] = "model" };
        if (settings is not null)
        {
            if (!string.IsNullOrWhiteSpace(settings.Model))
            {
                receipt["model"] = settings.Model.Trim();
            }

            if (!string.IsNullOrWhiteSpace(settings.Profile))
            {
                receipt["toolProfile"] = settings.Profile.Trim();
            }

            receipt["language"] = settings.English ? "English" : "español";
            receipt["voice"] = settings.VoiceMuted ? "muted" : "on";
        }

        if (video is not null)
        {
            receipt["videoMemory"] = new JsonObject { ["value"] = video, ["unit"] = "GB" };
        }

        if (memory is not null)
        {
            receipt["ram"] = new JsonObject { ["value"] = memory, ["unit"] = "GB" };
        }

        if (video is null && memory is null)
        {
            receipt["memory"] = "unreadable";
        }

        return Success(receipt);
    }

    /// <summary>The confirmation mode the engine rereads at each call (ConfirmationModeStore), the one BAXY's own bypass
    /// switch shows: normal asks the person's yes before a risky call, bypass runs it without asking. A file that could not
    /// be read (null) is a failure, never «normal».</summary>
    internal static OperationOutcome Confirmation(ConfirmationMode? mode) =>
        mode is null ? OperationOutcome.Failure(ConfirmationUnreadable) : Success(new JsonObject
        {
            ["version"] = 1,
            ["scope"] = "confirmation",
            ["mode"] = mode == ConfirmationMode.Bypass ? "bypass" : "normal",
            ["asksBeforeRiskyCalls"] = mode != ConfirmationMode.Bypass,
        });

    /// <summary>This session's internet exits as the view's log lists them (store.ts, netOf): every step of BAXY's
    /// replies that went out, with what went out and the reply's time; the latest <see cref="ExitsShown"/>, oldest
    /// first, and how many there were.</summary>
    internal static OperationOutcome Internet(IReadOnlyList<JsonObject> items)
    {
        ArgumentNullException.ThrowIfNull(items);
        var exits = new List<JsonObject>();
        foreach (JsonObject item in items)
        {
            if ((string?)item["who"] != "baxy" || item["steps"] is not JsonArray steps)
            {
                continue;
            }

            foreach (JsonNode? step in steps)
            {
                // An English view's step keeps the Spanish words beside its own (FieldProductChannel.OnStepCompleted).
                // ING5B (owner, 2026-11-13: in English, not a word of Spanish in what the model reads): the log is read
                // in the language in use; a step from before the change has only the words of then.
                if ((UiLanguage.IsEnglish ? (string?)step?["net"] : (string?)step?["netEs"] ?? (string?)step?["net"])
                    is { Length: > 0 } what)
                {
                    exits.Add(new JsonObject { ["destination"] = what, ["at"] = (string?)item["ts"] });
                }
            }
        }

        var receipt = new JsonObject
        {
            ["version"] = 1,
            ["scope"] = "internet",
            ["total"] = exits.Count,
            ["exits"] = new JsonArray([.. exits.Skip(Math.Max(0, exits.Count - ExitsShown))]),
        };
        if (exits.Count > ExitsShown)
        {
            receipt["shown"] = "latest " + ExitsShown.ToString(System.Globalization.CultureInfo.InvariantCulture);
        }

        return Success(receipt);
    }

    /// <summary>The version installed, as the App's stamp says it with no build commit (UpdatePanel.Version); none (a
    /// development copy) is a failure, never a number made up.</summary>
    internal static OperationOutcome Version(string? installed) =>
        string.IsNullOrWhiteSpace(installed) ? OperationOutcome.Failure(VersionUnknown) : Success(new JsonObject
        {
            ["version"] = 1,
            ["scope"] = "version",
            ["installed"] = installed.Trim(),
        });

    private static double? Gigabytes(double? value) =>
        value is { } measured && double.IsFinite(measured) && measured >= 0 ? Math.Round(measured, 2) : null;

    private static OperationOutcome Success(JsonObject receipt)
    {
        using JsonDocument document = JsonDocument.Parse(receipt.ToJsonString());
        return OperationOutcome.Success(document.RootElement.Clone());
    }
}
