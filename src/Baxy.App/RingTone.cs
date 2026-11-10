using System.IO;
using System.Runtime.InteropServices;
using Microsoft.Win32;

namespace Baxy.App;

/// <summary>
/// The sound of a ring the App plays, on Windows' default output as <see cref="Chime"/> (the device the echo canceller's
/// loopback hears, so the ear does not take the alarm for the person): the sound the person's Windows sound scheme gives
/// an alarm (<c>Notification.Looping.Alarm</c>, looped) or a reminder (<c>Notification.Reminder</c>), the same events
/// Windows' own alarm and reminder notifications play; when the scheme gives none, Windows' own files.
/// </summary>
internal static class RingTone
{
    private const uint Async = 0x1, NoDefault = 0x2, Loop = 0x8, FileName = 0x20000;

    /// <summary>Plays the kind's sound (an alarm's looped until <see cref="Stop"/>); false when nothing could play.</summary>
    internal static bool Play(string kind, bool loop)
    {
        string? path = Sound(kind == "alarm" ? "Notification.Looping.Alarm" : "Notification.Reminder",
            kind == "alarm" ? "Alarm01.wav" : "Windows Notify Calendar.wav");
        return path is not null && PlaySound(path, 0, Async | NoDefault | FileName | (loop ? Loop : 0));
    }

    /// <summary>Stops the sound the App plays (a chime too: only one plays at a time).</summary>
    internal static void Stop() => PlaySound(null, 0, 0);

    private static string? Sound(string schemeEvent, string windowsFile)
    {
        try
        {
            using RegistryKey? current = Registry.CurrentUser.OpenSubKey(
                @"AppEvents\Schemes\Apps\.Default\" + schemeEvent + @"\.Current");
            if (current?.GetValue(null) is string chosen && chosen.Length > 0)
            {
                string path = Environment.ExpandEnvironmentVariables(chosen);
                if (File.Exists(path))
                {
                    return path;
                }
            }
        }
        catch (Exception exception) when (exception is System.Security.SecurityException or IOException
            or UnauthorizedAccessException)
        {
            // The scheme could not be read: Windows' own file.
        }

        string fallback = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "Media", windowsFile);
        return File.Exists(fallback) ? fallback : null;
    }

    [DllImport("winmm.dll", EntryPoint = "PlaySoundW", CharSet = CharSet.Unicode)]
    private static extern bool PlaySound(string? sound, nint module, uint flags);
}
