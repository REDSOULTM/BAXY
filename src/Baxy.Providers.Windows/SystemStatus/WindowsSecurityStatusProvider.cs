using System.Globalization;
using System.Text.Json;
using Baxy.Providers.Windows.External;

namespace Baxy.Providers.Windows.SystemStatus;

/// <summary>What a security read returned: its result, or the error code that says why there is none.</summary>
public sealed record SecurityStatusReading(JsonElement? Result, string? ErrorCode);

/// <summary>The firewall and Windows Update reads of system.status (scopes «firewall» and «updates»).</summary>
public interface ISecurityStatusProvider
{
    ValueTask<SecurityStatusReading> ReadAsync(string scope, CancellationToken cancellationToken);
}

/// <summary>
/// Auditoría de los pedidos reales (2026-10-17): «¿el firewall está prendido?», «¿hay actualizaciones de Windows
/// esperando?». Both are read without changing anything and without administrator rights, through Windows PowerShell
/// (the core is published AOT, so no late-bound COM there): the firewall as Windows applies it now (NetSecurity,
/// ActiveStore), with the network profiles connected now; Windows Update from the Update Agent's local cache (an
/// offline search: what the last Windows search found, with its date), whether a restart is pending, and the titles of
/// the first 10 updates waiting.
/// </summary>
public sealed class WindowsSecurityStatusProvider : ISecurityStatusProvider
{
    internal const int MaximumTitles = 10;

    internal const string FirewallScript = """
        $ErrorActionPreference = 'Stop'
        try {
          $profiles = @(Get-NetFirewallProfile -PolicyStore ActiveStore | ForEach-Object {
            [pscustomobject]@{ name = [string]$_.Name; enabled = ([string]$_.Enabled -eq 'True') } })
          $connected = @(Get-NetConnectionProfile -ErrorAction SilentlyContinue | ForEach-Object { [string]$_.NetworkCategory } |
            Select-Object -Unique)
          [pscustomobject]@{ ok = $true; profiles = $profiles; connected = $connected } | ConvertTo-Json -Compress -Depth 4
        } catch { [pscustomobject]@{ ok = $false } | ConvertTo-Json -Compress }
        """;

    internal const string UpdatesScript = """
        $ErrorActionPreference = 'Stop'
        try {
          $reboot = [bool](New-Object -ComObject Microsoft.Update.SystemInfo).RebootRequired
          $last = (New-Object -ComObject Microsoft.Update.AutoUpdate).Results.LastSearchSuccessDate
          $searcher = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()
          $searcher.Online = $false
          $found = $searcher.Search('IsInstalled=0 and IsHidden=0')
          $titles = @($found.Updates | Select-Object -First 10 | ForEach-Object { [string]$_.Title })
          $when = if ($last -is [datetime] -and $last.Year -gt 1601) { $last.ToString('o') } else { $null }
          [pscustomobject]@{ ok = $true; reboot = $reboot; pending = [int]$found.Updates.Count; titles = $titles;
            lastSearchUtc = $when } | ConvertTo-Json -Compress -Depth 3
        } catch { [pscustomobject]@{ ok = $false } | ConvertTo-Json -Compress }
        """;

    private readonly IExternalProcessRunner _runner;

    public WindowsSecurityStatusProvider()
        : this(new ExternalProcessRunner())
    {
    }

    internal WindowsSecurityStatusProvider(IExternalProcessRunner runner) =>
        _runner = runner ?? throw new ArgumentNullException(nameof(runner));

    public async ValueTask<SecurityStatusReading> ReadAsync(string scope, CancellationToken cancellationToken)
    {
        (string script, TimeSpan timeout, string failure) = scope switch
        {
            "firewall" => (FirewallScript, TimeSpan.FromSeconds(30), "firewall_status_not_read"),
            "updates" => (UpdatesScript, TimeSpan.FromSeconds(90), "update_status_not_read"),
            _ => throw new ArgumentOutOfRangeException(nameof(scope)),
        };
        ExternalProcessResult run;
        try
        {
            run = await _runner.RunPowerShellAsync(script, [], timeout, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException
            or System.ComponentModel.Win32Exception or TimeoutException)
        {
            return new(null, failure);
        }
        if (run.ExitCode != 0)
            return new(null, failure);
        try
        {
            using JsonDocument document = JsonDocument.Parse(run.Output.Trim());
            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object
                || !root.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True)
            {
                return new(null, failure);
            }
            JsonElement? result = scope == "firewall" ? Firewall(root) : Updates(root);
            return result is null ? new(null, failure) : new(result, null);
        }
        catch (JsonException)
        {
            return new(null, failure);
        }
    }

    private static JsonElement? Firewall(JsonElement root)
    {
        if (!root.TryGetProperty("profiles", out JsonElement profiles)
            || profiles.ValueKind is not (JsonValueKind.Array or JsonValueKind.Object))
        {
            return null;
        }
        var read = new List<(string Name, bool Enabled)>();
        // ConvertTo-Json writes a one-item array as the item itself.
        IEnumerable<JsonElement> listed = profiles.ValueKind == JsonValueKind.Array ? profiles.EnumerateArray() : [profiles];
        foreach (JsonElement profile in listed)
        {
            if (!profile.TryGetProperty("name", out JsonElement name) || name.ValueKind != JsonValueKind.String
                || !profile.TryGetProperty("enabled", out JsonElement enabled)
                || enabled.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
            {
                return null;
            }
            read.Add((name.GetString()!, enabled.GetBoolean()));
        }
        if (read.Count == 0)
            return null;
        string[] connected = Strings(root, "connected");
        return ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("scope", "firewall");
            writer.WriteStartArray("profiles");
            foreach ((string name, bool enabled) in read)
            {
                writer.WriteStartObject();
                writer.WriteString("name", name);
                writer.WriteBoolean("enabled", enabled);
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteBoolean("allEnabled", read.All(profile => profile.Enabled));
            writer.WriteStartArray("connectedProfiles");
            foreach (string category in connected)
                writer.WriteStringValue(category);
            writer.WriteEndArray();
            writer.WriteString("authority", "windows_netsecurity_activestore_read");
            writer.WriteEndObject();
        });
    }

    private static JsonElement? Updates(JsonElement root)
    {
        if (!root.TryGetProperty("reboot", out JsonElement reboot) || reboot.ValueKind is not (JsonValueKind.True or JsonValueKind.False)
            || !root.TryGetProperty("pending", out JsonElement pending) || !pending.TryGetInt32(out int count) || count < 0)
        {
            return null;
        }
        string[] titles = Strings(root, "titles").Take(MaximumTitles).ToArray();
        string? lastSearch = root.TryGetProperty("lastSearchUtc", out JsonElement when) && when.ValueKind == JsonValueKind.String
            && DateTimeOffset.TryParse(when.GetString(), CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out DateTimeOffset parsed)
                ? parsed.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ", CultureInfo.InvariantCulture)
                : null;
        return ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("scope", "updates");
            writer.WriteBoolean("rebootRequired", reboot.GetBoolean());
            writer.WriteNumber("pendingCount", count);
            writer.WriteNumber("shownCount", titles.Length);
            writer.WriteStartArray("titles");
            foreach (string title in titles)
                writer.WriteStringValue(title);
            writer.WriteEndArray();
            // What Windows found at its last search, read from its local cache: no new search is made.
            writer.WriteBoolean("searchedOnline", false);
            if (lastSearch is null) writer.WriteNull("lastSearchUtc");
            else writer.WriteString("lastSearchUtc", lastSearch);
            writer.WriteString("authority", "windows_update_agent_local_cache_read");
            writer.WriteEndObject();
        });
    }

    private static string[] Strings(JsonElement root, string name)
    {
        if (!root.TryGetProperty(name, out JsonElement value))
            return [];
        // ConvertTo-Json writes a one-item array as the item itself.
        IEnumerable<JsonElement> items = value.ValueKind == JsonValueKind.Array ? value.EnumerateArray() : [value];
        return items.Where(item => item.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(item.GetString()))
            .Select(item => item.GetString()!)
            .ToArray();
    }
}
