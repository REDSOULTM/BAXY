using System.Text.Json;

namespace Baxy.Providers.Windows.Windows;

/// <summary>
/// v3 r6 lectores (t2-r4 c04-5 «cierra configuración» pidió confirmación): the applications whose windows hold no
/// document of the person, read from data (src/baxy_mind/data/documentless_applications.v1.json, embedded). Closing
/// one of their windows loses nothing; everything else, and anything unknown, may hold work and keeps asking.
/// v3 r22 uso real (t4-c03 «ya cierra discord» pidió confirmación): the same data lists, under «accountBacked», the
/// applications whose content lives in the person's account (it comes back when they are opened again), and under
/// «neverWithoutAsking» the identities that never close without asking, whatever list or launch provenance says.
/// </summary>
public static class DocumentlessApplications
{
    private static readonly Lazy<Data> Loaded = new(Load);

    /// <summary>
    /// Whether an application identity (a catalog AppUserModelID, packaged or desktop) or an executable path names an
    /// application listed as holding no document of the person (documentless or account-backed) and not listed as
    /// never closing without asking. Null or empty identities match nothing.
    /// </summary>
    public static bool Contains(string? appUserModelId, string? executablePath) =>
        Matches(Loaded.Value.Listed, appUserModelId, executablePath)
        && !NeverWithoutAsking(appUserModelId, executablePath);

    /// <summary>
    /// Whether an identity is listed as never closing without asking (data: «neverWithoutAsking»): neither a list nor
    /// BAXY's launch provenance makes its close a low reversible act.
    /// </summary>
    public static bool NeverWithoutAsking(string? appUserModelId, string? executablePath) =>
        Matches(Loaded.Value.Never, appUserModelId, executablePath);

    private static bool Matches(Lists lists, string? appUserModelId, string? executablePath)
    {
        if (!string.IsNullOrWhiteSpace(appUserModelId))
        {
            string identity = appUserModelId.Trim();
            int bang = identity.IndexOf('!', StringComparison.Ordinal);
            if (bang > 0
                ? lists.PackageFamilies.Contains(identity[..bang])
                : lists.AppUserModelIds.Contains(identity))
            {
                return true;
            }
        }

        if (string.IsNullOrWhiteSpace(executablePath))
        {
            return false;
        }

        string fileName;
        try
        {
            fileName = Path.GetFileName(executablePath.Trim());
        }
        catch (ArgumentException)
        {
            return false;
        }

        return fileName.Length > 0 && lists.Executables.Contains(fileName);
    }

    private static Data Load()
    {
        using Stream stream = typeof(DocumentlessApplications).Assembly.GetManifestResourceStream(
                "Baxy.Providers.Windows.DocumentlessApplications.json")
            ?? throw new InvalidOperationException("documentless_applications_missing");
        using JsonDocument document = JsonDocument.Parse(stream);
        JsonElement root = document.RootElement;
        Lists listed = ReadLists(root);
        if (root.TryGetProperty("accountBacked", out JsonElement accountBacked)
            && accountBacked.ValueKind == JsonValueKind.Object)
        {
            Lists account = ReadLists(accountBacked);
            listed.PackageFamilies.UnionWith(account.PackageFamilies);
            listed.AppUserModelIds.UnionWith(account.AppUserModelIds);
            listed.Executables.UnionWith(account.Executables);
        }

        Lists never = root.TryGetProperty("neverWithoutAsking", out JsonElement neverElement)
            && neverElement.ValueKind == JsonValueKind.Object
                ? ReadLists(neverElement)
                : new Lists(new(StringComparer.OrdinalIgnoreCase), new(StringComparer.OrdinalIgnoreCase),
                    new(StringComparer.OrdinalIgnoreCase));
        return new Data(listed, never);
    }

    private static Lists ReadLists(JsonElement element) => new(
        Read(element, "packageFamilies"),
        Read(element, "appUserModelIds"),
        Read(element, "executables"));

    private static HashSet<string> Read(JsonElement root, string name)
    {
        var values = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        if (root.TryGetProperty(name, out JsonElement array) && array.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement item in array.EnumerateArray())
            {
                if (item.ValueKind == JsonValueKind.String && !string.IsNullOrWhiteSpace(item.GetString()))
                {
                    values.Add(item.GetString()!.Trim());
                }
            }
        }

        return values;
    }

    private sealed record Lists(
        HashSet<string> PackageFamilies,
        HashSet<string> AppUserModelIds,
        HashSet<string> Executables);

    private sealed record Data(Lists Listed, Lists Never);
}
