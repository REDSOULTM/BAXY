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
    internal const string NameChanged = "said_name_changed";

    /// <summary>JSON as the model reads it: accents and «» as they are, never as \u escapes (every result the App writes
    /// itself, NativeTurnLoop).</summary>
    internal static readonly JsonSerializerOptions AsWritten = new() { Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping };

    // Where a folder named only by its name is looked for (its top level).
    private static readonly string[] NameRoots = ["home", "desktop", "documents", "downloads"];

    // The person's words for their home folder: they only say in which folder a name is (never a place by themselves:
    // every folder of theirs is in it).
    private static readonly string[] HomeWords =
        ["carpeta de usuario", "carpeta del usuario", "mi usuario", "carpeta personal", "home"];

    // The person's words for BAXY's working folder. With the home words, a place said that is no folder by its name: a
    // turn that says one is not ruled by the folder of the previous request (revisión de nb-w11-multi).
    private static readonly string[] WorkWords = ["carpeta de trabajo", "tu carpeta", "carpeta de baxy"];

    private const string OwnName = "baxy";

    private static readonly Regex FullPath = new(
        @"(?<![\p{L}\p{Nd}])[A-Za-z]:[\\/][^\s""'«»<>|?*,;]*", RegexOptions.CultureInvariant);

    // A path separator said as a word («baxy bench barra facturas», dictated).
    private static readonly Regex SaidSeparator = new(@"^ (?:barra|slash|diagonal) ", RegexOptions.CultureInvariant);

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
    // The words of the person's previous request (none after a heartbeat or a new session).
    private string _before = string.Empty;
    // The folders this turn's calls made in the person's folders (Ran).
    private readonly List<string> _made = [];

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
        _before = _words;
        _words = words ?? string.Empty;
        _told.Clear();
        _made.Clear();
    }

    /// <summary>
    /// The person's words answer the call that waits for their «sí»: the folders of the turn that asked it still hold,
    /// with any these words add, as when they press Sí (auditoría de la App, 2026-10-23).
    /// </summary>
    internal void Answered(string words) =>
        _words = _words.Length == 0 ? words ?? string.Empty : _words + "\n" + words;

    /// <summary>A call ran with <paramref name="arguments"/> as sent and ended with <paramref name="status"/>: a folder
    /// it made in the person's folders is one this turn made (Rule).</summary>
    internal void Ran(string operation, JsonObject arguments, string? status)
    {
        if (operation == "filesystem.create.directory" && status == OperationStatuses.Completed
            && ProductCatalog.TryGet(operation, out ProductOperationDescriptor? descriptor) && descriptor is not null
            && ReachOf(operation, descriptor, arguments) is { Sandbox: false, Items: [string folder] })
            _made.Add(folder);
    }

    /// <summary>A heartbeat or a new session: no words of the person's hold.</summary>
    internal void Clear() => Heard(string.Empty);

    /// <summary>The one file of the person's the call names, when it is there (SaidVerbs: an append presupposes it).</summary>
    internal string? FileThere(string operation, ProductOperationDescriptor descriptor, JsonObject arguments) =>
        ReachOf(operation, descriptor, arguments) is { Sandbox: false, Items: [string file] } && File.Exists(file)
            ? file
            : null;

    /// <summary>
    /// The folders this turn's words name, read at each file call (most turns make none): a folder the turn made since
    /// the last one counts (holdout v5 V5E043: «crea la carpeta X y dentro un archivo» wrote the file beside it).
    /// </summary>
    internal IReadOnlyList<Place> Places() => Places(_words);

    private IReadOnlyList<Place> Places(string words)
    {
        var found = new List<Place>();
        foreach (Match match in FullPath.Matches(words))
        {
            string said = Longest(match.Value, words[(match.Index + match.Length)..]);
            if (Absolute(said) is { } full && Path.GetPathRoot(full) is { Length: > 0 } drive && Directory.Exists(drive)
                && !Same(full, drive) && FolderOf(full) is { } folder)
                found.Add(new(folder, said));
        }

        bool pathSaid = found.Count > 0;
        string rest = FullPath.Replace(words, " ");
        var folders = new Dictionary<string, string[]>(StringComparer.OrdinalIgnoreCase);
        string[] Folders(string root) => folders.TryGetValue(root, out string[]? known) ? known
            : folders[root] = TopFolders(root);
        string[] roots = [.. NameRoots.Select(Root).OfType<string>().Distinct(StringComparer.OrdinalIgnoreCase)];
        string[] qualifiers = HomeWords.Any(word => Spoken(RelativePath.Replace(rest, " "))
            .Contains(Spoken(word), StringComparison.Ordinal)) && Root("home") is { } home ? [home] : [];

        // The folders of that name in the roots, kept where the words also name the root. Of several of one sound, the
        // ones spelled as said (said: the words as Spoken writes them) when any is: «vaca» is Vaca, not
        // also Baca (revisión de nb-w11-arch).
        IEnumerable<string> Named(string name, string said)
        {
            string[] all = [.. roots.SelectMany(Folders).Where(folder =>
                Sounded(Path.GetFileName(folder)) == name)];
            string[] spelled = [.. all.Where(folder => said.Contains(Spoken(Path.GetFileName(folder)), StringComparison.Ordinal))];
            if (spelled.Length > 0)
                all = spelled;
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
                    && Root(label) is { } known ? [known] : [.. Named(Sounded(parts[0]), Spoken(parts[0]))];
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
        string unpathed = pathSaid ? rest
            : RelativePath.Replace(saidRelatives.Aggregate(rest, static (text, said) => text.Replace(said, " ")), " ");
        string spoken = Sounded(unpathed);
        // The same words as written (Sounded keeps every position): which of the folders of one sound they spell.
        string written = Spoken(unpathed);
        var knownSaid = new HashSet<string>(StringComparer.Ordinal);
        foreach ((string name, string label) in PersonFolders.Names)
        {
            if (spoken.Contains(Sounded(name), StringComparison.Ordinal) && Root(label) is { } root && Directory.Exists(root))
            {
                found.Add(new(root, name));
                knownSaid.Add(Sounded(name));
            }
        }

        if (!pathSaid)
        {
            found.AddRange(relatives);
            // A known folder's name is that folder, not a folder of its name inside it (holdout v5 V5E043 on the
            // notebook: «en documentos» went to Documentos\Documentos).
            string[] names = [.. roots.SelectMany(Folders).Select(folder => Sounded(Path.GetFileName(folder)))
                .Distinct(StringComparer.Ordinal).Where(name => name.Count(char.IsLetter) >= 3
                    && name.Trim() != Sounded(OwnName).Trim() && !knownSaid.Contains(name)
                    && spoken.Contains(name, StringComparison.Ordinal))];
            foreach (string name in names)
            {
                // A name said only as part of a longer one that is also a folder's is that folder's (holdout v6 V6E043:
                // «la carpeta recetas abuela» is Recetas Abuela, not also a folder recetas).
                if (Occurrences(spoken, name).All(at => names.Any(other => other.Length > name.Length
                        && Occurrences(spoken, other).Any(from => from <= at && at + name.Length <= from + other.Length))))
                    continue;
                string[] named = [.. Named(name, written)];
                found.AddRange(named.Select(folder => new Place(folder, Path.GetFileName(folder), named.Length == 1)));
            }
        }

        // A separator said as a word between a folder named and one inside it leads into that one (holdout v5 V5E044,
        // dictado: «cuantos pdf hay en baxy bench barra facturas» counted in BAXY-bench).
        for (int index = 0; index < found.Count; index++)
            found[index] = Deeper(found[index], spoken, written);

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
        if (_words.Length == 0)
            return null;
        if (NameAsSaid(operation, arguments) is { } respelled)
            return respelled;
        if (!ModelAids.On(ModelAids.SaidFolder) || ReachOf(operation, descriptor, arguments) is not { } reach)
            return null;
        IReadOnlyList<Place> places = Places();
        // Holdout v6 V6E058, V6E062, V6E055: the folder of a request is left unsaid in the next one («uy, me equivoqué de
        // año, era fotos_2026»; «ábreme horario.txt que está ahí») and the call acted in the home folder. Words that name
        // no folder are ruled by the folders the person's previous request named, never to route a read there.
        bool earlier = places.Count == 0 && _before.Length > 0 && !HomeWords.Concat(WorkWords)
            .Any(word => Spoken(_words).Contains(Spoken(word), StringComparison.Ordinal));
        if (earlier)
        {
            if (descriptor.Risk == OperationRisks.ReadOnly)
                return null;
            places = Places(_before);
        }

        string who = earlier ? "the person's previous request named" : "the person named";
        if (places.Count == 0
            || (reach.Items.Count > 0 && reach.Items.All(item => places.Any(place => Within(item, place.Path)))))
            return null;
        string named = Said(places);
        string where = reach.Sandbox ? "BAXY's own working folder" : string.Join(", ", reach.Items);
        // Holdout v8 (falsedades #16): «haz una carpeta cumple_benja en BAXY-bench, adentro un archivo lista.txt»; the
        // write left out the folder just made and was offered BAXY-bench/lista.txt, beside it. A folder this turn made
        // inside a folder named is a place of it. Of those and the folders named, the ones that hold the file or folder
        // the call names are its place; of a write that names what none holds, the only folder made.
        Place[] made = [.. _made.Where(folder => places.Any(place => !Same(folder, place.Path) && Within(folder, place.Path)))
            .Distinct(StringComparer.OrdinalIgnoreCase).Select(folder => new Place(folder, Path.GetFileName(folder)))];
        Place[] holding = reach.Leaf is null ? []
            : [.. places.Concat(made).Where(place => Holds(place.Path, reach.Leaf))];
        IReadOnlyList<Place> targets = holding.Length == 1 ? holding
            : holding.Length == 0 && made.Length == 1 && reach.Leaf is not null && descriptor.Risk != OperationRisks.ReadOnly
                ? made : places;
        // The look there is said as a call, with what the call looked for (holdout v6 V6E042: told only that file_find
        // «looks there», the model wrote the same filesystem_search again).
        string? look = reach.Sandbox && descriptor.Risk == OperationRisks.ReadOnly
            && ProductCatalog.TryGet("file.find", out ProductOperationDescriptor? find) && find is not null
            && targets.Count == 1 && Express(find, Shared(arguments, find), targets[0]) is { } found
                ? $"to look there, call file_find with {Changes(new JsonObject(), found)}" : null;
        // Holdout v6 V6E034 (final_v5 s0): told only that filesystem_copy «cannot name a folder of theirs», the model
        // answered that the file was in the person's folder and not in its working folder, and copied nothing. The
        // operation that does the same act there is said as a call (aid «said_folder_counterpart»).
        string? twin = reach.Sandbox && targets.Count == 1 && ModelAids.On(ModelAids.SaidFolderCounterpart)
            ? Twin(operation, arguments, targets[0]) : null;
        look = twin ?? look;
        if (!_told.Add(operation + "\n" + arguments.ToJsonString()))
        {
            // Holdout v6 V6E042 (cien s0 and s2): the search refused was written again and ran in the working folder; its
            // note said only what it had not looked at, and the model answered «no está en mi carpeta de trabajo» (the
            // run that called file_find next found it). The look there is said again with what it did not look at.
            // Revisión de final2: only after a read. A copy or a move written again has run as written; its counterpart
            // said as a call to make would follow that act with a second one in the person's folder.
            string? after = descriptor.Risk == OperationRisks.ReadOnly ? look : null;
            return new(arguments, $"{who} {named}; this call acted in {where}, outside it, as it was written: "
                + $"it did not look at or change anything in {(places.Count == 1 ? "that folder" : "those folders")}"
                + (after is null ? string.Empty : "; " + after), null);
        }

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
            string which = targets.Count == 1 && made.Contains(targets[0])
                    ? $"{targets[0].Path}, the folder this turn made in {(places.Count == 1 ? "it" : "one of them")},"
                : places.Count == 1 ? "that folder"
                : targets.Count == 1 ? targets[0].Path + Holding(targets[0], reach.Leaf) : "one of them";
            next = $"nothing ran: {who} {named} and this call would act in {where}, outside it. If "
                + $"{which} is the place of this call, call {wire} again with "
                + string.Join(", or ", options.Where(option => option.Arguments is not null).Select(option =>
                    Changes(arguments, option.Arguments!, whole: true) + (targets.Count == 1
                        ? Reached(operation, descriptor, option.Arguments!, option.Place)
                        : $" for {option.Place.Path}{Holding(option.Place, reach.Leaf)}")))
                + "; " + again;
        }
        else if (reach.Sandbox)
        {
            next = $"nothing ran: {wire} acts only in BAXY's own working folder, not in the person's folders, and "
                + $"{who} {named}: {look ?? $"{wire} cannot name a folder of theirs"}. If the person asked for BAXY's "
                + "working folder itself, call it again exactly as before";
        }
        else
        {
            string values = string.Join(", ", descriptor.ArgumentsSchema.Properties
                .First(static property => property.Name == "folder").AllowedValues);
            next = $"nothing ran: {who} {named}, and {wire} reaches only the folders {values}, so it cannot "
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

    // Holdout v5 V5E043: a folder made with a name the person said, spelled otherwise (viaje_chiloe_2027 for «viaje
    // chiloé 2027»: accents, separators), is refused once with the call that writes it as they said it; the same call
    // again runs as written. Only a name whose folded words are exactly theirs and that differs beyond case. Aid
    // «said_name».
    private Ruling? NameAsSaid(string operation, JsonObject arguments)
    {
        if (operation != "filesystem.create.directory" || !ModelAids.On(ModelAids.SaidName)
            || Text(arguments["relativePath"]) is not { } relative || Parts(relative) is not { Length: > 0 } parts)
            return null;
        string leaf = parts[^1];
        // A spelling no folder name can hold («informe: tercer trimestre») is not offered: the call would fail.
        if (SaidSpelling(Spoken(leaf)) is not { } theirs || string.Equals(theirs, leaf, StringComparison.OrdinalIgnoreCase)
            || theirs.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0
            || !_told.Add("name\n" + arguments.ToJsonString()))
            return null;
        var respelled = (JsonObject)arguments.DeepClone();
        respelled["relativePath"] = string.Join('/', [.. parts[..^1], theirs]);
        return new(arguments, null, new JsonObject
        {
            ["status"] = "rejected",
            ["error"] = NameChanged,
            ["next"] = $"nothing ran: the person said the name «{theirs}» and this call writes «{leaf}»; call "
                + $"{operation.Replace('.', '_')} again with {Changes(arguments, respelled)}, as they said it; if they asked "
                + "for this spelling, call it again exactly as before",
        });
    }

    // The person's own spelling of words that fold to the ones given: the run of their words (without the punctuation at
    // its ends) whose folded form is exactly that.
    private string? SaidSpelling(string folded)
    {
        if (folded.Trim().Length == 0)
            return null;
        string[] words = _words.Split([' ', '\n', '\t'], StringSplitOptions.RemoveEmptyEntries);
        int most = folded.Trim().Split(' ').Length;
        for (int count = 1; count <= most; count++)
        {
            for (int start = 0; start + count <= words.Length; start++)
            {
                string run = string.Join(' ', words[start..(start + count)]).Trim('.', ',', ';', ':', '«', '»', '"', '(', ')', '¿', '?', '¡', '!');
                if (Spoken(run) == folded)
                    return run;
            }
        }

        return null;
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
        if (Holder(descriptor, place) is not (string label, string relative))
            return null;
        var routed = (JsonObject)arguments.DeepClone();
        routed["folder"] = label;
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

    // The deepest known folder of the call's folder argument that holds the place, and the place's path inside it (empty
    // for that folder itself); null when the call has no folder argument or none of its folders holds the place.
    private (string Label, string Relative)? Holder(ProductOperationDescriptor descriptor, Place place)
    {
        if (descriptor.ArgumentsSchema.Properties.FirstOrDefault(static property => property.Name == "folder") is not { } folder)
            return null;
        (string Label, string Root)? holder = null;
        foreach (string label in folder.AllowedValues)
        {
            if (label is not ("all_known" or "projects") && Root(label) is { } root && Within(place.Path, root)
                && (holder is null || root.Length > holder.Value.Root.Length))
                holder = (label, root);
        }

        return holder is not { } best ? null
            : (best.Label, Same(place.Path, best.Root) ? string.Empty
                : Path.GetRelativePath(best.Root, place.Path).Replace('\\', '/'));
    }

    // Revisión de los bucles de said_folder (93 repeated refusals in 64 turns of the saved runs): told the call that names
    // the folder, the model wrote it and then left the folder out of its next call (44 of them; final5 V6E048: file_edit
    // fixed, file_read in it, then file_edit and file_write without it, three refusals, ~20 s); and told relativePath
    // "BAXY-bench/facturas2025" and folder "home", it wrote relativePath "facturas2025" (27; V6E064, V8E067). The call is
    // said with where it acts, and the folder with how every call of the turn in it names it. Only in the forms this
    // call's arguments take (e2e final6c V6E044: file_write, told «as subdirectory», which it has not, answered without
    // calling).
    private string Reached(string operation, ProductOperationDescriptor descriptor, JsonObject routed, Place place) =>
        (ReachOf(operation, descriptor, routed) is { Sandbox: false, Items.Count: > 0 } reach
            ? $" (it acts in {string.Join(", ", reach.Items)})" : string.Empty)
        + (Holder(descriptor, place) is not (string label, string relative) ? string.Empty
            : relative.Length == 0 ? $"; any other call of this turn in that folder says it the same way, folder \"{label}\""
            : $"; any other call of this turn in that folder says it the same way: folder \"{label}\" with \"{relative}\" "
                + Forms(descriptor));

    // How the call's arguments put a path inside its folder: as subdirectory, or at the start of relativePath or name.
    private static string Forms(ProductOperationDescriptor descriptor)
    {
        bool Takes(string name) => descriptor.ArgumentsSchema.Properties.Any(property => property.Name == name);
        string start = (Takes("relativePath"), Takes("name")) switch
        {
            (true, true) => "at the start of relativePath or name",
            (true, false) => "at the start of relativePath",
            (false, true) => "at the start of name",
            _ => string.Empty,
        };
        return !Takes("subdirectory") ? start : start.Length == 0 ? "as subdirectory" : "as subdirectory, or " + start;
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
            // Holdout v6 V6E043: the folder's name respelled by the model («recetas_abuela» in Recetas Abuela) is it.
            if (own[^count..].Select(Sounded).SequenceEqual(parts.Take(count).Select(Sounded), StringComparer.Ordinal))
            {
                parts.RemoveRange(0, count);
                break;
            }
        }

        return string.Join('/', parts);
    }

    // The operations of BAXY's working folder whose act another one does in the person's folders: that one, the argument
    // it needs that the call had no way to say (the file's own name; the working folder's calls name it by its id), and
    // whether it copies.
    private static readonly Dictionary<string, (string Operation, string Name, bool Copy)> Twins = new(StringComparer.Ordinal)
    {
        ["filesystem.copy"] = ("filesystem.sandbox.move.named", "sourceFileName", true),
        ["filesystem.move"] = ("filesystem.sandbox.move.named", "sourceFileName", false),
        ["filesystem.read.text"] = ("file.read", "fileName", false),
    };

    // That operation as a call in the folder named: what the call gave that it also takes (a destination, inside the
    // folder), the folder, and the name it still needs; null when it has none or cannot name that folder.
    private string? Twin(string operation, JsonObject arguments, Place place)
    {
        if (!Twins.TryGetValue(operation, out (string Operation, string Name, bool Copy) twin)
            || !ProductCatalog.TryGet(twin.Operation, out ProductOperationDescriptor? other) || other is null
            || Express(other, Shared(arguments, other), place) is not { } routed)
            return null;
        if (twin.Copy)
            routed["copy"] = true;
        string wire = twin.Operation.Replace('.', '_');
        return $"{operation.Replace('.', '_')} cannot name a folder of theirs, and {wire} does it there: call {wire} with "
            + $"{Changes(new JsonObject(), routed)}, and {twin.Name} the file's own name";
    }

    // The arguments of a call that another operation also takes (a search's query, for file_find).
    private static JsonObject Shared(JsonObject arguments, ProductOperationDescriptor other)
    {
        var shared = new JsonObject();
        foreach ((string key, JsonNode? value) in arguments)
        {
            if (other.ArgumentsSchema.Properties.Any(property => property.Name == key))
                shared[key] = value?.DeepClone();
        }

        return shared;
    }

    // The arguments that differ, as the model writes them: folder "home" and subdirectory "proyecto". Whole: a place
    // given by folder and subdirectory is said with both (holdout v6 V6E034: told only the subdirectory of a call that
    // had folder "home", the model wrote it without that folder). A path inside a folder that changed is said with it
    // (holdout v6 V6E065: told only folder "home" for a call whose relativePath already held the folder named, the
    // model wrote that path again without it).
    private static string Changes(JsonObject given, JsonObject routed, bool whole = false)
    {
        bool split = whole && routed.ContainsKey("subdirectory");
        bool moved = !JsonNode.DeepEquals(routed["folder"], given["folder"]);
        var changes = new List<string>();
        foreach ((string key, JsonNode? value) in routed)
        {
            if (!JsonNode.DeepEquals(value, given[key]) || (split && key is "folder" or "subdirectory")
                || (moved && key == "relativePath"))
                changes.Add($"{key} {value?.ToJsonString(AsWritten) ?? "null"}");
        }

        changes.AddRange(given.Where(pair => !routed.ContainsKey(pair.Key)).Select(pair => $"no {pair.Key}"));
        return string.Join(" and ", changes);
    }

    private static string Said(IReadOnlyList<Place> places) => string.Join(" and ", places.Select(place =>
        Same(place.Said, place.Path) ? place.Path : $"«{place.Said}» ({place.Path})"));

    private static string Holding(Place place, string? leaf) =>
        leaf is null ? string.Empty : Held(place.Path, leaf) is { Length: > 0 } held
            ? $" ({string.Join(" and ", held)} {(held.Length == 1 ? "is" : "are")} there)" : $" (no {leaf} there)";

    private static bool Holds(string folder, string leaf) => Held(folder, leaf).Length > 0;

    // The names of what the folder holds by that name: the name itself or, with none so spelled, those of its words
    // otherwise separated (holdout v6 V6F010, SpokenFileNames).
    private static string[] Held(string folder, string leaf)
    {
        try
        {
            string path = Path.Combine(folder, leaf);
            if (File.Exists(path) || Directory.Exists(path))
                return [leaf];
            return Directory.Exists(folder)
                ? [.. Directory.EnumerateFileSystemEntries(folder).Select(entry => Path.GetFileName(entry))
                    .Where(name => SpokenFileNames.Same(name, leaf)).Order(StringComparer.Ordinal)]
                : [];
        }
        catch (Exception exception) when (exception is ArgumentException or IOException or UnauthorizedAccessException)
        {
            return [];
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

    // The folder a separator said as a word leads into from a place («cajón barra facturas»: facturas inside cajón), as
    // far as the words keep naming a folder inside the last one.
    // Of several inside it of one sound, the one spelled as written says (the same words as Spoken writes them).
    private static Place Deeper(Place place, string spoken, string written)
    {
        string said = Sounded(place.Said);
        int at = spoken.IndexOf(said, StringComparison.Ordinal);
        if (said.Trim().Length == 0 || at < 0)
            return place;
        int after = at + said.Length - 1;
        string folder = place.Path;
        while (SaidSeparator.Match(spoken[after..]) is { Success: true } separator)
        {
            int next = after + separator.Length - 1;
            string rest = spoken[next..];
            string? inner = TopFolders(folder).Where(child => rest.StartsWith(Sounded(Path.GetFileName(child)), StringComparison.Ordinal))
                .OrderByDescending(child => written[next..].StartsWith(Spoken(Path.GetFileName(child)), StringComparison.Ordinal))
                .ThenByDescending(child => Path.GetFileName(child).Length).FirstOrDefault();
            if (inner is null)
                break;
            after = next + Sounded(Path.GetFileName(inner)).Length - 1;
            folder = inner;
        }

        return Same(folder, place.Path) ? place
            : place with { Path = folder, Said = place.Said + "/" + Path.GetRelativePath(place.Path, folder).Replace('\\', '/') };
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

    // The person's words and a folder's name as they sound: a dictated name comes spelled by its sounds (holdout v6
    // V6E044: «baxi bench» for BAXY-bench), so the letters Spanish writes for one sound are one: b and v, s and z, i and
    // a y not before a vowel.
    private static string Sounded(string text)
    {
        char[] letters = Spoken(text).ToCharArray();
        for (int index = 0; index < letters.Length; index++)
        {
            letters[index] = letters[index] switch
            {
                'v' => 'b',
                'z' => 's',
                'y' when index + 1 == letters.Length || "aeiou".IndexOf(letters[index + 1]) < 0 => 'i',
                char letter => letter,
            };
        }

        return new string(letters);
    }

    private static IEnumerable<int> Occurrences(string text, string part)
    {
        for (int at = text.IndexOf(part, StringComparison.Ordinal); at >= 0;
             at = text.IndexOf(part, at + 1, StringComparison.Ordinal))
            yield return at;
    }

    private static string? Text(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out string? text) && !string.IsNullOrWhiteSpace(text) ? text.Trim() : null;
}
