using System.Diagnostics;
using System.Globalization;
using System.Text.Json.Nodes;

namespace Baxy.Installer;

/// <summary>
/// AUT2 (encargo: «que la bajada de los ficheros la haga BAXY abierta, diciendo y mostrando el avance con verdad»). How far
/// <c>--update --fetch</c> is, written beside this installer (the profile's updates folder, where BAXY started it) as
/// update-progress.json, for the BAXY that waits for it with its window open: its engine reads the end, its App says and
/// shows the bytes. Only what happened is written: the bytes that are here of what this machine needs (<c>done</c> of
/// <c>total</c>, an earlier try's included), those this run took from the network (<c>downloaded</c>), and how it ended.
/// A file written whole and then moved over the last one, so a reader never sees half of it.
/// </summary>
internal sealed class FetchProgress(string folder, string version, Func<DateTimeOffset>? now = null)
{
    internal const string FileName = "update-progress.json";
    internal const string Downloading = "downloading";
    internal const string Fetched = "fetched";
    internal const string Failed = "failed";

    private static readonly TimeSpan Apart = TimeSpan.FromMilliseconds(500);
    private readonly Func<DateTimeOffset> now = now ?? (() => DateTimeOffset.Now);
    private readonly Stopwatch since = new();
    private readonly object gate = new();

    internal void Report(InstallPhase phase, long done, long total)
    {
        if (phase != InstallPhase.Downloading)
        {
            return;
        }

        lock (gate)
        {
            if (since.IsRunning && since.Elapsed < Apart && done < total)
            {
                return;
            }

            since.Restart();
            Write(Downloading, done, total, null, null);
        }
    }

    internal void End(long downloaded, long total) => Write(Fetched, total, total, downloaded, null);

    internal void Fail(string reason, long downloaded) => Write(Failed, null, null, downloaded, reason);

    private void Write(string phase, long? done, long? total, long? downloaded, string? reason)
    {
        JsonObject written = new()
        {
            ["version"] = version,
            ["phase"] = phase,
            ["done"] = done,
            ["total"] = total,
            ["downloaded"] = downloaded,
            ["reason"] = reason,
            ["at"] = now().ToString("o", CultureInfo.InvariantCulture),
        };
        string path = Path.Combine(folder, FileName);
        string partial = path + ".new";
        try
        {
            File.WriteAllText(partial, written.ToJsonString());
            File.Move(partial, path, overwrite: true);
        }
        catch (Exception unwritten) when (unwritten is IOException or UnauthorizedAccessException)
        {
            // A reader holding it open (BAXY reading it now): the next report writes it again.
            Program.Log("the progress was not written: " + unwritten.Message);
        }
    }
}
