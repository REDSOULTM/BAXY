using System.IO;

namespace Baxy.App;

internal static class TextToSpeechPreferenceStore
{
    internal const string FileName = "tts-muted";

    internal static bool Read(string dataRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(dataRoot);
        try
        {
            string path = Path.Combine(dataRoot, FileName);
            return File.Exists(path)
                && bool.TryParse(File.ReadAllText(path).Trim(), out bool muted)
                && muted;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return false;
        }
    }

    internal static void Write(string dataRoot, bool muted)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(dataRoot);
        Directory.CreateDirectory(dataRoot);
        File.WriteAllText(Path.Combine(dataRoot, FileName), muted ? "true" : "false");
    }
}
