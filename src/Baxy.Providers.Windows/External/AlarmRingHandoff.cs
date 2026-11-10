using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// ALR1 (owner, 2026-11-08: «que cuando suena un recordatorio me suene y me lo repita… mismo funcionamiento que la alarma
/// de celular»): how a ring passes from the Task Scheduler's ring script to the open BAXY App and back. The App and the
/// core are separate processes, so the hand-off is files in the notifications folder of the data root:
/// <list type="bullet">
/// <item>the App holds the named mutex <see cref="MutexName"/> while it can ring;</item>
/// <item>at the time, the ring script, seeing that mutex, writes <c>&lt;task&gt;.due</c> (kind, title, clock, when) and
/// waits; the App takes it by renaming it to <c>&lt;task&gt;.ringing</c> (<see cref="Take"/>), so exactly one of the two
/// rings: a script that waited in vain takes it back by renaming it away and shows Windows' alarm notification;</item>
/// <item>stopping or snoozing it (schedule.alarms stop / snooze, the card's buttons go through it too) writes
/// <c>&lt;task&gt;.answer</c>; the App ends the ring by removing <c>.ringing</c>, which is what the operation reads back.</item>
/// </list>
/// </summary>
public static class AlarmRingHandoff
{
    /// <summary>The script's «it is the time».</summary>
    public const string DueExtension = ScheduledRingTasks.DueExtension;

    /// <summary>The App took the ring: it rings now.</summary>
    public const string RingingExtension = ScheduledRingTasks.RingingExtension;

    /// <summary>A stop or a snooze was asked for this ring.</summary>
    public const string AnswerExtension = ".answer";

    /// <summary>Characters of the task's id the model names a ringing notification by (its last ones).</summary>
    public const int IdLength = 8;

    /// <summary>The notifications folder of a data root (the one schedule.alarms writes).</summary>
    public static string Folder(string dataRoot) =>
        Path.Combine(Path.GetFullPath(dataRoot), ScheduledRingTasks.FolderName);

    /// <summary>The mutex the App holds while it can ring this folder's notifications: one per data root.</summary>
    public static string MutexName(string alarmRoot)
    {
        byte[] hash = SHA256.HashData(Encoding.UTF8.GetBytes(
            Path.GetFullPath(alarmRoot).TrimEnd(Path.DirectorySeparatorChar).ToUpperInvariant()));
        return @"Local\BAXY-Ring-" + Convert.ToHexStringLower(hash)[..16];
    }

    /// <summary>Whether an App holds this folder's rings now (its mutex exists): a .ringing file with no App behind it
    /// rings nowhere (the App ended without ending it).</summary>
    public static bool AppHolds(string alarmRoot)
    {
        if (!Mutex.TryOpenExisting(MutexName(alarmRoot), out Mutex? held))
        {
            return false;
        }

        held.Dispose();
        return true;
    }

    /// <summary>The short id of a notification's task (<c>BAXY-Alarm-…</c>): its last <see cref="IdLength"/> hex digits.</summary>
    public static string Id(string taskName) => taskName[^IdLength..];

    /// <summary>One ring: the task, its short id, its kind, its title (null when it has none), the local clock it was set
    /// for (HH:mm) and when it rang.</summary>
    public sealed record Ring(string TaskName, string Id, string Kind, string? Title, string Clock, DateTimeOffset RangUtc);

    /// <summary>Takes the ring the script handed over (renames its .due to .ringing); null when the script took it back
    /// first, or it is not a ring of BAXY's.</summary>
    public static Ring? Take(string duePath)
    {
        ArgumentNullException.ThrowIfNull(duePath);
        string ringing = Path.ChangeExtension(duePath, RingingExtension);
        string taskName = Path.GetFileNameWithoutExtension(duePath);
        if (!IsTaskName(taskName))
        {
            return null;
        }

        // An answer left from an earlier ring of this task (a daily alarm's yesterday) never ends this one.
        TryDelete(Path.ChangeExtension(duePath, AnswerExtension));
        try
        {
            File.Move(duePath, ringing);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return null;
        }

        // Once taken, the script has left it to this App: one that cannot be read still rings, at the time it was taken.
        return Read(ringing) ?? new Ring(taskName, Id(taskName), Kind(taskName), null,
            DateTimeOffset.Now.ToString("HH:mm", System.Globalization.CultureInfo.InvariantCulture), DateTimeOffset.UtcNow);
    }

    /// <summary>Removes every answer file of this folder (none is pending when an App starts).</summary>
    public static void ClearAnswers(string alarmRoot)
    {
        try
        {
            foreach (string answer in Directory.EnumerateFiles(alarmRoot, "BAXY-*" + AnswerExtension))
            {
                TryDelete(answer);
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // The next take of each ring clears its own.
        }
    }

    /// <summary>What rings now in this folder, the oldest first.</summary>
    public static IReadOnlyList<Ring> Ringing(string alarmRoot)
    {
        try
        {
            return [.. Directory.EnumerateFiles(alarmRoot, "BAXY-*" + RingingExtension)
                .Select(Read).OfType<Ring>().OrderBy(static ring => ring.RangUtc)];
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return [];
        }
    }

    /// <summary>Asks the App to end this ring: «stop», or «snooze» (the next ring is already set).</summary>
    public static void Answer(string alarmRoot, string taskName, string action) =>
        File.WriteAllText(Path.Combine(alarmRoot, taskName + AnswerExtension), action, new UTF8Encoding(false));

    /// <summary>The answer asked for this ring, or null.</summary>
    public static string? AnswerOf(string alarmRoot, string taskName)
    {
        try
        {
            string path = Path.Combine(alarmRoot, taskName + AnswerExtension);
            return File.Exists(path) ? File.ReadAllText(path).Trim() : null;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return null;
        }
    }

    /// <summary>Whether this ring still rings.</summary>
    public static bool IsRinging(string alarmRoot, string taskName) =>
        File.Exists(Path.Combine(alarmRoot, taskName + RingingExtension));

    /// <summary>The App ended this ring (answered, or it rang its time out): it no longer rings.</summary>
    public static void End(string alarmRoot, string taskName)
    {
        TryDelete(Path.Combine(alarmRoot, taskName + RingingExtension));
        TryDelete(Path.Combine(alarmRoot, taskName + AnswerExtension));
    }

    private static Ring? Read(string path)
    {
        string taskName = Path.GetFileNameWithoutExtension(path);
        if (!IsTaskName(taskName))
        {
            return null;
        }

        try
        {
            using JsonDocument document = JsonDocument.Parse(File.ReadAllText(path));
            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object
                || !root.TryGetProperty("rangUtc", out JsonElement rang) || rang.ValueKind != JsonValueKind.String
                || !DateTimeOffset.TryParse(rang.GetString(), System.Globalization.CultureInfo.InvariantCulture,
                    System.Globalization.DateTimeStyles.RoundtripKind, out DateTimeOffset rangUtc))
            {
                return null;
            }

            string? title = root.TryGetProperty("title", out JsonElement value) && value.ValueKind == JsonValueKind.String
                && !string.IsNullOrWhiteSpace(value.GetString()) ? value.GetString()!.Trim() : null;
            // A ring script that does not know its time (hourly, or upgraded from before) says the time it rang.
            string clock = root.TryGetProperty("clock", out JsonElement at) && at.ValueKind == JsonValueKind.String
                && !string.IsNullOrWhiteSpace(at.GetString())
                ? at.GetString()!
                : rangUtc.ToLocalTime().ToString("HH:mm", System.Globalization.CultureInfo.InvariantCulture);
            return new Ring(taskName, Id(taskName), Kind(taskName), title, clock, rangUtc);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
        {
            return null;
        }
    }

    // INT16 (blind review): the very name ScheduledRingScript gives a ring's task; a shorter one, taken, broke the App's
    // ring card (its id is the name's last 32 characters) and with it the loop that rings.
    private static bool IsTaskName(string taskName) => ScheduledRingScript.IsRingTask(taskName);

    private static string Kind(string taskName) =>
        taskName.StartsWith("BAXY-Alarm-", StringComparison.Ordinal) ? "alarm" : "reminder";

    private static void TryDelete(string path)
    {
        try
        {
            File.Delete(path);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // Left for the next start of the App, which clears what no ring holds.
        }
    }
}
