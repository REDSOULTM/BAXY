using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class PresenceAutostartTests
{
    [Test]
    public void CommandQuotesTheRunningExecutableAndTheWindowsStartFlag()
    {
        string exe = Path.Combine(
            TestContext.CurrentContext.WorkDirectory,
            "Baxy.exe");
        File.WriteAllBytes(exe, [0x4D, 0x5A]);
        string command = WindowsAutostartRegistration.BuildCommand(exe);

        Assert.That(command, Does.StartWith("\"" + Path.GetFullPath(exe) + "\" "));
        Assert.That(command, Does.EndWith(PresenceLimits.FromWindowsStartArgument));
        Assert.That(File.Exists(exe), Is.True);
    }

    [Test]
    public void EnsureRegisteredWritesTheLiveCommandOnce()
    {
        string exe = Path.Combine(
            TestContext.CurrentContext.WorkDirectory,
            "autostart-baxy.exe");
        File.WriteAllBytes(exe, [0x4D, 0x5A]);
        var run = new MemoryRunKey();
        var registration = new WindowsAutostartRegistration(run, () => exe);

        string first = registration.EnsureRegistered();
        string second = registration.EnsureRegistered();

        Assert.Multiple(() =>
        {
            Assert.That(first, Is.EqualTo(second));
            Assert.That(run.Writes, Is.EqualTo(1));
            Assert.That(run.Read(PresenceLimits.AutostartValueName), Is.EqualTo(first));
            Assert.That(registration.IsRegistered(), Is.True);
            Assert.That(
                WindowsAutostartRegistration.IsStartHidden(
                    [PresenceLimits.FromWindowsStartArgument]),
                Is.True);
            Assert.That(
                WindowsAutostartRegistration.IsStartHidden(["--tray"]),
                Is.True);
            Assert.That(WindowsAutostartRegistration.IsStartHidden([]), Is.False);
        });
    }

    [Test]
    public void StaleDebugTrayCommandIsReplacedByTheRunningExecutable()
    {
        string exe = Path.Combine(
            TestContext.CurrentContext.WorkDirectory,
            "release-baxy.exe");
        File.WriteAllBytes(exe, [0x4D, 0x5A]);
        var run = new MemoryRunKey();
        run.Write(
            PresenceLimits.AutostartValueName,
            "\"C:\\old\\Debug\\Baxy.exe\" --tray");
        var registration = new WindowsAutostartRegistration(run, () => exe);

        string command = registration.EnsureRegistered();

        Assert.That(command, Does.Contain(Path.GetFullPath(exe)));
        Assert.That(command, Does.Not.Contain("Debug"));
        Assert.That(run.Read(PresenceLimits.AutostartValueName), Is.EqualTo(command));
    }

    private sealed class MemoryRunKey : IWindowsRunKey
    {
        private readonly Dictionary<string, string> _values = new(StringComparer.Ordinal);
        internal int Writes { get; private set; }

        public string? Read(string name) =>
            _values.TryGetValue(name, out string? value) ? value : null;

        public void Write(string name, string value)
        {
            _values[name] = value;
            Writes++;
        }

        public void Delete(string name) => _values.Remove(name);
    }
}
