using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Auditoría semántica 2026-09-20 (REOPEN1993, grupo G): «instala Photoshop»,
/// «instala Spotify», «desinstalá Discord» son pedidos al gestor de paquetes
/// de Windows, no consultas a la biblioteca de Steam. La instalación resuelve
/// un paquete exacto (por id o por nombre único en <c>winget search</c>), lo
/// instala con ese id y lo verifica en <c>winget list</c>; la desinstalación
/// quita el paquete instalado y verifica su ausencia. Todo lo que winget no
/// tiene se dice tal cual.
/// </summary>
internal sealed partial class WingetPackageAdapter : IExternalOperationAdapter
{
    private static readonly TimeSpan QueryTimeout = TimeSpan.FromSeconds(45);
    // winget instala en minutos; el core contesta en segundos. La instalación
    // se lanza, se le da este plazo por si termina enseguida (paquetes chicos)
    // y, si sigue, el recibo dice que empezó y con qué proceso.
    private static readonly TimeSpan QuickCompletionWait = TimeSpan.FromSeconds(12);
    // WINGET2083: how long the installed list may lag the installer's exit.
    private static readonly TimeSpan InstalledListSettleWait = TimeSpan.FromSeconds(20);
    private static readonly TimeSpan InstalledListPollInterval = TimeSpan.FromSeconds(2);

    private readonly IExternalProcessRunner _runner;
    private readonly Func<IReadOnlyList<string>, int?> _launch;

    internal WingetPackageAdapter()
        : this(new ExternalProcessRunner(), null)
    {
    }

    internal WingetPackageAdapter(
        IExternalProcessRunner runner,
        Func<IReadOnlyList<string>, int?>? launch)
    {
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));
        _launch = launch ?? LaunchDetached;
    }

    public bool CanHandle(string operation) => operation is "package.install" or "package.uninstall";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        try
        {
            return operation switch
            {
                "package.install" => await InstallAsync(operation, arguments, cancellationToken).ConfigureAwait(false),
                "package.uninstall" => await UninstallAsync(operation, arguments, cancellationToken).ConfigureAwait(false),
                _ => ExternalJson.Failure(operation, "external_operation_not_supported"),
            };
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "winget_argument_invalid");
        }
        catch (System.ComponentModel.Win32Exception)
        {
            return ExternalJson.Failure(operation, "winget_adapter_unavailable");
        }
        catch (TimeoutException)
        {
            return ExternalJson.Failure(operation, "winget_adapter_timeout");
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException or JsonException or InvalidOperationException)
        {
            return ExternalJson.Failure(operation, "winget_adapter_failed");
        }
    }

    // package.install (BAXY Renew 2026-10-15): one call resolves the exact package, installs it and verifies it in the
    // installed list; the kernel asks the person first (installation risk) with the packageId the model named. It
    // replaces the prepare/commit pair, which the 4B took for uninstalling (decision2, two cases). A name that is not
    // exactly one package fails before any effect with the packages winget gave, so the next call can name one by id.
    private async ValueTask<ExternalCapabilityReceipt> InstallAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string requested = ExternalJson.RequiredString(arguments, "packageId").Trim();
        string? version = arguments.TryGetProperty("version", out JsonElement value)
            && value.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(value.GetString())
            ? value.GetString()!.Trim() : null;

        // 1. El id exacto, si lo es.
        PackageRow? resolved = await ShowExactAsync(requested, version, cancellationToken).ConfigureAwait(false);
        string resolvedBy = "winget_exact_show";
        if (resolved is null)
        {
            // 2. Un nombre («Spotify», «VLC»): la búsqueda lo resuelve sólo si
            // exactamente un resultado se llama así o su id termina así.
            List<PackageRow> found = await SearchAsync(requested, cancellationToken).ConfigureAwait(false);
            List<PackageRow> named = found.Where(row => MatchesName(row, requested)).ToList();
            if (named.Count > 1)
            {
                // El origen oficial de winget va antes que la tienda cuando los dos
                // ofrecen el mismo nombre; dos del mismo origen siguen siendo ambiguos.
                List<PackageRow> official = named.Where(row => row.Source == "winget").ToList();
                if (official.Count == 1)
                    named = official;
            }

            if (named.Count == 0)
                return Candidates(operation, "winget_package_not_resolved", requested, found);
            if (named.Count > 1)
                return Candidates(operation, "winget_package_ambiguous", requested, named);
            resolved = named[0];
            resolvedBy = "winget_search_unique_name";
        }

        PackageRow package = resolved.Value;
        if (version is not null && !string.Equals(version, package.Version, StringComparison.OrdinalIgnoreCase))
            return ExternalJson.FailureBeforeEffect(operation, "winget_version_not_verified");

        if (await IsInstalledAsync(package.Id, cancellationToken).ConfigureAwait(false))
        {
            return ExternalJson.Success(operation, Receipt(requested, package, resolvedBy, processId: null),
                effectObserved: false);
        }

        var effectBoundary = new ExternalEffectBoundary();
        effectBoundary.Cross(cancellationToken);
        List<string> install =
        [
            "install", "--id", package.Id, "--exact", "--silent",
            "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity",
        ];
        if (version is not null)
            install.AddRange(["--version", version]);
        int? processId = _launch(install);
        if (processId is null)
            return effectBoundary.Failure(operation, "winget_install_not_started");

        bool exited = await WaitForExitAsync(processId.Value, QuickCompletionWait, cancellationToken).ConfigureAwait(false);
        // WINGET2083 «instala 7-Zip»: the installer exits before the package
        // appears in winget's installed list, and a single read right after it
        // said «not installed» about a package that was in fact installed.
        // The list is read again for a few seconds before answering.
        bool installed = exited && await IsInstalledSoonAsync(package.Id, cancellationToken).ConfigureAwait(false);
        if (exited && !installed)
            return effectBoundary.Failure(operation, "winget_install_not_verified", effectObserved: true);
        // An installer still running is a started install, not a verified one (BAXY Renew audit 2026-10-15: it was a
        // success with installing:true).
        if (!installed)
            return effectBoundary.Failure(operation, "winget_install_still_running", effectObserved: true);

        return ExternalJson.Success(operation, Receipt(requested, package, resolvedBy, processId.Value),
            effectObserved: true);
    }

    // «alreadyInstalled» true: it was in the installed list before anything ran, and nothing was installed.
    private static JsonElement Receipt(string requested, PackageRow package, string resolvedBy, int? processId) =>
        ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("requested", requested);
            writer.WriteString("packageId", package.Id);
            writer.WriteString("name", package.Name);
            writer.WriteString("packageVersion", package.Version);
            writer.WriteString("packageSource", package.Source);
            writer.WriteString("resolvedBy", resolvedBy);
            writer.WriteBoolean("installed", true);
            writer.WriteBoolean("alreadyInstalled", processId is null);
            if (processId is not null)
                writer.WriteNumber("processId", processId.Value);
            writer.WriteString("authority", "winget_list_exact_postread");
            writer.WriteEndObject();
        });

    // The packages winget gave for the name, as it gave them (at most 8), so the next call can name one by its id.
    private static ExternalCapabilityReceipt Candidates(
        string operation,
        string errorCode,
        string requested,
        IReadOnlyList<PackageRow> rows) =>
        new(operation, false, false, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("requested", requested);
            writer.WriteStartArray("candidates");
            foreach (PackageRow row in rows.Take(8))
            {
                writer.WriteStartObject();
                writer.WriteString("name", row.Name);
                writer.WriteString("packageId", row.Id);
                writer.WriteString("packageVersion", row.Version);
                writer.WriteString("packageSource", row.Source);
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteEndObject();
        }), errorCode);

    private async ValueTask<bool> IsInstalledSoonAsync(string packageId, CancellationToken cancellationToken)
    {
        DateTimeOffset deadline = DateTimeOffset.UtcNow + InstalledListSettleWait;
        while (true)
        {
            if (await IsInstalledAsync(packageId, cancellationToken).ConfigureAwait(false))
            {
                return true;
            }

            if (DateTimeOffset.UtcNow >= deadline)
            {
                return false;
            }

            await Task.Delay(InstalledListPollInterval, cancellationToken).ConfigureAwait(false);
        }
    }

    private async ValueTask<ExternalCapabilityReceipt> UninstallAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string requested = ExternalJson.RequiredString(arguments, "packageId").Trim();
        List<PackageRow> installed = await ListAsync(requested, cancellationToken).ConfigureAwait(false);
        List<PackageRow> named = installed.Where(row => MatchesName(row, requested)).ToList();
        if (named.Count == 0)
            return ExternalJson.FailureBeforeEffect(operation, "winget_package_not_installed");
        if (named.Count > 1)
            return ExternalJson.FailureBeforeEffect(operation, "winget_package_ambiguous");
        PackageRow package = named[0];

        var effectBoundary = new ExternalEffectBoundary();
        effectBoundary.Cross(cancellationToken);
        int? processId = _launch([
            "uninstall", "--id", package.Id, "--exact", "--silent",
            "--accept-source-agreements", "--disable-interactivity",
        ]);
        if (processId is null)
            return effectBoundary.Failure(operation, "winget_uninstall_not_started");

        bool exited = await WaitForExitAsync(processId.Value, QuickCompletionWait, cancellationToken).ConfigureAwait(false);
        bool stillInstalled = await IsInstalledAsync(package.Id, cancellationToken).ConfigureAwait(false);
        if (exited && stillInstalled)
            return effectBoundary.Failure(operation, "winget_uninstall_not_verified", effectObserved: true);
        if (stillInstalled)
            return effectBoundary.Failure(operation, "winget_uninstall_still_running", effectObserved: true);

        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("requested", requested);
            writer.WriteString("packageId", package.Id);
            writer.WriteString("name", package.Name);
            writer.WriteString("previousVersion", package.Version);
            writer.WriteBoolean("removed", true);
            writer.WriteNumber("processId", processId.Value);
            writer.WriteString("authority", "winget_list_exact_absence_postread");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: true);
    }

    private async Task<PackageRow?> ShowExactAsync(string packageId, string? version, CancellationToken cancellationToken)
    {
        if (!Regex.IsMatch(packageId, @"^[A-Za-z0-9][A-Za-z0-9.+_-]*\.[A-Za-z0-9.+_-]+$|^[0-9A-Z]{12,14}$"))
            return null;
        var args = new List<string> { "show", "--id", packageId, "--exact", "--disable-interactivity", "--accept-source-agreements" };
        if (!string.IsNullOrWhiteSpace(version))
        {
            args.Add("--version");
            args.Add(version);
        }

        ExternalProcessResult process = await _runner.RunAsync("winget.exe", args, QueryTimeout, cancellationToken)
            .ConfigureAwait(false);
        if (process.ExitCode != 0)
            return null;
        Match identity = Regex.Match(process.Output, @"\[([^\]\s]+)\]");
        Match observedVersion = Regex.Match(process.Output, @"(?im)^(?:Versi[oó]n|Version):\s*(\S+)");
        Match name = Regex.Match(process.Output, @"(?im)^(?:Encontrado|Found)\s+(.+?)\s+\[");
        if (!identity.Success || !string.Equals(identity.Groups[1].Value, packageId, StringComparison.OrdinalIgnoreCase)
            || !observedVersion.Success)
        {
            return null;
        }

        return new PackageRow(
            name.Success ? name.Groups[1].Value.Trim() : packageId,
            identity.Groups[1].Value,
            observedVersion.Groups[1].Value.Trim(),
            "winget");
    }

    private async Task<List<PackageRow>> SearchAsync(string query, CancellationToken cancellationToken)
    {
        ExternalProcessResult process = await _runner.RunAsync(
            "winget.exe",
            ["search", query, "--disable-interactivity", "--accept-source-agreements"],
            QueryTimeout, cancellationToken).ConfigureAwait(false);
        return process.ExitCode == 0 ? ParseTable(process.Output) : [];
    }

    private async Task<List<PackageRow>> ListAsync(string query, CancellationToken cancellationToken)
    {
        ExternalProcessResult process = await _runner.RunAsync(
            "winget.exe",
            ["list", query, "--disable-interactivity", "--accept-source-agreements"],
            QueryTimeout, cancellationToken).ConfigureAwait(false);
        return process.ExitCode == 0 ? ParseTable(process.Output) : [];
    }

    private async Task<bool> IsInstalledAsync(string packageId, CancellationToken cancellationToken)
    {
        ExternalProcessResult process = await _runner.RunAsync(
            "winget.exe",
            ["list", "--id", packageId, "--exact", "--disable-interactivity", "--accept-source-agreements"],
            QueryTimeout, cancellationToken).ConfigureAwait(false);
        return process.ExitCode == 0
            && ParseTable(process.Output).Any(row => string.Equals(row.Id, packageId, StringComparison.OrdinalIgnoreCase));
    }

    internal static bool MatchesName(PackageRow row, string requested)
    {
        string wanted = Fold(requested);
        if (wanted.Length == 0)
            return false;
        if (Fold(row.Name) == wanted || Fold(row.Id) == wanted)
            return true;
        // «Spotify.Spotify», «Aleab.Toastify»: el nombre tras el editor. Un id
        // de tres segmentos («JinweiZhiguang.Lanhu.Photoshop») no nombra al
        // paquete por su última palabra.
        string[] segments = row.Id.Split('.');
        return segments.Length == 2 && Fold(segments[1]) == wanted;
    }

    private static string Fold(string text) =>
        Regex.Replace(text.Normalize(NormalizationForm.FormD), @"\p{Mn}+|[\s._-]+", string.Empty).ToLowerInvariant();

    // winget escribe una tabla alineada: nombre, id, versión, (disponible),
    // (coincidencia) y origen. El id es el token que un nombre no puede ser.
    internal static List<PackageRow> ParseTable(string output)
    {
        var rows = new List<PackageRow>();
        bool body = false;
        string header = string.Empty;
        int idColumn = -1;
        foreach (string rawLine in output.Split('\n'))
        {
            string line = rawLine.TrimEnd('\r');
            if (!body)
            {
                if (line.TrimStart().StartsWith("---", StringComparison.Ordinal))
                {
                    body = true;
                    // WINGET2085: the table is aligned under its header; the Id
                    // column starts where the header's «Id» does.
                    Match idHeader = Regex.Match(header, @"(?<=\s)Id(?=\s)");
                    idColumn = idHeader.Success ? idHeader.Index : -1;
                }
                else if (!string.IsNullOrWhiteSpace(line))
                {
                    header = line;
                }

                continue;
            }

            if (string.IsNullOrWhiteSpace(line))
                continue;
            // WINGET2085 «instala 7-Zip»: in «7-Zip 26.03 (x64 edition) 7zip.7zip
            // 26.03.00.0 winget» the version inside the display name matched the
            // dotted-id pattern first, the row read as id «26.03», and an
            // installed 7-Zip was reported absent. The id is searched from the
            // header's Id column on; the whole line is the fallback.
            int idIndex = idColumn > 0 ? IndexAtColumn(line, idColumn) : -1;
            Match id = idIndex > 0 && idIndex < line.Length
                ? IdToken.Match(line, idIndex)
                : Match.Empty;
            if (!id.Success)
                id = IdToken.Match(line);
            if (!id.Success)
                continue;
            string name = line[..id.Index].Trim();
            string[] rest = line[(id.Index + id.Length)..].Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (name.Length == 0 || rest.Length == 0)
                continue;
            string source = rest[^1] is "winget" or "msstore" ? rest[^1] : string.Empty;
            rows.Add(new PackageRow(name, id.Groups["id"].Value, rest[0], source));
        }

        return rows;
    }

    // winget aligns its table by display columns, and an East Asian wide character takes two («蓝湖» in a name moved
    // the Id column two characters left, and the version was read as the id). The index of the character at a column.
    private static int IndexAtColumn(string line, int column)
    {
        int width = 0;
        for (int index = 0; index < line.Length; index++)
        {
            if (width >= column)
                return index;
            width += IsWide(line[index]) ? 2 : 1;
        }

        return line.Length;
    }

    private static bool IsWide(char character) => character is
        >= '\u1100' and <= '\u115F' or >= '\u2E80' and <= '\uA4CF' or >= '\uAC00' and <= '\uD7A3'
        or >= '\uF900' and <= '\uFAFF' or >= '\uFE30' and <= '\uFE4F' or >= '\uFF00' and <= '\uFF60'
        or >= '\uFFE0' and <= '\uFFE6';

    private static readonly Regex IdToken = new(
        @"(?<=\s)(?<id>[A-Za-z0-9][A-Za-z0-9.+_-]*\.[A-Za-z0-9.+_-]+|[0-9A-Z]{12,14}|ARP\\[^\s]+|MSIX\\[^\s]+)(?=\s|$)",
        RegexOptions.CultureInvariant);

    private static int? LaunchDetached(IReadOnlyList<string> arguments)
    {
        var start = new ProcessStartInfo("winget.exe")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        foreach (string argument in arguments)
            start.ArgumentList.Add(argument);
        Process? process = Process.Start(start);
        if (process is null)
            return null;
        // Las salidas se drenan para que winget no se bloquee en un tubo lleno.
        _ = process.StandardOutput.ReadToEndAsync();
        _ = process.StandardError.ReadToEndAsync();
        return process.Id;
    }

    private static async Task<bool> WaitForExitAsync(int processId, TimeSpan budget, CancellationToken cancellationToken)
    {
        DateTime deadline = DateTime.UtcNow + budget;
        while (DateTime.UtcNow < deadline)
        {
            cancellationToken.ThrowIfCancellationRequested();
            try
            {
                using Process process = Process.GetProcessById(processId);
                if (process.HasExited)
                    return true;
            }
            catch (ArgumentException)
            {
                return true;
            }
            catch (InvalidOperationException)
            {
                return true;
            }

            await Task.Delay(500, cancellationToken).ConfigureAwait(false);
        }

        return false;
    }

    internal readonly record struct PackageRow(string Name, string Id, string Version, string Source);
}
