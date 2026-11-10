using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Security.Windows;

namespace Baxy.App;

/// <summary>
/// Settings → Behavior (owner's order of 2026-11-08, 00_IDENTIDAD «Abierto y personalizable»): the person's own texts for
/// BAXY's personality and tone, how it replies, and their standing preferences, kept in &lt;data&gt;\behavior.v1.json. Its name
/// and identity are not one of them: the mind keeps them fixed before the person's texts (behavior.py IDENTITY). Only the
/// texts the person wrote are kept; a field that is not there is the mind's factory text (src/baxy_mind/behavior.py, which
/// the mind's hello shows). They go to the mind with its catalog (MindSidecarClient.Behavior) and are words in its system
/// text, nothing else: the tools are the core's catalog and the kernel still authorizes and confirms every call. A change
/// relaunches the mind as a change of model does (MainWindowViewModel.BehaviorChanged), so its new prompt prefix is read
/// once and kept under its own key.
/// <para>REV_APP PRM-2 (2026-11-09): the file was kept in clear, beside a history that is sealed. It is what the person
/// wrote about themselves, so it is sealed the same way (<see cref="WindowsProtectedPayload"/>, as
/// <see cref="FieldSessionStore"/>): it opens only for this Windows user. One kept in clear before is read that once and
/// written back sealed.</para>
/// </summary>
internal sealed class PersonBehavior
{
    internal const string FileName = "behavior.v1.json";
    // The mind's behavior.MAX_CHARS (tests/test_mind_comportamiento.py holds them equal).
    internal const int MaxChars = 800;
    internal static readonly string[] Fields = ["personality", "replies", "preferences"];
    private const string Purpose = "baxy.behavior.v1";

    private readonly string _path;
    private readonly WindowsProtectedPayload _seal;
    private readonly object _sync = new();
    // The texts the running mind was configured with (ForMind as JSON), null with none; whether a mind came up at all
    // (with none, a change waits for the next start and asks for no relaunch).
    private string? _applied;
    private bool _started;

    internal PersonBehavior(string dataRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(dataRoot);
        _path = Path.Combine(dataRoot, FileName);
        _seal = new WindowsProtectedPayload(Path.Combine(dataRoot, "security", "behavior.v1.key"));
    }

    /// <summary>The person's own texts, by field: only the ones written, never empty ones.</summary>
    internal JsonObject Texts()
    {
        lock (_sync)
        {
            return Read();
        }
    }

    /// <summary>What the mind's catalog.configure carries: the person's texts, or null with none (the request is then the
    /// very one sent before this setting existed).</summary>
    internal JsonObject? ForMind()
    {
        JsonObject texts = Texts();
        return texts.Count == 0 ? null : texts;
    }

    /// <summary>A mind came up configured with <paramref name="sent"/>.</summary>
    internal void Started(JsonObject? sent)
    {
        lock (_sync)
        {
            _applied = sent?.ToJsonString();
            _started = true;
        }
    }

    /// <summary>Whether a mind came up and the texts kept differ from the ones it was configured with. Before any mind came
    /// up (a start that failed, no runtime), the next start takes them as they are.</summary>
    internal bool NeedsSwitch
    {
        get
        {
            string? now = ForMind()?.ToJsonString();
            lock (_sync)
            {
                return _started && !string.Equals(now, _applied, StringComparison.Ordinal);
            }
        }
    }

    /// <summary>
    /// The person's change: <c>reset</c> true puts every text back to the factory's; otherwise each field given is the
    /// person's text, and null or blank puts that one back. Null when kept, or why it was refused (nothing is kept then).
    /// </summary>
    internal string? Apply(JsonObject body)
    {
        ArgumentNullException.ThrowIfNull(body);
        lock (_sync)
        {
            JsonNode? reset = body["reset"];
            bool resetAll = false;
            if (reset is not null && (reset is not JsonValue flag || !flag.TryGetValue(out resetAll)))
            {
                return "behavior_invalid_text";
            }

            JsonObject texts = resetAll ? [] : Read();
            foreach (string field in Fields)
            {
                if (!body.ContainsKey(field))
                {
                    continue;
                }

                JsonNode? given = body[field];
                if (given is not null && (given is not JsonValue value || !value.TryGetValue(out string? _)))
                {
                    return "behavior_invalid_text";
                }

                string text = ((string?)given ?? string.Empty).Trim();
                if (text.Length > MaxChars)
                {
                    return "behavior_too_long";
                }

                if (text.Length == 0)
                {
                    texts.Remove(field);
                }
                else
                {
                    texts[field] = text;
                }
            }

            return Write(texts) ? null : "behavior_not_saved";
        }
    }

    // Sealed, or no file with no text. False when it could not be kept.
    private bool Write(JsonObject texts)
    {
        try
        {
            if (texts.Count == 0)
            {
                File.Delete(_path);
                return true;
            }

            Directory.CreateDirectory(Path.GetDirectoryName(_path)!);
            string temporary = _path + ".tmp";
            byte[] plain = Encoding.UTF8.GetBytes(texts.ToJsonString());
            try
            {
                File.WriteAllBytes(temporary, _seal.Seal(plain, Purpose));
            }
            finally
            {
                CryptographicOperations.ZeroMemory(plain);
            }

            File.Move(temporary, _path, overwrite: true);
            return true;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException
            or ProtectedPayloadException)
        {
            return false;
        }
    }

    /// <summary>The view's state: the mind's fixed identity, which nobody edits (owner's limit of 2026-11-08: BAXY is always
    /// called BAXY), and its factory texts, as its hello told them (<paramref name="hello"/>; null until a mind said so),
    /// the person's (null where the factory's is used), the limit, and whether the mind is being relaunched on them.</summary>
    internal JsonObject Json(JsonObject? hello, bool switching)
    {
        JsonObject? factory = hello?["factory"] as JsonObject;
        JsonObject texts = Texts();
        var own = new JsonObject();
        foreach (string field in Fields)
        {
            own[field] = texts[field]?.DeepClone();
        }

        return new JsonObject
        {
            ["identity"] = hello?["identity"]?.DeepClone(),
            ["factory"] = factory?.DeepClone(),
            ["texts"] = own,
            ["maxChars"] = MaxChars,
            ["switching"] = switching || NeedsSwitch,
        };
    }

    // Unreadable, not this user's or not an object is no text of the person's: the factory's, as with no file.
    private JsonObject Read()
    {
        var texts = new JsonObject();
        try
        {
            if (!File.Exists(_path))
            {
                return texts;
            }

            byte[] stored = File.ReadAllBytes(_path);
            // Kept before the file was sealed, it is plain JSON, read then as text (so with the mark of UTF-8 or a blank
            // before it, as one saved by hand has): read this once and written back sealed.
            int mark = stored.AsSpan().StartsWith(Encoding.UTF8.Preamble) ? Encoding.UTF8.Preamble.Length : 0;
            bool clear = stored.AsSpan(mark).TrimStart(" \t\r\n"u8) is [(byte)'{', ..];
            byte[] plain = clear ? stored : _seal.Open(stored, Purpose);
            JsonNode? parsed;
            try
            {
                parsed = JsonNode.Parse(plain.AsSpan(clear ? mark : 0));
            }
            finally
            {
                CryptographicOperations.ZeroMemory(plain);
            }

            if (parsed is JsonObject kept)
            {
                foreach (string field in Fields)
                {
                    if (kept[field] is JsonValue value && value.TryGetValue(out string? text) && text.Trim().Length > 0)
                    {
                        texts[field] = text.Trim();
                    }
                }
            }

            if (clear && texts.Count > 0)
            {
                _ = Write(texts);
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException
            or ProtectedPayloadException)
        {
            return [];
        }

        return texts;
    }
}
