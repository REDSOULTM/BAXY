using System.Globalization;
using System.Security;
using System.Text;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// The ring script of one alarm or reminder: what the Task Scheduler runs at its time. ALR1 (owner, 2026-11-08: «los
/// recordatorios y alarmas son solamente un sonido de música… mismo funcionamiento que la alarma de celular»):
/// <list type="number">
/// <item>with the BAXY App of this data root open (it holds <see cref="AlarmRingHandoff.MutexName"/>), the script hands
/// the ring over (<see cref="AlarmRingHandoff"/>) and the App rings it: its tone, its voice saying the text, its card;</item>
/// <item>otherwise, or when the App did not take it within <see cref="HandOffWait"/>, Windows' own notification rings
/// it, as an alarm or a reminder (Microsoft Learn, toast schema, <c>scenario</c>: «alarm… displayed pre-expanded and stay
/// on the user's screen till dismissed. Audio will loop by default and will use alarm audio»; «reminder… displayed
/// pre-expanded and stay on the user's screen till dismissed»), with the text and the system's own Snooze and Dismiss
/// buttons (app notification content, «System actions, such as snoozing or dismissing the notification»: their labels
/// are localized by Windows). The rename of the hand-over file is atomic, so only one of the two rings.</item>
/// </list>
/// An alarm's notification loops until it is answered or <see cref="AlarmCap"/> passes, as Android's clock silences a
/// ringing alarm after 10 minutes by default (AOSP DeskClock, SettingsDAO: <c>KEY_AUTO_SILENCE</c>, default "10").
/// </summary>
public static class ScheduledRingScript
{
    /// <summary>The first line of a ring script that hands over to the App (older ones do not, and are upgraded).</summary>
    public const string Marker = "# BAXY ring v2";

    /// <summary>How long the script waits for the open App to take the ring before Windows' notification rings it.</summary>
    internal static TimeSpan HandOffWait { get; set; } = TimeSpan.FromSeconds(15);

    /// <summary>How long an alarm rings when nobody answers it (AOSP DeskClock's «Silence after», 10 minutes).</summary>
    public static readonly TimeSpan AlarmCap = TimeSpan.FromMinutes(10);

    /// <summary>Whether a name is one BAXY gives a ring's task: nothing else is a ring of BAXY's.</summary>
    internal static bool IsRingTask(string name) => ScheduledRingTasks.IsRingTask(name);

    /// <summary>
    /// Writes the ring script of the task named by <paramref name="path"/>'s file name. <paramref name="clock"/> is the
    /// local time it is set for (HH:mm), said with it when it rings; null when it changes from ring to ring (hourly) or
    /// is not known (an upgraded script), and then the time it rings is said.
    /// </summary>
    public static void Write(string path, string? title, string? clock)
    {
        ArgumentNullException.ThrowIfNull(path);
        string folder = Path.GetDirectoryName(Path.GetFullPath(path))!;
        string taskName = Path.GetFileNameWithoutExtension(path);
        string kind = ScheduledRingTasks.Kind(taskName);
        bool say = kind == AlarmRingHandoff.SayKind;
        string receipt = Path.Combine(folder, taskName + ".fired");
        string tag = taskName[^16..];
        int handOffTicks = (int)(HandOffWait.TotalMilliseconds / 250);
        // The task may run 10 minutes at most (ScheduledNotificationTaskXml: ExecutionTimeLimit PT10M), the hand-over's
        // wait included: the notification is taken away before that, or it would loop on after the script was ended.
        int capTicks = (int)((AlarmCap - HandOffWait).TotalSeconds / 5) - 3;
        string script = Marker + "\n"
            + "$ErrorActionPreference='Stop'\n"
            + (title is null ? "" : "$title=" + Decoded(title) + "\n")
            + (clock is null ? "" : "$clock='" + clock + "'\n")
            + "$receipt=" + Decoded(receipt) + "\n"
            + "$rang=[DateTimeOffset]::UtcNow.ToString('O')\n"
            // 1. The open App rings it: the .due is its to take (renamed to .ringing); one left there is taken back. Any
            // failure on the way (a mutex this user may not open, a file that cannot be written) rings Windows' notification.
            + "$held=$null\n"
            + "try{if([Threading.Mutex]::TryOpenExisting('" + AlarmRingHandoff.MutexName(folder) + "',[ref]$held)){$held.Dispose()\n"
            + "$due=[IO.Path]::ChangeExtension($receipt,'" + AlarmRingHandoff.DueExtension + "')\n"
            + "[IO.File]::WriteAllText($due,(@{rangUtc=$rang" + (title is null ? "" : ";title=$title")
            + (clock is null ? "" : ";clock=$clock") + "}|ConvertTo-Json -Compress))\n"
            + "for($i=0;$i -lt " + handOffTicks.ToString(CultureInfo.InvariantCulture)
            + " -and [IO.File]::Exists($due);$i++){Start-Sleep -Milliseconds 250}\n"
            + "$late=[IO.Path]::ChangeExtension($receipt,'.late')\n"
            + "if([IO.File]::Exists($late)){[IO.File]::Delete($late)}\n"
            // Taken only when the .due is gone: a rename that failed with it still there is no hand-over.
            + "$taken=$false;try{[IO.File]::Move($due,$late)}catch{$taken=-not [IO.File]::Exists($due)}\n"
            + "try{[IO.File]::Delete($late)}catch{}\n"
            + "if($taken){[IO.File]::WriteAllText($receipt,(@{rangUtc=$rang;rungBy='app'}|ConvertTo-Json -Compress));exit 0}}}catch{}\n"
            // 2. Windows' notification, as an alarm or a reminder, read back from the notification history: under
            // PowerShell's own AppUserModelID, which Windows registers (msg.exe, used once, does not exist on Windows 11
            // Home). A history that could not be read after Show leaves notificationShown null (auditoría final, regla 3).
            + "$toast=$false\n"
            + "$app='{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe'\n"
            + "try{[void][Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]\n"
            + "[void][Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom.XmlDocument,ContentType=WindowsRuntime]\n"
            + "$xml=New-Object Windows.Data.Xml.Dom.XmlDocument\n"
            + "$xml.LoadXml(" + Decoded(ToastXml(kind, title, clock)) + ")\n"
            + "$note=[Windows.UI.Notifications.ToastNotification]::new($xml);$note.Tag='" + tag + "'\n"
            + "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show($note);$toast=$null;Start-Sleep -Milliseconds 300\n"
            + "$toast=@([Windows.UI.Notifications.ToastNotificationManager]::History.GetHistory($app)|Where-Object{$_.Tag -eq '" + tag + "'}).Count -gt 0}catch{}\n"
            // A notification that was not shown (notifications off) still rings: the alarm sound, three times. A routine's
            // text (RUT4) never rings: not shown, its receipt says so and nothing sounds.
            + "$sound='toast'\n"
            + (say ? "if($toast -eq $false){$sound='none'}\n" :
                "if($toast -eq $false){$sound='none'\n"
                + "try{$wav='C:\\Windows\\Media\\Alarm01.wav'\n"
                + "if([IO.File]::Exists($wav)){for($i=0;$i -lt 3;$i++){(New-Object Media.SoundPlayer $wav).PlaySync();$sound='wav'}}"
                + "else{for($i=0;$i -lt 3;$i++){[Console]::Beep(880,700);$sound='beep'}}}catch{}}\n")
            + "[IO.File]::WriteAllText($receipt,(@{rangUtc=$rang;notificationShown=$toast;sound=$sound}|ConvertTo-Json -Compress))\n"
            // An alarm's notification that nobody answered stops looping at the cap.
            + (kind != "alarm" ? "" :
                "if($toast -ne $false){try{for($i=0;$i -lt " + capTicks.ToString(CultureInfo.InvariantCulture) + ";$i++){Start-Sleep -Seconds 5\n"
                + "if(@([Windows.UI.Notifications.ToastNotificationManager]::History.GetHistory($app)|Where-Object{$_.Tag -eq '" + tag + "'}).Count -eq 0){exit 0}}\n"
                + "[Windows.UI.Notifications.ToastNotificationManager]::History.Remove('" + tag + "','',$app)}catch{}}\n");
        File.WriteAllText(path, script, new UTF8Encoding(false));
    }

    /// <summary>
    /// The notification of a ring the App did not take, or took and could not sound (the App's RingToast): BAXY, the
    /// text and the time, as an alarm (its looping alarm
    /// sound) or a reminder (the reminder sound), with Windows' own Snooze and Dismiss (<c>activationType="system"</c>,
    /// no snooze interval given: «snooze only once for a system-defined time interval»).
    /// </summary>
    public static string ToastXml(string kind, string? title, string? clock)
    {
        var text = new StringBuilder("<text>BAXY</text>");
        if (title is not null) text.Append("<text>").Append(SecurityElement.Escape(title)).Append("</text>");
        // RUT4: a routine's text with BAXY closed is an ordinary notification, shown once: no alarm or reminder scenario
        // (those stay on screen until dismissed), no buttons, no sound of its own (Microsoft Learn, toast schema: the
        // scenario attribute and the audio element are optional; without them it is a normal notification).
        if (kind == AlarmRingHandoff.SayKind)
        {
            return "<toast><visual><binding template=\"ToastGeneric\">" + text + "</binding></visual></toast>";
        }

        if (clock is not null) text.Append("<text>").Append(SecurityElement.Escape(clock)).Append("</text>");
        string audio = kind == "alarm"
            ? "<audio src=\"ms-winsoundevent:Notification.Looping.Alarm\" loop=\"true\"/>"
            : "<audio src=\"ms-winsoundevent:Notification.Reminder\"/>";
        return "<toast scenario=\"" + kind + "\"><visual><binding template=\"ToastGeneric\">" + text
            + "</binding></visual><actions><action activationType=\"system\" arguments=\"snooze\" content=\"\"/>"
            + "<action activationType=\"system\" arguments=\"dismiss\" content=\"\"/></actions>" + audio + "</toast>";
    }

    /// <summary>The title a ring script keeps (its own line), or null.</summary>
    public static string? ReadTitle(string path)
    {
        if (!File.Exists(path)) return null;
        // The title's own line: a ring script with no title has none, and the receipt path in it is no title.
        Match encoded = Regex.Match(File.ReadAllText(path), @"^\$title=.*?FromBase64String\('([A-Za-z0-9+/=]+)'\)",
            RegexOptions.CultureInvariant | RegexOptions.Multiline, TimeSpan.FromMilliseconds(100));
        if (!encoded.Success) return null;
        try
        {
            return Encoding.UTF8.GetString(Convert.FromBase64String(encoded.Groups[1].Value));
        }
        catch (FormatException)
        {
            return null;
        }
    }

    /// <summary>
    /// Rewrites, in this notifications folder, every ring script written before the hand-over (the alarms and reminders
    /// already set keep ringing, now as the App or Windows' alarm notification rings them): same file, same title, same
    /// receipt, so the task that runs it stays as it is. Returns how many it rewrote; a script it cannot read or write
    /// stays as it was, and rings as before.
    /// </summary>
    public static int Upgrade(string alarmRoot)
    {
        ArgumentNullException.ThrowIfNull(alarmRoot);
        if (!Directory.Exists(alarmRoot)) return 0;
        int upgraded = 0;
        string[] scripts;
        try
        {
            scripts = Directory.GetFiles(alarmRoot, "BAXY-*.ps1");
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return 0;
        }

        foreach (string script in scripts)
        {
            if (!IsRingTask(Path.GetFileNameWithoutExtension(script))) continue;
            try
            {
                string text = File.ReadAllText(script);
                // Only BAXY's own ring scripts of before (they write their receipt): nothing else is touched.
                if (text.StartsWith(Marker, StringComparison.Ordinal) || !text.Contains("$receipt=", StringComparison.Ordinal))
                    continue;
                Write(script, ReadTitle(script), clock: null);
                upgraded++;
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                // It rings as before.
            }
        }

        return upgraded;
    }

    private static string Decoded(string value) =>
        "[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"
        + Convert.ToBase64String(Encoding.UTF8.GetBytes(value)) + "'))";
}
