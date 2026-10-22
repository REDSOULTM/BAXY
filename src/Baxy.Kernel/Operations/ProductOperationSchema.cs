using System.Buffers;
using System.Collections.ObjectModel;
using System.Globalization;
using System.Text;
using System.Text.Json;

namespace Baxy.Kernel.Operations;

#pragma warning disable CA1720 // JSON Schema uses the canonical type names.
[Flags]
public enum OperationJsonType
{
    None = 0,
    Null = 1 << 0,
    Boolean = 1 << 1,
    Integer = 1 << 2,
    Number = 1 << 3,
    String = 1 << 4,
    Array = 1 << 5,
}
#pragma warning restore CA1720

public sealed class OperationArgumentProperty
{
    public OperationArgumentProperty(
        string name,
        OperationJsonType types,
        long? minimum = null,
        long? maximum = null,
        int? minimumLength = null,
        int? maximumLength = null,
        int? maximumUtf8Bytes = null,
        IReadOnlyList<string>? allowedValues = null,
        bool? constantBoolean = null,
        bool nonWhitespace = false,
        OperationJsonType itemTypes = OperationJsonType.None,
        int? minimumItems = null,
        int? maximumItems = null,
        int? itemMaximumUtf8Bytes = null,
        bool itemNonWhitespace = false)
    {
        if (!IsCanonicalPropertyName(name))
        {
            throw new ArgumentException("Argument property names must be canonical camelCase ASCII.", nameof(name));
        }

        ValidateTypes(types, nameof(types));
        if (minimum > maximum)
        {
            throw new ArgumentException("The minimum cannot exceed the maximum.", nameof(minimum));
        }

        if (minimumLength is < 0 || maximumLength is < 0 || minimumLength > maximumLength)
        {
            throw new ArgumentOutOfRangeException(nameof(minimumLength));
        }

        if (maximumUtf8Bytes is < 1)
        {
            throw new ArgumentOutOfRangeException(nameof(maximumUtf8Bytes));
        }

        if (minimumItems is < 0 || maximumItems is < 0 || minimumItems > maximumItems)
        {
            throw new ArgumentOutOfRangeException(nameof(minimumItems));
        }

        if (itemMaximumUtf8Bytes is < 1)
        {
            throw new ArgumentOutOfRangeException(nameof(itemMaximumUtf8Bytes));
        }

        if (types.HasFlag(OperationJsonType.Array))
        {
            ValidateTypes(itemTypes, nameof(itemTypes));
            if (itemTypes.HasFlag(OperationJsonType.Array))
            {
                throw new ArgumentException("Nested arrays are not part of the operation schema subset.", nameof(itemTypes));
            }
        }
        else if (itemTypes != OperationJsonType.None
            || minimumItems.HasValue
            || maximumItems.HasValue
            || itemMaximumUtf8Bytes.HasValue
            || itemNonWhitespace)
        {
            throw new ArgumentException("Array item constraints require the array type.", nameof(itemTypes));
        }

        if ((minimum.HasValue || maximum.HasValue)
            && !types.HasFlag(OperationJsonType.Integer))
        {
            throw new ArgumentException("Numeric ranges require the integer type.", nameof(types));
        }

        if ((minimumLength.HasValue
                || maximumLength.HasValue
                || maximumUtf8Bytes.HasValue
                || nonWhitespace)
            && !types.HasFlag(OperationJsonType.String))
        {
            throw new ArgumentException("String constraints require the string type.", nameof(types));
        }

        string[] values = allowedValues?.ToArray() ?? [];
        if (values.Length > 0)
        {
            if (!types.HasFlag(OperationJsonType.String)
                || values.Any(string.IsNullOrEmpty)
                || values.Distinct(StringComparer.Ordinal).Count() != values.Length
                || !values.SequenceEqual(values.Order(StringComparer.Ordinal), StringComparer.Ordinal))
            {
                throw new ArgumentException(
                    "Allowed values must be unique, non-empty, ordinally sorted strings.",
                    nameof(allowedValues));
            }
        }

        if (constantBoolean.HasValue && !types.HasFlag(OperationJsonType.Boolean))
        {
            throw new ArgumentException("A Boolean constant requires the Boolean type.", nameof(types));
        }

        Name = name;
        Types = types;
        Minimum = minimum;
        Maximum = maximum;
        MinimumLength = minimumLength;
        MaximumLength = maximumLength;
        MaximumUtf8Bytes = maximumUtf8Bytes;
        AllowedValues = Array.AsReadOnly(values);
        ConstantBoolean = constantBoolean;
        NonWhitespace = nonWhitespace;
        ItemTypes = itemTypes;
        MinimumItems = minimumItems;
        MaximumItems = maximumItems;
        ItemMaximumUtf8Bytes = itemMaximumUtf8Bytes;
        ItemNonWhitespace = itemNonWhitespace;
    }

    public string Name { get; }

    public OperationJsonType Types { get; }

    public long? Minimum { get; }

    public long? Maximum { get; }

    public int? MinimumLength { get; }

    public int? MaximumLength { get; }

    public int? MaximumUtf8Bytes { get; }

    public IReadOnlyList<string> AllowedValues { get; }

    public bool? ConstantBoolean { get; }

    public bool NonWhitespace { get; }

    public OperationJsonType ItemTypes { get; }

    public int? MinimumItems { get; }

    public int? MaximumItems { get; }

    public int? ItemMaximumUtf8Bytes { get; }

    public bool ItemNonWhitespace { get; }

    private static void ValidateTypes(OperationJsonType types, string parameterName)
    {
        const OperationJsonType all = OperationJsonType.Null
            | OperationJsonType.Boolean
            | OperationJsonType.Integer
            | OperationJsonType.Number
            | OperationJsonType.String
            | OperationJsonType.Array;
        if (types == OperationJsonType.None || (types & ~all) != 0)
        {
            throw new ArgumentOutOfRangeException(parameterName);
        }
    }

    private static bool IsCanonicalPropertyName(string? value)
    {
        if (string.IsNullOrEmpty(value) || value[0] is < 'a' or > 'z')
        {
            return false;
        }

        return value.All(static character => character is >= 'a' and <= 'z'
            or >= 'A' and <= 'Z'
            or >= '0' and <= '9');
    }
}

public sealed class OperationArgumentsSchema
{
    public OperationArgumentsSchema(
        IReadOnlyList<OperationArgumentProperty> properties,
        IReadOnlyList<string> required)
    {
        ArgumentNullException.ThrowIfNull(properties);
        ArgumentNullException.ThrowIfNull(required);
        OperationArgumentProperty[] propertyCopy = properties.ToArray();
        string[] requiredCopy = required.ToArray();
        if (propertyCopy.Any(static property => property is null)
            || !propertyCopy.Select(static property => property.Name)
                .SequenceEqual(
                    propertyCopy.Select(static property => property.Name)
                        .Order(StringComparer.Ordinal),
                    StringComparer.Ordinal)
            || propertyCopy.Select(static property => property.Name)
                .Distinct(StringComparer.Ordinal).Count() != propertyCopy.Length)
        {
            throw new ArgumentException(
                "Schema properties must be unique and ordinally sorted.",
                nameof(properties));
        }

        if (!requiredCopy.SequenceEqual(requiredCopy.Order(StringComparer.Ordinal), StringComparer.Ordinal)
            || requiredCopy.Distinct(StringComparer.Ordinal).Count() != requiredCopy.Length
            || requiredCopy.Any(name => !propertyCopy.Any(property =>
                string.Equals(property.Name, name, StringComparison.Ordinal))))
        {
            throw new ArgumentException(
                "Required properties must be unique, ordinally sorted schema properties.",
                nameof(required));
        }

        Properties = Array.AsReadOnly(propertyCopy);
        Required = Array.AsReadOnly(requiredCopy);
        CanonicalJson = BuildCanonicalJson();
    }

    public string Type { get; } = "object";

    public IReadOnlyList<OperationArgumentProperty> Properties { get; }

    public IReadOnlyList<string> Required { get; }

    public string CanonicalJson { get; }

    private string BuildCanonicalJson()
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteString("type", Type);
            writer.WritePropertyName("properties");
            writer.WriteStartObject();
            foreach (OperationArgumentProperty property in Properties)
            {
                writer.WritePropertyName(property.Name);
                writer.WriteStartObject();
                WriteTypes(writer, "type", property.Types);
                if (property.AllowedValues.Count > 0)
                {
                    writer.WritePropertyName("enum");
                    writer.WriteStartArray();
                    if (property.Types.HasFlag(OperationJsonType.Null))
                    {
                        writer.WriteNullValue();
                    }

                    foreach (string allowed in property.AllowedValues)
                    {
                        writer.WriteStringValue(allowed);
                    }

                    writer.WriteEndArray();
                }

                WriteNumber(writer, "minimum", property.Minimum);
                WriteNumber(writer, "maximum", property.Maximum);
                WriteNumber(writer, "minLength", property.MinimumLength);
                WriteNumber(writer, "maxLength", property.MaximumLength);
                WriteNumber(writer, "x-maxUtf8Bytes", property.MaximumUtf8Bytes);
                if (property.NonWhitespace)
                {
                    writer.WriteBoolean("x-nonWhitespace", true);
                }

                if (property.ConstantBoolean.HasValue)
                {
                    writer.WriteBoolean("const", property.ConstantBoolean.Value);
                }

                WriteNumber(writer, "minItems", property.MinimumItems);
                WriteNumber(writer, "maxItems", property.MaximumItems);
                if (property.ItemTypes != OperationJsonType.None)
                {
                    writer.WritePropertyName("items");
                    writer.WriteStartObject();
                    WriteTypes(writer, "type", property.ItemTypes);
                    WriteNumber(writer, "x-maxUtf8Bytes", property.ItemMaximumUtf8Bytes);
                    if (property.ItemNonWhitespace)
                    {
                        writer.WriteBoolean("x-nonWhitespace", true);
                    }

                    writer.WriteEndObject();
                }

                writer.WriteEndObject();
            }

            writer.WriteEndObject();
            writer.WritePropertyName("required");
            writer.WriteStartArray();
            foreach (string required in Required)
            {
                writer.WriteStringValue(required);
            }

            writer.WriteEndArray();
            writer.WriteBoolean("additionalProperties", false);
            writer.WriteEndObject();
        }

        return Encoding.UTF8.GetString(buffer.WrittenSpan);
    }

    private static void WriteTypes(
        Utf8JsonWriter writer,
        string propertyName,
        OperationJsonType types)
    {
        string[] names = EnumerateTypes(types).ToArray();
        writer.WritePropertyName(propertyName);
        if (names.Length == 1)
        {
            writer.WriteStringValue(names[0]);
            return;
        }

        writer.WriteStartArray();
        foreach (string name in names)
        {
            writer.WriteStringValue(name);
        }

        writer.WriteEndArray();
    }

    private static IEnumerable<string> EnumerateTypes(OperationJsonType types)
    {
        if (types.HasFlag(OperationJsonType.Null))
        {
            yield return "null";
        }

        if (types.HasFlag(OperationJsonType.Boolean))
        {
            yield return "boolean";
        }

        if (types.HasFlag(OperationJsonType.Integer))
        {
            yield return "integer";
        }

        if (types.HasFlag(OperationJsonType.Number))
        {
            yield return "number";
        }

        if (types.HasFlag(OperationJsonType.String))
        {
            yield return "string";
        }

        if (types.HasFlag(OperationJsonType.Array))
        {
            yield return "array";
        }
    }

    private static void WriteNumber(Utf8JsonWriter writer, string name, long? value)
    {
        if (value.HasValue)
        {
            writer.WriteNumber(name, value.Value);
        }
    }
}

public sealed class ProductOperationDescriptor
{
    internal ProductOperationDescriptor(
        string name,
        OperationArgumentsSchema argumentsSchema,
        string risk,
        string verifierContractId,
        string description,
        bool? requiresObservedEffect = null,
        IReadOnlyList<OperationEffect>? effects = null,
        TimeSpan? budget = null)
    {
        if (!Baxy.Contracts.ContractValidator.IsOperationName(name))
        {
            throw new ArgumentException("The operation name is not canonical.", nameof(name));
        }

        ArgumentNullException.ThrowIfNull(argumentsSchema);
        if (!Baxy.Contracts.OperationRisks.IsKnown(risk))
        {
            throw new ArgumentException("The operation risk is not canonical.", nameof(risk));
        }

        if (!IsCanonicalContractId(verifierContractId))
        {
            throw new ArgumentException("The verifier contract identifier is not canonical.", nameof(verifierContractId));
        }

        if (string.IsNullOrWhiteSpace(description))
        {
            throw new ArgumentException("The operation description is required.", nameof(description));
        }

        Name = name;
        ArgumentsSchema = argumentsSchema;
        Risk = risk;
        VerifierContractId = verifierContractId;
        Description = description;
        if (budget <= TimeSpan.Zero)
        {
            throw new ArgumentOutOfRangeException(nameof(budget), "An operation's budget is a positive time.");
        }

        RequiresObservedEffect = requiresObservedEffect ?? (risk != Baxy.Contracts.OperationRisks.ReadOnly);
        Effects = effects ?? [];
        Budget = budget;
        if (Effects.SelectMany(static effect => effect.When).Any(condition =>
                !argumentsSchema.Properties.Any(property => property.Name == condition.Argument)))
        {
            throw new ArgumentException("An effect's condition names an argument the schema does not have.",
                nameof(effects));
        }

        EffectKinds = Effects.Select(static effect => effect.Kind).Distinct(StringComparer.Ordinal)
            .Order(StringComparer.Ordinal).ToArray();
    }

    public string Name { get; }

    public OperationArgumentsSchema ArgumentsSchema { get; }

    public string Risk { get; }

    public string VerifierContractId { get; }

    public string Description { get; }

    // Privacy risk and requiring an observed mutation are separate contract facts.
    public bool RequiresObservedEffect { get; }

    /// <summary>Where its effect lands besides its risk (<see cref="Baxy.Contracts.OperationEffects"/>).</summary>
    public IReadOnlyList<OperationEffect> Effects { get; }

    /// <summary>The kinds of <see cref="Effects"/>, each once, in order: what the operation may do with some call.</summary>
    public IReadOnlyList<string> EffectKinds { get; }

    /// <summary>
    /// How long its provider may take, declared only where it takes longer than an ordinary call (al máximo, flujos):
    /// the App waits that long for its answer before its margin starts, instead of the same time for every call.
    /// </summary>
    public TimeSpan? Budget { get; }

    /// <summary>Whether this call, with these arguments, has that effect.</summary>
    public bool Has(string effect, JsonElement arguments) =>
        Effects.Any(declared => declared.Kind == effect && declared.Applies(arguments));

    private static bool IsCanonicalContractId(string? value)
    {
        if (string.IsNullOrEmpty(value) || value.Length > 128)
        {
            return false;
        }

        bool segmentStart = true;
        foreach (char character in value)
        {
            if (character == '.')
            {
                if (segmentStart)
                {
                    return false;
                }

                segmentStart = true;
                continue;
            }

            if (segmentStart)
            {
                if (character is < 'a' or > 'z')
                {
                    return false;
                }

                segmentStart = false;
            }
            else if (character is not (>= 'a' and <= 'z')
                and not (>= '0' and <= '9'))
            {
                return false;
            }
        }

        return !segmentStart;
    }
}

/// <summary>
/// An argument a call got wrong and what is wrong with it (<see cref="OperationArgumentValidator.Problems"/>), with what
/// lets the model correct it in one turn (P5.3): the arguments the tool takes, the values the argument takes when they
/// are few, and the one of them nearest to what was given when it is close enough to be the one meant.
/// </summary>
public sealed record ArgumentProblem(string Name, string Problem)
{
    /// <summary>The arguments the tool takes, for one it does not take.</summary>
    public IReadOnlyList<string>? Accepted { get; init; }

    /// <summary>The value the argument takes (or the argument the tool takes) nearest to the one given.</summary>
    public string? Nearest { get; init; }

    /// <summary>The values the argument takes, when they are <see cref="OperationArgumentValidator.AllowedShown"/> or fewer.</summary>
    public IReadOnlyList<string>? Allowed { get; init; }

    /// <summary>The arguments of which a call gives exactly one (<see cref="ExactlyOneOf"/>).</summary>
    public IReadOnlyList<string>? OneOf { get; init; }

    /// <summary>A required argument the call does not give.</summary>
    public static ArgumentProblem Missing(string name) => new(name, "required and missing");

    /// <summary>A call that gives none or more than one of arguments of which it gives exactly one.</summary>
    public static ArgumentProblem ExactlyOneOf(params string[] names) =>
        new(names[0], "exactly one of oneOf must be given") { OneOf = names };
}

public static class OperationArgumentValidator
{
    /// <summary>How many values of an argument a refusal lists (<see cref="ArgumentProblem.Allowed"/>).</summary>
    public const int AllowedShown = 12;

    public static bool IsValid(JsonElement arguments, OperationArgumentsSchema schema)
    {
        ArgumentNullException.ThrowIfNull(schema);
        if (arguments.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        var seen = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonProperty supplied in arguments.EnumerateObject())
        {
            if (!seen.Add(supplied.Name))
            {
                return false;
            }

            OperationArgumentProperty? contract = schema.Properties.FirstOrDefault(property =>
                string.Equals(property.Name, supplied.Name, StringComparison.Ordinal));
            if (contract is null || !IsValidValue(supplied.Value, contract))
            {
                return false;
            }
        }

        return schema.Required.All(seen.Contains);
    }

    /// <summary>
    /// The arguments that make <see cref="IsValid"/> false, each with what is wrong in words the model can act on
    /// (audit 2026-10-15: «invalid_arguments» alone did not say which argument nor what it takes): one not declared,
    /// one given twice, one whose value the schema refuses (with what it expects), then each required one missing. In
    /// the order seen; never the value given, so a private argument stays private. Empty for arguments the schema
    /// takes, and one problem for a non-object. P5.3: one the tool does not take carries the ones it does
    /// (<see cref="ArgumentProblem.Accepted"/>), and a value outside an argument's values carries them when they are
    /// few (<see cref="ArgumentProblem.Allowed"/>); either carries the nearest name or value when one is close enough.
    /// </summary>
    public static IReadOnlyList<ArgumentProblem> Problems(JsonElement arguments, OperationArgumentsSchema schema)
    {
        ArgumentNullException.ThrowIfNull(schema);
        var problems = new List<ArgumentProblem>();
        if (arguments.ValueKind != JsonValueKind.Object)
        {
            problems.Add(new ArgumentProblem("arguments", "expected an object"));
            return problems;
        }

        // A name already given is never the one suggested for another.
        HashSet<string> given = arguments.EnumerateObject().Select(static property => property.Name)
            .ToHashSet(StringComparer.Ordinal);
        var seen = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonProperty supplied in arguments.EnumerateObject())
        {
            OperationArgumentProperty? contract = schema.Properties.FirstOrDefault(property =>
                string.Equals(property.Name, supplied.Name, StringComparison.Ordinal));
            ArgumentProblem? problem = !seen.Add(supplied.Name) ? new ArgumentProblem(supplied.Name, "given twice")
                : contract is null ? new ArgumentProblem(supplied.Name, "not an argument of this tool")
                {
                    Accepted = [.. schema.Properties.Select(static property => property.Name)],
                    Nearest = Nearest(supplied.Name, schema.Properties.Select(static property => property.Name)
                        .Where(name => !given.Contains(name))),
                }
                : IsValidValue(supplied.Value, contract) ? null
                : contract.AllowedValues.Count > 0 ? NotAllowed(supplied, contract)
                : new ArgumentProblem(supplied.Name, "expected " + Expected(contract));
            if (problem is not null && problems.All(known => known.Name != supplied.Name))
            {
                problems.Add(problem);
            }
        }

        problems.AddRange(schema.Required.Where(name => !seen.Contains(name))
            .Select(ArgumentProblem.Missing));
        return problems;
    }

    // A value outside an argument's values: the values when few, and the nearest to a text given.
    private static ArgumentProblem NotAllowed(JsonProperty supplied, OperationArgumentProperty contract) =>
        new(supplied.Name, contract.Types.HasFlag(OperationJsonType.Null)
            ? "expected one of the allowed values or null"
            : "expected one of the allowed values")
        {
            Allowed = contract.AllowedValues.Count <= AllowedShown ? contract.AllowedValues : null,
            Nearest = supplied.Value.ValueKind == JsonValueKind.String
                ? Nearest(supplied.Value.GetString()!, contract.AllowedValues)
                : null,
        };

    /// <summary>
    /// The candidate meant by <paramref name="given"/>, compared without case and without the separators «_», «-», «.»
    /// and spaces («app_id» is «appId», «cpu memory» is «cpu_memory»): the one equal to it; else, for three characters
    /// or more, the one it begins («batt» is «battery», «window» is «windowId»); else the nearest by edit distance,
    /// when close enough to be the one meant: at most a third of the longer of the two (at least one edit) and fewer
    /// edits than its length. Null when two are as near («gpu» begins «gpu_usage» and «gpu_identity»).
    /// </summary>
    private static string? Nearest(string given, IEnumerable<string> candidates)
    {
        string folded = Folded(given);
        (string Name, string Folded)[] targets = [.. candidates.Select(static candidate => (candidate, Folded(candidate)))];
        string[] equal = [.. targets.Where(target => target.Folded == folded).Select(static target => target.Name)];
        if (equal.Length > 0)
        {
            return equal.Length == 1 ? equal[0] : null;
        }

        string[] begun = folded.Length < 3
            ? []
            : [.. targets.Where(target => target.Folded.StartsWith(folded, StringComparison.Ordinal))
                .Select(static target => target.Name)];
        if (begun.Length > 0)
        {
            return begun.Length == 1 ? begun[0] : null;
        }

        string? nearest = null;
        int nearestDistance = int.MaxValue;
        int nearestLength = 0;
        bool tied = false;
        foreach ((string candidate, string target) in targets)
        {
            int distance = EditDistance(folded, target);
            if (distance < nearestDistance)
            {
                (nearest, nearestDistance, nearestLength, tied) = (candidate, distance, target.Length, false);
            }
            else if (distance == nearestDistance)
            {
                tied = true;
            }
        }

        int longer = Math.Max(folded.Length, nearestLength);
        return nearest is not null && !tied && nearestDistance < longer
            && nearestDistance <= Math.Max(1, (longer + 1) / 3)
                ? nearest
                : null;
    }

    private static string Folded(string value)
    {
        var folded = new StringBuilder(value.Length);
        foreach (char character in value)
        {
            if (character is not ('_' or '-' or '.' or ' '))
            {
                folded.Append(char.ToLowerInvariant(character));
            }
        }

        return folded.ToString();
    }

    // Levenshtein over two rows.
    private static int EditDistance(string left, string right)
    {
        int[] previous = new int[right.Length + 1];
        int[] current = new int[right.Length + 1];
        for (int column = 0; column <= right.Length; column++)
        {
            previous[column] = column;
        }

        for (int row = 1; row <= left.Length; row++)
        {
            current[0] = row;
            for (int column = 1; column <= right.Length; column++)
            {
                int substitution = previous[column - 1] + (left[row - 1] == right[column - 1] ? 0 : 1);
                current[column] = Math.Min(substitution, Math.Min(previous[column], current[column - 1]) + 1);
            }

            (previous, current) = (current, previous);
        }

        return previous[right.Length];
    }

    // What a declared argument without a list of values takes, as its schema says it.
    private static string Expected(OperationArgumentProperty contract)
    {
        if (contract.ConstantBoolean is bool constant)
        {
            return constant ? "true" : "false";
        }

        var parts = new List<string>();
        foreach ((OperationJsonType type, string word) in new[]
                 {
                     (OperationJsonType.String, "text"), (OperationJsonType.Integer, "an integer"),
                     (OperationJsonType.Boolean, "true or false"), (OperationJsonType.Array, "a list"),
                     (OperationJsonType.Number, "a number"), (OperationJsonType.Null, "null"),
                 })
        {
            if (contract.Types.HasFlag(type))
            {
                parts.Add(word);
            }
        }

        string expected = string.Join(" or ", parts);
        if (contract.Minimum.HasValue || contract.Maximum.HasValue)
        {
            expected += $" from {contract.Minimum?.ToString(CultureInfo.InvariantCulture) ?? "any"}"
                + $" to {contract.Maximum?.ToString(CultureInfo.InvariantCulture) ?? "any"}";
        }

        if (contract.NonWhitespace)
        {
            expected += ", not empty";
        }

        if (contract.MinimumLength is int minimumLength and > 0)
        {
            expected += $", at least {minimumLength.ToString(CultureInfo.InvariantCulture)} characters";
        }

        if (contract.MaximumUtf8Bytes is int bytes)
        {
            expected += $", at most {bytes.ToString(CultureInfo.InvariantCulture)} bytes";
        }
        else if (contract.MaximumLength is int length)
        {
            expected += $", at most {length.ToString(CultureInfo.InvariantCulture)} characters";
        }

        if (contract.MinimumItems.HasValue || contract.MaximumItems.HasValue)
        {
            expected += $", {contract.MinimumItems?.ToString(CultureInfo.InvariantCulture) ?? "0"}"
                + $" to {contract.MaximumItems?.ToString(CultureInfo.InvariantCulture) ?? "any"} items";
        }

        if (contract.Types.HasFlag(OperationJsonType.Array) && contract.ItemTypes != OperationJsonType.None)
        {
            expected += contract.ItemTypes.HasFlag(OperationJsonType.String) ? ", each item text" : ", each item a value";
            if (contract.ItemNonWhitespace)
            {
                expected += " not empty";
            }

            if (contract.ItemMaximumUtf8Bytes is int itemBytes)
            {
                expected += $" of at most {itemBytes.ToString(CultureInfo.InvariantCulture)} bytes";
            }
        }

        return expected;
    }

    private static bool IsValidValue(JsonElement value, OperationArgumentProperty contract)
    {
        if (!MatchesType(value, contract.Types))
        {
            return false;
        }

        if (value.ValueKind == JsonValueKind.String)
        {
            string text = value.GetString()!;
            if (contract.MinimumLength.HasValue && text.Length < contract.MinimumLength.Value
                || contract.MaximumLength.HasValue && text.Length > contract.MaximumLength.Value
                || contract.MaximumUtf8Bytes.HasValue
                    && Encoding.UTF8.GetByteCount(text) > contract.MaximumUtf8Bytes.Value
                || contract.NonWhitespace && string.IsNullOrWhiteSpace(text)
                || contract.AllowedValues.Count > 0
                    && !contract.AllowedValues.Contains(text, StringComparer.Ordinal))
            {
                return false;
            }
        }

        if (value.ValueKind == JsonValueKind.Number
            && contract.Types.HasFlag(OperationJsonType.Integer))
        {
            if (!value.TryGetInt64(out long number)
                || !string.Equals(
                    value.GetRawText(),
                    number.ToString(CultureInfo.InvariantCulture),
                    StringComparison.Ordinal)
                || contract.Minimum.HasValue && number < contract.Minimum.Value
                || contract.Maximum.HasValue && number > contract.Maximum.Value)
            {
                return false;
            }
        }

        if (value.ValueKind is JsonValueKind.True or JsonValueKind.False
            && contract.ConstantBoolean.HasValue
            && value.GetBoolean() != contract.ConstantBoolean.Value)
        {
            return false;
        }

        if (value.ValueKind == JsonValueKind.Array)
        {
            int count = value.GetArrayLength();
            if (contract.MinimumItems.HasValue && count < contract.MinimumItems.Value
                || contract.MaximumItems.HasValue && count > contract.MaximumItems.Value)
            {
                return false;
            }

            foreach (JsonElement item in value.EnumerateArray())
            {
                if (!MatchesType(item, contract.ItemTypes))
                {
                    return false;
                }

                if (item.ValueKind == JsonValueKind.String)
                {
                    string text = item.GetString()!;
                    if (contract.ItemMaximumUtf8Bytes.HasValue
                            && Encoding.UTF8.GetByteCount(text) > contract.ItemMaximumUtf8Bytes.Value
                        || contract.ItemNonWhitespace && string.IsNullOrWhiteSpace(text))
                    {
                        return false;
                    }
                }
            }
        }

        return true;
    }

    private static bool MatchesType(JsonElement value, OperationJsonType types) =>
        value.ValueKind switch
        {
            JsonValueKind.Null => types.HasFlag(OperationJsonType.Null),
            JsonValueKind.True or JsonValueKind.False => types.HasFlag(OperationJsonType.Boolean),
            JsonValueKind.Number => types.HasFlag(OperationJsonType.Integer)
                || types.HasFlag(OperationJsonType.Number),
            JsonValueKind.String => types.HasFlag(OperationJsonType.String),
            JsonValueKind.Array => types.HasFlag(OperationJsonType.Array),
            _ => false,
        };
}
