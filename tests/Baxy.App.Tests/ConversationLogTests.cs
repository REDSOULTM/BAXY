using System.IO;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The private log of the conversation (src/Baxy.App/ConversationLog.cs): it goes with «olvida todo» and with deleting
/// every conversation, as the sealed kept conversations do (auditoría de la App, 2026-10-23).
/// </summary>
[TestFixture]
public sealed class ConversationLogTests
{
    [Test]
    public void ClearingTheLogTakesItsArchiveAndWhatFollowsIsLoggedAgain()
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-app-tests", Guid.NewGuid().ToString("N"));
        try
        {
            var log = new ConversationLog(folder, maximumBytes: 300);
            for (int line = 0; line < 4; line++)
            {
                log.Append(new ConversationMessage("Tú", "mi ciudad es Ñuñoa " + line, true, DateTimeOffset.Now));
            }

            string live = Path.Combine(folder, "conversation.v1.jsonl");
            Assert.That(File.Exists(live) && File.Exists(live + BoundedJsonlFile.ArchiveSuffix), Is.True);

            log.Clear();

            Assert.That(File.Exists(live) || File.Exists(live + BoundedJsonlFile.ArchiveSuffix), Is.False);
            log.Append(new ConversationMessage("BAXY", "Listo.", false, DateTimeOffset.Now));
            Assert.That(File.ReadAllText(live), Does.Contain("Listo.").And.Not.Contain("Ñuñoa"));
        }
        finally
        {
            if (Directory.Exists(folder))
            {
                Directory.Delete(folder, recursive: true);
            }
        }
    }
}
