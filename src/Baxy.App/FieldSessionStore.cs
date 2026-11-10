using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Security.Windows;

namespace Baxy.App;

/// <summary>
/// The conversations kept on this PC (design v4, Sessions: open, rename, new), one file each in
/// <c>&lt;datos&gt;/sessions/</c>, local only like the conversation log (owner, 2026-09-20). Each keeps what the view
/// showed and the mind's own conversation, calls and results included, so an opened session gives the model back what
/// really ran — never a retelling of bare replies, which taught it to say «Listo» without calling (mind.py,
/// new_session).
/// <para>
/// 2026-10-22, review of the App: the mind's conversation holds what the view never shows (a secret typed and masked on
/// screen, what memory calls read), so each file is sealed with the profile's DPAPI-wrapped key (AES-GCM,
/// <see cref="WindowsProtectedPayload"/>, as the private memory) and opens only for this Windows user. A session kept in
/// clear before then is read once and written back sealed.
/// </para>
/// </summary>
internal sealed class FieldSessionStore
{
    internal const int MaximumSessions = 50;
    private const string Schema = "baxy.field-session.v1";

    private readonly string _directory;
    private readonly WindowsProtectedPayload _seal;

    internal FieldSessionStore(string dataRoot)
    {
        _directory = Path.Combine(dataRoot, "sessions");
        _seal = new WindowsProtectedPayload(Path.Combine(dataRoot, "security", "field-sessions.v1.key"));
    }

    internal static FieldSessionStore CreateDefault() => new(MemoryOperationProtector.ResolveDataRoot());

    /// <summary>Who gave a conversation its name: its first words (until it closes), the model when it closed
    /// (FieldProductChannel.NameClosedAsync), or the person. The model never names over the person's own; a conversation
    /// kept before this was known counts as the person's.</summary>
    internal const string LabelByFirst = "first";
    internal const string LabelByModel = "model";
    internal const string LabelByPerson = "person";

    internal sealed record Session(string Id, string Label, DateTimeOffset Created, DateTimeOffset Updated, JsonArray Items,
        JsonArray? Mind, string LabelBy = LabelByPerson);

    internal IReadOnlyList<Session> List()
    {
        var sessions = new List<Session>();
        if (!Directory.Exists(_directory))
        {
            return sessions;
        }

        foreach (string file in Directory.EnumerateFiles(_directory, "*.json"))
        {
            if (Read(file) is { } session)
            {
                sessions.Add(session with { Items = [], Mind = null });
            }
        }

        return [.. sessions.OrderByDescending(static s => s.Updated)];
    }

    internal Session? Load(string id) => IsId(id) ? Read(PathOf(id)) : null;

    internal bool Save(Session session)
    {
        if (!Write(session))
        {
            return false;
        }

        Prune();
        return true;
    }

    private bool Write(Session session)
    {
        if (!IsId(session.Id))
        {
            return false;
        }

        try
        {
            Directory.CreateDirectory(_directory);
            var document = new JsonObject
            {
                ["schema"] = Schema,
                ["id"] = session.Id,
                ["label"] = session.Label,
                ["labelBy"] = session.LabelBy,
                ["created"] = session.Created.ToString("O", CultureInfo.InvariantCulture),
                ["updated"] = session.Updated.ToString("O", CultureInfo.InvariantCulture),
                ["items"] = session.Items.DeepClone(),
                ["mind"] = session.Mind?.DeepClone(),
            };
            string path = PathOf(session.Id), temporary = path + ".tmp";
            byte[] plain = Encoding.UTF8.GetBytes(document.ToJsonString());
            try
            {
                File.WriteAllBytes(temporary, _seal.Seal(plain, Schema));
            }
            finally
            {
                CryptographicOperations.ZeroMemory(plain);
            }

            global::Baxy.Kernel.AtomicFileReplacement.ReplaceOrCreate(temporary, path);
            return true;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException
            or ProtectedPayloadException)
        {
            return false;
        }
    }

    internal bool Rename(string id, string label)
    {
        Session? session = Load(id);
        return session is not null && Save(session with { Label = label, LabelBy = LabelByPerson });
    }

    /// <summary>
    /// BAXY Renew al máximo 11.4 (identity: the memory «se puede borrar entera»; the mind's conversation here holds what
    /// memory calls read): every kept conversation but <paramref name="keep"/> goes, with any half-written copy. How
    /// many conversations went.
    /// </summary>
    internal int DeleteAll(string? keep = null)
    {
        if (!Directory.Exists(_directory))
        {
            return 0;
        }

        int deleted = 0;
        foreach (string file in Directory.EnumerateFiles(_directory, "*.json*"))
        {
            string name = Path.GetFileName(file);
            if ((keep is null || (name != keep + ".json" && name != keep + ".json.tmp")) && Delete(file)
                && name.EndsWith(".json", StringComparison.Ordinal))
            {
                deleted++;
            }
        }

        return deleted;
    }

    // Past the limit, the conversations touched longest ago go.
    private void Prune()
    {
        foreach (Session old in List().Skip(MaximumSessions))
        {
            Delete(PathOf(old.Id));
        }
    }

    private static bool Delete(string path)
    {
        try
        {
            File.Delete(path);
            return true;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return false;
        }
    }

    private string PathOf(string id) => Path.Combine(_directory, id + ".json");

    private static bool IsId(string id) => id.Length is > 0 and <= 32 && id.All(static c => char.IsAsciiLetterOrDigit(c));

    private Session? Read(string path)
    {
        try
        {
            if (!File.Exists(path))
            {
                return null;
            }

            byte[] stored = File.ReadAllBytes(path);
            // A session kept before the files were sealed is plain JSON: it is read this once and written back sealed.
            bool clear = stored is [(byte)'{', ..];
            byte[] plain = clear ? stored : _seal.Open(stored, Schema);
            JsonNode? parsed;
            try
            {
                parsed = JsonNode.Parse(plain);
            }
            finally
            {
                CryptographicOperations.ZeroMemory(plain);
            }

            if (parsed is not JsonObject document
                || (string?)document["schema"] != Schema
                || (string?)document["id"] is not { } id
                || !DateTimeOffset.TryParse((string?)document["created"], CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out DateTimeOffset created)
                || !DateTimeOffset.TryParse((string?)document["updated"], CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out DateTimeOffset updated))
            {
                return null;
            }

            string labelBy = (string?)document["labelBy"] is LabelByFirst or LabelByModel ? (string)document["labelBy"]! : LabelByPerson;
            var session = new Session(id, (string?)document["label"] ?? string.Empty, created, updated,
                document["items"] as JsonArray ?? [], document["mind"] as JsonArray, labelBy);
            if (clear && id == Path.GetFileNameWithoutExtension(path))
            {
                Write(session);
            }

            return session;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException
            or InvalidOperationException or ProtectedPayloadException)
        {
            return null;
        }
    }
}
