using System.Globalization;
using System.IO.Compression;
using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// WEB1 (2026-11-07, LIC1 R3): the places the weather and another place's time read by name. They were asked of
/// Open-Meteo's free geocoder, whose free use is «only ... for non-commercial purposes» (https://open-meteo.com/en/terms);
/// its places are GeoNames', published for download under CC BY 4.0 (https://download.geonames.org/export/dump/readme.txt),
/// and BAXY now carries them (<c>Data/geonames_places.v1.tsv.gz</c>, made by <c>scripts/datos/geonames_lugares.py</c>):
/// a place's name no longer leaves this PC. A place is named as GeoNames names it in Spanish and in English (and by its
/// main and ASCII names), with its region, province, country, population and IANA time zone.
/// </summary>
internal sealed class GeoNamesGazetteer
{
    private const string ResourceName = "Baxy.Providers.Windows.GeoNamesPlaces.tsv.gz";
    private static readonly Lazy<GeoNamesGazetteer> s_shared = new(Load, LazyThreadSafetyMode.ExecutionAndPublication);

    // Kept as sorted arrays, not as a dictionary of lists: about 176 000 places and 300 000 names.
    private readonly GazetteerPlace[] _places;
    private readonly long[] _ids;
    private readonly string[] _names;
    private readonly int[] _namedPlaces;
    private readonly Dictionary<long, (string Es, string En)> _provinces = [];
    private readonly Dictionary<string, long> _countries = new(StringComparer.Ordinal);
    private readonly Dictionary<string, string> _capitalZones = new(StringComparer.Ordinal);

    internal GeoNamesGazetteer(TextReader lines)
    {
        var places = new List<GazetteerPlace>();
        var names = new List<(string Name, long Id)>();
        var spellings = new Dictionary<string, string>(StringComparer.Ordinal);
        for (string? line = lines.ReadLine(); line is not null; line = lines.ReadLine())
        {
            if (line.Length == 0 || line[0] == '#')
                continue;
            string[] fields = line.Split('\t');
            switch (fields[0])
            {
                case "C":
                    _countries[fields[1]] = long.Parse(fields[2], CultureInfo.InvariantCulture);
                    break;
                case "N":
                    _provinces[long.Parse(fields[1], CultureInfo.InvariantCulture)] =
                        (fields[2], fields[3] == fields[2] ? fields[2] : fields[3]);
                    break;
                case "P":
                    GazetteerPlace place = Read(fields);
                    places.Add(place);
                    // Its Spanish, English, main and ASCII names, each once.
                    var own = new HashSet<string>(StringComparer.Ordinal);
                    foreach (string spelling in fields.Skip(10).Take(4))
                    {
                        string name = Fold(spelling);
                        if (name.Length == 0 || !own.Add(name))
                            continue;
                        if (!spellings.TryGetValue(name, out string? shared))
                            spellings[name] = shared = name;
                        names.Add((shared, place.Id));
                    }
                    break;
            }
        }

        places.Sort(static (left, right) => left.Id.CompareTo(right.Id));
        _places = [.. places];
        _ids = [.. places.Select(static place => place.Id)];
        foreach (GazetteerPlace capital in places.Where(static place => place.FeatureCode == "PPLC")
                     .OrderBy(static place => place.Population))
        {
            if (capital.TimeZone is { } zone)
                _capitalZones[capital.CountryCode] = zone;
        }
        names.Sort(static (left, right) => string.CompareOrdinal(left.Name, right.Name) is int order and not 0
            ? order
            : left.Id.CompareTo(right.Id));
        _names = [.. names.Select(static name => name.Name)];
        _namedPlaces = [.. names.Select(name => Array.BinarySearch(_ids, name.Id))];
    }

    /// <summary>The places of this PC's copy, read once when a place is first asked.</summary>
    internal static GeoNamesGazetteer Shared => s_shared.Value;

    /// <summary>The places named so (case, accents and punctuation folded), in Spanish, in English or by GeoNames' own
    /// name.</summary>
    internal IReadOnlyList<GazetteerPlace> Named(string name)
    {
        string folded = Fold(name);
        var named = new List<GazetteerPlace>();
        for (int index = First(folded); index < _names.Length && _names[index] == folded; index++)
            named.Add(_places[_namedPlaces[index]]);
        return named;
    }

    /// <summary>
    /// The places named so that a person means by the name. A first-order region is one of them («North Carolina»,
    /// «Carolina del Norte», «Texas») unless the name is its capital's or a capital's of its country (PPLC, PPLG, PPLA:
    /// «Valparaíso», «Buenos Aires», «Washington»), or a town of comparable size inside it bears the name («Nueva York»):
    /// that town is the one meant. A seat of a lesser division (a county, a municipality) or a town abroad does not take
    /// a region's name («Virginia», «California», «Florida»).
    /// </summary>
    internal IReadOnlyList<GazetteerPlace> Meant(string name)
    {
        IReadOnlyList<GazetteerPlace> named = Named(name);
        return [.. named.Where(region => !region.IsRegion || !named.Any(place => place.IsPopulatedPlace
            && ((place.IsCapital && place.CountryCode == region.CountryCode)
                || (place.RegionId == region.Id && place.Population >= ComparableSize * region.Population))))];
    }

    /// <summary>A place whose population is at least this share of another's is of comparable size.</summary>
    internal const double ComparableSize = 0.25;

    /// <summary>The time zone of a country's capital, for a place of that country that has none of its own (a country of
    /// several zones read as a whole), or null.</summary>
    internal string? CapitalZone(GazetteerPlace place) => _capitalZones.GetValueOrDefault(place.CountryCode);

    /// <summary>The places one of whose names begins with the name asked (as whole words), largest first: what the
    /// person may have meant when no place is named exactly so.</summary>
    internal IReadOnlyList<GazetteerPlace> NamedFrom(string name, int count)
    {
        string folded = Fold(name);
        if (folded.Length == 0)
            return [];
        var found = new HashSet<GazetteerPlace>();
        for (int index = First(folded);
             index < _names.Length && _names[index].StartsWith(folded, StringComparison.Ordinal);
             index++)
        {
            if (_names[index].Length == folded.Length || _names[index][folded.Length] == ' ')
                found.Add(_places[_namedPlaces[index]]);
        }

        return [.. found.OrderByDescending(static place => place.Population).ThenBy(static place => place.Id).Take(count)];
    }

    // Ronda 19 (r17 t2-c13 «¿qué tiempo va a hacer mañana en Valencia? ¿cojo paraguas?» → Valencia, Venezuela, the
    // most populous, with no country said): places of the asked name whose size is comparable (a quarter of the
    // largest or more) are namesakes, and among several nothing is chosen: they go back as candidates, largest first.
    // The country the person's speech marks (dialectCountry) keeps the namesakes of that country; a much smaller
    // place of the name is no namesake of a large one.
    // Ronda final 10 (regla 3): how many places were found, the first eight listed.
    private const int ListedCandidates = 8;
    private const int CountedCandidates = 100;

    /// <summary>
    /// The place a name means, or none and what was found instead. The place read is the one whose name is the name
    /// asked (case, accents and punctuation folded), in Spanish or in English, because the person names it in either.
    /// Uso real tanda 4c «Digame el weather lunes 13 en North Carolina» read «Calvary, Georgia», a hamlet that carries
    /// the state's name as an alias: an alias, a park that carries the name or a place that only shares a word with it
    /// is not the place. A first-order region is a place of its name unless a capital or a town of comparable size
    /// inside it bears it (<see cref="Meant"/>). M58 (v3d-final F-p07-t1/t2 «the weather in Foster City»): «Lugar,
    /// Región» looks up only the name and keeps, of the places of that name, those whose region, province or country is
    /// the one said. WEB2 (2026-11-07): the weather's choice, and another place's time's too: that one took the most
    /// populated of the name («Georgia» was the state, said as the place) and the first place whose name began so, and
    /// read «Mérida, Venezuela» as a name.
    /// </summary>
    internal GazetteerChoice Choose(string location, string? dialectCountry = null)
    {
        string[] parts = location.Split(',', 2, StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        string? within = parts.Length == 2 ? parts[1] : null;
        string name = within is null ? location : parts[0];
        List<GazetteerPlace> named = [.. Meant(name)];
        List<GazetteerPlace> exact = named;
        if (within is not null)
        {
            string said = Fold(within);
            exact = [.. named.Where(place => Within(place, said))];
        }

        if (exact.Count == 0)
        {
            return new(null, named.Count > 0
                ? [.. named.OrderByDescending(static place => place.Population)]
                : NamedFrom(name, CountedCandidates), false, false);
        }
        double top = exact.Max(static place => place.Population);
        // WEB2: GeoNames gives most divisions no population: one without it is of a size unknown, a namesake of any
        // («La Reina», a comuna of Chile, and a municipality of El Salvador).
        List<GazetteerPlace> comparable = [.. exact
            .Where(place => top <= 0 || place.Population >= ComparableSize * top
                || (place.IsDivision && place.Population <= 0))
            .OrderByDescending(static place => place.Population)];
        bool elsewhere = false;
        if (comparable.Count > 1 && dialectCountry is { Length: > 0 } marked)
        {
            List<GazetteerPlace> spoken = [.. comparable.Where(place =>
                string.Equals(place.CountryCode, marked, StringComparison.OrdinalIgnoreCase))];
            if (spoken.Count == 1)
            {
                elsewhere = true;
                comparable = spoken;
            }
        }

        return comparable.Count > 1
            ? new(null, comparable, true, false)
            : new(comparable[0], [], false, elsewhere);
    }

    /// <summary>The places found instead of the one asked, as a receipt gives them: how many, the first eight listed.</summary>
    internal JsonElement CandidatesJson(string requested, IReadOnlyList<GazetteerPlace> candidates) =>
        ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("requested", requested);
            writer.WriteNumber("candidateCount", candidates.Count);
            if (candidates.Count > ListedCandidates) writer.WriteBoolean("truncated", true);
            writer.WriteStartArray("candidates");
            foreach (GazetteerPlace item in candidates.Take(ListedCandidates))
            {
                writer.WriteStartObject();
                writer.WriteString("name", item.NameEs);
                if (Region(item) is { } region)
                    writer.WriteString("region", region.NameEs);
                writer.WriteString("country", Country(item)?.NameEs ?? string.Empty);
                writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteEndObject();
        });

    // The region, the province or the country of the place (in Spanish or in English), or its country's code.
    private bool Within(GazetteerPlace place, string said)
    {
        (string Es, string En)? province = Province(place);
        GazetteerPlace? region = Region(place);
        GazetteerPlace? country = Country(place);
        string?[] names =
        [
            region?.NameEs, region?.NameEn, province?.Es, province?.En, country?.NameEs, country?.NameEn,
            place.CountryCode,
        ];
        return names.Any(name => name is not null && Fold(name) == said);
    }

    /// <summary>The first-order region a place belongs to (a region is its own), or null.</summary>
    internal GazetteerPlace? Region(GazetteerPlace place) => Place(place.RegionId);

    /// <summary>The names of the province (second-order division) a place belongs to, or null.</summary>
    internal (string Es, string En)? Province(GazetteerPlace place) =>
        _provinces.TryGetValue(place.ProvinceId, out (string Es, string En) names) ? names : null;

    /// <summary>The country a place is in, as a place, or null.</summary>
    internal GazetteerPlace? Country(GazetteerPlace place) =>
        _countries.TryGetValue(place.CountryCode, out long id) ? Place(id) : null;

    /// <summary>Case, accents and punctuation folded: «Valparaíso», «valparaiso» and «VALPARAÍSO» are one name.</summary>
    internal static string Fold(string text)
    {
        var folded = new StringBuilder(text.Length);
        foreach (char character in text.Normalize(NormalizationForm.FormD))
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) == UnicodeCategory.NonSpacingMark)
                continue;
            folded.Append(char.IsLetterOrDigit(character) ? char.ToLowerInvariant(character) : ' ');
        }
        return string.Join(' ', folded.ToString().Split(' ', StringSplitOptions.RemoveEmptyEntries));
    }

    private GazetteerPlace? Place(long id) =>
        Array.BinarySearch(_ids, id) is int index and >= 0 ? _places[index] : null;

    // The first name not ordered before the one asked.
    private int First(string folded)
    {
        int low = 0, high = _names.Length;
        while (low < high)
        {
            int middle = (low + high) >>> 1;
            if (string.CompareOrdinal(_names[middle], folded) < 0)
                low = middle + 1;
            else
                high = middle;
        }
        return low;
    }

    private static GazetteerPlace Read(string[] fields) => new(
        long.Parse(fields[1], CultureInfo.InvariantCulture),
        string.Intern(fields[2]),
        double.Parse(fields[3], CultureInfo.InvariantCulture),
        double.Parse(fields[4], CultureInfo.InvariantCulture),
        string.Intern(fields[5]),
        fields[6].Length > 0 ? long.Parse(fields[6], CultureInfo.InvariantCulture) : 0,
        fields[7].Length > 0 ? long.Parse(fields[7], CultureInfo.InvariantCulture) : 0,
        double.Parse(fields[8], CultureInfo.InvariantCulture),
        fields[9].Length > 0 ? string.Intern(fields[9]) : null,
        fields[10],
        fields[11] == fields[10] ? fields[10] : fields[11]);

    private static GeoNamesGazetteer Load()
    {
        using Stream resource = typeof(GeoNamesGazetteer).Assembly.GetManifestResourceStream(ResourceName)
            ?? throw new InvalidOperationException("The place names are not in this build.");
        using var unzipped = new GZipStream(resource, CompressionMode.Decompress);
        using var reader = new StreamReader(unzipped, Encoding.UTF8);
        return new GeoNamesGazetteer(reader);
    }
}

/// <summary>The place a name means (and whether namesakes of other countries were set aside by the person's speech),
/// or none and the places found instead: the namesakes of comparable size (Ambiguous), the places of the name outside
/// the region said, or the places whose name begins so when none is named so.</summary>
internal sealed record GazetteerChoice(
    GazetteerPlace? Place, IReadOnlyList<GazetteerPlace> Candidates, bool Ambiguous, bool NamesakesElsewhere);

/// <summary>
/// A place of GeoNames: its feature code (PPL… a populated place, ADM1 a first-order region, ADM2 or ADM3 a lesser
/// division people name as a town, a comuna or a municipality, PCL… a country;
/// https://www.geonames.org/export/codes.html), coordinates, country code, region and province, population, IANA time
/// zone (none for a country that has several), and its Spanish and English names (it is also found by GeoNames' main
/// and ASCII names). A region or a province of 0 is none.
/// </summary>
internal sealed record GazetteerPlace(
    long Id,
    string FeatureCode,
    double Latitude,
    double Longitude,
    string CountryCode,
    long RegionId,
    long ProvinceId,
    double Population,
    string? TimeZone,
    string NameEs,
    string NameEn)
{
    internal bool IsRegion => FeatureCode == "ADM1";

    internal bool IsDivision => FeatureCode is "ADM2" or "ADM3";

    internal bool IsPopulatedPlace => FeatureCode.StartsWith("PPL", StringComparison.Ordinal);

    // A country's capital, its seat of government or the seat of a first-order region (PPLC, PPLG, PPLA).
    internal bool IsCapital => FeatureCode is "PPLC" or "PPLG" or "PPLA";
}
