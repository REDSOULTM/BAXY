namespace Baxy.Providers.Windows;

internal static class AtomicFileReplacement
{
    private const int MaximumAttempts = 200;

    internal static void Replace(
        string sourcePath,
        string destinationPath,
        string? destinationBackupFileName = null,
        bool ignoreMetadataErrors = false)
    {
        for (int attempt = 1; ; attempt++)
        {
            try
            {
                File.Replace(
                    sourcePath,
                    destinationPath,
                    destinationBackupFileName,
                    ignoreMetadataErrors);
                return;
            }
            catch (IOException) when (attempt < MaximumAttempts)
            {
                Thread.Sleep(10);
            }
        }
    }
}
