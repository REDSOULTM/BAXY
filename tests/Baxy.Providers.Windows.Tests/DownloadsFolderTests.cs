using Baxy.Providers.Windows.Filesystem;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// FT/proveedores goal (review of receipts): Downloads is the folder Windows knows (FOLDERID_Downloads), the same one
/// the Shell opens as shell:Downloads, not the profile's «Downloads» assumed.
/// </summary>
[TestFixture]
public sealed class DownloadsFolderTests
{
    [Test]
    public void DownloadsIsTheFolderTheShellKnows()
    {
        Type? shellType = Type.GetTypeFromProgID("Shell.Application");
        Assert.That(shellType, Is.Not.Null);
        dynamic shell = Activator.CreateInstance(shellType!)!;
        string shellPath = (string)shell.Namespace("shell:Downloads").Self.Path;

        Assert.That(DownloadsFolder.Path(), Is.EqualTo(shellPath).IgnoreCase);
    }
}
