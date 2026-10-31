using System.Text.Json;
using Baxy.Contracts;
using Baxy.Providers.Windows.Applications;

namespace Baxy.Core;

/// <summary>
/// Ajuste c3 (humos del 31-10): the installed applications of the last verified read, kept in the core's private data
/// folder, so a start whose read is late (a cold start after signing in) still shows the model the list. Only a list the
/// contract takes is kept or read back; anything else is no list.
/// </summary>
internal sealed class KeptApplicationCatalog(string path)
{
    internal const string FileName = "application-catalog.v1.json";

    internal InstalledApplicationCatalogSnapshot? Load()
    {
        try
        {
            ApplicationCatalogSnapshot? kept = JsonSerializer.Deserialize(
                File.ReadAllBytes(path), BaxyJsonContext.Default.ApplicationCatalogSnapshot);
            if (kept is not { Verified: true })
            {
                return null;
            }

            ContractValidator.Validate(kept);
            return new InstalledApplicationCatalogSnapshot(true, kept.Complete, [.. kept.Names]);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
        {
            return null;
        }
    }

    internal void Keep(InstalledApplicationCatalogSnapshot read)
    {
        if (!read.Verified)
        {
            return;
        }

        var snapshot = new ApplicationCatalogSnapshot(
            ApplicationCatalogContract.CurrentVersion, true, read.Complete, [.. read.Names]);
        string temporary = path + ".tmp";
        try
        {
            ContractValidator.Validate(snapshot);
            File.WriteAllBytes(temporary, JsonSerializer.SerializeToUtf8Bytes(
                snapshot, BaxyJsonContext.Default.ApplicationCatalogSnapshot));
            File.Move(temporary, path, overwrite: true);
        }
        // Not kept is only a slower next start: the list this start read still goes to the App.
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException)
        {
            try
            {
                File.Delete(temporary);
            }
            catch (Exception cleanup) when (cleanup is IOException or UnauthorizedAccessException)
            {
                // A temporary file left behind is overwritten by the next keep; the kept list itself is untouched.
            }
        }
    }
}
