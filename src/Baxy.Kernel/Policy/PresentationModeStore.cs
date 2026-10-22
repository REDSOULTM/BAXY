namespace Baxy.Kernel.Policy;

/// <summary>
/// El modo accesible de la interfaz vive en un fichero del perfil, como el de
/// confirmación: lo escriben la interfaz propia y la operación del chat, y lo
/// lee la App para presentar. Sólo cambia cómo se presenta, nunca lo que se
/// puede hacer (identidad, «Accesibilidad — central en el motor, modo en la interfaz»).
/// </summary>
public static class PresentationModeStore
{
    public const string FileName = "presentation-mode";
    public const string Accessible = "accessible";
    public const string Normal = "normal";

    public static bool ReadAccessible(string? dataRoot) => TryReadAccessible(dataRoot, out bool accessible) && accessible;

    /// <summary>
    /// Revisión 2026-10-22 (C-3): whether the file could be read at all (one another program holds locked cannot), so a
    /// switch never takes «unreadable» for «off»; <paramref name="accessible"/> is what it says when it could.
    /// </summary>
    public static bool TryReadAccessible(string? dataRoot, out bool accessible)
    {
        accessible = false;
        if (string.IsNullOrWhiteSpace(dataRoot))
        {
            return true;
        }

        try
        {
            string path = Path.Combine(dataRoot, FileName);
            accessible = File.Exists(path)
                && string.Equals(File.ReadAllText(path).Trim(), Accessible, StringComparison.Ordinal);
            return true;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return false;
        }
    }

    public static void WriteAccessible(string dataRoot, bool accessible)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(dataRoot);
        Directory.CreateDirectory(dataRoot);
        File.WriteAllText(Path.Combine(dataRoot, FileName), accessible ? Accessible : Normal);
    }
}
