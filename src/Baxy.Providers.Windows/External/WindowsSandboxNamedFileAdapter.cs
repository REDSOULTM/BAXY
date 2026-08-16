using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsSandboxNamedFileAdapter : IExternalOperationAdapter
{
    private readonly string _root;

    internal WindowsSandboxNamedFileAdapter(string dataRoot) =>
        _root = Path.Combine(Path.GetFullPath(dataRoot), "filesystem-sandbox");

    public bool CanHandle(string operation) => operation is
        "filesystem.sandbox.append.named" or "filesystem.sandbox.diff.named"
        or "filesystem.sandbox.move.named";

    public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            return ValueTask.FromResult(operation switch
            {
                "filesystem.sandbox.append.named" => Append(
                    operation, arguments, effectBoundary),
                "filesystem.sandbox.diff.named" => Diff(operation, arguments),
                "filesystem.sandbox.move.named" => Move(
                    operation, arguments, effectBoundary),
                _ => ExternalJson.Failure(operation, "sandbox_named_operation_invalid"),
            });
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return ValueTask.FromResult(effectBoundary.Failure(
                operation, "sandbox_named_filesystem_unavailable"));
        }
        catch (InvalidDataException exception)
        {
            return ValueTask.FromResult(effectBoundary.Failure(operation, exception.Message));
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException or System.Security.SecurityException)
        {
            return ValueTask.FromResult(effectBoundary.Failure(
                operation, "sandbox_named_filesystem_unavailable"));
        }
    }

    private ExternalCapabilityReceipt Append(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary)
    {
        string fileName = SafeFileName(ExternalJson.RequiredString(arguments, "fileName"));
        string text = arguments.GetProperty("text").GetString() ?? string.Empty;
        string path = ResolveUnique(fileName, exact: true);
        var info = new FileInfo(path);
        if (info.Length > 10 * 1024 * 1024)
            return ExternalJson.Failure(operation, "sandbox_named_file_too_large");
        long beforeLength = info.Length;
        string beforeHash = Hash(path);
        effectBoundary.Cross();
        File.AppendAllText(path, text, new UTF8Encoding(false));
        byte[] expected = Encoding.UTF8.GetBytes(text);
        using FileStream stream = File.Open(path, FileMode.Open, FileAccess.Read, FileShare.Read);
        if (stream.Length != beforeLength + expected.Length)
            return ExternalJson.Failure(operation, "sandbox_append_length_postread_failed", true);
        stream.Position = beforeLength;
        byte[] observed = new byte[expected.Length];
        stream.ReadExactly(observed);
        if (!observed.SequenceEqual(expected))
            return ExternalJson.Failure(operation, "sandbox_append_content_postread_failed", true);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("fileName", fileName); writer.WriteString("previousSha256", beforeHash);
            writer.WriteString("sha256", Hash(path)); writer.WriteNumber("appendedBytes", expected.Length);
            writer.WriteString("authority", "sandbox_named_append_hash_postread"); writer.WriteEndObject();
        }), effectObserved: true);
    }

    private ExternalCapabilityReceipt Move(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary)
    {
        string sourceName = SafeFileName(ExternalJson.RequiredString(arguments, "sourceFileName"));
        string relativeDestination = ExternalJson.RequiredString(arguments, "destinationRelativePath")
            .Replace(Path.AltDirectorySeparatorChar, Path.DirectorySeparatorChar);
        string source = ResolveUnique(sourceName, exact: true);
        string destination = ConfinedDestination(relativeDestination);
        if (File.Exists(destination) || Directory.Exists(destination))
            return ExternalJson.Failure(operation, "sandbox_move_destination_exists");
        string hash = Hash(source);
        effectBoundary.Cross();
        Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
        File.Move(source, destination);
        if (File.Exists(source) || !File.Exists(destination)
            || !string.Equals(Hash(destination), hash, StringComparison.Ordinal))
            return ExternalJson.Failure(operation, "sandbox_move_postread_failed", true);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("sourceFileName", sourceName);
            writer.WriteString("destinationRelativePath", relativeDestination);
            writer.WriteString("sha256", hash); writer.WriteBoolean("sourceAbsent", true);
            writer.WriteString("authority", "sandbox_named_move_hash_absence_postread");
            writer.WriteEndObject();
        }), true);
    }

    private ExternalCapabilityReceipt Diff(string operation, JsonElement arguments)
    {
        string leftQuery = ExternalJson.RequiredString(arguments, "leftQuery");
        string rightQuery = ExternalJson.RequiredString(arguments, "rightQuery");
        string left = ResolveUnique(leftQuery, exact: false);
        string right = ResolveRelatedUnique(rightQuery, left);
        string[] leftLines = ReadLines(left);
        string[] rightLines = ReadLines(right);
        int maximum = Math.Max(leftLines.Length, rightLines.Length);
        var changes = Enumerable.Range(0, maximum)
            .Where(index => !string.Equals(
                index < leftLines.Length ? leftLines[index] : null,
                index < rightLines.Length ? rightLines[index] : null,
                StringComparison.Ordinal))
            .Take(100).ToArray();
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("leftName", Path.GetFileName(left));
            writer.WriteString("rightName", Path.GetFileName(right));
            writer.WriteString("leftSha256", Hash(left)); writer.WriteString("rightSha256", Hash(right));
            writer.WriteNumber("changedLineCount", changes.Length); writer.WriteStartArray("changedLines");
            foreach (int line in changes) writer.WriteNumberValue(line + 1);
            writer.WriteEndArray(); writer.WriteString("authority", "sandbox_named_diff_hash_snapshot");
            writer.WriteEndObject();
        }), effectObserved: false);
    }

    private string ResolveRelatedUnique(string query, string left)
    {
        if (!Directory.Exists(_root)) throw new InvalidDataException("sandbox_named_root_not_found");
        string leftStem = Path.GetFileNameWithoutExtension(left);
        string leftExtension = Path.GetExtension(left);
        string[] matches = Enumerate()
            .Where(path => !string.Equals(path, left, StringComparison.OrdinalIgnoreCase)
                && Path.GetFileName(path).Contains(query, StringComparison.OrdinalIgnoreCase))
            .ToArray();
        string[] related = matches.Where(path =>
                string.Equals(Path.GetExtension(path), leftExtension, StringComparison.OrdinalIgnoreCase)
                && Path.GetFileNameWithoutExtension(path).Contains(
                    leftStem, StringComparison.OrdinalIgnoreCase))
            .Take(2).ToArray();
        if (related.Length == 1) return related[0];
        if (related.Length > 1 || matches.Length > 1)
            throw new InvalidDataException("sandbox_named_file_ambiguous");
        if (matches.Length == 0) throw new InvalidDataException("sandbox_named_file_not_found");
        return matches[0];
    }

    private string ResolveUnique(string query, bool exact)
    {
        if (!Directory.Exists(_root)) throw new InvalidDataException("sandbox_named_root_not_found");
        string[] matches = Enumerate().Where(path => exact
                ? string.Equals(Path.GetFileName(path), query, StringComparison.OrdinalIgnoreCase)
                : Path.GetFileName(path).Contains(query, StringComparison.OrdinalIgnoreCase))
            .Take(2).ToArray();
        if (matches.Length == 0) throw new InvalidDataException("sandbox_named_file_not_found");
        if (matches.Length > 1) throw new InvalidDataException("sandbox_named_file_ambiguous");
        return matches[0];
    }

    private IEnumerable<string> Enumerate()
    {
        var options = new EnumerationOptions
        {
            RecurseSubdirectories = true,
            IgnoreInaccessible = true,
            AttributesToSkip = FileAttributes.ReparsePoint,
            MaxRecursionDepth = 20,
        };
        return Directory.EnumerateFiles(_root, "*", options);
    }

    private string ConfinedDestination(string relative)
    {
        if (string.IsNullOrWhiteSpace(relative) || Path.IsPathRooted(relative))
            throw new InvalidDataException("sandbox_move_destination_invalid");
        string root = Path.GetFullPath(_root).TrimEnd(Path.DirectorySeparatorChar);
        string destination = Path.GetFullPath(Path.Combine(root, relative));
        if (!destination.StartsWith(root + Path.DirectorySeparatorChar,
                StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("sandbox_move_destination_invalid");
        return destination;
    }

    private static string SafeFileName(string value)
    {
        string name = value.Trim();
        if (name != Path.GetFileName(name) || name.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0)
            throw new InvalidDataException("sandbox_named_file_name_invalid");
        return name;
    }

    private static string[] ReadLines(string path)
    {
        var info = new FileInfo(path);
        if (info.Length > 2 * 1024 * 1024)
            throw new InvalidDataException("sandbox_diff_file_too_large");
        return File.ReadAllLines(path, Encoding.UTF8);
    }

    private static string Hash(string path)
    {
        using FileStream stream = File.OpenRead(path);
        return Convert.ToHexStringLower(SHA256.HashData(stream));
    }
}
