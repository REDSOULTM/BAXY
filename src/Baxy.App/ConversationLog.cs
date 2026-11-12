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
/// que reescribir lo dicho. <c>BAXY_CONVERSATION_LOG=0</c> lo desactiva. Tiene
/// tope (<see cref="BoundedJsonlFile"/>): al pasarlo, lo anterior queda en
/// <c>conversation.v1.jsonl.1</c> y el registro vivo empieza de nuevo.
/// PRV1 (revisión de privacidad 2026-11-09, PRIV-02): guardaba en claro cada mensaje y ningún texto del producto lo
/// decía. La identidad dice qué guarda BAXY de la persona («las preferencias del usuario, lo que suele pedir, y la
/// conversación reciente», que «se puede ver, editar y borrar entero»: documentacion/00_IDENTIDAD.md, «Memoria y
/// privacidad»), y eso son las conversaciones guardadas, selladas. Este registro es para medir: en el producto anota la
/// hora, quién habló, la ruta y la latencia, sin el texto; lo guarda entero sólo quien lo pide en su PC con
/// <c>BAXY_TRACE_WORDS=1</c> (la misma variable que lee la traza de la mente, src/baxy_mind/__main__.py).
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

    internal const string WordsEnvironmentVariable = "BAXY_TRACE_WORDS";

    private readonly BoundedJsonlFile _file;
    private readonly bool _keepsWords;
    private readonly object _gate = new();
    private DateTimeOffset? _lastUserMessageAt;
    private int _turn;

    internal ConversationLog(
        string directory,
        long maximumBytes = BoundedJsonlFile.DefaultMaximumBytes,
        bool keepsWords = true)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(directory);
        _file = new BoundedJsonlFile(Path.Combine(directory, "conversation.v1.jsonl"), maximumBytes);
        _keepsWords = keepsWords;
    }

    internal static ConversationLog? CreateDefault()
    {
        if (string.Equals(Environment.GetEnvironmentVariable("BAXY_CONVERSATION_LOG"), "0", StringComparison.Ordinal))
        {
            return null;
        }

        try
        {
            return new ConversationLog(Path.Combine(MemoryOperationProtector.ResolveDataRoot(), "conversation"),
                keepsWords: KeepsWords(Environment.GetEnvironmentVariable(WordsEnvironmentVariable)));
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or InvalidOperationException)
        {
            return null;
        }
    }

    /// <summary>Whether the product's log keeps what was said: only where the PC's owner set the variable to «1».</summary>
    /// <remarks>UNI1 (REV8 P3): «1» and the other usual ways of saying yes to a variable (y, yes, t, true, on, as Python's
    /// strtobool reads them), as the mind reads it (src/baxy_mind/__main__.py, trace_words); «true» used to remove
    /// what the owner meant to keep.</remarks>
    internal static bool KeepsWords(string? variable) =>
        variable?.Trim().ToLowerInvariant() is "1" or "y" or "yes" or "t" or "true" or "on";

    /// <summary>Whether the log holds anything (its file or its archive): «Olvidar todo» would delete it (PRV1 D7).</summary>
    internal bool HoldsAny
    {
        get
        {
            lock (_gate)
            {
                return File.Exists(_file.FilePath) || File.Exists(_file.ArchivePath);
            }
        }
    }

    /// <summary>
    /// The person had BAXY forget everything, or deleted every conversation: this log goes too, its archive included.
    /// Auditoría de la App (2026-10-23): the kept conversations are sealed and deleted then because they hold what memory
    /// calls read, and this log kept the same lines in clear text after both. What follows is logged again.
    /// </summary>
    internal void Clear()
    {
        lock (_gate)
        {
            foreach (string path in (string[])[_file.FilePath, _file.ArchivePath])
            {
                try
                {
                    File.Delete(path);
                }
                catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
                {
                    // Held by another reader for a moment: the next forget takes it.
                }
            }

            _lastUserMessageAt = null;
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
            };
            if (_keepsWords)
            {
                payload["text"] = message.Body;
            }

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
                Directory.CreateDirectory(Path.GetDirectoryName(_file.FilePath)!);
                _file.AppendLine(JsonSerializer.Serialize(payload, JsonOptions));
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                // The log is a convenience for the owner; the conversation goes on.
            }
        }
    }
}
