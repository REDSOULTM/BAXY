using System.Runtime.InteropServices;
using System.Security;
using Baxy.Providers.Windows.Applications;
using Microsoft.Win32;
using Microsoft.Win32.SafeHandles;

namespace Baxy.Providers.Windows.Windows;

/// <summary>
/// v3 r22 revisión (la persona en plena reunión pide cerrar la app): whether an application is capturing the
/// microphone right now, read the way Windows itself shows the microphone-in-use indicator. The capability access
/// manager keeps, per application, under ConsentStore\microphone, the start and stop of its last use: a packaged
/// application under its package family name, any other under NonPackaged\ with its full executable path written
/// with '#' for ''. A recorded start with no stop means the capture is still open. Every process of the application
/// counts (a call usually captures in a helper process of the same executable or package), so a call or meeting
/// window of an application whose content otherwise lives in the account is never closed without asking: leaving a
/// call is not undone by opening the application again. Nothing here names an application.
/// </summary>
internal static class MicrophoneInUse
{
    internal const string ConsentStore =
        @"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone";

    private const uint ProcessQueryLimitedInformation = 0x00001000;
    private const int ErrorInsufficientBuffer = 122;
    private const int MaximumFamilyCharacters = 256;

    /// <summary>
    /// The consent-store subkeys (relative to <see cref="ConsentStore"/>) that may record this application's use.
    /// </summary>
    internal static IReadOnlyList<string> KeysFor(
        string? appUserModelId, string? executablePath, string? packageFamilyName)
    {
        var keys = new List<string>();
        void Add(string key)
        {
            if (!keys.Contains(key, StringComparer.OrdinalIgnoreCase))
            {
                keys.Add(key);
            }
        }

        if (!string.IsNullOrWhiteSpace(packageFamilyName))
        {
            Add(packageFamilyName.Trim());
        }

        if (!string.IsNullOrWhiteSpace(appUserModelId))
        {
            string identity = appUserModelId.Trim();
            int bang = identity.IndexOf('!', StringComparison.Ordinal);
            if (bang > 0)
            {
                Add(identity[..bang]);
            }
        }

        if (!string.IsNullOrWhiteSpace(executablePath) && Path.IsPathFullyQualified(executablePath.Trim()))
        {
            Add(@"NonPackaged\" + executablePath.Trim().Replace('\\', '#'));
        }

        return keys;
    }

    /// <summary>
    /// Whether any of the keys records a capture that started and has not stopped. <paramref name="read"/> returns
    /// the (LastUsedTimeStart, LastUsedTimeStop) pair of a key, or null when the key does not exist.
    /// </summary>
    internal static bool Capturing(IEnumerable<string> keys, Func<string, (long? Start, long? Stop)?> read)
    {
        foreach (string key in keys)
        {
            if (read(key) is { Start: > 0, Stop: 0 or null })
            {
                return true;
            }
        }

        return false;
    }

    /// <summary>
    /// Reads this machine's consent store for a window's application. A store that cannot be read counts as
    /// capturing (fail-closed: the close keeps asking).
    /// </summary>
    internal static bool Capturing(WindowIdentity identity)
    {
        try
        {
            IReadOnlyList<string> keys = KeysFor(
                identity.AppUserModelId, identity.ExecutablePath, PackageFamilyOf(identity.ProcessId));
            return Capturing(keys, ReadRegistry);
        }
        catch (Exception exception) when (exception is SecurityException or UnauthorizedAccessException
            or IOException or ArgumentException)
        {
            return true;
        }
    }

    private static (long? Start, long? Stop)? ReadRegistry(string key)
    {
        foreach (RegistryKey hive in new[] { Registry.CurrentUser, Registry.LocalMachine })
        {
            using RegistryKey? entry = hive.OpenSubKey(ConsentStore + @"\" + key, writable: false);
            if (entry is null)
            {
                continue;
            }

            long? start = AsTicks(entry.GetValue("LastUsedTimeStart"));
            long? stop = AsTicks(entry.GetValue("LastUsedTimeStop"));
            if (start is > 0 && stop is 0 or null)
            {
                return (start, stop);
            }
        }

        return null;
    }

    private static long? AsTicks(object? value) => value switch
    {
        long number => number,
        int number => number,
        _ => null,
    };

    // The package family of the window's own process (a packaged desktop application), or null when it has none or
    // cannot be opened (the identity's catalog id and executable path still name it).
    private static string? PackageFamilyOf(int processId)
    {
        if (processId <= 0)
        {
            return null;
        }

        using SafeProcessHandle handle = NativeMethods.OpenProcess(
            ProcessQueryLimitedInformation, inheritHandle: false, checked((uint)processId));
        if (handle.IsInvalid)
        {
            return null;
        }

        uint length = 0;
        int result = NativeMethods.GetPackageFamilyName(handle, ref length, 0);
        // No package (APPMODEL_ERROR_NO_PACKAGE) or anything but a size answer: no family to read.
        if (result != ErrorInsufficientBuffer || length is 0 or > MaximumFamilyCharacters)
        {
            return null;
        }

        nint buffer = Marshal.AllocHGlobal(checked((int)length * sizeof(char)));
        try
        {
            if (NativeMethods.GetPackageFamilyName(handle, ref length, buffer) != 0 || length == 0)
            {
                return null;
            }

            return Marshal.PtrToStringUni(buffer, checked((int)length - 1));
        }
        finally
        {
            Marshal.FreeHGlobal(buffer);
        }
    }
}
