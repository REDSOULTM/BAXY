using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.Kernel.Operations;

/// <summary>
/// Estabilización, encargo C: the places of an application that have an address of their own (a protocol the application
/// registered in Windows: its library, its store, its search with what is searched). One source, in data
/// (src/baxy_mind/data/app_places.v1.json, embedded), read here; the file's own examples are the contract its tests hold
/// this reader to. app.open takes a place by its name (<see cref="PlaceNames"/>, the schema's
/// closed list) and the address is composed only here, from the application's own entry: an application, a place or a
/// value the data does not declare has no address, and no address ever has a scheme its application does not declare.
/// No application is named in code. Encargo imp-steam: the same entry declares the acts of its game catalog that the
/// application starts by an address of its own (install, uninstall, launch a game by its catalog number, «acts») with the
/// names of the control of its own dialog that confirms them («confirm»), and the public search that turns a game's
/// title into its catalog number («titles», only the title leaves the computer); no act is a place app.open takes.
/// BAXY Renew al máximo (F019, E015): a place may declare what only it shows in the application's window («shows»), so a
/// look at that window says which of its places is in sight (<see cref="PlaceShown(string?, IEnumerable{string?})"/>).
/// </summary>
public static class ApplicationPlaces
{
    private const string Resource = "Baxy.Kernel.AppPlaces.json";

    // A value searched for, as the person said it; a game's identifier is a catalog number.
    private const int QueryMaximumUtf8Bytes = 128;
    private const int GameMaximumDigits = 16;

    // The shortest text a place's «shows» may declare, squeezed (<see cref="Squeezed"/>): a shorter one is in too much.
    private const int ShownMinimumCharacters = 6;

    private static readonly Lazy<IReadOnlyDictionary<string, Application>> Loaded = new(() =>
    {
        using JsonDocument document = Load();
        return Read(document);
    });

    /// <summary>Every place name the data declares, ordinally sorted and distinct (app.open's «place» values).</summary>
    public static IReadOnlyList<string> PlaceNames { get; } =
        [.. Loaded.Value.Values.SelectMany(application => application.Places.Keys).Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)];

    private static readonly Lazy<IReadOnlyList<(string Name, IReadOnlyCollection<string> Places)>> Named = new(() =>
    {
        using JsonDocument document = Load();
        IReadOnlyDictionary<string, Application> applications = Read(document);
        return [.. document.RootElement.GetProperty("applications").EnumerateObject()
            .Select(entry => (entry.Name, (IReadOnlyCollection<string>)[.. applications[Fold(entry.Name)].Places.Keys]))];
    });

    /// <summary>
    /// The applications, as the data name them, that declare <paramref name="place"/> with an address of its own: what an
    /// opening refused for that place is told with (e2e p3/p4 E014: «Configuración del sistema» with «sound», eight times).
    /// </summary>
    public static IReadOnlyList<string> ApplicationsWith(string? place) =>
        place is null ? [] : [.. Named.Value.Where(entry => entry.Places.Contains(place)).Select(entry => entry.Name)];

    /// <summary>
    /// Every name the data give <paramref name="application"/> (folded: its own and its other Start catalog names, as in
    /// <see cref="ReadNames"/>); empty when the data do not declare it.
    /// </summary>
    public static IReadOnlyList<string> NamesOf(string? application) =>
        application is not null && Loaded.Value.TryGetValue(Fold(application), out Application? declared)
            ? [.. Loaded.Value.Where(entry => ReferenceEquals(entry.Value, declared)).Select(entry => entry.Key)]
            : [];

    /// <summary>
    /// The address of <paramref name="place"/> of <paramref name="application"/> (its name in the Start catalog, as
    /// app.open says it) filled with <paramref name="value"/>; null when the data declares no such application or place,
    /// or the value does not fit the place's slot (none given for a slot, one given for none, a game that is not a
    /// number, a text too long or with control characters).
    /// </summary>
    public static string? Address(string? application, string? place, string? value) =>
        Address(Loaded.Value, application, place, value);

    /// <summary>
    /// BAXY Renew cu (C03 en frío): whether the data says <paramref name="application"/> starts behind its own sign-in
    /// (Steam: an updater and «Iniciar sesión», then its window), so a place handed while it starts is lost and goes
    /// again to the window it settles on.
    /// </summary>
    public static bool StartsBehindSignIn(string? application) =>
        application is not null && Loaded.Value.TryGetValue(Fold(application), out Application? found) && found.StartsBehindSignIn;

    internal static string? Address(
        IReadOnlyDictionary<string, Application> applications, string? application, string? place, string? value) =>
        application is not null && place is not null
        && applications.TryGetValue(Fold(application), out Application? declared)
        && declared.Places.TryGetValue(place, out string? template)
            ? Filled(template, value)
            : null;

    /// <summary>
    /// Banco de uso 2026-11-03 (U33): the page on the web of <paramref name="place"/> of <paramref name="application"/>
    /// («web» in the data, an https address with the same slot as the place's own), filled with <paramref name="value"/>
    /// as <see cref="Address(string?, string?, string?)"/> fills it; null when the data declare none or the value does
    /// not fit. What an opening of the place says when the application is not on the PC.
    /// </summary>
    public static string? WebAddress(string? application, string? place, string? value) =>
        application is not null && place is not null
        && Loaded.Value.TryGetValue(Fold(application), out Application? declared)
        && declared.Web.TryGetValue(place, out string? template)
            ? Filled(template, value)
            : null;

    // An address with its slot filled by the value it takes (none for no slot); null when the value does not fit.
    private static string? Filled(string template, string? value)
    {
        string? slot = SlotOf(template);
        if (slot is null)
        {
            return string.IsNullOrEmpty(value) ? template : null;
        }

        if (string.IsNullOrWhiteSpace(value) || value.Any(char.IsControl))
        {
            return null;
        }

        string? filled = slot switch
        {
            "{query}" when Encoding.UTF8.GetByteCount(value) <= QueryMaximumUtf8Bytes => Uri.EscapeDataString(value.Trim()),
            "{game}" when value.Length <= GameMaximumDigits && value.All(char.IsAsciiDigit) => value,
            "{slug}" when Encoding.UTF8.GetByteCount(value) <= QueryMaximumUtf8Bytes && Slug(value) is { Length: > 0 } slug
                => slug,
            _ => null,
        };
        return filled is null ? null : template.Replace(slot, filled, StringComparison.Ordinal);
    }

    /// <summary>
    /// BAXY Renew cu (C04): the places <paramref name="application"/> opens at directly, ordinally sorted, each with what
    /// its slot takes («query»: what is searched; «game»: a game), null for none; empty for an application with none.
    /// </summary>
    public static IReadOnlyList<(string Place, string? Takes)> PlacesOf(string? application) =>
        application is not null && Loaded.Value.TryGetValue(Fold(application), out Application? declared)
            ? [.. declared.Places.OrderBy(place => place.Key, StringComparer.Ordinal)
                .Select(place => (place.Key, SlotOf(place.Value)?.Trim('{', '}')))]
            : [];

    /// <summary>
    /// Encargo 80: the read the data of <paramref name="application"/> declare, which answers what its pages do not say at a
    /// glance; null for an application with none.
    /// </summary>
    public static ApplicationRead? ReadOf(string? application) =>
        application is not null && Loaded.Value.TryGetValue(Fold(application), out Application? declared)
            ? declared.Read
            : null;

    /// <summary>
    /// BAXY Renew cu (C04): the game catalog of <paramref name="application"/> when its <paramref name="place"/> takes a
    /// game (its slot is the catalog number), so a game's title said for it is that catalog's to turn into the number.
    /// Null for any other application or place.
    /// </summary>
    public static string? GameCatalogOf(string? application, string? place) =>
        application is not null && place is not null
        && Loaded.Value.TryGetValue(Fold(application), out Application? declared)
        && declared.GameCatalog is not null
        && declared.Places.TryGetValue(place, out string? template) && SlotOf(template) == "{game}"
            ? declared.GameCatalog
            : null;

    /// <summary>
    /// BAXY Renew cu (C04 variant, C05): the application whose data name the game catalog <paramref name="catalog"/>, by
    /// the name the data give it (its name in the Start catalog); null when none does.
    /// </summary>
    public static string? ApplicationOfCatalog(string? catalog) =>
        catalog is null ? null : Named.Value
            .Select(entry => entry.Name)
            .FirstOrDefault(name => Loaded.Value.TryGetValue(Fold(name), out Application? declared)
                && string.Equals(declared.GameCatalog, catalog, StringComparison.Ordinal));

    /// <summary>
    /// The act <paramref name="act"/> of the application whose data name the game catalog <paramref name="catalog"/>
    /// («gameCatalog»), for the game <paramref name="game"/> (its catalog number): its address and the names of the
    /// control of the application's own dialog that confirms it. Null when the data declare no such act or the game is no
    /// catalog number.
    /// </summary>
    public static GameAct? GameActOf(string? catalog, string? act, string? game) =>
        GameActOf(Loaded.Value, catalog, act, game);

    internal static GameAct? GameActOf(
        IReadOnlyDictionary<string, Application> applications, string? catalog, string? act, string? game)
    {
        Application? declared = Catalogued(applications, catalog);
        if (act is null || declared is null || !declared.Acts.TryGetValue(act, out GameAct? template)
            || string.IsNullOrEmpty(game) || game.Length > GameMaximumDigits || !game.All(char.IsAsciiDigit))
        {
            return null;
        }

        return template with { Address = template.Address.Replace("{game}", game, StringComparison.Ordinal) };
    }

    /// <summary>
    /// The public search of the game catalog <paramref name="catalog"/>'s application for <paramref name="title"/> (the
    /// title escaped into its slot; nothing else of the person leaves) and where its answer lists each game's number and
    /// name. Null when the data declare none or the title does not fit (blank, too long, control characters).
    /// </summary>
    public static TitleSearch? TitleSearchOf(string? catalog, string? title) =>
        TitleSearchOf(Loaded.Value, catalog, title);

    internal static TitleSearch? TitleSearchOf(
        IReadOnlyDictionary<string, Application> applications, string? catalog, string? title)
    {
        TitleSearch? template = Catalogued(applications, catalog)?.Titles;
        if (template is null || string.IsNullOrWhiteSpace(title) || title.Any(char.IsControl)
            || Encoding.UTF8.GetByteCount(title) > QueryMaximumUtf8Bytes)
        {
            return null;
        }

        return template with
        {
            Address = template.Address.Replace("{title}", Uri.EscapeDataString(title.Trim()), StringComparison.Ordinal),
        };
    }

    /// <summary>
    /// BAXY Renew al máximo (F019, E015: Steam's library read as «la página principal» or «la tienda»): which place of
    /// <paramref name="application"/> a look at its window shows, from what the look read in it (<paramref name="seen"/>:
    /// its text lines and its controls' names). A place shows when a text its «shows» declares is in one of them, compared
    /// squeezed (lower case, no accents, letters and digits only: an OCR that reads «https:,'/store_steampoweredcom/»
    /// still holds «store.steampowered.com»). Null when the data declare nothing shown for the application, when none
    /// shows, or when two places do (which one is in sight is then not known, and nothing is said).
    /// </summary>
    public static ShownPlace? PlaceShown(string? application, IEnumerable<string?> seen) =>
        PlaceShown(Loaded.Value, application, seen);

    internal static ShownPlace? PlaceShown(
        IReadOnlyDictionary<string, Application> applications, string? application, IEnumerable<string?> seen)
    {
        if (application is null || !applications.TryGetValue(Fold(application), out Application? declared)
            || declared.Shows.Count == 0)
        {
            return null;
        }

        string[] read = [.. seen.Select(line => Squeezed(line ?? string.Empty)).Where(line => line.Length > 0)];
        ShownPlace? shown = null;
        foreach ((string place, IReadOnlyList<string> texts) in declared.Shows.OrderBy(entry => entry.Key, StringComparer.Ordinal))
        {
            string? by = texts.FirstOrDefault(text => read.Any(line => line.Contains(Squeezed(text), StringComparison.Ordinal)));
            if (by is null)
            {
                continue;
            }

            if (shown is not null)
            {
                return null;
            }

            shown = new ShownPlace(place, by);
        }

        return shown;
    }

    /// <summary>
    /// Práctica e2e E014: whether two names are one application as the data compare them (case, accents and spacing left
    /// out, or two Start names the data give one entry), so the place a look shows is told against the one app.open
    /// asked; false when either is missing.
    /// </summary>
    public static bool SameApplication(string? one, string? other) =>
        !string.IsNullOrWhiteSpace(one) && !string.IsNullOrWhiteSpace(other)
        && (string.Equals(Fold(one), Fold(other), StringComparison.Ordinal)
            || (Loaded.Value.TryGetValue(Fold(one), out Application? first)
                && Loaded.Value.TryGetValue(Fold(other), out Application? second) && ReferenceEquals(first, second)));

    /// <summary>
    /// Revisión w11-rev4: whether the data declare a text <paramref name="place"/> of <paramref name="application"/>
    /// shows; a place that declares none is never found in sight (<see cref="PlaceShown(string?, IEnumerable{string?})"/>),
    /// so another one found is no proof it is not there (a game's page shows the store's address too).
    /// </summary>
    public static bool DeclaresShown(string? application, string? place) =>
        application is not null && place is not null && Loaded.Value.TryGetValue(Fold(application), out Application? declared)
        && declared.Shows.TryGetValue(place, out IReadOnlyList<string>? texts) && texts.Count > 0;

    private static Application? Catalogued(IReadOnlyDictionary<string, Application> applications, string? catalog) =>
        catalog is null ? null : applications.Values.FirstOrDefault(
            application => string.Equals(application.GameCatalog, catalog, StringComparison.Ordinal));

    /// <summary>An act's address and the names of the control of the application's own dialog that confirms it.</summary>
    public sealed record GameAct(string Address, IReadOnlyList<string> Confirm);

    /// <summary>The place a look shows and the text the data declare for it that the look read.</summary>
    public sealed record ShownPlace(string Place, string Shown);

    /// <summary>A read an application's data declare: its call, and what it tells.</summary>
    public sealed record ApplicationRead(string Operation, JsonObject Arguments, string Tells);

    /// <summary>A title search's address and the fields of its JSON answer: the list, and each item's number and name.</summary>
    public sealed record TitleSearch(string Address, string List, string Id, string Name);

    /// <summary>
    /// The application's entry: its schemes, its places (each with its address), and for a game catalog's application
    /// the catalog's name, its acts and its title search; and what each place that declares it shows in its window.
    /// </summary>
    internal sealed record Application(
        IReadOnlyList<string> Schemes,
        IReadOnlyDictionary<string, string> Places,
        string? GameCatalog,
        IReadOnlyDictionary<string, GameAct> Acts,
        TitleSearch? Titles,
        bool StartsBehindSignIn = false)
    {
        internal IReadOnlyDictionary<string, IReadOnlyList<string>> Shows { get; init; } =
            new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal);

        /// <summary>Each place's page on the web, when the data declare one (<see cref="WebAddress"/>).</summary>
        internal IReadOnlyDictionary<string, string> Web { get; init; } =
            new Dictionary<string, string>(StringComparer.Ordinal);

        /// <summary>The read its data declare (<see cref="ReadOf"/>).</summary>
        internal ApplicationRead? Read { get; init; }
    }

    /// <summary>
    /// The data's applications by folded name. Every address must open with one of its application's schemes and carry at
    /// most one known slot; data that breaks it is refused whole, never half read.
    /// </summary>
    internal static IReadOnlyDictionary<string, Application> Read(JsonDocument document)
    {
        var applications = new Dictionary<string, Application>(StringComparer.Ordinal);
        foreach (JsonProperty entry in document.RootElement.GetProperty("applications").EnumerateObject())
        {
            string[] schemes = [.. entry.Value.GetProperty("schemes").EnumerateArray().Select(scheme => scheme.GetString()!)];
            var places = new Dictionary<string, string>(StringComparer.Ordinal);
            var shows = new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal);
            var web = new Dictionary<string, string>(StringComparer.Ordinal);
            foreach (JsonProperty place in entry.Value.GetProperty("places").EnumerateObject())
            {
                // What only this place shows: texts, none too short to tell a place by.
                if (place.Value.TryGetProperty("shows", out JsonElement shown))
                {
                    string[] texts = [.. shown.EnumerateArray().Select(text => text.GetString() ?? string.Empty)];
                    if (texts.Length == 0 || texts.Any(text => Squeezed(text).Length < ShownMinimumCharacters))
                    {
                        throw new InvalidDataException($"app_places: {entry.Name}/{place.Name}/shows");
                    }

                    shows[place.Name] = texts;
                }

                // A place named but without an address of its own (measured: no protocol reaches it) opens nothing.
                if (!place.Value.TryGetProperty("address", out JsonElement declared))
                {
                    continue;
                }

                string address = declared.GetString()!;
                int colon = address.IndexOf(':', StringComparison.Ordinal);
                if (colon <= 0 || !schemes.Contains(address[..colon], StringComparer.Ordinal)
                    || address.Count(character => character == '{') > 1
                    || (address.Contains('{', StringComparison.Ordinal) && SlotOf(address) is null))
                {
                    throw new InvalidDataException($"app_places: {entry.Name}/{place.Name}");
                }

                places[place.Name] = address;

                // Its page on the web: https, with the slot the address has and nothing else.
                if (place.Value.TryGetProperty("web", out JsonElement page))
                {
                    string onWeb = page.GetString() ?? string.Empty;
                    if (!onWeb.StartsWith("https://", StringComparison.Ordinal)
                        || onWeb.Count(character => character == '{') > 1 || SlotOf(onWeb) != SlotOf(address)
                        || !Uri.TryCreate(onWeb, UriKind.Absolute, out _))
                    {
                        throw new InvalidDataException($"app_places: {entry.Name}/{place.Name}/web");
                    }

                    web[place.Name] = onWeb;
                }
            }

            string? catalog = entry.Value.TryGetProperty("gameCatalog", out JsonElement named) ? named.GetString() : null;
            bool signIn = entry.Value.TryGetProperty("startsBehindSignIn", out JsonElement behind)
                && behind.ValueKind == JsonValueKind.True;
            var application = new Application(
                schemes, places, catalog, ReadActs(entry, schemes, catalog), ReadTitles(entry, catalog), signIn)
            {
                Shows = shows,
                Web = web,
                Read = entry.Value.TryGetProperty("read", out JsonElement read) ? ReadRead(entry.Name, read) : null,
            };
            foreach (string name in (string[])[entry.Name, .. ReadNames(entry)])
            {
                if (!applications.TryAdd(Fold(name), application))
                {
                    throw new InvalidDataException($"app_places: {entry.Name}/names");
                }
            }
        }

        return applications;
    }

    private static ApplicationRead ReadRead(string application, JsonElement read)
    {
        string operation = read.TryGetProperty("operation", out JsonElement named) ? named.GetString() ?? string.Empty : string.Empty;
        string tells = read.TryGetProperty("tells", out JsonElement told) ? told.GetString() ?? string.Empty : string.Empty;
        return string.IsNullOrWhiteSpace(operation) || string.IsNullOrWhiteSpace(tells)
            || !read.TryGetProperty("arguments", out JsonElement arguments)
            || JsonNode.Parse(arguments.GetRawText()) is not JsonObject written
                ? throw new InvalidDataException($"app_places: {application}/read")
                : new ApplicationRead(operation, written, tells);
    }

    // Ajuste c3 (e2e de la VM, Windows en inglés, E014): the other names the Start catalog gives the same application in
    // another display language («Settings» where Spanish Windows says «Configuración»), each the same entry with the same
    // places. None blank; a name already another application's is refused with the whole data (checked as they are added).
    private static string[] ReadNames(JsonProperty entry)
    {
        if (!entry.Value.TryGetProperty("names", out JsonElement declared))
        {
            return [];
        }

        string[] names = [.. declared.EnumerateArray().Select(name => name.GetString() ?? string.Empty)];
        return names.Any(name => Fold(name).Length == 0)
            ? throw new InvalidDataException($"app_places: {entry.Name}/names")
            : names;
    }

    // An act opens with one of its application's schemes and carries exactly the game's slot; its confirming names are
    // words, never blank. Acts belong to an application with a game catalog.
    private static Dictionary<string, GameAct> ReadActs(JsonProperty entry, string[] schemes, string? catalog)
    {
        var acts = new Dictionary<string, GameAct>(StringComparer.Ordinal);
        if (!entry.Value.TryGetProperty("acts", out JsonElement declared))
        {
            return acts;
        }

        foreach (JsonProperty act in declared.EnumerateObject())
        {
            string address = act.Value.GetProperty("address").GetString()!;
            int colon = address.IndexOf(':', StringComparison.Ordinal);
            string[] confirm = act.Value.TryGetProperty("confirm", out JsonElement names)
                ? [.. names.EnumerateArray().Select(name => name.GetString() ?? string.Empty)]
                : [];
            if (catalog is null || colon <= 0 || !schemes.Contains(address[..colon], StringComparer.Ordinal)
                || address.Count(character => character == '{') != 1
                || !address.Contains("{game}", StringComparison.Ordinal)
                || confirm.Any(string.IsNullOrWhiteSpace))
            {
                throw new InvalidDataException($"app_places: {entry.Name}/acts/{act.Name}");
            }

            acts[act.Name] = new GameAct(address, confirm);
        }

        return acts;
    }

    // A title search is a public https address with exactly the title's slot, and names the fields of its answer.
    private static TitleSearch? ReadTitles(JsonProperty entry, string? catalog)
    {
        if (!entry.Value.TryGetProperty("titles", out JsonElement declared))
        {
            return null;
        }

        string address = declared.GetProperty("address").GetString()!;
        var search = new TitleSearch(
            address,
            declared.GetProperty("list").GetString() ?? string.Empty,
            declared.GetProperty("id").GetString() ?? string.Empty,
            declared.GetProperty("name").GetString() ?? string.Empty);
        if (catalog is null || !address.StartsWith("https://", StringComparison.Ordinal)
            || address.Count(character => character == '{') != 1
            || !address.Contains("{title}", StringComparison.Ordinal)
            || string.IsNullOrWhiteSpace(search.List) || string.IsNullOrWhiteSpace(search.Id)
            || string.IsNullOrWhiteSpace(search.Name))
        {
            throw new InvalidDataException($"app_places: {entry.Name}/titles");
        }

        return search;
    }

    private static JsonDocument Load()
    {
        using Stream stream = typeof(ApplicationPlaces).Assembly.GetManifestResourceStream(Resource)
            ?? throw new InvalidOperationException(Resource);
        return JsonDocument.Parse(stream);
    }

    private static string? SlotOf(string address) =>
        address.Contains("{query}", StringComparison.Ordinal) ? "{query}"
        : address.Contains("{game}", StringComparison.Ordinal) ? "{game}"
        : address.Contains("{slug}", StringComparison.Ordinal) ? "{slug}"
        : null;

    /// <summary>
    /// Uso real 2026-10-21 (e2e del notebook: «la página de Fortnite en la aplicación de Epic» opened the web store): a
    /// store that names a game's page by its title written as an address (Epic: …/store/p/rocket-league) gets the title
    /// in lower case, without accents, every run of anything but letters and digits made one hyphen. Empty when nothing
    /// of the title is left.
    /// </summary>
    internal static string Slug(string title)
    {
        var builder = new StringBuilder(title.Length);
        bool pendingHyphen = false;
        foreach (char character in title.Normalize(NormalizationForm.FormD).ToLowerInvariant())
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) == UnicodeCategory.NonSpacingMark)
                continue;
            if (character is (>= 'a' and <= 'z') or (>= '0' and <= '9'))
            {
                if (pendingHyphen && builder.Length > 0)
                    builder.Append('-');
                builder.Append(character);
                pendingHyphen = false;
            }
            else
            {
                pendingHyphen = true;
            }
        }

        return builder.ToString();
    }

    // A text as a look's text is compared with a place's «shows»: lower case, no accents, letters and digits only (what
    // OCR reads between words, and a dot of an address, is not compared).
    private static string Squeezed(string text)
    {
        var builder = new StringBuilder(text.Length);
        foreach (char character in text.Normalize(NormalizationForm.FormD).ToLowerInvariant())
        {
            if (char.IsLetterOrDigit(character))
            {
                builder.Append(character);
            }
        }

        return builder.ToString();
    }

    // An application's name as the Start catalog writes it and as the data does: lower case, no accents, single spaces.
    private static string Fold(string name)
    {
        string decomposed = name.Normalize(NormalizationForm.FormD);
        var builder = new StringBuilder(decomposed.Length);
        foreach (char character in decomposed)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) != UnicodeCategory.NonSpacingMark)
            {
                builder.Append(char.ToLowerInvariant(character));
            }
        }

        return string.Join(' ', builder.ToString().Split(' ', StringSplitOptions.RemoveEmptyEntries));
    }
}
