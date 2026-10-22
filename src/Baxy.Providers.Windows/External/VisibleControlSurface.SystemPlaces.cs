using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.External;

internal static partial class VisibleControlSurface
{
    // Renew al máximo (lote 4, c): the Control Panel applets that configure Windows itself, as the system tools of the
    // incidente del 2026-10-15 do (SystemToolProcesses), run inside processes the person also uses: rundll32 hosts every
    // applet (Control_RunDLL <file>.cpl, the Sound one the person asks for too) and explorer every folder, so no process
    // name tells them. The system properties (sysdm.cpl), the network connections whose «Deshabilitar» leaves the machine
    // without network (ncpa.cpl) and the firewall (firewall.cpl) are never acted on: told in rundll32 by the applet its
    // command line runs, and in explorer by a folder window titled with the name Windows itself gives the Network
    // Connections folder or the firewall's page (their shell folders' localized names, read from the registry).
    private static readonly HashSet<string> SystemApplets = new(StringComparer.OrdinalIgnoreCase)
    {
        "sysdm", "ncpa", "firewall",
    };

    // Network Connections and Windows Defender Firewall, as the shell names their folders.
    private static readonly string[] SystemPlaceFolders =
    [
        "{7007ACC7-3202-11D1-AAD2-00805FC1270E}", "{4026492F-2F69-46B8-B9BF-5654FC07E423}",
    ];

    /// <summary>
    /// A window of a Control Panel applet that configures Windows itself: rundll32 running sysdm.cpl, ncpa.cpl or
    /// firewall.cpl (<paramref name="commandLine"/>), or an explorer folder window (CabinetWClass) whose title, or a
    /// « - » segment of it, is one of <paramref name="systemPlaces"/>, folded. Never acted on, named or not.
    /// </summary>
    internal static bool SystemToolWindow(
        string? processName, string? className, string? title, string? commandLine, IReadOnlyCollection<string> systemPlaces)
    {
        string process = (processName ?? string.Empty).Trim();
        if (process.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
            process = process[..^4];
        if (string.Equals(process, "rundll32", StringComparison.OrdinalIgnoreCase))
        {
            return !string.IsNullOrEmpty(commandLine)
                && AppletRun().Matches(commandLine).Any(applet => SystemApplets.Contains(applet.Groups["name"].Value));
        }

        if (!string.Equals(process, "explorer", StringComparison.OrdinalIgnoreCase)
            || !string.Equals(className, "CabinetWClass", StringComparison.Ordinal))
            return false;
        string folded = FoldTitle(title);
        if (folded.Length == 0)
            return false;
        string[] segments = TitleSeparator().Split(folded);
        return systemPlaces.Select(FoldTitle).Any(place => place.Length > 0 && segments.Contains(place, StringComparer.Ordinal));
    }

    /// <summary>
    /// <paramref name="root"/> or a window that owns it is a system tool's (<paramref name="systemWindow"/>): a dialog
    /// an applet opens (an adapter's properties over Network Connections) is the applet's.
    /// </summary>
    internal static bool SystemToolChain(nint root, Func<nint, nint> ownerOf, Func<nint, bool> systemWindow)
    {
        for (int hop = 0; root != 0 && hop < 8; hop++, root = ownerOf(root))
        {
            if (systemWindow(root))
                return true;
        }

        return false;
    }

    /// <summary>The window's root, or a window that owns it, is a Control Panel applet that configures Windows.</summary>
    internal static bool SystemToolWindow(nint window)
    {
        nint root = window == 0 ? 0 : GetAncestor(window, 2);
        return SystemToolChain(root, owned => GetWindow(owned, 4), candidate =>
        {
            (int processId, string processName) = WindowProcess(candidate);
            bool hostsApplets = string.Equals(processName, "rundll32", StringComparison.OrdinalIgnoreCase);
            return SystemToolWindow(
                processName, ClassName(candidate), WindowTitle(candidate), hostsApplets ? CommandLineOf(processId) : null,
                SystemPlaces);
        });
    }

    private static readonly Lazy<IReadOnlyList<string>> SystemPlaceNames = new(ReadSystemPlaces);

    /// <summary>The names this Windows gives the Network Connections folder and the firewall's page.</summary>
    internal static IReadOnlyList<string> SystemPlaces => SystemPlaceNames.Value;

    private static string[] ReadSystemPlaces()
    {
        var names = new List<string>();
        foreach (string folder in SystemPlaceFolders)
        {
            try
            {
                using Microsoft.Win32.RegistryKey? key = Microsoft.Win32.Registry.ClassesRoot.OpenSubKey(@"CLSID\" + folder);
                if (key?.GetValue("LocalizedString") is string localized && IndirectString(localized) is { Length: > 0 } shown)
                    names.Add(shown);
                // The folder's own name, the one an English Windows shows.
                if (key?.GetValue(null) is string own && own.Trim().Length > 0)
                    names.Add(own.Trim());
            }
            catch (Exception exception) when (exception is System.Security.SecurityException or IOException
                or UnauthorizedAccessException)
            {
            }
        }

        return [.. names];
    }

    private static string? IndirectString(string source)
    {
        char[] buffer = new char[512];
        return SHLoadIndirectString(source, buffer, buffer.Length, 0) == 0
            && Array.IndexOf(buffer, '\0') is var end and > 0
                ? new string(buffer, 0, end).Trim()
                : null;
    }

    /// <summary>The command line a process was started with (ProcessCommandLineInformation); null when not read.</summary>
    internal static string? CommandLineOf(int processId)
    {
        if (processId <= 0)
            return null;
        nint process = OpenProcess(0x1000, false, unchecked((uint)processId));
        if (process == 0)
            return null;
        nint buffer = 0;
        try
        {
            _ = NtQueryInformationProcess(process, 60, 0, 0, out int size);
            if (size <= 0 || size > 1 << 20)
                return null;
            buffer = Marshal.AllocHGlobal(size);
            if (NtQueryInformationProcess(process, 60, buffer, size, out _) != 0)
                return null;
            // A UNICODE_STRING: its length in bytes, then (pointer-aligned) where its characters are.
            int length = (ushort)Marshal.ReadInt16(buffer);
            nint text = Marshal.ReadIntPtr(buffer, IntPtr.Size);
            return length == 0 || text == 0 ? string.Empty : Marshal.PtrToStringUni(text, length / 2);
        }
        finally
        {
            if (buffer != 0)
                Marshal.FreeHGlobal(buffer);
            _ = CloseHandle(process);
        }
    }

    // An applet's file in a command line: «sysdm.cpl», «"C:\WINDOWS\system32\NCPA.CPL",».
    [System.Text.RegularExpressions.GeneratedRegex(@"(?<name>[^\\/""\s,]+)\.cpl(?=$|[\s"",])",
        System.Text.RegularExpressions.RegexOptions.IgnoreCase | System.Text.RegularExpressions.RegexOptions.CultureInvariant)]
    private static partial System.Text.RegularExpressions.Regex AppletRun();

    [LibraryImport("ntdll.dll")]
    private static partial int NtQueryInformationProcess(nint process, int informationClass, nint information, int length, out int returned);

    [LibraryImport("shlwapi.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial int SHLoadIndirectString(string source, [Out] char[] output, int length, nint reserved);
}
