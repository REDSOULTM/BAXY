using Baxy.Providers.Windows.Clipboard;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class WindowsClipboardProviderTests
{
    [Test]
    public async Task ReadRequiresTwoIdenticalSnapshots()
    {
        var platform = new FakeClipboardPlatform("privado", 7);
        var provider = new WindowsClipboardProvider(platform);

        ClipboardTextSnapshot result = await provider.ReadTextAsync(100, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Text, Is.EqualTo("privado"));
            Assert.That(result.SequenceNumber, Is.EqualTo(7));
            Assert.That(platform.ReadCount, Is.EqualTo(2));
        });
    }

    [Test]
    public void ChangedClipboardDuringReadFailsClosed()
    {
        var platform = new FakeClipboardPlatform("uno", 3) { ChangeOnSecondRead = true };
        var provider = new WindowsClipboardProvider(platform);

        Assert.That(
            async () => await provider.ReadTextAsync(100, CancellationToken.None),
            Throws.TypeOf<ClipboardProviderException>()
                .With.Property(nameof(ClipboardProviderException.Code))
                .EqualTo("clipboard_changed_during_read"));
    }

    [Test]
    public async Task WriteReopensAndVerifiesExactTextAndSequence()
    {
        var platform = new FakeClipboardPlatform("antes", 10);
        var provider = new WindowsClipboardProvider(platform);

        ClipboardWriteResult result = await provider.WriteTextAsync("después", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(platform.Text, Is.EqualTo("después"));
            Assert.That(platform.ReplaceCount, Is.EqualTo(1));
            Assert.That(platform.ReadCount, Is.EqualTo(3));
            Assert.That(result.SequenceNumber, Is.EqualTo(11));
            Assert.That(result.CharacterCount, Is.EqualTo(7));
            Assert.That(result.Changed, Is.True);
        });
    }

    private sealed class FakeClipboardPlatform(string text, uint sequence) : IClipboardPlatform
    {
        public string Text { get; private set; } = text;

        public uint Sequence { get; private set; } = sequence;

        public int ReadCount { get; private set; }

        public int ReplaceCount { get; private set; }

        public bool ChangeOnSecondRead { get; init; }

        public uint GetSequenceNumber() => Sequence;

        public ClipboardTextSnapshot ReadText(int maximumCharacters)
        {
            ReadCount++;
            if (ChangeOnSecondRead && ReadCount == 2)
            {
                Text = "dos";
                Sequence++;
            }

            bool truncated = Text.Length > maximumCharacters;
            string bounded = truncated ? Text[..maximumCharacters] : Text;
            return new ClipboardTextSnapshot(bounded, bounded.Length, truncated, Sequence);
        }

        public void ReplaceText(string text)
        {
            ReplaceCount++;
            Text = text;
            Sequence++;
        }
    }
}
