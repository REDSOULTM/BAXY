namespace Baxy.Providers.Windows.SystemStatus;

public sealed record WindowsIdentitySnapshot(
    string Domain,
    string UserName,
    string QualifiedName);

public interface IWindowsIdentityProvider
{
    ValueTask<WindowsIdentitySnapshot?> ReadVerifiedAsync(
        CancellationToken cancellationToken);
}

public sealed class WindowsIdentityProvider : IWindowsIdentityProvider
{
    private readonly IWindowsIdentityProbe _probe;

    public WindowsIdentityProvider() : this(new EnvironmentWindowsIdentityProbe())
    {
    }

    internal WindowsIdentityProvider(IWindowsIdentityProbe probe) =>
        _probe = probe ?? throw new ArgumentNullException(nameof(probe));

    public ValueTask<WindowsIdentitySnapshot?> ReadVerifiedAsync(
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        WindowsIdentitySnapshot first = _probe.Read();
        cancellationToken.ThrowIfCancellationRequested();
        WindowsIdentitySnapshot second = _probe.Read();
        return ValueTask.FromResult<WindowsIdentitySnapshot?>(
            first == second && first.UserName.Length > 0 ? second : null);
    }
}

internal interface IWindowsIdentityProbe
{
    WindowsIdentitySnapshot Read();
}

internal sealed class EnvironmentWindowsIdentityProbe : IWindowsIdentityProbe
{
    public WindowsIdentitySnapshot Read()
    {
        string domain = Environment.UserDomainName.Trim();
        string user = Environment.UserName.Trim();
        string qualified = domain.Length == 0 ? user : $"{domain}\\{user}";
        return new WindowsIdentitySnapshot(domain, user, qualified);
    }
}
