using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// All the memory BAXY uses, piece by piece (owner, 2026-11-08: Settings › Modelo showed only the model's): its own
/// process and every process under it, grouped by what each is. Each model server is a piece of its own, the one holding
/// the most video memory first. A reading that could not be taken is null, never 0.
/// </summary>
internal static class OwnMemory
{
    private const double Gibibyte = 1L << 30;

    private static readonly string[] Order = ["app", "view", "core", "mind", "model", "model_aux", "ollama", "other"];

    /// <summary>What a process under BAXY is, by its executable's name; the process of BAXY itself is the App.</summary>
    internal static string PieceOf(string processName, bool isSelf) => isSelf ? "app" : processName.ToLowerInvariant() switch
    {
        "msedgewebview2" => "view",
        "baxy-core" => "core",
        "python" or "pythonw" => "mind",
        "llama-server" => "model",
        "ollama" or "ollama_llama_server" or "ollama app" => "ollama",
        _ => "other",
    };

    /// <param name="self">BAXY's own process.</param>
    /// <param name="processes">BAXY's process and every process under it.</param>
    /// <param name="ram">The working set of a group of processes, in bytes, or null.</param>
    /// <param name="vram">The dedicated video memory of a group of processes, in bytes, or null.</param>
    internal static JsonObject Read(
        int self,
        IReadOnlyCollection<(int Id, string Name)> processes,
        Func<IReadOnlyCollection<int>, long?> ram,
        Func<IReadOnlyCollection<int>, long?> vram)
    {
        ArgumentNullException.ThrowIfNull(processes);
        ArgumentNullException.ThrowIfNull(ram);
        ArgumentNullException.ThrowIfNull(vram);

        var groups = new List<(string Piece, string? Name, int[] Ids, long? Ram, long? Vram)>();
        foreach (IGrouping<(string Piece, string? Name), int> group in processes
            .Where(static process => PieceOf(process.Name, false) != "model")
            .GroupBy(process =>
            {
                string piece = PieceOf(process.Name, process.Id == self);
                return (piece, piece == "other" ? process.Name : null);
            }, static process => process.Id))
        {
            int[] ids = [.. group];
            groups.Add((group.Key.Piece, group.Key.Name, ids, ram(ids), vram(ids)));
        }

        // Each model server on its own, the one holding the most video memory being the model.
        bool first = true;
        foreach ((int id, long? r, long? v) in processes
            .Where(static process => PieceOf(process.Name, false) == "model")
            .Select(process => (process.Id, ram([process.Id]), vram([process.Id])))
            .OrderByDescending(static server => server.Item3 ?? -1))
        {
            groups.Add((first ? "model" : "model_aux", null, [id], r, v));
            first = false;
        }

        var parts = new JsonArray();
        foreach ((string piece, string? name, _, long? r, long? v) in groups
            .OrderBy(static group => Array.IndexOf(Order, group.Piece))
            .ThenBy(static group => group.Name, StringComparer.OrdinalIgnoreCase))
        {
            parts.Add(new JsonObject { ["piece"] = piece, ["name"] = name, ["ramGb"] = Gb(r), ["vramGb"] = Gb(v) });
        }

        return new JsonObject
        {
            ["ramGb"] = Gb(Sum(groups.Select(static group => group.Ram))),
            ["vramGb"] = Gb(Sum(groups.Select(static group => group.Vram))),
            ["parts"] = parts,
        };
    }

    private static long? Sum(IEnumerable<long?> values)
    {
        long? total = null;
        foreach (long? value in values)
        {
            if (value is { } known)
            {
                total = (total ?? 0) + known;
            }
        }

        return total;
    }

    private static double? Gb(long? bytes) => bytes is { } known ? Math.Round(known / Gibibyte, 3) : null;
}
