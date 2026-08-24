using System.Buffers;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Baxy.App;

internal sealed class DurableRetryStore
{
    // This plaintext outbox provides crash safety and accidental-corruption detection,
    // not confidentiality or authenticated tamper evidence.
    internal const int MaximumEntries = 128;
    internal const int MaximumFileBytes = 1_048_576;
    internal const int MaximumArgumentsBytes = 65_536;
    private const int CurrentVersion = 1;
    private const int MaximumArgumentsDepth = 32;
    private readonly string _path;
    private readonly Action<string>? _beforeCommitVerification;

    public DurableRetryStore(string path)
        : this(path, beforeCommitVerification: null)
    {
    }

    internal DurableRetryStore(string path, Action<string>? beforeCommitVerification)
    {
        _path = PreparePath(path);
        _beforeCommitVerification = beforeCommitVerification;
    }

    public static string ResolveDefaultPath()
    {
        string dataRoot = MemoryOperationProtector.ResolveDataRoot();
        return Path.Combine(dataRoot, "shell", "retry-outbox.v1.json");
    }

    public IReadOnlyList<PreparedOperation> Load()
    {
        EnsureSafePath(_path);
        if (!File.Exists(_path))
        {
            return [];
        }

        byte[] utf8 = ReadBoundedFile(_path);
        if (utf8.Length == 0)
        {
            throw new InvalidDataException("La cola durable está vacía o truncada.");
        }

        DurableRetryDocument document;
        try
        {
            using (JsonDocument structure = JsonDocument.Parse(utf8))
            {
                ValidateNoDuplicateProperties(structure.RootElement, depth: 0);
            }

            document = JsonSerializer.Deserialize(
                    utf8,
                    DurableRetryJsonContext.Default.DurableRetryDocument)
                ?? throw new InvalidDataException("La cola durable contiene null.");
        }
        catch (JsonException exception)
        {
            throw new InvalidDataException("La cola durable contiene JSON inválido.", exception);
        }

        if (document.Version != CurrentVersion)
        {
            throw new InvalidDataException("La versión de la cola durable no es compatible.");
        }

        if (document.Entries is null || document.Entries.Count > MaximumEntries)
        {
            throw new InvalidDataException("La cola durable supera el límite de entradas.");
        }

        var operations = new List<PreparedOperation>(document.Entries.Count);
        var identities = new HashSet<string>(StringComparer.Ordinal);
        var invocationIds = new HashSet<string>(StringComparer.Ordinal);
        foreach (DurableRetryEntry entry in document.Entries)
        {
            PreparedOperation operation = RestoreAndValidate(entry);
            if (!identities.Add(operation.IdentityKey))
            {
                throw new InvalidDataException("La cola durable contiene una identidad duplicada.");
            }

            if (!invocationIds.Add(operation.InvocationId))
            {
                throw new InvalidDataException("La cola durable contiene un ID de invocación duplicado.");
            }

            operations.Add(operation);
        }

        return operations;
    }

    /// <summary>
    /// Carga la cola durable apartando el archivo cuando resultó ilegible.
    /// Un outbox corrupto no puede impedir que BAXY vuelva a arrancar —el
    /// «reintentar» de la ventana volvería a leerlo y fallaría igual, para
    /// siempre—, pero tampoco se borra en silencio: puede contener
    /// operaciones cuyo efecto quizá ocurrió, así que se conserva en disco
    /// con nombre de cuarentena y quien llama lo dice en voz alta.
    /// </summary>
    public DurableRetryLoad LoadOrQuarantine()
    {
        try
        {
            return new DurableRetryLoad(Load(), UnreadablePath: null);
        }
        catch (InvalidDataException)
        {
            return new DurableRetryLoad([], Quarantine());
        }
    }

    private string Quarantine()
    {
        string candidate = _path
            + ".unreadable-"
            + DateTime.UtcNow.ToString(
                "yyyyMMdd'T'HHmmssfff'Z'",
                System.Globalization.CultureInfo.InvariantCulture);
        try
        {
            File.Move(_path, candidate);
            return candidate;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // Apartarlo falló: el archivo sigue donde estaba y eso es lo que
            // se reporta. Conservar la ruta real vale más que una ruta que no
            // existe.
            return _path;
        }
    }

    public void Save(IReadOnlyCollection<PreparedOperation> operations)
    {
        ArgumentNullException.ThrowIfNull(operations);
        if (operations.Count > MaximumEntries)
        {
            throw new InvalidOperationException("La cola durable alcanzó su límite de entradas.");
        }

        EnsureSafePath(_path);
        var entries = new List<DurableRetryEntry>(operations.Count);
        var identities = new HashSet<string>(StringComparer.Ordinal);
        var invocationIds = new HashSet<string>(StringComparer.Ordinal);
        foreach (PreparedOperation operation in operations)
        {
            ArgumentNullException.ThrowIfNull(operation);
            JsonElement arguments = operation.Arguments;
            ValidateEntry(
                operation.OperationName,
                arguments,
                operation.MissionId,
                operation.InvocationId);
            if (!identities.Add(operation.IdentityKey)
                || !invocationIds.Add(operation.InvocationId))
            {
                throw new InvalidOperationException("La cola durable no admite identidades duplicadas.");
            }

            entries.Add(new DurableRetryEntry
            {
                Operation = operation.OperationName,
                Arguments = arguments,
                MissionId = operation.MissionId,
                InvocationId = operation.InvocationId,
                Checksum = ComputeEntryChecksum(
                    operation.OperationName,
                    arguments,
                    operation.MissionId,
                    operation.InvocationId),
            });
        }

        var document = new DurableRetryDocument
        {
            Version = CurrentVersion,
            Entries = entries,
        };
        byte[] utf8 = JsonSerializer.SerializeToUtf8Bytes(
            document,
            DurableRetryJsonContext.Default.DurableRetryDocument);
        if (utf8.Length > MaximumFileBytes)
        {
            throw new InvalidOperationException("La cola durable supera su límite de tamaño.");
        }

        WriteAtomically(utf8);
    }

    private static PreparedOperation RestoreAndValidate(DurableRetryEntry entry)
    {
        if (entry is null)
        {
            throw new InvalidDataException("La cola durable contiene una entrada null.");
        }

        try
        {
            ValidateEntry(entry.Operation, entry.Arguments, entry.MissionId, entry.InvocationId);
            ValidateChecksum(entry.Checksum);
            string expectedChecksum = ComputeEntryChecksum(
                entry.Operation!,
                entry.Arguments,
                entry.MissionId!,
                entry.InvocationId!);
            if (!string.Equals(entry.Checksum, expectedChecksum, StringComparison.Ordinal))
            {
                throw new JsonException("El checksum de la entrada durable no coincide.");
            }

            return PreparedOperation.Restore(
                entry.Operation!,
                entry.Arguments,
                entry.MissionId!,
                entry.InvocationId!);
        }
        catch (Exception exception) when (exception is ArgumentException or JsonException)
        {
            throw new InvalidDataException("La cola durable contiene una entrada inválida.", exception);
        }
    }

    private static void ValidateEntry(
        string? operation,
        JsonElement arguments,
        string? missionId,
        string? invocationId)
    {
        if (!Baxy.Contracts.ContractValidator.IsOperationName(operation))
        {
            throw new JsonException("La operación durable no es válida.");
        }

        if (!Baxy.Contracts.ContractValidator.IsCanonicalIdentifier(missionId)
            || !Baxy.Contracts.ContractValidator.IsCanonicalIdentifier(invocationId))
        {
            throw new JsonException("Los IDs durables no son UUID canónicos.");
        }

        if (arguments.ValueKind != JsonValueKind.Object)
        {
            throw new JsonException("Los argumentos durables deben ser un objeto JSON.");
        }

        if (System.Text.Encoding.UTF8.GetByteCount(arguments.GetRawText()) > MaximumArgumentsBytes)
        {
            throw new JsonException("Los argumentos durables superan el límite de tamaño.");
        }

        ValidateJsonValue(arguments, depth: 0);
    }

    private static void ValidateChecksum(string? checksum)
    {
        if (checksum is null
            || checksum.Length != SHA256.HashSizeInBytes * 2
            || checksum.Any(static character =>
                character is not (>= '0' and <= '9')
                and not (>= 'a' and <= 'f')))
        {
            throw new JsonException("El checksum durable no es SHA-256 hexadecimal canónico.");
        }
    }

    private static string ComputeEntryChecksum(
        string operation,
        JsonElement arguments,
        string missionId,
        string invocationId)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteString("operation", operation);
            writer.WritePropertyName("arguments");
            WriteCanonicalJson(writer, arguments);
            writer.WriteString("missionId", missionId);
            writer.WriteString("invocationId", invocationId);
            writer.WriteEndObject();
        }

        return Convert.ToHexStringLower(SHA256.HashData(buffer.WrittenSpan));
    }

    private static void WriteCanonicalJson(Utf8JsonWriter writer, JsonElement value)
    {
        switch (value.ValueKind)
        {
            case JsonValueKind.Object:
                writer.WriteStartObject();
                foreach (JsonProperty property in value
                             .EnumerateObject()
                             .OrderBy(static property => property.Name, StringComparer.Ordinal))
                {
                    writer.WritePropertyName(property.Name);
                    WriteCanonicalJson(writer, property.Value);
                }

                writer.WriteEndObject();
                break;
            case JsonValueKind.Array:
                writer.WriteStartArray();
                foreach (JsonElement item in value.EnumerateArray())
                {
                    WriteCanonicalJson(writer, item);
                }

                writer.WriteEndArray();
                break;
            case JsonValueKind.String:
                writer.WriteStringValue(value.GetString());
                break;
            case JsonValueKind.Number:
                writer.WriteRawValue(value.GetRawText());
                break;
            case JsonValueKind.True:
                writer.WriteBooleanValue(true);
                break;
            case JsonValueKind.False:
                writer.WriteBooleanValue(false);
                break;
            case JsonValueKind.Null:
                writer.WriteNullValue();
                break;
            default:
                throw new JsonException("Los argumentos durables contienen un valor JSON no válido.");
        }
    }

    private static void ValidateJsonValue(JsonElement value, int depth)
    {
        if (depth > MaximumArgumentsDepth)
        {
            throw new JsonException("Los argumentos durables superan el límite de profundidad.");
        }

        if (value.ValueKind == JsonValueKind.Object)
        {
            var propertyNames = new HashSet<string>(StringComparer.Ordinal);
            foreach (JsonProperty property in value.EnumerateObject())
            {
                if (!propertyNames.Add(property.Name))
                {
                    throw new JsonException("Los argumentos durables contienen propiedades duplicadas.");
                }

                ValidateJsonValue(property.Value, depth + 1);
            }

            return;
        }

        if (value.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement item in value.EnumerateArray())
            {
                ValidateJsonValue(item, depth + 1);
            }

            return;
        }

        if (value.ValueKind is JsonValueKind.Undefined)
        {
            throw new JsonException("Los argumentos durables contienen un valor indefinido.");
        }
    }

    private static void ValidateNoDuplicateProperties(JsonElement value, int depth)
    {
        if (depth > 64)
        {
            throw new JsonException("La cola durable supera el límite de profundidad.");
        }

        if (value.ValueKind == JsonValueKind.Object)
        {
            var propertyNames = new HashSet<string>(StringComparer.Ordinal);
            foreach (JsonProperty property in value.EnumerateObject())
            {
                if (!propertyNames.Add(property.Name))
                {
                    throw new JsonException("La cola durable contiene propiedades duplicadas.");
                }

                ValidateNoDuplicateProperties(property.Value, depth + 1);
            }
        }
        else if (value.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement item in value.EnumerateArray())
            {
                ValidateNoDuplicateProperties(item, depth + 1);
            }
        }
    }

    private static string PreparePath(string path)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        if (!Path.IsPathFullyQualified(path)
            || path.StartsWith("\\\\", StringComparison.Ordinal))
        {
            throw new ArgumentException("La cola durable requiere una ruta local absoluta.", nameof(path));
        }

        string fullPath = Path.GetFullPath(path);
        string? root = Path.GetPathRoot(fullPath);
        if (string.IsNullOrEmpty(root)
            || root.Length < 3
            || root[1] != ':'
            || (root[2] != Path.DirectorySeparatorChar && root[2] != Path.AltDirectorySeparatorChar))
        {
            throw new ArgumentException("La cola durable requiere una unidad local.", nameof(path));
        }

        if (fullPath.IndexOf(':', root.Length) >= 0)
        {
            throw new ArgumentException("La cola durable no admite flujos alternativos.", nameof(path));
        }

        string? directory = Path.GetDirectoryName(fullPath);
        if (string.IsNullOrEmpty(directory))
        {
            throw new ArgumentException("La cola durable requiere una carpeta padre.", nameof(path));
        }

        EnsureNoReparsePoint(directory);
        ValidateFileAttributes(fullPath);
        return fullPath;
    }

    private static void EnsureSafePath(string path)
    {
        string? directory = Path.GetDirectoryName(path);
        if (string.IsNullOrEmpty(directory))
        {
            throw new InvalidDataException("La cola durable no tiene una carpeta padre.");
        }

        EnsureNoReparsePoint(directory);
        ValidateFileAttributes(path);
    }

    private static void EnsureNoReparsePoint(string directory)
    {
        string fullDirectory = Path.GetFullPath(directory);
        string? root = Path.GetPathRoot(fullDirectory);
        if (string.IsNullOrEmpty(root))
        {
            throw new InvalidDataException("La carpeta durable no tiene una unidad local.");
        }

        string current = root;
        string remainder = fullDirectory[root.Length..];
        foreach (string segment in remainder.Split(
                     [Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar],
                     StringSplitOptions.RemoveEmptyEntries))
        {
            current = Path.Combine(current, segment);
            if (!Directory.Exists(current))
            {
                Directory.CreateDirectory(current);
            }

            FileAttributes attributes = File.GetAttributes(current);
            if ((attributes & FileAttributes.ReparsePoint) != 0)
            {
                throw new IOException("La ruta de la cola durable atraviesa un punto de análisis.");
            }

            if ((attributes & FileAttributes.Directory) == 0)
            {
                throw new IOException("La ruta de la cola durable atraviesa un archivo.");
            }
        }
    }

    private static void ValidateFileAttributes(string path)
    {
        FileAttributes attributes;
        try
        {
            attributes = File.GetAttributes(path);
        }
        catch (FileNotFoundException)
        {
            return;
        }
        catch (DirectoryNotFoundException)
        {
            return;
        }

        if ((attributes & FileAttributes.ReparsePoint) != 0)
        {
            throw new IOException("El archivo de la cola durable no puede ser un punto de análisis.");
        }

        if ((attributes & FileAttributes.Directory) != 0)
        {
            throw new IOException("La ruta de la cola durable no puede ser una carpeta.");
        }
    }

    private static byte[] ReadBoundedFile(string path)
    {
        using var stream = new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            bufferSize: 4096,
            FileOptions.SequentialScan);
        if (stream.Length > MaximumFileBytes)
        {
            throw new InvalidDataException("La cola durable supera su límite de tamaño.");
        }

        byte[] content = new byte[checked((int)stream.Length)];
        stream.ReadExactly(content);
        return content;
    }

    private void WriteAtomically(ReadOnlySpan<byte> utf8)
    {
        string directory = Path.GetDirectoryName(_path)!;
        string temporaryPath = Path.Combine(
            directory,
            $".{Path.GetFileName(_path)}.{Guid.NewGuid():N}.tmp");
        try
        {
            using (var stream = new FileStream(
                       temporaryPath,
                       FileMode.CreateNew,
                       FileAccess.Write,
                       FileShare.None,
                       bufferSize: 4096,
                       FileOptions.WriteThrough))
            {
                stream.Write(utf8);
                stream.Flush(flushToDisk: true);
            }

            _beforeCommitVerification?.Invoke(temporaryPath);
            ValidateFileAttributes(temporaryPath);
            byte[] staged = ReadBoundedFile(temporaryPath);
            if (!utf8.SequenceEqual(staged))
            {
                throw new IOException("La verificación previa de la cola durable no coincidió.");
            }

            EnsureSafePath(_path);
            ValidateFileAttributes(temporaryPath);
            if (File.Exists(_path))
            {
                AtomicFileReplacement.Replace(temporaryPath, _path);
            }
            else
            {
                File.Move(temporaryPath, _path);
            }
        }
        finally
        {
            try
            {
                File.Delete(temporaryPath);
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                // A stale private temp file is safer than weakening a successfully committed outbox.
            }
        }
    }
}

/// <summary>
/// Resultado de abrir la cola durable. <paramref name="UnreadablePath"/> es
/// <see langword="null"/> cuando el archivo se leyó entero; si no, es dónde
/// quedó lo que no se pudo interpretar.
/// </summary>
internal readonly record struct DurableRetryLoad(
    IReadOnlyList<PreparedOperation> Operations,
    string? UnreadablePath);

internal sealed class DurableRetryDocument
{
    [JsonRequired]
    public int Version { get; init; }

    [JsonRequired]
    public List<DurableRetryEntry>? Entries { get; init; }
}

internal sealed class DurableRetryEntry
{
    [JsonRequired]
    public string? Operation { get; init; }

    [JsonRequired]
    public JsonElement Arguments { get; init; }

    [JsonRequired]
    public string? MissionId { get; init; }

    [JsonRequired]
    public string? InvocationId { get; init; }

    [JsonRequired]
    public string? Checksum { get; init; }
}

[JsonSourceGenerationOptions(
    PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase,
    PropertyNameCaseInsensitive = false,
    UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
    GenerationMode = JsonSourceGenerationMode.Metadata)]
[JsonSerializable(typeof(DurableRetryDocument))]
internal sealed partial class DurableRetryJsonContext : JsonSerializerContext;
