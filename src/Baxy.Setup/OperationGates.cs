using System.Security.Cryptography;
using System.Text;

namespace Baxy.Setup;

internal sealed class ProductOperationGate : IDisposable
{
    // The product lifecycle must be serialized across every interactive Windows
    // session for this user. A Local\\ mutex only protects the current session.
    private const string NamePrefix = "Global\\BAXY.Product.";
    private readonly NamedOperationGate _gate;

    private ProductOperationGate(string installationRoot, NamedOperationGate gate)
    {
        InstallationRoot = installationRoot;
        _gate = gate;
    }

    internal string InstallationRoot { get; }

    internal bool WasAbandoned => _gate.WasAbandoned;

    internal bool IsActive => _gate.IsActive;

    internal static ProductOperationGate Acquire(string installationRoot)
    {
        string root = PathSafety.ValidateInstallationRoot(installationRoot);
        return new ProductOperationGate(
            root,
            NamedOperationGate.Acquire(BuildMutexName(root), "product lifecycle"));
    }

    internal static string BuildMutexName(string installationRoot) =>
        NamedOperationGate.BuildMutexName(
            PathSafety.ValidateInstallationRoot(installationRoot),
            NamePrefix);

    public void Dispose() => _gate.Dispose();
}

internal sealed class InstallationOperationGate : IDisposable
{
    // Installation, launch and uninstall share this gate, so it must also span
    // fast-user-switching and Remote Desktop sessions.
    private const string NamePrefix = "Global\\BAXY.Setup.";
    private readonly NamedOperationGate _gate;

    private InstallationOperationGate(string installationRoot, NamedOperationGate gate)
    {
        InstallationRoot = installationRoot;
        _gate = gate;
    }

    internal string InstallationRoot { get; }

    internal bool WasAbandoned => _gate.WasAbandoned;

    internal bool IsActive => _gate.IsActive;

    internal static InstallationOperationGate Acquire(string installationRoot)
    {
        string root = PathSafety.ValidateInstallationRoot(installationRoot);
        return new InstallationOperationGate(
            root,
            NamedOperationGate.Acquire(BuildMutexName(root), "installation engine"));
    }

    internal static string BuildMutexName(string installationRoot) =>
        NamedOperationGate.BuildMutexName(
            PathSafety.ValidateInstallationRoot(installationRoot),
            NamePrefix);

    public void Dispose() => _gate.Dispose();
}

internal sealed class NamedOperationGate : IDisposable
{
    private readonly Mutex _mutex;
    private bool _disposed;

    private NamedOperationGate(Mutex mutex, bool wasAbandoned)
    {
        _mutex = mutex;
        WasAbandoned = wasAbandoned;
    }

    internal bool WasAbandoned { get; }

    internal bool IsActive => !_disposed;

    internal static NamedOperationGate Acquire(string mutexName, string operation)
    {
        Mutex mutex = new(
            initiallyOwned: false,
            mutexName,
            CrossSessionCurrentUserOptions);
        bool acquired = false;
        bool abandoned = false;
        try
        {
            try
            {
                acquired = mutex.WaitOne(TimeSpan.Zero);
            }
            catch (AbandonedMutexException)
            {
                acquired = true;
                abandoned = true;
            }

            if (!acquired)
            {
                throw new InstallationSafetyException(
                    $"Another BAXY {operation} operation is already running.");
            }

            return new NamedOperationGate(mutex, abandoned);
        }
        catch
        {
            if (acquired)
            {
                mutex.ReleaseMutex();
            }

            mutex.Dispose();
            throw;
        }
    }

    internal static string BuildMutexName(string installationRoot, string prefix)
    {
        string digest = Convert.ToHexString(
            SHA256.HashData(Encoding.UTF8.GetBytes(installationRoot.ToUpperInvariant())));
        return prefix + digest[..24];
    }

    internal static NamedWaitHandleOptions CrossSessionCurrentUserOptions => new()
    {
        CurrentUserOnly = true,
        CurrentSessionOnly = false,
    };

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _mutex.ReleaseMutex();
        _mutex.Dispose();
        _disposed = true;
    }
}
