using NUnit.Framework;

namespace Baxy.Setup.Tests;

[TestFixture]
public sealed class OperationGatesTests
{
    [Test]
    public void NameOnlyGatesPreserveStableCaseInsensitiveSeparatedNames()
    {
        using GateTestTree first = GateTestTree.Create(createRoot: false);
        using GateTestTree second = GateTestTree.Create(createRoot: false);

        string product = ProductOperationGate.BuildMutexName(first.Root);
        string productSame = ProductOperationGate.BuildMutexName(first.Root.ToUpperInvariant());
        string productOther = ProductOperationGate.BuildMutexName(second.Root);
        string installation = InstallationOperationGate.BuildMutexName(first.Root);
        string installationSame = InstallationOperationGate.BuildMutexName(
            first.Root.ToUpperInvariant());
        string installationOther = InstallationOperationGate.BuildMutexName(second.Root);

        Assert.Multiple(() =>
        {
            Assert.That(product, Does.Match(@"^Global\\BAXY\.Product\.[0-9A-F]{24}$"));
            Assert.That(productSame, Is.EqualTo(product));
            Assert.That(productOther, Is.Not.EqualTo(product));
            Assert.That(ProductOperationLease.BuildMutexName(first.Root), Is.EqualTo(product));
            Assert.That(installation, Does.Match(@"^Global\\BAXY\.Setup\.[0-9A-F]{24}$"));
            Assert.That(installationSame, Is.EqualTo(installation));
            Assert.That(installationOther, Is.Not.EqualTo(installation));
            Assert.That(installation, Is.Not.EqualTo(product));
            Assert.That(
                NamedOperationGate.CrossSessionCurrentUserOptions.CurrentUserOnly,
                Is.True);
            Assert.That(
                NamedOperationGate.CrossSessionCurrentUserOptions.CurrentSessionOnly,
                Is.False);
        });
    }

    [Test]
    public void NameOnlyGatesDoNotCreateOrOpenInstallationFilesystemState()
    {
        using GateTestTree tree = GateTestTree.Create(createRoot: false);
        string[] outerBefore = Directory.GetFileSystemEntries(tree.Outer);

        using (ProductOperationGate product = ProductOperationGate.Acquire(tree.Root))
        using (InstallationOperationGate installation = InstallationOperationGate.Acquire(tree.Root))
        {
            Assert.Multiple(() =>
            {
                Assert.That(product.WasAbandoned, Is.False);
                Assert.That(installation.WasAbandoned, Is.False);
                Assert.That(Directory.Exists(tree.Root), Is.False);
                Assert.That(File.Exists(tree.Root), Is.False);
                Assert.That(Directory.GetFileSystemEntries(tree.Outer), Is.EqualTo(outerBefore));
            });
        }

        Assert.That(Directory.GetFileSystemEntries(tree.Outer), Is.EqualTo(outerBefore));
    }

    [Test]
    public void ProductGateRejectsAnotherThreadUntilRelease()
    {
        using GateTestTree tree = GateTestTree.Create(createRoot: false);
        using ProductOperationGate first = ProductOperationGate.Acquire(tree.Root);

        bool rejected = Task.Run(() => IsProductGateRejected(tree.Root))
            .GetAwaiter()
            .GetResult();

        Assert.That(rejected, Is.True);
        first.Dispose();
        Assert.That(
            Task.Run(() => IsProductGateRejected(tree.Root)).GetAwaiter().GetResult(),
            Is.False);
    }

    [Test]
    public void InstallationGateRejectsAnotherThreadUntilRelease()
    {
        using GateTestTree tree = GateTestTree.Create(createRoot: false);
        using InstallationOperationGate first = InstallationOperationGate.Acquire(tree.Root);

        bool rejected = Task.Run(() => IsInstallationGateRejected(tree.Root))
            .GetAwaiter()
            .GetResult();

        Assert.That(rejected, Is.True);
        first.Dispose();
        Assert.That(
            Task.Run(() => IsInstallationGateRejected(tree.Root)).GetAwaiter().GetResult(),
            Is.False);
    }

    [Test]
    public void ProductGateSurfacesAbandonedOwnershipWhileHoldingExclusion()
    {
        using GateTestTree tree = GateTestTree.Create(createRoot: false);
        using Mutex abandoned = AbandonMutex(ProductOperationGate.BuildMutexName(tree.Root));

        using ProductOperationGate recovered = ProductOperationGate.Acquire(tree.Root);

        Assert.That(recovered.WasAbandoned, Is.True);
        Assert.That(
            Task.Run(() => IsProductGateRejected(tree.Root)).GetAwaiter().GetResult(),
            Is.True);
    }

    [Test]
    public void InstallationGateSurfacesAbandonedOwnershipWhileHoldingExclusion()
    {
        using GateTestTree tree = GateTestTree.Create(createRoot: false);
        using Mutex abandoned = AbandonMutex(
            InstallationOperationGate.BuildMutexName(tree.Root));

        using InstallationOperationGate recovered = InstallationOperationGate.Acquire(tree.Root);

        Assert.That(recovered.WasAbandoned, Is.True);
        Assert.That(
            Task.Run(() => IsInstallationGateRejected(tree.Root)).GetAwaiter().GetResult(),
            Is.True);
    }

    [Test]
    public void HoldingOnlyBothNameGatesDoesNotPreventAtomicRootRename()
    {
        using GateTestTree tree = GateTestTree.Create(createRoot: true);
        string sentinel = Path.Combine(tree.Root, "sentinel.txt");
        File.WriteAllText(sentinel, "owned");
        string tombstone = tree.Root + ".tombstone";

        using ProductOperationGate product = ProductOperationGate.Acquire(tree.Root);
        using InstallationOperationGate installation = InstallationOperationGate.Acquire(tree.Root);
        Directory.Move(tree.Root, tombstone);

        Assert.Multiple(() =>
        {
            Assert.That(Directory.Exists(tree.Root), Is.False);
            Assert.That(File.ReadAllText(Path.Combine(tombstone, "sentinel.txt")), Is.EqualTo("owned"));
            Assert.That(
                Task.Run(() => IsProductGateRejected(tree.Root)).GetAwaiter().GetResult(),
                Is.True);
            Assert.That(
                Task.Run(() => IsInstallationGateRejected(tree.Root)).GetAwaiter().GetResult(),
                Is.True);
        });

        Directory.Move(tombstone, tree.Root);
        Assert.That(File.ReadAllText(sentinel), Is.EqualTo("owned"));
    }

    [Test]
    public void ProductLeaseLosesAtNameGateBeforeCreatingMissingRoot()
    {
        using GateTestTree tree = GateTestTree.Create(createRoot: false);
        using ProductOperationGate blocker = ProductOperationGate.Acquire(tree.Root);

        bool rejected = Task.Run(() =>
        {
            try
            {
                using ProductOperationLease _ = ProductOperationLease.Acquire(tree.Root);
                return false;
            }
            catch (InstallationSafetyException)
            {
                return true;
            }
        }).GetAwaiter().GetResult();

        Assert.Multiple(() =>
        {
            Assert.That(rejected, Is.True);
            Assert.That(Directory.Exists(tree.Root), Is.False);
        });
    }

    [Test]
    public void InstallationEngineLosesAtNameGateBeforeCreatingMissingRoot()
    {
        using GateTestTree tree = GateTestTree.Create(createRoot: false);
        using InstallationOperationGate blocker = InstallationOperationGate.Acquire(tree.Root);
        InstallationEngine engine = new(tree.Root);

        bool rejected = Task.Run(() =>
        {
            try
            {
                _ = engine.GetCurrentVersion();
                return false;
            }
            catch (InstallationSafetyException)
            {
                return true;
            }
        }).GetAwaiter().GetResult();

        Assert.Multiple(() =>
        {
            Assert.That(rejected, Is.True);
            Assert.That(Directory.Exists(tree.Root), Is.False);
        });
    }

    [Test]
    public void NameOnlyGateDisposeIsIdempotent()
    {
        using GateTestTree tree = GateTestTree.Create(createRoot: false);
        ProductOperationGate product = ProductOperationGate.Acquire(tree.Root);
        InstallationOperationGate installation = InstallationOperationGate.Acquire(tree.Root);

        product.Dispose();
        installation.Dispose();

        Assert.Multiple(() =>
        {
            Assert.That(product.Dispose, Throws.Nothing);
            Assert.That(installation.Dispose, Throws.Nothing);
        });
    }

    private static bool IsProductGateRejected(string root)
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

    private static bool IsInstallationGateRejected(string root)
    {
        try
        {
            using InstallationOperationGate _ = InstallationOperationGate.Acquire(root);
            return false;
        }
        catch (InstallationSafetyException)
        {
            return true;
        }
    }

    private static Mutex AbandonMutex(string name)
    {
        using ManualResetEventSlim acquired = new(initialState: false);
        Mutex? abandoned = null;
        Thread thread = new(() =>
        {
            abandoned = new Mutex(
                initiallyOwned: false,
                name,
                NamedOperationGate.CrossSessionCurrentUserOptions);
            _ = abandoned.WaitOne();
            acquired.Set();
        });
        thread.IsBackground = true;
        thread.Start();
        Assert.That(acquired.Wait(TimeSpan.FromSeconds(10)), Is.True);
        Assert.That(thread.Join(TimeSpan.FromSeconds(10)), Is.True);
        return abandoned ?? throw new AssertionException(
            "The abandoned mutex handle was not captured.");
    }

    private sealed class GateTestTree : IDisposable
    {
        private GateTestTree(string outer, string root)
        {
            Outer = outer;
            Root = root;
        }

        internal string Outer { get; }

        internal string Root { get; }

        internal static GateTestTree Create(bool createRoot)
        {
            string outer = Path.Combine(
                Path.GetTempPath(),
                "baxy-operation-gates",
                Guid.NewGuid().ToString("N"));
            string root = Path.Combine(outer, "BAXY");
            Directory.CreateDirectory(outer);
            if (createRoot)
            {
                Directory.CreateDirectory(root);
            }

            return new GateTestTree(outer, root);
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
