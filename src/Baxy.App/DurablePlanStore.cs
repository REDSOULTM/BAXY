using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.Json.Nodes;
using Baxy.Security.Windows;

namespace Baxy.App;

internal sealed class DurablePlanStore
{
    internal const int MaximumFileBytes = 1_048_576;
    private const int CurrentVersion = 1;
    private const string Purpose = "baxy.planner.state.v1";
    private readonly string _path;
    private readonly WindowsProtectedPayload _protector;

    internal DurablePlanStore(string path, string keyPath)
    {
        _path = ValidatePath(path);
        _protector = new WindowsProtectedPayload(keyPath);
    }

    internal static DurablePlanStore CreateDefault()
    {
        string directory = Path.Combine(
            MemoryOperationProtector.ResolveDataRoot(),
            "shell");
        return new DurablePlanStore(
            Path.Combine(directory, "planner-state.v1.bin"),
            Path.Combine(directory, "planner-state.v1.key"));
    }

    internal PendingMindPlanExecution? Load(RetryableOperationRegistry registry)
    {
        ArgumentNullException.ThrowIfNull(registry);
        EnsureSafePath(_path);
        if (!File.Exists(_path))
        {
            return null;
        }

        byte[] envelope = ReadBounded(_path);
        byte[] plaintext = _protector.Open(envelope, Purpose);
        try
        {
            using (JsonDocument structure = JsonDocument.Parse(plaintext))
            {
                ValidateNoDuplicateProperties(structure.RootElement, depth: 0);
            }

            DurablePlanDocument document = JsonSerializer.Deserialize(
                    plaintext,
                    DurablePlanJsonContext.Default.DurablePlanDocument)
                ?? throw new InvalidDataException("El estado durable del planner contiene null.");
            ValidateDocument(document);
            var steps = document.Steps!
                .Select(RestoreStep)
                .ToArray();
            var execution = new PendingMindPlanExecution(
                document.Objective!,
                steps,
                document.ReplanCount)
            {
                NextIndex = document.NextIndex,
                PendingEffectMayHaveOccurred = document.PendingEffectMayHaveOccurred,
            };
            foreach (JsonElement observation in document.Observations!.EnumerateArray())
            {
                execution.Observations.Add(JsonNode.Parse(observation.GetRawText()));
            }

            execution.CompletedMessages.AddRange(document.CompletedMessages!);
            if (document.PendingOperation is not null)
            {
                DurablePreparedOperation pending = document.PendingOperation;
                PreparedOperation restored = PreparedOperation.Restore(
                    pending.Operation!,
                    pending.Arguments,
                    pending.MissionId!,
                    pending.InvocationId!);
                execution.PendingOperation = registry.RestorePlanOperation(restored);
            }

            return execution;
        }
        catch (JsonException exception)
        {
            throw new InvalidDataException(
                "El estado durable del planner contiene JSON inválido.",
                exception);
        }
        finally
        {
            System.Security.Cryptography.CryptographicOperations.ZeroMemory(plaintext);
        }
    }

    internal void Save(PendingMindPlanExecution execution)
    {
        ArgumentNullException.ThrowIfNull(execution);
        var document = new DurablePlanDocument
        {
            Version = CurrentVersion,
            Objective = execution.Objective,
            Steps = execution.Steps.Select(CreateStep).ToList(),
            NextIndex = execution.NextIndex,
            ReplanCount = execution.ReplanCount,
            Observations = SerializeNodeToElement(execution.Observations),
            CompletedMessages = execution.CompletedMessages.ToList(),
            PendingEffectMayHaveOccurred = execution.PendingEffectMayHaveOccurred,
            PendingOperation = execution.PendingOperation is null
                ? null
                : new DurablePreparedOperation
                {
                    Operation = execution.PendingOperation.OperationName,
                    Arguments = execution.PendingOperation.Arguments,
                    MissionId = execution.PendingOperation.MissionId,
                    InvocationId = execution.PendingOperation.InvocationId,
                },
        };
        ValidateDocument(document);
        byte[] plaintext = JsonSerializer.SerializeToUtf8Bytes(
            document,
            DurablePlanJsonContext.Default.DurablePlanDocument);
        try
        {
            byte[] envelope = _protector.Seal(plaintext, Purpose);
            if (envelope.Length > MaximumFileBytes)
            {
                throw new InvalidOperationException(
                    "El estado durable del planner supera el límite.");
            }

            WriteAtomically(envelope);
        }
        finally
        {
            System.Security.Cryptography.CryptographicOperations.ZeroMemory(plaintext);
        }
    }

    internal void Clear()
    {
        EnsureSafePath(_path);
        if (File.Exists(_path))
        {
            File.Delete(_path);
        }
    }

    private static DurablePlanStep CreateStep(MindPlanStep step)
    {
        JsonElement? arguments = step.Arguments is null
            ? null
            : SerializeNodeToElement(step.Arguments);

        return new DurablePlanStep
        {
            Id = step.Id,
            Operation = step.Operation,
            Purpose = step.Purpose,
            DependsOn = step.DependsOn.ToList(),
            ArgumentsMode = step.ArgumentsMode,
            Arguments = arguments,
            HasArguments = step.Arguments is not null,
        };
    }

    internal static JsonElement SerializeNodeToElement(JsonNode value)
    {
        ArgumentNullException.ThrowIfNull(value);
        return JsonSerializer.SerializeToElement(value);
    }

    private static MindPlanStep RestoreStep(DurablePlanStep step)
    {
        JsonObject? arguments = step.HasArguments && step.Arguments is { } storedArguments
            ? JsonNode.Parse(storedArguments.GetRawText()) as JsonObject
            : null;
        return new MindPlanStep(
            step.Id!,
            step.Operation!,
            step.Purpose!,
            step.DependsOn!,
            step.ArgumentsMode!,
            arguments);
    }

    private static void ValidateDocument(DurablePlanDocument document)
    {
        if (document.Version != CurrentVersion
            || string.IsNullOrWhiteSpace(document.Objective)
            || document.Steps is not { Count: > 0 and <= 16 }
            || document.NextIndex < 0
            || document.NextIndex >= document.Steps.Count
            || document.ReplanCount is < 0 or > 2
            || document.Observations.ValueKind != JsonValueKind.Array
            || document.Observations.GetArrayLength() > 32
            || document.CompletedMessages is null
            || document.CompletedMessages.Count
                != document.Observations.GetArrayLength()
            || document.CompletedMessages.Count > 32
            || document.CompletedMessages.Any(static message =>
                message is null || message.Length > 16_384)
            || document.Steps.Any(static step => step is null))
        {
            throw new InvalidDataException("El estado durable del planner no es coherente.");
        }

        var mindSteps = document.Steps.Select(RestoreStep).ToArray();
        _ = MindPlanBoundary.ValidateAndConvert(
            document.Objective,
            new MindPlanResult("plan", string.Empty, mindSteps));
        if (document.PendingOperation is { } pending)
        {
            if (string.IsNullOrWhiteSpace(pending.Operation)
                || pending.Operation.StartsWith("memory.", StringComparison.Ordinal)
                || pending.Arguments.ValueKind != JsonValueKind.Object
                || !Baxy.Contracts.ContractValidator.IsCanonicalIdentifier(pending.MissionId)
                || !Baxy.Contracts.ContractValidator.IsCanonicalIdentifier(pending.InvocationId))
            {
                throw new InvalidDataException(
                    "La operación pendiente del planner no es válida.");
            }
        }
    }

    private void WriteAtomically(ReadOnlySpan<byte> bytes)
    {
        EnsureSafePath(_path);
        string directory = Path.GetDirectoryName(_path)!;
        Directory.CreateDirectory(directory);
        string temporary = Path.Combine(
            directory,
            $".{Path.GetFileName(_path)}.{Guid.NewGuid():N}.tmp");
        try
        {
            using (var stream = new FileStream(
                       temporary,
                       FileMode.CreateNew,
                       FileAccess.Write,
                       FileShare.None,
                       4096,
                       FileOptions.WriteThrough))
            {
                stream.Write(bytes);
                stream.Flush(flushToDisk: true);
            }

            if (File.Exists(_path))
            {
                AtomicFileReplacement.Replace(temporary, _path);
            }
            else
            {
                File.Move(temporary, _path);
            }
        }
        finally
        {
            try
            {
                File.Delete(temporary);
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
            }
        }
    }

    private static byte[] ReadBounded(string path)
    {
        using var stream = new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            4096,
            FileOptions.SequentialScan);
        if (stream.Length is <= 0 or > MaximumFileBytes)
        {
            throw new InvalidDataException("El estado durable del planner tiene tamaño inválido.");
        }

        byte[] bytes = new byte[checked((int)stream.Length)];
        stream.ReadExactly(bytes);
        return bytes;
    }

    private static string ValidatePath(string path)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        if (!Path.IsPathFullyQualified(path) || path.StartsWith("\\\\", StringComparison.Ordinal))
        {
            throw new ArgumentException("El estado durable requiere una ruta local absoluta.", nameof(path));
        }

        string full = Path.GetFullPath(path);
        string? root = Path.GetPathRoot(full);
        if (string.IsNullOrEmpty(root) || full.IndexOf(':', root.Length) >= 0)
        {
            throw new ArgumentException("La ruta durable no es canónica.", nameof(path));
        }

        EnsureSafePath(full);
        return full;
    }

    private static void EnsureSafePath(string path)
    {
        string? directory = Path.GetDirectoryName(path);
        if (string.IsNullOrEmpty(directory))
        {
            throw new InvalidDataException("La ruta durable no tiene carpeta padre.");
        }

        string fullDirectory = Path.GetFullPath(directory);
        string root = Path.GetPathRoot(fullDirectory)!;
        string current = root;
        foreach (string segment in fullDirectory[root.Length..].Split(
                     [Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar],
                     StringSplitOptions.RemoveEmptyEntries))
        {
            current = Path.Combine(current, segment);
            if (!Directory.Exists(current))
            {
                Directory.CreateDirectory(current);
            }

            if ((File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
            {
                throw new IOException("La ruta durable atraviesa un reparse point.");
            }
        }

        if (File.Exists(path)
            && (File.GetAttributes(path) & (FileAttributes.ReparsePoint | FileAttributes.Directory)) != 0)
        {
            throw new IOException("El archivo durable no es regular.");
        }
    }

    private static void ValidateNoDuplicateProperties(JsonElement value, int depth)
    {
        if (depth > 32)
        {
            throw new JsonException("El estado durable supera la profundidad permitida.");
        }

        if (value.ValueKind == JsonValueKind.Object)
        {
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (JsonProperty property in value.EnumerateObject())
            {
                if (!names.Add(property.Name))
                {
                    throw new JsonException("El estado durable contiene propiedades duplicadas.");
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
}

internal sealed class DurablePlanDocument
{
    [JsonRequired]
    public int Version { get; init; }

    [JsonRequired]
    public string? Objective { get; init; }

    [JsonRequired]
    public List<DurablePlanStep>? Steps { get; init; }

    [JsonRequired]
    public int NextIndex { get; init; }

    [JsonRequired]
    public int ReplanCount { get; init; }

    [JsonRequired]
    public JsonElement Observations { get; init; }

    [JsonRequired]
    public List<string>? CompletedMessages { get; init; }

    [JsonRequired]
    public bool PendingEffectMayHaveOccurred { get; init; }

    public DurablePreparedOperation? PendingOperation { get; init; }
}

internal sealed class DurablePlanStep
{
    [JsonRequired]
    public string? Id { get; init; }

    [JsonRequired]
    public string? Operation { get; init; }

    [JsonRequired]
    public string? Purpose { get; init; }

    [JsonRequired]
    public List<string>? DependsOn { get; init; }

    [JsonRequired]
    public string? ArgumentsMode { get; init; }

    [JsonRequired]
    public bool HasArguments { get; init; }

    [JsonRequired]
    public JsonElement? Arguments { get; init; }
}

internal sealed class DurablePreparedOperation
{
    [JsonRequired]
    public string? Operation { get; init; }

    [JsonRequired]
    public JsonElement Arguments { get; init; }

    [JsonRequired]
    public string? MissionId { get; init; }

    [JsonRequired]
    public string? InvocationId { get; init; }
}

[JsonSourceGenerationOptions(
    PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase,
    PropertyNameCaseInsensitive = false,
    UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
    GenerationMode = JsonSourceGenerationMode.Metadata)]
[JsonSerializable(typeof(DurablePlanDocument))]
internal sealed partial class DurablePlanJsonContext : JsonSerializerContext;
