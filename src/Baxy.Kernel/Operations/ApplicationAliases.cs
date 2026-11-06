using System.Globalization;
using System.Text;
using System.Text.Json;

namespace Baxy.Kernel.Operations;

/// <summary>
/// Encargo 12: the non-ambiguous abbreviations people use for an application or a channel («wsp» for WhatsApp, «ds»
/// for Discord), one list of equivalences per app. One source in data (src/baxy_mind/data/app_aliases.v1.json,
/// embedded), read here. The owner's only accepted help is a name-equivalence table: no rule of intent, no fixed
/// phrase. Used where the App weighs what the person said against the name of a channel or an app (NetworkEgress's
/// channel guard, SaidApplication's app.open routing): a name is said when the person's words hold it or one of its
/// abbreviations as a whole word. Normalized as the rest of the code does (lower case, no accents, letters and digits
/// only). No application is named in code; the file's own abbreviations are the contract its tests hold this reader to.
/// </summary>
public static class ApplicationAliases
{
    private const string Resource = "Baxy.Kernel.AppAliases.json";

    // Every folded form that names an application (its name and each of its abbreviations) -> that app's abbreviations,
    // each folded and single-spaced. Every form across the data is unique (an abbreviation shared by two apps, or one
    // that is another app's name, is a data bug: refused whole), so an abbreviation names one app only.
    private static readonly Lazy<IReadOnlyDictionary<string, IReadOnlyList<string>>> Loaded = new(Load);

    // Every folded form -> every form of its app, its name first. The forms of one app share one list of abbreviations
    // in Loaded (Read), and its name is the one form that list does not hold.
    private static readonly Lazy<IReadOnlyDictionary<string, IReadOnlyList<string>>> AllForms = new(static () =>
        Loaded.Value.GroupBy(static pair => pair.Value, ReferenceEqualityComparer.Instance)
            .SelectMany(static app =>
            {
                IReadOnlyList<string> aliases = (IReadOnlyList<string>)app.Key!;
                string[] forms = [app.Select(static pair => pair.Key).Single(form => !aliases.Contains(form)), .. aliases];
                return app.Select(pair => KeyValuePair.Create(pair.Key, (IReadOnlyList<string>)forms));
            })
            .ToDictionary(StringComparer.Ordinal));

    /// <summary>
    /// Whether the person's words <paramref name="said"/> name the channel or application <paramref name="name"/> by one
    /// of its non-ambiguous abbreviations, as a whole word (the caller's own check still covers the name itself). False
    /// when the data list no abbreviation for it, or none of them is among their words.
    /// </summary>
    public static bool Names(string? said, string? name)
    {
        if (string.IsNullOrWhiteSpace(said) || name is null
            || !Loaded.Value.TryGetValue(Fold(name), out IReadOnlyList<string>? aliases))
        {
            return false;
        }

        string words = " " + Fold(said) + " ";
        return aliases.Any(alias => words.Contains(" " + alias + " ", StringComparison.Ordinal));
    }

    /// <summary>The non-ambiguous abbreviations the data give <paramref name="name"/> (folded); empty when none.</summary>
    public static IReadOnlyList<string> Of(string? name) =>
        name is not null && Loaded.Value.TryGetValue(Fold(name), out IReadOnlyList<string>? aliases) ? aliases : [];

    /// <summary>
    /// Banco de uso 2026-11-03 (S01, S05, S06): every form of the application <paramref name="name"/> is one of, folded,
    /// its name first and then its abbreviations («disney_plus» is Disney+'s: «disney», …, «disney plus»); empty when
    /// the data do not know it as an application.
    /// </summary>
    public static IReadOnlyList<string> FormsOf(string? name) =>
        name is not null && AllForms.Value.TryGetValue(Fold(name), out IReadOnlyList<string>? forms) ? forms : [];

    private static IReadOnlyDictionary<string, IReadOnlyList<string>> Load()
    {
        using Stream stream = typeof(ApplicationAliases).Assembly.GetManifestResourceStream(Resource)
            ?? throw new InvalidOperationException(Resource);
        using JsonDocument document = JsonDocument.Parse(stream);
        return Read(document);
    }

    /// <summary>
    /// The data's abbreviations by every folded form that names an app. An abbreviation blank once folded, equal to its
    /// own app's name, shared by two apps, or equal to any app's name is a data bug: the whole data is refused (checked
    /// as each form is added), never half read.
    /// </summary>
    internal static IReadOnlyDictionary<string, IReadOnlyList<string>> Read(JsonDocument document)
    {
        var byForm = new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal);
        foreach (JsonProperty entry in document.RootElement.GetProperty("applications").EnumerateObject())
        {
            string name = Fold(entry.Name);
            string[] aliases = [.. entry.Value.GetProperty("aliases").EnumerateArray()
                .Select(alias => Fold(alias.GetString() ?? string.Empty))];
            if (name.Length == 0 || aliases.Any(alias => alias.Length == 0 || alias == name))
            {
                throw new InvalidDataException($"app_aliases: {entry.Name}");
            }

            foreach (string form in (string[])[name, .. aliases])
            {
                if (!byForm.TryAdd(form, aliases))
                {
                    throw new InvalidDataException($"app_aliases: {entry.Name}/{form}");
                }
            }
        }

        return byForm;
    }

    // Lower case without accents, letters and digits only, single spaces: «Whats App» and «whatsapp business» fold the
    // way the data store their abbreviations (and the way NetworkEgress.Folded and SaidFolders.Spoken fold the person's
    // words), so a whole-word match is the same comparison on both sides.
    internal static string Fold(string text)
    {
        var builder = new StringBuilder(text.Length);
        bool pending = false;
        foreach (char character in text.Normalize(NormalizationForm.FormD))
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) == UnicodeCategory.NonSpacingMark)
            {
                continue;
            }

            char lower = char.ToLowerInvariant(character);
            if (lower is (>= 'a' and <= 'z') or (>= '0' and <= '9'))
            {
                if (pending && builder.Length > 0)
                {
                    builder.Append(' ');
                }

                builder.Append(lower);
                pending = false;
            }
            else
            {
                pending = true;
            }
        }

        return builder.ToString();
    }
}
