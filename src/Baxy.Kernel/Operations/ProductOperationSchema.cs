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

public enum ToolExposure
{
    Public,
    Internal,
}

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

    public bool AdditionalProperties { get; }

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
        ToolExposure toolExposure,
        string description)
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

        if (!Enum.IsDefined(toolExposure))
        {
            throw new ArgumentOutOfRangeException(nameof(toolExposure));
        }

        if (string.IsNullOrWhiteSpace(description))
        {
            throw new ArgumentException("The operation description is required.", nameof(description));
        }

        Name = name;
        ArgumentsSchema = argumentsSchema;
        Risk = risk;
        VerifierContractId = verifierContractId;
        ToolExposure = toolExposure;
        Description = description;
    }

    public string Name { get; }

    public OperationArgumentsSchema ArgumentsSchema { get; }

    public string Risk { get; }

    public string VerifierContractId { get; }

    public ToolExposure ToolExposure { get; }

    public string Description { get; }

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

public static class OperationArgumentValidator
{
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
