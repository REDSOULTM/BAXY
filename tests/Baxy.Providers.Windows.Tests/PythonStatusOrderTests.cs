using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Revisión nb-q-apps2: the registered Pythons are listed newest first by their version's numbers (3.12 before 3.9, as
/// text it was the other way round), and pip show runs from a neutral folder, never BAXY's own working directory (a
/// «pip» there would be what «-m pip» runs). Nothing is run here.
/// </summary>
[TestFixture]
public sealed class PythonStatusOrderTests
{
    [Test]
    public void VersionsAreOrderedByTheirNumbersNewestFirst()
    {
        var versions = new List<string> { "3.9.13", "3.12.4", "3.10", "3.12.10", "2.7", "3.13t" };

        versions.Sort((left, right) => WindowsDeviceControlAdapter.ComparePythonVersions(right, left));

        Assert.That(versions, Is.EqualTo(new[] { "3.13t", "3.12.10", "3.12.4", "3.10", "3.9.13", "2.7" }));
    }

    [Test]
    public void PipShowRunsFromTheSystemFolder()
    {
        string script = WindowsDeviceControlAdapter.PipShowScript;
        int location = script.IndexOf("Set-Location -LiteralPath ([Environment]::SystemDirectory)", StringComparison.Ordinal);

        Assert.That(location, Is.GreaterThanOrEqualTo(0), "pip show ran in BAXY's working directory");
        Assert.That(location, Is.LessThan(script.IndexOf("-m pip show", StringComparison.Ordinal)));
    }
}
