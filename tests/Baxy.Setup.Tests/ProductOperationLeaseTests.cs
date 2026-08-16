using System.Text;
using NUnit.Framework;

namespace Baxy.Setup.Tests;

[TestFixture]
public sealed class ProductOperationLeaseTests
{
    [Test]
    public void Acquire_CreatesAndReusesTheExactDurableLock()
    {
        using TemporaryRoot temporary = TemporaryRoot.Create(createRoot: false);

        ProductOperationLease.Acquire(temporary.Root).Dispose();

        string lockPath = Path.Combine(temporary.Root, "product.lock");
        Assert.That(File.ReadAllBytes(lockPath),
            Is.EqualTo(Encoding.ASCII.GetBytes("BAXY product lock v1\n")));
        PathSafety.AssertRegularFile(lockPath);

        DateTime lastWrite = File.GetLastWriteTimeUtc(lockPath);
        ProductOperationLease.Acquire(
            temporary.Root,
            requireExistingRootAndLock: true).Dispose();

        Assert.That(File.GetLastWriteTimeUtc(lockPath), Is.EqualTo(lastWrite));
    }

    [Test]
    public void Acquire_RejectsConcurrentAccessAndAllowsItAfterRelease()
    {
        using TemporaryRoot temporary = TemporaryRoot.Create();
        using ProductOperationLease first = ProductOperationLease.Acquire(temporary.Root);

        Assert.Throws<InstallationSafetyException>(
            () => ProductOperationLease.Acquire(temporary.Root).Dispose());

        first.Dispose();
        Assert.DoesNotThrow(
            () => ProductOperationLease.Acquire(temporary.Root).Dispose());
    }

    [Test]
    public void Acquire_RejectsMissingExistingStateWithoutCreatingAnything()
    {
        using TemporaryRoot missingRoot = TemporaryRoot.Create(createRoot: false);

        Assert.Throws<InstallationSafetyException>(
            () => ProductOperationLease.Acquire(
                missingRoot.Root,
                requireExistingRootAndLock: true));
        Assert.That(Directory.Exists(missingRoot.Root), Is.False);

        using TemporaryRoot missingLock = TemporaryRoot.Create();
        Assert.Throws<InstallationSafetyException>(
            () => ProductOperationLease.Acquire(
                missingLock.Root,
                requireExistingRootAndLock: true));
        Assert.That(File.Exists(Path.Combine(missingLock.Root, "product.lock")), Is.False);
    }

    [TestCase("")]
    [TestCase("foreign")]
    [TestCase("BAXY product lock v2\n")]
    public void Acquire_RejectsMalformedExistingLockBytesAndPreservesThem(string content)
    {
        using TemporaryRoot temporary = TemporaryRoot.Create();
        string lockPath = Path.Combine(temporary.Root, "product.lock");
        byte[] bytes = Encoding.ASCII.GetBytes(content);
        File.WriteAllBytes(lockPath, bytes);

        if (bytes.Length == 0)
        {
            ProductOperationLease.Acquire(temporary.Root).Dispose();
            Assert.That(File.ReadAllBytes(lockPath),
                Is.EqualTo(Encoding.ASCII.GetBytes("BAXY product lock v1\n")));
            return;
        }

        Assert.Throws<InstallationSafetyException>(
            () => ProductOperationLease.Acquire(temporary.Root).Dispose());
        Assert.That(File.ReadAllBytes(lockPath), Is.EqualTo(bytes));
    }

    [Test]
    public void Acquire_RejectsADirectoryAtTheLockPath()
    {
        using TemporaryRoot temporary = TemporaryRoot.Create();
        string lockPath = Path.Combine(temporary.Root, "product.lock");
        Directory.CreateDirectory(lockPath);

        Assert.Throws<InstallationSafetyException>(
            () => ProductOperationLease.Acquire(temporary.Root).Dispose());
        Assert.That(Directory.Exists(lockPath), Is.True);
    }

    [Test]
    public void BuildMutexName_IsStableCaseInsensitiveAndSeparatedByRoot()
    {
        using TemporaryRoot first = TemporaryRoot.Create();
        using TemporaryRoot second = TemporaryRoot.Create();

        string firstName = ProductOperationLease.BuildMutexName(first.Root);
        string sameName = ProductOperationLease.BuildMutexName(first.Root.ToUpperInvariant());
        string secondName = ProductOperationLease.BuildMutexName(second.Root);

        Assert.Multiple(() =>
        {
            Assert.That(firstName, Does.Match(@"^Global\\BAXY\.Product\.[0-9A-F]{24}$"));
            Assert.That(sameName, Is.EqualTo(firstName));
            Assert.That(secondName, Is.Not.EqualTo(firstName));
        });
    }

    [Test]
    public void Dispose_IsIdempotent()
    {
        using TemporaryRoot temporary = TemporaryRoot.Create();
        ProductOperationLease lease = ProductOperationLease.Acquire(temporary.Root);

        lease.Dispose();
        Assert.DoesNotThrow(lease.Dispose);
    }

    [Test]
    public void AcquireWithHeldGateComposesPersistentLockWithoutTakingGateOwnership()
    {
        using TemporaryRoot temporary = TemporaryRoot.Create(createRoot: false);
        using ProductOperationGate gate = ProductOperationGate.Acquire(temporary.Root);
        ProductOperationLease lease = ProductOperationLease.AcquireWithHeldGate(
            temporary.Root.ToUpperInvariant(),
            gate);

        lease.Dispose();

        Assert.Multiple(() =>
        {
            Assert.That(gate.IsActive, Is.True);
            Assert.That(File.Exists(Path.Combine(temporary.Root, "product.lock")), Is.True);
            Assert.That(
                Task.Run(() => IsGateRejected(temporary.Root)).GetAwaiter().GetResult(),
                Is.True);
        });
    }

    [Test]
    public void AcquireWithHeldGateRejectsDisposedOrForeignGateWithoutFilesystemMutation()
    {
        using TemporaryRoot first = TemporaryRoot.Create(createRoot: false);
        using TemporaryRoot second = TemporaryRoot.Create(createRoot: false);
        ProductOperationGate disposed = ProductOperationGate.Acquire(first.Root);
        disposed.Dispose();

        Assert.Multiple(() =>
        {
            Assert.That(
                () => ProductOperationLease.AcquireWithHeldGate(first.Root, disposed),
                Throws.TypeOf<InstallationSafetyException>());
            using ProductOperationGate foreign = ProductOperationGate.Acquire(second.Root);
            Assert.That(
                () => ProductOperationLease.AcquireWithHeldGate(first.Root, foreign),
                Throws.TypeOf<InstallationSafetyException>());
        });
        Assert.That(Directory.Exists(first.Root), Is.False);
    }

    private static bool IsGateRejected(string root)
    {
        try
        {
            using ProductOperationGate _ = ProductOperationGate.Acquire(root);
            return false;
        }
        catch (InstallationSafetyException)
        {
            return true;
        }
    }

    private sealed class TemporaryRoot : IDisposable
    {
        private TemporaryRoot(string outer, string root)
        {
            Outer = outer;
            Root = root;
        }

        internal string Outer { get; }

        internal string Root { get; }

        internal static TemporaryRoot Create(bool createRoot = true)
        {
            string outer = Path.Combine(
                Path.GetTempPath(),
                $"baxy-product-lease-{Guid.NewGuid():N}");
            string root = Path.Combine(outer, "BAXY");
            Directory.CreateDirectory(outer);
            if (createRoot)
            {
                Directory.CreateDirectory(root);
            }

            return new TemporaryRoot(outer, root);
        }

        public void Dispose()
        {
            if (Directory.Exists(Outer))
            {
                Directory.Delete(Outer, recursive: true);
            }
        }
    }
}
