using System.Diagnostics;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Chrome before 138 shows UI Automation only its frame, so BAXY cannot see or press what a page holds. Measured 05-11 on
/// Chrome 136 with a page of four controls: 0 of 4 as it comes, 4 of 4 started with this flag, and the worker pressed a button
/// of the page. From 138 it is the default
/// (https://developer.chrome.com/blog/windows-uia-support-update). The flag is for the Chrome BAXY itself starts: it changes
/// nothing of the person's, lasts as long as that run, and a Chrome already open ignores it. The enterprise policy reaches
/// a Chrome the person starts too, but its menu then says «Administrado por tu organización» (measured), so it is not used.
/// </summary>
internal static class ChromeUiaFlag
{
    internal const string Flag = "--enable-features=UiaProvider";

    internal const int NativeFromMajor = 138;

    internal static string? For(string? executable) => For(executable, ReadMajor);

    internal static string? For(string? executable, Func<string, int?> major)
    {
        if (string.IsNullOrWhiteSpace(executable)
            || !string.Equals(Path.GetFileName(executable), "chrome.exe", StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        return major(executable) is int version && version < NativeFromMajor ? Flag : null;
    }

    private static int? ReadMajor(string executable)
    {
        if (!File.Exists(executable))
            return null;
        int major = FileVersionInfo.GetVersionInfo(executable).FileMajorPart;
        return major > 0 ? major : null;
    }
}
