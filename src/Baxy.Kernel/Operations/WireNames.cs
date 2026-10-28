namespace Baxy.Kernel.Operations;

/// <summary>
/// The name the model sees for each operation (its wire name), by the mind's own rule (src/baxy_mind/wire.py, Wires):
/// the operation's id with «.» → «_», except where that name would be a proper prefix of another name the model is shown
/// (audio_volume ⊂ audio_volume_adjust), which gets «_set» (or «_2set», «_3set»… when that clashes by shape with
/// another name). A text the App or a provider gives the model names a call by this name, the one the model sees
/// (tests/fixtures/wire_names.v1.json, checked against the mind and against this class, keeps them the same).
/// </summary>
public sealed class WireNames
{
    private const string Suffix = "set";

    private static readonly Lazy<WireNames> ProductNames = new(static () => new WireNames(
        ProductCatalog.ToolDescriptors.Select(static descriptor => descriptor.Name), MindTools));

    private readonly Dictionary<string, string> _names;

    /// <summary>The names the mind shows the model besides the catalog's (mind.py: ASK_USER, CONFIRM, CALCULATE).</summary>
    public static IReadOnlyList<string> MindTools { get; } = ["ask_user", "confirm_pending", "calculate"];

    /// <summary>The wire names of the product catalog, which the App sends whole to the mind.</summary>
    public static WireNames Product => ProductNames.Value;

    public WireNames(IEnumerable<string> operations, IEnumerable<string> fixedNames)
    {
        ArgumentNullException.ThrowIfNull(operations);
        ArgumentNullException.ThrowIfNull(fixedNames);
        // In the order given, as the mind's dict keeps it: the suffix a short name gets depends on the ones before it.
        List<string> order = [.. operations.Distinct(StringComparer.Ordinal)];
        string[] fixedShown = [.. fixedNames];
        var names = order.ToDictionary(static op => op, Plain, StringComparer.Ordinal);
        // Each round gives every short name a suffix that clashes with no name that stays; a renamed name that is still
        // short is renamed again in the next round, and each round renames, so the names of a catalog settle.
        for (int round = 0; round <= order.Count; round++)
        {
            List<string> shorts = [.. order.Where(op => IsShort(op, order, names, fixedShown))];
            if (shorts.Count == 0)
                break;
            var shortSet = new HashSet<string>(shorts, StringComparer.Ordinal);
            List<string> taken = [.. fixedShown, .. order.Where(op => !shortSet.Contains(op)).Select(op => names[op])];
            foreach (string op in shorts)
            {
                string named = names[op];
                for (int k = 1; ; k++)
                {
                    string candidate = $"{named}_{(k > 1 ? k.ToString(System.Globalization.CultureInfo.InvariantCulture) : "")}{Suffix}";
                    if (!Clashes(candidate, taken))
                    {
                        names[op] = candidate;
                        break;
                    }
                }

                taken.Add(names[op]);
            }
        }

        _names = names;
    }

    /// <summary>The wire name of an operation of the product catalog, as the model sees it.</summary>
    public static string Of(string operation) => Product.Name(operation);

    /// <summary>The wire name of an operation; one this catalog does not have keeps its plain name.</summary>
    public string Name(string operation)
    {
        ArgumentNullException.ThrowIfNull(operation);
        return _names.TryGetValue(operation, out string? name) ? name : Plain(operation);
    }

    private static string Plain(string operation) => operation.Replace('.', '_');

    // The operation whose name is a prefix of another name shown (or the same name as another one).
    private static bool IsShort(
        string op, List<string> order, Dictionary<string, string> names, string[] fixedShown)
    {
        string name = names[op];
        return order.Any(other => !string.Equals(other, op, StringComparison.Ordinal)
                && names[other].StartsWith(name, StringComparison.Ordinal))
            || fixedShown.Any(shown => shown.StartsWith(name, StringComparison.Ordinal));
    }

    // What two names may not share: one a prefix of the other, the same letters but for «_», or the same parts in
    // another order.
    private static bool Clashes(string name, List<string> others)
    {
        string letters = name.Replace("_", "", StringComparison.Ordinal);
        string[] parts = Parts(name);
        return others.Any(other => other.StartsWith(name, StringComparison.Ordinal)
            || name.StartsWith(other, StringComparison.Ordinal)
            || string.Equals(other.Replace("_", "", StringComparison.Ordinal), letters, StringComparison.Ordinal)
            || Parts(other).SequenceEqual(parts, StringComparer.Ordinal));
    }

    private static string[] Parts(string name) => [.. name.Split('_').Order(StringComparer.Ordinal)];
}
