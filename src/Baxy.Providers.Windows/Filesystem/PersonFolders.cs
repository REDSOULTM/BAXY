using System.Globalization;
using System.Text;

namespace Baxy.Providers.Windows.Filesystem;

/// <summary>
/// The person's known folders: where Windows keeps each one (a moved or redirected Desktop, Documents or Downloads
/// included), and the names a person gives them, in Spanish and English, folded (lower case, no accents). The file
/// tools' <c>folder</c> argument takes the labels; the App reads the same names in the person's words
/// (Baxy.App.SaidFolders).
/// </summary>
public static class PersonFolders
{
    /// <summary>The folded names a person gives a known folder, by its label.</summary>
    public static IReadOnlyDictionary<string, string> Names { get; } = new Dictionary<string, string>(StringComparer.Ordinal)
    {
        ["desktop"] = "desktop",
        ["escritorio"] = "desktop",
        ["documents"] = "documents",
        ["documentos"] = "documents",
        ["mis documentos"] = "documents",
        ["downloads"] = "downloads",
        ["descargas"] = "downloads",
        ["pictures"] = "pictures",
        ["imagenes"] = "pictures",
        ["mis imagenes"] = "pictures",
        ["music"] = "music",
        ["musica"] = "music",
        ["mi musica"] = "music",
        ["videos"] = "videos",
        ["mis videos"] = "videos",
    };

    /// <summary>Where the known folder of that label is (the profile root for «home»); null for a label it is not.</summary>
    public static string? Path(string label) => label switch
    {
        "desktop" => Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
        "documents" => Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
        "downloads" => DownloadsFolder.Path(),
        "pictures" => Environment.GetFolderPath(Environment.SpecialFolder.MyPictures),
        "music" => Environment.GetFolderPath(Environment.SpecialFolder.MyMusic),
        "videos" => Environment.GetFolderPath(Environment.SpecialFolder.MyVideos),
        "home" => Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
        _ => null,
    };

    /// <summary>Lower case without accents, trimmed: «Imágenes» is «imagenes».</summary>
    public static string Fold(string value)
    {
        var builder = new StringBuilder(value.Length);
        foreach (char character in value.Trim().Normalize(NormalizationForm.FormD))
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) != UnicodeCategory.NonSpacingMark)
                builder.Append(char.ToLowerInvariant(character));
        }

        return builder.ToString();
    }
}
