using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// The conversations kept on this PC (design v4, Sessions: open, rename, new), one file each in
/// <c>&lt;datos&gt;/sessions/</c>, local only like the conversation log (owner, 2026-09-20). Each keeps what the view
/// showed and the mind's own conversation, calls and results included, so an opened session gives the model back what
/// really ran — never a retelling of bare replies, which taught it to say «Listo» without calling (mind.py,
/// new_session).
/// </summary>
internal sealed class FieldSessionStore
{
    internal const int MaximumSessions = 50;
    private const string Schema = "baxy.field-session.v1";

    private readonly string _directory;

    internal FieldSessionStore(string dataRoot)
    {
        _directory = Path.Combine(dataRoot, "sessions");
    }

    internal static FieldSessionStore CreateDefault() => new(MemoryOperationProtector.ResolveDataRoot());

    internal sealed record Session(string Id, string Label, DateTimeOffset Created, DateTimeOffset Updated, JsonArray Items,
        JsonArray? Mind);

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
                ["created"] = session.Created.ToString("O", CultureInfo.InvariantCulture),
                ["updated"] = session.Updated.ToString("O", CultureInfo.InvariantCulture),
                ["items"] = session.Items.DeepClone(),
                ["mind"] = session.Mind?.DeepClone(),
            };
            string path = PathOf(session.Id), temporary = path + ".tmp";
            File.WriteAllText(temporary, document.ToJsonString());
            File.Move(temporary, path, overwrite: true);
            Prune();
            return true;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return false;
        }
    }

    internal bool Rename(string id, string label)
    {
        Session? session = Load(id);
        return session is not null && Save(session with { Label = label });
    }

    // Past the limit, the conversations touched longest ago go.
    private void Prune()
    {
        foreach (Session old in List().Skip(MaximumSessions))
        {
            try
            {
                File.Delete(PathOf(old.Id));
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
            }
        }
    }

    private string PathOf(string id) => Path.Combine(_directory, id + ".json");

    private static bool IsId(string id) => id.Length is > 0 and <= 32 && id.All(static c => char.IsAsciiLetterOrDigit(c));

    private static Session? Read(string path)
    {
        try
        {
            if (!File.Exists(path) || JsonNode.Parse(File.ReadAllText(path)) is not JsonObject document
                || (string?)document["schema"] != Schema
                || (string?)document["id"] is not { } id
                || !DateTimeOffset.TryParse((string?)document["created"], CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out DateTimeOffset created)
                || !DateTimeOffset.TryParse((string?)document["updated"], CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out DateTimeOffset updated))
            {
                return null;
            }

            return new Session(id, (string?)document["label"] ?? string.Empty, created, updated,
                document["items"] as JsonArray ?? [], document["mind"] as JsonArray);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or JsonException
            or InvalidOperationException)
        {
            return null;
        }
    }
}
