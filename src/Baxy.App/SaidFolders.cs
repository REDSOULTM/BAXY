using System.IO;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Filesystem;
using Baxy.Providers.Windows.Infrastructure;

namespace Baxy.App;

/// <summary>
/// Renew al máximo (w6, rutas; holdout v4 «archivos» 3/10 in every configuration): when the person names a folder of
/// theirs («en C:\Users\…\proyecto», «en la carpeta proyecto», «en Documentos/proyecto»), the model's file calls left
/// it out and acted in their home, in a known folder or in BAXY's working folder, and the reply told the named folder
/// («lo agregué a tareas.txt en proyecto» of a file written in the home folder; «proyecto no lo tenía» after looking
/// only in Desktop, Documents and Downloads). In a turn the person opened, the folders their words name are the place
/// of its file calls: a call whose place the catalog's arguments say (folder, subdirectory, relativePath, fileName,
/// name; BAXY's working folder for a filesystem call without folder) and that is not inside one of them is, before
/// anything runs, routed into it when it only reads (the result says so), or refused with the call that names it
/// (anything else: nothing is written, deleted or opened outside what the person named). The same call written again
/// exactly as before runs as written, and its result says that it acted outside the folder the person named: the model
/// may know better (a copy from the named folder to another place), never silently. Aid «said_folder» (BAXY_AYUDAS).
/// <para>
/// A folder is named by a full path (its folder when it names a file; one that does not exist yet counts), by the
/// person's name for a known folder (PersonFolders.Names), or, when no full path was said, by the name of a folder in
/// their home, Desktop, Documents or Downloads (its top level; hidden, system, read-only shell and linked folders
/// left out), alone or as the first part of a relative path. A name found in several of them is the one in their home
/// when their words say so («en mi carpeta de usuario»); otherwise all of them, and of those the ones that hold the
/// file the call names. A folder that holds another one named is the way to it, not a place of its own, unless that
/// one is only one of several of its name. BAXY's own name is how the person speaks to it, never a folder they name.
/// </para>
/// </summary>
internal sealed class SaidFolders
{
    internal const string LeftOut = "said_folder_left_out";

    /// <summary>JSON as the model reads it: accents and «» as they are, never as \u escapes (every result the App writes
    /// itself, NativeTurnLoop).</summary>
    internal static readonly JsonSerializerOptions AsWritten = new() { Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping };

    // Where a folder named only by its name is looked for (its top level).
    private static readonly string[] NameRoots = ["home", "desktop", "documents", "downloads"];

    // The person's words for their home folder: they only say in which folder a name is (never a place by themselves:
    // every folder of theirs is in it).
    private static readonly string[] HomeWords =
        ["carpeta de usuario", "carpeta del usuario", "mi usuario", "carpeta personal", "home"];

    private const string OwnName = "baxy";

    private static readonly Regex FullPath = new(
        @"(?<![\p{L}\p{Nd}])[A-Za-z]:[\\/][^\s""'«»<>|?*,;]*", RegexOptions.CultureInvariant);

    private static readonly Regex RelativePath = new(
        @"[^\s""'«»<>|?*,;:\\/]+(?:[\\/][^\s""'«»<>|?*,;:\\/]+)+", RegexOptions.CultureInvariant);

    private static readonly EnumerationOptions TopLevel = new()
    {
        IgnoreInaccessible = true,
        AttributesToSkip = FileAttributes.Hidden | FileAttributes.System | FileAttributes.ReparsePoint
            | FileAttributes.ReadOnly,
    };

    private readonly Func<string, string?> _known;
    private readonly HashSet<string> _told = new(StringComparer.Ordinal);
    private string _words = string.Empty;

    /// <param name="known">Where each known folder is, by its label (tests point them at a temporary folder).</param>
    internal SaidFolders(Func<string, string?>? known = null) => _known = known ?? PersonFolders.Path;

    /// <summary>
    /// A folder the person named: its full path, what they said of it, and whether it is the only folder their words can
    /// mean (false for a name found in several places).
    /// </summary>
    internal sealed record Place(string Path, string Said, bool Sure = true);

    /// <summary>
    /// What happens to a call: it runs with <paramref name="Arguments"/> (its own, or routed into the folder named) and
    /// <paramref name="Note"/> goes with its result; or nothing runs and <paramref name="Refusal"/> is its whole result.
    /// </summary>
    internal sealed record Ruling(JsonObject Arguments, string? Note, JsonObject? Refusal);

    /// <summary>The person's words open a turn: the folders they name are this turn's.</summary>
    internal void Heard(string words)
    {
        _words = words ?? string.Empty;
        _told.Clear();
    }

    /// <summary>
    /// The person's words answer the call that waits for their «sí»: the folders of the turn that asked it still hold,
    /// with any these words add, as when they press Sí (auditoría de la App, 2026-10-23).
    /// </summary>
    internal void Answered(string words) =>
        _words = _words.Length == 0 ? words ?? string.Empty : _words + "\n" + words;

    /// <summary>A heartbeat or a new session: no words of the person's hold.</summary>
    internal void Clear() => Heard(string.Empty);

    /// <summary>
    /// The folders this turn's words name, read at each file call (most turns make none): a folder the turn made since
    /// the last one counts (holdout v5 V5E043: «crea la carpeta X y dentro un archivo» wrote the file beside it).
    /// </summary>
    internal IReadOnlyList<Place> Places()
    {
        var found = new List<Place>();
        foreach (Match match in FullPath.Matches(_words))
        {
            string said = Longest(match.Value, _words[(match.Index + match.Length)..]);
            if (Absolute(said) is { } full && Path.GetPathRoot(full) is { Length: > 0 } drive && Directory.Exists(drive)
                && !Same(full, drive) && FolderOf(full) is { } folder)
                found.Add(new(folder, said));
        }

        bool pathSaid = found.Count > 0;
        string rest = FullPath.Replace(_words, " ");
        var folders = new Dictionary<string, string[]>(StringComparer.OrdinalIgnoreCase);
        string[] Folders(string root) => folders.TryGetValue(root, out string[]? known) ? known
            : folders[root] = TopFolders(root);
        string[] roots = [.. NameRoots.Select(Root).OfType<string>().Distinct(StringComparer.OrdinalIgnoreCase)];
        string[] qualifiers = HomeWords.Any(word => Spoken(RelativePath.Replace(rest, " "))
            .Contains(Spoken(word), StringComparison.Ordinal)) && Root("home") is { } home ? [home] : [];

        // The folders of that name in the roots, kept where the words also name the root.
        IEnumerable<string> Named(string name)
        {
            string[] all = [.. roots.SelectMany(Folders).Where(folder =>
                Spoken(Path.GetFileName(folder)) == name)];
            string[] qualified = [.. all.Where(folder => qualifiers.Any(root => Same(Path.GetDirectoryName(folder)!, root)))];
            return qualified.Length > 0 ? qualified : all;
        }

        // A relative path said, with the words after it while they still name something under where it starts
        // (holdout v5 V5E045/V5E047: «Documentos\Turnos Farmacia» was Documents\Turnos); of its starts, the ones where
        // it exists, when any does (V5E044 on the PC: a BAXY-bench on the Desktop without the facturas named).
        var relatives = new List<Place>();
        var saidRelatives = new List<string>();
        if (!pathSaid)
        {
            foreach (Match match in RelativePath.Matches(rest))
            {
                string[] parts = Parts(match.Value.TrimEnd('.', ':', ')'));
                if (parts.Length < 2)
                    continue;
                string[] starts = PersonFolders.Names.TryGetValue(PersonFolders.Fold(parts[0]), out string? label)
                    && Root(label) is { } known ? [known] : [.. Named(Spoken(parts[0]))];
                string said = LongestRelative(match.Value, rest[(match.Index + match.Length)..], starts);
                saidRelatives.Add(said);
                parts = Parts(said);
                string[] all = [.. starts.Select(start => FolderOf(Path.Combine([start, .. parts[1..]]))).OfType<string>()];
                string[] existing = [.. all.Where(Directory.Exists)];
                string[] kept = existing.Length > 0 ? existing : all;
                relatives.AddRange(kept.Select(folder => new Place(folder, said, kept.Length == 1)));
            }
        }

        // The words of a relative path are that path's («Documentos/proyecto» is not Documents).
        string spoken = Spoken(pathSaid ? rest
            : RelativePath.Replace(saidRelatives.Aggregate(rest, static (text, said) => text.Replace(said, " ")), " "));
        var knownSaid = new HashSet<string>(StringComparer.Ordinal);
        foreach ((string name, string label) in PersonFolders.Names)
        {
            if (spoken.Contains(Spoken(name), StringComparison.Ordinal) && Root(label) is { } root && Directory.Exists(root))
            {
                found.Add(new(root, name));
                knownSaid.Add(Spoken(name));
            }
        }

        if (!pathSaid)
        {
            found.AddRange(relatives);
            // A known folder's name is that folder, not a folder of its name inside it (holdout v5 V5E043 on the
            // notebook: «en documentos» went to Documentos\Documentos).
            foreach (string name in roots.SelectMany(Folders).Select(folder => Spoken(Path.GetFileName(folder)))
                         .Distinct(StringComparer.Ordinal))
            {
                if (name.Count(char.IsLetter) >= 3 && name.Trim() != OwnName && !knownSaid.Contains(name)
                    && spoken.Contains(name, StringComparison.Ordinal))
                {
                    string[] named = [.. Named(name)];
                    found.AddRange(named.Select(folder => new Place(folder, Path.GetFileName(folder), named.Length == 1)));
                }
            }
        }

        // A folder that holds another one named is the way to it, unless that one is only one of several of its name
        // («de proyecto al escritorio» with a proyecto on the Desktop and another in the home folder).
        Place[] distinct = [.. found.GroupBy(place => place.Path, StringComparer.OrdinalIgnoreCase)
            .Select(group => group.OrderByDescending(place => place.Sure).First())];
        return [.. distinct.Where(place => !distinct.Any(other =>
            other.Sure && !Same(other.Path, place.Path) && Within(other.Path, place.Path)))];
    }

    /// <summary>What happens to this call in this turn; null: it runs as it is (not a file call, or inside a folder named).</summary>
    internal Ruling? Rule(string operation, ProductOperationDescriptor descriptor, JsonObject arguments)
    {
        if (_words.Length == 0 || !ModelAids.On(ModelAids.SaidFolder) || ReachOf(operation, descriptor, arguments) is not { } reach)
            return null;
        IReadOnlyList<Place> places = Places();
        if (places.Count == 0
            || (reach.Items.Count > 0 && reach.Items.All(item => places.Any(place => Within(item, place.Path)))))
            return null;
        string named = Said(places);
        string where = reach.Sandbox ? "BAXY's own working folder" : string.Join(", ", reach.Items);
        if (!_told.Add(operation + "\n" + arguments.ToJsonString()))
        {
            return new(arguments, $"the person named {named}; this call acted in {where}, outside it, as it was written: "
                + $"it did not look at or change anything in {(places.Count == 1 ? "that folder" : "those folders")}", null);
        }

        // Of several folders named, the ones that hold the file or folder the call names are its place.
        Place[] holding = reach.Leaf is null ? [.. places]
            : [.. places.Where(place => Holds(place.Path, reach.Leaf))];
        IReadOnlyList<Place> targets = holding.Length == 1 ? holding : places;
        string wire = operation.Replace('.', '_');
        if (descriptor.Risk == OperationRisks.ReadOnly && targets.Count == 1
            && Express(descriptor, arguments, targets[0]) is { } routed)
        {
            return new(routed, $"the person named {named}: this call looked in {targets[0].Path} "
                + $"({Changes(arguments, routed)}) instead of {where}, as it was written; to look at {where} itself, "
                + "call it again exactly as before", null);
        }

        (Place Place, JsonObject? Arguments)[] options = [.. targets.Select(place => (place, Express(descriptor, arguments, place)))];
        string again = $"if the person asked for {where} itself, call it again exactly as before";
        string next;
        if (options.Any(option => option.Arguments is not null))
        {
            // Of two folders of that name, the one that holds the file is said by its path and what it holds.
            string which = places.Count == 1 ? "that folder"
                : targets.Count == 1 ? targets[0].Path + Holding(targets[0], reach.Leaf) : "one of them";
            next = $"nothing ran: the person named {named} and this call would act in {where}, outside it. If "
                + $"{which} is the place of this call, call {wire} again with "
                + string.Join(", or ", options.Where(option => option.Arguments is not null).Select(option =>
                    Changes(arguments, option.Arguments!) + (targets.Count == 1 ? string.Empty
                        : $" for {option.Place.Path}{Holding(option.Place, reach.Leaf)}")))
                + "; " + again;
        }
        else if (reach.Sandbox)
        {
            string alternative = descriptor.Risk == OperationRisks.ReadOnly
                && ProductCatalog.TryGet("file.find", out ProductOperationDescriptor? find) && find is not null
                && targets.Count == 1 && Express(find, new JsonObject(), targets[0]) is { } look
                    ? $"file_find with {Changes(new JsonObject(), look)} looks there"
                    : $"{wire} cannot name a folder of theirs";
            next = $"nothing ran: {wire} acts only in BAXY's own working folder, not in the person's folders, and the "
                + $"person named {named}: {alternative}. If the person asked for BAXY's working folder itself, call it "
                + "again exactly as before";
        }
        else
        {
            string values = string.Join(", ", descriptor.ArgumentsSchema.Properties
                .First(static property => property.Name == "folder").AllowedValues);
            next = $"nothing ran: the person named {named}, and {wire} reaches only the folders {values}, so it cannot "
                + $"act there (it would act in {where}); {again}";
        }

        var refusal = new JsonObject
        {
            ["status"] = "rejected",
            ["error"] = LeftOut,
            ["saidFolders"] = new JsonArray([.. places.Select(place => JsonValue.Create(place.Path))]),
            ["next"] = next,
        };
        return new(arguments, null, refusal);
    }

    // Where a call acts: the items it names (a file or folder, or the folders a bare name is looked for under), or BAXY's
    // working folder; Leaf, the name of the file or folder it names. Null: the call says no place (not a file call).
    private sealed record Reach(IReadOnlyList<string> Items, bool Sandbox, string? Leaf);

    private Reach? ReachOf(string operation, ProductOperationDescriptor descriptor, JsonObject arguments)
    {
        IReadOnlyList<OperationArgumentProperty> properties = descriptor.ArgumentsSchema.Properties;
        OperationArgumentProperty? folderArgument = properties.FirstOrDefault(static property => property.Name == "folder");
        bool Takes(string name) => properties.Any(property => property.Name == name);
        if (folderArgument is null)
            return operation.StartsWith("filesystem.", StringComparison.Ordinal) ? new([], true, null) : null;
        string? folder = Text(arguments["folder"]);
        try
        {
            if (Takes("relativePath"))
            {
                if (Text(arguments["relativePath"]) is not { } relative)
                    return null;
                string leaf = Path.GetFileName(relative.TrimEnd('/', '\\'));
                if (folder is not null)
                    return Root(folder) is { } root ? new([Combine(root, relative)], false, leaf) : null;
                // As the working folder's provider reads it: a full path is its place, a known folder's name first is
                // that folder, and anything else is the working folder.
                if (Path.IsPathFullyQualified(relative))
                    return new([Path.GetFullPath(relative)], false, leaf);
                string[] parts = Parts(relative);
                return parts.Length > 1 && PersonFolders.Names.TryGetValue(PersonFolders.Fold(parts[0]), out string? named)
                    && folderArgument.AllowedValues.Contains(named) && Root(named) is { } known
                        ? new([Path.GetFullPath(Path.Combine([known, .. parts[1..]]))], false, leaf)
                        : new([], true, leaf);
            }

            if (folder is null)
            {
                // Without folder the work folder's own operations act in it (holdout v5 V5E032/V5E040: moving and
                // copying by name).
                return operation.StartsWith("filesystem.sandbox.", StringComparison.Ordinal)
                    ? new([], true, Takes("sourceFileName") ? Text(arguments["sourceFileName"]) : null) : null;
            }

            string[] labels = folder == "all_known"
                ? [.. folderArgument.AllowedValues.Where(static value => value is not ("all_known" or "home" or "projects"))]
                : [folder];
            var roots = new List<string>();
            foreach (string label in labels)
            {
                if (Root(label) is not { } root)
                    return null;
                roots.Add(root);
            }

            if (Takes("subdirectory") && Text(arguments["subdirectory"]) is { } subdirectory)
                roots = Path.IsPathFullyQualified(subdirectory) ? [Path.GetFullPath(subdirectory)]
                    : [.. roots.Select(root => Combine(root, subdirectory))];
            string? name = Takes("name") ? Text(arguments["name"]) : null;
            string? item = name ?? (Takes("fileName") ? Text(arguments["fileName"]) : null)
                ?? (Takes("sourceFileName") ? Text(arguments["sourceFileName"]) : null);
            if (item is null)
            {
                string? query = Takes("query") ? Text(arguments["query"]) : null;
                return new(roots, false, query is not null && query.IndexOfAny(['*', '?']) < 0 ? query : null);
            }

            string itemLeaf = Path.GetFileName(item.TrimEnd('/', '\\'));
            // A name is that item in the folder; a bare fileName is looked for anywhere under it.
            return Path.IsPathFullyQualified(item) ? new([Path.GetFullPath(item)], false, itemLeaf)
                : name is not null || Parts(item).Length > 1 ? new([.. roots.Select(root => Combine(root, item))], false, itemLeaf)
                : new(roots, false, itemLeaf);
        }
        catch (Exception exception) when (exception is ArgumentException or NotSupportedException or PathTooLongException)
        {
            // A path Windows cannot read: the provider refuses it, before any effect.
            return null;
        }
    }

    // The call with the folder named in place of the one it gave, as its own arguments say it (folder, subdirectory, or
    // the path or name inside the folder); null when its arguments cannot name that folder.
    private JsonObject? Express(ProductOperationDescriptor descriptor, JsonObject arguments, Place place)
    {
        IReadOnlyList<OperationArgumentProperty> properties = descriptor.ArgumentsSchema.Properties;
        bool Takes(string name) => properties.Any(property => property.Name == name);
        if (properties.FirstOrDefault(static property => property.Name == "folder") is not { } folderArgument)
            return null;
        (string Label, string Root)? holder = null;
        foreach (string label in folderArgument.AllowedValues)
        {
            if (label is not ("all_known" or "projects") && Root(label) is { } root && Within(place.Path, root)
                && (holder is null || root.Length > holder.Value.Root.Length))
                holder = (label, root);
        }

        if (holder is not { } best)
            return null;
        string relative = Same(place.Path, best.Root) ? string.Empty
            : Path.GetRelativePath(best.Root, place.Path).Replace('\\', '/');
        var routed = (JsonObject)arguments.DeepClone();
        routed["folder"] = best.Label;
        if (Takes("subdirectory"))
        {
            if (relative.Length == 0)
                routed.Remove("subdirectory");
            else
                routed["subdirectory"] = relative;
            if (Text(routed["fileName"]) is { } fileName)
                routed["fileName"] = Path.GetFileName(fileName.TrimEnd('/', '\\'));
            // A destination inside the folder, without the folder's own path it repeats (V5E032: «BAXY-bench/…»).
            if (Text(routed["destinationRelativePath"]) is { } destination)
                routed["destinationRelativePath"] = Inside(destination, relative);
            return routed;
        }

        string? key = Takes("relativePath") ? "relativePath" : Takes("name") ? "name" : null;
        if (key is not null && Text(arguments[key]) is { } given)
        {
            string inside = Inside(given, relative);
            routed[key] = relative.Length == 0 ? inside : relative + "/" + inside;
            return routed;
        }

        return relative.Length == 0 && key is null ? routed : null;
    }

    // What a path the call gave names inside the folder: a full path's last part; a relative one without a known
    // folder's name it begins with, nor the folder's own last parts it repeats («proyecto/notas.txt» in proyecto).
    private static string Inside(string given, string relative)
    {
        if (Path.IsPathFullyQualified(given))
            return Path.GetFileName(given.TrimEnd('/', '\\'));
        List<string> parts = [.. Parts(given)];
        if (parts.Count > 1 && PersonFolders.Names.ContainsKey(PersonFolders.Fold(parts[0])))
            parts.RemoveAt(0);
        string[] own = Parts(relative);
        for (int count = Math.Min(own.Length, parts.Count - 1); count > 0; count--)
        {
            if (own[^count..].SequenceEqual(parts.Take(count), StringComparer.OrdinalIgnoreCase))
            {
                parts.RemoveRange(0, count);
                break;
            }
        }

        return string.Join('/', parts);
    }

    // The arguments that differ, as the model writes them: folder "home" and subdirectory "proyecto".
    private static string Changes(JsonObject given, JsonObject routed)
    {
        var changes = new List<string>();
        foreach ((string key, JsonNode? value) in routed)
        {
            if (!JsonNode.DeepEquals(value, given[key]))
                changes.Add($"{key} {value?.ToJsonString(AsWritten) ?? "null"}");
        }

        changes.AddRange(given.Where(pair => !routed.ContainsKey(pair.Key)).Select(pair => $"no {pair.Key}"));
        return string.Join(" and ", changes);
    }

    private static string Said(IReadOnlyList<Place> places) => string.Join(" and ", places.Select(place =>
        Same(place.Said, place.Path) ? place.Path : $"«{place.Said}» ({place.Path})"));

    private static string Holding(Place place, string? leaf) =>
        leaf is null ? string.Empty : Holds(place.Path, leaf) ? $" ({leaf} is there)" : $" (no {leaf} there)";

    private static bool Holds(string folder, string leaf)
    {
        try
        {
            string path = Path.Combine(folder, leaf);
            return File.Exists(path) || Directory.Exists(path);
        }
        catch (ArgumentException)
        {
            return false;
        }
    }

    private string? Root(string label) =>
        _known(label) is { Length: > 0 } root && Absolute(root) is { } full ? full : null;

    // The folder a path names: itself, or the folder of a file (one with an extension when it does not exist yet).
    private static string? FolderOf(string path)
    {
        if (Absolute(path) is not { } full)
            return null;
        return Directory.Exists(full) ? full
            : File.Exists(full) || Path.HasExtension(full) ? Path.GetDirectoryName(full)
            : full;
    }

    private static string[] TopFolders(string root)
    {
        try
        {
            return Directory.Exists(root) ? [.. Directory.EnumerateDirectories(root, "*", TopLevel)] : [];
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return [];
        }
    }

    // A full path the words said, with the words after it while they keep naming something that exists (a folder with
    // spaces in its name), without the punctuation that ends a sentence.
    private static string Longest(string said, string after)
    {
        char[] ending = ['.', ':', ')', ',', ';', '\\', '/'];
        string best = said.TrimEnd(ending);
        string candidate = said;
        foreach (string word in after.Split(' ').Skip(1).Take(5))
        {
            candidate += " " + word;
            string trimmed = candidate.TrimEnd(ending);
            if (Absolute(trimmed) is { } full && (Directory.Exists(full) || File.Exists(full)))
                best = trimmed;
        }

        return best;
    }

    // A relative path the words said, with the words after it while they keep naming something that exists under one of
    // the folders it can start in (a folder with spaces in its name), without the punctuation that ends a sentence.
    private static string LongestRelative(string said, string after, IReadOnlyList<string> starts)
    {
        char[] ending = ['.', ':', ')', ',', ';', '\\', '/'];
        string best = said.TrimEnd('.', ':', ')');
        string candidate = said;
        foreach (string word in after.Split(' ').Skip(1).Take(5))
        {
            candidate += " " + word;
            string trimmed = candidate.TrimEnd(ending);
            string[] parts = Parts(trimmed);
            if (starts.Any(start => Absolute(Path.Combine([start, .. parts[1..]])) is { } full
                    && (Directory.Exists(full) || File.Exists(full))))
                best = trimmed;
        }

        return best;
    }

    private static string? Absolute(string path)
    {
        try
        {
            if (!Path.IsPathFullyQualified(path))
                return null;
            string full = Path.GetFullPath(path);
            string trimmed = full.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            return trimmed.Length > 2 ? trimmed : full;
        }
        catch (Exception exception) when (exception is ArgumentException or NotSupportedException or PathTooLongException)
        {
            return null;
        }
    }

    private static string Combine(string root, string relative) =>
        Path.GetFullPath(Path.Combine(root, relative.Replace('/', Path.DirectorySeparatorChar)))
            .TrimEnd(Path.DirectorySeparatorChar);

    private static bool Same(string left, string right) =>
        string.Equals(left.TrimEnd('\\', '/'), right.TrimEnd('\\', '/'), StringComparison.OrdinalIgnoreCase);

    // The path is the folder or inside it.
    private static bool Within(string path, string folder) =>
        Same(path, folder) || path.StartsWith(folder.TrimEnd('\\', '/') + "\\", StringComparison.OrdinalIgnoreCase);

    private static string[] Parts(string path) =>
        path.Split(['/', '\\'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

    // Folded words between single spaces: «BAXY-bench,» and «baxy bench» are « baxy bench » (SaidApplication too).
    internal static string Spoken(string text)
    {
        var spoken = new StringBuilder(" ");
        foreach (char character in PersonFolders.Fold(text))
        {
            if (char.IsLetterOrDigit(character))
                spoken.Append(character);
            else if (spoken[^1] != ' ')
                spoken.Append(' ');
        }

        if (spoken[^1] != ' ')
            spoken.Append(' ');
        return spoken.ToString();
    }

    private static string? Text(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out string? text) && !string.IsNullOrWhiteSpace(text) ? text.Trim() : null;
}
