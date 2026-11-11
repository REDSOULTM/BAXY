using System.Diagnostics;
using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;

namespace Baxy.Core.Operations;

/// <summary>
/// baxy.update (actualizar-ordenes-app, encargo del dueño 2026-11-09: «un botón de actualizar y decirle BAXY actualízate»):
/// whether there is a newer BAXY where this one came from (<see cref="BaxyDistribution"/>), and moving to it.
/// <list type="bullet">
/// <item>GitHub: check reads the latest stable release (<see cref="GitHubLatestRelease"/>) and, when it is newer, its
/// release.json under the owner's signature (FIR1, <see cref="ReleaseSignature"/>): a release without it is never offered
/// nor installed. Install downloads its BAXY-Instalador.exe beside the profile's data, keeps it only when its bytes are
/// the size and SHA-256 that signed release.json gives (GitHub's own digest moves with whoever uploads), starts it
/// with <c>--update --dir &lt;this folder&gt;</c> and asks the App to exit as «Salir» does. The installer waits for BAXY
/// to close, downloads its own parts against the SHA-256 it carries, unpacks them beside this folder and only then swaps
/// them in; anything that fails before the swap leaves this BAXY as it was, and a swap that fails puts it back
/// (src/Baxy.Installer/Installation.cs). The person's data (%LOCALAPPDATA%\BAXY) is not in that folder.</item>
/// <item>Steam and itch.io update what they installed themselves: Steam updates its apps (Steamworks, «Uploading to
/// Steam»: a build set live reaches the customers), and the itch app «looks for game updates on start-up, and every 30
/// minutes» and installs one with a single candidate (https://itch.io/docs/itch/integrating/updates.html, read
/// 2026-11-09). BAXY never downloads around them: check says so, and install opens the store's page of BAXY (Steam's
/// library; itch.io's page from the itch app's receipt).</item>
/// </list>
/// Install asks the person's yes in normal mode (installation); check, and install on a store, lower it
/// (<see cref="PreflightAsync"/>), and there is nothing to ask when there is no newer version.
/// </summary>
internal sealed class BaxyUpdateHandler : IOperationHandler, IInvocationPreflight
{
    internal const string Operation = "baxy.update";
    private const string InstallerPrefix = "BAXY-Instalador-";

    // REV_APP UPD-b (2026-11-09): no byte of the installer in this long and the download is cut. HttpClient's timeout does
    // not do it: «when using the ResponseHeadersRead option, the timeout applies only up to where the headers end and the
    // content starts» (learn.microsoft.com/dotnet/api/system.net.http.httpcompletionoption, read 2026-11-09). The figure
    // is the one the installer's own downloads use (src/Baxy.Installer/PartFetcher.cs).
    private static readonly TimeSpan Stall = TimeSpan.FromSeconds(60);

    private readonly string? _dataRoot;
    private readonly BaxyDistribution _distribution;
    private readonly Version _installed;
    private readonly HttpClient _http;
    private readonly Func<ProcessStartInfo, bool> _start;
    private readonly string _exitEvent;
    private readonly TimeSpan _stall;
    private readonly TimeSpan _budget;
    private readonly IReadOnlyList<string> _keys;

    internal BaxyUpdateHandler(
        string? dataRoot,
        BaxyDistribution? distribution = null,
        Version? installed = null,
        HttpClient? http = null,
        Func<ProcessStartInfo, bool>? start = null,
        string exitEvent = BaxyExitHandler.AppExitEventName,
        TimeSpan? stall = null,
        TimeSpan? budget = null,
        IReadOnlyList<string>? keys = null)
    {
        _dataRoot = dataRoot;
        _distribution = distribution ?? BaxyDistribution.OfCore(AppContext.BaseDirectory);
        _installed = installed ?? OwnVersion();
        _http = http ?? new HttpClient { Timeout = TimeSpan.FromSeconds(20) };
        _start = start ?? Start;
        _exitEvent = exitEvent;
        _stall = stall ?? Stall;
        _budget = budget ?? UpdateInstallerFile.Budget;
        _keys = keys ?? ReleaseSignature.BuiltInKeys(typeof(BaxyUpdateHandler).Assembly);
    }

    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition(Operation);

    /// <summary>
    /// INS-7: every update left its installer (about 80 MB) in &lt;data&gt;\updates for good. The BAXY that starts removes
    /// the ones that install its own version or an older one, whole or half downloaded; a newer one, downloaded and
    /// not yet run, stays, and so does any file this handler did not name.
    /// </summary>
    internal static void RemoveSpentInstallers(string dataRoot) => RemoveInstallersUpTo(dataRoot, OwnVersion());

    internal static void RemoveInstallersUpTo(string dataRoot, Version installed)
    {
        string folder = UpdateInstallerFile.Folder(dataRoot);
        if (!Directory.Exists(folder))
        {
            return;
        }

        foreach (string path in Directory.EnumerateFiles(folder, InstallerPrefix + "*"))
        {
            if (InstallerVersion(Path.GetFileName(path)) is not { } version || version > installed)
            {
                continue;
            }

            try
            {
                File.Delete(path);
            }
            catch (Exception inUse) when (inUse is IOException or UnauthorizedAccessException)
            {
                // The installer that just opened this BAXY may still be closing, and Windows does not delete a file in
                // use: the next start takes it.
            }
        }
    }

    // The version in a name DownloadAsync gave: BAXY-Instalador-1.4.0.exe, or the same with .part while it arrives.
    private static Version? InstallerVersion(string name)
    {
        string rest = name[InstallerPrefix.Length..];
        foreach (string ending in (ReadOnlySpan<string>)[".exe.part", ".exe"])
        {
            if (rest.EndsWith(ending, StringComparison.OrdinalIgnoreCase))
            {
                return Version.TryParse(rest[..^ending.Length], out Version? version) && version is { Build: >= 0, Revision: -1 }
                    ? version
                    : null;
            }
        }

        return null;
    }

    private string UserAgent => $"BAXY/{_installed.ToString(3)}";

    public async ValueTask<InvocationPreflightResult> PreflightAsync(JsonElement arguments, CancellationToken cancellationToken)
    {
        if (Action(arguments) != "install")
        {
            return InvocationPreflightResult.Lowered(OperationRisk.ReadOnly);
        }

        switch (_distribution.Channel)
        {
            case BaxyDistribution.Steam or BaxyDistribution.Itch:
                // Only the store's page opens: nothing is installed by BAXY.
                return InvocationPreflightResult.Lowered(OperationRisk.Reversible);
            case BaxyDistribution.GitHub:
                // No yes is asked for what cannot run: no newer version, or none that can be checked.
                (LatestRelease? latest, string? unread) = await LatestAsync(cancellationToken).ConfigureAwait(false);
                if (NotInstallable(latest, unread) is { } failure)
                {
                    return InvocationPreflightResult.Fails(failure);
                }

                // FIR1: nor for one the owner did not sign.
                (_, OperationOutcome? refused) = latest is null
                    ? (null, null)
                    : await SignedAsync(latest, Facts(), cancellationToken).ConfigureAwait(false);
                return refused is null ? InvocationPreflightResult.Proceed : InvocationPreflightResult.Fails(refused);
            default:
                return InvocationPreflightResult.Fails(Development());
        }
    }

    public async ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(invocation);
        return Action(invocation.Arguments) switch
        {
            "check" => await CheckAsync(cancellationToken).ConfigureAwait(false),
            "install" => await InstallAsync(cancellationToken).ConfigureAwait(false),
            _ => OperationOutcome.InvalidArguments(Definition, invocation.Arguments),
        };
    }

    private async Task<OperationOutcome> CheckAsync(CancellationToken cancellationToken)
    {
        JsonObject receipt = Facts();
        if (_distribution.Channel is BaxyDistribution.Steam or BaxyDistribution.Itch)
        {
            receipt["updatedBy"] = _distribution.Channel;
            receipt["storeUpdatesItself"] = true;
            receipt["authority"] = "baxy_distribution_store";
            return Success(receipt);
        }

        if (_distribution.Channel != BaxyDistribution.GitHub)
        {
            return Development();
        }

        (LatestRelease? latest, string? unread) = await LatestAsync(cancellationToken).ConfigureAwait(false);
        if (unread is not null)
        {
            return OperationOutcome.RetryableFailure(unread, Json(receipt));
        }

        receipt["checked"] = true;
        receipt["updatedBy"] = BaxyDistribution.GitHub;
        receipt["latest"] = latest?.Version.ToString(3);
        receipt["newer"] = latest is not null && latest.Version > _installed;
        if (latest is not null && latest.Version > _installed)
        {
            (ReleaseInstaller? signed, OperationOutcome? refused) = await SignedAsync(latest, receipt, cancellationToken)
                .ConfigureAwait(false);
            if (refused is not null)
            {
                return refused;
            }

            receipt["downloadBytes"] = signed?.Bytes;
        }

        receipt["releasePage"] = latest?.Page?.AbsoluteUri;
        receipt["authority"] = "github_releases_latest";
        return Success(receipt);
    }

    private async Task<OperationOutcome> InstallAsync(CancellationToken cancellationToken)
    {
        JsonObject receipt = Facts();
        switch (_distribution.Channel)
        {
            case BaxyDistribution.Steam:
                // Steam's library, as src/baxy_mind/data/app_places.v1.json already opens it: Steam shows there the update
                // it has for BAXY and installs it itself.
                return Opened(receipt, "steam://open/games", "steam_library");

            case BaxyDistribution.Itch:
                return _distribution.ItchPage() is { } page
                    ? Opened(receipt, page.AbsoluteUri, "itch_page")
                    : OperationOutcome.Failure("baxy_update_by_itch_app", Json(Store(receipt)));
            case BaxyDistribution.GitHub:
                break;
            default:
                return Development();
        }

        (LatestRelease? latest, string? unread) = await LatestAsync(cancellationToken).ConfigureAwait(false);
        if (NotInstallable(latest, unread) is { } failure)
        {
            return failure;
        }

        receipt["checked"] = true;
        if (latest is not { Installer: not null } || _dataRoot is not { } dataRoot)
        {
            return OperationOutcome.Failure("baxy_update_installer_missing", Json(receipt));
        }

        receipt["latest"] = latest.Version.ToString(3);
        (ReleaseInstaller? installer, OperationOutcome? refused) = await SignedAsync(latest, receipt, cancellationToken)
            .ConfigureAwait(false);
        if (installer is null)
        {
            return refused ?? NotSigned(receipt, "invalid");
        }

        string folder = UpdateInstallerFile.Folder(dataRoot);
        string? exe;

        // The App stops waiting for this answer (UpdatePanel.InstallTimeout) and then says it does not know whether the
        // installer opened: by then the download ended here, as done or as failed, and no installer starts after it.
        using CancellationTokenSource within = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        within.CancelAfter(_budget);
        try
        {
            exe = await DownloadAsync(
                installer, UpdateInstallerFile.Target(dataRoot, latest.Version.ToString(3)), within.Token).ConfigureAwait(false);
        }
        catch (Exception failed) when (failed is HttpRequestException or IOException or UnauthorizedAccessException
            or OperationCanceledException && !cancellationToken.IsCancellationRequested)
        {
            return OperationOutcome.RetryableFailure("baxy_update_download_failed", Json(receipt));
        }

        if (exe is null)
        {
            // What came is not what the owner signed: it is deleted and never run.
            return OperationOutcome.Failure("baxy_update_hash_mismatch", Json(receipt));
        }

        ProcessStartInfo start = new(exe)
        {
            UseShellExecute = false,
            // Not inside the folder being replaced: Windows does not move a folder that is a process's working one.
            WorkingDirectory = folder,
        };
        foreach (string argument in new[] { "--update", "--dir", _distribution.Root })
        {
            start.ArgumentList.Add(argument);
        }

        if (!_start(start))
        {
            return OperationOutcome.Failure("baxy_update_installer_not_started", Json(receipt));
        }

        receipt["installerSha256"] = installer.Sha256;
        receipt["installerStarted"] = true;
        receipt["appExitRequested"] = AskTheAppToExit();
        receipt["delivered"] = true;
        receipt["authority"] = "baxy_update_installer_started";
        return Success(receipt);
    }

    // Why GitHub's latest release cannot be installed now, or null when it can. Pure: preflight and the run both use it.
    private OperationOutcome? NotInstallable(LatestRelease? latest, string? unread)
    {
        JsonObject receipt = Facts();
        if (unread is not null)
        {
            return OperationOutcome.RetryableFailure(unread, Json(receipt));
        }

        receipt["checked"] = true;
        receipt["latest"] = latest?.Version.ToString(3);
        if (latest is null || latest.Version <= _installed)
        {
            receipt["newer"] = false;
            return OperationOutcome.Failure("baxy_update_already_latest", Json(receipt));
        }

        return latest.Installer is null || string.IsNullOrWhiteSpace(_dataRoot)
            ? OperationOutcome.Failure("baxy_update_installer_missing", Json(receipt))
            : null;
    }

    /// <summary>
    /// FIR1: the release's installer as the owner signed it, or why it is refused. release.json and release.json.sig are
    /// read whole into memory (a few hundred bytes, never more than <see cref="ReleaseSignature.ManifestLimit"/>); the
    /// signature must be one of the built-in keys over exactly those bytes, and what it signs must be this release's version
    /// (an old release.json, signed for real, under a newer tag is refused) and name its installer by size and SHA-256.
    /// «signature» in the receipt says which: missing, invalid or version.
    /// </summary>
    private async Task<(ReleaseInstaller? Installer, OperationOutcome? Refused)> SignedAsync(
        LatestRelease latest, JsonObject receipt, CancellationToken cancellationToken)
    {
        if (latest.Manifest is not { } manifestAsset || latest.Signature is not { } signatureAsset || latest.Installer is not { } listed)
        {
            return (null, NotSigned(receipt, "missing"));
        }

        byte[]? manifest;
        byte[]? signature;
        try
        {
            manifest = await SmallAsync(manifestAsset.Download, ReleaseSignature.ManifestLimit, cancellationToken).ConfigureAwait(false);
            signature = await SmallAsync(signatureAsset.Download, ReleaseSignature.SignatureLimit, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception failed) when (failed is HttpRequestException or IOException
            or OperationCanceledException && !cancellationToken.IsCancellationRequested)
        {
            return (null, OperationOutcome.RetryableFailure("baxy_update_unreachable", Json(receipt)));
        }

        if (manifest is null || signature is null || !ReleaseSignature.Verifies(manifest, signature, _keys))
        {
            return (null, NotSigned(receipt, manifest is null || signature is null ? "missing" : "invalid"));
        }

        if (SignedInstaller(manifest, listed.Download) is not { } signed)
        {
            return (null, NotSigned(receipt, "invalid"));
        }

        return signed.Version == latest.Version && signed.Version > _installed
            ? (signed.Installer, null)
            : (null, NotSigned(receipt, "version"));
    }

    private static OperationOutcome NotSigned(JsonObject receipt, string signature)
    {
        receipt["signature"] = signature;
        return OperationOutcome.Failure("baxy_update_not_signed", Json(receipt));
    }

    // What a signed release.json says of its version and its installer (scripts/build_github_release.py writes it).
    private static (Version Version, ReleaseInstaller Installer)? SignedInstaller(byte[] manifest, Uri download)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(manifest);
            JsonElement root = document.RootElement;
            return root.ValueKind == JsonValueKind.Object
                && root.TryGetProperty("version", out JsonElement version) && version.ValueKind == JsonValueKind.String
                && GitHubLatestRelease.ParseVersion(version.GetString()) is { } number
                && root.TryGetProperty("installer", out JsonElement installer) && installer.ValueKind == JsonValueKind.Object
                && installer.TryGetProperty("file", out JsonElement file) && file.ValueKind == JsonValueKind.String
                && file.GetString() == GitHubLatestRelease.InstallerName
                && installer.TryGetProperty("bytes", out JsonElement bytes) && bytes.TryGetInt64(out long size) && size > 0
                && installer.TryGetProperty("sha256", out JsonElement sha) && sha.ValueKind == JsonValueKind.String
                && sha.GetString() is { Length: 64 } hash && hash.All(char.IsAsciiHexDigitLower)
                    ? (number, new ReleaseInstaller(download, size, hash))
                    : null;
        }
        catch (JsonException)
        {
            return null;
        }
    }

    // A small file of the release, whole; null when it is longer than its limit.
    private async Task<byte[]?> SmallAsync(Uri address, int limit, CancellationToken cancellationToken)
    {
        using HttpRequestMessage request = new(HttpMethod.Get, address);
        request.Headers.UserAgent.ParseAdd(UserAgent);
        using HttpResponseMessage response = await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
            .ConfigureAwait(false);
        response.EnsureSuccessStatusCode();
        await using Stream body = await response.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false);
        using MemoryStream kept = new();
        byte[] buffer = new byte[4096];
        for (int read; (read = await body.ReadAsync(buffer, cancellationToken).ConfigureAwait(false)) > 0;)
        {
            if (kept.Length + read > limit)
            {
                return null;
            }

            kept.Write(buffer, 0, read);
        }

        return kept.ToArray();
    }

    // The installer goes to <data>\updates as a «.part», never more bytes of it than the owner signed (REV_APP COR-2), and
    // is kept only when what came has the signed size and SHA-256. Null when it does not.
    private async Task<string?> DownloadAsync(ReleaseInstaller installer, string target, CancellationToken cancellationToken)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(target)!);
        if (File.Exists(target) && await HashAsync(target, cancellationToken).ConfigureAwait(false) == installer.Sha256)
        {
            return target;
        }

        string partial = UpdateInstallerFile.Partial(target);
        bool fits = true;
        using (HttpRequestMessage request = new(HttpMethod.Get, installer.Download))
        {
            request.Headers.UserAgent.ParseAdd(UserAgent);
            using HttpResponseMessage response = await _http.SendAsync(
                request, HttpCompletionOption.ResponseHeadersRead, cancellationToken).ConfigureAwait(false);
            response.EnsureSuccessStatusCode();
            await using Stream body = await response.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false);
            await using FileStream file = new(partial, FileMode.Create, FileAccess.Write, FileShare.None, 1 << 16, useAsync: true);
            byte[] buffer = new byte[1 << 16];
            long written = 0;
            while (fits)
            {
                int read;
                using (CancellationTokenSource stalled = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken))
                {
                    stalled.CancelAfter(_stall);
                    read = await body.ReadAsync(buffer, stalled.Token).ConfigureAwait(false);
                }

                if (read == 0)
                {
                    break;
                }

                written += read;
                fits = written <= installer.Bytes;
                if (fits)
                {
                    await file.WriteAsync(buffer.AsMemory(0, read), cancellationToken).ConfigureAwait(false);
                }
            }
        }

        FileInfo downloaded = new(partial);
        if (!fits || downloaded.Length != installer.Bytes
            || await HashAsync(partial, cancellationToken).ConfigureAwait(false) != installer.Sha256)
        {
            File.Delete(partial);
            return null;
        }

        File.Move(partial, target, overwrite: true);
        return target;
    }

    private static async Task<string> HashAsync(string path, CancellationToken cancellationToken)
    {
        await using FileStream file = File.OpenRead(path);
        return Convert.ToHexStringLower(await SHA256.HashDataAsync(file, cancellationToken).ConfigureAwait(false));
    }

    private async Task<(LatestRelease? Latest, string? Unread)> LatestAsync(CancellationToken cancellationToken)
    {
        if (_distribution.Repository is not { } repository)
        {
            return (null, "baxy_update_source_unknown");
        }

        try
        {
            LatestRelease? latest = await GitHubLatestRelease.ReadAsync(_http, repository, UserAgent, cancellationToken)
                .ConfigureAwait(false);
            return latest is null ? (null, "baxy_update_unreachable") : (latest, null);
        }
        catch (Exception unreachable) when (unreachable is HttpRequestException or JsonException
            or TaskCanceledException && !cancellationToken.IsCancellationRequested)
        {
            return (null, "baxy_update_unreachable");
        }
    }

    private OperationOutcome Opened(JsonObject receipt, string address, string opened)
    {
        Store(receipt);
        if (!_start(new ProcessStartInfo(address) { UseShellExecute = true }))
        {
            return OperationOutcome.Failure("baxy_update_store_not_opened", Json(receipt));
        }

        receipt["opened"] = opened;
        receipt["delivered"] = true;
        receipt["authority"] = "baxy_update_store_opened";
        return Success(receipt);
    }

    private JsonObject Store(JsonObject receipt)
    {
        receipt["updatedBy"] = _distribution.Channel;
        receipt["storeUpdatesItself"] = true;
        return receipt;
    }

    private OperationOutcome Development() =>
        OperationOutcome.Failure("baxy_update_development_build", Json(Facts()));

    // MEN1-E (AMD2 §9, 2026-11-09: a development build failed before looking and the model said «No hay una versión más
    // reciente»): «checked» says whether this call read the latest version published. It starts false and only the
    // paths that read it turn it true, so a failure before reading (a development copy, GitHub unreachable, an unknown
    // source) and a store that updates BAXY itself never pass for «read, and there is none» (latest and newer beside a
    // true). The mind says it in the result's line of any tool (mind.NOT_CHECKED).
    private JsonObject Facts() => new()
    {
        ["version"] = 1,
        ["channel"] = _distribution.Channel,
        ["installed"] = _installed.ToString(3),
        ["checked"] = false,
    };

    // As baxy.exit asks: the App that listens closes after this call answers.
    private bool AskTheAppToExit()
    {
        try
        {
            if (!EventWaitHandle.TryOpenExisting(_exitEvent, out EventWaitHandle? exit))
            {
                return false;
            }

            using (exit)
            {
                return exit.Set();
            }
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    private static bool Start(ProcessStartInfo start)
    {
        try
        {
            using Process? started = Process.Start(start);
            return started is not null || start.UseShellExecute;
        }
        catch (Exception refused) when (refused is System.ComponentModel.Win32Exception or InvalidOperationException
            or FileNotFoundException)
        {
            return false;
        }
    }

    private static string? Action(JsonElement arguments) =>
        arguments.ValueKind == JsonValueKind.Object && arguments.TryGetProperty("action", out JsonElement action)
        && action.ValueKind == JsonValueKind.String
            ? action.GetString()
            : null;

    private static Version OwnVersion() =>
        GitHubLatestRelease.ParseVersion(Assembly.GetEntryAssembly()?
            .GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion)
        ?? new Version(0, 0, 0);

    private static JsonElement Json(JsonObject receipt)
    {
        using JsonDocument document = JsonDocument.Parse(receipt.ToJsonString());
        return document.RootElement.Clone();
    }

    private static OperationOutcome Success(JsonObject receipt) => OperationOutcome.Success(Json(receipt));
}
