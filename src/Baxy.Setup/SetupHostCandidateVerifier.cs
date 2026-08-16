using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;
using Microsoft.Win32.SafeHandles;

namespace Baxy.Setup;

internal sealed record CapturedSetupHost(
    string Path,
    StableSetupHostIdentity Identity);

internal sealed record VerifiedSetupHostEvidence(
    string ApplicationPath,
    string TransactionId,
    string Path,
    StableSetupHostIdentity Identity);

internal sealed record VerifiedSetupHostCandidate(
    string ApplicationPath,
    StableSetupHostIdentity Identity,
    VerifiedSetupHostEvidence Evidence);

internal sealed record SetupHostCandidateRunRequest(
    string ApplicationPath,
    string WorkingDirectory,
    string EvidencePath,
    string TransactionId,
    IReadOnlyList<string> Arguments,
    StableSetupHostIdentity ExpectedIdentity,
    bool InheritHandles,
    uint CreationFlags,
    uint TimeoutMilliseconds);

internal sealed record SetupHostCandidateRunResult(
    bool TimedOut,
    uint ExitCode);

internal interface ISetupHostProcessPathProvider
{
    string? GetProcessPath();
}

internal interface ISetupHostCandidateRunner
{
    SetupHostCandidateRunResult Run(SetupHostCandidateRunRequest request);
}

internal enum SetupHostCandidateVerifierFaultPoint
{
    FirstEvidenceReadComplete,
}

internal interface ISetupHostCandidateVerifierFaultInjector
{
    void Checkpoint(SetupHostCandidateVerifierFaultPoint point, string path);
}

internal sealed class EnvironmentSetupHostProcessPathProvider : ISetupHostProcessPathProvider
{
    public string? GetProcessPath() => Environment.ProcessPath;
}

internal sealed partial class SetupHostCandidateVerifier
{
    internal const uint RequiredCreationFlags = 0x00000400;
    internal const uint RequiredTimeoutMilliseconds = 120_000;

    private const int IdentityBufferSize = 1024 * 1024;
    private const int MaximumEvidenceBytes = 4096;
    private const int MaximumWindowsCommandLineCharacters = 32_767;
    private const string EvidencePrefix = ".baxy-setup-verify-";
    private const string EvidenceSuffix = ".json";

    private static readonly string[] VerificationArgumentsPrefix =
    [
        "--verify-embedded",
        "--evidence",
    ];

    private readonly ISetupHostProcessPathProvider processPathProvider;
    private readonly ISetupHostCandidateRunner runner;
    private readonly ISetupHostCandidateVerifierFaultInjector? faultInjector;

    internal SetupHostCandidateVerifier()
        : this(
            new EnvironmentSetupHostProcessPathProvider(),
            new WindowsSetupHostCandidateRunner())
    {
    }

    internal SetupHostCandidateVerifier(
        ISetupHostProcessPathProvider processPathProvider,
        ISetupHostCandidateRunner runner,
        ISetupHostCandidateVerifierFaultInjector? faultInjector = null)
    {
        this.processPathProvider = processPathProvider ??
            throw new ArgumentNullException(nameof(processPathProvider));
        this.runner = runner ?? throw new ArgumentNullException(nameof(runner));
        this.faultInjector = faultInjector;
    }

    internal CapturedSetupHost CaptureCurrentHost()
    {
        string path = ValidateExistingApplication(
            processPathProvider.GetProcessPath(),
            "current Setup process path");
        StableSetupHostIdentity identity = ReadStableIdentity(
            path,
            "current Setup process");
        return new CapturedSetupHost(path, identity);
    }

    internal VerifiedSetupHostCandidate VerifyStagedCandidate(
        string applicationPath,
        StableSetupHostIdentity expectedIdentity,
        string transactionId,
        VerifiedProductPackage parentPackage)
    {
        ArgumentNullException.ThrowIfNull(parentPackage);
        string validatedTransactionId = ValidateTransactionId(transactionId);
        string application = ValidateExistingApplication(
            applicationPath,
            "staged Setup candidate path");
        StableSetupHostManager.VerifyExact(application, expectedIdentity);
        StableSetupHostIdentity before = ReadStableIdentity(
            application,
            "staged Setup candidate");
        RequireIdentity(before, expectedIdentity, "staged Setup candidate");

        string workingDirectory = Path.GetDirectoryName(application)!;
        string evidencePath = GetEvidencePath(workingDirectory, validatedTransactionId);
        if (FileSystemEntryExists(evidencePath))
        {
            VerifiedSetupHostEvidence recoveredEvidence = ReadAndVerifyEvidence(
                application,
                validatedTransactionId,
                evidencePath,
                parentPackage);
            StableSetupHostManager.VerifyExact(application, expectedIdentity);
            StableSetupHostIdentity recoveredCandidate = ReadStableIdentity(
                application,
                "recovered staged Setup candidate");
            RequireIdentity(
                recoveredCandidate,
                before,
                "recovered staged Setup candidate");
            return new VerifiedSetupHostCandidate(
                application,
                recoveredCandidate,
                recoveredEvidence);
        }

        SetupHostCandidateRunRequest request = new(
            application,
            workingDirectory,
            evidencePath,
            validatedTransactionId,
            [VerificationArgumentsPrefix[0], VerificationArgumentsPrefix[1], evidencePath],
            expectedIdentity,
            InheritHandles: false,
            RequiredCreationFlags,
            RequiredTimeoutMilliseconds);

        SetupHostCandidateRunResult result;
        try
        {
            result = runner.Run(request) ??
                throw new InstallationSafetyException(
                    "The Setup candidate runner returned no result.");
        }
        catch (InstallationSafetyException)
        {
            throw;
        }
        catch (Exception exception) when (
            exception is ArgumentException or IOException or InvalidOperationException or
            UnauthorizedAccessException or Win32Exception)
        {
            throw new InstallationSafetyException(
                "The staged Setup candidate could not execute its embedded verification mode.",
                exception);
        }

        if (result.TimedOut)
        {
            throw new InstallationSafetyException(
                "The staged Setup candidate timed out during embedded verification.");
        }

        if (result.ExitCode != 0)
        {
            throw new InstallationSafetyException(
                $"The staged Setup candidate rejected embedded verification with exit code {result.ExitCode}.");
        }

        StableSetupHostManager.VerifyExact(application, expectedIdentity);
        StableSetupHostIdentity after = ReadStableIdentity(
            application,
            "staged Setup candidate after verification");
        RequireIdentity(after, before, "staged Setup candidate after verification");

        VerifiedSetupHostEvidence evidence = ReadAndVerifyEvidence(
            application,
            validatedTransactionId,
            evidencePath,
            parentPackage);
        return new VerifiedSetupHostCandidate(application, after, evidence);
    }

    internal static bool DeleteVerifiedEvidence(
        VerifiedSetupHostEvidence evidence,
        VerifiedProductPackage parentPackage)
    {
        ArgumentNullException.ThrowIfNull(evidence);
        ArgumentNullException.ThrowIfNull(parentPackage);
        string application = ValidateApplicationSyntax(
            evidence.ApplicationPath,
            "verified Setup candidate application path");
        string transactionId = ValidateTransactionId(evidence.TransactionId);
        string path = ValidateEvidencePath(evidence.Path, application, transactionId);
        if (!FileSystemEntryExists(path))
        {
            return false;
        }

        StableSetupHostIdentity actual = ReadAndVerifyEvidenceIdentity(
            path,
            parentPackage,
            faultInjector: null);
        RequireIdentity(actual, evidence.Identity, "verified Setup evidence");
        DeleteEvidenceByLockedHandle(path, evidence.Identity, parentPackage);
        if (FileSystemEntryExists(path))
        {
            throw new InstallationSafetyException(
                "The exact verified Setup evidence remained after deletion.");
        }

        return true;
    }

    internal VerifiedSetupHostEvidence? RecoverVerifiedEvidenceIfPresent(
        string applicationPath,
        StableSetupHostIdentity expectedIdentity,
        string transactionId,
        VerifiedProductPackage parentPackage)
    {
        ArgumentNullException.ThrowIfNull(parentPackage);
        string validatedTransactionId = ValidateTransactionId(transactionId);
        string application = ValidateExistingApplication(
            applicationPath,
            "verified Setup evidence application path");
        StableSetupHostManager.VerifyExact(application, expectedIdentity);
        StableSetupHostIdentity before = ReadStableIdentity(
            application,
            "verified Setup evidence application");
        RequireIdentity(before, expectedIdentity, "verified Setup evidence application");
        string evidencePath = GetEvidencePath(
            Path.GetDirectoryName(application)!,
            validatedTransactionId);
        if (!FileSystemEntryExists(evidencePath))
        {
            return null;
        }

        VerifiedSetupHostEvidence evidence = ReadAndVerifyEvidence(
            application,
            validatedTransactionId,
            evidencePath,
            parentPackage);
        StableSetupHostManager.VerifyExact(application, expectedIdentity);
        StableSetupHostIdentity after = ReadStableIdentity(
            application,
            "verified Setup evidence application after recovery");
        RequireIdentity(after, before, "verified Setup evidence application after recovery");
        return evidence;
    }

    internal static void ValidateRunnerRequest(SetupHostCandidateRunRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        string application = ValidateExistingApplication(
            request.ApplicationPath,
            "Setup candidate runner application path");
        string workingDirectory = RequireSafeParent(application);
        string transactionId = ValidateTransactionId(request.TransactionId);
        string evidence = ValidateEvidencePath(
            request.EvidencePath,
            application,
            transactionId);
        if (!string.Equals(application, request.ApplicationPath, StringComparison.Ordinal) ||
            !string.Equals(workingDirectory, request.WorkingDirectory, StringComparison.Ordinal) ||
            request.Arguments is not { Count: 3 } ||
            !string.Equals(
                request.Arguments[0],
                VerificationArgumentsPrefix[0],
                StringComparison.Ordinal) ||
            !string.Equals(
                request.Arguments[1],
                VerificationArgumentsPrefix[1],
                StringComparison.Ordinal) ||
            !string.Equals(request.Arguments[2], evidence, StringComparison.Ordinal) ||
            request.InheritHandles ||
            request.CreationFlags != RequiredCreationFlags ||
            request.TimeoutMilliseconds != RequiredTimeoutMilliseconds)
        {
            throw new InstallationSafetyException(
                "The Setup candidate runner request violates its fixed process contract.");
        }

        if (FileSystemEntryExists(evidence))
        {
            throw new InstallationSafetyException(
                "The Setup candidate verification evidence path must still be new.");
        }

        StableSetupHostManager.VerifyExact(application, request.ExpectedIdentity);
    }

    internal static string BuildWindowsCommandLine(SetupHostCandidateRunRequest request)
    {
        ValidateRunnerRequest(request);
        string commandLine =
            $"\"{request.ApplicationPath}\" --verify-embedded --evidence \"{request.EvidencePath}\"";
        if (commandLine.Length + 1 > MaximumWindowsCommandLineCharacters)
        {
            throw new InstallationSafetyException(
                "The Setup candidate verification command line exceeds the reviewed Windows limit.");
        }

        return commandLine;
    }

    private VerifiedSetupHostEvidence ReadAndVerifyEvidence(
        string application,
        string transactionId,
        string evidencePath,
        VerifiedProductPackage parentPackage)
    {
        StableSetupHostIdentity identity = ReadAndVerifyEvidenceIdentity(
            evidencePath,
            parentPackage,
            faultInjector);
        return new VerifiedSetupHostEvidence(
            application,
            transactionId,
            evidencePath,
            identity);
    }

    private static StableSetupHostIdentity ReadAndVerifyEvidenceIdentity(
        string evidencePath,
        VerifiedProductPackage parentPackage,
        ISetupHostCandidateVerifierFaultInjector? faultInjector)
    {
        byte[] first = ReadEvidenceBytes(evidencePath);
        faultInjector?.Checkpoint(
            SetupHostCandidateVerifierFaultPoint.FirstEvidenceReadComplete,
            evidencePath);
        byte[] second = ReadEvidenceBytes(evidencePath);
        if (!first.AsSpan().SequenceEqual(second))
        {
            throw new InstallationSafetyException(
                "The Setup candidate verification evidence changed while being read.");
        }

        EmbeddedVerificationEvidence evidence = ParseCanonicalEvidence(first);
        RequireEvidenceMatchesParent(evidence, parentPackage);
        return new StableSetupHostIdentity(
            Convert.ToHexStringLower(SHA256.HashData(first)),
            first.LongLength);
    }

    private static EmbeddedVerificationEvidence ParseCanonicalEvidence(byte[] bytes)
    {
        if (bytes.Length is <= 0 or > MaximumEvidenceBytes)
        {
            throw new InstallationSafetyException(
                "The Setup candidate verification evidence has an invalid length.");
        }

        if (bytes.Length >= 3 &&
            bytes[0] == 0xef &&
            bytes[1] == 0xbb &&
            bytes[2] == 0xbf)
        {
            throw new InstallationSafetyException(
                "A UTF-8 BOM is forbidden in Setup candidate verification evidence.");
        }

        try
        {
            using JsonDocument document = JsonDocument.Parse(bytes);
            if (document.RootElement.ValueKind != JsonValueKind.Object)
            {
                throw new InstallationSafetyException(
                    "Setup candidate verification evidence must be a JSON object.");
            }

            string[] expectedProperties =
            [
                "schema",
                "status",
                "version",
                "data_schema",
                "package_sha256",
                "package_bytes",
                "manifest_sha256",
                "content_id",
                "source_date_epoch",
                "commit",
            ];
            int propertyIndex = 0;
            foreach (JsonProperty property in document.RootElement.EnumerateObject())
            {
                if (propertyIndex >= expectedProperties.Length ||
                    !string.Equals(
                        property.Name,
                        expectedProperties[propertyIndex],
                        StringComparison.Ordinal))
                {
                    throw new InstallationSafetyException(
                        "The Setup candidate verification evidence property set is non-canonical.");
                }

                propertyIndex++;
            }

            if (propertyIndex != expectedProperties.Length)
            {
                throw new InstallationSafetyException(
                    "The Setup candidate verification evidence property set is incomplete.");
            }

            EmbeddedVerificationEvidence? evidence = JsonSerializer.Deserialize(
                bytes,
                SetupJsonContext.Default.EmbeddedVerificationEvidence);
            if (evidence is null ||
                !string.Equals(
                    evidence.Schema,
                    PackageContract.EmbeddedVerificationEvidenceSchema,
                    StringComparison.Ordinal) ||
                !string.Equals(evidence.Status, "passed", StringComparison.Ordinal))
            {
                throw new InstallationSafetyException(
                    "The Setup candidate verification evidence schema or status is invalid.");
            }

            byte[] canonicalJson = JsonSerializer.SerializeToUtf8Bytes(
                evidence,
                SetupJsonContext.Default.EmbeddedVerificationEvidence);
            if (bytes.Length != canonicalJson.Length + 1 ||
                bytes[^1] != (byte)'\n' ||
                !bytes.AsSpan(0, canonicalJson.Length).SequenceEqual(canonicalJson))
            {
                throw new InstallationSafetyException(
                    "The Setup candidate verification evidence is not canonical UTF-8 JSON with one LF.");
            }

            return evidence;
        }
        catch (InstallationSafetyException)
        {
            throw;
        }
        catch (Exception exception) when (
            exception is JsonException or InvalidOperationException or IOException)
        {
            throw new InstallationSafetyException(
                "The Setup candidate verification evidence is malformed.",
                exception);
        }
    }

    private static void RequireEvidenceMatchesParent(
        EmbeddedVerificationEvidence evidence,
        VerifiedProductPackage parentPackage)
    {
        if (evidence.DataSchema != parentPackage.DataSchema ||
            !string.Equals(evidence.Version, parentPackage.Version, StringComparison.Ordinal) ||
            !string.Equals(
                evidence.PackageSha256,
                parentPackage.PackageSha256,
                StringComparison.Ordinal) ||
            evidence.PackageBytes != parentPackage.PackageLength ||
            !string.Equals(
                evidence.ManifestSha256,
                parentPackage.ManifestSha256,
                StringComparison.Ordinal) ||
            !string.Equals(evidence.ContentId, parentPackage.ContentId, StringComparison.Ordinal) ||
            evidence.SourceDateEpoch != parentPackage.SourceDateEpoch ||
            !string.Equals(evidence.Commit, parentPackage.Commit, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "The Setup candidate verification evidence does not match the parent verified package.");
        }
    }

    private static byte[] ReadEvidenceBytes(string path)
    {
        try
        {
            PathSafety.AssertRegularFile(path);
            using FileStream stream = new(
                path,
                FileMode.Open,
                FileAccess.Read,
                FileShare.Read,
                MaximumEvidenceBytes,
                FileOptions.SequentialScan);
            long length = stream.Length;
            if (length is <= 0 or > MaximumEvidenceBytes)
            {
                throw new InstallationSafetyException(
                    "The Setup candidate verification evidence has an invalid length.");
            }

            byte[] bytes = new byte[checked((int)length)];
            stream.ReadExactly(bytes);
            if (stream.Length != length || stream.ReadByte() != -1)
            {
                throw new InstallationSafetyException(
                    "The Setup candidate verification evidence changed while being read.");
            }

            PathSafety.AssertRegularFile(path);
            return bytes;
        }
        catch (InstallationSafetyException)
        {
            throw;
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException or OverflowException)
        {
            throw new InstallationSafetyException(
                "The Setup candidate verification evidence is not a stable regular file.",
                exception);
        }
    }

    private static StableSetupHostIdentity ReadStableIdentity(string path, string description)
    {
        StableSetupHostIdentity first = ReadIdentityOnce(path, description);
        StableSetupHostIdentity second = ReadIdentityOnce(path, description);
        RequireIdentity(second, first, description);
        return second;
    }

    private static StableSetupHostIdentity ReadIdentityOnce(string path, string description)
    {
        try
        {
            PathSafety.AssertRegularFile(path);
            using FileStream stream = new(
                path,
                FileMode.Open,
                FileAccess.Read,
                FileShare.Read,
                IdentityBufferSize,
                FileOptions.SequentialScan);
            long bytes = stream.Length;
            if (bytes <= 0)
            {
                throw new InstallationSafetyException(
                    $"The {description} must have a positive byte length.");
            }

            string sha256 = Convert.ToHexStringLower(SHA256.HashData(stream));
            if (stream.Length != bytes)
            {
                throw new InstallationSafetyException(
                    $"The {description} byte length changed during hashing.");
            }

            PathSafety.AssertRegularFile(path);
            return new StableSetupHostIdentity(sha256, bytes);
        }
        catch (InstallationSafetyException)
        {
            throw;
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException or
            CryptographicException or OverflowException)
        {
            throw new InstallationSafetyException(
                $"The {description} could not be hashed as a stable regular file.",
                exception);
        }
    }

    private static string ValidateExistingApplication(string? path, string field)
    {
        string fullPath = ValidateApplicationSyntax(path, field);
        _ = RequireSafeParent(fullPath);
        try
        {
            PathSafety.AssertRegularFile(fullPath);
        }
        catch (InstallationSafetyException)
        {
            throw;
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException)
        {
            throw new InstallationSafetyException(
                $"The {field} must be an existing safe regular executable file.",
                exception);
        }

        return fullPath;
    }

    private static string ValidateApplicationSyntax(string? path, string field)
    {
        string fullPath = ValidateAbsolutePath(path, field);
        if (!string.Equals(Path.GetExtension(fullPath), ".exe", StringComparison.OrdinalIgnoreCase))
        {
            throw new InstallationSafetyException($"The {field} must use the .exe extension.");
        }

        return fullPath;
    }

    private static string ValidateEvidencePath(
        string path,
        string application,
        string transactionId)
    {
        string fullPath = ValidateAbsolutePath(path, "Setup candidate verification evidence path");
        string applicationParent = Path.GetDirectoryName(application)!;
        if (!string.Equals(
                Path.GetDirectoryName(fullPath),
                applicationParent,
                StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "Setup candidate verification evidence must be a sibling of the application.");
        }

        string expectedLeaf = $"{EvidencePrefix}{transactionId}{EvidenceSuffix}";
        if (!string.Equals(Path.GetFileName(fullPath), expectedLeaf, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "The Setup candidate verification evidence filename is outside its owned contract.");
        }

        return fullPath;
    }

    private static string GetEvidencePath(
        string workingDirectory,
        string transactionId)
    {
        string candidate = Path.Combine(
            workingDirectory,
            $"{EvidencePrefix}{transactionId}{EvidenceSuffix}");
        return ValidateEvidencePath(
            candidate,
            Path.Combine(workingDirectory, "candidate.exe"),
            transactionId);
    }

    private static string ValidateTransactionId(string? transactionId)
    {
        if (transactionId is not { Length: 32 } ||
            !transactionId.AsSpan().ContainsOnlyLowerHex() ||
            !Guid.TryParseExact(transactionId, "N", out Guid parsed) ||
            !string.Equals(parsed.ToString("N"), transactionId, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "The Setup candidate verification transaction ID must be a canonical lowercase GUID N value.");
        }

        return transactionId;
    }

    private static string ValidateAbsolutePath(string? path, string field)
    {
        if (string.IsNullOrWhiteSpace(path) ||
            !Path.IsPathFullyQualified(path) ||
            path.Contains('\0') ||
            path.Contains('"'))
        {
            throw new InstallationSafetyException($"The {field} must be an absolute Windows path.");
        }

        string fullPath;
        try
        {
            fullPath = Path.GetFullPath(path);
        }
        catch (Exception exception) when (
            exception is ArgumentException or IOException or NotSupportedException)
        {
            throw new InstallationSafetyException($"The {field} is invalid.", exception);
        }

        if (Path.GetFileName(fullPath).Contains(':', StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                $"The {field} cannot address an alternate data stream.");
        }

        return fullPath;
    }

    private static string RequireSafeParent(string path)
    {
        string? parent = Path.GetDirectoryName(path);
        if (string.IsNullOrEmpty(parent))
        {
            throw new InstallationSafetyException(
                "A Setup candidate verification path must have a parent directory.");
        }

        PathSafety.AssertExistingChainHasNoReparsePoint(parent);
        if (!Directory.Exists(parent))
        {
            throw new InstallationSafetyException(
                "The Setup candidate verification parent directory must already exist.");
        }

        FileAttributes attributes = File.GetAttributes(parent);
        if ((attributes & (FileAttributes.Directory | FileAttributes.ReparsePoint)) !=
            FileAttributes.Directory)
        {
            throw new InstallationSafetyException(
                "The Setup candidate verification parent directory is unsafe.");
        }

        return parent;
    }

    private static void RequireIdentity(
        StableSetupHostIdentity actual,
        StableSetupHostIdentity expected,
        string description)
    {
        if (actual.Bytes != expected.Bytes ||
            !string.Equals(actual.Sha256, expected.Sha256, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                $"The {description} does not match its exact SHA-256 and byte length.");
        }
    }

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

    private static unsafe void DeleteEvidenceByLockedHandle(
        string path,
        StableSetupHostIdentity expected,
        VerifiedProductPackage parentPackage)
    {
        const uint genericRead = 0x80000000;
        const uint delete = 0x00010000;
        const uint shareRead = 0x00000001;
        const uint openExisting = 3;
        const uint openReparsePoint = 0x00200000;
        const int fileDispositionInfo = 4;

        using SafeFileHandle handle = CreateEvidenceFile(
            path,
            genericRead | delete,
            shareRead,
            0,
            openExisting,
            openReparsePoint,
            0);
        if (handle.IsInvalid)
        {
            throw new InstallationSafetyException(
                "The exact verified Setup evidence could not be locked for deletion.",
                new Win32Exception(Marshal.GetLastPInvokeError()));
        }

        if (!GetEvidenceFileInformation(handle, out ByHandleFileInformation information))
        {
            throw new InstallationSafetyException(
                "Windows could not attest the locked Setup evidence file.",
                new Win32Exception(Marshal.GetLastPInvokeError()));
        }

        FileAttributes attributes = (FileAttributes)information.FileAttributes;
        if ((attributes & (FileAttributes.Directory | FileAttributes.ReparsePoint)) != 0 ||
            information.NumberOfLinks != 1)
        {
            throw new InstallationSafetyException(
                "The locked Setup evidence is not an owned regular single-link file.");
        }

        // The handle denies write and delete sharing, so this path attestation and the
        // subsequent semantic read refer to the same directory entry until disposition.
        PathSafety.AssertRegularFile(path);
        long length = RandomAccess.GetLength(handle);
        if (length is <= 0 or > MaximumEvidenceBytes)
        {
            throw new InstallationSafetyException(
                "The locked Setup evidence has an invalid length.");
        }

        ulong informationLength =
            ((ulong)information.FileSizeHigh << 32) | information.FileSizeLow;
        if (informationLength != (ulong)length)
        {
            throw new InstallationSafetyException(
                "The locked Setup evidence length is inconsistent.");
        }

        byte[] bytes = new byte[checked((int)length)];
        int offset = 0;
        while (offset < bytes.Length)
        {
            int read = RandomAccess.Read(handle, bytes.AsSpan(offset), offset);
            if (read <= 0)
            {
                throw new InstallationSafetyException(
                    "The locked Setup evidence ended before its attested length.");
            }

            offset += read;
        }

        EmbeddedVerificationEvidence parsed = ParseCanonicalEvidence(bytes);
        RequireEvidenceMatchesParent(parsed, parentPackage);
        StableSetupHostIdentity actual = new(
            Convert.ToHexStringLower(SHA256.HashData(bytes)),
            bytes.LongLength);
        RequireIdentity(actual, expected, "locked verified Setup evidence");

        int disposition = 1;
        if (!SetEvidenceFileInformation(
                handle,
                fileDispositionInfo,
                (nint)(&disposition),
                sizeof(int)))
        {
            throw new InstallationSafetyException(
                "Windows refused exact-handle deletion of the verified Setup evidence.",
                new Win32Exception(Marshal.GetLastPInvokeError()));
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ByHandleFileInformation
    {
        internal uint FileAttributes;
        internal uint CreationTimeLow;
        internal uint CreationTimeHigh;
        internal uint LastAccessTimeLow;
        internal uint LastAccessTimeHigh;
        internal uint LastWriteTimeLow;
        internal uint LastWriteTimeHigh;
        internal uint VolumeSerialNumber;
        internal uint FileSizeHigh;
        internal uint FileSizeLow;
        internal uint NumberOfLinks;
        internal uint FileIndexHigh;
        internal uint FileIndexLow;
    }

    [LibraryImport(
        "kernel32.dll",
        EntryPoint = "CreateFileW",
        SetLastError = true,
        StringMarshalling = StringMarshalling.Utf16)]
    private static partial SafeFileHandle CreateEvidenceFile(
        string fileName,
        uint desiredAccess,
        uint shareMode,
        nint securityAttributes,
        uint creationDisposition,
        uint flagsAndAttributes,
        nint templateFile);

    [LibraryImport(
        "kernel32.dll",
        EntryPoint = "GetFileInformationByHandle",
        SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetEvidenceFileInformation(
        SafeFileHandle file,
        out ByHandleFileInformation fileInformation);

    [LibraryImport(
        "kernel32.dll",
        EntryPoint = "SetFileInformationByHandle",
        SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetEvidenceFileInformation(
        SafeFileHandle file,
        int fileInformationClass,
        nint fileInformation,
        int bufferSize);
}

internal static class LowerHexSpanExtensions
{
    internal static bool ContainsOnlyLowerHex(this ReadOnlySpan<char> value)
    {
        foreach (char character in value)
        {
            if (character is not (>= '0' and <= '9') and not (>= 'a' and <= 'f'))
            {
                return false;
            }
        }

        return true;
    }
}

internal sealed partial class WindowsSetupHostCandidateRunner : ISetupHostCandidateRunner
{
    private const uint WaitObject0 = 0;
    private const uint WaitTimeout = 258;
    private const uint WaitFailed = uint.MaxValue;
    private const uint TerminatedExitCode = 0xba710001;
    private const uint TerminationWaitMilliseconds = 30_000;

    private readonly IInstalledApplicationEnvironment environment;

    internal WindowsSetupHostCandidateRunner()
        : this(new ProcessEnvironmentSnapshot())
    {
    }

    internal WindowsSetupHostCandidateRunner(IInstalledApplicationEnvironment environment)
    {
        this.environment = environment ?? throw new ArgumentNullException(nameof(environment));
    }

    public SetupHostCandidateRunResult Run(SetupHostCandidateRunRequest request)
    {
        SetupHostCandidateVerifier.ValidateRunnerRequest(request);
        string commandLine = SetupHostCandidateVerifier.BuildWindowsCommandLine(request);
        char[] commandLineBuffer = (commandLine + '\0').ToCharArray();
        char[] environmentBlock;
        try
        {
            environmentBlock = InstalledApplicationLauncher.BuildEnvironmentBlock(
                environment.Capture());
        }
        catch (InstalledApplicationLaunchException exception)
        {
            throw new InstallationSafetyException(
                "The Setup candidate verification environment is invalid.",
                exception);
        }

        StartupInfo startupInfo = new()
        {
            Size = checked((uint)Marshal.SizeOf<StartupInfo>()),
        };
        ProcessInformation processInformation;
        bool created;
        int createError;
        GCHandle commandLineHandle = default;
        GCHandle environmentHandle = default;
        try
        {
            commandLineHandle = GCHandle.Alloc(commandLineBuffer, GCHandleType.Pinned);
            environmentHandle = GCHandle.Alloc(environmentBlock, GCHandleType.Pinned);
            created = CreateProcessW(
                request.ApplicationPath,
                commandLineHandle.AddrOfPinnedObject(),
                processAttributes: 0,
                threadAttributes: 0,
                inheritHandles: false,
                request.CreationFlags,
                environmentHandle.AddrOfPinnedObject(),
                request.WorkingDirectory,
                ref startupInfo,
                out processInformation);
            createError = Marshal.GetLastPInvokeError();
        }
        finally
        {
            if (environmentHandle.IsAllocated)
            {
                environmentHandle.Free();
            }

            if (commandLineHandle.IsAllocated)
            {
                commandLineHandle.Free();
            }
        }

        if (!created)
        {
            throw new InstallationSafetyException(
                "CreateProcessW rejected the staged Setup candidate.",
                new Win32Exception(createError));
        }

        using SafeWaitHandle processHandle = new(processInformation.ProcessHandle, ownsHandle: true);
        using SafeWaitHandle threadHandle = new(processInformation.ThreadHandle, ownsHandle: true);
        if (processHandle.IsInvalid || threadHandle.IsInvalid || processInformation.ProcessId == 0)
        {
            if (!processHandle.IsInvalid)
            {
                TerminateOwnedChildAndWait(processHandle);
            }

            throw new InstallationSafetyException(
                "CreateProcessW returned invalid Setup candidate process handles.");
        }

        uint waitResult = WaitForSingleObject(processHandle, request.TimeoutMilliseconds);
        if (waitResult == WaitTimeout)
        {
            TerminateOwnedChildAndWait(processHandle);
            return new SetupHostCandidateRunResult(
                TimedOut: true,
                ReadExitCode(processHandle));
        }

        if (waitResult == WaitFailed)
        {
            int waitError = Marshal.GetLastPInvokeError();
            throw TerminateAfterWaitFailure(
                processHandle,
                "Waiting for the staged Setup candidate failed.",
                new Win32Exception(waitError));
        }

        if (waitResult != WaitObject0)
        {
            throw TerminateAfterWaitFailure(
                processHandle,
                "Waiting for the staged Setup candidate returned an unexpected state.",
                new InvalidOperationException($"Unexpected wait result 0x{waitResult:X8}."));
        }

        return new SetupHostCandidateRunResult(
            TimedOut: false,
            ReadExitCode(processHandle));
    }

    private static uint ReadExitCode(SafeWaitHandle processHandle)
    {
        if (!GetExitCodeProcess(processHandle, out uint exitCode))
        {
            throw new InstallationSafetyException(
                "Windows could not read the staged Setup candidate exit code.",
                new Win32Exception(Marshal.GetLastPInvokeError()));
        }

        return exitCode;
    }

    private static InstallationSafetyException TerminateAfterWaitFailure(
        SafeWaitHandle processHandle,
        string message,
        Exception original)
    {
        try
        {
            TerminateOwnedChildAndWait(processHandle);
        }
        catch (Exception cleanup)
        {
            return new InstallationSafetyException(
                message + " The owned child also could not be terminated cleanly.",
                new AggregateException(original, cleanup));
        }

        return new InstallationSafetyException(message, original);
    }

    private static void TerminateOwnedChildAndWait(SafeWaitHandle processHandle)
    {
        if (!TerminateProcess(processHandle, TerminatedExitCode))
        {
            int error = Marshal.GetLastPInvokeError();
            if (WaitForSingleObject(processHandle, 0) != WaitObject0)
            {
                throw new InstallationSafetyException(
                    "Windows could not terminate the owned Setup candidate child.",
                    new Win32Exception(error));
            }

            return;
        }

        uint waitResult = WaitForSingleObject(processHandle, TerminationWaitMilliseconds);
        if (waitResult != WaitObject0)
        {
            Exception detail = waitResult == WaitFailed
                ? new Win32Exception(Marshal.GetLastPInvokeError())
                : new TimeoutException("The terminated Setup candidate child did not signal completion.");
            throw new InstallationSafetyException(
                "The owned Setup candidate child did not terminate cleanly.",
                detail);
        }
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct StartupInfo
    {
        internal uint Size;
        internal nint Reserved;
        internal nint Desktop;
        internal nint Title;
        internal uint X;
        internal uint Y;
        internal uint XSize;
        internal uint YSize;
        internal uint XCountChars;
        internal uint YCountChars;
        internal uint FillAttribute;
        internal uint Flags;
        internal ushort ShowWindow;
        internal ushort Reserved2Size;
        internal nint Reserved2;
        internal nint StandardInput;
        internal nint StandardOutput;
        internal nint StandardError;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ProcessInformation
    {
        internal nint ProcessHandle;
        internal nint ThreadHandle;
        internal uint ProcessId;
        internal uint ThreadId;
    }

    [LibraryImport(
        "kernel32.dll",
        EntryPoint = "CreateProcessW",
        SetLastError = true,
        StringMarshalling = StringMarshalling.Utf16)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool CreateProcessW(
        string applicationName,
        nint commandLine,
        nint processAttributes,
        nint threadAttributes,
        [MarshalAs(UnmanagedType.Bool)] bool inheritHandles,
        uint creationFlags,
        nint environment,
        string currentDirectory,
        ref StartupInfo startupInfo,
        out ProcessInformation processInformation);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    private static partial uint WaitForSingleObject(
        SafeWaitHandle handle,
        uint milliseconds);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool TerminateProcess(
        SafeWaitHandle process,
        uint exitCode);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetExitCodeProcess(
        SafeWaitHandle process,
        out uint exitCode);
}
