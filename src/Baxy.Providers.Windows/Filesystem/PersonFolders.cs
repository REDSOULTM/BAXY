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
            or "capture.screenshot" or "capture.active.window"
            => ["desktop", "documents", "downloads", "home", "pictures"],
        "file.compress" or "desktop.wallpaper.set" => ["desktop", "documents", "downloads", "pictures"],
        _ => [],
    };

    // Encargo 17 (U23): where a folder of the person's is looked for by its name, and how deep, as a file to open is
    // (WindowsFileToolsAdapter.LocateOpenTarget): the four known folders four levels down, then the home folder's own
    // folders one level down; at most five, within a bound of time.
    private static readonly (string Label, int Depth)[] FolderSearchPlaces =
        [("desktop", 4), ("documents", 4), ("downloads", 4), ("pictures", 4), ("home", 1)];
    private const int FolderSearchCandidates = 5;
    private static readonly TimeSpan FolderSearchBudget = TimeSpan.FromSeconds(2);

    /// <summary>
    /// Encargo 17 (banco uso-cf8d, U23): the person's folders named <paramref name="name"/> (folded: case and accents
    /// aside), under their known folders (<see cref="FolderSearchPlaces"/>; hidden, system, unreadable and linked folders
    /// left out), each as a file tool's path takes it: the known folder's label, then the folders inside it.
    /// <paramref name="complete"/> is false when the search was cut (its time, its count, a folder it could not list).
    /// </summary>
    public static IReadOnlyList<string> FoldersNamed(string name, Func<string, string?> where, out bool complete)
    {
        string wanted = Fold(name);
        var found = new List<string>();
        complete = true;
        if (wanted.Length == 0)
            return found;
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var clock = System.Diagnostics.Stopwatch.StartNew();
        bool cut = false;
        bool OutOfTime() => cut || (cut = clock.Elapsed > FolderSearchBudget);
        foreach ((string label, int depth) in FolderSearchPlaces)
        {
            if (OutOfTime() || found.Count >= FolderSearchCandidates || Root(where, label) is not { } root
                || !System.IO.Directory.Exists(root))
                continue;
            try
            {
                var folders = new System.IO.Enumeration.FileSystemEnumerable<string>(
                    root,
                    (ref System.IO.Enumeration.FileSystemEntry entry) => entry.ToFullPath(),
                    new System.IO.EnumerationOptions
                    {
                        RecurseSubdirectories = true,
                        MaxRecursionDepth = depth,
                        IgnoreInaccessible = true,
                        AttributesToSkip = System.IO.FileAttributes.Hidden | System.IO.FileAttributes.System
                            | System.IO.FileAttributes.ReparsePoint,
                    })
                {
                    ShouldIncludePredicate = (ref System.IO.Enumeration.FileSystemEntry entry) =>
                        !OutOfTime() && entry.IsDirectory && Fold(entry.FileName.ToString()) == wanted,
                    ShouldRecursePredicate = (ref System.IO.Enumeration.FileSystemEntry _) => !OutOfTime(),
                };
                // A folder inside two known folders (the Desktop inside the home folder) is said once, from the first.
                foreach (string folder in folders.Where(seen.Add))
                {
                    found.Add(label + "\\" + System.IO.Path.GetRelativePath(root, folder));
                    if (found.Count >= FolderSearchCandidates)
                        break;
                }
            }
            catch (Exception exception) when (exception is System.IO.IOException or UnauthorizedAccessException)
            {
                cut = true;
            }
        }

        complete = !cut && found.Count < FolderSearchCandidates;
        return found;
    }

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
