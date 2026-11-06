using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.Applications;

/// <summary>
/// Encargo 94: the program Windows opens a plain text file with, as the person left it: its friendly name and executable,
/// by AssocQueryString (shlwapi), the call that reads the association the way the shell does, also for a packaged program.
/// Null when none is set.
/// </summary>
internal static partial class PlainTextAssociation
{
    private const int Success = 0;
    private const int AssocStringExecutable = 2;
    private const int AssocStringFriendlyName = 4;
    private const int MaximumLength = 1024;

    internal static (string Name, string Executable)? Read() =>
        Query(AssocStringFriendlyName) is { } name && Query(AssocStringExecutable) is { } executable
            && Path.IsPathFullyQualified(executable)
            ? (name, executable)
            : null;

    private static string? Query(int what)
    {
        char[] buffer = new char[MaximumLength];
        uint length = MaximumLength;
        if (AssocQueryString(0, what, ".txt", "open", buffer, ref length) != Success || length <= 1)
            return null;
        string text = new string(buffer, 0, (int)length - 1).Trim();
        return text.Length == 0 ? null : text;
    }

    [LibraryImport("shlwapi.dll", EntryPoint = "AssocQueryStringW", StringMarshalling = StringMarshalling.Utf16)]
    private static partial int AssocQueryString(
        uint flags, int what, string association, string? extra, [Out] char[] output, ref uint length);
}
