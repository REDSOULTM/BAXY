using System.Diagnostics;
using System.Globalization;
using System.IO;

namespace Baxy.Installer;

/// <summary>
/// V132 (1.3.2, PKG6): the uninstall from the installed copy runs from a copy in TEMP (Program.UninstallFromACopy), and
/// Windows does not let a running exe delete itself, so each uninstall from «Installed apps» or by its
/// QuietUninstallString left 81 MB in TEMP for ever. Inno Setup's uninstaller, whose two phases these are, sweeps its
/// leftover copy on its next run (DeleteResidualTempUninstallDirs); after an uninstall nothing of BAXY runs again, so the
/// copy hands its removal to cmd.exe, which outlives it: it deletes the copy by name once it is let go and then its
/// folder only when empty, so nothing it did not bring is ever deleted.
/// </summary>
internal static class TempCopy
{
    internal const string CopyName = "BAXY-Desinstalador.exe";
    internal const string FolderPrefix = "BAXY-";

    /// <summary>
    /// The folder <see cref="Program"/> made for this copy (<c>TEMP\BAXY-*</c>, directly in TEMP, its name only letters,
    /// digits and dots as Directory.CreateTempSubdirectory makes it), holding the copy and nothing else; null for any other
    /// place (the downloaded installer, a copy run by hand from elsewhere).
    /// </summary>
    internal static string? FolderToRemove(string copy, string temp)
    {
        try
        {
            string file = Path.GetFullPath(copy);
            string? folder = Path.GetDirectoryName(file);
            if (folder is null
                || !string.Equals(Path.GetFileName(file), CopyName, StringComparison.OrdinalIgnoreCase)
                || !IsOwnName(Path.GetFileName(folder))
                || !string.Equals(
                    Path.GetDirectoryName(folder),
                    Path.TrimEndingDirectorySeparator(Path.GetFullPath(temp)),
                    StringComparison.OrdinalIgnoreCase))
            {
                return null;
            }

            string[] entries = Directory.GetFileSystemEntries(folder);
            return entries.Length == 1 && string.Equals(entries[0], file, StringComparison.OrdinalIgnoreCase) ? folder : null;
        }
        catch (Exception unreadable) when (unreadable is IOException or UnauthorizedAccessException or ArgumentException
            or NotSupportedException)
        {
            Program.Log(unreadable.ToString());
            return null;
        }
    }

    /// <summary>
    /// cmd.exe in TEMP, hidden: it names the folder by its own name only (<see cref="IsOwnName"/>), so nothing of TEMP's
    /// path reaches cmd's syntax (a %i in it would be the loop's). Each try deletes the copy if it is a file, then the
    /// folder if it is empty, and waits a second (ping, as timeout needs a console's input). Started by the shell, it
    /// inherits no handle of the copy: a script reading the original's output is not held until it ends.
    /// </summary>
    internal static ProcessStartInfo Remover(string folder, string temp, int tries = 60)
    {
        string name = Path.GetFileName(folder);
        if (!IsOwnName(name))
        {
            throw new ArgumentException($"{folder} is not a copy's folder", nameof(folder));
        }

        string copy = $"{name}\\{CopyName}";
        string ping = Path.Combine(Environment.SystemDirectory, "PING.EXE");
        return new ProcessStartInfo(Path.Combine(Environment.SystemDirectory, "cmd.exe"))
        {
            // /s: the outer quotes are cmd's and the inner ones stay; /v:off: no ! expansion whatever the registry says.
            Arguments = string.Create(CultureInfo.InvariantCulture,
                $"/d /q /v:off /s /c \"for /l %i in (1,1,{tries}) do @(if not exist \"{copy}\\*\" del /f /q \"{copy}\" 2>nul"
                + $" & rmdir \"{name}\" 2>nul & if not exist \"{name}\" (exit /b 0) else \"{ping}\" -n 2 127.0.0.1 >nul)\""),
            UseShellExecute = true,
            WindowStyle = ProcessWindowStyle.Hidden,
            WorkingDirectory = temp,
        };
    }

    /// <summary>The copy's last act: its removal handed over, or nothing when it is not the copy in TEMP.</summary>
    internal static void RemoveWhenDone()
    {
        string temp = Path.GetTempPath();
        if (Environment.ProcessPath is not { } copy || FolderToRemove(copy, temp) is not { } folder)
        {
            return;
        }

        try
        {
            using Process? started = Process.Start(Remover(folder, temp));
            Program.Log($"the copy in {folder} is removed once it ends");
        }
        catch (Exception failed) when (failed is System.ComponentModel.Win32Exception or InvalidOperationException)
        {
            Program.Log(failed.ToString());
        }
    }

    private static bool IsOwnName(string name) =>
        name.Length > FolderPrefix.Length
        && name.StartsWith(FolderPrefix, StringComparison.OrdinalIgnoreCase)
        && name.All(static character => char.IsAsciiLetterOrDigit(character) || character is '.' or '-');
}
