using System.Text.Json;
using Baxy.Contracts;

namespace Baxy.Kernel.Policy;

/// <summary>
/// Hallazgo de seguridad E030 (w9-sha): «sobrescribe notas.txt…» was refused (version_conflict) with the file's current
/// SHA-256 in the refusal, the model retried with that hash and the file was replaced without the person's yes. An
/// expected version is the caller's word that it saw what it replaces; one the mind knows only because a response that
/// did not complete told it (a refusal, a failure) is no sighting. Such a replacement asks in normal mode, bound to that
/// exact invocation; a version a completed response gave too (file.read, a listing, the write that made it), before or
/// after the refusal, is observed and goes as before. Only what the kernel itself sent counts, never the mind's word.
/// </summary>
public sealed class ToldVersions
{
    // The operations that replace what is there under an expected version: the argument that holds it, the name a
    // result gives it (as the end of a property's name: currentSha256, fileSha256, sha256), the identity beside it in the
    // same result object and in the call, and an argument that, true, keeps every byte there (no replacement). Copying,
    // moving and restoring never write over what exists (destination_exists); a task.complete, reopen or restore loses
    // nothing; deleting and trashing already ask.
    private static readonly Dictionary<string, Expectation> Replacements = new(StringComparer.Ordinal)
    {
        ["file.write"] = new("expectedSha256", "sha256", Identity: null, Keeps: "append"),
        ["note.update"] = new("expectedRevision", "revision", Identity: "noteId", Keeps: null),
        ["task.update"] = new("expectedVersion", "version", Identity: "taskId", Keeps: null),
    };

    private static readonly Expectation[] Kinds = [.. Replacements.Values.DistinctBy(static entry => entry.Kind)];

    // Forgetting an observation only makes a replacement ask; a told version is forgotten oldest first.
    private const int MaximumObserved = 4096;
    private const int MaximumTold = 1024;
    private readonly HashSet<string> _observed = new(StringComparer.Ordinal);
    private readonly HashSet<string> _told = new(StringComparer.Ordinal);
    private readonly Queue<string> _toldOrder = new();

    /// <summary>Whether this operation replaces what is there under an expected version (it asks only sometimes).</summary>
    public static bool ExpectsAVersion(string operation) => Replacements.ContainsKey(operation);

    /// <summary>The versions a response the kernel sent gives: observed when it completed, told otherwise.</summary>
    public void Record(OperationResponse response)
    {
        if (response.Result is not { } result)
        {
            return;
        }

        bool completed = string.Equals(response.Status, OperationStatuses.Completed, StringComparison.Ordinal);
        foreach (string token in Versions(result))
        {
            if (completed)
            {
                _told.Remove(token);
                if (_observed.Count >= MaximumObserved)
                {
                    _observed.Clear();
                }

                _observed.Add(token);
            }
            else if (!_observed.Contains(token) && _told.Add(token))
            {
                _toldOrder.Enqueue(token);
                while (_toldOrder.Count > MaximumTold)
                {
                    _told.Remove(_toldOrder.Dequeue());
                }
            }
        }
    }

    /// <summary>Whether this call replaces what is there under a version that only a response that did not complete gave.</summary>
    public bool OnlyToldBy(string operation, JsonElement arguments)
    {
        if (!Replacements.TryGetValue(operation, out Expectation? expectation)
            || arguments.ValueKind != JsonValueKind.Object
            || (expectation.Keeps is { } keeps
                && arguments.TryGetProperty(keeps, out JsonElement kept)
                && kept.ValueKind == JsonValueKind.True)
            || !arguments.TryGetProperty(expectation.Argument, out JsonElement version)
            || Text(version) is not { } value)
        {
            return false;
        }

        string? identity = null;
        if (expectation.Identity is { } name)
        {
            if (!arguments.TryGetProperty(name, out JsonElement given) || given.ValueKind != JsonValueKind.String)
            {
                return false;
            }

            identity = given.GetString();
        }

        return _told.Contains(Token(expectation.Kind, identity, value));
    }

    // Every version in a result, at any depth: a property whose name ends in a kind, with the identity its kind names
    // beside it in the same object.
    private static IEnumerable<string> Versions(JsonElement element)
    {
        if (element.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement item in element.EnumerateArray())
            {
                foreach (string token in Versions(item))
                {
                    yield return token;
                }
            }

            yield break;
        }

        if (element.ValueKind != JsonValueKind.Object)
        {
            yield break;
        }

        foreach (JsonProperty property in element.EnumerateObject())
        {
            if (Text(property.Value) is { } value)
            {
                foreach (Expectation kind in Kinds)
                {
                    if (!property.Name.EndsWith(kind.Kind, StringComparison.OrdinalIgnoreCase))
                    {
                        continue;
                    }

                    string? identity = null;
                    if (kind.Identity is { } name)
                    {
                        if (!element.TryGetProperty(name, out JsonElement beside)
                            || beside.ValueKind != JsonValueKind.String)
                        {
                            continue;
                        }

                        identity = beside.GetString();
                    }

                    yield return Token(kind.Kind, identity, value);
                }
            }
            else
            {
                foreach (string token in Versions(property.Value))
                {
                    yield return token;
                }
            }
        }
    }

    private static string? Text(JsonElement value) => value.ValueKind switch
    {
        JsonValueKind.String => value.GetString(),
        JsonValueKind.Number => value.TryGetInt64(out long whole)
            ? whole.ToString(System.Globalization.CultureInfo.InvariantCulture)
            : value.GetRawText(),
        _ => null,
    };

    private static string Token(string kind, string? identity, string value) =>
        kind + "\n" + identity?.ToLowerInvariant() + "\n" + value;

    private sealed record Expectation(string Argument, string Kind, string? Identity, string? Keeps);
}
