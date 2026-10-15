using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Encargo CS (banco fz1 s14: Discord cold after a restart went through its updater and the recipient's resolution gave
/// up at 20.6 s): how long a messaging client's main window may take to show after it is opened cold, per application
/// (data client_cold_start.v1.json), and the measured default of D59 §1 for any other.
/// </summary>
internal static class ClientColdStart
{
    private static readonly Lazy<(TimeSpan Default, Dictionary<string, TimeSpan> Applications)> Data = new(Load);

    /// <summary>The cold-start clock of the application <paramref name="application"/> opens.</summary>
    internal static TimeSpan For(string application) =>
        Data.Value.Applications.TryGetValue(application, out TimeSpan listed) ? listed : Data.Value.Default;

    private static (TimeSpan, Dictionary<string, TimeSpan>) Load()
    {
        using Stream stream = typeof(ClientColdStart).Assembly.GetManifestResourceStream(
                "Baxy.Providers.Windows.ClientColdStart.json")
            ?? throw new InvalidOperationException("client_cold_start_missing");
        using JsonDocument document = JsonDocument.Parse(stream);
        JsonElement root = document.RootElement;
        var applications = new Dictionary<string, TimeSpan>(StringComparer.OrdinalIgnoreCase);
        foreach (JsonProperty application in root.GetProperty("applications").EnumerateObject())
        {
            applications[application.Name] = TimeSpan.FromSeconds(application.Value.GetDouble());
        }

        return (TimeSpan.FromSeconds(root.GetProperty("defaultSeconds").GetDouble()), applications);
    }
}
