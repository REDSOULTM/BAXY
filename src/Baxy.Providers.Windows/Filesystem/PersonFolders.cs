using System.Globalization;
using System.Text;

namespace Baxy.Providers.Windows.Filesystem;

/// <summary>
/// The person's known folders: where Windows keeps each one (a moved or redirected Desktop, Documents or Downloads
/// included), and the names a person gives them, in Spanish and English, folded (lower case, no accents). The file
/// tools' <c>path</c> is read with them (Place); the App reads the same names in the person's words
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

    /// <summary>
    /// Where a file tool's <c>path</c> is (P2.4, ajuste c3: one argument «as the person said it», in place of folder,
    /// subdirectory and relativePath): a full path is itself; a path whose first part is a known folder's name (Names,
    /// or the label a result gives, «home» included) is inside that folder, wherever Windows keeps it; any other is inside
    /// the person's home (every folder of theirs is in it). It is then in the deepest folder of <paramref name="labels"/>
    /// that holds it (or is it); null when none does, or when Windows cannot read it as a path.
    /// </summary>
    /// <param name="where">Where each known folder is, by its label (tests point them at a temporary folder).</param>
    public static SaidPath? Place(string? path, IReadOnlyCollection<string> labels, Func<string, string?> where)
    {
        string said = (path ?? string.Empty).Trim().Replace('/', '\\');
        if (said.Length == 0 || said.Contains('\0') || (System.IO.Path.IsPathRooted(said)
            && !System.IO.Path.IsPathFullyQualified(said)))
            return null;
        try
        {
            bool full = System.IO.Path.IsPathFullyQualified(said);
            if (!full)
            {
                string[] parts = said.Split('\\', 2);
                string? label = Known(parts[0]);
                if (label is not null && Root(where, label) is { } known)
                    said = parts.Length == 1 ? known : System.IO.Path.Combine(known, parts[1]);
                else if (Root(where, "home") is { } home)
                    said = System.IO.Path.Combine(home, said);
                else
                    return null;
            }

            string place = System.IO.Path.GetFullPath(said).TrimEnd('\\');
            (string Label, string Root)? holder = null;
            foreach (string label in labels)
            {
                if (Root(where, label) is { } root && (string.Equals(place, root, StringComparison.OrdinalIgnoreCase)
                        || place.StartsWith(root + "\\", StringComparison.OrdinalIgnoreCase))
                    && (holder is null || root.Length > holder.Value.Root.Length))
                    holder = (label, root);
            }

            return holder is not { } best ? null : new SaidPath(best.Label, best.Root,
                place.Length == best.Root.Length ? string.Empty : place[(best.Root.Length + 1)..], full);
        }
        catch (Exception exception) when (exception is ArgumentException or NotSupportedException
            or System.IO.PathTooLongException)
        {
            return null;
        }
    }

    /// <summary>
    /// Whether a path names no folder: only a name, with no separator, that is no known folder's name (Place reads it in
    /// the person's home; a read, an edit or a delete looks for it under Desktop, Documents and Downloads).
    /// </summary>
    public static bool NameOnly(string? path)
    {
        string said = (path ?? string.Empty).Trim();
        return said.Length > 0 && said.IndexOfAny(['/', '\\']) < 0 && !System.IO.Path.IsPathRooted(said)
            && Known(said) is null;
    }

    // The label of a known folder by a path's first part: its name (Names) or the label a result gives («home» too).
    private static string? Known(string part)
    {
        string first = Fold(part);
        return first == "home" ? "home" : Names.TryGetValue(first, out string? named) ? named : null;
    }

    /// <summary>
    /// The known folders a file tool's path may be in, by operation (the labels its folder argument took before P2.4);
    /// none for an operation without one. Every folder of the person's is in their home, so «home» reaches any of them.
    /// </summary>
    public static IReadOnlyCollection<string> PathLabels(string operation) => operation switch
    {
        "file.write" or "filesystem.create.directory" or "file.read" or "file.edit" or "filesystem.known.trash.named"
            or "filesystem.sandbox.move.named" => ["desktop", "documents", "downloads", "home"],
        "file.find" or "file.open" or "filesystem.folder.open" or "filesystem.explorer.count"
            => ["desktop", "documents", "downloads", "home", "pictures"],
        "file.compress" or "desktop.wallpaper.set" => ["desktop", "documents", "downloads", "pictures"],
        _ => [],
    };

    private static string? Root(Func<string, string?> where, string label) =>
        where(label) is { Length: > 0 } root && System.IO.Path.IsPathFullyQualified(root)
            ? System.IO.Path.GetFullPath(root).TrimEnd('\\')
            : null;

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

/// <summary>
/// A file tool's path read against the person's folders (PersonFolders.Place): the known folder that holds it (its label
/// and where it is), the rest of the path inside it ("" for the folder itself), and whether the person said it as a full
/// path.
/// </summary>
public sealed record SaidPath(string Label, string Root, string Relative, bool Full)
{
    /// <summary>The folder part of Relative ("" when it is directly in the folder) and its last part.</summary>
    public (string Folder, string Leaf) Split() =>
        Relative.LastIndexOf('\\') is var cut and >= 0 ? (Relative[..cut], Relative[(cut + 1)..]) : (string.Empty, Relative);
}
