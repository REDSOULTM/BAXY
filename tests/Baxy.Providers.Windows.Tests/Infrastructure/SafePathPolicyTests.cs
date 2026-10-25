using Baxy.Providers.Windows.Infrastructure;
using Baxy.Tests;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests.Infrastructure;

/// <summary>
/// The state directory of the audio invocations (calidad del PC, 2026-10-25: nobody tested SafePathPolicy itself). A
/// junction anywhere on the way, at the leaf or above it, makes the path untrusted, and creating the directory through
/// one fails before anything is written where the junction points.
/// </summary>
[TestFixture]
internal sealed class SafePathPolicyTests
{
    private string _root = null!;

    [SetUp]
    public void SetUp()
    {
        _root = Path.Combine(Path.GetTempPath(), $"baxy-safe-path-{Guid.NewGuid():N}");
        Directory.CreateDirectory(_root);
    }

    [TearDown]
    public void TearDown()
    {
        try
        {
            Directory.Delete(_root, recursive: true);
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }
    }

    [Test]
    public void A_plain_directory_is_trusted_and_a_missing_one_is_not()
    {
        string plain = Directory.CreateDirectory(Path.Combine(_root, "estado")).FullName;

        Assert.Multiple(() =>
        {
            Assert.That(SafePathPolicy.IsExistingPathWithoutReparse(plain), Is.True);
            Assert.That(SafePathPolicy.IsExistingPathWithoutReparse(Path.Combine(_root, "falta")), Is.False);
            Assert.That(SafePathPolicy.IsExistingPathWithoutReparse(""), Is.False);
            Assert.That(SafePathPolicy.IsExistingPathWithoutReparse("C:\\a\0b"), Is.False);
        });
    }

    [Test]
    public void A_junction_at_the_leaf_or_above_it_is_not_trusted()
    {
        string target = Directory.CreateDirectory(Path.Combine(_root, "otro")).FullName;
        Directory.CreateDirectory(Path.Combine(target, "dentro"));
        string link = NtfsTestJunction.Create(Path.Combine(_root, "enlace"), target).FullName;

        Assert.Multiple(() =>
        {
            Assert.That(SafePathPolicy.IsExistingPathWithoutReparse(link), Is.False);
            Assert.That(SafePathPolicy.IsExistingPathWithoutReparse(Path.Combine(link, "dentro")), Is.False);
            Assert.That(SafePathPolicy.IsExistingPathWithoutReparse(Path.Combine(target, "dentro")), Is.True);
        });
    }

    [Test]
    public void Creating_through_a_junction_fails_and_writes_nothing_where_it_points()
    {
        string target = Directory.CreateDirectory(Path.Combine(_root, "otro")).FullName;
        string link = NtfsTestJunction.Create(Path.Combine(_root, "enlace"), target).FullName;

        Assert.Multiple(() =>
        {
            Assert.That(
                () => SafePathPolicy.NormalizeAndCreatePrivateDirectory(Path.Combine(link, "audio", "estado")),
                Throws.InstanceOf<IOException>());
            Assert.That(() => SafePathPolicy.NormalizeAndCreatePrivateDirectory(link), Throws.InstanceOf<IOException>());
            Assert.That(Directory.EnumerateFileSystemEntries(target), Is.Empty);
        });
    }

    [Test]
    public void A_missing_plain_directory_is_created_with_its_parents_and_returned_without_a_trailing_separator()
    {
        string wanted = Path.Combine(_root, "audio", "estado") + Path.DirectorySeparatorChar;

        string created = SafePathPolicy.NormalizeAndCreatePrivateDirectory(wanted);

        Assert.Multiple(() =>
        {
            Assert.That(created, Is.EqualTo(Path.Combine(_root, "audio", "estado")));
            Assert.That(Directory.Exists(created), Is.True);
            Assert.That(SafePathPolicy.NormalizeAndCreatePrivateDirectory(created), Is.EqualTo(created));
        });
    }

    [TestCase("")]
    [TestCase("   ")]
    public void A_blank_path_is_refused(string path) =>
        Assert.That(() => SafePathPolicy.NormalizeAndCreatePrivateDirectory(path), Throws.ArgumentException);
}
