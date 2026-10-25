using System.IO;
using System.Security;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// WindowsAutostartRegistration.EnsureRegistered runs inside OnStartup: a Run key that a policy blocks must not stop
/// the start (the dispatcher would mark the failure handled and leave BAXY with no window holding the mutex).
/// </summary>
[TestFixture]
public sealed class AutostartRegistrationTests
{
    private static readonly string InstallRoot = Path.Combine(Path.GetTempPath(), "baxy-autostart-fake", "Programs", "BAXY");

    private static WindowsAutostartRegistration Registration(IWindowsRunKey key) =>
        new(key,
            executablePath: () => Path.Combine(InstallRoot, "Baxy.exe"),
            installationRoot: InstallRoot,
            defaultDataRoot: Path.Combine(Path.GetTempPath(), "baxy-autostart-fake", "BAXY", "1"),
            configuredDataRoot: static () => null);

    [Test]
    public void AWriteThePolicyBlocksLeavesTheStartGoingAndSaysWhy()
    {
        var key = new FakeRunKey { WriteFailure = new UnauthorizedAccessException("blocked by policy") };
        WindowsAutostartRegistration registration = Registration(key);

        Assert.DoesNotThrow(() => registration.EnsureRegistered([]));
        Assert.That(registration.LastFailure, Does.Contain("UnauthorizedAccessException"));
    }

    [Test]
    public void AReadThePolicyBlocksLeavesTheStartGoing()
    {
        var key = new FakeRunKey { ReadFailure = new SecurityException("no access") };
        WindowsAutostartRegistration registration = Registration(key);

        Assert.DoesNotThrow(() => registration.EnsureRegistered([]));
        Assert.That(registration.LastFailure, Does.Contain("SecurityException"));
    }

    [Test]
    public void AWriteThatWorksRegistersAndLeavesNoFailure()
    {
        var key = new FakeRunKey();
        WindowsAutostartRegistration registration = Registration(key);

        registration.EnsureRegistered([]);

        Assert.That(key.Values[PresenceLimits.AutostartValueName], Does.Contain(PresenceLimits.FromWindowsStartArgument));
        Assert.That(registration.LastFailure, Is.Null);
    }

    private sealed class FakeRunKey : IWindowsRunKey
    {
        internal Dictionary<string, string> Values { get; } = new(StringComparer.OrdinalIgnoreCase);

        internal Exception? ReadFailure { get; init; }

        internal Exception? WriteFailure { get; init; }

        public string? Read(string name) =>
            ReadFailure is { } failure ? throw failure : Values.GetValueOrDefault(name);

        public void Write(string name, string value)
        {
            if (WriteFailure is { } failure)
            {
                throw failure;
            }

            Values[name] = value;
        }

        public void Delete(string name) => Values.Remove(name);
    }
}
