using System.Globalization;

namespace Baxy.Providers.Windows.Infrastructure;

/// <summary>
/// Holdout v4 (falsedad): «69 % de CPU» was said where the reading was 0.69 %; a bare 0.69 beside «percent» reads as a
/// fraction, and a size in bytes is converted by the model, sometimes wrongly. A reading's percentage and size also go
/// written with their unit, as a person reads them in Spanish: a decimal comma, «%» after a space, and sizes in KB, MB,
/// GB or TB of 1024 as Windows shows them («31,7 GB»). The numbers stay beside them, unchanged.
/// </summary>
public static class ReadingUnits
{
    private static readonly NumberFormatInfo Spanish = new()
    {
        NumberDecimalSeparator = ",",
        NumberGroupSeparator = ".",
        NegativeSign = "-",
    };

    private static readonly string[] SizeUnits = ["bytes", "KB", "MB", "GB", "TB"];

    /// <summary>A percentage already on the 0-100 scale: «0,69 %», «85 %»; one above zero that rounds to it, «menos de
    /// 0,01 %».</summary>
    public static string Percent(double percent)
    {
        double rounded = Math.Round(percent, 2, MidpointRounding.AwayFromZero);
        return rounded == 0 && percent > 0
            ? "menos de 0,01 %"
            : rounded.ToString("0.##", Spanish) + " %";
    }

    public static string? Percent(double? percent) => percent is { } value ? Percent(value) : null;

    /// <summary>A size in bytes in the largest unit of 1024 it reaches: «512 bytes», «1,5 KB», «31,7 GB».</summary>
    public static string Size(double bytes)
    {
        int unit = 0;
        double value = Math.Max(0, bytes);
        while (value >= 1024 && unit < SizeUnits.Length - 1)
        {
            value /= 1024;
            unit++;
        }

        return (unit == 0 ? value.ToString("0", Spanish) : value.ToString("0.#", Spanish)) + " " + SizeUnits[unit];
    }

    public static string? Size(double? bytes) => bytes is { } value ? Size(value) : null;

    /// <summary>The share of <paramref name="part"/> in <paramref name="whole"/> as a percentage, or null for no
    /// whole.</summary>
    public static string? Share(double part, double whole) => whole > 0 ? Percent(100d * part / whole) : null;
}
