using System.Diagnostics;
using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// V132 (1.3.2, PKG6's finding): uninstalling through «Installed apps» or its QuietUninstallString runs a copy of the
/// installer from TEMP (Program.UninstallFromACopy), and that 81 MB copy stayed there for ever: Windows does not let a
/// running exe delete itself. The copy leaves its removal to a process that outlives it, and only for its own folder.
/// </summary>
[TestFixture]
internal sealed class TempCopyTests
{
    private string temp = string.Empty;

    [SetUp]
    public void SetUp()
    {
        // A TEMP whose path has what cmd.exe would otherwise read as syntax (spaces, parentheses, &, ^, %, ! and a %i, the
        // loop's variable) and letters beyond ASCII (held-out, V132).
        temp = Path.Combine(Path.GetTempPath(), "baxy-installer-tests", Path.GetRandomFileName(), "Juan (x) & Ana ^ 100% !hola! %i Pérez Ñandú");
        Directory.CreateDirectory(temp);
    }

    [TearDown]
    public void TearDown() => Directory.Delete(Path.GetDirectoryName(temp)!, recursive: true);

    [Test]
    public void The_copy_in_its_own_folder_of_TEMP_is_removed()
    {
        string copy = Copy("BAXY-abc123");

        Assert.That(TempCopy.FolderToRemove(copy, temp), Is.EqualTo(Path.GetDirectoryName(copy)));
        Assert.That(TempCopy.FolderToRemove(copy, temp + Path.DirectorySeparatorChar), Is.EqualTo(Path.GetDirectoryName(copy)));
    }

    [TestCase("outside")]
    [TestCase("other name")]
    [TestCase("another file")]
    [TestCase("a subfolder")]
    [TestCase("deeper")]
    [TestCase("not ours")]
    [TestCase("a name cmd would read")]
    public void Nothing_but_the_copys_own_folder_is_ever_removed(string how)
    {
        string copy = how switch
        {
            "outside" => Copy("BAXY-abc", Path.Combine(Path.GetDirectoryName(temp)!, "Descargas")),
            "deeper" => Copy("BAXY-abc", Path.Combine(temp, "x")),
            "not ours" => Copy("Programas"),
            "a name cmd would read" => Copy("BAXY-a & b"),
            _ => Copy("BAXY-abc"),
        };
        string folder = Path.GetDirectoryName(copy)!;
        switch (how)
        {
            case "other name":
                File.Move(copy, copy = Path.Combine(folder, "BAXY-Instalador.exe"));
                break;
            case "another file":
                File.WriteAllText(Path.Combine(folder, "notas.txt"), "mías");
                break;
            case "a subfolder":
                Directory.CreateDirectory(Path.Combine(folder, "fotos"));
                break;
        }

        Assert.That(TempCopy.FolderToRemove(copy, temp), Is.Null);
    }

    // The real cmd.exe, against a file still held open (as the copy's own exe is while it runs): the folder goes once it
    // is let go, and with it nothing else.
    [Test]
    public async Task The_remover_waits_for_the_copy_to_end_and_takes_only_its_folder()
    {
        string copy = Copy("BAXY-abc123");
        string folder = Path.GetDirectoryName(copy)!;
        string neighbour = Path.Combine(temp, "BAXY-Instalador.log");
        await File.WriteAllTextAsync(neighbour, "log");
        FileStream held = new(copy, FileMode.Open, FileAccess.Read, FileShare.Read);
        using Process? remover = Process.Start(TempCopy.Remover(folder, temp));
        try
        {
            Assert.That(remover, Is.Not.Null);
            await Task.Delay(1500);
            Assert.That(File.Exists(copy), Is.True, "not while it runs");
        }
        finally
        {
            await held.DisposeAsync();
        }

        Assert.That(remover!.WaitForExit(TimeSpan.FromSeconds(20)), Is.True);
        Assert.That(Directory.Exists(folder), Is.False);
        Assert.That(File.Exists(neighbour), Is.True);
        Assert.That(Directory.GetFileSystemEntries(temp), Is.EqualTo(new[] { neighbour }));
    }

    // Something written into the folder meanwhile stays, and so does the folder: the remover deletes one file by name and
    // removes the folder only when it is empty.
    [Test]
    public void The_remover_never_deletes_what_it_did_not_bring()
    {
        string copy = Copy("BAXY-abc123");
        string folder = Path.GetDirectoryName(copy)!;
        string added = Path.Combine(folder, "notas.txt");
        File.WriteAllText(added, "mías");

        using Process? remover = Process.Start(TempCopy.Remover(folder, temp, tries: 2));

        Assert.That(remover!.WaitForExit(TimeSpan.FromSeconds(20)), Is.True);
        Assert.That(File.Exists(copy), Is.False);
        Assert.That(File.ReadAllText(added), Is.EqualTo("mías"));
    }

    // Review (V132): something that took the copy's name as a folder meanwhile is not emptied by «del».
    [Test]
    public void The_remover_never_empties_a_folder_with_the_copys_name()
    {
        string copy = Copy("BAXY-abc123");
        File.Delete(copy);
        Directory.CreateDirectory(copy);
        string inside = Path.Combine(copy, "notas.txt");
        File.WriteAllText(inside, "mías");

        using Process? remover = Process.Start(TempCopy.Remover(Path.GetDirectoryName(copy)!, temp, tries: 2));

        Assert.That(remover!.WaitForExit(TimeSpan.FromSeconds(20)), Is.True);
        Assert.That(File.ReadAllText(inside), Is.EqualTo("mías"));
    }

    [Test]
    public void A_folder_whose_name_cmd_would_read_is_never_handed_to_it() =>
        Assert.That(() => TempCopy.Remover(Path.Combine(temp, "BAXY-a %i & b"), temp), Throws.ArgumentException);

    private string Copy(string folderName, string? under = null)
    {
        string folder = Path.Combine(under ?? temp, folderName);
        Directory.CreateDirectory(folder);
        string copy = Path.Combine(folder, TempCopy.CopyName);
        File.WriteAllText(copy, "copia del instalador");
        return copy;
    }
}
