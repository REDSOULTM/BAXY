using System.Globalization;
using System.Text;
using System.Text.Json;

namespace Baxy.Kernel.Operations;

/// <summary>
/// Estabilización, encargo C: the places of an application that have an address of their own (a protocol the application
/// registered in Windows: its library, its store, its search with what is searched). One source, in data
/// (src/baxy_mind/data/app_places.v1.json, embedded), read here and by the mind (semantic/app_places); the file's own
/// examples tie both readers in their tests. app.open takes a place by its name (<see cref="PlaceNames"/>, the schema's
/// closed list) and the address is composed only here, from the application's own entry: an application, a place or a
/// value the data does not declare has no address, and no address ever has a scheme its application does not declare.
/// No application is named in code. Encargo imp-steam: the same entry declares the acts of its game catalog that the
/// application starts by an address of its own (install, uninstall, launch a game by its catalog number, «acts») with the
/// names of the control of its own dialog that confirms them («confirm»), and the public search that turns a game's
/// title into its catalog number («titles», only the title leaves the computer); no act is a place app.open takes.
/// </summary>
public static class ApplicationPlaces
{
    private const string Resource = "Baxy.Kernel.AppPlaces.json";

    // A value searched for, as the person said it; a game's identifier is a catalog number.
    private const int QueryMaximumUtf8Bytes = 128;
    private const int GameMaximumDigits = 16;

    private static readonly Lazy<IReadOnlyDictionary<string, Application>> Loaded = new(() =>
    {
        using JsonDocument document = Load();
        return Read(document);
    });

    /// <summary>Every place name the data declares, ordinally sorted and distinct (app.open's «place» values).</summary>
    public static IReadOnlyList<string> PlaceNames { get; } =
        [.. Loaded.Value.Values.SelectMany(application => application.Places.Keys).Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal)];

    /// <summary>
    /// The address of <paramref name="place"/> of <paramref name="application"/> (its name in the Start catalog, as
    /// app.open says it) filled with <paramref name="value"/>; null when the data declares no such application or place,
    /// or the value does not fit the place's slot (none given for a slot, one given for none, a game that is not a
    /// number, a text too long or with control characters).
    /// </summary>
    public static string? Address(string? application, string? place, string? value) =>
        Address(Loaded.Value, application, place, value);

    /// <summary>
    /// Encargo IMP4: the data declare where <paramref name="application"/> draws its conversation («conversation»): a
    /// question about what was written there is answered from the lines its own drawing shows (the mind reads them).
    /// </summary>
    public static bool HasConversation(string? application) =>
        application is not null && Loaded.Value.TryGetValue(Fold(application), out Application? entry) && entry.Conversation;

    internal static string? Address(
        IReadOnlyDictionary<string, Application> applications, string? application, string? place, string? value)
    {
        if (application is null || place is null
            || !applications.TryGetValue(Fold(application), out Application? declared)
            || !declared.Places.TryGetValue(place, out string? template))
        {
            return null;
        }

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
            _ => null,
        };
        return filled is null ? null : template.Replace(slot, filled, StringComparison.Ordinal);
    }

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

    private static Application? Catalogued(IReadOnlyDictionary<string, Application> applications, string? catalog) =>
        catalog is null ? null : applications.Values.FirstOrDefault(
            application => string.Equals(application.GameCatalog, catalog, StringComparison.Ordinal));

    /// <summary>An act's address and the names of the control of the application's own dialog that confirms it.</summary>
    public sealed record GameAct(string Address, IReadOnlyList<string> Confirm);

    /// <summary>A title search's address and the fields of its JSON answer: the list, and each item's number and name.</summary>
    public sealed record TitleSearch(string Address, string List, string Id, string Name);

    /// <summary>
    /// The application's entry: its schemes, its places (each with its address), and for a game catalog's application
    /// the catalog's name, its acts and its title search.
    /// </summary>
    internal sealed record Application(
        IReadOnlyList<string> Schemes,
        IReadOnlyDictionary<string, string> Places,
        string? GameCatalog,
        IReadOnlyDictionary<string, GameAct> Acts,
        TitleSearch? Titles,
        bool Conversation = false);

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
            foreach (JsonProperty place in entry.Value.GetProperty("places").EnumerateObject())
            {
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
            }

            string? catalog = entry.Value.TryGetProperty("gameCatalog", out JsonElement named) ? named.GetString() : null;
            applications[Fold(entry.Name)] = new Application(
                schemes, places, catalog, ReadActs(entry, schemes, catalog), ReadTitles(entry, catalog),
                entry.Value.TryGetProperty("conversation", out JsonElement conversation)
                    && conversation.ValueKind == JsonValueKind.Object);
        }

        return applications;
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
        : null;

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
