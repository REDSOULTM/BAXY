using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Baxy.App;

/// <summary>
/// Registro privado de la conversación (decisión del dueño, 2026-09-20): cada
/// mensaje de la persona y cada respuesta de BAXY, con su hora, la ruta que la
/// produjo y la latencia desde el último mensaje de la persona. Vive sólo en el
/// perfil local (<c>&lt;datos&gt;/conversation/conversation.v1.jsonl</c>) y nunca
/// sale del PC; sirve para reportar fallos y latencias del uso diario sin tener
/// que reescribir lo dicho. <c>BAXY_CONVERSATION_LOG=0</c> lo desactiva.
/// </summary>
internal sealed class ConversationLog
{
    internal const string Schema = "baxy.conversation.v1";

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        WriteIndented = false,
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    private readonly string _path;
    private readonly object _gate = new();
    private DateTimeOffset? _lastUserMessageAt;
    private int _turn;

    internal ConversationLog(string directory)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(directory);
        _path = Path.Combine(directory, "conversation.v1.jsonl");
    }

    internal string FilePath => _path;

    internal static ConversationLog? CreateDefault()
    {
        if (string.Equals(Environment.GetEnvironmentVariable("BAXY_CONVERSATION_LOG"), "0", StringComparison.Ordinal))
        {
            return null;
        }

        try
        {
            return new ConversationLog(Path.Combine(MemoryOperationProtector.ResolveDataRoot(), "conversation"));
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or InvalidOperationException)
        {
            return null;
        }
    }

    /// <summary>Appends one message; a failure to write never reaches the shell.</summary>
    internal void Append(ConversationMessage message)
    {
        ArgumentNullException.ThrowIfNull(message);
        lock (_gate)
        {
            long? latencyMs = null;
            if (message.IsUser)
            {
                _turn++;
                _lastUserMessageAt = message.CreatedAt;
            }
            else if (_lastUserMessageAt is { } asked)
            {
                latencyMs = (long)Math.Max(0, (message.CreatedAt - asked).TotalMilliseconds);
            }

            var payload = new Dictionary<string, object?>
            {
                ["schema"] = Schema,
                ["utc"] = message.CreatedAt.ToUniversalTime().ToString("O", CultureInfo.InvariantCulture),
                ["local"] = message.CreatedAt.ToLocalTime().ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture),
                ["turn"] = _turn,
                ["role"] = message.IsUser ? "user" : "assistant",
                ["speaker"] = message.Speaker,
                ["text"] = message.Body,
            };
            if (message.Route is not null)
            {
                payload["route"] = message.Route;
            }

            if (latencyMs is not null)
            {
                payload["latency_ms"] = latencyMs;
            }

            try
            {
                Directory.CreateDirectory(System.IO.Path.GetDirectoryName(_path)!);
                File.AppendAllText(_path, JsonSerializer.Serialize(payload, JsonOptions) + Environment.NewLine);
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                // The log is a convenience for the owner; the conversation goes on.
            }
        }
    }
}
