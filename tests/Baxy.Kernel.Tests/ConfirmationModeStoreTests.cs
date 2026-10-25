using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// The file that switches confirmations off (calidad del PC, 2026-10-25): only an explicit word turns bypass on, any
/// other content is normal, and a file that cannot be read says so instead of passing for «normal» (revisión
/// 2026-10-22, C-3), so a switch never flips on what it could not read.
/// </summary>
[TestFixture]
public sealed class ConfirmationModeStoreTests
{
    [TestCase("bypass", ConfirmationMode.Bypass)]
    [TestCase("BYPASS", ConfirmationMode.Bypass)]
    [TestCase("  bypass\r\n", ConfirmationMode.Bypass)]
    [TestCase("all", ConfirmationMode.Bypass)]
    [TestCase("normal", ConfirmationMode.Normal)]
    [TestCase("Normal\n", ConfirmationMode.Normal)]
    [TestCase("confirm_risky", ConfirmationMode.Normal)]
    [TestCase("risk-aware", ConfirmationMode.Normal)]
    public void The_words_of_the_file_are_read_in_any_case_and_around_spaces(string text, ConfirmationMode expected) =>
        Assert.That(ConfirmationModeStore.Parse(text), Is.EqualTo(expected));

    [TestCase(null)]
    [TestCase("")]
    [TestCase("   ")]
    [TestCase("bypass please")]
    [TestCase("by pass")]
    [TestCase("true")]
    [TestCase("1")]
    [TestCase("bypass\nnormal")]
    public void Anything_else_is_no_word(string? text) =>
        Assert.That(ConfirmationModeStore.Parse(text), Is.Null);

    [TestCase("bypass please")]
    [TestCase("true")]
    [TestCase("")]
    public void A_file_without_a_word_is_read_as_normal(string text)
    {
        using var root = new Root();
        File.WriteAllText(Path.Combine(root.Path, ConfirmationModeStore.FileName), text);

        Assert.Multiple(() =>
        {
            Assert.That(ConfirmationModeStore.TryRead(root.Path, out ConfirmationMode mode), Is.True);
            Assert.That(mode, Is.EqualTo(ConfirmationMode.Normal));
            Assert.That(ConfirmationModeStore.Read(root.Path), Is.EqualTo(ConfirmationMode.Normal));
        });
    }

    [Test]
    public void A_file_another_program_holds_locked_is_unreadable_not_normal()
    {
        using var root = new Root();
        string path = Path.Combine(root.Path, ConfirmationModeStore.FileName);
        ConfirmationModeStore.Write(root.Path, ConfirmationMode.Bypass);

        bool readable;
        ConfirmationMode mode;
        using (new FileStream(path, FileMode.Open, FileAccess.ReadWrite, FileShare.None))
        {
            readable = ConfirmationModeStore.TryRead(root.Path, out mode);
        }

        Assert.Multiple(() =>
        {
            Assert.That(readable, Is.False);
            Assert.That(mode, Is.EqualTo(ConfirmationMode.Normal));
            Assert.That(ConfirmationModeStore.TryRead(root.Path, out ConfirmationMode after), Is.True);
            Assert.That(after, Is.EqualTo(ConfirmationMode.Bypass));
        });
    }

    [Test]
    public void No_data_root_is_readable_and_normal_and_writing_needs_one()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ConfirmationModeStore.TryRead(null, out ConfirmationMode none), Is.True);
            Assert.That(none, Is.EqualTo(ConfirmationMode.Normal));
            Assert.That(ConfirmationModeStore.TryRead("  ", out ConfirmationMode blank), Is.True);
            Assert.That(blank, Is.EqualTo(ConfirmationMode.Normal));
            Assert.That(() => ConfirmationModeStore.Write(" ", ConfirmationMode.Bypass), Throws.ArgumentException);
        });
    }

    [Test]
    public void Writing_creates_a_missing_data_root_and_writes_one_word()
    {
        using var root = new Root();
        string nested = Path.Combine(root.Path, "perfil");

        ConfirmationModeStore.Write(nested, ConfirmationMode.Bypass);
        string bypass = File.ReadAllText(Path.Combine(nested, ConfirmationModeStore.FileName));
        ConfirmationModeStore.Write(nested, ConfirmationMode.Normal);
        string normal = File.ReadAllText(Path.Combine(nested, ConfirmationModeStore.FileName));

        Assert.Multiple(() =>
        {
            Assert.That(bypass, Is.EqualTo("bypass"));
            Assert.That(normal, Is.EqualTo("normal"));
        });
    }

    private sealed class Root : IDisposable
    {
        internal Root()
        {
            Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-confirmation-store-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(Path);
        }

        internal string Path { get; }

        public void Dispose()
        {
            try
            {
                Directory.Delete(Path, recursive: true);
            }
            catch (IOException)
            {
            }
        }
    }
}
