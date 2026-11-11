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

    [Test]
    public void TheCopyTheGitHubInstallerLeavesMayOwnTheSignInStart()
    {
        var key = new FakeRunKey();
        string executable = Path.Combine(InstallRoot + "-App", "app", "Baxy.exe");
        WindowsAutostartRegistration registration = new(
            key,
            executablePath: () => executable,
            installationRoot: InstallRoot,
            defaultDataRoot: Path.Combine(Path.GetTempPath(), "baxy-autostart-fake", "BAXY", "1"),
            configuredDataRoot: static () => null);

        Assert.That(registration.MayRegister(executable, []), Is.True);
    }

    // COX-1: another BAXY installed beside this one (its own setup) had the Run value «BAXY»; this one took it at its
    // start and its uninstall left the other with no start with Windows. What it replaces is kept first.
    [Test]
    public void TheStartOfAnotherBaxyIsKeptBeforeThisOneTakesIt()
    {
        string other = OtherBaxy();
        var key = new FakeRunKey { CanKeep = true };
        key.Values[PresenceLimits.AutostartValueName] = Quoted(other);

        Registration(key).EnsureRegistered([]);

        Assert.That(key.Kept, Is.EqualTo(Quoted(other)));
        Assert.That(key.Values[PresenceLimits.AutostartValueName], Does.Contain(InstallRoot));
    }

    [Test]
    public void WithNowhereToKeepItTheStartOfAnotherBaxyStays()
    {
        string other = OtherBaxy();
        var key = new FakeRunKey { CanKeep = false };
        key.Values[PresenceLimits.AutostartValueName] = Quoted(other);
        WindowsAutostartRegistration registration = Registration(key);

        registration.EnsureRegistered([]);

        Assert.That(key.Values[PresenceLimits.AutostartValueName], Is.EqualTo(Quoted(other)));
        Assert.That(registration.IsRegisteredForCurrent(), Is.False, "the switch says this one does not start with Windows");
    }

    [Test]
    public void TheOwnersSwitchTakesItAndKeepsWhatItReplaced()
    {
        string other = OtherBaxy();
        var key = new FakeRunKey { CanKeep = false };
        key.Values[PresenceLimits.AutostartValueName] = Quoted(other);

        Assert.That(Registration(key).SetForCurrent(true, []), Is.True);

        Assert.That(key.Values[PresenceLimits.AutostartValueName], Does.Contain(InstallRoot));
        Assert.That(key.KeepAsked, Is.EqualTo(1));
    }

    [Test]
    public void AStartWhoseExeIsGoneIsReplacedWithNothingKept()
    {
        var key = new FakeRunKey { CanKeep = true };
        key.Values[PresenceLimits.AutostartValueName] = Quoted(Path.Combine(Path.GetTempPath(), "baxy-autostart-fake", "gone", "Baxy.exe"));

        Registration(key).EnsureRegistered([]);

        Assert.That(key.Values[PresenceLimits.AutostartValueName], Does.Contain(InstallRoot));
        Assert.That(key.Kept, Is.Null);
    }

    private static string Quoted(string exe) => "\"" + exe + "\" " + PresenceLimits.FromWindowsStartArgument;

    private static string OtherBaxy()
    {
        string other = Path.Combine(Path.GetTempPath(), "baxy-autostart-fake", "Other", "versions", "1.0", "Baxy.exe");
        Directory.CreateDirectory(Path.GetDirectoryName(other)!);
        File.WriteAllText(other, "the other app");
        return other;
    }

    private sealed class FakeRunKey : IWindowsRunKey
    {
        internal Dictionary<string, string> Values { get; } = new(StringComparer.OrdinalIgnoreCase);

        internal bool CanKeep { get; init; }

        internal string? Kept { get; private set; }

        internal int KeepAsked { get; private set; }

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

        public bool KeepReplaced(string executable, string command)
        {
            KeepAsked++;
            if (CanKeep)
            {
                Kept = command;
            }

            return CanKeep;
        }
    }
}
