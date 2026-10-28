using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// La región de casa que la persona fijó en Windows (Configuración › Hora e idioma › Región), como código ISO 3166 de
/// dos letras. No es la región del formato de fechas ni la del idioma, que pueden ser de otro país: es dónde vive.
/// </summary>
internal static partial class HomeRegion
{
    // Null when Windows has no country set (it answers «001», the world) or the call fails.
    internal static unsafe string? Read()
    {
        const int capacity = 16;
        char* name = stackalloc char[capacity];
        int written = GetUserDefaultGeoName(name, capacity);
        if (written != 3) return null;
        string code = new(name, 0, 2);
        return code.All(char.IsAsciiLetterUpper) ? code : null;
    }

    [LibraryImport("kernel32.dll")]
    private static unsafe partial int GetUserDefaultGeoName(char* geoName, int geoNameCount);
}
