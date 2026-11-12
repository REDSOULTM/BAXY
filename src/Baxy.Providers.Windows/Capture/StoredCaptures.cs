namespace Baxy.Providers.Windows.Capture;

/// <summary>
/// PRV1 (revisión de privacidad 2026-11-09, PRIV-02): the private capture folder held up to 16 whole screens, in clear
/// bitmaps, for as long as BAXY was installed: nothing removed them when BAXY closed, nor when the person deleted every
/// conversation or had BAXY forget everything, and no text of the product said they were there. A capture is read by
/// the calls that follow it in the same request (OCR, vision) and by nothing later: it goes when that request ends, when
/// BAXY closes, when the engine starts (what a run that was killed left) and when the person deletes everything.
/// </summary>
public static class StoredCaptures
{
    /// <summary>
    /// The notes of the playbacks that were not verified, which the browser's adapter keeps in this folder where the
    /// PC's owner asked for words to be kept: each names what the person asked to play and the last page seen.
    /// </summary>
    public const string PlaybackNotes = "streaming-playback-rejections.jsonl";

    /// <summary>
    /// Removes every stored capture of the folder, and the temporaries of captures that were being written. How many
    /// could not be removed (held open by a reader this moment): they go with the next clearing. A folder that is not
    /// there holds none.
    /// </summary>
    public static int Clear(string directory) => Remove(directory, "capture_*.bmp", ".capture_*.tmp");

    /// <summary>
    /// The person deletes everything: the captures go (<see cref="Clear"/>) and so do the <see cref="PlaybackNotes"/>,
    /// which name what they asked for (revisión a ciegas de PRV1: they stayed).
    /// </summary>
    public static int ClearAll(string directory) => Remove(directory, "capture_*.bmp", ".capture_*.tmp", PlaybackNotes);

    private static int Remove(string directory, params string[] patterns)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(directory);
        FileInfo[] files;
        try
        {
            var folder = new DirectoryInfo(directory);
            if (!folder.Exists)
            {
                return 0;
            }

            files = [.. patterns.SelectMany(folder.GetFiles)];
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return 0;
        }

        int left = 0;
        foreach (FileInfo file in files)
        {
            try
            {
                file.Delete();
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                left++;
            }
        }

        return left;
    }
}
