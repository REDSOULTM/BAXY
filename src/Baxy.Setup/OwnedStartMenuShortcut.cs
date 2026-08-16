using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using Microsoft.Win32.SafeHandles;

namespace Baxy.Setup;

internal enum OwnedStartMenuShortcutState
{
    Missing,
    Exact,
}

internal sealed record OwnedStartMenuShortcutSnapshot(
    OwnedStartMenuShortcutState State,
    string? Sha256,
    long Bytes)
{
    internal static OwnedStartMenuShortcutSnapshot Missing { get; } =
        new(OwnedStartMenuShortcutState.Missing, null, 0);
}

internal enum OwnedStartMenuShortcutFaultPoint
{
    DirectoryCreated,
    LinkCreatedAndVerified,
    BeforeLinkDeleteLock,
    LinkLockedAndVerifiedBeforeDeletion,
}

internal interface IOwnedStartMenuShortcutFaultInjector
{
    void Checkpoint(OwnedStartMenuShortcutFaultPoint point);
}

internal sealed partial class OwnedStartMenuShortcut
{
    private const int MaxPathCharacters = 260;
    private const int MaximumInformationTipCharacters = 1024;
    private const string OwnedDirectoryName = "BAXY";
    private const string OwnedLinkName = "BAXY.lnk";

    private readonly string startMenuDirectory;
    private readonly string shortcutPath;
    private readonly ShellLinkSpecification specification;
    private readonly IOwnedStartMenuShortcutFaultInjector? faultInjector;

    internal OwnedStartMenuShortcut(
        string startMenuDirectory,
        string shortcutPath,
        ShellLinkSpecification specification,
        IOwnedStartMenuShortcutFaultInjector? faultInjector = null)
    {
        this.startMenuDirectory = ValidateStartMenuDirectoryPath(startMenuDirectory);
        this.shortcutPath = ValidateShortcutPath(shortcutPath, this.startMenuDirectory);
        this.specification = specification ?? throw new ArgumentNullException(nameof(specification));
        this.faultInjector = faultInjector;
        ValidateParentDirectory();
    }

    internal OwnedStartMenuShortcutSnapshot Probe()
    {
        FileAttributes? directoryAttributes = TryGetAttributes(startMenuDirectory);
        if (directoryAttributes is null)
        {
            ValidateParentDirectory();
            return OwnedStartMenuShortcutSnapshot.Missing;
        }

        ValidateOwnedDirectory(directoryAttributes.Value);

        FileAttributes? linkAttributes = TryGetAttributes(shortcutPath);
        if (linkAttributes is null)
        {
            return OwnedStartMenuShortcutSnapshot.Missing;
        }

        ValidateLinkAttributes(linkAttributes.Value);
        return VerifyExactLink();
    }

    internal OwnedStartMenuShortcutSnapshot Ensure() => EnsureCore(journalTemporaryPath: null);

    internal OwnedStartMenuShortcutSnapshot EnsureFromJournal(string transactionId)
    {
        if (!Guid.TryParseExact(transactionId, "N", out Guid parsed) ||
            !string.Equals(transactionId, parsed.ToString("N"), StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "A shortcut transaction id must be a lowercase Guid in exact N format.");
        }

        string temporary = Path.Combine(startMenuDirectory, $".baxy-{transactionId}.lnk");
        if (temporary.Length >= MaxPathCharacters)
        {
            throw new InstallationSafetyException(
                "The Start Menu directory is too long for a journaled shortcut temporary.");
        }

        return EnsureCore(temporary);
    }

    private OwnedStartMenuShortcutSnapshot EnsureCore(string? journalTemporaryPath)
    {
        OwnedStartMenuShortcutSnapshot existing = Probe();
        if (existing.State == OwnedStartMenuShortcutState.Exact)
        {
            if (journalTemporaryPath is not null &&
                TryGetAttributes(journalTemporaryPath) is not null)
            {
                DeleteVerifiedJournalTemporary(journalTemporaryPath);
            }

            return existing;
        }

        ValidateSpecificationBeforeMutation();
        bool createdDirectory = false;
        OwnedStartMenuShortcutSnapshot? createdLink = null;
        try
        {
            if (TryGetAttributes(startMenuDirectory) is null)
            {
                ValidateParentDirectory();
                Directory.CreateDirectory(startMenuDirectory);
                createdDirectory = true;
                FileAttributes createdAttributes = File.GetAttributes(startMenuDirectory);
                ValidateOwnedDirectory(createdAttributes);
                faultInjector?.Checkpoint(OwnedStartMenuShortcutFaultPoint.DirectoryCreated);
            }
            else
            {
                ValidateOwnedDirectory(File.GetAttributes(startMenuDirectory));
            }

            if (TryGetAttributes(shortcutPath) is not null)
            {
                throw new InstallationSafetyException(
                    "Refusing to overwrite an existing Start Menu shortcut path.");
            }

            if (journalTemporaryPath is not null &&
                TryGetAttributes(journalTemporaryPath) is not null)
            {
                VerifyJournalTemporary(journalTemporaryPath);
                WindowsShellLink.PromoteVerifiedJournalTemporary(
                    shortcutPath,
                    journalTemporaryPath,
                    specification);
            }
            else if (journalTemporaryPath is null)
            {
                WindowsShellLink.WriteNewVerified(shortcutPath, specification);
            }
            else
            {
                WindowsShellLink.WriteNewVerifiedFromJournal(
                    shortcutPath,
                    journalTemporaryPath,
                    specification);
            }

            createdLink = Probe();
            if (createdLink.State != OwnedStartMenuShortcutState.Exact)
            {
                throw new InstallationSafetyException(
                    "The newly created Start Menu shortcut could not be attested.");
            }

            faultInjector?.Checkpoint(OwnedStartMenuShortcutFaultPoint.LinkCreatedAndVerified);
            return createdLink;
        }
        catch (Exception original)
        {
            try
            {
                if (createdLink is not null)
                {
                    _ = DeleteOwnedVerified(createdLink.Sha256!, createdLink.Bytes);
                }
                else if (createdDirectory)
                {
                    RemoveOwnedDirectoryIfEmpty();
                }
            }
            catch (Exception cleanup)
            {
                throw new InstallationSafetyException(
                    "Start Menu shortcut creation failed and its verified rollback also failed.",
                    new AggregateException(original, cleanup));
            }

            throw;
        }
    }

    private void VerifyJournalTemporary(string path)
    {
        FileAttributes? attributes = TryGetAttributes(path);
        if (attributes is null)
        {
            throw new InstallationSafetyException(
                "The journaled Start Menu shortcut temporary is missing.");
        }

        ValidateLinkAttributes(attributes.Value);
        PathSafety.AssertRegularFile(path);
        WindowsShellLink.ReadAndVerify(path, specification);
        PathSafety.AssertRegularFile(path);
    }

    private void DeleteVerifiedJournalTemporary(string path)
    {
        VerifyJournalTemporary(path);
        File.Delete(path);
        if (TryGetAttributes(path) is not null)
        {
            throw new InstallationSafetyException(
                "The verified journaled Start Menu shortcut temporary remained after deletion.");
        }
    }

    internal bool DeleteOwnedVerified(string expectedSha256, long expectedBytes) =>
        DeleteOwnedVerifiedCore(
            expectedSha256,
            expectedBytes,
            allowMovedInstallationPaths: false);

    internal bool DeleteOwnedVerifiedAfterInstallationMove(
        string expectedSha256,
        long expectedBytes) =>
        DeleteOwnedVerifiedCore(
            expectedSha256,
            expectedBytes,
            allowMovedInstallationPaths: true);

    private bool DeleteOwnedVerifiedCore(
        string expectedSha256,
        long expectedBytes,
        bool allowMovedInstallationPaths)
    {
        ValidateExpectedIdentity(expectedSha256, expectedBytes);

        FileAttributes? directoryAttributes = TryGetAttributes(startMenuDirectory);
        if (directoryAttributes is null)
        {
            ValidateParentDirectory();
            return false;
        }

        ValidateOwnedDirectory(directoryAttributes.Value);
        FileAttributes? linkAttributes = TryGetAttributes(shortcutPath);
        if (linkAttributes is null)
        {
            RemoveOwnedDirectoryIfEmpty();
            return false;
        }

        ValidateLinkAttributes(linkAttributes.Value);
        if (!VerifyLinkUnderReadLock(
                expectedSha256,
                expectedBytes,
                allowMovedInstallationPaths))
        {
            if (TryGetAttributes(shortcutPath) is not null)
            {
                throw new InstallationSafetyException(
                    "The Start Menu shortcut path changed while semantic verification acquired its lock.");
            }

            RemoveOwnedDirectoryIfEmpty();
            return false;
        }

        faultInjector?.Checkpoint(OwnedStartMenuShortcutFaultPoint.BeforeLinkDeleteLock);
        bool deleted = DeleteLinkByLockedHandle(expectedSha256, expectedBytes);
        if (!deleted)
        {
            if (TryGetAttributes(shortcutPath) is not null)
            {
                throw new InstallationSafetyException(
                    "The Start Menu shortcut path changed while deletion acquired its lock.");
            }

            RemoveOwnedDirectoryIfEmpty();
            return false;
        }

        if (TryGetAttributes(shortcutPath) is not null)
        {
            throw new InstallationSafetyException(
                "A Start Menu shortcut path exists after exact-handle deletion.");
        }

        RemoveOwnedDirectoryIfEmpty();
        return true;
    }

    private bool VerifyLinkUnderReadLock(
        string expectedSha256,
        long expectedBytes,
        bool allowMovedInstallationPaths)
    {
        const uint genericRead = 0x80000000;
        const uint shareRead = 0x00000001;
        const uint openExisting = 3;
        const uint openReparsePoint = 0x00200000;
        const int errorFileNotFound = 2;
        const int errorPathNotFound = 3;

        using SafeFileHandle handle = CreateShortcutFile(
            shortcutPath,
            genericRead,
            shareRead,
            0,
            openExisting,
            openReparsePoint,
            0);
        if (handle.IsInvalid)
        {
            int error = Marshal.GetLastPInvokeError();
            if (error is errorFileNotFound or errorPathNotFound)
            {
                return false;
            }

            throw new InstallationSafetyException(
                "The Start Menu shortcut could not be locked for semantic verification.",
                new Win32Exception(error));
        }

        ByHandleFileInformation before = ReadLockedFileInformation(handle);
        RequireOwnedLockedFile(before);

        // IPersistFile.Load requires its own read handle. This guard requests no DELETE
        // access, but still denies write and delete sharing, so COM reads the same stable
        // directory entry. The later READ|DELETE handle is independently rebound to the
        // same expected SHA-256 and byte length before it can delete anything.
        PathSafety.AssertRegularFile(shortcutPath);
        if (allowMovedInstallationPaths)
        {
            WindowsShellLink.ReadAndVerifyAfterInstallationMove(shortcutPath, specification);
        }
        else
        {
            WindowsShellLink.ReadAndVerify(shortcutPath, specification);
        }

        PathSafety.AssertRegularFile(shortcutPath);

        FileIdentity identity = ComputeLockedFileIdentity(handle, expectedBytes);
        RequireExpectedIdentity(
            new OwnedStartMenuShortcutSnapshot(
                OwnedStartMenuShortcutState.Exact,
                identity.Sha256,
                identity.Bytes),
            expectedSha256,
            expectedBytes);

        ByHandleFileInformation after = ReadLockedFileInformation(handle);
        RequireOwnedLockedFile(after);
        if (!SameLockedFile(before, after) ||
            GetFileLength(after) != checked((ulong)identity.Bytes))
        {
            throw new InstallationSafetyException(
                "The Start Menu shortcut changed during locked semantic verification.");
        }

        return true;
    }

    private unsafe bool DeleteLinkByLockedHandle(string expectedSha256, long expectedBytes)
    {
        const uint genericRead = 0x80000000;
        const uint delete = 0x00010000;
        const uint shareRead = 0x00000001;
        const uint openExisting = 3;
        const uint openReparsePoint = 0x00200000;
        const int errorFileNotFound = 2;
        const int errorPathNotFound = 3;
        const int fileDispositionInfo = 4;

        using SafeFileHandle handle = CreateShortcutFile(
            shortcutPath,
            genericRead | delete,
            shareRead,
            0,
            openExisting,
            openReparsePoint,
            0);
        if (handle.IsInvalid)
        {
            int error = Marshal.GetLastPInvokeError();
            if (error is errorFileNotFound or errorPathNotFound)
            {
                return false;
            }

            throw new InstallationSafetyException(
                "The exact Start Menu shortcut could not be locked for deletion.",
                new Win32Exception(error));
        }

        ByHandleFileInformation before = ReadLockedFileInformation(handle);
        RequireOwnedLockedFile(before);

        PathSafety.AssertRegularFile(shortcutPath);
        FileIdentity identity = ComputeLockedFileIdentity(handle, expectedBytes);
        RequireExpectedIdentity(
            new OwnedStartMenuShortcutSnapshot(
                OwnedStartMenuShortcutState.Exact,
                identity.Sha256,
                identity.Bytes),
            expectedSha256,
            expectedBytes);

        ByHandleFileInformation after = ReadLockedFileInformation(handle);
        RequireOwnedLockedFile(after);
        if (!SameLockedFile(before, after) ||
            GetFileLength(after) != checked((ulong)identity.Bytes))
        {
            throw new InstallationSafetyException(
                "The locked Start Menu shortcut changed during deletion attestation.");
        }

        faultInjector?.Checkpoint(
            OwnedStartMenuShortcutFaultPoint.LinkLockedAndVerifiedBeforeDeletion);

        ByHandleFileInformation beforeDisposition = ReadLockedFileInformation(handle);
        RequireOwnedLockedFile(beforeDisposition);
        if (!SameLockedFile(after, beforeDisposition) ||
            GetFileLength(beforeDisposition) != checked((ulong)identity.Bytes))
        {
            throw new InstallationSafetyException(
                "The locked Start Menu shortcut changed before exact-handle disposition.");
        }

        int disposition = 1;
        if (!SetShortcutFileInformation(
                handle,
                fileDispositionInfo,
                (nint)(&disposition),
                sizeof(int)))
        {
            throw new InstallationSafetyException(
                "Windows refused exact-handle deletion of the verified Start Menu shortcut.",
                new Win32Exception(Marshal.GetLastPInvokeError()));
        }

        return true;
    }

    private static ByHandleFileInformation ReadLockedFileInformation(SafeFileHandle handle)
    {
        if (!GetShortcutFileInformation(handle, out ByHandleFileInformation information))
        {
            throw new InstallationSafetyException(
                "Windows could not attest the locked Start Menu shortcut.",
                new Win32Exception(Marshal.GetLastPInvokeError()));
        }

        return information;
    }

    private static void RequireOwnedLockedFile(ByHandleFileInformation information)
    {
        FileAttributes attributes = (FileAttributes)information.FileAttributes;
        if ((attributes & (FileAttributes.Directory | FileAttributes.ReparsePoint)) != 0 ||
            information.NumberOfLinks != 1)
        {
            throw new InstallationSafetyException(
                "The locked Start Menu shortcut is not a regular single-link file.");
        }
    }

    private static FileIdentity ComputeLockedFileIdentity(
        SafeFileHandle handle,
        long expectedBytes)
    {
        long length = RandomAccess.GetLength(handle);
        if (length <= 0 || length != expectedBytes)
        {
            throw new InstallationSafetyException(
                "The locked Start Menu shortcut does not match its expected byte length.");
        }

        using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        byte[] buffer = new byte[64 * 1024];
        long offset = 0;
        while (offset < length)
        {
            int requested = checked((int)Math.Min(buffer.Length, length - offset));
            int read = RandomAccess.Read(handle, buffer.AsSpan(0, requested), offset);
            if (read <= 0)
            {
                throw new InstallationSafetyException(
                    "The locked Start Menu shortcut ended before its attested length.");
            }

            hash.AppendData(buffer, 0, read);
            offset += read;
        }

        if (RandomAccess.GetLength(handle) != length)
        {
            throw new InstallationSafetyException(
                "The locked Start Menu shortcut length changed while hashing.");
        }

        return new FileIdentity(Convert.ToHexStringLower(hash.GetHashAndReset()), length);
    }

    private static ulong GetFileLength(ByHandleFileInformation information) =>
        ((ulong)information.FileSizeHigh << 32) | information.FileSizeLow;

    private static bool SameLockedFile(
        ByHandleFileInformation left,
        ByHandleFileInformation right) =>
        left.VolumeSerialNumber == right.VolumeSerialNumber &&
        left.FileIndexHigh == right.FileIndexHigh &&
        left.FileIndexLow == right.FileIndexLow;

    private OwnedStartMenuShortcutSnapshot VerifyExactLink()
    {
        PathSafety.AssertRegularFile(shortcutPath);
        WindowsShellLink.ReadAndVerify(shortcutPath, specification);
        FileIdentity first = ComputeFileIdentity();

        PathSafety.AssertRegularFile(shortcutPath);
        WindowsShellLink.ReadAndVerify(shortcutPath, specification);
        FileIdentity second = ComputeFileIdentity();
        PathSafety.AssertRegularFile(shortcutPath);

        if (first != second)
        {
            throw new InstallationSafetyException(
                "The Start Menu shortcut changed while its identity was being attested.");
        }

        return new OwnedStartMenuShortcutSnapshot(
            OwnedStartMenuShortcutState.Exact,
            second.Sha256,
            second.Bytes);
    }

    private FileIdentity ComputeFileIdentity()
    {
        using FileStream stream = new(
            shortcutPath,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read);
        long bytes = stream.Length;
        if (bytes <= 0)
        {
            throw new InstallationSafetyException(
                "An owned Start Menu shortcut must have a positive byte length.");
        }

        string sha256 = Convert.ToHexStringLower(SHA256.HashData(stream));
        return new FileIdentity(sha256, bytes);
    }

    private void RemoveOwnedDirectoryIfEmpty()
    {
        FileAttributes? attributes = TryGetAttributes(startMenuDirectory);
        if (attributes is null)
        {
            return;
        }

        ValidateOwnedDirectory(attributes.Value);
        using IEnumerator<string> entries =
            Directory.EnumerateFileSystemEntries(startMenuDirectory).GetEnumerator();
        if (entries.MoveNext())
        {
            return;
        }

        try
        {
            Directory.Delete(startMenuDirectory, recursive: false);
        }
        catch (DirectoryNotFoundException)
        {
            // An already absent owned directory is the desired state.
        }
        catch (IOException) when (Directory.Exists(startMenuDirectory) &&
            Directory.EnumerateFileSystemEntries(startMenuDirectory).Any())
        {
            // A concurrently added unrelated sibling is never ours to remove.
        }
    }

    private void ValidateParentDirectory()
    {
        string parent = Path.GetDirectoryName(startMenuDirectory)!;
        PathSafety.AssertExistingChainHasNoReparsePoint(parent);
        FileAttributes? attributes = TryGetAttributes(parent);
        if (attributes is null ||
            (attributes.Value & FileAttributes.Directory) == 0 ||
            (attributes.Value & FileAttributes.ReparsePoint) != 0)
        {
            throw new InstallationSafetyException(
                "The Start Menu shortcut parent must be an existing regular directory.");
        }
    }

    private void ValidateSpecificationBeforeMutation()
    {
        ValidateExistingRegularFile(specification.TargetPath, "target path");
        ValidateExistingDirectory(specification.WorkingDirectory, "working directory");
        ValidateExistingRegularFile(specification.IconPath, "icon path");
        ValidateInformationTipText(specification.Description, nameof(specification.Description));
        ValidateInformationTipText(specification.Arguments, nameof(specification.Arguments));
    }

    private static void ValidateExistingRegularFile(string path, string field)
    {
        string fullPath = ValidateAbsolutePath(path, $"shell-link {field}");
        if (!File.Exists(fullPath))
        {
            throw new InstallationSafetyException(
                $"The shell-link {field} must be an existing regular file.");
        }

        PathSafety.AssertRegularFile(fullPath);
    }

    private static void ValidateExistingDirectory(string path, string field)
    {
        string fullPath = ValidateAbsolutePath(path, $"shell-link {field}");
        PathSafety.AssertExistingChainHasNoReparsePoint(fullPath);
        FileAttributes? attributes = TryGetAttributes(fullPath);
        if (attributes is null ||
            (attributes.Value & FileAttributes.Directory) == 0 ||
            (attributes.Value & FileAttributes.ReparsePoint) != 0)
        {
            throw new InstallationSafetyException(
                $"The shell-link {field} must be an existing regular directory.");
        }
    }

    private static void ValidateInformationTipText(string value, string field)
    {
        ArgumentNullException.ThrowIfNull(value);
        if (value.Contains('\0'))
        {
            throw new InstallationSafetyException($"The shell-link {field} contains a null character.");
        }

        if (value.Length >= MaximumInformationTipCharacters)
        {
            throw new InstallationSafetyException(
                $"The shell-link {field} exceeds the reviewed " +
                $"{MaximumInformationTipCharacters - 1}-character contract.");
        }
    }

    private void ValidateOwnedDirectory(FileAttributes attributes)
    {
        PathSafety.AssertExistingChainHasNoReparsePoint(startMenuDirectory);
        if ((attributes & FileAttributes.Directory) == 0 ||
            (attributes & FileAttributes.ReparsePoint) != 0)
        {
            throw new InstallationSafetyException(
                "The owned Start Menu path must be a regular directory.");
        }
    }

    private static void ValidateLinkAttributes(FileAttributes attributes)
    {
        if ((attributes & FileAttributes.Directory) != 0 ||
            (attributes & FileAttributes.ReparsePoint) != 0)
        {
            throw new InstallationSafetyException(
                "The owned Start Menu shortcut path is not a regular file.");
        }
    }

    private static string ValidateStartMenuDirectoryPath(string path)
    {
        string fullPath = ValidateAbsolutePath(path, "Start Menu directory");
        if (!string.Equals(
                Path.GetFileName(fullPath),
                OwnedDirectoryName,
                StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "The owned Start Menu directory must be the exact BAXY child directory.");
        }

        if (Path.GetDirectoryName(fullPath) is null)
        {
            throw new InstallationSafetyException(
                "The owned Start Menu directory must have a parent directory.");
        }

        return fullPath;
    }

    private static string ValidateShortcutPath(string path, string directory)
    {
        string fullPath = ValidateAbsolutePath(path, "Start Menu shortcut");
        string expected = Path.Combine(directory, OwnedLinkName);
        if (!string.Equals(fullPath, expected, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "The owned Start Menu shortcut must be the exact BAXY.lnk child.");
        }

        return fullPath;
    }

    private static string ValidateAbsolutePath(string path, string field)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        if (!Path.IsPathFullyQualified(path))
        {
            throw new InstallationSafetyException($"The {field} must be an absolute path.");
        }

        if (path.Contains('\0'))
        {
            throw new InstallationSafetyException($"The {field} contains a null character.");
        }

        string fullPath = Path.GetFullPath(path)
            .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        if (fullPath.Length >= MaxPathCharacters)
        {
            throw new InstallationSafetyException(
                $"The {field} exceeds the reviewed {MaxPathCharacters - 1}-character contract.");
        }

        return fullPath;
    }

    private static FileAttributes? TryGetAttributes(string path)
    {
        try
        {
            return File.GetAttributes(path);
        }
        catch (FileNotFoundException)
        {
            return null;
        }
        catch (DirectoryNotFoundException)
        {
            return null;
        }
    }

    private static void ValidateExpectedIdentity(string sha256, long bytes)
    {
        ArgumentNullException.ThrowIfNull(sha256);
        if (sha256.Length != 64 || sha256.Any(character =>
                character is not (>= '0' and <= '9') and not (>= 'a' and <= 'f')))
        {
            throw new InstallationSafetyException(
                "An expected Start Menu shortcut SHA-256 must be 64 lowercase hexadecimal characters.");
        }

        if (bytes <= 0)
        {
            throw new InstallationSafetyException(
                "An expected Start Menu shortcut byte length must be positive.");
        }
    }

    private static void RequireExpectedIdentity(
        OwnedStartMenuShortcutSnapshot observed,
        string expectedSha256,
        long expectedBytes)
    {
        if (observed.State != OwnedStartMenuShortcutState.Exact ||
            !string.Equals(observed.Sha256, expectedSha256, StringComparison.Ordinal) ||
            observed.Bytes != expectedBytes)
        {
            throw new InstallationSafetyException(
                "Refusing to delete a Start Menu shortcut whose exact identity is not owned.");
        }
    }

    private sealed record FileIdentity(string Sha256, long Bytes);

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
    private static partial SafeFileHandle CreateShortcutFile(
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
    private static partial bool GetShortcutFileInformation(
        SafeFileHandle file,
        out ByHandleFileInformation fileInformation);

    [LibraryImport(
        "kernel32.dll",
        EntryPoint = "SetFileInformationByHandle",
        SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetShortcutFileInformation(
        SafeFileHandle file,
        int fileInformationClass,
        nint fileInformation,
        int bufferSize);
}
