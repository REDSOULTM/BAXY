using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class TextToSpeechPreferenceStoreTests
{
    [Test]
    public void PreferencePersistsBothMuteStates()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-tts-pref-" + Guid.NewGuid());
        try
        {
            Assert.That(TextToSpeechPreferenceStore.Read(root), Is.False);

            TextToSpeechPreferenceStore.Write(root, muted: true);
            Assert.That(TextToSpeechPreferenceStore.Read(root), Is.True);

            TextToSpeechPreferenceStore.Write(root, muted: false);
            Assert.That(TextToSpeechPreferenceStore.Read(root), Is.False);
        }
        finally
        {
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }
}
