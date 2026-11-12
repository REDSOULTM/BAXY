using Microsoft.Win32;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// The browser the person uses: the one Windows opens a web link with
/// (HKCU UrlAssociations\https, <see cref="UserBrowserIdentityResolver.ChosenProgId"/>), not one BAXY picks. Owner 2026-10-02:
/// «cuando le pido una canción de YouTube la abre en Edge, que no es mi navegador
/// predeterminado; tengo Disney y HBO iniciados en Opera».
/// </summary>
internal sealed record UserBrowserIdentity(
    string ProgId,
    string Family,
    string DisplayName,
    string Executable)
{
    /// <summary>
    /// The process that draws the browser's windows. Opera may register its launcher.exe, which hands the page to
    /// opera.exe and owns no window, so a listing by the launcher's name would take a running Opera for a closed one.
    /// </summary>
    internal string ProcessName => Family is "opera" or "opera_gx"
        ? "opera"
        : Path.GetFileNameWithoutExtension(Executable);

    /// <summary>
    /// Fragments of the SMTC SourceAppUserModelId a Chromium or Firefox build
    /// publishes for its media sessions. Firefox registers a hashed AUMID
    /// (308046B0AF4A39CB for the release channel), hence the second token.
    /// Opera's two editions are told apart in <see cref="OwnsMediaSession"/>.
    /// </summary>
    private IReadOnlyList<string> MediaSessionTokens => Family switch
    {
        "chrome" => ["chrome"],
        "edge" => ["msedge", "microsoftedge"],
        "brave" => ["brave"],
        "vivaldi" => ["vivaldi"],
        "firefox" => ["firefox", "308046b0af4a39cb"],
        _ => [ProcessName],
    };

    /// <summary>
    /// Whether the media session is this browser's. Opera and Opera GX are separate browsers: Opera GX publishes
    /// «OperaSoftware.OperaGXWebBrowser.…» (measured), or «Opera GXStable» by its ProgId, so a session of one never
    /// verifies a page opened in the other.
    /// </summary>
    internal bool OwnsMediaSession(string sourceAppUserModelId)
    {
        if (Family is "opera" or "opera_gx")
        {
            string folded = string.Concat(sourceAppUserModelId.Where(char.IsLetterOrDigit)).ToLowerInvariant();
            bool gx = folded.Contains("operagx", StringComparison.Ordinal);
            return Family == "opera_gx" ? gx : !gx && folded.Contains("opera", StringComparison.Ordinal);
        }
        return MediaSessionTokens.Any(token => sourceAppUserModelId.Contains(
            token, StringComparison.OrdinalIgnoreCase));
    }
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
                using RegistryKey? association = Registry.CurrentUser.OpenSubKey(UrlAssociations + scheme);
                string? progId = association is null ? null : ChosenProgId(association);
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

    /// <summary>
    /// Feria (NB-W5): the ProgId a scheme's association names. Windows 11 from 25H2 writes the person's choice to
    /// UserChoiceLatest\ProgId and no longer updates the legacy UserChoice, which keeps the browser chosen before; the
    /// legacy key counts only where the newer one is absent.
    /// </summary>
    internal static string? ChosenProgId(RegistryKey association)
    {
        using RegistryKey? latest = association.OpenSubKey(@"UserChoiceLatest\ProgId");
        using RegistryKey? legacy = association.OpenSubKey("UserChoice");
        return new[] { latest?.GetValue("ProgId"), legacy?.GetValue("ProgId") }
            .OfType<string>()
            .FirstOrDefault(static progId => !string.IsNullOrWhiteSpace(progId));
    }

    /// <summary>
    /// PC-F8 cierre (acotado): whether an executable is a web browser Windows knows: one registered as a browser
    /// (Clients\StartMenuInternet, machine and user) or the one a web link opens with. Null when the registry cannot be
    /// read.
    /// </summary>
    internal static bool? IsRegisteredBrowser(string executable)
    {
        try
        {
            if (RegisteredBrowsers(Registry.LocalMachine, Registry.CurrentUser)
                .Any(registered => SameExecutable(CommandExecutable(registered.OpenCommand), executable)))
                return true;

            return SameExecutable(ResolveFromRegistry()?.Executable, executable);
        }
        catch (Exception exception) when (exception is System.Security.SecurityException
            or UnauthorizedAccessException or IOException or ArgumentException or NotSupportedException)
        {
            return null;
        }
    }

    /// <summary>
    /// Feria 2026-10-27 (caso 19): the installed browser of a family (as <see cref="Classify"/> names it) that Windows
    /// has registered (Clients\StartMenuInternet, the user's first), whatever the default one is. Null when none of
    /// that family is registered with an executable that exists; throws when the registry cannot be read.
    /// </summary>
    internal static UserBrowserIdentity? ResolveRegistered(string family) =>
        RegisteredBrowsers(Registry.CurrentUser, Registry.LocalMachine)
            .Select(static registered => Resolve(registered.Name, registered.OpenCommand))
            .FirstOrDefault(identity => identity is not null
                && string.Equals(identity.Family, family, StringComparison.Ordinal)
                && File.Exists(identity.Executable));

    /// <summary>
    /// Encargo 100: the processes that draw the windows of every browser Windows knows (registered, or the one a web link opens
    /// with); empty when the registry cannot be read.
    /// </summary>
    internal static IReadOnlySet<string> RegisteredProcessNames()
    {
        try
        {
            HashSet<string> names = new(RegisteredBrowsers(Registry.LocalMachine, Registry.CurrentUser)
                .Select(static registered => Resolve(registered.Name, registered.OpenCommand)?.ProcessName)
                .OfType<string>(), StringComparer.OrdinalIgnoreCase);
            if (ResolveFromRegistry()?.ProcessName is { } chosen)
                names.Add(chosen);
            return names;
        }
        catch (Exception exception) when (exception is System.Security.SecurityException
            or UnauthorizedAccessException or IOException or ArgumentException or NotSupportedException)
        {
            return new HashSet<string>();
        }
    }

    /// <summary>
    /// LEC4: the browser Windows knows (the one a web link opens with first, then those registered) whose windows the
    /// process of that name draws (<see cref="UserBrowserIdentity.ProcessName"/>); null when none, or the registry cannot
    /// be read.
    /// </summary>
    internal static UserBrowserIdentity? RegisteredDrawnBy(string processName)
    {
        try
        {
            return new[] { ResolveFromRegistry() }
                .Concat(RegisteredBrowsers(Registry.CurrentUser, Registry.LocalMachine)
                    .Select(static registered => Resolve(registered.Name, registered.OpenCommand)))
                .FirstOrDefault(identity => identity is not null
                    && string.Equals(identity.ProcessName, processName, StringComparison.OrdinalIgnoreCase));
        }
        catch (Exception exception) when (exception is System.Security.SecurityException
            or UnauthorizedAccessException or IOException or ArgumentException or NotSupportedException)
        {
            return null;
        }
    }

    private static IEnumerable<(string Name, string? OpenCommand)> RegisteredBrowsers(params RegistryKey[] hives)
    {
        foreach (RegistryKey hive in hives)
        {
            foreach (string clients in new[] { @"SOFTWARE\Clients\StartMenuInternet", @"SOFTWARE\WOW6432Node\Clients\StartMenuInternet" })
            {
                using RegistryKey? browsers = hive.OpenSubKey(clients);
                foreach (string name in browsers?.GetSubKeyNames() ?? [])
                {
                    using RegistryKey? command = browsers!.OpenSubKey(name + @"\shell\open\command");
                    yield return (name, command?.GetValue(null) as string);
                }
            }
        }
    }

    private static bool SameExecutable(string? registered, string executable) =>
        registered is not null && string.Equals(
            Path.GetFullPath(registered), Path.GetFullPath(executable), StringComparison.OrdinalIgnoreCase);

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
