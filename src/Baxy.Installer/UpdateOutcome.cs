using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.Installer;

/// <summary>
/// AUT1: how an update that BAXY started ended, written by the installer beside itself (the profile's
/// &lt;data&gt;\updates, where BAXY downloads it: UpdateInstallerFile) so the BAXY that opens after it says it with
/// truth, from this file and not from memory: «me actualicé a la X», or that it could not and why. The App links this
/// file (Baxy.App.csproj).
/// <list type="bullet">
/// <item><see cref="Started"/>: the new BAXY is in place and was opened; the one it replaced is still kept beside it.</item>
/// <item><see cref="Installed"/>: the new BAXY said it started (<see cref="Confirm"/>) and the old one is gone.</item>
/// <item><see cref="Failed"/>: nothing was changed (<see cref="UpdateOutcome.Reason"/> says why).</item>
/// <item><see cref="RolledBack"/>: the new BAXY did not start and the one that was there is back.</item>
/// </list>
/// </summary>
internal sealed record UpdateOutcome(string From, string To, string State, string? Reason, long DownloadedBytes, int Seconds, string At)
{
    internal const string Started = "started";
    internal const string Installed = "installed";
    internal const string Failed = "failed";
    internal const string RolledBack = "rolled_back";

    /// <summary>The new BAXY was opened and never said it started.</summary>
    internal const string NotStarted = "not_started";

    private const string FileName = "last-update.json";
    private const string ConfirmedName = "last-update.started";
    private const string ToldName = "last-update.told";

    /// <summary>The new BAXY is in the folder (it may still be confirming its start).</summary>
    internal bool Updated => State is Started or Installed;

    internal void Write(string folder)
    {
        Directory.CreateDirectory(folder);
        JsonObject json = new()
        {
            ["from"] = From,
            ["to"] = To,
            ["state"] = State,
            ["reason"] = Reason,
            ["downloadedBytes"] = DownloadedBytes,
            ["seconds"] = Seconds,
            ["at"] = At,
        };
        // Whole or not at all: the BAXY that reads it never finds half a file.
        string writing = Path.Combine(folder, FileName + ".new");
        File.WriteAllText(writing, json.ToJsonString());
        File.Move(writing, Path.Combine(folder, FileName), overwrite: true);
    }

    /// <summary>What the last update ended in, or null: none, or a file that is not one.</summary>
    internal static UpdateOutcome? Read(string folder)
    {
        try
        {
            return JsonNode.Parse(File.ReadAllText(Path.Combine(folder, FileName))) is JsonObject json
                && Text(json, "from") is { } from && Text(json, "to") is { } to && Text(json, "state") is { } state
                && Text(json, "at") is { } at
                    ? new UpdateOutcome(
                        from, to, state, Text(json, "reason"), Number(json, "downloadedBytes"), (int)Number(json, "seconds"), at)
                    : null;
        }
        catch (Exception unread) when (unread is IOException or UnauthorizedAccessException or JsonException)
        {
            return null;
        }
    }

    /// <summary>The BAXY of <paramref name="version"/> says it started: the installer that waits lets the old one go.</summary>
    internal static void Confirm(string folder, string version) => File.WriteAllText(Path.Combine(folder, ConfirmedName), version);

    internal static bool IsConfirmed(string folder, string version) => Kept(Path.Combine(folder, ConfirmedName)) == version;

    internal static void Unconfirm(string folder) => File.Delete(Path.Combine(folder, ConfirmedName));

    /// <summary>Whether this outcome was already told to the person; each one is told once.</summary>
    internal bool WasTold(string folder) => Kept(Path.Combine(folder, ToldName)) == At;

    internal void MarkTold(string folder) => File.WriteAllText(Path.Combine(folder, ToldName), At);

    private static string? Kept(string path)
    {
        try
        {
            return File.ReadAllText(path).Trim();
        }
        catch (Exception unread) when (unread is IOException or UnauthorizedAccessException)
        {
            return null;
        }
    }

    private static string? Text(JsonObject json, string name) =>
        json[name] is JsonValue value && value.TryGetValue(out string? text) && !string.IsNullOrWhiteSpace(text) ? text : null;

    private static long Number(JsonObject json, string name) =>
        json[name] is JsonValue value && value.TryGetValue(out long number) ? number : 0;
}
