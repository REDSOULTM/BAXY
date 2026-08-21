namespace Baxy.Kernel.Policy;

/// <summary>
/// El ajuste de confirmación vive en un fichero del data root y, si falta,
/// en <c>BAXY_CONFIRMATION_MODE</c>. El motor lo relee en cada invocación
/// para que bypass quede encendido hasta que se apague, sin un segundo camino.
/// </summary>
public static class ConfirmationModeStore
{
    public const string FileName = "confirmation-mode";
    public const string EnvironmentVariable = "BAXY_CONFIRMATION_MODE";

    public static ConfirmationMode Read(string? dataRoot = null)
    {
        if (!string.IsNullOrWhiteSpace(dataRoot))
        {
            try
            {
                string path = Path.Combine(dataRoot, FileName);
                if (File.Exists(path))
                {
                    ConfirmationMode? fromFile = Parse(File.ReadAllText(path));
                    if (fromFile is { } mode)
                    {
                        return mode;
                    }
                }
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
            }
        }

        return Parse(Environment.GetEnvironmentVariable(EnvironmentVariable))
            ?? ConfirmationMode.Normal;
    }

    public static void Write(string dataRoot, ConfirmationMode mode)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(dataRoot);
        Directory.CreateDirectory(dataRoot);
        File.WriteAllText(
            Path.Combine(dataRoot, FileName),
            mode == ConfirmationMode.Bypass ? "bypass" : "normal");
    }

    public static ConfirmationMode? Parse(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        string trimmed = value.Trim();
        if (trimmed.Equals("bypass", StringComparison.OrdinalIgnoreCase)
            || trimmed.Equals("all", StringComparison.OrdinalIgnoreCase))
        {
            return ConfirmationMode.Bypass;
        }

        if (trimmed.Equals("normal", StringComparison.OrdinalIgnoreCase)
            || trimmed.Equals("confirm_risky", StringComparison.OrdinalIgnoreCase)
            || trimmed.Equals("risk-aware", StringComparison.OrdinalIgnoreCase))
        {
            return ConfirmationMode.Normal;
        }

        return null;
    }
}
