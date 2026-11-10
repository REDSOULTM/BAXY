using System.Diagnostics;
using Microsoft.Win32;
using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// W1: the options a borrowed machine and a script need (A4/A5 on the AMD, REL2/REL4): --help, --dir, --no-voice and an
/// --uninstall --quiet that leaves the machine as it was. Every place here is a temporary folder or a registry key of
/// the test's own; nothing touches the BAXY of the machine that runs them.
/// </summary>
[TestFixture]
internal sealed class CommandLineTests
{
    private string directory = string.Empty;
    private string keys = string.Empty;
    private WindowsPlaces places = null!;

    [SetUp]
    public void SetUp()
    {
        directory = Path.Combine(Path.GetTempPath(), "baxy-installer-tests", Path.GetRandomFileName());
        Directory.CreateDirectory(directory);
        keys = @"Software\BAXY-Installer-Tests\" + Path.GetRandomFileName();
        places = new WindowsPlaces(
            Path.Combine(directory, "Start", "BAXY.lnk"),
            keys + @"\Uninstall\BAXY-App",
            keys + @"\Run",
            Path.Combine(directory, "data"),
            Path.Combine(directory, "other-baxy"));
        Directory.CreateDirectory(Path.GetDirectoryName(places.Link)!);
        // Windows always has the parent of the uninstall entries.
        Registry.CurrentUser.CreateSubKey(keys + @"\Uninstall").Dispose();
    }

    [TearDown]
    public void TearDown()
    {
        Registry.CurrentUser.DeleteSubKeyTree(keys, throwOnMissingSubKey: false);
        string parent = Path.GetDirectoryName(keys)!;
        bool empty;
        using (RegistryKey? tests = Registry.CurrentUser.OpenSubKey(parent))
        {
            empty = tests is { SubKeyCount: 0, ValueCount: 0 };
        }

        if (empty)
        {
            Registry.CurrentUser.DeleteSubKey(parent, throwOnMissingSubKey: false);
        }

        Directory.Delete(directory, recursive: true);
    }

    [TestCase("--help")]
    [TestCase("-h")]
    [TestCase("/?")]
    public void Help_is_asked_in_the_usual_ways(string argument)
    {
        Assert.That(CommandLine.Parse([argument]).Help, Is.True);
    }

    // INS-3, INS-4 and INS-5: what a script reads to know what --quiet did. With --quiet an update does not open BAXY
    // (a console over the network has no desktop to show it on), and each way of not ending well has its number.
    [TestCase("es", "Con --quiet no la abre", "tarjeta gráfica", "«Aplicaciones instaladas»")]
    [TestCase("en", "With --quiet it does not open it", "graphics card", "«Installed apps»")]
    public void The_help_says_what_quiet_does_and_what_each_exit_code_means(string language, string update, string card, string entry)
    {
        string[] help = CommandLine.HelpText(language, @"C:\Users\someone\AppData\Local\Programs\BAXY-App").Split('\n');

        Assert.Multiple(() =>
        {
            Assert.That(help, Has.Some.Contain(update));
            Assert.That(help, Has.Some.Contain($" {QuietInstall.NoGraphicsCard} ").And.Contain(card));
            Assert.That(help, Has.Some.Contain($" {QuietInstall.NotRegistered} ").And.Contain(entry));
            Assert.That(help, Has.Some.Contain($" {CommandLine.InvalidCommandLine} "));
        });
    }

    [TestCase("en", "Installs with no window")]
    [TestCase("es", "Instala sin ventana")]
    public void The_help_names_every_option_in_both_languages(string language, string said)
    {
        string help = CommandLine.HelpText(language, @"C:\Users\someone\AppData\Local\Programs\BAXY-App");

        Assert.Multiple(() =>
        {
            foreach (string option in new[] { "--quiet", "--dir", "--no-voice", "--uninstall", "--delete-data", "--update", "--help" })
            {
                Assert.That(help, Does.Contain(option));
            }

            Assert.That(help, Does.Contain(said));
            Assert.That(help, Does.Contain(@"C:\Users\someone\AppData\Local\Programs\BAXY-App"));
            Assert.That(help, Does.Contain(CommandLine.InvalidCommandLine.ToString(System.Globalization.CultureInfo.InvariantCulture)));
        });
    }

    [Test]
    public void The_options_are_read_with_their_values()
    {
        CommandLine command = CommandLine.Parse(["--uninstall", "--quiet", "--dir", @"D:\Pruebas\BAXY", "--no-voice", "--delete-data"]);

        Assert.That(command, Is.EqualTo(new CommandLine(
            Quiet: true, Uninstall: true, NoVoice: true, DeleteData: true, Directory: @"D:\Pruebas\BAXY")));
        Assert.That(CommandLine.Parse([@"--dir=D:\Pruebas\BAXY"]).Directory, Is.EqualTo(@"D:\Pruebas\BAXY"));
    }

    // BAXY updating itself (BaxyUpdateHandler) starts the installer over its own folder; an update is never an uninstall.
    [Test]
    public void The_update_BAXY_starts_names_its_folder_and_never_goes_with_an_uninstall()
    {
        Assert.Multiple(() =>
        {
            Assert.That(CommandLine.Parse(["--update", "--dir", @"D:\Pruebas\BAXY"]),
                Is.EqualTo(new CommandLine(Update: true, Directory: @"D:\Pruebas\BAXY")));
            Assert.That(CommandLine.Parse(["--update", "--uninstall"]).Error, Is.Not.Null);
        });
    }

    [TestCase("--silent")]
    [TestCase("--dir")]
    [TestCase("--delete-data")]
    public void An_option_it_does_not_know_or_without_its_value_is_refused(string argument)
    {
        Assert.That(CommandLine.Parse([argument]).Error, Is.Not.Null);
    }

    [Test]
    public void The_copy_that_uninstalls_is_told_the_folder_and_what_it_was_asked()
    {
        CommandLine copy = CommandLine.Parse(CommandLine.Parse(["--uninstall", "--quiet", "--delete-data"])
            .ForTheCopy(@"D:\Pruebas\BAXY", 4242).ToArray());

        Assert.That(copy, Is.EqualTo(new CommandLine(
            Quiet: true, Uninstall: true, UninstallRun: true, DeleteData: true, Directory: @"D:\Pruebas\BAXY", Original: 4242)));
    }

    [Test]
    public void A_chosen_folder_must_be_a_full_path_and_never_a_drive()
    {
        Assert.Throws<ArgumentException>(() => InstallPaths.Chosen(@"Pruebas\BAXY"));
        Assert.Throws<ArgumentException>(() => InstallPaths.Chosen(@"C:\"));
        Assert.That(InstallPaths.Chosen(Path.Combine(directory, "BAXY") + @"\").Root, Is.EqualTo(Path.Combine(directory, "BAXY")));
    }

    // The swap moves what was in the folder away and deletes it: a folder of the person's own is never taken for BAXY's.
    [Test]
    public void A_chosen_folder_with_other_files_is_refused_and_one_with_baxy_is_taken()
    {
        string theirs = Path.Combine(directory, "Documents");
        Directory.CreateDirectory(theirs);
        File.WriteAllText(Path.Combine(theirs, "notes.txt"), "mine");
        string empty = Path.Combine(directory, "empty");
        Directory.CreateDirectory(empty);
        InstallPaths installed = new(Path.Combine(directory, "BAXY"));
        Directory.CreateDirectory(Path.GetDirectoryName(installed.App)!);
        File.WriteAllText(installed.App, "the app");

        Assert.Throws<ArgumentException>(() => InstallPaths.Chosen(theirs));
        Assert.That(InstallPaths.Chosen(empty).Root, Is.EqualTo(empty));
        Assert.That(InstallPaths.Chosen(installed.Root), Is.EqualTo(installed));
    }

    [Test]
    public void An_uninstall_without_a_folder_takes_the_one_registered()
    {
        InstallPaths paths = Installed("D-BAXY");

        Assert.That(InstallPaths.ForUninstall(null, places), Is.EqualTo(paths));
        Registry.CurrentUser.DeleteSubKeyTree(keys);
        Assert.That(InstallPaths.ForUninstall(null, places), Is.EqualTo(InstallPaths.ForThisUser));
    }

    [Test]
    public void An_uninstall_never_takes_a_folder_that_is_not_baxys()
    {
        string theirs = Path.Combine(directory, "Documents");
        Directory.CreateDirectory(theirs);
        File.WriteAllText(Path.Combine(theirs, "notes.txt"), "mine");

        Assert.Throws<ArgumentException>(() => InstallPaths.ForUninstall(theirs, places));
        Assert.That(File.Exists(Path.Combine(theirs, "notes.txt")), Is.True);
    }

    [Test]
    public void A_quiet_uninstall_leaves_the_machine_as_before_the_install()
    {
        using (RegistryKey run = Registry.CurrentUser.CreateSubKey(places.RunKey))
        {
            run.SetValue("Someone-else", @"C:\Other\other.exe");
        }

        string[] withTheirRun = Everything();
        InstallPaths paths = Installed("BAXY-App");
        using (RegistryKey run = Registry.CurrentUser.CreateSubKey(places.RunKey))
        {
            run.SetValue(WindowsIntegration.AutostartValue, $"\"{paths.App}\" --from-windows-start");
        }

        Assert.That(Everything(), Is.Not.EqualTo(withTheirRun), "the install left its marks");

        WindowsIntegration.Uninstall(paths, deleteData: false, places);

        Assert.That(Everything(), Is.EqualTo(withTheirRun), "the run value of another program stays");
    }

    [Test]
    public void Deleting_the_data_takes_baxys_data_folder_too_unless_another_baxy_shares_it()
    {
        InstallPaths paths = Installed("BAXY-App");
        Directory.CreateDirectory(Path.Combine(places.Data, "1"));
        File.WriteAllText(Path.Combine(places.Data, "1", "memory.db"), "x");
        Directory.CreateDirectory(places.OtherBaxy);

        Assert.Throws<InvalidOperationException>(() => WindowsIntegration.Uninstall(paths, deleteData: true, places));
        Assert.That(File.Exists(paths.App), Is.True, "nothing is removed when the data cannot go with it");

        Directory.Delete(places.OtherBaxy);
        WindowsIntegration.Uninstall(paths, deleteData: true, places);

        Assert.That(Directory.Exists(places.Data), Is.False);
        Assert.That(Directory.Exists(paths.Root), Is.False);
    }

    // INT16: Settings › Personalización keeps its choices in the view's localStorage (look.ts, «baxy.look»). WebView2
    // keeps it in its user data folder (EBWebView\Default\Local Storage\leveldb), which for the default profile is
    // BAXY\webview2-field (App, MainWindow.FieldViewDataFolder): «borrar tus datos» takes it with the rest.
    [Test]
    public void Deleting_the_data_takes_the_views_local_storage_too()
    {
        InstallPaths paths = Installed("BAXY-App");
        string leveldb = Path.Combine(places.Data, "webview2-field", "EBWebView", "Default", "Local Storage", "leveldb");
        Directory.CreateDirectory(leveldb);
        File.WriteAllText(Path.Combine(leveldb, "000003.log"), "_http://127.0.0.1\0\u0001baxy.look\u0001{\"reply\":\"xl\"}");

        WindowsIntegration.Uninstall(paths, deleteData: true, places);

        Assert.That(Directory.Exists(Path.Combine(places.Data, "webview2-field")), Is.False);
    }

    // Inno Setup's way: the copy that uninstalls ends the original with its result, which the caller then reads.
    [Test]
    public void The_original_is_ended_with_the_result_of_the_copy()
    {
        string copy = Path.Combine(directory, "BAXY-Instalador.exe");
        File.Copy(Path.Combine(Environment.SystemDirectory, "PING.EXE"), copy);
        using Process original = Process.Start(new ProcessStartInfo(copy, "-n 30 127.0.0.1")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
        })!;

        Assert.That(OriginalProcess.End(original.Id, 7, "BAXY-Instalador"), Is.True);
        Assert.That(original.WaitForExit(5000), Is.True);
        Assert.That(original.ExitCode, Is.EqualTo(7));
        Assert.That(OriginalProcess.End(Environment.ProcessId, 7, "BAXY-Instalador"), Is.False, "another program is never ended");
    }

    // Blind review of W1: the installer's own name is no sign of BAXY, a Downloads folder holds it too.
    [Test]
    public void A_folder_with_only_the_installer_in_it_is_not_taken_for_baxy()
    {
        string downloads = Path.Combine(directory, "Downloads");
        Directory.CreateDirectory(downloads);
        File.WriteAllText(Path.Combine(downloads, WindowsIntegration.InstallerName), "exe");
        File.WriteAllText(Path.Combine(downloads, "photo.jpg"), "mine");

        Assert.Throws<ArgumentException>(() => InstallPaths.Chosen(downloads));
        Assert.Throws<ArgumentException>(() => InstallPaths.ForUninstall(downloads, places));
    }

    [Test]
    public void A_chosen_folder_whose_neighbours_would_be_deleted_is_refused()
    {
        string folder = Path.Combine(directory, "Photos");
        Directory.CreateDirectory(folder + ".old");

        Assert.Throws<ArgumentException>(() => InstallPaths.Chosen(folder));
    }

    [Test]
    public void Uninstalling_another_folder_leaves_the_entries_of_the_registered_one()
    {
        InstallPaths registered = Installed("BAXY-App");
        InstallPaths other = new(Path.Combine(directory, "Copy"));
        Directory.CreateDirectory(Path.GetDirectoryName(other.App)!);
        File.WriteAllText(other.App, "the app");

        WindowsIntegration.Uninstall(other, deleteData: false, places);

        Assert.That(Directory.Exists(other.Root), Is.False);
        Assert.That(File.Exists(places.Link), Is.True);
        Assert.That(WindowsIntegration.RegisteredRoot(places), Is.EqualTo(registered.Root));
    }

    // The quiet uninstall from the installed copy: the published single-file exe keeps its own file open without delete
    // sharing while the original waits, and the folder cannot move («Access denied», measured with the real exe). The
    // folder is emptied around it, the entries go, and the exe and the folder go once the original ended.
    [Test]
    public void The_folder_is_emptied_around_the_exe_the_original_holds_and_both_go_once_it_ended()
    {
        InstallPaths paths = Installed("BAXY-App");
        string exe = Path.Combine(paths.Root, WindowsIntegration.InstallerName);
        File.Copy(Path.Combine(Environment.SystemDirectory, "PING.EXE"), exe, overwrite: true);
        using Process original = Process.Start(new ProcessStartInfo(exe, "-n 30 127.0.0.1")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            WorkingDirectory = directory,
        })!;

        using (new FileStream(exe, FileMode.Open, FileAccess.Read, FileShare.Read))
        {
            Assert.Catch<IOException>(() => WindowsIntegration.RemoveFolders(paths), "held like the single-file exe");
            WindowsIntegration.Uninstall(paths, deleteData: false, places, held: exe);

            Assert.That(Directory.GetFileSystemEntries(paths.Root), Is.EqualTo(new[] { exe }));
            Assert.That(File.Exists(places.Link), Is.False);
            Assert.That(WindowsIntegration.RegisteredRoot(places), Is.Null);
            Assert.That(Directory.Exists(paths.Downloads), Is.False);
        }

        Assert.That(OriginalProcess.End(original.Id, 0, "BAXY-Instalador"), Is.True);
        WindowsIntegration.DeleteHeld(paths, exe);

        Assert.That(Directory.Exists(paths.Root), Is.False);
    }

    // The other BAXY registers the same Run value from its own folder (…\Programs\BAXY\versions\…): a folder whose name
    // only begins like this one's is not this one.
    [Test]
    public void The_start_with_windows_of_a_folder_with_a_longer_name_stays()
    {
        InstallPaths paths = Installed("BAXY");
        string theirs = $"\"{Path.Combine(directory, "BAXY-Other", "Baxy.exe")}\" --from-windows-start";
        using (RegistryKey run = Registry.CurrentUser.CreateSubKey(places.RunKey))
        {
            run.SetValue(WindowsIntegration.AutostartValue, theirs);
        }

        WindowsIntegration.Uninstall(paths, deleteData: false, places);

        using RegistryKey? after = Registry.CurrentUser.OpenSubKey(places.RunKey);
        Assert.That(after?.GetValue(WindowsIntegration.AutostartValue), Is.EqualTo(theirs));
    }

    [Test]
    public void No_voice_keeps_the_installers_voice_off()
    {
        using Voice quiet = new(allowed: false);

        Assert.That(quiet.IsOn, Is.False);
    }

    private InstallPaths Installed(string name)
    {
        InstallPaths paths = new(Path.Combine(directory, name));
        Directory.CreateDirectory(Path.Combine(paths.Root, "app"));
        File.WriteAllText(paths.App, "the app");
        Directory.CreateDirectory(paths.Root + ".download");
        WindowsIntegration.Register(paths, "9.9.9", 1000, places);
        return paths;
    }

    // The files under the test's folder and every value under its registry key.
    private string[] Everything()
    {
        IEnumerable<string> files = Directory.EnumerateFileSystemEntries(directory, "*", SearchOption.AllDirectories)
            .Select(path => "file " + Path.GetRelativePath(directory, path));
        return [.. files.Concat(Values(keys)).Order(StringComparer.Ordinal)];
    }

    private static string[] Values(string name)
    {
        using RegistryKey? key = Registry.CurrentUser.OpenSubKey(name);
        if (key is null)
        {
            return [];
        }

        return key.GetValueNames().Select(value => $"value {name}\\{value}={key.GetValue(value)}")
            .Concat(key.GetSubKeyNames().SelectMany(sub => Values(name + "\\" + sub).Prepend("key " + name + "\\" + sub)))
            .ToArray();
    }
}
