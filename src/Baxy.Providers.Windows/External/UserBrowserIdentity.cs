using Microsoft.Win32;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// The browser the person uses: the one Windows opens a web link with
/// (HKCU UrlAssociations\https\UserChoice), not one BAXY picks. Owner 2026-10-02:
/// «cuando le pido una canción de YouTube la abre en Edge, que no es mi navegador
/// predeterminado; tengo Disney y HBO iniciados en Opera».
/// </summary>
internal sealed record UserBrowserIdentity(
    string ProgId,
    string Family,
    string DisplayName,
    string Executable)
{
    internal string ProcessName => Path.GetFileNameWithoutExtension(Executable);

    /// <summary>
    /// Fragments of the SMTC SourceAppUserModelId a Chromium or Firefox build
    /// publishes for its media sessions. Firefox registers a hashed AUMID
    /// (308046B0AF4A39CB for the release channel), hence the second token.
    /// </summary>
    internal IReadOnlyList<string> MediaSessionTokens => Family switch
    {
        "opera" or "opera_gx" => ["opera"],
        "chrome" => ["chrome"],
        "edge" => ["msedge", "microsoftedge"],
        "brave" => ["brave"],
        "vivaldi" => ["vivaldi"],
        "firefox" => ["firefox", "308046b0af4a39cb"],
        _ => [ProcessName],
    };

    internal bool OwnsMediaSession(string sourceAppUserModelId) =>
        MediaSessionTokens.Any(token => sourceAppUserModelId.Contains(
            token, StringComparison.OrdinalIgnoreCase));
}

internal static class UserBrowserIdentityResolver
{
    private const string UrlAssociations =
        @"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\";

    /// <summary>
    /// Reads the https association first (what a link opens with), then http.
    /// Returns null when no association names an installed executable.
    /// </summary>
    internal static UserBrowserIdentity? ResolveFromRegistry()
    {
        foreach (string scheme in new[] { "https", "http" })
        {
            try
            {
                using RegistryKey? choice = Registry.CurrentUser.OpenSubKey(
                    UrlAssociations + scheme + @"\UserChoice");
                string? progId = choice?.GetValue("ProgId") as string;
                if (string.IsNullOrWhiteSpace(progId))
                    continue;
                using RegistryKey? command = Registry.ClassesRoot.OpenSubKey(
                    progId + @"\shell\open\command");
                UserBrowserIdentity? identity = Resolve(progId, command?.GetValue(null) as string);
                if (identity is not null && File.Exists(identity.Executable))
                    return identity;
            }
            catch (Exception exception) when (exception is System.Security.SecurityException
                or UnauthorizedAccessException or IOException or ArgumentException)
            {
                // An unreadable association is no browser: the caller keeps its fallback.
            }
        }
        return null;
    }

    internal static UserBrowserIdentity? Resolve(string? progId, string? openCommand)
    {
        if (string.IsNullOrWhiteSpace(progId))
            return null;
        string? executable = CommandExecutable(openCommand);
        if (executable is null)
            return null;
        (string family, string display) = Classify(progId, executable);
        return new UserBrowserIdentity(progId.Trim(), family, display, executable);
    }

    /// <summary>
    /// The executable of a shell open command: the quoted first token, or the
    /// unquoted text up to «.exe». Only an absolute path counts.
    /// </summary>
    internal static string? CommandExecutable(string? command)
    {
        if (string.IsNullOrWhiteSpace(command))
            return null;
        string text = Environment.ExpandEnvironmentVariables(command.Trim());
        string candidate;
        if (text.StartsWith('"'))
        {
            int end = text.IndexOf('"', 1);
            if (end <= 1)
                return null;
            candidate = text[1..end];
        }
        else
        {
            int end = text.IndexOf(".exe", StringComparison.OrdinalIgnoreCase);
            if (end < 0)
                return null;
            candidate = text[..(end + 4)];
        }
        candidate = candidate.Trim();
        return candidate.EndsWith(".exe", StringComparison.OrdinalIgnoreCase)
            && Path.IsPathFullyQualified(candidate)
                ? candidate
                : null;
    }

    internal static (string Family, string DisplayName) Classify(string progId, string executable)
    {
        string id = progId.Trim().ToLowerInvariant();
        string exe = Path.GetFileName(executable).ToLowerInvariant();
        bool gxPath = executable.Contains("Opera GX", StringComparison.OrdinalIgnoreCase);
        if (id.StartsWith("opera gx", StringComparison.Ordinal) || (exe == "opera.exe" && gxPath))
            return ("opera_gx", "Opera GX");
        if (id.StartsWith("opera", StringComparison.Ordinal) || exe == "opera.exe")
            return ("opera", "Opera");
        if (id.StartsWith("chrome", StringComparison.Ordinal) || exe == "chrome.exe")
            return ("chrome", "Google Chrome");
        if (id.StartsWith("msedge", StringComparison.Ordinal) || exe == "msedge.exe")
            return ("edge", "Microsoft Edge");
        if (id.StartsWith("brave", StringComparison.Ordinal) || exe == "brave.exe")
            return ("brave", "Brave");
        if (id.StartsWith("vivaldi", StringComparison.Ordinal) || exe == "vivaldi.exe")
            return ("vivaldi", "Vivaldi");
        if (id.StartsWith("firefox", StringComparison.Ordinal) || exe == "firefox.exe")
            return ("firefox", "Firefox");
        return ("other", Path.GetFileNameWithoutExtension(executable));
    }
}
