using NUnit.Framework;

namespace Baxy.Setup.Tests;

[TestFixture]
public sealed class SetupCommandAndPathsTests
{
    [Test]
    public void EmptyArgumentsSelectInstall()
    {
        SetupCommand command = SetupCommand.Parse([]);

        Assert.Multiple(() =>
        {
            Assert.That(command.Kind, Is.EqualTo(SetupCommandKind.Install));
            Assert.That(command.DataPolicy, Is.Null);
            Assert.That(command.Quiet, Is.False);
            Assert.That(command.EvidencePath, Is.Null);
        });
    }

    [TestCase("--launch", "Launch")]
    [TestCase("--rollback", "Rollback")]
    public void ExactStandaloneCommandsAreParsed(string argument, string expectedKind)
    {
        SetupCommand command = SetupCommand.Parse([argument]);

        Assert.Multiple(() =>
        {
            Assert.That(command.Kind.ToString(), Is.EqualTo(expectedKind));
            Assert.That(command.DataPolicy, Is.Null);
            Assert.That(command.Quiet, Is.False);
            Assert.That(command.EvidencePath, Is.Null);
        });
    }

    [Test]
    public void StandardUninstallExplicitlyUsesTheSafeKeepDataPolicy()
    {
        SetupCommand command = SetupCommand.Parse(["--uninstall"]);

        Assert.Multiple(() =>
        {
            Assert.That(command.Kind, Is.EqualTo(SetupCommandKind.Uninstall));
            Assert.That(command.DataPolicy, Is.EqualTo(UninstallDataPolicy.KeepData));
            Assert.That(command.Quiet, Is.False);
            Assert.That(command.EvidencePath, Is.Null);
        });
    }

    [Test]
    public void ExactQuietKeepDataPolicyIsParsed()
    {
        SetupCommand command = SetupCommand.Parse(["--uninstall", "--keep-data", "--quiet"]);

        Assert.Multiple(() =>
        {
            Assert.That(command.Kind, Is.EqualTo(SetupCommandKind.Uninstall));
            Assert.That(command.DataPolicy, Is.EqualTo(UninstallDataPolicy.KeepData));
            Assert.That(command.Quiet, Is.True);
            Assert.That(command.EvidencePath, Is.Null);
        });
    }

    [Test]
    public void QuietPurgeRequiresTheExactDestructiveConfirmationToken()
    {
        SetupCommand command = SetupCommand.Parse(
            ["--uninstall", "--purge-data", "--confirm-purge-data", "--quiet"]);

        Assert.Multiple(() =>
        {
            Assert.That(command.Kind, Is.EqualTo(SetupCommandKind.Uninstall));
            Assert.That(command.DataPolicy, Is.EqualTo(UninstallDataPolicy.PurgeData));
            Assert.That(command.Quiet, Is.True);
            Assert.That(command.EvidencePath, Is.Null);
        });
    }

    [Test]
    public void ExactEmbeddedVerificationCommandPreservesEvidenceArgument()
    {
        const string evidence = @"C:\evidence\setup.json";

        SetupCommand command = SetupCommand.Parse(["--verify-embedded", "--evidence", evidence]);

        Assert.Multiple(() =>
        {
            Assert.That(command.Kind, Is.EqualTo(SetupCommandKind.VerifyEmbedded));
            Assert.That(command.DataPolicy, Is.Null);
            Assert.That(command.Quiet, Is.False);
            Assert.That(command.EvidencePath, Is.EqualTo(evidence));
        });
    }

    [TestCaseSource(nameof(InvalidCommands))]
    public void EveryOtherArgumentShapeIsRejected(string[] arguments)
    {
        Assert.That(() => SetupCommand.Parse(arguments), Throws.TypeOf<ArgumentException>());
    }

    [Test]
    public void NullArgumentArrayIsRejected()
    {
        Assert.That(() => SetupCommand.Parse(null!), Throws.TypeOf<ArgumentNullException>());
    }

    [Test]
    public void KnownFoldersProduceTheExactOwnedLayoutWithoutCreatingIt()
    {
        using TemporaryKnownFolders temporary = new();

        CanonicalWindowsPaths paths = CanonicalWindowsPaths.FromKnownFolders(
            temporary.LocalAppData,
            temporary.ProgramsFolder);

        Assert.Multiple(() =>
        {
            Assert.That(paths.InstallationRoot, Is.EqualTo(Path.Combine(temporary.LocalAppData, "Programs", "BAXY")));
            Assert.That(paths.StableSetupHost, Is.EqualTo(Path.Combine(paths.InstallationRoot, "Baxy.Setup.exe")));
            Assert.That(paths.VersionsRoot, Is.EqualTo(Path.Combine(paths.InstallationRoot, "versions")));
            Assert.That(paths.CurrentPointer, Is.EqualTo(Path.Combine(paths.InstallationRoot, "current")));
            Assert.That(paths.DataRoot, Is.EqualTo(Path.Combine(temporary.LocalAppData, "BAXY")));
            Assert.That(paths.StartMenuDirectory, Is.EqualTo(Path.Combine(temporary.ProgramsFolder, "BAXY")));
            Assert.That(paths.StartMenuShortcut, Is.EqualTo(Path.Combine(paths.StartMenuDirectory, "BAXY.lnk")));
            Assert.That(Directory.Exists(paths.InstallationRoot), Is.False);
            Assert.That(Directory.Exists(paths.DataRoot), Is.False);
            Assert.That(Directory.Exists(paths.StartMenuDirectory), Is.False);
        });
    }

    [Test]
    public void TrailingDirectorySeparatorsAreNormalized()
    {
        using TemporaryKnownFolders temporary = new();

        CanonicalWindowsPaths paths = CanonicalWindowsPaths.FromKnownFolders(
            temporary.LocalAppData + Path.DirectorySeparatorChar,
            temporary.ProgramsFolder + Path.DirectorySeparatorChar);

        Assert.Multiple(() =>
        {
            Assert.That(paths.InstallationRoot, Does.StartWith(temporary.LocalAppData + Path.DirectorySeparatorChar));
            Assert.That(paths.StartMenuDirectory, Does.StartWith(temporary.ProgramsFolder + Path.DirectorySeparatorChar));
            Assert.That(paths.InstallationRoot, Does.Not.Contain(new string(Path.DirectorySeparatorChar, 2)));
        });
    }

    [TestCase("local")]
    [TestCase("programs")]
    public void RelativeKnownFolderIsRejected(string relativeFolder)
    {
        using TemporaryKnownFolders temporary = new();
        string localAppData = relativeFolder == "local" ? "relative-local" : temporary.LocalAppData;
        string programsFolder = relativeFolder == "programs" ? "relative-programs" : temporary.ProgramsFolder;

        Assert.That(
            () => CanonicalWindowsPaths.FromKnownFolders(localAppData, programsFolder),
            Throws.TypeOf<InstallationSafetyException>());
    }

    [TestCase("local")]
    [TestCase("programs")]
    public void EmptyKnownFolderIsRejected(string emptyFolder)
    {
        using TemporaryKnownFolders temporary = new();
        string localAppData = emptyFolder == "local" ? " " : temporary.LocalAppData;
        string programsFolder = emptyFolder == "programs" ? " " : temporary.ProgramsFolder;

        Assert.That(
            () => CanonicalWindowsPaths.FromKnownFolders(localAppData, programsFolder),
            Throws.TypeOf<ArgumentException>());
    }

    [Test]
    public void ReparsePointInKnownFolderChainIsRejectedWhenWindowsAllowsCreatingIt()
    {
        using TemporaryKnownFolders temporary = new();
        string target = Path.Combine(temporary.Root, "local-target");
        string link = Path.Combine(temporary.Root, "local-link");
        Directory.CreateDirectory(target);
        _ = Baxy.Tests.NtfsTestJunction.Create(link, target);

        try
        {
            Assert.That(
                () => CanonicalWindowsPaths.FromKnownFolders(link, temporary.ProgramsFolder),
                Throws.TypeOf<InstallationSafetyException>());
        }
        finally
        {
            Directory.Delete(link);
        }
    }

    [Test]
    public void ReparsePointAtDerivedInstallationRootIsRejectedWhenWindowsAllowsCreatingIt()
    {
        using TemporaryKnownFolders temporary = new();
        string localPrograms = Path.Combine(temporary.LocalAppData, "Programs");
        string target = Path.Combine(temporary.Root, "install-target");
        string link = Path.Combine(localPrograms, "BAXY");
        Directory.CreateDirectory(localPrograms);
        Directory.CreateDirectory(target);
        _ = Baxy.Tests.NtfsTestJunction.Create(link, target);

        try
        {
            Assert.That(
                () => CanonicalWindowsPaths.FromKnownFolders(temporary.LocalAppData, temporary.ProgramsFolder),
                Throws.TypeOf<InstallationSafetyException>());
        }
        finally
        {
            Directory.Delete(link);
        }
    }

    [Test]
    public void UninstallPathResolutionDoesNotInspectTheUserDataLeaf()
    {
        using TemporaryKnownFolders temporary = new();
        string target = Path.Combine(temporary.Root, "private-data-target");
        string dataLink = Path.Combine(temporary.LocalAppData, "BAXY");
        Directory.CreateDirectory(target);
        _ = Baxy.Tests.NtfsTestJunction.Create(dataLink, target);

        try
        {
            Assert.That(
                () => CanonicalWindowsPaths.FromKnownFolders(
                    temporary.LocalAppData,
                    temporary.ProgramsFolder),
                Throws.TypeOf<InstallationSafetyException>());

            CanonicalWindowsPaths uninstall =
                CanonicalWindowsPaths.FromKnownFoldersForUninstall(
                    temporary.LocalAppData,
                    temporary.ProgramsFolder);
            Assert.Multiple(() =>
            {
                Assert.That(uninstall.DataRoot, Is.EqualTo(dataLink));
                Assert.That(Directory.Exists(target), Is.True);
                Assert.That(
                    Directory.GetFileSystemEntries(target),
                    Is.Empty,
                    "Resolving keep-data paths must not enumerate the user-data target.");
            });
        }
        finally
        {
            Directory.Delete(dataLink);
        }
    }

    private static IEnumerable<TestCaseData> InvalidCommands()
    {
        yield return Invalid("Command_names_are_case_sensitive", "--Launch");
        yield return Invalid("Launch_rejects_extra_argument", "--launch", "--quiet");
        yield return Invalid("Rollback_rejects_duplicate", "--rollback", "--rollback");
        yield return Invalid("Quiet_requires_explicit_policy", "--uninstall", "--quiet");
        yield return Invalid("Policy_requires_quiet", "--uninstall", "--keep-data");
        yield return Invalid("Purge_requires_quiet", "--uninstall", "--purge-data");
        yield return Invalid("Purge_requires_confirmation", "--uninstall", "--purge-data", "--quiet");
        yield return Invalid(
            "Purge_confirmation_order_is_fixed",
            "--uninstall",
            "--purge-data",
            "--quiet",
            "--confirm-purge-data");
        yield return Invalid(
            "Purge_confirmation_is_case_sensitive",
            "--uninstall",
            "--purge-data",
            "--Confirm-Purge-Data",
            "--quiet");
        yield return Invalid(
            "Keep_data_rejects_purge_confirmation",
            "--uninstall",
            "--keep-data",
            "--confirm-purge-data",
            "--quiet");
        yield return Invalid("Policy_order_is_fixed", "--uninstall", "--quiet", "--keep-data");
        yield return Invalid("Uninstall_must_be_first", "--quiet", "--uninstall", "--keep-data");
        yield return Invalid("Quiet_rejects_duplicate", "--uninstall", "--keep-data", "--quiet", "--quiet");
        yield return Invalid("Policies_are_exclusive", "--uninstall", "--keep-data", "--purge-data", "--quiet");
        yield return Invalid("Verification_requires_evidence_pair", "--verify-embedded");
        yield return Invalid("Evidence_requires_value", "--verify-embedded", "--evidence");
        yield return Invalid("Evidence_rejects_empty_value", "--verify-embedded", "--evidence", "");
        yield return Invalid("Evidence_rejects_blank_value", "--verify-embedded", "--evidence", "  ");
        yield return Invalid("Evidence_order_is_fixed", "--evidence", "x", "--verify-embedded");
        yield return Invalid("Verification_rejects_extra_argument", "--verify-embedded", "--evidence", "x", "--quiet");
        yield return Invalid(
            "Uninstall_worker_is_not_a_public_command",
            "--uninstall-worker",
            "0123456789abcdef0123456789abcdef");
        yield return Invalid("Public_install_root_is_forbidden", "--install-root", @"C:\BAXY");
        yield return Invalid("Public_data_root_is_forbidden", "--data-root", @"C:\BAXY-Data");
        yield return Invalid("Bare_path_is_forbidden", @"C:\BAXY\Baxy.Setup.exe");
        yield return Invalid("Null_argument_is_forbidden", new string[] { null! });
    }

    private static TestCaseData Invalid(string name, params string[] arguments) =>
        new TestCaseData((object)arguments).SetName(name);

    private sealed class TemporaryKnownFolders : IDisposable
    {
        internal TemporaryKnownFolders()
        {
            Root = Path.Combine(Path.GetTempPath(), "baxy-setup-path-tests", Guid.NewGuid().ToString("N"));
            LocalAppData = Path.Combine(Root, "local");
            ProgramsFolder = Path.Combine(Root, "start-menu", "programs");
            Directory.CreateDirectory(LocalAppData);
            Directory.CreateDirectory(ProgramsFolder);
        }

        internal string Root { get; }

        internal string LocalAppData { get; }

        internal string ProgramsFolder { get; }

        public void Dispose()
        {
            if (Directory.Exists(Root))
            {
                Directory.Delete(Root, recursive: true);
            }
        }
    }
}
