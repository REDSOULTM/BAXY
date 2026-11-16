using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// AUT2 (encargo: «que la bajada de los ficheros la haga BAXY abierta, diciendo y mostrando el avance con verdad (y
/// "faltan unos N minutos" sólo si es medido), y que se cierre sólo para el cambio de carpeta»). What the installer's
/// --fetch writes as it downloads (update-progress.json in the profile's updates folder, src/Baxy.Installer/FetchProgress.cs)
/// becomes at most three lines of BAXY's, each when it is true: how much it downloads, half of it with the minutes left
/// when the pace was measured long enough to say them, and that everything came and it closes for some seconds. Nothing
/// is said of a download too short to be worth a line, nor of a failure: the engine's receipt says that, and the model
/// tells it. Its lines are BAXY's own, as «Me actualicé a la X» (LastUpdate), shown in the conversation and said aloud.
/// </summary>
internal sealed class UpdateProgress(bool english, TimeProvider? clock = null)
{
    /// <summary>The pace is measured over this long at least before minutes are said.</summary>
    internal static readonly TimeSpan Measured = TimeSpan.FromSeconds(5);

    /// <summary>A download shorter than this is not announced: «Me actualicé» says it after.</summary>
    internal const long WorthSaying = 20L << 20;

    private readonly TimeProvider clock = clock ?? TimeProvider.System;
    private (long Done, DateTimeOffset At)? first;
    private int said;

    /// <summary>The line to say now for this reading of the file, or null.</summary>
    internal string? Next(JsonObject? progress)
    {
        if (progress is null || (string?)progress["version"] is not { } version)
        {
            return null;
        }

        string? phase = (string?)progress["phase"];
        long done = Number(progress["done"]);
        long total = Number(progress["total"]);
        DateTimeOffset now = clock.GetUtcNow();
        if (phase == "downloading" && total > 0)
        {
            first ??= (done, now);
            if (said == 0 && total >= WorthSaying)
            {
                said = 1;
                return UiLanguage.Say(english, $"Bajo lo que cambió de la {version}: {Mb(total)} MB.",
                    $"I’m downloading what changed in {version}: {Mb(total)} MB.");
            }

            if (said == 1 && done * 2 >= total)
            {
                said = 2;
                string half = UiLanguage.Say(english, $"Voy en la mitad: {Mb(done)} de {Mb(total)} MB.",
                    $"I’m halfway: {Mb(done)} of {Mb(total)} MB.");
                return Minutes(done, total, now) is { } minutes
                    ? half + UiLanguage.Say(english, $" Faltan unos {minutes} minutos.", $" About {minutes} minutes left.")
                    : half;
            }

            return null;
        }

        if (phase == "fetched" && said is > 0 and < 3)
        {
            said = 3;
            return UiLanguage.Say(english, "Ya bajé todo. Me cierro unos segundos para cambiarme y me vuelvo a abrir.",
                "Everything is downloaded. I’ll close for a few seconds to switch and open again.");
        }

        return null;
    }

    /// <summary>
    /// MEN3 (VIVO24B, 15-11-2026: to «Baxi, actualízate» BAXY closed for the update with the turn unanswered, written or
    /// said, until the new version said «Me actualicé a la 1.5.4»): the line BAXY says as it closes for an install whose
    /// receipt says its installer started, with the version it goes to; null for any other receipt.
    /// </summary>
    internal static string? Leaving(JsonObject? receipt, bool english) =>
        receipt is not null && UpdatePanel.StartedInstaller(receipt) && (string?)receipt["latest"] is { Length: > 0 } version
            ? UiLanguage.Say(english, $"Voy a actualizarme a la {version}; me cierro y vuelvo en un momento.",
                $"I’m going to update to {version}; I’ll close and be back in a moment.")
            : null;

    /// <summary>Reads the file as it is now; null when it is not there or not whole yet.</summary>
    internal static JsonObject? Read(string path)
    {
        try
        {
            return File.Exists(path) ? JsonNode.Parse(File.ReadAllText(path)) as JsonObject : null;
        }
        catch (Exception unread) when (unread is IOException or UnauthorizedAccessException or JsonException)
        {
            return null;
        }
    }

    // Minutes left at the pace measured since the first reading, when measured long enough and at least one is left.
    private int? Minutes(long done, long total, DateTimeOffset now)
    {
        if (first is not { } start || now - start.At < Measured || done <= start.Done)
        {
            return null;
        }

        double perSecond = (done - start.Done) / (now - start.At).TotalSeconds;
        double left = (total - done) / perSecond;
        return left >= 60 ? (int)Math.Ceiling(left / 60) : null;
    }

    private static long Number(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out long number) ? number : 0;

    private string Mb(long bytes) =>
        (bytes / 1_000_000d).ToString("N0", english ? CultureInfo.InvariantCulture : CultureInfo.GetCultureInfo("es-ES"));
}
