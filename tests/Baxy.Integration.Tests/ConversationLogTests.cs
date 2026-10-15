using System.Text.Json;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Registro privado de la conversación (dueño, 2026-09-20): cada mensaje queda en
/// el perfil con su hora, ruta y la latencia de la respuesta desde el último
/// mensaje de la persona; un directorio no escribible no rompe la conversación.
/// </summary>
[TestFixture]
public sealed class ConversationLogTests
{
    [Test]
    public void MessagesAreAppendedWithTurnNumbersAndReplyLatency()
    {
        string directory = Path.Combine(Path.GetTempPath(), "baxy-conversation-log-" + Guid.NewGuid().ToString("N"));
        try
        {
            var log = new ConversationLog(directory);
            DateTimeOffset asked = new(2026, 9, 20, 20, 15, 0, TimeSpan.FromHours(-3));
            log.Append(new ConversationMessage("Vos", "abrí steam", true, asked));
            log.Append(new ConversationMessage("BAXY", "Steam ya estaba abierto.", false, asked.AddMilliseconds(1_250), "status"));
            log.Append(new ConversationMessage("Vos", "poné un video de batman", true, asked.AddSeconds(40)));
            log.Append(new ConversationMessage("BAXY", "Reproduciendo Batwheels.", false, asked.AddSeconds(45).AddMilliseconds(400)));

            string[] lines = File.ReadAllLines(log.FilePath);
            Assert.That(lines, Has.Length.EqualTo(4));
            using JsonDocument first = JsonDocument.Parse(lines[0]);
            using JsonDocument reply = JsonDocument.Parse(lines[1]);
            using JsonDocument last = JsonDocument.Parse(lines[3]);
            Assert.Multiple(() =>
            {
                Assert.That(first.RootElement.GetProperty("schema").GetString(), Is.EqualTo(ConversationLog.Schema));
                Assert.That(first.RootElement.GetProperty("role").GetString(), Is.EqualTo("user"));
                Assert.That(first.RootElement.GetProperty("turn").GetInt32(), Is.EqualTo(1));
                Assert.That(first.RootElement.GetProperty("text").GetString(), Is.EqualTo("abrí steam"));
                Assert.That(first.RootElement.TryGetProperty("latency_ms", out _), Is.False);
                Assert.That(reply.RootElement.GetProperty("role").GetString(), Is.EqualTo("assistant"));
                Assert.That(reply.RootElement.GetProperty("latency_ms").GetInt64(), Is.EqualTo(1_250));
                Assert.That(reply.RootElement.GetProperty("route").GetString(), Is.EqualTo("status"));
                Assert.That(last.RootElement.GetProperty("turn").GetInt32(), Is.EqualTo(2));
                Assert.That(last.RootElement.GetProperty("latency_ms").GetInt64(), Is.EqualTo(5_400));
                Assert.That(last.RootElement.GetProperty("utc").GetString(), Does.EndWith("Z").Or.Contain("+00:00"));
            });
        }
        finally
        {
            try { Directory.Delete(directory, recursive: true); } catch (IOException) { }
        }
    }

    [Test]
    public void AnUnwritableDirectoryNeverThrows()
    {
        string blocked = Path.Combine(Path.GetTempPath(), "baxy-conversation-log-blocked-" + Guid.NewGuid().ToString("N"));
        File.WriteAllText(blocked, "a file where the directory should be");
        try
        {
            var log = new ConversationLog(blocked);
            Assert.DoesNotThrow(() => log.Append(new ConversationMessage("Vos", "hola", true, DateTimeOffset.Now)));
        }
        finally
        {
            File.Delete(blocked);
        }
    }

    [Test]
    public void TheEnvironmentSwitchDisablesTheLog()
    {
        string? previous = Environment.GetEnvironmentVariable("BAXY_CONVERSATION_LOG");
        try
        {
            Environment.SetEnvironmentVariable("BAXY_CONVERSATION_LOG", "0");
            Assert.That(ConversationLog.CreateDefault(), Is.Null);
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_CONVERSATION_LOG", previous);
        }
    }
}
