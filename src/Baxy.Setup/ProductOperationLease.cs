using System.Text;

namespace Baxy.Setup;

internal sealed class ProductOperationLease : IDisposable
{
    private const string LockFileName = "product.lock";
    private static readonly byte[] LockFileBytes = Encoding.ASCII.GetBytes("BAXY product lock v1\n");

    private readonly ProductOperationGate? _ownedGate;
    private readonly FileStream _lockStream;
    private bool _disposed;

    private ProductOperationLease(
        ProductOperationGate? ownedGate,
        FileStream lockStream)
    {
        _ownedGate = ownedGate;
        _lockStream = lockStream;
    }

    internal static ProductOperationLease Acquire(
        string installationRoot,
        bool requireExistingRootAndLock = false)
    {
        string root = PathSafety.ValidateInstallationRoot(installationRoot);
        ProductOperationGate gate = ProductOperationGate.Acquire(root);
        try
        {
            return AcquireCore(
                root,
                requireExistingRootAndLock,
                ownedGate: gate);
        }
        catch
        {
            gate.Dispose();
            throw;
        }
    }

    internal static ProductOperationLease AcquireWithHeldGate(
        string installationRoot,
        ProductOperationGate heldGate,
        bool requireExistingRootAndLock = false)
    {
        string root = PathSafety.ValidateInstallationRoot(installationRoot);
        ArgumentNullException.ThrowIfNull(heldGate);
        if (!string.Equals(
                heldGate.InstallationRoot,
                root,
                StringComparison.OrdinalIgnoreCase))
        {
            throw new InstallationSafetyException(
                "The held product operation gate belongs to another installation root.");
        }

        if (!heldGate.IsActive)
        {
            throw new InstallationSafetyException(
                "The held product operation gate is no longer active.");
        }

        return AcquireCore(root, requireExistingRootAndLock, ownedGate: null);
    }

    private static ProductOperationLease AcquireCore(
        string root,
        bool requireExistingRootAndLock,
        ProductOperationGate? ownedGate)
    {
        if (requireExistingRootAndLock)
        {
            AssertExistingDirectory(root);
        }
        else
        {
            PathSafety.EnsureOwnedDirectory(root, root);
        }

        string lockPath = Path.Combine(root, LockFileName);
        bool lockExists = File.Exists(lockPath) || Directory.Exists(lockPath);
        if (requireExistingRootAndLock && !lockExists)
        {
            throw new InstallationSafetyException("The persistent BAXY product lock file is missing.");
        }

        if (lockExists)
        {
            if (!File.Exists(lockPath))
            {
                throw new InstallationSafetyException(
                    "The persistent BAXY product lock path is not a file.");
            }

            PathSafety.AssertRegularFile(lockPath);
        }

        FileStream lockStream;
        try
        {
            lockStream = new FileStream(
                lockPath,
                requireExistingRootAndLock ? FileMode.Open : FileMode.OpenOrCreate,
                FileAccess.ReadWrite,
                FileShare.None);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            throw new InstallationSafetyException(
                "Another process holds or denies access to the BAXY product lock file.",
                exception);
        }

        try
        {
            VerifyOrInitializeLockFile(lockStream);
            return new ProductOperationLease(ownedGate, lockStream);
        }
        catch
        {
            lockStream.Dispose();
            throw;
        }
    }

    internal static string BuildMutexName(string installationRoot) =>
        ProductOperationGate.BuildMutexName(installationRoot);

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _lockStream.Dispose();
        _ownedGate?.Dispose();
        _disposed = true;
    }

    private static void AssertExistingDirectory(string path)
    {
        PathSafety.AssertExistingChainHasNoReparsePoint(path);
        if (!Directory.Exists(path))
        {
            throw new InstallationSafetyException("The existing BAXY installation root is missing.");
        }

        FileAttributes attributes = File.GetAttributes(path);
        if ((attributes & FileAttributes.Directory) == 0 ||
            (attributes & FileAttributes.ReparsePoint) != 0)
        {
            throw new InstallationSafetyException("The existing BAXY installation root is unsafe.");
        }
    }

    private static void VerifyOrInitializeLockFile(FileStream stream)
    {
        if (stream.Length == 0)
        {
            stream.Write(LockFileBytes);
            stream.Flush(flushToDisk: true);
            return;
        }

        if (stream.Length != LockFileBytes.Length)
        {
            throw new InstallationSafetyException("The persistent BAXY product lock file is malformed.");
        }

        byte[] actual = new byte[LockFileBytes.Length];
        stream.Position = 0;
        stream.ReadExactly(actual);
        if (!actual.AsSpan().SequenceEqual(LockFileBytes))
        {
            throw new InstallationSafetyException("The persistent BAXY product lock file is malformed.");
        }
    }
}
