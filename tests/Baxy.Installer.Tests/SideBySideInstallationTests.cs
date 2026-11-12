using Baxy.Providers.Windows.External;
using Microsoft.Win32;
using NUnit.Framework;

namespace Baxy.Installer.Tests;

/// <summary>
/// UNI2 (VIVO11, point 5): a second copy installed with --dir in another folder took the «Installed apps» entry and the
/// Start-menu shortcut of the BAXY already installed; removing the copy left that BAXY with no entry, and removing it
/// afterwards left the old BAXY beside them with no Run value and no shortcut. The rule: each installation owns only
/// what points at its own folder. Every order of installing and removing two of them, with and without the old BAXY,
/// ends with each one's marks intact while it is there and the old BAXY's given back when the last new one goes.
/// Every folder and registry key here is the test's own.
/// </summary>
[TestFixture]
internal sealed class SideBySideInstallationTests
{
    private string directory = string.Empty;
    private string keys = string.Empty;
    private WindowsPlaces places = null!;
    private InstallPaths usual = null!;
    private InstallPaths copy = null!;
    private string oldExe = string.Empty;
    private string oldCommand = string.Empty;
    private byte[] oldLink = [];

    /// <summary>The installer before UNI2, as a file: what tells it apart from this one.</summary>
    private const string BeforeTheFix = "the installer before UNI2";

    private string StartFolder => Path.GetDirectoryName(places.Link)!;

    private string UninstallParent => Path.GetDirectoryName(places.UninstallKey)!;

    [SetUp]
    public void SetUp()
    {
        directory = Path.Combine(Path.GetTempPath(), "baxy-installer-tests", Path.GetRandomFileName());
        Directory.CreateDirectory(directory);
        keys = @"Software\BAXY-Installer-Tests\" + Path.GetRandomFileName();
        usual = new InstallPaths(Path.Combine(directory, "Programs", "BAXY-App"));
        copy = new InstallPaths(Path.Combine(directory, "elsewhere", "copia"));
        places = new WindowsPlaces(
            Path.Combine(directory, "Start", "BAXY.lnk"),
            keys + @"\Uninstall\BAXY-App",
            keys + @"\Run",
            Path.Combine(directory, "data"),
            Path.Combine(directory, "Programs", "BAXY"))
        {
            Scheduler = new NoScheduler(),
            UsualRoot = usual.Root,
        };
        Directory.CreateDirectory(StartFolder);
        Registry.CurrentUser.CreateSubKey(UninstallParent).Dispose();
        Registry.CurrentUser.CreateSubKey(places.RunKey).Dispose();
        oldExe = Path.Combine(places.OtherBaxy, "versions", "1.1.1", "Baxy.exe");
        oldCommand = $"\"{oldExe}\" --from-windows-start";
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

    /// <summary>Installing <c>first</c> then <c>second</c>, removing <c>gone</c> then the other: 8 orders.</summary>
    [Test]
    public void Each_installation_keeps_its_own_marks_and_the_old_baxy_gets_its_own_back(
        [Values] bool oldBaxy, [Values] bool usualFirst, [Values] bool usualGoesFirst)
    {
        if (oldBaxy)
        {
            PutTheOldBaxy();
        }

        InstallPaths first = usualFirst ? usual : copy;
        InstallPaths second = usualFirst ? copy : usual;
        Install(first);
        Install(second);

        Assert.Multiple(() =>
        {
            Assert.That(EntryOf(usual), Is.Not.Null, "the BAXY in the usual folder has its entry in «Installed apps»");
            Assert.That(EntryOf(copy), Is.Not.Null, "the copy has its entry in «Installed apps»");
            Assert.That(EntryOf(usual), Is.Not.EqualTo(EntryOf(copy)), "one entry each");
            Assert.That(DisplayName(usual), Is.Not.EqualTo(DisplayName(copy)), "told apart in «Installed apps»");
            Assert.That(ShellLink.Target(places.Link), Is.EqualTo(first.App), "«BAXY» in Start stays the first one's");
            Assert.That(LinksTo(second), Has.Count.EqualTo(1), "the second one has a Start shortcut of its own");
            Assert.That(Run(), Is.EqualTo(Command(usual)), "the BAXY in the usual folder starts with Windows");
            // The data are shared with the old BAXY when it is there (its own check comes first), else with the other one.
            Assert.That(WindowsIntegration.DataSharedWith(usual, places), Is.EqualTo(oldBaxy ? places.OtherBaxy : copy.Root));
            Assert.That(WindowsIntegration.DataSharedWith(copy, places), Is.EqualTo(oldBaxy ? places.OtherBaxy : usual.Root));
        });

        InstallPaths gone = usualGoesFirst ? usual : copy;
        InstallPaths stays = usualGoesFirst ? copy : usual;
        WindowsIntegration.Uninstall(gone, deleteData: false, places);

        Assert.Multiple(() =>
        {
            Assert.That(EntryOf(gone), Is.Null, "the one removed leaves no entry");
            Assert.That(EntryOf(stays), Is.Not.Null, "the one that stays keeps its entry");
            Assert.That(Value(EntryOf(stays)!, "UninstallString"), Does.Contain(stays.Root));
            Assert.That(LinksTo(gone), Is.Empty, "no shortcut to a folder that is gone");
            Assert.That(LinksTo(stays), Is.Not.Empty, "the one that stays keeps a Start shortcut");
            Assert.That(Run(), Is.EqualTo(stays == usual ? Command(usual) : oldBaxy ? oldCommand : null));
        });

        WindowsIntegration.Uninstall(stays, deleteData: false, places);

        Assert.Multiple(() =>
        {
            Assert.That(Entries(), Is.Empty, "nothing of either is left in «Installed apps»");
            Assert.That(Run(), Is.EqualTo(oldBaxy ? oldCommand : null), "the old BAXY starts with Windows again");
            Assert.That(
                Directory.GetFiles(StartFolder),
                oldBaxy ? Is.EqualTo(new[] { places.Link }) : Is.Empty,
                "only the old BAXY's shortcut is left");
            if (oldBaxy)
            {
                Assert.That(File.ReadAllBytes(places.Link), Is.EqualTo(oldLink), "byte for byte");
            }
        });
    }

    /// <summary>VIVO11 exactly: the usual one, a copy with --dir, the copy removed, then the usual one, the old BAXY beside.</summary>
    [Test]
    public void The_sequence_seen_live_leaves_the_old_baxy_as_it_was()
    {
        PutTheOldBaxy();
        Install(usual);
        Install(copy);
        WindowsIntegration.Uninstall(copy, deleteData: false, places);

        Assert.That(Value(EntryOf(usual)!, "InstallLocation"), Is.EqualTo(usual.Root), "the usual one is still in «Installed apps»");
        Assert.That(ShellLink.Target(places.Link), Is.EqualTo(usual.App));

        WindowsIntegration.Uninstall(usual, deleteData: false, places);

        Assert.That(Run(), Is.EqualTo(oldCommand));
        Assert.That(File.ReadAllBytes(places.Link), Is.EqualTo(oldLink));
    }

    /// <summary>An update of either one, with the other there, touches nothing of the other.</summary>
    [TestCase(true)]
    [TestCase(false)]
    public void Updating_one_with_the_other_there_keeps_both_as_they_were(bool updateUsual)
    {
        PutTheOldBaxy();
        Install(usual);
        Install(copy);
        Dictionary<string, string> before = Snapshot();

        Install(updateUsual ? usual : copy);

        Assert.That(Snapshot(), Is.EqualTo(before));
        WindowsIntegration.Uninstall(usual, deleteData: false, places);
        WindowsIntegration.Uninstall(copy, deleteData: false, places);
        Assert.That(Run(), Is.EqualTo(oldCommand));
        Assert.That(File.ReadAllBytes(places.Link), Is.EqualTo(oldLink));
    }

    /// <summary>
    /// A PC where a copy installed before this fix already took the entry: it names the copy and keeps the usual one's
    /// shortcut as «replaced» (the old BAXY's start with Windows is kept there too). The usual one's next install or
    /// update repairs it: each gets its own entry and shortcut, and the old BAXY's start comes back when both go.
    /// </summary>
    [TestCase(true)]
    [TestCase(false)]
    public void An_entry_a_copy_took_before_the_fix_is_repaired_when_the_usual_one_updates(bool copyGoesFirst)
    {
        PutTheOldBaxy();
        Install(usual);
        // What the installer before UNI2 did when the copy was installed: the same key, its shortcut over the usual one's.
        Directory.CreateDirectory(Path.GetDirectoryName(copy.App)!);
        File.WriteAllText(copy.App, "the app");
        byte[] usualLink = File.ReadAllBytes(places.Link);
        using (RegistryKey main = Registry.CurrentUser.CreateSubKey(places.UninstallKey))
        {
            main.SetValue("InstallLocation", copy.Root);
            main.SetValue("DisplayIcon", copy.App);
            main.SetValue("UninstallString", $"\"{Path.Combine(copy.Root, WindowsIntegration.InstallerName)}\" --uninstall");
            main.SetValue("ReplacedStartLink", usualLink, RegistryValueKind.Binary);
            main.SetValue("ReplacedStartLinkTarget", usual.App);
        }

        ShellLink.Write(places.Link, copy.App, "BAXY");

        Install(usual);

        Assert.Multiple(() =>
        {
            Assert.That(Value(EntryOf(usual)!, "InstallLocation"), Is.EqualTo(usual.Root));
            Assert.That(EntryOf(copy), Is.Not.Null.And.Not.EqualTo(EntryOf(usual)));
            Assert.That(ShellLink.Target(places.Link), Is.EqualTo(usual.App));
            Assert.That(LinksTo(copy), Has.Count.EqualTo(1));
        });

        WindowsIntegration.Uninstall(copyGoesFirst ? copy : usual, deleteData: false, places);
        WindowsIntegration.Uninstall(copyGoesFirst ? usual : copy, deleteData: false, places);

        Assert.That(Entries(), Is.Empty);
        Assert.That(Run(), Is.EqualTo(oldCommand));
        Assert.That(LinksTo(usual).Concat(LinksTo(copy)), Is.Empty);
    }

    /// <summary>The App and the store's ring removal see every installation «Installed apps» names, not just one.</summary>
    [Test]
    public void Every_installation_is_found_by_its_folder()
    {
        Install(usual);
        Install(copy);

        IReadOnlyList<InstalledBaxyEntries.Entry> all = InstalledBaxyEntries.All(places.UninstallKey);
        Assert.That(all.Select(static entry => entry.Root), Is.EquivalentTo(new[] { usual.Root, copy.Root }));
        Assert.That(InstalledBaxyEntries.Holding(copy.App, places.UninstallKey)?.Root, Is.EqualTo(copy.Root));
        Assert.That(InstalledBaxyEntries.Holding(usual.App, places.UninstallKey)?.Root, Is.EqualTo(usual.Root));
        Assert.That(InstalledBaxyEntries.Holding(oldExe, places.UninstallKey), Is.Null);
    }

    /// <summary>Blind review: a main entry on a drive that is not there now is not taken; one whose folder is gone is.</summary>
    [TestCase(true)]
    [TestCase(false)]
    public void A_main_entry_is_taken_only_when_its_folder_is_surely_gone(bool driveThere)
    {
        string? missingDrive = Enumerable.Range('D', 23).Select(static letter => $"{(char)letter}:\\")
            .FirstOrDefault(static drive => !Directory.Exists(drive));
        Assume.That(missingDrive, Is.Not.Null, "every drive letter is in use");
        string away = driveThere ? Path.Combine(directory, "gone", "BAXY-App") : Path.Combine(missingDrive!, "BAXY-App");
        using (RegistryKey main = Registry.CurrentUser.CreateSubKey(places.UninstallKey))
        {
            main.SetValue("InstallLocation", away);
        }

        Install(copy);

        Assert.That(Value(places.UninstallKey, "InstallLocation"), Is.EqualTo(driveThere ? copy.Root : away));
        Assert.That(EntryOf(copy), Is.Not.Null);
    }

    /// <summary>
    /// Blind review: the old installer's state, where the copy is what Windows starts at sign-in (it took the Run value
    /// and kept the old BAXY's in the main entry): the repair moves that kept value with the copy, which gives it back.
    /// </summary>
    [Test]
    public void The_repair_moves_the_kept_start_with_the_one_windows_starts()
    {
        PutTheOldBaxy();
        Install(usual);
        Directory.CreateDirectory(Path.GetDirectoryName(copy.App)!);
        File.WriteAllText(copy.App, "the app");
        using (RegistryKey main = Registry.CurrentUser.CreateSubKey(places.UninstallKey))
        {
            main.SetValue("InstallLocation", copy.Root);
            main.SetValue("ReplacedStartLink", File.ReadAllBytes(places.Link), RegistryValueKind.Binary);
            main.SetValue("ReplacedStartLinkTarget", usual.App);
        }

        SetRun(Command(copy));
        WindowsIntegration.Register(usual, "9.9.9", 1000, places);

        Assert.That(Value(EntryOf(copy)!, WindowsIntegration.ReplacedAutostartValue), Is.EqualTo(oldCommand));
        Assert.That(Value(EntryOf(usual)!, WindowsIntegration.ReplacedAutostartValue), Is.Null);
        WindowsIntegration.Uninstall(copy, deleteData: false, places);
        Assert.That(Run(), Is.EqualTo(oldCommand));
        WindowsIntegration.Uninstall(usual, deleteData: false, places);
        Assert.That(Run(), Is.EqualTo(oldCommand));
        Assert.That(Entries(), Is.Empty);
    }

    /// <summary>
    /// Blind review: in the old installer's state, the usual one removed before any repair takes back from the copy's
    /// entry the old BAXY's start it kept there, and the copy's entry keeps nothing of it.
    /// </summary>
    [Test]
    public void Removing_the_usual_one_in_the_old_state_gives_the_old_baxy_its_start_back()
    {
        PutTheOldBaxy();
        Install(usual);
        Directory.CreateDirectory(Path.GetDirectoryName(copy.App)!);
        File.WriteAllText(copy.App, "the app");
        using (RegistryKey main = Registry.CurrentUser.CreateSubKey(places.UninstallKey))
        {
            main.SetValue("InstallLocation", copy.Root);
            main.SetValue("ReplacedStartLink", File.ReadAllBytes(places.Link), RegistryValueKind.Binary);
            main.SetValue("ReplacedStartLinkTarget", usual.App);
        }

        WindowsIntegration.Uninstall(usual, deleteData: false, places);

        Assert.That(Run(), Is.EqualTo(oldCommand));
        Assert.That(Value(places.UninstallKey, "InstallLocation"), Is.EqualTo(copy.Root), "the copy keeps its entry");
        Assert.That(Value(places.UninstallKey, WindowsIntegration.ReplacedAutostartValue), Is.Null);
        WindowsIntegration.Uninstall(copy, deleteData: false, places);
        Assert.That(Run(), Is.EqualTo(oldCommand));
        Assert.That(Entries(), Is.Empty);
    }

    /// <summary>Three at once, two of them in folders with the same name: one entry and one shortcut each.</summary>
    [Test]
    public void Three_installations_two_with_the_same_folder_name_each_keep_their_own()
    {
        InstallPaths third = new(Path.Combine(directory, "other", "copia"));
        Install(usual);
        Install(copy);
        Install(third);

        Assert.That(new[] { EntryOf(usual), EntryOf(copy), EntryOf(third) }, Is.Unique.And.Not.Contains(null));
        Assert.That(LinksTo(copy).Concat(LinksTo(third)).Distinct().Count(), Is.EqualTo(2));
        WindowsIntegration.Uninstall(copy, deleteData: false, places);
        Assert.That(LinksTo(third), Has.Count.EqualTo(1));
        Assert.That(EntryOf(third), Is.Not.Null);
        Assert.That(ShellLink.Target(places.Link), Is.EqualTo(usual.App));
        WindowsIntegration.Uninstall(usual, deleteData: false, places);
        WindowsIntegration.Uninstall(third, deleteData: false, places);
        Assert.That(Entries(), Is.Empty);
        Assert.That(Directory.GetFiles(StartFolder), Is.Empty);
    }

    /// <summary>
    /// UNI3 (VIVOU2, s11-s12): after the repair, «Installed apps» removes the copy with the uninstaller its entry names.
    /// The copy's own was the installer before UNI2, which knows neither the entry nor the shortcut the repair gave it, so
    /// it deleted the folder and left both behind. With the repairing installer in its place, nothing of the copy stays.
    /// </summary>
    [TestCase(true)]
    [TestCase(false)]
    public void Removing_the_copy_from_its_entry_after_the_repair_leaves_nothing_of_it(bool runStartsCopy)
    {
        PutTheOldBaxy();
        Install(usual);
        TakenByACopyBeforeTheFix(runStartsCopy);
        WindowsIntegration.Register(usual, "9.9.9", 1000, places);

        RemoveFromItsEntry(copy);

        Assert.Multiple(() =>
        {
            Assert.That(Directory.Exists(copy.Root), Is.False, "its folder is gone");
            Assert.That(EntryOf(copy), Is.Null, "no entry for a BAXY that is gone");
            Assert.That(LinksTo(copy), Is.Empty, "no shortcut to it");
            Assert.That(Value(places.UninstallKey, "InstallLocation"), Is.EqualTo(usual.Root));
            Assert.That(ShellLink.Target(places.Link), Is.EqualTo(usual.App));
            Assert.That(Run(), Is.EqualTo(runStartsCopy ? oldCommand : Command(usual)), "the old BAXY's start comes back with it");
        });

        WindowsIntegration.Uninstall(usual, deleteData: false, places);

        Assert.That(Entries(), Is.Empty);
        Assert.That(Run(), Is.EqualTo(oldCommand));
        Assert.That(Directory.GetFiles(StartFolder), Is.Empty, "the old BAXY's shortcut was lost before the fix; no other is left");
    }

    /// <summary>
    /// UNI3 (VIVOU2, s12): what an uninstaller before the fix left of a copy (its entry and its shortcut, its folder gone)
    /// goes the next time an installer starts, and nothing of the BAXY still there changes.
    /// </summary>
    [Test]
    public void What_an_uninstaller_before_the_fix_left_goes_when_an_installer_starts()
    {
        PutTheOldBaxy();
        Install(usual);
        // The registry and Start menu of VIVOU2's s11 (the copy with an entry and a shortcut of its own), with the copy's
        // uninstaller still the one before the fix, as it was before this fix's repair left its own there.
        Install(copy);
        File.WriteAllText(Path.Combine(copy.Root, WindowsIntegration.InstallerName), BeforeTheFix);
        RemoveFromItsEntry(copy);
        string copyEntry = EntryOf(copy)!;
        Assert.That(copyEntry, Is.Not.Null, "the uninstaller before the fix leaves the copy's entry");
        Assert.That(LinksTo(copy), Has.Count.EqualTo(1), "and its shortcut");
        string copyLink = LinksTo(copy)[0];
        Dictionary<string, string> rest = Snapshot()
            .Where(seen => !seen.Key.StartsWith(copyEntry + "|", StringComparison.Ordinal) && seen.Key != copyLink)
            .ToDictionary();

        WindowsIntegration.ForgetGone(places);

        Assert.Multiple(() =>
        {
            Assert.That(EntryOf(copy), Is.Null);
            Assert.That(LinksTo(copy), Is.Empty);
            Assert.That(Snapshot(), Is.EqualTo(rest), "nothing else changes");
        });

        WindowsIntegration.Uninstall(usual, deleteData: false, places);

        Assert.That(Entries(), Is.Empty);
        Assert.That(Run(), Is.EqualTo(oldCommand));
        Assert.That(File.ReadAllBytes(places.Link), Is.EqualTo(oldLink));
    }

    /// <summary>
    /// UNI3: what goes is only what is BAXY's by its values and surely gone: an entry beside the main one whose app and
    /// uninstaller are both missing on a drive that is there, and a BAXY shortcut to such a folder. An installation with
    /// either exe, one on a drive that is not there now, the main entry (what it kept is the old BAXY's), a key of
    /// another program's with a name like BAXY's, and a shortcut to another program stay.
    /// </summary>
    [Test]
    public void Forgetting_keeps_what_is_there_what_may_come_back_and_what_is_not_baxys()
    {
        string? missingDrive = Enumerable.Range('D', 23).Select(static letter => $"{(char)letter}:\\")
            .FirstOrDefault(static drive => !Directory.Exists(drive));
        Assume.That(missingDrive, Is.Not.Null, "every drive letter is in use");
        InstallPaths gone = new(Path.Combine(directory, "other", "gone"));
        InstallPaths unplugged = new(Path.Combine(missingDrive!, "BAXY-App"));
        InstallPaths someoneElses = new(Path.Combine(directory, "other", "someone"));
        InstallPaths loose = new(Path.Combine(directory, "other", "loose"));
        Install(usual);
        Install(copy);
        Install(gone);
        File.Delete(copy.App);
        Directory.Delete(gone.Root, recursive: true);
        Directory.Delete(usual.Root, recursive: true);
        BaxyLikeEntry(UninstallParent + @"\BAXY-App-0badc0de", unplugged.Root, "REDSOULTM");
        BaxyLikeEntry(UninstallParent + @"\BAXY-App-1badc0de", someoneElses.Root, "Someone");
        ShellLink.Write(Path.Combine(StartFolder, "BAXY (loose).lnk"), loose.App, "BAXY");
        ShellLink.Write(Path.Combine(StartFolder, "BAXY (other).lnk"), Path.Combine(someoneElses.Root, "other.exe"), "other");
        ShellLink.Write(Path.Combine(StartFolder, "BAXY (unplugged).lnk"), unplugged.App, "BAXY");

        WindowsIntegration.ForgetGone(places);

        Assert.Multiple(() =>
        {
            Assert.That(EntryOf(gone), Is.Null, "an installation with neither exe goes");
            Assert.That(LinksTo(gone).Concat(LinksTo(loose)), Is.Empty, "and the BAXY shortcuts to it or to such a folder");
            Assert.That(EntryOf(copy), Is.Not.Null, "its uninstaller is there: it can still be removed from its entry");
            Assert.That(LinksTo(copy), Has.Count.EqualTo(1));
            Assert.That(EntryOf(unplugged), Is.Not.Null, "a drive that is not there now may come back");
            Assert.That(EntryOf(someoneElses), Is.Not.Null, "not BAXY's");
            Assert.That(EntryOf(usual), Is.EqualTo(places.UninstallKey), "the main entry stays, gone or not");
            Assert.That(ShellLink.Target(places.Link), Is.EqualTo(usual.App), "and «BAXY»");
            Assert.That(File.Exists(Path.Combine(StartFolder, "BAXY (other).lnk")), Is.True, "another program's shortcut");
            Assert.That(File.Exists(Path.Combine(StartFolder, "BAXY (unplugged).lnk")), Is.True);
        });
    }

    /// <summary>
    /// Blind review of UNI3: a copy halfway through an update's swap or an uninstall is beside its folder, not gone
    /// (Installation.Replace moves it to .old and .new into its place; Remove moves it to .removing-*): it stays.
    /// </summary>
    [TestCase(".old")]
    [TestCase(".new")]
    [TestCase(".removing-0123456789abcdef")]
    public void A_copy_halfway_through_a_swap_or_an_uninstall_is_not_forgotten(string beside)
    {
        Install(usual);
        Install(copy);
        Directory.Move(copy.Root, copy.Root + beside);

        WindowsIntegration.ForgetGone(places);

        Assert.That(EntryOf(copy), Is.Not.Null);
        Assert.That(LinksTo(copy), Has.Count.EqualTo(1));
    }

    /// <summary>
    /// UNI3: when Windows does not let the repair put its uninstaller in the copy's folder, the repair is done all the
    /// same, no half-copied file is left there, and what the old uninstaller then leaves is forgotten by the next installer.
    /// </summary>
    [Test]
    public void When_the_copys_uninstaller_cannot_be_replaced_what_it_leaves_is_forgotten_later()
    {
        PutTheOldBaxy();
        Install(usual);
        TakenByACopyBeforeTheFix(runStartsCopy: false);
        string uninstaller = Path.Combine(copy.Root, WindowsIntegration.InstallerName);
        File.SetAttributes(uninstaller, FileAttributes.ReadOnly);

        WindowsIntegration.Register(usual, "9.9.9", 1000, places);

        File.SetAttributes(uninstaller, FileAttributes.Normal);
        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllText(uninstaller), Is.EqualTo(BeforeTheFix), "the old one stays, whole");
            Assert.That(Directory.GetFiles(copy.Root, "*.new"), Is.Empty, "no half-copied uninstaller beside it");
            Assert.That(Value(places.UninstallKey, "InstallLocation"), Is.EqualTo(usual.Root), "the main entry is repaired");
            Assert.That(EntryOf(copy), Is.Not.Null.And.Not.EqualTo(places.UninstallKey));
        });

        RemoveFromItsEntry(copy);
        WindowsIntegration.ForgetGone(places);

        Assert.That(EntryOf(copy), Is.Null);
        Assert.That(LinksTo(copy), Is.Empty);
        Assert.That(ShellLink.Target(places.Link), Is.EqualTo(usual.App));
    }

    /// <summary>
    /// The old installer's state (as in <see cref="An_entry_a_copy_took_before_the_fix_is_repaired_when_the_usual_one_updates"/>),
    /// with the copy's own uninstaller being that installer: it took the main entry, kept the usual one's shortcut as
    /// «replaced» and, when <paramref name="runStartsCopy"/>, Windows starts it at sign-in.
    /// </summary>
    private void TakenByACopyBeforeTheFix(bool runStartsCopy)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(copy.App)!);
        File.WriteAllText(copy.App, "the app");
        string uninstaller = Path.Combine(copy.Root, WindowsIntegration.InstallerName);
        File.WriteAllText(uninstaller, BeforeTheFix);
        using (RegistryKey main = Registry.CurrentUser.CreateSubKey(places.UninstallKey))
        {
            main.SetValue("InstallLocation", copy.Root);
            main.SetValue("DisplayIcon", copy.App);
            main.SetValue("UninstallString", $"\"{uninstaller}\" --uninstall");
            main.SetValue("QuietUninstallString", $"\"{uninstaller}\" --uninstall --quiet");
            main.SetValue("ReplacedStartLink", File.ReadAllBytes(places.Link), RegistryValueKind.Binary);
            main.SetValue("ReplacedStartLinkTarget", usual.App);
        }

        ShellLink.Write(places.Link, copy.App, "BAXY");
        if (runStartsCopy)
        {
            SetRun(Command(copy));
        }
    }

    /// <summary>
    /// What «Installed apps» does: it runs the uninstaller the entry names. This installer removes the installation as it
    /// is now (<see cref="WindowsIntegration.Uninstall"/>); the one before UNI2 (bf2dcf470, RemoveEntries) only what it
    /// knew of: the folder, the Run value that starts it (with nothing given back when the main entry is not its own),
    /// and the main entry and «BAXY» when they are its own.
    /// </summary>
    private void RemoveFromItsEntry(InstallPaths paths)
    {
        string quoted = Value(EntryOf(paths)!, "UninstallString") ?? string.Empty;
        Assert.That(quoted, Does.StartWith("\""));
        string uninstaller = quoted[1..quoted.IndexOf('"', 1)];
        if (File.ReadAllBytes(uninstaller).AsSpan().SequenceEqual(File.ReadAllBytes(Environment.ProcessPath!)))
        {
            WindowsIntegration.Uninstall(paths, deleteData: false, places);
            return;
        }

        Assert.That(File.ReadAllText(uninstaller), Is.EqualTo(BeforeTheFix), "the uninstaller is this installer or the one before the fix");
        if (Run() is { } command && command.Contains(paths.Root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
        {
            using RegistryKey run = Registry.CurrentUser.OpenSubKey(places.RunKey, writable: true)!;
            run.DeleteValue(WindowsIntegration.AutostartValue);
        }

        if (string.Equals(Value(places.UninstallKey, "InstallLocation"), paths.Root, StringComparison.OrdinalIgnoreCase))
        {
            if (string.Equals(ShellLink.Target(places.Link), paths.App, StringComparison.OrdinalIgnoreCase))
            {
                File.Delete(places.Link);
            }

            Registry.CurrentUser.DeleteSubKeyTree(places.UninstallKey);
        }

        Directory.Delete(paths.Root, recursive: true);
    }

    /// <summary>An entry with the values this installer writes (<see cref="WindowsIntegration.Register"/>).</summary>
    private static void BaxyLikeEntry(string entry, string root, string publisher)
    {
        string installer = Path.Combine(root, WindowsIntegration.InstallerName);
        using RegistryKey key = Registry.CurrentUser.CreateSubKey(entry);
        key.SetValue("DisplayName", $"BAXY ({root})");
        key.SetValue("Publisher", publisher);
        key.SetValue("InstallLocation", root);
        key.SetValue("DisplayIcon", Path.Combine(root, "app", "Baxy.exe"));
        key.SetValue("UninstallString", $"\"{installer}\" --uninstall");
    }

    private void PutTheOldBaxy()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(oldExe)!);
        File.WriteAllText(oldExe, "the old app");
        ShellLink.Write(places.Link, oldExe, "BAXY");
        oldLink = File.ReadAllBytes(places.Link);
        SetRun(oldCommand);
    }

    /// <summary>The installer's last step, then the App's first start (WindowsAutostartRegistration): only the one in
    /// the usual folder takes the Run value, keeping the old one's in its own entry.</summary>
    private void Install(InstallPaths paths)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(paths.App)!);
        File.WriteAllText(paths.App, "the app");
        WindowsIntegration.Register(paths, "9.9.9", 1000, places);
        if (paths != usual || Run() == Command(usual))
        {
            return;
        }

        if (Run() is { } current && current.Contains(places.OtherBaxy, StringComparison.OrdinalIgnoreCase)
            && EntryOf(usual) is { } entry)
        {
            using RegistryKey key = Registry.CurrentUser.OpenSubKey(entry, writable: true)!;
            key.SetValue(WindowsIntegration.ReplacedAutostartValue, current);
        }

        SetRun(Command(usual));
    }

    private static string Command(InstallPaths paths) => $"\"{paths.App}\" --from-windows-start";

    private List<string> Entries()
    {
        using RegistryKey parent = Registry.CurrentUser.OpenSubKey(UninstallParent)!;
        return [.. parent.GetSubKeyNames().Select(name => UninstallParent + @"\" + name)];
    }

    private string? EntryOf(InstallPaths paths) =>
        Entries().FirstOrDefault(entry => string.Equals(Value(entry, "InstallLocation"), paths.Root, StringComparison.OrdinalIgnoreCase));

    private string? DisplayName(InstallPaths paths) => EntryOf(paths) is { } entry ? Value(entry, "DisplayName") : null;

    private static string? Value(string entry, string name)
    {
        using RegistryKey? key = Registry.CurrentUser.OpenSubKey(entry);
        return key?.GetValue(name) as string;
    }

    private List<string> LinksTo(InstallPaths paths) =>
        [.. Directory.GetFiles(StartFolder, "*.lnk").Where(link => string.Equals(ShellLink.Target(link), paths.App, StringComparison.OrdinalIgnoreCase))];

    private Dictionary<string, string> Snapshot()
    {
        Dictionary<string, string> seen = new(StringComparer.Ordinal);
        foreach (string entry in Entries())
        {
            using RegistryKey key = Registry.CurrentUser.OpenSubKey(entry)!;
            foreach (string name in key.GetValueNames().Where(static name => name != "DisplayVersion" && name != "EstimatedSize"))
            {
                seen[entry + "|" + name] = key.GetValue(name) is byte[] bytes ? Convert.ToHexString(bytes) : $"{key.GetValue(name)}";
            }
        }

        // A shortcut written again holds the target's new file times (MS-SHLLINK, ShellLinkHeader): what it starts counts.
        foreach (string link in Directory.GetFiles(StartFolder))
        {
            seen[link] = ShellLink.Target(link) ?? "?";
        }

        seen["run"] = Run() ?? "-";
        return seen;
    }

    private void SetRun(string command)
    {
        using RegistryKey run = Registry.CurrentUser.CreateSubKey(places.RunKey);
        run.SetValue(WindowsIntegration.AutostartValue, command);
    }

    private string? Run()
    {
        using RegistryKey? run = Registry.CurrentUser.OpenSubKey(places.RunKey);
        return run?.GetValue(WindowsIntegration.AutostartValue) as string;
    }

    /// <summary>No alarm is set in these cases: a scheduler that is never opened.</summary>
    private sealed class NoScheduler : ITaskSchedulerHost
    {
        public ITaskSchedulerSession Open() => throw new AssertionException("the scheduler was opened");

        public int? ToastsEnabledSetting() => null;

        public string CurrentUserSid() => "S-1-5-21-1-2-3-1001";
    }
}
