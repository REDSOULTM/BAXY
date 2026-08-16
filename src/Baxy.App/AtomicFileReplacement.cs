using System.IO;

namespace Baxy.App;

internal static class AtomicFileReplacement
{
    private const int MaximumAttempts = 200;

    internal static void Replace(string sourcePath, string destinationPath)
    {
        for (int attempt = 1; ; attempt++)
        {
            try
            {
                File.Replace(
                    sourcePath,
                    destinationPath,
                    destinationBackupFileName: null);
                return;
            }
            catch (IOException) when (attempt < MaximumAttempts)
            {
                Thread.Sleep(10);
            }
        }
    }
}
