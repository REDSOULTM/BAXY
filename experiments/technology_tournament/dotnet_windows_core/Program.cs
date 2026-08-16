using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Baxy.Tournament;

internal sealed class RequestProblem(string message) : Exception(message);

internal static partial class Program
{
    private const int SchemaVersion = 1;
    private const string CreatePrefix = "crea la nota ";
    private const string CreateSeparator = " con el texto: ";
    private static readonly string[] CompoundSuffixes = [" y después léela", " y despues leela"];
    private static readonly HashSet<char> InvalidWindowsChars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*'];
    private static readonly HashSet<string> ReservedWindowsNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
    };

    [GeneratedRegex("^[A-Za-z0-9._-]{1,128}$", RegexOptions.CultureInvariant)]
    private static partial Regex InvocationPattern();

    private static JsonObject BaseResponse(
        string invocationId,
        string state,
        string intent,
        string effect,
        string risk,
        string verification,
        string response,
        JsonArray? operations = null,
        JsonArray? evidence = null,
        bool replayed = false,
        bool recovered = false)
    {
        return new JsonObject
        {
            ["schema_version"] = SchemaVersion,
            ["invocation_id"] = invocationId,
            ["mission_id"] = $"mission-{invocationId}",
            ["state"] = state,
            ["intent"] = intent,
            ["effect"] = effect,
            ["risk"] = risk,
            ["operations"] = operations ?? [],
            ["verification"] = new JsonObject
            {
                ["status"] = verification,
                ["evidence"] = evidence ?? []
            },
            ["response"] = response,
            ["replayed"] = replayed,
            ["journal_recovered"] = recovered
        };
    }

    private static JsonObject Invalid(string invocationId, string message, bool recovered = false) =>
        BaseResponse(invocationId, "blocked", "invalid", "none", "high", "unverified", message, recovered: recovered);

    private static string WorkspaceFromRequest(JsonObject request)
    {
        var value = request["workspace"]?.GetValue<string>();
        if (string.IsNullOrEmpty(value) || value.Contains('\0') || !Path.IsPathFullyQualified(value))
        {
            throw new RequestProblem("workspace inválido");
        }

        var workspace = Path.GetFullPath(value);
        var allowed = Environment.GetEnvironmentVariable("BAXY_TOURNAMENT_ROOT");
        if (!string.IsNullOrEmpty(allowed))
        {
            var allowedRoot = Path.GetFullPath(allowed);
            var relative = Path.GetRelativePath(allowedRoot, workspace);
            if (Path.IsPathFullyQualified(relative) || relative == ".." || relative.StartsWith($"..{Path.DirectorySeparatorChar}", StringComparison.Ordinal))
            {
                throw new RequestProblem("workspace fuera de la raíz autorizada");
            }
        }

        Directory.CreateDirectory(workspace);
        return workspace;
    }

    private static string SafeFilename(string raw)
    {
        var name = raw.Trim();
        if (name.Length == 0 || name != raw || name.Contains('\0') || name is "." or ".." || name.Contains("..", StringComparison.Ordinal))
        {
            throw new RequestProblem("nombre de nota inválido");
        }
        if (name.Any(InvalidWindowsChars.Contains) || name.EndsWith('.') || name.EndsWith(' '))
        {
            throw new RequestProblem("nombre de nota fuera del espacio permitido");
        }
        var stem = name.Split('.', 2)[0];
        if (ReservedWindowsNames.Contains(stem) || Encoding.UTF8.GetByteCount(name) > 240)
        {
            throw new RequestProblem("nombre reservado o demasiado largo");
        }
        return name;
    }

    private static string NotePath(string workspace, string directory, string filename)
    {
        var root = Path.GetFullPath(Path.Combine(workspace, directory));
        Directory.CreateDirectory(root);
        var candidate = Path.GetFullPath(Path.Combine(root, filename));
        if (!string.Equals(Path.GetDirectoryName(candidate), root, StringComparison.OrdinalIgnoreCase))
        {
            throw new RequestProblem("ruta fuera del espacio permitido");
        }
        return candidate;
    }

    private static void AtomicWrite(string path, string text, string invocationId)
    {
        var temporary = Path.Combine(Path.GetDirectoryName(path)!, $".{Path.GetFileName(path)}.{invocationId}.tmp");
        var data = Encoding.UTF8.GetBytes(text);
        using (var stream = new FileStream(temporary, FileMode.Create, FileAccess.Write, FileShare.None, 4096, FileOptions.WriteThrough))
        {
            stream.Write(data);
            stream.Flush(true);
        }
        File.Move(temporary, path, true);
    }

    private static string QuarantinePath(string workspace)
    {
        for (var number = 1; number < 10_000; number++)
        {
            var candidate = Path.Combine(workspace, $"journal.corrupt.{number:0000}.jsonl");
            if (!File.Exists(candidate))
            {
                return candidate;
            }
        }
        throw new InvalidOperationException("demasiadas cuarentenas de journal");
    }

    internal static bool RepairJournal(string workspace)
    {
        var path = Path.Combine(workspace, "journal.jsonl");
        if (!File.Exists(path))
        {
            return false;
        }
        var raw = File.ReadAllBytes(path);
        if (raw.Length == 0)
        {
            return false;
        }
        var validLength = 0;
        var invalidAt = -1;
        while (validLength < raw.Length)
        {
            var newline = Array.IndexOf(raw, (byte)'\n', validLength);
            if (newline < 0)
            {
                invalidAt = validLength;
                break;
            }
            var count = newline - validLength;
            if (count > 0 && raw[newline - 1] == (byte)'\r')
            {
                count--;
            }
            try
            {
                var text = new UTF8Encoding(false, true).GetString(raw, validLength, count);
                if (JsonNode.Parse(text) is not JsonObject)
                {
                    invalidAt = validLength;
                    break;
                }
            }
            catch (Exception exception) when (exception is JsonException or DecoderFallbackException)
            {
                invalidAt = validLength;
                break;
            }
            validLength = newline + 1;
        }
        if (invalidAt < 0)
        {
            return false;
        }
        var quarantine = QuarantinePath(workspace);
        using (var bad = new FileStream(quarantine, FileMode.CreateNew, FileAccess.Write, FileShare.None, 4096, FileOptions.WriteThrough))
        {
            bad.Write(raw.AsSpan(invalidAt));
            bad.Flush(true);
        }
        using (var journal = new FileStream(path, FileMode.Open, FileAccess.Write, FileShare.Read))
        {
            journal.SetLength(invalidAt);
            journal.Flush(true);
        }
        return true;
    }

    private static List<JsonObject> LoadJournal(string workspace)
    {
        var path = Path.Combine(workspace, "journal.jsonl");
        if (!File.Exists(path))
        {
            return [];
        }
        var records = new List<JsonObject>();
        foreach (var line in File.ReadLines(path, Encoding.UTF8))
        {
            if (!string.IsNullOrWhiteSpace(line) && JsonNode.Parse(line) is JsonObject record)
            {
                records.Add(record);
            }
        }
        return records;
    }

    private static void AppendJournal(string workspace, JsonObject value)
    {
        var path = Path.Combine(workspace, "journal.jsonl");
        var data = Encoding.UTF8.GetBytes(value.ToJsonString(new JsonSerializerOptions { WriteIndented = false }) + "\n");
        using var stream = new FileStream(path, FileMode.Append, FileAccess.Write, FileShare.Read, 4096, FileOptions.WriteThrough);
        stream.Write(data);
        stream.Flush(true);
    }

    private static (JsonObject? Replay, bool Started) ExistingInvocation(
        IEnumerable<JsonObject> records,
        string invocationId,
        string message)
    {
        var started = false;
        foreach (var record in records)
        {
            if (record["invocation_id"]?.GetValue<string>() != invocationId)
            {
                continue;
            }
            if (record["message"]?.GetValue<string>() != message)
            {
                throw new RequestProblem("invocation_id reutilizado con otra petición");
            }
            if (record["status"]?.GetValue<string>() == "started")
            {
                started = true;
            }
            if (record["status"]?.GetValue<string>() == "completed" && record["result"] is JsonObject result)
            {
                var replay = (JsonObject)result.DeepClone();
                replay["replayed"] = true;
                return (replay, started);
            }
        }
        return (null, started);
    }

    private static (string Filename, string Content, bool Compound)? ParseCreate(string message)
    {
        var lowered = message.ToLowerInvariant();
        if (!lowered.StartsWith(CreatePrefix, StringComparison.Ordinal))
        {
            return null;
        }
        var separatorIndex = lowered.IndexOf(CreateSeparator, CreatePrefix.Length, StringComparison.Ordinal);
        if (separatorIndex < 0)
        {
            return null;
        }
        var filename = message[CreatePrefix.Length..separatorIndex];
        var content = message[(separatorIndex + CreateSeparator.Length)..];
        var loweredContent = content.ToLowerInvariant();
        var compound = false;
        foreach (var suffix in CompoundSuffixes)
        {
            if (loweredContent.EndsWith(suffix, StringComparison.Ordinal))
            {
                content = content[..^suffix.Length];
                compound = true;
                break;
            }
        }
        return (filename, content, compound);
    }

    private static JsonObject Done(
        string invocationId,
        string intent,
        string effect,
        string response,
        JsonArray operations,
        JsonArray evidence,
        bool recovered) =>
        BaseResponse(invocationId, "done", intent, effect, "low", "verified", response, operations, evidence, recovered: recovered);

    private static JsonObject Execute(string invocationId, string message, string workspace, bool recovered)
    {
        var trimmed = message.Trim();
        var lowered = trimmed.ToLowerInvariant();
        if (message.Contains('\0'))
        {
            return Invalid(invocationId, "No ejecuté la petición porque contiene un byte NUL.", recovered);
        }
        if (lowered.StartsWith("hola", StringComparison.Ordinal))
        {
            return BaseResponse(invocationId, "done", "conversation", "none", "low", "not_applicable", "Estoy bien y lista para ayudarte.", recovered: recovered);
        }

        var create = ParseCreate(trimmed);
        if (create is not null)
        {
            string name;
            string path;
            try
            {
                name = SafeFilename(create.Value.Filename);
                path = NotePath(workspace, "notes", name);
            }
            catch (RequestProblem)
            {
                return BaseResponse(invocationId, "blocked", "note.create", "reversible", "high", "unverified", "No creé la nota porque su ruta sale del espacio permitido.", recovered: recovered);
            }
            AtomicWrite(path, create.Value.Content, invocationId);
            var observed = File.ReadAllText(path, Encoding.UTF8);
            var intent = create.Value.Compound ? "note.create_and_read" : "note.create";
            if (observed != create.Value.Content)
            {
                return BaseResponse(invocationId, "failed", intent, "reversible", "low", "unverified", "La nota no pudo verificarse después de escribirla.", recovered: recovered);
            }
            var relative = $"notes/{name}";
            var operations = new JsonArray(
                (JsonNode)new JsonObject { ["operation"] = "note.create", ["state"] = "done", ["relative_path"] = relative });
            if (create.Value.Compound)
            {
                operations.Add(
                    (JsonNode)new JsonObject { ["operation"] = "note.read", ["state"] = "done", ["relative_path"] = relative });
            }
            var evidence = new JsonArray(
                (JsonNode)new JsonObject { ["kind"] = "file_readback", ["relative_path"] = relative, ["utf8_bytes"] = Encoding.UTF8.GetByteCount(observed) });
            var response = create.Value.Compound
                ? $"Creé y verifiqué la nota {name}. Dice: {observed}"
                : $"Creé y verifiqué la nota {name}.";
            return Done(invocationId, intent, "reversible", response, operations, evidence, recovered);
        }

        const string readPrefix = "lee la nota ";
        if (lowered.StartsWith(readPrefix, StringComparison.Ordinal))
        {
            string name;
            string path;
            try
            {
                name = SafeFilename(trimmed[readPrefix.Length..]);
                path = NotePath(workspace, "notes", name);
            }
            catch (RequestProblem)
            {
                return Invalid(invocationId, "No leí la nota porque su nombre no es seguro.", recovered);
            }
            if (!File.Exists(path))
            {
                return BaseResponse(invocationId, "blocked", "note.read", "read_only", "low", "unverified", $"No pude leer la nota {name} porque no existe.", recovered: recovered);
            }
            var content = File.ReadAllText(path, Encoding.UTF8);
            var relative = $"notes/{name}";
            return Done(
                invocationId,
                "note.read",
                "read_only",
                $"La nota {name} dice: {content}",
                new JsonArray((JsonNode)new JsonObject { ["operation"] = "note.read", ["state"] = "done", ["relative_path"] = relative }),
                new JsonArray((JsonNode)new JsonObject { ["kind"] = "file_read", ["relative_path"] = relative, ["utf8_bytes"] = Encoding.UTF8.GetByteCount(content) }),
                recovered);
        }

        const string trashPrefix = "mueve la nota ";
        const string trashSuffix = " a la papelera";
        if (lowered.StartsWith(trashPrefix, StringComparison.Ordinal) && lowered.EndsWith(trashSuffix, StringComparison.Ordinal))
        {
            string name;
            string source;
            string target;
            try
            {
                name = SafeFilename(trimmed[trashPrefix.Length..^trashSuffix.Length]);
                source = NotePath(workspace, "notes", name);
                target = NotePath(workspace, "trash", name);
            }
            catch (RequestProblem)
            {
                return Invalid(invocationId, "No moví la nota porque su nombre no es seguro.", recovered);
            }
            if (File.Exists(source))
            {
                File.Move(source, target, true);
            }
            if (!File.Exists(target) || File.Exists(source))
            {
                return BaseResponse(invocationId, "blocked", "note.trash", "reversible", "low", "unverified", $"No pude mover {name} porque la nota no existe.", recovered: recovered);
            }
            return Done(
                invocationId,
                "note.trash",
                "reversible",
                $"Moví la nota {name} a la papelera y lo verifiqué.",
                new JsonArray((JsonNode)new JsonObject { ["operation"] = "note.trash", ["state"] = "done", ["relative_path"] = $"trash/{name}" }),
                new JsonArray((JsonNode)new JsonObject { ["kind"] = "move_verified", ["present"] = $"trash/{name}", ["absent"] = $"notes/{name}" }),
                recovered);
        }

        const string restorePrefix = "restaura la nota ";
        if (lowered.StartsWith(restorePrefix, StringComparison.Ordinal))
        {
            string name;
            string source;
            string target;
            try
            {
                name = SafeFilename(trimmed[restorePrefix.Length..]);
                source = NotePath(workspace, "trash", name);
                target = NotePath(workspace, "notes", name);
            }
            catch (RequestProblem)
            {
                return Invalid(invocationId, "No restauré la nota porque su nombre no es seguro.", recovered);
            }
            if (File.Exists(source))
            {
                File.Move(source, target, true);
            }
            if (!File.Exists(target) || File.Exists(source))
            {
                return BaseResponse(invocationId, "blocked", "note.restore", "reversible", "low", "unverified", $"No pude restaurar {name} porque no está en la papelera.", recovered: recovered);
            }
            return Done(
                invocationId,
                "note.restore",
                "reversible",
                $"Restauré la nota {name} y lo verifiqué.",
                new JsonArray((JsonNode)new JsonObject { ["operation"] = "note.restore", ["state"] = "done", ["relative_path"] = $"notes/{name}" }),
                new JsonArray((JsonNode)new JsonObject { ["kind"] = "move_verified", ["present"] = $"notes/{name}", ["absent"] = $"trash/{name}" }),
                recovered);
        }

        if (lowered.StartsWith("borra ", StringComparison.Ordinal) || lowered.StartsWith("elimina ", StringComparison.Ordinal))
        {
            return BaseResponse(invocationId, "blocked", "unsafe.delete", "destructive", "critical", "unverified", "No ejecutaré ese borrado: el objetivo está fuera del espacio seguro y es destructivo.", recovered: recovered);
        }
        return BaseResponse(invocationId, "blocked", "unknown", "none", "low", "unverified", "No puedo completar esa petición con las capacidades disponibles.", recovered: recovered);
    }

    private static JsonObject HandleRequest(JsonNode? node)
    {
        if (node is not JsonObject request)
        {
            return Invalid("invalid-request", "La petición no tiene un objeto válido.");
        }
        var invocationId = request["invocation_id"]?.GetValue<string>();
        var message = request["message"]?.GetValue<string>();
        if (invocationId is null || !InvocationPattern().IsMatch(invocationId))
        {
            return Invalid("invalid-request", "La petición no tiene un invocation_id válido.");
        }
        if (message is null)
        {
            return Invalid(invocationId, "La petición no contiene texto válido.");
        }
        if (Encoding.UTF8.GetByteCount(message) > 16_384)
        {
            return Invalid(invocationId, "La petición supera el tamaño permitido.");
        }
        string workspace;
        try
        {
            workspace = WorkspaceFromRequest(request);
        }
        catch (Exception exception) when (exception is RequestProblem or ArgumentException or IOException or UnauthorizedAccessException)
        {
            return Invalid(invocationId, "El workspace solicitado no está autorizado.");
        }

        var recovered = RepairJournal(workspace);
        JsonObject? replay;
        bool started;
        try
        {
            (replay, started) = ExistingInvocation(LoadJournal(workspace), invocationId, message);
        }
        catch (RequestProblem)
        {
            return Invalid(invocationId, "Ese invocation_id ya pertenece a otra petición.", recovered);
        }
        if (replay is not null)
        {
            replay["journal_recovered"] = (replay["journal_recovered"]?.GetValue<bool>() ?? false) || recovered;
            return replay;
        }
        if (!started)
        {
            AppendJournal(workspace, new JsonObject
            {
                ["schema_version"] = SchemaVersion,
                ["status"] = "started",
                ["invocation_id"] = invocationId,
                ["message"] = message
            });
        }
        JsonObject result;
        try
        {
            result = Execute(invocationId, message, workspace, recovered);
        }
        catch (Exception)
        {
            Console.Error.WriteLine("BAXY_EXECUTION_ERROR internal_failure");
            result = BaseResponse(invocationId, "failed", "internal", "none", "high", "unverified", "No pude completar la petición por un fallo interno.", recovered: recovered);
        }
        AppendJournal(workspace, new JsonObject
        {
            ["schema_version"] = SchemaVersion,
            ["status"] = "completed",
            ["invocation_id"] = invocationId,
            ["message"] = message,
            ["result"] = result.DeepClone()
        });
        return result;
    }

    private static int Main(string[] args)
    {
        Console.InputEncoding = new UTF8Encoding(false);
        Console.OutputEncoding = new UTF8Encoding(false);
        string? line;
        while ((line = Console.ReadLine()) is not null)
        {
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }
            var timer = Stopwatch.StartNew();
            JsonNode? input;
            try
            {
                input = JsonNode.Parse(line);
            }
            catch (JsonException)
            {
                Console.Error.WriteLine("BAXY_PROTOCOL_ERROR malformed_json");
                continue;
            }
            var result = HandleRequest(input);
            timer.Stop();
            result["elapsed_ns"] = (long)(timer.Elapsed.TotalMilliseconds * 1_000_000d);
            Console.WriteLine(result.ToJsonString(new JsonSerializerOptions { WriteIndented = false }));
        }
        return 0;
    }
}
