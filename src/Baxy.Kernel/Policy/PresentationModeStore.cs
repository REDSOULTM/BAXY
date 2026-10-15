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

    public static bool ReadAccessible(string? dataRoot)
    {
        if (string.IsNullOrWhiteSpace(dataRoot))
        {
            return false;
        }

        try
        {
            string path = Path.Combine(dataRoot, FileName);
            return File.Exists(path)
                && string.Equals(File.ReadAllText(path).Trim(), Accessible, StringComparison.Ordinal);
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
