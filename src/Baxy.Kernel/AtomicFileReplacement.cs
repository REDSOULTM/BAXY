namespace Baxy.Kernel;

public static class AtomicFileReplacement
{
    private const int MaximumAttempts = 200;

    public static void Replace(
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

    // C13 (agent-desktop probes/windows/FINDINGS.md:151, measured on 17763; the same here on 10.0.26300, C: and F:, NTFS):
    // File.Move with overwrite over a destination someone holds open answered access denied in 12 of 12 access and sharing
    // modes, so an indexer, an antivirus or a backup reading the file made a save fail. File.Replace passed in the 6 that
    // share deletion, the holder going on reading what it opened, and answered sharing violation in the other 6, which
    // pass when the holder closes: the retry above. It cannot make a missing destination, and a moved file can.
    /// <summary>Puts a closed temporary file in the destination's place, whether or not the destination exists.</summary>
    public static void ReplaceOrCreate(string sourcePath, string destinationPath)
    {
        for (int attempt = 1; ; attempt++)
        {
            try
            {
                if (File.Exists(destinationPath))
                    File.Replace(sourcePath, destinationPath, destinationBackupFileName: null, ignoreMetadataErrors: true);
                else
                    File.Move(sourcePath, destinationPath, overwrite: false);
                return;
            }
            catch (IOException) when (attempt < MaximumAttempts)
            {
                Thread.Sleep(10);
            }
        }
    }
}
