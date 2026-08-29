using Baxy.Providers.Windows.Applications;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class WindowsApplicationOpenProviderTests
{
    private const long FirstCreationTime = 638_880_000_000_000_000;

    [Test]
    public async Task NewInvocationPersistsIntentAndUsesOnlyTheBreakawayBootstrapLaunch()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        FakeProcessState launched = environment.Win32Process(
            processId: 71,
            creationTime: FirstCreationTime,
            windowHandle: (nint)0x701,
            foreground: true);
        platform.ProcessToCreate = launched;
        WindowsApplicationLauncher launcher = environment.CreateLauncher(platform);
        ApplicationOpenRequest request = Request();

        ApplicationLaunchReceipt receipt = await launcher.LaunchAsync(
            request,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.LaunchIssued, Is.True);
            Assert.That(receipt.ReusedExisting, Is.False);
            Assert.That(receipt.ProcessId, Is.EqualTo(71));
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(platform.CreateCalls, Is.EqualTo(1));
            Assert.That(platform.LastCreatedExecutable, Is.EqualTo(environment.BootstrapPath));
            Assert.That(platform.LastCreationFlags, Is.EqualTo(0x01000000));
            Assert.That(platform.LastInheritHandles, Is.False);
            Assert.That(platform.LastCommandLine, Is.Null);
            Assert.That(File.Exists(environment.StatePathFor(request.InvocationId)), Is.True);
        });
    }

    [Test]
    public void CrashAfterCreateBeforeReceiptThenReopenReconcilesWithoutSecondLaunch()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        platform.ProcessToCreate = environment.Win32Process(
            72,
            FirstCreationTime,
            (nint)0x702,
            foreground: true);
        ApplicationOpenRequest request = Request();
        WindowsApplicationLauncher crashing = environment.CreateLauncher(
            platform,
            static () => throw new SyntheticCrashException());

        Assert.That(
            async () => await crashing.LaunchAsync(request, CancellationToken.None),
            Throws.TypeOf<SyntheticCrashException>());

        WindowsApplicationLauncher reopened = environment.CreateLauncher(platform);
        ApplicationLaunchReceipt reconciled = reopened.LaunchAsync(
            request,
            CancellationToken.None).AsTask().GetAwaiter().GetResult();

        Assert.Multiple(() =>
        {
            Assert.That(platform.CreateCalls, Is.EqualTo(1));
            Assert.That(reconciled.LaunchIssued, Is.True);
            Assert.That(reconciled.ReusedExisting, Is.False);
            Assert.That(reconciled.ProcessId, Is.EqualTo(72));
            Assert.That(reconciled.ErrorCode, Is.Null);
        });
    }

    [Test]
    public void CrashIntentWithoutObservableProcessFailsClosedWithoutSecondLaunch()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        FakeProcessState launched = environment.Win32Process(
            721,
            FirstCreationTime,
            (nint)0x721,
            foreground: true);
        platform.ProcessToCreate = launched;
        ApplicationOpenRequest request = Request();
        WindowsApplicationLauncher crashing = environment.CreateLauncher(
            platform,
            static () => throw new SyntheticCrashException());

        Assert.That(
            async () => await crashing.LaunchAsync(request, CancellationToken.None),
            Throws.TypeOf<SyntheticCrashException>());

        launched.Alive = false;
        ApplicationLaunchReceipt ambiguous = environment.CreateLauncher(platform)
            .LaunchAsync(request, CancellationToken.None).AsTask().GetAwaiter().GetResult();

        Assert.Multiple(() =>
        {
            Assert.That(platform.CreateCalls, Is.EqualTo(1));
            Assert.That(ambiguous.LaunchIssued, Is.True);
            Assert.That(ambiguous.ProcessId, Is.Null);
            Assert.That(ambiguous.ErrorCode, Is.EqualTo(
                ApplicationOpenErrorCodes.VerificationFailed));
        });
    }

    [TestCase(true)]
    [TestCase(false)]
    public void CrashIntentInventoryFailurePreservesPossibleEffectWithoutRelaunch(
        bool failInitialReplayInventory)
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        FakeProcessState launched = environment.Win32Process(
            722,
            FirstCreationTime,
            (nint)0x722,
            foreground: true);
        platform.ProcessToCreate = launched;
        ApplicationOpenRequest request = Request();
        WindowsApplicationLauncher crashing = environment.CreateLauncher(
            platform,
            static () => throw new SyntheticCrashException());

        Assert.That(
            async () => await crashing.LaunchAsync(request, CancellationToken.None),
            Throws.TypeOf<SyntheticCrashException>());

        if (failInitialReplayInventory)
        {
            platform.ThrowInventory = true;
        }
        else
        {
            launched.Alive = false;
            platform.ThrowInventoryOnCall = platform.InventoryCalls + 2;
        }

        ApplicationLaunchReceipt uncertain = environment.CreateLauncher(platform)
            .LaunchAsync(request, CancellationToken.None).AsTask().GetAwaiter().GetResult();

        Assert.Multiple(() =>
        {
            Assert.That(platform.CreateCalls, Is.EqualTo(1));
            Assert.That(uncertain.LaunchIssued, Is.True);
            Assert.That(uncertain.ErrorCode, Is.EqualTo(
                ApplicationOpenErrorCodes.InventoryFailed));
        });
    }

    [Test]
    public void CrashIntentTargetResolutionFailurePreservesPossibleEffectWithoutRelaunch()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        platform.ProcessToCreate = environment.Win32Process(
            723,
            FirstCreationTime,
            (nint)0x723,
            foreground: true);
        ApplicationOpenRequest request = Request();
        WindowsApplicationLauncher crashing = environment.CreateLauncher(
            platform,
            static () => throw new SyntheticCrashException());

        Assert.That(
            async () => await crashing.LaunchAsync(request, CancellationToken.None),
            Throws.TypeOf<SyntheticCrashException>());

        platform.ThrowTargetMissing = true;
        ApplicationLaunchReceipt uncertain = environment.CreateLauncher(platform)
            .LaunchAsync(request, CancellationToken.None).AsTask().GetAwaiter().GetResult();

        Assert.Multiple(() =>
        {
            Assert.That(platform.CreateCalls, Is.EqualTo(1));
            Assert.That(uncertain.LaunchIssued, Is.True);
            Assert.That(uncertain.ErrorCode, Is.EqualTo(
                ApplicationOpenErrorCodes.ApplicationNotFound));
        });
    }

    [Test]
    public async Task EffectOnlyReceiptIsReconciledAsPendingIntentBeforeAnyRelaunch()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        FakeProcessState process = environment.Win32Process(
            73,
            FirstCreationTime,
            (nint)0x703,
            foreground: true);
        process.ThrowInventoryOnObserve = true;
        platform.ProcessToCreate = process;
        WindowsApplicationLauncher launcher = environment.CreateLauncher(platform);
        ApplicationOpenRequest request = Request();

        ApplicationLaunchReceipt partial = await launcher.LaunchAsync(
            request,
            CancellationToken.None);
        process.ThrowInventoryOnObserve = false;
        ApplicationLaunchReceipt reconciled = await environment.CreateLauncher(platform)
            .LaunchAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(partial.LaunchIssued, Is.True);
            Assert.That(partial.ProcessId, Is.Null);
            Assert.That(partial.ErrorCode, Is.EqualTo(ApplicationOpenErrorCodes.InventoryFailed));
            Assert.That(reconciled.ProcessId, Is.EqualTo(73));
            Assert.That(reconciled.ErrorCode, Is.Null);
            Assert.That(platform.CreateCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task EffectOnlyWithoutCandidateFailsClosedButNewInvocationCanProgress()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        FakeProcessState firstProcess = environment.Win32Process(
            731,
            FirstCreationTime,
            (nint)0x731,
            foreground: true);
        firstProcess.ThrowInventoryOnObserve = true;
        platform.ProcessToCreate = firstProcess;
        ApplicationOpenRequest firstRequest = Request();

        ApplicationLaunchReceipt partial = await environment.CreateLauncher(platform)
            .LaunchAsync(firstRequest, CancellationToken.None);
        firstProcess.ThrowInventoryOnObserve = false;
        firstProcess.Alive = false;
        ApplicationLaunchReceipt ambiguous = await environment.CreateLauncher(platform)
            .LaunchAsync(firstRequest, CancellationToken.None);

        FakeProcessState secondProcess = environment.Win32Process(
            732,
            FirstCreationTime + 1,
            (nint)0x732,
            foreground: true);
        platform.ProcessToCreate = secondProcess;
        ApplicationLaunchReceipt fresh = await environment.CreateLauncher(platform)
            .LaunchAsync(Request(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(partial.ErrorCode, Is.EqualTo(
                ApplicationOpenErrorCodes.InventoryFailed));
            Assert.That(ambiguous.ErrorCode, Is.EqualTo(
                ApplicationOpenErrorCodes.VerificationFailed));
            Assert.That(ambiguous.LaunchIssued, Is.True);
            Assert.That(ambiguous.ProcessId, Is.Null);
            Assert.That(fresh.ErrorCode, Is.Null);
            Assert.That(fresh.ProcessId, Is.EqualTo(732));
            Assert.That(platform.CreateCalls, Is.EqualTo(2));
        });
    }

    [Test]
    public async Task CompletionCapacityIsReservedBeforeCreateProcess()
    {
        using TestEnvironment environment = new();
        string capacityFiller = Path.Combine(environment.StateDirectory, "capacity.json");
        using (FileStream stream = new(
            capacityFiller,
            FileMode.CreateNew,
            FileAccess.Write,
            FileShare.None))
        {
            stream.SetLength((64L * 1024 * 1024) - (512L * 1024));
        }

        FakePlatform platform = environment.CreatePlatform();
        platform.ProcessToCreate = environment.Win32Process(
            74,
            FirstCreationTime,
            (nint)0x704,
            foreground: true);

        ApplicationOpenRequest request = Request();
        ApplicationLaunchReceipt receipt = await environment.CreateLauncher(platform)
            .LaunchAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(
                ApplicationOpenErrorCodes.StateCapacityReached));
            Assert.That(receipt.LaunchIssued, Is.False);
            Assert.That(platform.CreateCalls, Is.Zero);
            Assert.That(File.Exists(environment.StatePathFor(request.InvocationId)), Is.False);
        });
    }

    [Test]
    public async Task InventoryFailureFailsClosedBeforeLaunch()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        platform.ThrowInventory = true;
        platform.ProcessToCreate = environment.Win32Process(
            75,
            FirstCreationTime,
            (nint)0x705,
            foreground: true);

        ApplicationLaunchReceipt receipt = await environment.CreateLauncher(platform)
            .LaunchAsync(Request(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(
                ApplicationOpenErrorCodes.InventoryFailed));
            Assert.That(receipt.LaunchIssued, Is.False);
            Assert.That(platform.CreateCalls, Is.Zero);
        });
    }

    [Test]
    public void PreCancelledRequestDoesNotTouchStateInventoryOrLaunch()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        WindowsApplicationLauncher launcher = environment.CreateLauncher(platform);
        using CancellationTokenSource cancellation = new();
        cancellation.Cancel();

        Assert.That(
            async () => await launcher.LaunchAsync(Request(), cancellation.Token),
            Throws.InstanceOf<OperationCanceledException>());

        Assert.Multiple(() =>
        {
            Assert.That(platform.InventoryCalls, Is.Zero);
            Assert.That(platform.CreateCalls, Is.Zero);
            Assert.That(
                Directory.EnumerateFileSystemEntries(environment.StateDirectory),
                Is.Empty);
        });
    }

    [Test]
    public async Task MissingTrustedBootstrapReturnsAppNotFoundWithoutLaunch()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        platform.ThrowTargetMissing = true;

        ApplicationLaunchReceipt receipt = await environment.CreateLauncher(platform)
            .LaunchAsync(Request(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(
                ApplicationOpenErrorCodes.ApplicationNotFound));
            Assert.That(platform.InventoryCalls, Is.Zero);
            Assert.That(platform.CreateCalls, Is.Zero);
        });
    }

    [Test]
    public async Task CreateProcessFailureLeavesRetryableIntentAndSameInvocationCanRetry()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        platform.ThrowLaunch = true;
        platform.ProcessToCreate = environment.Win32Process(
            751,
            FirstCreationTime,
            (nint)0x751,
            foreground: true);
        WindowsApplicationLauncher launcher = environment.CreateLauncher(platform);
        ApplicationOpenRequest request = Request();

        ApplicationLaunchReceipt failed = await launcher.LaunchAsync(
            request,
            CancellationToken.None);
        platform.ThrowLaunch = false;
        ApplicationLaunchReceipt retried = await launcher.LaunchAsync(
            request,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(failed.ErrorCode, Is.EqualTo(
                ApplicationOpenErrorCodes.LaunchFailed));
            Assert.That(failed.LaunchIssued, Is.False);
            Assert.That(File.Exists(environment.StatePathFor(request.InvocationId)), Is.True);
            Assert.That(retried.LaunchIssued, Is.True);
            Assert.That(retried.ProcessId, Is.EqualTo(751));
            Assert.That(platform.CreateCalls, Is.EqualTo(2));
        });
    }

    [Test]
    public async Task DifferentInvocationReusesAndFocusesExistingNotepadWithoutClosingIt()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        FakeProcessState existing = environment.Win32Process(
            76,
            FirstCreationTime,
            (nint)0x706,
            foreground: false);
        platform.Processes.Add(existing);
        WindowsApplicationLauncher launcher = environment.CreateLauncher(platform);

        ApplicationLaunchReceipt first = await launcher.LaunchAsync(
            Request(),
            CancellationToken.None);
        ApplicationLaunchReceipt second = await launcher.LaunchAsync(
            Request(),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.ReusedExisting, Is.True);
            Assert.That(second.ReusedExisting, Is.True);
            Assert.That(platform.CreateCalls, Is.Zero);
            Assert.That(existing.FocusRequests, Is.EqualTo(2));
            Assert.That(existing.TerminationRequests, Is.Zero);
            Assert.That(existing.Alive, Is.True);
        });
    }

    [Test]
    public async Task CompletedLaunchWithExitedProcessNeverRelaunchesSameInvocation()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        FakeProcessState launched = environment.Win32Process(
            7601,
            FirstCreationTime,
            (nint)0x7601,
            foreground: true);
        platform.ProcessToCreate = launched;
        ApplicationOpenRequest request = Request();
        WindowsApplicationLauncher launcher = environment.CreateLauncher(platform);

        ApplicationLaunchReceipt first = await launcher.LaunchAsync(
            request,
            CancellationToken.None);
        launched.Alive = false;
        platform.ProcessToCreate = environment.Win32Process(
            7602,
            FirstCreationTime + 1,
            (nint)0x7602,
            foreground: true);
        ApplicationLaunchReceipt replay = await launcher.LaunchAsync(
            request,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.ErrorCode, Is.Null);
            Assert.That(replay.ErrorCode, Is.EqualTo(
                ApplicationOpenErrorCodes.VerificationFailed));
            Assert.That(replay.LaunchIssued, Is.True);
            Assert.That(replay.ProcessId, Is.EqualTo(7601));
            Assert.That(platform.CreateCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task CompletedReuseWithExitedProcessNeverLaunchesSameInvocation()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        FakeProcessState existing = environment.Win32Process(
            7603,
            FirstCreationTime,
            (nint)0x7603,
            foreground: true);
        platform.Processes.Add(existing);
        platform.ProcessToCreate = environment.Win32Process(
            7604,
            FirstCreationTime + 1,
            (nint)0x7604,
            foreground: true);
        ApplicationOpenRequest request = Request();
        WindowsApplicationLauncher launcher = environment.CreateLauncher(platform);

        ApplicationLaunchReceipt first = await launcher.LaunchAsync(
            request,
            CancellationToken.None);
        existing.Alive = false;
        ApplicationLaunchReceipt replay = await launcher.LaunchAsync(
            request,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.ReusedExisting, Is.True);
            Assert.That(replay.ErrorCode, Is.EqualTo(
                ApplicationOpenErrorCodes.VerificationFailed));
            Assert.That(replay.ReusedExisting, Is.True);
            Assert.That(replay.ProcessId, Is.EqualTo(7603));
            Assert.That(platform.CreateCalls, Is.Zero);
        });
    }

    [Test]
    public async Task ExistingCandidateExitDuringFocusBecomesVerificationFailure()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        FakeProcessState existing = environment.Win32Process(
            761,
            FirstCreationTime,
            (nint)0x761,
            foreground: false);
        existing.ExitOnObservation = 2;
        platform.Processes.Add(existing);

        ApplicationLaunchReceipt receipt = await environment.CreateLauncher(platform)
            .LaunchAsync(Request(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(
                ApplicationOpenErrorCodes.VerificationFailed));
            Assert.That(receipt.ReusedExisting, Is.True);
            Assert.That(platform.CreateCalls, Is.Zero);
            Assert.That(existing.Alive, Is.False);
        });
    }

    [Test]
    public async Task LaunchedCandidateExitDuringFocusBecomesVerificationFailure()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        FakeProcessState launched = environment.Win32Process(
            762,
            FirstCreationTime,
            (nint)0x762,
            foreground: false);
        launched.ExitOnObservation = 3;
        platform.ProcessToCreate = launched;

        ApplicationLaunchReceipt receipt = await environment.CreateLauncher(platform)
            .LaunchAsync(Request(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(
                ApplicationOpenErrorCodes.VerificationFailed));
            Assert.That(receipt.LaunchIssued, Is.True);
            Assert.That(platform.CreateCalls, Is.EqualTo(1));
            Assert.That(launched.Alive, Is.False);
        });
    }

    [Test]
    public async Task ExistingCandidateWithoutWindowIsWaitedAndNeverDuplicated()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        FakeProcessState existing = environment.Win32Process(
            77,
            FirstCreationTime,
            windowHandle: 0,
            foreground: false);
        platform.Processes.Add(existing);

        ApplicationLaunchReceipt receipt = await environment.CreateLauncher(platform)
            .LaunchAsync(Request(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ReusedExisting, Is.True);
            Assert.That(receipt.WindowHandle, Is.Null);
            Assert.That(platform.DelayCalls, Is.EqualTo(19));
            Assert.That(platform.CreateCalls, Is.Zero);
        });
    }

    [Test]
    public async Task ExplicitMicrosoftPackagedIdentityIsReusedWithoutBootstrapLaunch()
    {
        using TestEnvironment environment = new();
        string packageFullName =
            "Microsoft.WindowsNotepad_11.2605.29.0_x64__8wekyb3d8bbwe";
        string executablePath = environment.CreatePackagedExecutable(packageFullName);
        FakePlatform platform = environment.CreatePlatform();
        FakeProcessState packaged = new()
        {
            ProcessId = 78,
            CreationTimeUtcTicks = FirstCreationTime,
            ExecutablePath = executablePath,
            PackageFamilyName = "Microsoft.WindowsNotepad_8wekyb3d8bbwe",
            PackageFullName = packageFullName,
            WindowHandle = (nint)0x708,
            WindowVisible = true,
            Foreground = true,
        };
        platform.Processes.Add(packaged);

        ApplicationLaunchReceipt receipt = await environment.CreateLauncher(platform)
            .LaunchAsync(Request(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ReusedExisting, Is.True);
            Assert.That(receipt.PackageFamilyName, Is.EqualTo(
                "Microsoft.WindowsNotepad_8wekyb3d8bbwe"));
            Assert.That(receipt.ExecutablePath, Is.EqualTo(executablePath));
            Assert.That(platform.CreateCalls, Is.Zero);
            Assert.That(packaged.TerminationRequests, Is.Zero);
        });
    }

    [TestCase("family")]
    [TestCase("publisher")]
    [TestCase("short_version")]
    [TestCase("resource")]
    [TestCase("path")]
    [TestCase("reparse")]
    public async Task InvalidPackagedIdentityOrUntrustedPathIsNeverReused(string defect)
    {
        using TestEnvironment environment = new();
        bool trustPackagedPath = !string.Equals(defect, "reparse", StringComparison.Ordinal);
        FakePlatform platform = environment.CreatePlatform(trustPackagedPath);
        string validFullName =
            "Microsoft.WindowsNotepad_11.2605.29.0_x64__8wekyb3d8bbwe";
        string packageFullName = defect switch
        {
            "publisher" => "Microsoft.WindowsNotepad_11.2605.29.0_x64__evilpublisher",
            "short_version" =>
                "Microsoft.WindowsNotepad_11.2605_x64__8wekyb3d8bbwe",
            "resource" =>
                "Microsoft.WindowsNotepad_11.2605.29.0_x64_neutral_8wekyb3d8bbwe",
            _ => validFullName,
        };
        string executablePath = environment.CreatePackagedExecutable(packageFullName);
        if (string.Equals(defect, "path", StringComparison.Ordinal))
        {
            executablePath = Path.Combine(
                environment.ProgramFilesDirectory,
                "WindowsApps",
                validFullName,
                "Other",
                "Notepad.exe");
            Directory.CreateDirectory(Path.GetDirectoryName(executablePath)!);
            File.WriteAllBytes(executablePath, [0x4D, 0x5A]);
        }

        platform.Processes.Add(new FakeProcessState
        {
            ProcessId = 781,
            CreationTimeUtcTicks = FirstCreationTime,
            ExecutablePath = executablePath,
            PackageFamilyName = string.Equals(defect, "family", StringComparison.Ordinal)
                ? "Contoso.Notepad_1234567890abc"
                : "Microsoft.WindowsNotepad_8wekyb3d8bbwe",
            PackageFullName = packageFullName,
            WindowHandle = (nint)0x781,
            WindowVisible = true,
            Foreground = true,
        });
        platform.ProcessToCreate = environment.Win32Process(
            782,
            FirstCreationTime + TimeSpan.TicksPerSecond,
            (nint)0x782,
            foreground: true);

        ApplicationLaunchReceipt receipt = await environment.CreateLauncher(platform)
            .LaunchAsync(Request(), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.LaunchIssued, Is.True);
            Assert.That(receipt.ReusedExisting, Is.False);
            Assert.That(receipt.ProcessId, Is.EqualTo(782));
            Assert.That(platform.CreateCalls, Is.EqualTo(1));
            Assert.That(platform.Processes[0].FocusRequests, Is.Zero);
        });
    }

    [Test]
    public async Task FalseLauncherCannotMakeIndependentRealVerifierSucceed()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        ApplicationOpenRequest request = Request();
        ApplicationLaunchReceipt invented = ReceiptFor(
            request,
            environment.BootstrapPath,
            processId: 79,
            creationTime: FirstCreationTime,
            windowHandle: 0x709,
            launchIssued: true);
        WindowsApplicationOpenProvider provider = new(
            new StubLauncher(invented),
            new WindowsApplicationOpenVerifier(platform));

        ApplicationOpenResult result = await provider.OpenAsync(
            request,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Succeeded, Is.True);
            Assert.That(result.Verified, Is.False);
            Assert.That(result.ErrorCode, Is.EqualTo(
                ApplicationOpenErrorCodes.VerificationFailed));
            Assert.That(result.DisplayName, Is.EqualTo("Bloc de notas"));
            Assert.That(platform.OpenCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task VerifierRejectsPidReuseWhenCreationTimeDoesNotMatchReceipt()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        FakeProcessState reusedPid = environment.Win32Process(
            80,
            FirstCreationTime + TimeSpan.TicksPerSecond,
            (nint)0x800,
            foreground: true);
        platform.Processes.Add(reusedPid);
        ApplicationOpenRequest request = Request();
        ApplicationLaunchReceipt receipt = ReceiptFor(
            request,
            environment.BootstrapPath,
            processId: 80,
            creationTime: FirstCreationTime,
            windowHandle: 0x800,
            launchIssued: true);

        ApplicationVerificationResult verification =
            await new WindowsApplicationOpenVerifier(platform).VerifyAsync(
                request,
                receipt,
                CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(verification.Verified, Is.False);
            Assert.That(verification.ErrorCode, Is.EqualTo(
                ApplicationOpenErrorCodes.VerificationFailed));
            Assert.That(reusedPid.FocusRequests, Is.Zero);
        });
    }

    [Test]
    public async Task VerifierBindsAConvergedMainWindowAfterPackagedHandleTransition()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        FakeProcessState process = environment.Win32Process(
            800,
            FirstCreationTime,
            (nint)0x8002,
            foreground: false);
        platform.Processes.Add(process);
        ApplicationOpenRequest request = Request();
        ApplicationLaunchReceipt transientReceipt = ReceiptFor(
            request,
            environment.BootstrapPath,
            800,
            FirstCreationTime,
            windowHandle: 0x8001,
            launchIssued: true);

        ApplicationVerificationResult result =
            await new WindowsApplicationOpenVerifier(platform).VerifyAsync(
                request,
                transientReceipt,
                CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.True);
            Assert.That(result.ProcessId, Is.EqualTo(800));
            Assert.That(result.WindowHandle, Is.EqualTo(0x8002));
            Assert.That(process.FocusRequests, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task VerifierRejectsAnInvisibleWindowEvenWhenForegroundIsClaimed()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        FakeProcessState process = environment.Win32Process(
            801,
            FirstCreationTime,
            (nint)0x801,
            foreground: true);
        process.WindowVisible = false;
        process.FocusSucceeds = false;
        platform.Processes.Add(process);
        ApplicationOpenRequest request = Request();
        ApplicationLaunchReceipt receipt = ReceiptFor(
            request,
            environment.BootstrapPath,
            801,
            FirstCreationTime,
            0x801,
            launchIssued: true);

        ApplicationVerificationResult result =
            await new WindowsApplicationOpenVerifier(platform).VerifyAsync(
                request,
                receipt,
                CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.False);
            Assert.That(result.ErrorCode, Is.EqualTo(
                ApplicationOpenErrorCodes.VerificationFailed));
        });
    }

    [Test]
    public async Task VisibleNotepadIsVerifiedWhenForegroundStealIsRefused()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        FakeProcessState process = environment.Win32Process(
            802,
            FirstCreationTime,
            (nint)0x802,
            foreground: false);
        process.WindowVisible = true;
        process.FocusSucceeds = false;
        platform.Processes.Add(process);
        ApplicationOpenRequest request = Request();
        ApplicationLaunchReceipt receipt = ReceiptFor(
            request,
            environment.BootstrapPath,
            802,
            FirstCreationTime,
            0x802,
            launchIssued: true);

        ApplicationVerificationResult result =
            await new WindowsApplicationOpenVerifier(platform).VerifyAsync(
                request,
                receipt,
                CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.Verified, Is.True);
            Assert.That(result.ProcessId, Is.EqualTo(802));
            Assert.That(result.WindowHandle, Is.EqualTo(0x802));
            Assert.That(process.FocusRequests, Is.EqualTo(1));
            Assert.That(platform.DelayCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public void StoreNotepadOwnedVisibleWindowIsSelectedWhenMainWindowHandleIsZero()
    {
        const int processId = 26808;
        NotepadIdentityPolicy.ObservedTopLevelWindow[] windows =
        [
            new((nint)0x10, 1, true, 800, 600),
            new((nint)0x20, unchecked((uint)processId), false, 1920, 1080),
            new((nint)0x30, unchecked((uint)processId), true, 200, 100),
            new((nint)0x40, unchecked((uint)processId), true, 800, 600),
            new((nint)0, unchecked((uint)processId), true, 900, 900),
        ];

        nint chosen = NotepadIdentityPolicy.LargestVisibleOwnedWindow(processId, windows);

        Assert.That(chosen, Is.EqualTo((nint)0x40));
    }

    [TestCase("Bloc de notas", true)]
    [TestCase("Notepad", true)]
    [TestCase("Sin título: Bloc de notas", true)]
    [TestCase("Untitled - Notepad", true)]
    [TestCase("Calculadora", false)]
    [TestCase("Chrome", false)]
    public void StoreNotepadChromeTitleIdentifiesTheVisibleFrameHostWindow(
        string title,
        bool expected)
    {
        Assert.That(NotepadIdentityPolicy.IsNotepadWindowTitle(title), Is.EqualTo(expected));
    }

    [Test]
    public void StoreNotepadReturnsNoWindowWhenTheProcessOwnsNoneVisible()
    {
        nint chosen = NotepadIdentityPolicy.LargestVisibleOwnedWindow(
            99,
            [
                new((nint)0x10, 99, false, 400, 400),
                new((nint)0x11, 8, true, 400, 400),
            ]);

        Assert.That(chosen, Is.EqualTo(nint.Zero));
    }

    [Test]
    public async Task PartialLaunchCanRetryFocusAndVerificationWithSameInvocation()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        FakeProcessState process = environment.Win32Process(
            81,
            FirstCreationTime,
            windowHandle: 0,
            foreground: false);
        platform.ProcessToCreate = process;
        WindowsApplicationOpenProvider provider = new(
            environment.CreateLauncher(platform),
            new WindowsApplicationOpenVerifier(platform));
        ApplicationOpenRequest request = Request();

        ApplicationOpenResult partial = await provider.OpenAsync(
            request,
            CancellationToken.None);
        process.WindowHandle = (nint)0x801;
        process.WindowVisible = true;
        process.FocusSucceeds = true;
        ApplicationOpenResult retried = await provider.OpenAsync(
            request,
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(partial.Succeeded, Is.True);
            Assert.That(partial.Verified, Is.False);
            Assert.That(partial.Receipt.LaunchIssued, Is.True);
            Assert.That(retried.Verified, Is.True);
            Assert.That(retried.ProcessId, Is.EqualTo(81));
            Assert.That(retried.WindowHandle, Is.EqualTo(0x801));
            Assert.That(platform.CreateCalls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task CorruptedDurableReceiptFailsClosedWithoutInventoryOrLaunch()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        platform.ProcessToCreate = environment.Win32Process(
            82,
            FirstCreationTime,
            (nint)0x802,
            foreground: true);
        ApplicationOpenRequest request = Request();
        WindowsApplicationLauncher launcher = environment.CreateLauncher(platform);
        _ = await launcher.LaunchAsync(request, CancellationToken.None);
        int inventoryCallsBeforeCorruption = platform.InventoryCalls;
        string path = environment.StatePathFor(request.InvocationId);
        string json = File.ReadAllText(path);
        int checksumStart = json.IndexOf("\"checksum\":\"", StringComparison.Ordinal)
            + "\"checksum\":\"".Length;
        char replacement = json[checksumStart] == '0' ? '1' : '0';
        char[] corrupted = json.ToCharArray();
        corrupted[checksumStart] = replacement;
        File.WriteAllText(path, new string(corrupted));

        ApplicationLaunchReceipt result = await environment.CreateLauncher(platform)
            .LaunchAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.ErrorCode, Is.EqualTo(ApplicationOpenErrorCodes.StateCorrupt));
            Assert.That(platform.CreateCalls, Is.EqualTo(1));
            Assert.That(platform.InventoryCalls, Is.EqualTo(inventoryCallsBeforeCorruption));
        });
    }

    [TestCase("{\"version\":1,\"state\":null,\"checksum\":\"00\"}")]
    [TestCase("{\"version\":1,\"checksum\":\"00\"}")]
    public async Task NullOrMissingDurableStateFailsClosedWithoutOperatingSystemAccess(
        string json)
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        ApplicationOpenRequest request = Request();
        File.WriteAllText(environment.StatePathFor(request.InvocationId), json);

        ApplicationLaunchReceipt result = await environment.CreateLauncher(platform)
            .LaunchAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.ErrorCode, Is.EqualTo(ApplicationOpenErrorCodes.StateCorrupt));
            Assert.That(platform.InventoryCalls, Is.Zero);
            Assert.That(platform.CreateCalls, Is.Zero);
        });
    }

    [TestCase(true)]
    [TestCase(false)]
    public async Task NullOrMissingBaselineFailsClosedWithoutOperatingSystemAccess(
        bool includeNullBaseline)
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();
        ApplicationOpenRequest request = Request();
        string baseline = includeNullBaseline ? ",\"baselineProcessKeys\":null" : string.Empty;
        string json = string.Create(
            System.Globalization.CultureInfo.InvariantCulture,
            $"{{\"version\":1,\"state\":{{\"invocationId\":\"{request.InvocationId}\",\"applicationId\":\"windows.notepad\",\"intentCreatedUtcTicks\":{FirstCreationTime}{baseline},\"receipt\":null}},\"checksum\":\"00\"}}");
        File.WriteAllText(environment.StatePathFor(request.InvocationId), json);

        ApplicationLaunchReceipt result = await environment.CreateLauncher(platform)
            .LaunchAsync(request, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(result.ErrorCode, Is.EqualTo(ApplicationOpenErrorCodes.StateCorrupt));
            Assert.That(platform.InventoryCalls, Is.Zero);
            Assert.That(platform.CreateCalls, Is.Zero);
        });
    }

    [TestCase(@"C:\Windows\System32\notepad.exe")]
    [TestCase("windows.notepad & calc.exe")]
    [TestCase("WINDOWS.NOTEPAD")]
    public async Task RejectsPathsMetacharactersAndNonExactApplicationIds(string applicationId)
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();

        ApplicationLaunchReceipt receipt = await environment.CreateLauncher(platform)
            .LaunchAsync(
                new ApplicationOpenRequest(applicationId, InvocationId()),
                CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(
                ApplicationOpenErrorCodes.InvalidApplication));
            Assert.That(platform.InventoryCalls, Is.Zero);
            Assert.That(platform.CreateCalls, Is.Zero);
        });
    }

    [Test]
    public async Task RejectsNonCanonicalInvocationIdBeforeStateOrOperatingSystemAccess()
    {
        using TestEnvironment environment = new();
        FakePlatform platform = environment.CreatePlatform();

        ApplicationLaunchReceipt receipt = await environment.CreateLauncher(platform)
            .LaunchAsync(
                new ApplicationOpenRequest(ApplicationIds.Notepad, "not-a-uuid"),
                CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(
                ApplicationOpenErrorCodes.InvalidInvocation));
            Assert.That(platform.InventoryCalls, Is.Zero);
            Assert.That(platform.CreateCalls, Is.Zero);
        });
    }

    private static ApplicationOpenRequest Request() =>
        new(ApplicationIds.Notepad, InvocationId());

    private static string InvocationId() => Guid.NewGuid().ToString("D");

    private static ApplicationLaunchReceipt ReceiptFor(
        ApplicationOpenRequest request,
        string executablePath,
        int processId,
        long creationTime,
        long windowHandle,
        bool launchIssued) =>
        new(
            request.InvocationId,
            request.ApplicationId,
            launchIssued,
            ReusedExisting: !launchIssued,
            processId,
            creationTime,
            executablePath,
            PackageFamilyName: null,
            PackageFullName: null,
            windowHandle,
            ErrorCode: null);

    private sealed class StubLauncher(ApplicationLaunchReceipt receipt) : IApplicationLauncher
    {
        public ValueTask<ApplicationLaunchReceipt> LaunchAsync(
            ApplicationOpenRequest request,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(receipt);
        }
    }

    private sealed class TestEnvironment : IDisposable
    {
        private readonly string _root = Path.Combine(
            Path.GetTempPath(),
            $"baxy-app-open-{Guid.NewGuid():N}");

        public TestEnvironment()
        {
            BootstrapPath = Path.Combine(_root, "Windows", "System32", "notepad.exe");
            ProgramFilesDirectory = Path.Combine(_root, "Program Files");
            StateDirectory = Path.Combine(_root, "state");
            Directory.CreateDirectory(Path.GetDirectoryName(BootstrapPath)!);
            Directory.CreateDirectory(ProgramFilesDirectory);
            Directory.CreateDirectory(StateDirectory);
            File.WriteAllBytes(BootstrapPath, [0x4D, 0x5A]);
        }

        public string BootstrapPath { get; }

        public string ProgramFilesDirectory { get; }

        public string StateDirectory { get; }

        public FakePlatform CreatePlatform(bool trustPackagedPaths = true) => new(
            new NotepadLaunchTarget(
                BootstrapPath,
                ProgramFilesDirectory,
                new FakePathTrust(trustPackagedPaths)));

        public WindowsApplicationLauncher CreateLauncher(
            FakePlatform platform,
            Action? crashHook = null) =>
            new(
                platform,
                new ApplicationInvocationStore(StateDirectory),
                crashHook);

        public FakeProcessState Win32Process(
            int processId,
            long creationTime,
            nint windowHandle,
            bool foreground) =>
            new()
            {
                ProcessId = processId,
                CreationTimeUtcTicks = creationTime,
                ExecutablePath = BootstrapPath,
                WindowHandle = windowHandle,
                WindowVisible = windowHandle != 0,
                Foreground = foreground,
            };

        public string CreatePackagedExecutable(string packageFullName)
        {
            string path = Path.Combine(
                ProgramFilesDirectory,
                "WindowsApps",
                packageFullName,
                "Notepad",
                "Notepad.exe");
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllBytes(path, [0x4D, 0x5A]);
            return path;
        }

        public string StatePathFor(string invocationId) =>
            new ApplicationInvocationStore(StateDirectory).GetStatePath(invocationId);

        public void Dispose()
        {
            try
            {
                Directory.Delete(_root, recursive: true);
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }
    }

    private sealed class FakePlatform(NotepadLaunchTarget target) : IWindowsApplicationPlatform
    {
        public DateTimeOffset UtcNow { get; set; } =
            new(2026, 7, 14, 20, 0, 0, TimeSpan.Zero);

        public List<FakeProcessState> Processes { get; } = [];

        public FakeProcessState? ProcessToCreate { get; set; }

        public bool ThrowInventory { get; set; }

        public int? ThrowInventoryOnCall { get; set; }

        public bool ThrowTargetMissing { get; set; }

        public bool ThrowLaunch { get; set; }

        public int InventoryCalls { get; private set; }

        public int CreateCalls { get; private set; }

        public int OpenCalls { get; private set; }

        public int DelayCalls { get; private set; }

        public string? LastCreatedExecutable { get; private set; }

        public uint LastCreationFlags { get; private set; }

        public bool LastInheritHandles { get; private set; }

        public string? LastCommandLine { get; private set; }

        public NotepadLaunchTarget ResolveNotepadLaunchTarget() =>
            ThrowTargetMissing
                ? throw new FileNotFoundException("Synthetic missing bootstrap.")
                : target;

        public IReadOnlyList<IWindowsApplicationProcess> EnumerateNotepadProcesses()
        {
            InventoryCalls++;
            if (ThrowInventory || ThrowInventoryOnCall == InventoryCalls)
            {
                throw new ApplicationInventoryException("Synthetic inventory failure.");
            }

            return Processes
                .Where(static process => process.Alive)
                .Select(static process => (IWindowsApplicationProcess)new FakeProcessHandle(process))
                .ToArray();
        }

        public IWindowsApplicationProcess CreateProcess(
            string executablePath,
            uint creationFlags,
            bool inheritHandles,
            string? commandLine)
        {
            CreateCalls++;
            LastCreatedExecutable = executablePath;
            LastCreationFlags = creationFlags;
            LastInheritHandles = inheritHandles;
            LastCommandLine = commandLine;
            if (ThrowLaunch)
            {
                throw new InvalidOperationException("Synthetic CreateProcess failure.");
            }

            FakeProcessState process = ProcessToCreate
                ?? throw new InvalidOperationException("No synthetic launch was configured.");
            if (!Processes.Contains(process))
            {
                Processes.Add(process);
            }

            return new FakeProcessHandle(process);
        }

        public IWindowsApplicationProcess? OpenProcess(int processId)
        {
            OpenCalls++;
            FakeProcessState? process = Processes.LastOrDefault(
                candidate => candidate.Alive && candidate.ProcessId == processId);
            return process is null ? null : new FakeProcessHandle(process);
        }

        public ValueTask DelayAsync(TimeSpan delay, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            DelayCalls++;
            return ValueTask.CompletedTask;
        }
    }

    private sealed class FakePathTrust(bool trusted) : IApplicationPathTrust
    {
        public bool IsExistingPathWithoutReparse(string path) => trusted;
    }

    private sealed class FakeProcessState
    {
        public int ProcessId { get; init; }

        public long CreationTimeUtcTicks { get; init; }

        public required string ExecutablePath { get; init; }

        public string? PackageFamilyName { get; init; }

        public string? PackageFullName { get; init; }

        public nint WindowHandle { get; set; }

        public bool WindowVisible { get; set; }

        public bool Foreground { get; set; }

        public bool FocusSucceeds { get; set; } = true;

        public bool ThrowInventoryOnObserve { get; set; }

        public int? ExitOnObservation { get; set; }

        public int ObservationRequests { get; set; }

        public bool Alive { get; set; } = true;

        public int FocusRequests { get; set; }

        public int TerminationRequests { get; set; }
    }

    private sealed class FakeProcessHandle(FakeProcessState process) : IWindowsApplicationProcess
    {
        private bool _disposed;

        public int ProcessId => process.ProcessId;

        public ApplicationProcessObservation Observe()
        {
            ObjectDisposedException.ThrowIf(_disposed, this);
            process.ObservationRequests++;
            if (process.ExitOnObservation == process.ObservationRequests)
            {
                process.Alive = false;
            }

            if (!process.Alive)
            {
                throw new ApplicationProcessExitedException();
            }

            if (process.ThrowInventoryOnObserve)
            {
                throw new ApplicationInventoryException("Synthetic observation failure.");
            }

            return new ApplicationProcessObservation(
                process.ProcessId,
                process.CreationTimeUtcTicks,
                process.ExecutablePath,
                process.PackageFamilyName,
                process.PackageFullName,
                process.WindowHandle,
                process.WindowVisible,
                process.Foreground);
        }

        public void RequestForeground(nint windowHandle)
        {
            ObjectDisposedException.ThrowIf(_disposed, this);
            process.FocusRequests++;
            if (process.FocusSucceeds && windowHandle == process.WindowHandle)
            {
                process.Foreground = true;
            }
        }

        public void Dispose() => _disposed = true;
    }

    private sealed class SyntheticCrashException : Exception;
}
