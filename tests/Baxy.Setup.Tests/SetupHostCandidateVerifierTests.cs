using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using NUnit.Framework;

namespace Baxy.Setup.Tests;

[TestFixture]
public sealed class SetupHostCandidateVerifierTests
{
    [Test]
    public void CaptureCurrentHost_UsesOnlyTheInjectedProcessPathAndHashesExactBytes()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        byte[] expectedBytes = File.ReadAllBytes(tree.SourcePath);
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(new UnexpectedRunner());

        CapturedSetupHost captured = verifier.CaptureCurrentHost();

        Assert.Multiple(() =>
        {
            Assert.That(captured.Path, Is.EqualTo(tree.SourcePath));
            Assert.That(captured.Identity.Bytes, Is.EqualTo(expectedBytes.LongLength));
            Assert.That(captured.Identity.Sha256, Is.EqualTo(Sha256(expectedBytes)));
            Assert.That(captured.Identity.Sha256, Does.Match("^[0-9a-f]{64}$"));
        });
    }

    [Test]
    public void CaptureCurrentHost_RejectsNullRelativeMissingAndDirectoryPaths()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        string missing = Path.Combine(tree.Root, "missing.exe");
        string?[] invalidPaths = [null, "relative.exe", missing, tree.Root];

        Assert.Multiple(() =>
        {
            foreach (string? path in invalidPaths)
            {
                SetupHostCandidateVerifier verifier = new(
                    new FixedProcessPathProvider(path),
                    new UnexpectedRunner());
                Assert.That(
                    verifier.CaptureCurrentHost,
                    Throws.TypeOf<InstallationSafetyException>(),
                    path ?? "null");
            }
        });
    }

    [Test]
    public void CaptureCurrentHost_RejectsAReparsePoint()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        string link = Path.Combine(tree.Root, "process-link.exe");
        string target = Path.Combine(tree.Root, "process-reparse-target");
        Directory.CreateDirectory(target);
        _ = Baxy.Tests.NtfsTestJunction.Create(link, target);

        try
        {
            SetupHostCandidateVerifier verifier = new(
                new FixedProcessPathProvider(link),
                new UnexpectedRunner());

            Assert.That(
                verifier.CaptureCurrentHost,
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(File.Exists(tree.SourcePath), Is.True);
        }
        finally
        {
            if (Path.Exists(link))
            {
                Directory.Delete(link);
            }
        }
    }

    [Test]
    public void CaptureCurrentHost_RejectsHardLinksAndPreservesBothNames()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        string alias = Path.Combine(tree.Root, "process-hard-link.exe");
        Assert.That(
            CreateHardLink(alias, tree.SourcePath, 0),
            Is.True,
            $"CreateHardLinkW failed with Win32 error {Marshal.GetLastWin32Error()}.");
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(new UnexpectedRunner());

        Assert.That(
            verifier.CaptureCurrentHost,
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(tree.SourcePath), Is.True);
            Assert.That(File.Exists(alias), Is.True);
        });
    }

    [Test]
    public void CaptureCurrentHost_RejectsAlternateDataStreamsAndPreservesThem()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        string stream = tree.SourcePath + ":foreign";
        File.WriteAllText(stream, "foreign");
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(new UnexpectedRunner());

        Assert.That(
            verifier.CaptureCurrentHost,
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(File.ReadAllText(stream), Is.EqualTo("foreign"));
    }

    [Test]
    public void VerifyStagedCandidate_UsesTheExactRequestAndAcceptsCanonicalEvidence()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        string? observedCommandLine = null;
        bool evidenceWasNew = false;
        RecordingRunner runner = new(request =>
        {
            evidenceWasNew = !FileSystemEntryExists(request.EvidencePath);
            observedCommandLine = SetupHostCandidateVerifier.BuildWindowsCommandLine(request);
            EmbeddedPackageSource.WriteVerificationEvidence(request.EvidencePath, tree.Package);
            return new SetupHostCandidateRunResult(TimedOut: false, ExitCode: 0);
        });
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(runner);
        StableSetupHostIdentity expected = Identity(tree.CandidatePath);

        VerifiedSetupHostCandidate verified = verifier.VerifyStagedCandidate(
            tree.CandidatePath,
            expected,
            tree.TransactionId,
            tree.Package);

        SetupHostCandidateRunRequest request = runner.LastRequest!;
        Assert.Multiple(() =>
        {
            Assert.That(evidenceWasNew, Is.True);
            Assert.That(request.ApplicationPath, Is.EqualTo(tree.CandidatePath));
            Assert.That(request.WorkingDirectory, Is.EqualTo(tree.CandidateDirectory));
            Assert.That(Path.GetDirectoryName(request.EvidencePath), Is.EqualTo(tree.CandidateDirectory));
            Assert.That(
                Path.GetFileName(request.EvidencePath),
                Is.EqualTo($".baxy-setup-verify-{tree.TransactionId}.json"));
            Assert.That(
                request.Arguments,
                Is.EqualTo(new[] { "--verify-embedded", "--evidence", request.EvidencePath }));
            Assert.That(request.TransactionId, Is.EqualTo(tree.TransactionId));
            Assert.That(request.ExpectedIdentity, Is.EqualTo(expected));
            Assert.That(request.InheritHandles, Is.False);
            Assert.That(
                request.CreationFlags,
                Is.EqualTo(SetupHostCandidateVerifier.RequiredCreationFlags));
            Assert.That(
                request.TimeoutMilliseconds,
                Is.EqualTo(SetupHostCandidateVerifier.RequiredTimeoutMilliseconds));
            Assert.That(
                observedCommandLine,
                Is.EqualTo(
                    $"\"{tree.CandidatePath}\" --verify-embedded --evidence " +
                    $"\"{request.EvidencePath}\""));
            Assert.That(verified.ApplicationPath, Is.EqualTo(tree.CandidatePath));
            Assert.That(verified.Identity, Is.EqualTo(expected));
            Assert.That(verified.Evidence.ApplicationPath, Is.EqualTo(tree.CandidatePath));
            Assert.That(verified.Evidence.TransactionId, Is.EqualTo(tree.TransactionId));
            Assert.That(verified.Evidence.Path, Is.EqualTo(request.EvidencePath));
            Assert.That(verified.Evidence.Identity.Bytes, Is.GreaterThan(0));
            Assert.That(verified.Evidence.Identity.Sha256, Does.Match("^[0-9a-f]{64}$"));
            Assert.That(File.Exists(verified.Evidence.Path), Is.True);
        });

        Assert.That(
            SetupHostCandidateVerifier.DeleteVerifiedEvidence(verified.Evidence, tree.Package),
            Is.True);
        Assert.That(
            SetupHostCandidateVerifier.DeleteVerifiedEvidence(verified.Evidence, tree.Package),
            Is.False);
    }

    [Test]
    public void VerifyStagedCandidate_RetryReusesOnlyExactCanonicalTransactionEvidence()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        SetupHostCandidateVerifier firstVerifier = tree.CreateVerifier(SuccessfulRunner(tree));
        StableSetupHostIdentity expected = Identity(tree.CandidatePath);
        VerifiedSetupHostCandidate first = firstVerifier.VerifyStagedCandidate(
            tree.CandidatePath,
            expected,
            tree.TransactionId,
            tree.Package);
        byte[] evidenceBytes = File.ReadAllBytes(first.Evidence.Path);
        RecordingRunner retryRunner = new(_ =>
            throw new InvalidOperationException("A recovered verification must not rerun the child."));
        SetupHostCandidateVerifier retryVerifier = tree.CreateVerifier(retryRunner);

        VerifiedSetupHostCandidate recovered = retryVerifier.VerifyStagedCandidate(
            tree.CandidatePath,
            expected,
            tree.TransactionId,
            tree.Package);

        Assert.Multiple(() =>
        {
            Assert.That(retryRunner.InvocationCount, Is.Zero);
            Assert.That(recovered, Is.EqualTo(first));
            Assert.That(File.ReadAllBytes(recovered.Evidence.Path), Is.EqualTo(evidenceBytes));
        });
        Assert.That(
            SetupHostCandidateVerifier.DeleteVerifiedEvidence(recovered.Evidence, tree.Package),
            Is.True);
    }

    [Test]
    public void RecoverVerifiedEvidenceIfPresent_MissingIsReadOnlyAndDoesNotRunChild()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        RecordingRunner runner = new(_ =>
            throw new InvalidOperationException("Read-only evidence recovery must not run a child."));
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(runner);

        VerifiedSetupHostEvidence? evidence = verifier.RecoverVerifiedEvidenceIfPresent(
            tree.CandidatePath,
            Identity(tree.CandidatePath),
            tree.TransactionId,
            tree.Package);

        Assert.Multiple(() =>
        {
            Assert.That(evidence, Is.Null);
            Assert.That(runner.InvocationCount, Is.Zero);
            Assert.That(
                Directory.GetFileSystemEntries(tree.CandidateDirectory),
                Is.EqualTo(new[] { tree.CandidatePath }));
        });
    }

    [Test]
    public void RecoverVerifiedEvidenceIfPresent_ReattestsExactEvidenceAfterCandidateIsPublished()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        SetupHostCandidateVerifier creator = tree.CreateVerifier(SuccessfulRunner(tree));
        StableSetupHostIdentity identity = Identity(tree.CandidatePath);
        VerifiedSetupHostCandidate created = creator.VerifyStagedCandidate(
            tree.CandidatePath,
            identity,
            tree.TransactionId,
            tree.Package);
        string stable = Path.Combine(tree.CandidateDirectory, "Baxy.Setup.exe");
        File.Move(tree.CandidatePath, stable);
        RecordingRunner runner = new(_ =>
            throw new InvalidOperationException("Read-only evidence recovery must not run a child."));
        SetupHostCandidateVerifier recovery = tree.CreateVerifier(runner);

        VerifiedSetupHostEvidence? recovered = recovery.RecoverVerifiedEvidenceIfPresent(
            stable,
            identity,
            tree.TransactionId,
            tree.Package);

        Assert.Multiple(() =>
        {
            Assert.That(recovered, Is.Not.Null);
            Assert.That(recovered!.ApplicationPath, Is.EqualTo(stable));
            Assert.That(recovered.TransactionId, Is.EqualTo(tree.TransactionId));
            Assert.That(recovered.Path, Is.EqualTo(created.Evidence.Path));
            Assert.That(recovered.Identity, Is.EqualTo(created.Evidence.Identity));
            Assert.That(runner.InvocationCount, Is.Zero);
        });
        Assert.That(
            SetupHostCandidateVerifier.DeleteVerifiedEvidence(recovered!, tree.Package),
            Is.True);
    }

    [Test]
    public void RecoverVerifiedEvidenceIfPresent_RejectsAndPreservesForeignEntryWithoutRunning()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        string evidencePath = Path.Combine(
            tree.CandidateDirectory,
            $".baxy-setup-verify-{tree.TransactionId}.json");
        byte[] foreign = [0x66, 0x6f, 0x72, 0x65, 0x69, 0x67, 0x6e];
        File.WriteAllBytes(evidencePath, foreign);
        RecordingRunner runner = new(_ =>
            throw new InvalidOperationException("Foreign evidence must not run a child."));
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(runner);

        Assert.That(
            () => verifier.RecoverVerifiedEvidenceIfPresent(
                tree.CandidatePath,
                Identity(tree.CandidatePath),
                tree.TransactionId,
                tree.Package),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.Multiple(() =>
        {
            Assert.That(runner.InvocationCount, Is.Zero);
            Assert.That(File.ReadAllBytes(evidencePath), Is.EqualTo(foreign));
        });
    }

    [Test]
    public void VerifyStagedCandidate_RetryPreservesForeignTransactionEvidenceAndDoesNotRun()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        string evidencePath = Path.Combine(
            tree.CandidateDirectory,
            $".baxy-setup-verify-{tree.TransactionId}.json");
        byte[] foreign = [0x66, 0x6f, 0x72, 0x65, 0x69, 0x67, 0x6e];
        File.WriteAllBytes(evidencePath, foreign);
        RecordingRunner runner = new(_ =>
            throw new InvalidOperationException("Foreign recovery evidence must prevent execution."));
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(runner);

        Assert.That(
            () => verifier.VerifyStagedCandidate(
                tree.CandidatePath,
                Identity(tree.CandidatePath),
                tree.TransactionId,
                tree.Package),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(runner.InvocationCount, Is.Zero);
            Assert.That(File.ReadAllBytes(evidencePath), Is.EqualTo(foreign));
        });
    }

    [Test]
    public void VerifyStagedCandidate_RejectsNoncanonicalTransactionIdsBeforeRunning()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        RecordingRunner runner = new(_ => throw new InvalidOperationException("Must not run."));
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(runner);
        StableSetupHostIdentity expected = Identity(tree.CandidatePath);
        string[] invalid =
        [
            string.Empty,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("N").ToUpperInvariant(),
            new string('z', 32),
        ];

        Assert.Multiple(() =>
        {
            foreach (string transactionId in invalid)
            {
                Assert.That(
                    () => verifier.VerifyStagedCandidate(
                        tree.CandidatePath,
                        expected,
                        transactionId,
                        tree.Package),
                    Throws.TypeOf<InstallationSafetyException>(),
                    transactionId);
            }
        });
        Assert.That(runner.InvocationCount, Is.Zero);
    }

    [Test]
    public void VerifyStagedCandidate_NonzeroExitPreservesUntrustedEvidence()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        byte[] foreign = [0x42, 0x41, 0x58, 0x59];
        RecordingRunner runner = new(request =>
        {
            File.WriteAllBytes(request.EvidencePath, foreign);
            return new SetupHostCandidateRunResult(TimedOut: false, ExitCode: 30);
        });
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(runner);

        Assert.That(
            () => verifier.VerifyStagedCandidate(
                tree.CandidatePath,
                Identity(tree.CandidatePath),
                tree.TransactionId,
                tree.Package),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(
            File.ReadAllBytes(runner.LastRequest!.EvidencePath),
            Is.EqualTo(foreign));
    }

    [Test]
    public void VerifyStagedCandidate_TimeoutPreservesUntrustedEvidenceAndUsesBoundedRequest()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        byte[] foreign = [0x74, 0x69, 0x6d, 0x65, 0x6f, 0x75, 0x74];
        RecordingRunner runner = new(request =>
        {
            File.WriteAllBytes(request.EvidencePath, foreign);
            return new SetupHostCandidateRunResult(TimedOut: true, ExitCode: 0xba710001);
        });
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(runner);

        Assert.That(
            () => verifier.VerifyStagedCandidate(
                tree.CandidatePath,
                Identity(tree.CandidatePath),
                tree.TransactionId,
                tree.Package),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(
                runner.LastRequest!.TimeoutMilliseconds,
                Is.EqualTo(120_000));
            Assert.That(
                File.ReadAllBytes(runner.LastRequest.EvidencePath),
                Is.EqualTo(foreign));
        });
    }

    [Test]
    public void VerifyStagedCandidate_ZeroExitWithoutEvidenceFailsClosed()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        RecordingRunner runner = new(_ =>
            new SetupHostCandidateRunResult(TimedOut: false, ExitCode: 0));
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(runner);

        Assert.That(
            () => verifier.VerifyStagedCandidate(
                tree.CandidatePath,
                Identity(tree.CandidatePath),
                tree.TransactionId,
                tree.Package),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(FileSystemEntryExists(runner.LastRequest!.EvidencePath), Is.False);
    }

    [TestCase(EvidenceFault.MalformedJson)]
    [TestCase(EvidenceFault.Utf8Bom)]
    [TestCase(EvidenceFault.CrLf)]
    [TestCase(EvidenceFault.PropertyOrder)]
    [TestCase(EvidenceFault.WrongSchema)]
    [TestCase(EvidenceFault.WrongStatus)]
    [TestCase(EvidenceFault.WrongVersion)]
    [TestCase(EvidenceFault.WrongDataSchema)]
    [TestCase(EvidenceFault.WrongPackageSha256)]
    [TestCase(EvidenceFault.WrongPackageBytes)]
    [TestCase(EvidenceFault.WrongManifestSha256)]
    [TestCase(EvidenceFault.WrongContentId)]
    [TestCase(EvidenceFault.WrongSourceDateEpoch)]
    [TestCase(EvidenceFault.WrongCommit)]
    [TestCase(EvidenceFault.Oversized)]
    public void VerifyStagedCandidate_RejectsAndPreservesMalformedOrMismatchedEvidence(
        EvidenceFault fault)
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        byte[] written = CreateFaultedEvidence(tree.Package, fault);
        RecordingRunner runner = new(request =>
        {
            File.WriteAllBytes(request.EvidencePath, written);
            return new SetupHostCandidateRunResult(TimedOut: false, ExitCode: 0);
        });
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(runner);

        Assert.That(
            () => verifier.VerifyStagedCandidate(
                tree.CandidatePath,
                Identity(tree.CandidatePath),
                tree.TransactionId,
                tree.Package),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(
            File.ReadAllBytes(runner.LastRequest!.EvidencePath),
            Is.EqualTo(written));
    }

    [Test]
    public void VerifyStagedCandidate_ReReadDetectsEvidenceTamperingAndPreservesNewBytes()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        byte[] tampered = Encoding.UTF8.GetBytes("{\"foreign\":true}\n");
        RecordingRunner runner = new(request =>
        {
            EmbeddedPackageSource.WriteVerificationEvidence(request.EvidencePath, tree.Package);
            return new SetupHostCandidateRunResult(TimedOut: false, ExitCode: 0);
        });
        EvidenceMutationFaultInjector injector = new(path =>
            File.WriteAllBytes(path, tampered));
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(runner, injector);

        Assert.That(
            () => verifier.VerifyStagedCandidate(
                tree.CandidatePath,
                Identity(tree.CandidatePath),
                tree.TransactionId,
                tree.Package),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(
            File.ReadAllBytes(runner.LastRequest!.EvidencePath),
            Is.EqualTo(tampered));
    }

    [Test]
    public void VerifyStagedCandidate_DetectsCandidateMutationAndPreservesBothArtifacts()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        byte[] tamperedCandidate = [0x4d, 0x5a, 0x99];
        RecordingRunner runner = new(request =>
        {
            EmbeddedPackageSource.WriteVerificationEvidence(request.EvidencePath, tree.Package);
            File.WriteAllBytes(request.ApplicationPath, tamperedCandidate);
            return new SetupHostCandidateRunResult(TimedOut: false, ExitCode: 0);
        });
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(runner);
        StableSetupHostIdentity original = Identity(tree.CandidatePath);

        Assert.That(
            () => verifier.VerifyStagedCandidate(
                tree.CandidatePath,
                original,
                tree.TransactionId,
                tree.Package),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(File.ReadAllBytes(tree.CandidatePath), Is.EqualTo(tamperedCandidate));
            Assert.That(File.Exists(runner.LastRequest!.EvidencePath), Is.True);
        });
    }

    [Test]
    public void VerifyStagedCandidate_RejectsUnsafeApplicationPathsBeforeInvokingRunner()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        RecordingRunner runner = new(_ => throw new InvalidOperationException("Must not run."));
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(runner);
        StableSetupHostIdentity expected = Identity(tree.CandidatePath);

        Assert.Multiple(() =>
        {
            Assert.That(
                () => verifier.VerifyStagedCandidate(
                    "relative.exe",
                    expected,
                    tree.TransactionId,
                    tree.Package),
                Throws.TypeOf<InstallationSafetyException>());
            Assert.That(
                () => verifier.VerifyStagedCandidate(
                    Path.Combine(tree.Root, "missing.exe"),
                    expected,
                    tree.TransactionId,
                    tree.Package),
                Throws.TypeOf<InstallationSafetyException>());
        });
        Assert.That(runner.InvocationCount, Is.Zero);
    }

    [Test]
    public void VerifyStagedCandidate_RejectsAHardLinkedApplicationBeforeInvokingRunner()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        StableSetupHostIdentity expected = Identity(tree.CandidatePath);
        string alias = Path.Combine(tree.Root, "candidate-alias.exe");
        Assert.That(CreateHardLink(alias, tree.CandidatePath, 0), Is.True);
        RecordingRunner runner = new(_ => throw new InvalidOperationException("Must not run."));
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(runner);

        Assert.That(
            () => verifier.VerifyStagedCandidate(
                tree.CandidatePath,
                expected,
                tree.TransactionId,
                tree.Package),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.Multiple(() =>
        {
            Assert.That(runner.InvocationCount, Is.Zero);
            Assert.That(File.Exists(tree.CandidatePath), Is.True);
            Assert.That(File.Exists(alias), Is.True);
        });
    }

    [Test]
    public void VerifyStagedCandidate_RejectsWrongExpectedIdentityBeforeInvokingRunner()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        RecordingRunner runner = new(_ => throw new InvalidOperationException("Must not run."));
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(runner);
        StableSetupHostIdentity wrong = Identity(tree.CandidatePath) with
        {
            Sha256 = new string('0', 64),
        };

        Assert.That(
            () => verifier.VerifyStagedCandidate(
                tree.CandidatePath,
                wrong,
                tree.TransactionId,
                tree.Package),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(runner.InvocationCount, Is.Zero);
    }

    [Test]
    public void VerifyStagedCandidate_RejectsUnsafeEvidenceEntriesAndPreservesThem()
    {
        using CandidateTestTree adsTree = CandidateTestTree.Create();
        RecordingRunner adsRunner = new(request =>
        {
            EmbeddedPackageSource.WriteVerificationEvidence(request.EvidencePath, adsTree.Package);
            File.WriteAllText(request.EvidencePath + ":foreign", "foreign");
            return new SetupHostCandidateRunResult(TimedOut: false, ExitCode: 0);
        });
        SetupHostCandidateVerifier adsVerifier = adsTree.CreateVerifier(adsRunner);
        Assert.That(
            () => adsVerifier.VerifyStagedCandidate(
                adsTree.CandidatePath,
                Identity(adsTree.CandidatePath),
                adsTree.TransactionId,
                adsTree.Package),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(
            File.ReadAllText(adsRunner.LastRequest!.EvidencePath + ":foreign"),
            Is.EqualTo("foreign"));

        using CandidateTestTree hardLinkTree = CandidateTestTree.Create();
        string? hardLinkAlias = null;
        RecordingRunner hardLinkRunner = new(request =>
        {
            EmbeddedPackageSource.WriteVerificationEvidence(
                request.EvidencePath,
                hardLinkTree.Package);
            hardLinkAlias = Path.Combine(hardLinkTree.Root, "evidence-alias.json");
            Assert.That(CreateHardLink(hardLinkAlias, request.EvidencePath, 0), Is.True);
            return new SetupHostCandidateRunResult(TimedOut: false, ExitCode: 0);
        });
        SetupHostCandidateVerifier hardLinkVerifier = hardLinkTree.CreateVerifier(hardLinkRunner);
        Assert.That(
            () => hardLinkVerifier.VerifyStagedCandidate(
                hardLinkTree.CandidatePath,
                Identity(hardLinkTree.CandidatePath),
                hardLinkTree.TransactionId,
                hardLinkTree.Package),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(hardLinkRunner.LastRequest!.EvidencePath), Is.True);
            Assert.That(File.Exists(hardLinkAlias), Is.True);
        });
    }

    [Test]
    public void DeleteVerifiedEvidence_RejectsChangedBytesAndPreservesThem()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        RecordingRunner runner = SuccessfulRunner(tree);
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(runner);
        VerifiedSetupHostCandidate verified = verifier.VerifyStagedCandidate(
            tree.CandidatePath,
            Identity(tree.CandidatePath),
            tree.TransactionId,
            tree.Package);
        byte[] foreign = [0x66, 0x6f, 0x72, 0x65, 0x69, 0x67, 0x6e];
        File.WriteAllBytes(verified.Evidence.Path, foreign);

        Assert.That(
            () => SetupHostCandidateVerifier.DeleteVerifiedEvidence(
                verified.Evidence,
                tree.Package),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(File.ReadAllBytes(verified.Evidence.Path), Is.EqualTo(foreign));
    }

    [Test]
    public void DeleteVerifiedEvidence_RequiresMatchingParentAndASingleLinkBeforeDeletion()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        SetupHostCandidateVerifier verifier = tree.CreateVerifier(SuccessfulRunner(tree));
        VerifiedSetupHostCandidate verified = verifier.VerifyStagedCandidate(
            tree.CandidatePath,
            Identity(tree.CandidatePath),
            tree.TransactionId,
            tree.Package);
        using MemoryStream foreignStream = TestProductPackageFactory.Open(
            TestProductPackageFactory.Create(salt: "foreign"));
        VerifiedProductPackage foreignPackage = new ProductPackageVerifier().Verify(foreignStream);

        Assert.That(
            () => SetupHostCandidateVerifier.DeleteVerifiedEvidence(
                verified.Evidence,
                foreignPackage),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.That(File.Exists(verified.Evidence.Path), Is.True);

        string alias = Path.Combine(tree.Root, "verified-evidence-alias.json");
        Assert.That(CreateHardLink(alias, verified.Evidence.Path, 0), Is.True);
        Assert.That(
            () => SetupHostCandidateVerifier.DeleteVerifiedEvidence(
                verified.Evidence,
                tree.Package),
            Throws.TypeOf<InstallationSafetyException>());
        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(verified.Evidence.Path), Is.True);
            Assert.That(File.Exists(alias), Is.True);
        });

        File.Delete(alias);
        Assert.That(
            SetupHostCandidateVerifier.DeleteVerifiedEvidence(
                verified.Evidence,
                tree.Package),
            Is.True);
    }

    [Test]
    public void DeleteVerifiedEvidence_RejectsAForgedNonOwnedPathWithoutDeleting()
    {
        using CandidateTestTree tree = CandidateTestTree.Create();
        string foreignPath = Path.Combine(tree.CandidateDirectory, "foreign.json");
        byte[] foreign = [0x01, 0x02, 0x03];
        File.WriteAllBytes(foreignPath, foreign);
        VerifiedSetupHostEvidence forged = new(
            tree.CandidatePath,
            tree.TransactionId,
            foreignPath,
            new StableSetupHostIdentity(Sha256(foreign), foreign.LongLength));

        Assert.That(
            () => SetupHostCandidateVerifier.DeleteVerifiedEvidence(forged, tree.Package),
            Throws.TypeOf<InstallationSafetyException>());

        Assert.That(File.ReadAllBytes(foreignPath), Is.EqualTo(foreign));
    }

    private static RecordingRunner SuccessfulRunner(CandidateTestTree tree) => new(request =>
    {
        EmbeddedPackageSource.WriteVerificationEvidence(request.EvidencePath, tree.Package);
        return new SetupHostCandidateRunResult(TimedOut: false, ExitCode: 0);
    });

    private static byte[] CreateFaultedEvidence(
        VerifiedProductPackage package,
        EvidenceFault fault)
    {
        if (fault == EvidenceFault.MalformedJson)
        {
            return Encoding.UTF8.GetBytes("{\"schema\":\n");
        }

        if (fault == EvidenceFault.Oversized)
        {
            return Enumerable.Repeat((byte)'x', 4097).ToArray();
        }

        EmbeddedVerificationEvidence evidence = new()
        {
            Schema = fault == EvidenceFault.WrongSchema
                ? "foreign-schema"
                : PackageContract.EmbeddedVerificationEvidenceSchema,
            Status = fault == EvidenceFault.WrongStatus ? "failed" : "passed",
            Version = fault == EvidenceFault.WrongVersion ? "9.9.9" : package.Version,
            DataSchema = fault == EvidenceFault.WrongDataSchema
                ? package.DataSchema + 1
                : package.DataSchema,
            PackageSha256 = fault == EvidenceFault.WrongPackageSha256
                ? new string('0', 64)
                : package.PackageSha256,
            PackageBytes = fault == EvidenceFault.WrongPackageBytes
                ? package.PackageLength + 1
                : package.PackageLength,
            ManifestSha256 = fault == EvidenceFault.WrongManifestSha256
                ? new string('0', 64)
                : package.ManifestSha256,
            ContentId = fault == EvidenceFault.WrongContentId
                ? new string('0', 64)
                : package.ContentId,
            SourceDateEpoch = fault == EvidenceFault.WrongSourceDateEpoch
                ? package.SourceDateEpoch + 1
                : package.SourceDateEpoch,
            Commit = fault == EvidenceFault.WrongCommit
                ? new string('0', 40)
                : package.Commit,
        };
        byte[] json = JsonSerializer.SerializeToUtf8Bytes(
            evidence,
            SetupJsonContext.Default.EmbeddedVerificationEvidence);
        byte[] canonical = [.. json, (byte)'\n'];
        return fault switch
        {
            EvidenceFault.Utf8Bom => [0xef, 0xbb, 0xbf, .. canonical],
            EvidenceFault.CrLf => [.. canonical.AsSpan(0, canonical.Length - 1), (byte)'\r', (byte)'\n'],
            EvidenceFault.PropertyOrder => SwapFirstProperties(canonical),
            _ => canonical,
        };
    }

    private static byte[] SwapFirstProperties(byte[] canonical)
    {
        string source = Encoding.UTF8.GetString(canonical);
        string schema = $"\"schema\":\"{PackageContract.EmbeddedVerificationEvidenceSchema}\"";
        string expectedPrefix = $"{{{schema},\"status\":\"passed\",";
        string replacement = $"{{\"status\":\"passed\",{schema},";
        string swapped = source.Replace(expectedPrefix, replacement, StringComparison.Ordinal);
        if (string.Equals(source, swapped, StringComparison.Ordinal))
        {
            throw new InvalidOperationException("The evidence property-order fixture did not match.");
        }

        return Encoding.UTF8.GetBytes(swapped);
    }

    private static StableSetupHostIdentity Identity(string path)
    {
        byte[] bytes = File.ReadAllBytes(path);
        return new StableSetupHostIdentity(Sha256(bytes), bytes.LongLength);
    }

    private static string Sha256(byte[] bytes) =>
        Convert.ToHexStringLower(SHA256.HashData(bytes));

    private static bool FileSystemEntryExists(string path)
    {
        try
        {
            _ = File.GetAttributes(path);
            return true;
        }
        catch (FileNotFoundException)
        {
            return false;
        }
        catch (DirectoryNotFoundException)
        {
            return false;
        }
    }

    private sealed class FixedProcessPathProvider(string? path) : ISetupHostProcessPathProvider
    {
        public string? GetProcessPath() => path;
    }

    private sealed class RecordingRunner(
        Func<SetupHostCandidateRunRequest, SetupHostCandidateRunResult> action) :
        ISetupHostCandidateRunner
    {
        internal SetupHostCandidateRunRequest? LastRequest { get; private set; }

        internal int InvocationCount { get; private set; }

        public SetupHostCandidateRunResult Run(SetupHostCandidateRunRequest request)
        {
            InvocationCount++;
            LastRequest = request;
            return action(request);
        }
    }

    private sealed class UnexpectedRunner : ISetupHostCandidateRunner
    {
        public SetupHostCandidateRunResult Run(SetupHostCandidateRunRequest request) =>
            throw new InvalidOperationException("The process runner was not expected.");
    }

    private sealed class EvidenceMutationFaultInjector(Action<string> mutation) :
        ISetupHostCandidateVerifierFaultInjector
    {
        public void Checkpoint(SetupHostCandidateVerifierFaultPoint point, string path)
        {
            Assert.That(
                point,
                Is.EqualTo(SetupHostCandidateVerifierFaultPoint.FirstEvidenceReadComplete));
            mutation(path);
        }
    }

    public enum EvidenceFault
    {
        MalformedJson,
        Utf8Bom,
        CrLf,
        PropertyOrder,
        WrongSchema,
        WrongStatus,
        WrongVersion,
        WrongDataSchema,
        WrongPackageSha256,
        WrongPackageBytes,
        WrongManifestSha256,
        WrongContentId,
        WrongSourceDateEpoch,
        WrongCommit,
        Oversized,
    }

    private sealed class CandidateTestTree : IDisposable
    {
        private CandidateTestTree(
            string root,
            string sourcePath,
            string candidateDirectory,
            string candidatePath,
            string transactionId,
            VerifiedProductPackage package)
        {
            Root = root;
            SourcePath = sourcePath;
            CandidateDirectory = candidateDirectory;
            CandidatePath = candidatePath;
            TransactionId = transactionId;
            Package = package;
        }

        internal string Root { get; }

        internal string SourcePath { get; }

        internal string CandidateDirectory { get; }

        internal string CandidatePath { get; }

        internal string TransactionId { get; }

        internal VerifiedProductPackage Package { get; }

        internal static CandidateTestTree Create()
        {
            string root = Path.Combine(
                Path.GetTempPath(),
                $"baxy-host-candidate-{Guid.NewGuid():N}",
                "área ñ 漢字");
            string sourceDirectory = Path.Combine(root, "entrega actual");
            string candidateDirectory = Path.Combine(root, "programa estable");
            Directory.CreateDirectory(sourceDirectory);
            Directory.CreateDirectory(candidateDirectory);
            string source = Path.Combine(sourceDirectory, "Baxy.Setup entrega ñ 漢字.exe");
            string candidate = Path.Combine(candidateDirectory, "Baxy.Setup.next.exe");
            byte[] executable = [0x4d, 0x5a, 0x01, 0x02, 0x03, 0x04];
            File.WriteAllBytes(source, executable);
            File.WriteAllBytes(candidate, executable);
            using MemoryStream packageStream = TestProductPackageFactory.Open(
                TestProductPackageFactory.Create());
            VerifiedProductPackage package = new ProductPackageVerifier().Verify(packageStream);
            return new CandidateTestTree(
                root,
                source,
                candidateDirectory,
                candidate,
                Guid.NewGuid().ToString("N"),
                package);
        }

        internal SetupHostCandidateVerifier CreateVerifier(
            ISetupHostCandidateRunner runner,
            ISetupHostCandidateVerifierFaultInjector? faultInjector = null) =>
            new(
                new FixedProcessPathProvider(SourcePath),
                runner,
                faultInjector);

        public void Dispose()
        {
            string? outer = Directory.GetParent(Root)?.FullName;
            if (outer is not null && Directory.Exists(outer))
            {
                Directory.Delete(outer, recursive: true);
            }
        }
    }

    [DllImport(
        "kernel32.dll",
        EntryPoint = "CreateHardLinkW",
        CharSet = CharSet.Unicode,
        SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CreateHardLink(
        string fileName,
        string existingFileName,
        nint securityAttributes);
}
