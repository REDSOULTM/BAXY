using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Auditoría semántica 2026-09-20 (REOPEN1993, grupo G): «instala Photoshop»,
/// «instala Spotify», «desinstalá Discord» son pedidos al gestor de paquetes
/// de Windows, no consultas a la biblioteca de Steam. La preparación resuelve
/// un paquete exacto (por id o por nombre único en <c>winget search</c>) y lo
/// deja anotado; la confirmación instala con ese id y verifica en
/// <c>winget list</c>; la desinstalación quita el paquete instalado y verifica
/// su ausencia. Todo lo que winget no tiene se dice tal cual.
/// </summary>
internal sealed partial class WingetPackageAdapter : IExternalOperationAdapter
{
    private static readonly TimeSpan QueryTimeout = TimeSpan.FromSeconds(45);
    // winget instala en minutos; el core contesta en segundos. La instalación
    // se lanza, se le da este plazo por si termina enseguida (paquetes chicos)
    // y, si sigue, el recibo dice que empezó y con qué proceso.
    private static readonly TimeSpan QuickCompletionWait = TimeSpan.FromSeconds(12);

    private readonly IExternalProcessRunner _runner;
    private readonly string _preparedRoot;
    private readonly Func<IReadOnlyList<string>, int?> _launch;

    internal WingetPackageAdapter(string dataRoot)
        : this(new ExternalProcessRunner(), Path.Combine(dataRoot, "packages", "prepared"), null)
    {
    }

    internal WingetPackageAdapter(
        IExternalProcessRunner runner,
        string preparedRoot,
        Func<IReadOnlyList<string>, int?>? launch)
    {
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));
        _preparedRoot = preparedRoot ?? throw new ArgumentNullException(nameof(preparedRoot));
        _launch = launch ?? LaunchDetached;
    }

    public bool CanHandle(string operation) =>
        operation is "package.install.prepare" or "package.install.commit" or "package.uninstall";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        try
        {
            return operation switch
            {
                "package.install.prepare" => await PrepareAsync(operation, arguments, cancellationToken).ConfigureAwait(false),
                "package.install.commit" => await CommitAsync(operation, arguments, cancellationToken).ConfigureAwait(false),
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

    private async ValueTask<ExternalCapabilityReceipt> PrepareAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string requested = ExternalJson.RequiredString(arguments, "packageId").Trim();
        string? version = arguments.TryGetProperty("version", out JsonElement value)
            && value.ValueKind == JsonValueKind.String ? value.GetString() : null;

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
                return ExternalJson.FailureBeforeEffect(operation, "winget_package_not_resolved");
            if (named.Count > 1)
                return ExternalJson.FailureBeforeEffect(operation, "winget_package_ambiguous");
            resolved = named[0];
            resolvedBy = "winget_search_unique_name";
        }

        PackageRow package = resolved.Value;
        if (!string.IsNullOrWhiteSpace(version)
            && !string.Equals(version, package.Version, StringComparison.OrdinalIgnoreCase))
        {
            return ExternalJson.FailureBeforeEffect(operation, "winget_version_not_verified");
        }

        bool installed = await IsInstalledAsync(package.Id, cancellationToken).ConfigureAwait(false);
        string confirmationId = "winget_" + Convert.ToHexStringLower(SHA256.HashData(
            Encoding.UTF8.GetBytes(package.Id + "\n" + package.Version)))[..24];
        if (!installed)
        {
            Directory.CreateDirectory(_preparedRoot);
            string record = JsonSerializer.Serialize(new Dictionary<string, string>
            {
                ["confirmationId"] = confirmationId,
                ["packageId"] = package.Id,
                ["name"] = package.Name,
                ["version"] = package.Version,
                ["source"] = package.Source,
                ["preparedUtc"] = DateTimeOffset.UtcNow.ToString("O"),
            }, WingetJsonContext.Default.DictionaryStringString);
            await File.WriteAllTextAsync(
                Path.Combine(_preparedRoot, confirmationId + ".json"), record, cancellationToken)
                .ConfigureAwait(false);
        }

        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("requested", requested);
            if (!installed)
                writer.WriteString("confirmationId", confirmationId);
            writer.WriteString("packageId", package.Id);
            writer.WriteString("name", package.Name);
            writer.WriteString("resolvedVersion", package.Version);
            writer.WriteString("packageSource", package.Source);
            writer.WriteString("source", resolvedBy);
            writer.WriteBoolean("installed", installed);
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private async ValueTask<ExternalCapabilityReceipt> CommitAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string confirmationId = ExternalJson.RequiredString(arguments, "confirmationId").Trim();
        if (!Regex.IsMatch(confirmationId, "^winget_[0-9a-f]{24}$"))
            return ExternalJson.FailureBeforeEffect(operation, "winget_confirmation_not_prepared");
        string recordPath = Path.Combine(_preparedRoot, confirmationId + ".json");
        if (!File.Exists(recordPath))
            return ExternalJson.FailureBeforeEffect(operation, "winget_confirmation_not_prepared");
        Dictionary<string, string>? record = JsonSerializer.Deserialize(
            await File.ReadAllTextAsync(recordPath, cancellationToken).ConfigureAwait(false),
            WingetJsonContext.Default.DictionaryStringString);
        if (record is null || !record.TryGetValue("packageId", out string? packageId) || string.IsNullOrWhiteSpace(packageId))
            return ExternalJson.FailureBeforeEffect(operation, "winget_confirmation_not_prepared");
        string requestedVersion = record.GetValueOrDefault("version") ?? string.Empty;

        var effectBoundary = new ExternalEffectBoundary();
        effectBoundary.Cross(cancellationToken);
        int? processId = _launch([
            "install", "--id", packageId, "--exact", "--silent",
            "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity",
        ]);
        if (processId is null)
            return effectBoundary.Failure(operation, "winget_install_not_started");

        bool exited = await WaitForExitAsync(processId.Value, QuickCompletionWait, cancellationToken).ConfigureAwait(false);
        bool installed = exited && await IsInstalledAsync(packageId, cancellationToken).ConfigureAwait(false);
        if (exited && !installed)
            return effectBoundary.Failure(operation, "winget_install_not_verified", effectObserved: true);

        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("confirmationId", confirmationId);
            writer.WriteString("packageId", packageId);
            writer.WriteString("name", record.GetValueOrDefault("name") ?? packageId);
            writer.WriteString("requestedVersion", requestedVersion);
            writer.WriteBoolean("installed", installed);
            writer.WriteBoolean("installing", !installed);
            writer.WriteNumber("processId", processId.Value);
            writer.WriteString("authority", installed ? "winget_list_exact_postread" : "winget_install_process_running");
            writer.WriteEndObject();
        });
        File.Delete(recordPath);
        return ExternalJson.Success(operation, result, effectObserved: true);
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

        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("requested", requested);
            writer.WriteString("packageId", package.Id);
            writer.WriteString("name", package.Name);
            writer.WriteString("previousVersion", package.Version);
            writer.WriteBoolean("removed", !stillInstalled);
            writer.WriteBoolean("uninstalling", stillInstalled);
            writer.WriteNumber("processId", processId.Value);
            writer.WriteString("authority", stillInstalled ? "winget_uninstall_process_running" : "winget_list_exact_absence_postread");
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
        foreach (string rawLine in output.Split('\n'))
        {
            string line = rawLine.TrimEnd('\r');
            if (!body)
            {
                if (line.TrimStart().StartsWith("---", StringComparison.Ordinal))
                    body = true;
                continue;
            }

            if (string.IsNullOrWhiteSpace(line))
                continue;
            Match id = Regex.Match(line, @"(?<=\s)(?<id>[A-Za-z0-9][A-Za-z0-9.+_-]*\.[A-Za-z0-9.+_-]+|[0-9A-Z]{12,14}|ARP\\[^\s]+|MSIX\\[^\s]+)(?=\s|$)");
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

[System.Text.Json.Serialization.JsonSerializable(typeof(Dictionary<string, string>))]
internal sealed partial class WingetJsonContext : System.Text.Json.Serialization.JsonSerializerContext
{
}
