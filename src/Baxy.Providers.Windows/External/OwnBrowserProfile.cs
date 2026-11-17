using System.Diagnostics;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// DIAX11 (privacidad; vivo Radeon H-006 y PC del dueño, Edge 157.0.4341.60): BAXY's own browser profiles
/// (<c>%LOCALAPPDATA%\BAXY\browser-session-v1\&lt;family&gt;</c>) never take the person's account. A new Edge profile
/// signed itself in with the Microsoft account Windows is signed into within 3 s and turned sync on
/// (<c>account_info</c>, <c>consented_to_sync=true</c>; at 5 min on the Radeon <c>has_setup_completed</c> and
/// <c>keep_everything_synced</c>): what BAXY browsed went up to the person's account, and their passwords and favorites
/// came down into a profile BAXY drives over CDP. Microsoft documents the behavior (ImplicitSignInEnabled, «Microsoft
/// Edge attempts to sign in the user into their profile based on what and how they sign in to their OS»,
/// https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies/ImplicitSignInEnabled, 2026-11-03), but its
/// remedies are machine policies, and the person's machine is not BAXY's to configure.
/// </summary>
internal static class OwnBrowserProfile
{
    /// <summary>
    /// The Edge features behind the person's Microsoft account reaching an own profile, all off. «msImplicitSignin»:
    /// the sign-in with the account Windows is signed into, named in msedge.dll 157 and turned off for the same reason
    /// by apps that launch Edge on a profile of their own («Without them a fresh Edge profile signs itself in with the
    /// Microsoft account Windows is signed into, shows a sync prompt over the app window», github.com/Niminem/Neel
    /// docs/GUIDE.md, 2026-10-16; also gary23w/nl-veil, dseditor/QwenASRMiniTool); «msM365LinksImplicitSignin», the same
    /// from a Microsoft 365 link. The rest are the single sign-on to Microsoft sites with the machine's account that
    /// Microsoft documents for profiles with no account of their own («allows non-MSA profiles to be able to use single
    /// sign-on for Microsoft sites using MSA credentials present on the machine», MSAWebSiteSSOUsingThisProfileAllowed,
    /// learn.microsoft.com, 2026-11-03), and its step from a site's session to the browser's («web to browser»).
    /// Measured on Edge 157 (tmp\DIAX11ivo, sso.log): with msImplicitSignin alone, opening bing.com left the
    /// person's session on Bing and Live (_U, .MSA.Auth, MSPAuth) and the account in the profile 2 of 2, and turning
    /// that profile's own SSO switch off (edge.msa_sso_info.allow_for_non_msa_profile=false) did not stop it; with
    /// these off, no session 5 of 5 (bing.com, a Bing search, login.live.com, msn.com, outlook.live.com).
    /// </summary>
    internal static readonly string[] EdgeAccountFeatures =
    [
        "msImplicitSignin",
        "msM365LinksImplicitSignin",
        "msAllowMSAPrtSSOForNonMSAProfile",
        "msAutoToggleMSAPrtSSOForNonMSAProfile",
        "msSSOBrowserHint",
        "msSSOBrowserHintPhase2",
        "msSsoByHttpDefer",
        "msEnableWebToBrowserSignIn",
        "msSeamlessWebToBrowserSignIn",
        "msQuickAuthToBrowserSignIn",
    ];

    /// <summary>
    /// What every launch of an own profile carries. «--disable-sync»: Chromium's switch, «Disables syncing browser data
    /// to a Google Account» (components/sync/base/command_line_switches.h; Edge's sync is the same service). Then
    /// <see cref="EdgeAccountFeatures"/> off. Measured on this Edge: the profile's own prefs (signin.allowed=false, Local
    /// State edge_implicit_sign_in_enabled=false) with «--disable-sync» still signed in 2 of 2. Chromium keeps only the
    /// last «--disable-features», so no other launch argument may carry one. A browser that does not know a feature
    /// (Chrome, Brave, Opera) ignores it.
    /// </summary>
    internal static readonly string[] AccountSwitches =
        ["--disable-sync", "--disable-features=" + string.Join(',', EdgeAccountFeatures)];

    /// <summary>Written once every own profile was checked: the check is the 1.5.x profiles' migration, not a rule
    /// over a sign-in the person makes later in BAXY's browser on purpose (sync stays off for it anyway).</summary>
    internal const string CheckedMarker = "account-check-v1";

    /// <summary>The families whose profile was discarded and not yet said to the person.</summary>
    internal const string NoticeMarker = "account-removed-notice";

    /// <summary>
    /// The one family whose own profile took an account by itself: Edge signs a profile in with the account Windows is
    /// signed into (ImplicitSignInEnabled, above). Chrome, Brave and Opera have no such sign-in, so an account in their
    /// own profile is one the person put there on purpose (REVX2 DX11-1): theirs, kept, and launched with sync off
    /// (<see cref="AccountSwitches"/>) like every own profile.
    /// </summary>
    internal const string SignsItselfIn = "edge";

    private const long LargestReadBytes = 32L * 1024 * 1024;

    /// <summary>The folder of BAXY's own browser profiles (browser-session-v1); null when they live elsewhere (no
    /// LocalApplicationData: each profile then sits inside the data profile, beside what is not a browser's).</summary>
    internal static string? SharedRoot(string dataRoot)
    {
        string? root = Path.GetDirectoryName(WebBrowserAdapter.SharedBrowserProfile(dataRoot, "edge"));
        return root is not null && string.Equals(Path.GetFileName(root), "browser-session-v1", StringComparison.Ordinal)
            ? root
            : null;
    }

    /// <summary>The data root of the BAXY installed for this Windows user (Baxy.Core and the App without
    /// BAXY_DATA_DIR); null without LocalApplicationData.</summary>
    internal static string? InstalledDataRoot()
    {
        try
        {
            string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            return string.IsNullOrWhiteSpace(local) ? null : Path.Combine(local, "BAXY", "1");
        }
        catch (Exception exception) when (exception is ArgumentException or PlatformNotSupportedException)
        {
            return null;
        }
    }

    /// <summary>
    /// <paramref name="sharedRoot"/> only for the BAXY it belongs to, the one installed for this Windows user (REVX2
    /// DX11-3): the folder is per user, not per data root, so a core or App on another data root (a live test, a dev
    /// instance: BAXY_DATA_DIR) would otherwise discard the installed BAXY's profiles and take the notice its App has to
    /// say. Null for any other data root: nothing there is looked at, deleted or marked.
    /// </summary>
    internal static string? SharedRootOwnedBy(string dataRoot, string? sharedRoot, string? installedDataRoot)
    {
        if (sharedRoot is null || installedDataRoot is null)
            return null;
        try
        {
            return string.Equals(Path.TrimEndingDirectorySeparator(Path.GetFullPath(dataRoot)),
                Path.TrimEndingDirectorySeparator(Path.GetFullPath(installedDataRoot)), StringComparison.OrdinalIgnoreCase)
                ? sharedRoot
                : null;
        }
        catch (Exception exception) when (exception is ArgumentException or NotSupportedException
            or PathTooLongException)
        {
            return null;
        }
    }

    /// <summary>
    /// Whether the Chromium user data folder <paramref name="userDataDir"/> is signed in to an account: the browser's
    /// profile list names a primary account (<c>Local State</c> profile.info_cache: gaia_id, user_name,
    /// is_consented_primary_account), or a profile consented to sync or set it up (<c>Preferences</c>
    /// google.services.consented_to_sync, sync.has_setup_completed). A site the person signed in to inside BAXY's
    /// browser (an <c>account_info</c> with no primary account and no sync) is not: that session is theirs to keep.
    /// Never reads or returns who: only whether. An unreadable file is no evidence.
    /// </summary>
    internal static bool IsSignedIn(string userDataDir)
    {
        if (!Directory.Exists(userDataDir))
            return false;
        if (Read(Path.Combine(userDataDir, "Local State")) is { } localState)
        {
            using (localState)
            {
                if (localState.RootElement.ValueKind == JsonValueKind.Object
                    && localState.RootElement.TryGetProperty("profile", out JsonElement profile)
                    && profile.ValueKind == JsonValueKind.Object
                    && profile.TryGetProperty("info_cache", out JsonElement cache)
                    && cache.ValueKind == JsonValueKind.Object)
                {
                    foreach (JsonProperty entry in cache.EnumerateObject())
                    {
                        if (entry.Value.ValueKind == JsonValueKind.Object
                            && (NonEmptyText(entry.Value, "gaia_id") || NonEmptyText(entry.Value, "user_name")
                                || IsTrue(entry.Value, "is_consented_primary_account")))
                            return true;
                    }
                }
            }
        }
        IEnumerable<string> profiles;
        try
        {
            profiles = Directory.EnumerateDirectories(userDataDir).ToArray();
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return false;
        }
        foreach (string directory in profiles)
        {
            if (Read(Path.Combine(directory, "Preferences")) is not { } preferences)
                continue;
            using (preferences)
            {
                JsonElement root = preferences.RootElement;
                if (root.ValueKind != JsonValueKind.Object)
                    continue;
                if (root.TryGetProperty("google", out JsonElement google) && google.ValueKind == JsonValueKind.Object
                    && google.TryGetProperty("services", out JsonElement services)
                    && services.ValueKind == JsonValueKind.Object && IsTrue(services, "consented_to_sync"))
                    return true;
                if (root.TryGetProperty("sync", out JsonElement sync) && sync.ValueKind == JsonValueKind.Object
                    && IsTrue(sync, "has_setup_completed"))
                    return true;
            }
        }
        return false;
    }

    /// <summary>
    /// Once (<see cref="CheckedMarker"/>): the own Edge profile under <paramref name="root"/> (<see cref="SignsItselfIn"/>;
    /// no other family's) that holds an account (<see cref="IsSignedIn"/>) is discarded: its browser, if still open (BAXY's browser outlives BAXY), is
    /// closed —only the processes started on that very folder—, and the folder is deleted, since what it holds of the
    /// person came from their account, which keeps it. The person's own browsers and their account are not touched.
    /// The families discarded wait in <see cref="NoticeMarker"/> to be said once. A profile that cannot be deleted now
    /// leaves the check undone, so the next start tries again.
    /// </summary>
    internal static IReadOnlyList<string> DiscardSignedInProfiles(string root, Func<string, int>? closeBrowsers = null)
    {
        closeBrowsers ??= CloseBrowsersOn;
        if (!Directory.Exists(root) || File.Exists(Path.Combine(root, CheckedMarker)))
            return [];
        var discarded = new List<string>();
        bool complete = true;
        string directory = Path.Combine(root, SignsItselfIn);
        if (Directory.Exists(directory) && new DirectoryInfo(directory).LinkTarget is null && IsSignedIn(directory))
        {
            closeBrowsers(directory);
            if (TryDelete(directory))
                discarded.Add(SignsItselfIn);
            else
                complete = false;
        }
        try
        {
            if (discarded.Count > 0)
            {
                string notice = Path.Combine(root, NoticeMarker);
                IEnumerable<string> before = File.Exists(notice) ? File.ReadAllLines(notice) : [];
                File.WriteAllLines(notice, before.Concat(discarded).Distinct(StringComparer.Ordinal));
            }
            if (complete)
                File.WriteAllText(Path.Combine(root, CheckedMarker), string.Empty);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // Not written: the next start checks again, and finds nothing more to discard.
        }
        return discarded;
    }

    /// <summary>The families discarded and not yet said (<see cref="NoticeMarker"/>).</summary>
    internal static IReadOnlyList<string> ReadNotice(string root)
    {
        try
        {
            string notice = Path.Combine(root, NoticeMarker);
            return File.Exists(notice) ? File.ReadAllLines(notice).Where(line => line.Length > 0).ToArray() : [];
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return [];
        }
    }

    /// <summary>The notice was said: it is not said again.</summary>
    internal static void ForgetNotice(string root)
    {
        try
        {
            File.Delete(Path.Combine(root, NoticeMarker));
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // Said again at the next start: better twice than never.
        }
    }

    /// <summary>Whether <paramref name="commandLine"/> started a browser on exactly <paramref name="userDataDir"/>.</summary>
    internal static bool StartedOn(string? commandLine, string userDataDir)
    {
        if (string.IsNullOrEmpty(commandLine))
            return false;
        string folder = Path.TrimEndingDirectorySeparator(Path.GetFullPath(userDataDir));
        foreach (string form in new[] { "--user-data-dir=" + folder, "\"--user-data-dir=" + folder, "--user-data-dir=\"" + folder })
        {
            for (int at = commandLine.IndexOf(form, StringComparison.OrdinalIgnoreCase); at >= 0;
                 at = commandLine.IndexOf(form, at + 1, StringComparison.OrdinalIgnoreCase))
            {
                int end = at + form.Length;
                if (end == commandLine.Length || commandLine[end] is '"' or ' ' or '\\')
                    return true;
            }
        }
        return false;
    }

    // Every process started on that folder (the browser and its children), by its own command line; nothing else.
    internal static int CloseBrowsersOn(string userDataDir)
    {
        int closed = 0;
        foreach (Process process in Process.GetProcesses())
        {
            using (process)
            {
                try
                {
                    if (!StartedOn(VisibleControlSurface.CommandLineOf(process.Id), userDataDir))
                        continue;
                    process.Kill();
                    process.WaitForExit(5000);
                    closed++;
                }
                catch (Exception exception) when (exception is InvalidOperationException
                    or System.ComponentModel.Win32Exception or NotSupportedException)
                {
                }
            }
        }
        return closed;
    }

    private static bool TryDelete(string directory)
    {
        for (int attempt = 1; ; attempt++)
        {
            try
            {
                Directory.Delete(directory, recursive: true);
                return true;
            }
            catch (DirectoryNotFoundException)
            {
                return true;
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                if (attempt >= 5)
                    return false;
                Thread.Sleep(500);
            }
        }
    }

    private static JsonDocument? Read(string path)
    {
        try
        {
            var file = new FileInfo(path);
            if (!file.Exists || file.Length > LargestReadBytes)
                return null;
            using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
            return JsonDocument.Parse(stream);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
        {
            return null;
        }
    }

    private static bool NonEmptyText(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
        && !string.IsNullOrEmpty(value.GetString());

    private static bool IsTrue(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.True;
}
