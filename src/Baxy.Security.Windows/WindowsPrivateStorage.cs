using System.Buffers.Binary;
using System.Diagnostics.CodeAnalysis;
using System.Runtime.InteropServices;
using System.Security.Principal;
using Microsoft.Win32.SafeHandles;

namespace Baxy.Security.Windows;

/// <summary>
/// Opens private local storage through identity-checked Windows handles. Directory
/// handles deliberately deny delete sharing so an accepted path cannot be exchanged
/// for a junction between validation and the file operation.
/// </summary>
public static partial class WindowsPrivateStorage
{
    private const string PrivateDataDirectoryName = "BAXY";
    private const uint GenericRead = 0x80000000;
    private const uint GenericWrite = 0x40000000;
    private const uint DeleteAccess = 0x00010000;
    private const uint ReadControl = 0x00020000;
    private const uint WriteDac = 0x00040000;
    private const uint FileReadAttributes = 0x00000080;
    private const uint FileTraverse = 0x00000020;
    private const uint FileShareRead = 0x00000001;
    private const uint FileShareWrite = 0x00000002;
    private const uint FileShareDelete = 0x00000004;
    private const uint CreateNew = 1;
    private const uint OpenExisting = 3;
    private const uint FileFlagWriteThrough = 0x80000000;
    private const uint FileFlagBackupSemantics = 0x02000000;
    private const uint FileFlagOpenReparsePoint = 0x00200000;
    private const uint FileFlagSequentialScan = 0x08000000;
    private const uint FileTypeDisk = 0x0001;
    private const uint OwnerSecurityInformation = 0x00000001;
    private const uint DaclSecurityInformation = 0x00000004;
    private const ushort SeDaclProtected = 0x1000;
    private const int ErrorFileNotFound = 2;
    private const int ErrorPathNotFound = 3;
    private const int ErrorAlreadyExists = 183;
    private const int MaximumFinalPathCharacters = 32 * 1024;
    private const int SeFileObject = 1;
    private const int FileAttributeTagInfo = 9;
    private const int NtFileRenameInformation = 10;
    private const int StatusObjectNameCollision = unchecked((int)0xC0000035);

    private static readonly string CurrentUserSid = GetCurrentUserSid();

    /// <summary>
    /// Validates and prepares BAXY's private data root as a direct child of its
    /// protected directory in the current user's local application-data
    /// directory. The fixed two-level chain prevents a configurable shared
    /// parent from deleting the whole private store through FILE_DELETE_CHILD
    /// while BAXY is not running.
    /// </summary>
    public static string PreparePrivateDataRoot(string directoryPath)
    {
        EnsureWindows();
        string trustedAnchor = NormalizeLocalPath(
            Environment.GetFolderPath(
                Environment.SpecialFolder.LocalApplicationData,
                Environment.SpecialFolderOption.DoNotVerify),
            requireFileName: false);
        string privateParent = NormalizeLocalPath(
            Path.Combine(trustedAnchor, PrivateDataDirectoryName),
            requireFileName: false);
        string fullPath = NormalizeLocalPath(directoryPath, requireFileName: false);
        if (!string.Equals(
                Path.GetDirectoryName(fullPath),
                privateParent,
                StringComparison.OrdinalIgnoreCase))
        {
            throw UnsafePath();
        }

        using (WindowsPrivateDirectoryLease anchor = AcquireDirectory(
                   trustedAnchor,
                   createMissing: false,
                   protectLeaf: false))
        {
            EnsureTrustedOwner(anchor.LeafHandle);
            anchor.Validate();
        }

        using (WindowsPrivateDirectoryLease parent = AcquireDirectory(
                   privateParent,
                   createMissing: true,
                   protectLeaf: true))
        {
            parent.Validate();
        }

        using WindowsPrivateDirectoryLease dataRoot = AcquireDirectory(
            fullPath,
            createMissing: true,
            protectLeaf: true);
        dataRoot.Validate();
        return dataRoot.Path;
    }

    public static WindowsPrivateDirectoryLease AcquireDirectory(
        string directoryPath,
        bool createMissing,
        bool protectLeaf)
    {
        EnsureWindows();
        string fullPath = NormalizeLocalPath(directoryPath, requireFileName: false);
        string root = Path.GetPathRoot(fullPath)!;
        var handles = new List<SafeFileHandle>();
        try
        {
            string current = root;
            handles.Add(OpenAndValidateDirectory(current, protectAcl: false));
            string relative = Path.GetRelativePath(root, fullPath);
            string[] components = relative.Split(
                Path.DirectorySeparatorChar,
                StringSplitOptions.RemoveEmptyEntries);
            for (int index = 0; index < components.Length; index++)
            {
                current = Path.Combine(current, components[index]);
                bool isLeaf = index == components.Length - 1;
                if (createMissing && protectLeaf && isLeaf)
                {
                    CreatePrivateDirectory(current);
                }
                else if (createMissing && !Directory.Exists(current))
                {
                    try
                    {
                        Directory.CreateDirectory(current);
                    }
                    catch (Exception exception) when (exception is IOException
                        or UnauthorizedAccessException)
                    {
                        throw UnsafePath();
                    }
                }

                handles.Add(OpenAndValidateDirectory(current, protectLeaf && isLeaf));
            }

            if (components.Length == 0 && protectLeaf)
            {
                throw UnsafePath();
            }

            return new WindowsPrivateDirectoryLease(fullPath, handles);
        }
        catch
        {
            foreach (SafeFileHandle handle in handles)
            {
                handle.Dispose();
            }

            throw;
        }
    }

    public static bool TryOpenFile(
        string path,
        FileAccess access,
        FileShare share,
        bool deleteAccess,
        [NotNullWhen(true)] out WindowsPrivateFileLease? lease)
    {
        EnsureWindows();
        string fullPath = NormalizeLocalPath(path, requireFileName: true);
        string directory = Path.GetDirectoryName(fullPath) ?? throw UnsafePath();
        // A missing parent is an ordinary "not found" result for a probe. If it
        // appears after this check, AcquireDirectory still validates every
        // component and rejects reparse points or an untrusted ACL.
        if (!Directory.Exists(directory))
        {
            lease = null;
            return false;
        }

        WindowsPrivateDirectoryLease directoryLease = AcquireDirectory(
            directory,
            createMissing: false,
            protectLeaf: false);
        SafeFileHandle? handle = null;
        try
        {
            directoryLease.Validate();
            uint desiredAccess = ReadControl | FileReadAttributes;
            if ((access & FileAccess.Read) != 0)
            {
                desiredAccess |= GenericRead;
            }

            if ((access & FileAccess.Write) != 0)
            {
                desiredAccess |= GenericWrite;
            }

            if (deleteAccess)
            {
                desiredAccess |= DeleteAccess;
            }

            handle = CreateFile(
                fullPath,
                desiredAccess,
                ToNativeShare(share),
                0,
                OpenExisting,
                FileFlagOpenReparsePoint | FileFlagSequentialScan,
                0);
            if (handle.IsInvalid)
            {
                int error = Marshal.GetLastPInvokeError();
                handle.Dispose();
                handle = null;
                if (error is ErrorFileNotFound or ErrorPathNotFound)
                {
                    directoryLease.Dispose();
                    lease = null;
                    return false;
                }

                throw UnsafePath();
            }

            ValidateFileHandle(handle, fullPath);
            directoryLease.Validate();
            var stream = new FileStream(
                handle,
                access,
                bufferSize: 4096,
                isAsync: false);
            handle = null;
            lease = new WindowsPrivateFileLease(fullPath, directoryLease, stream, deleteAccess);
            return true;
        }
        catch
        {
            handle?.Dispose();
            directoryLease.Dispose();
            throw;
        }
    }

    public static WindowsPrivateFileLease CreateFile(
        string path,
        bool writeThrough = true)
    {
        EnsureWindows();
        string fullPath = NormalizeLocalPath(path, requireFileName: true);
        string directory = Path.GetDirectoryName(fullPath) ?? throw UnsafePath();
        WindowsPrivateDirectoryLease directoryLease = AcquireDirectory(
            directory,
            createMissing: false,
            protectLeaf: false);
        SafeFileHandle? handle = null;
        try
        {
            directoryLease.Validate();
            uint flags = FileFlagOpenReparsePoint;
            if (writeThrough)
            {
                flags |= FileFlagWriteThrough;
            }

            handle = CreateFile(
                fullPath,
                GenericWrite | DeleteAccess | ReadControl | WriteDac | FileReadAttributes,
                0,
                0,
                CreateNew,
                flags,
                0);
            if (handle.IsInvalid)
            {
                throw UnsafePath();
            }

            ValidateFileHandle(handle, fullPath);
            directoryLease.Validate();
            ApplyPrivateDacl(handle, directory: false);
            var stream = new FileStream(
                handle,
                FileAccess.Write,
                bufferSize: 4096,
                isAsync: false);
            handle = null;
            return new WindowsPrivateFileLease(fullPath, directoryLease, stream, canRename: true);
        }
        catch
        {
            handle?.Dispose();
            directoryLease.Dispose();
            throw;
        }
    }

    public static bool Rename(
        WindowsPrivateFileLease source,
        string destinationFileName,
        bool replace)
    {
        ArgumentNullException.ThrowIfNull(source);
        ValidateFileName(destinationFileName);
        if (!source.CanRename)
        {
            throw UnsafePath();
        }

        source.FlushToDisk();
        ValidateFileHandle(source.Handle, source.Path);
        string destinationPath = Path.Combine(source.DirectoryPath, destinationFileName);
        byte[] fileName = MemoryMarshal.AsBytes(destinationFileName.AsSpan()).ToArray();
        int rootOffset = IntPtr.Size == sizeof(long) ? 8 : 4;
        int lengthOffset = rootOffset + IntPtr.Size;
        int nameOffset = lengthOffset + sizeof(uint);
        byte[] renameInfo = new byte[checked(nameOffset + fileName.Length + sizeof(char))];
        BinaryPrimitives.WriteUInt32LittleEndian(
            renameInfo.AsSpan(0, sizeof(uint)),
            replace ? 1u : 0u);
        if (IntPtr.Size == sizeof(long))
        {
            BinaryPrimitives.WriteInt64LittleEndian(
                renameInfo.AsSpan(rootOffset, sizeof(long)),
                source.DirectoryHandle.DangerousGetHandle().ToInt64());
        }
        else
        {
            BinaryPrimitives.WriteInt32LittleEndian(
                renameInfo.AsSpan(rootOffset, sizeof(int)),
                source.DirectoryHandle.DangerousGetHandle().ToInt32());
        }

        BinaryPrimitives.WriteUInt32LittleEndian(
            renameInfo.AsSpan(lengthOffset, sizeof(uint)),
            checked((uint)fileName.Length));
        fileName.CopyTo(renameInfo, nameOffset);
        int status;
        unsafe
        {
            fixed (byte* renamePointer = renameInfo)
            {
                status = NtSetInformationFile(
                    source.Handle,
                    out _,
                    renamePointer,
                    checked((uint)renameInfo.Length),
                    NtFileRenameInformation);
            }
        }

        if (status < 0)
        {
            if (!replace && status == StatusObjectNameCollision)
            {
                return false;
            }

            throw UnsafePath();
        }

        ValidateFileHandle(source.Handle, destinationPath);
        source.UpdatePath(destinationPath);
        return true;
    }

    public static void Delete(WindowsPrivateFileLease file)
    {
        ArgumentNullException.ThrowIfNull(file);
        if (!file.CanRename)
        {
            throw UnsafePath();
        }

        ValidateFileHandle(file.Handle, file.Path);
        byte disposition = 1;
        bool deleted;
        unsafe
        {
            deleted = SetFileInformationByHandle(
                file.Handle,
                fileInformationClass: 4,
                &disposition,
                bufferSize: 1);
        }

        if (!deleted)
        {
            throw UnsafePath();
        }
    }

    internal static void ValidateFileHandle(SafeFileHandle handle, string expectedPath)
    {
        if (handle.IsInvalid
            || GetFileType(handle) != FileTypeDisk
            || !GetFileInformationByHandleEx(
                handle,
                FileAttributeTagInfo,
                out FileAttributeTagInformation attributes,
                checked((uint)Marshal.SizeOf<FileAttributeTagInformation>()))
            || (attributes.FileAttributes & (uint)(FileAttributes.Directory | FileAttributes.ReparsePoint)) != 0
            || !GetFileInformationByHandle(handle, out ByHandleFileInformation information)
            || information.NumberOfLinks != 1)
        {
            throw UnsafePath();
        }

        EnsureExpectedFinalPath(handle, expectedPath);
        EnsureTrustedOwner(handle);
    }

    private static SafeFileHandle OpenAndValidateDirectory(string path, bool protectAcl)
    {
        uint desiredAccess = FileTraverse | FileReadAttributes | ReadControl;
        if (protectAcl)
        {
            desiredAccess |= WriteDac;
        }

        SafeFileHandle handle = CreateFile(
            path,
            desiredAccess,
            FileShareRead | FileShareWrite,
            0,
            OpenExisting,
            FileFlagBackupSemantics | FileFlagOpenReparsePoint,
            0);
        try
        {
            ValidateDirectoryHandle(handle, path);
            if (protectAcl)
            {
                EnsureTrustedOwner(handle);
                ApplyPrivateDacl(handle, directory: true);
            }

            return handle;
        }
        catch
        {
            handle.Dispose();
            throw;
        }
    }

    internal static void ValidateDirectoryHandle(SafeFileHandle handle, string expectedPath)
    {
        if (handle.IsInvalid
            || GetFileType(handle) != FileTypeDisk
            || !GetFileInformationByHandleEx(
                handle,
                FileAttributeTagInfo,
                out FileAttributeTagInformation attributes,
                checked((uint)Marshal.SizeOf<FileAttributeTagInformation>()))
            || (attributes.FileAttributes & (uint)FileAttributes.Directory) == 0
            || (attributes.FileAttributes & (uint)FileAttributes.ReparsePoint) != 0)
        {
            throw UnsafePath();
        }

        EnsureExpectedFinalPath(handle, expectedPath);
    }

    private static void ApplyPrivateDacl(SafeFileHandle handle, bool directory)
    {
        nint descriptor = CreatePrivateSecurityDescriptor(directory);
        try
        {
            if (!SetKernelObjectSecurity(handle, DaclSecurityInformation, descriptor))
            {
                throw UnsafePath();
            }

            EnsureProtectedDacl(handle);
        }
        finally
        {
            _ = LocalFree(descriptor);
        }
    }

    private static void CreatePrivateDirectory(string path)
    {
        nint descriptor = CreatePrivateSecurityDescriptor(directory: true);
        try
        {
            var attributes = new SecurityAttributes
            {
                Length = checked((uint)Marshal.SizeOf<SecurityAttributes>()),
                SecurityDescriptor = descriptor,
                InheritHandle = 0,
            };
            if (!CreateDirectory(path, ref attributes))
            {
                int error = Marshal.GetLastPInvokeError();
                if (error != ErrorAlreadyExists)
                {
                    throw UnsafePath();
                }
            }
        }
        finally
        {
            _ = LocalFree(descriptor);
        }
    }

    private static nint CreatePrivateSecurityDescriptor(bool directory)
    {
        string inheritance = directory ? "OICI" : string.Empty;
        string sddl = string.Concat(
            "D:P(A;", inheritance, ";FA;;;SY)(A;", inheritance,
            ";FA;;;", CurrentUserSid, ")");
        if (!ConvertStringSecurityDescriptorToSecurityDescriptor(
                sddl,
                stringSdRevision: 1,
                out nint descriptor,
                out _))
        {
            throw UnsafePath();
        }

        return descriptor;
    }

    private static void EnsureTrustedOwner(SafeFileHandle handle)
    {
        uint status = GetSecurityInfo(
            handle,
            SeFileObject,
            OwnerSecurityInformation,
            out nint owner,
            out _,
            out _,
            out _,
            out nint descriptor);
        if (status != 0 || descriptor == 0 || owner == 0)
        {
            if (descriptor != 0)
            {
                _ = LocalFree(descriptor);
            }

            throw UnsafePath();
        }

        try
        {
            string ownerSid = SidToString(owner);
            if (!string.Equals(ownerSid, CurrentUserSid, StringComparison.Ordinal)
                && !string.Equals(ownerSid, "S-1-5-18", StringComparison.Ordinal)
                && !string.Equals(ownerSid, "S-1-5-32-544", StringComparison.Ordinal))
            {
                throw UnsafePath();
            }
        }
        finally
        {
            _ = LocalFree(descriptor);
        }
    }

    private static void EnsureProtectedDacl(SafeFileHandle handle)
    {
        uint status = GetSecurityInfo(
            handle,
            SeFileObject,
            DaclSecurityInformation,
            out _,
            out _,
            out _,
            out _,
            out nint descriptor);
        if (status != 0 || descriptor == 0)
        {
            if (descriptor != 0)
            {
                _ = LocalFree(descriptor);
            }

            throw UnsafePath();
        }

        try
        {
            if (!GetSecurityDescriptorControl(descriptor, out ushort control, out _)
                || (control & SeDaclProtected) == 0)
            {
                throw UnsafePath();
            }
        }
        finally
        {
            _ = LocalFree(descriptor);
        }
    }

    private static void EnsureExpectedFinalPath(SafeFileHandle handle, string expectedPath)
    {
        char[] buffer = new char[MaximumFinalPathCharacters];
        uint length = GetFinalPathNameByHandle(
            handle,
            buffer,
            checked((uint)buffer.Length),
            flags: 0);
        if (length == 0 || length >= buffer.Length)
        {
            throw UnsafePath();
        }

        string actual = NormalizeFinalPath(new string(buffer, 0, checked((int)length)));
        string expected = Path.TrimEndingDirectorySeparator(Path.GetFullPath(expectedPath));
        if (!string.Equals(actual, expected, StringComparison.OrdinalIgnoreCase))
        {
            throw UnsafePath();
        }
    }

    private static string NormalizeFinalPath(string path)
    {
        const string extendedUnc = @"\\?\UNC\";
        const string extendedDos = @"\\?\";
        if (path.StartsWith(extendedUnc, StringComparison.OrdinalIgnoreCase))
        {
            path = string.Concat(@"\\", path.AsSpan(extendedUnc.Length));
        }
        else if (path.StartsWith(extendedDos, StringComparison.OrdinalIgnoreCase))
        {
            path = path[extendedDos.Length..];
        }

        return Path.TrimEndingDirectorySeparator(path);
    }

    private static string NormalizeLocalPath(string path, bool requireFileName)
    {
        if (string.IsNullOrWhiteSpace(path)
            || path.StartsWith(@"\\", StringComparison.Ordinal)
            || !Path.IsPathFullyQualified(path))
        {
            throw UnsafePath();
        }

        string fullPath;
        try
        {
            fullPath = Path.GetFullPath(path);
        }
        catch (Exception exception) when (exception is ArgumentException
            or NotSupportedException
            or PathTooLongException)
        {
            throw UnsafePath();
        }

        string? root = Path.GetPathRoot(fullPath);
        if (root is null
            || root.Length != 3
            || fullPath.AsSpan(root.Length).Contains(Path.VolumeSeparatorChar)
            || (requireFileName && string.IsNullOrEmpty(Path.GetFileName(fullPath))))
        {
            throw UnsafePath();
        }

        return Path.TrimEndingDirectorySeparator(fullPath);
    }

    private static void ValidateFileName(string fileName)
    {
        if (string.IsNullOrWhiteSpace(fileName)
            || fileName.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0
            || !string.Equals(Path.GetFileName(fileName), fileName, StringComparison.Ordinal))
        {
            throw UnsafePath();
        }
    }

    private static uint ToNativeShare(FileShare share)
    {
        const FileShare supported = FileShare.Read | FileShare.Write | FileShare.Delete;
        if ((share & ~supported) != 0)
        {
            throw new ArgumentOutOfRangeException(nameof(share));
        }

        uint result = 0;
        if ((share & FileShare.Read) != 0)
        {
            result |= FileShareRead;
        }

        if ((share & FileShare.Write) != 0)
        {
            result |= FileShareWrite;
        }

        if ((share & FileShare.Delete) != 0)
        {
            result |= FileShareDelete;
        }

        return result;
    }

    private static string SidToString(nint sid)
    {
        if (!ConvertSidToStringSid(sid, out nint text) || text == 0)
        {
            throw UnsafePath();
        }

        try
        {
            return Marshal.PtrToStringUni(text) ?? throw UnsafePath();
        }
        finally
        {
            _ = LocalFree(text);
        }
    }

    private static string GetCurrentUserSid()
    {
        try
        {
            return WindowsIdentity.GetCurrent().User?.Value ?? throw UnsafePath();
        }
        catch (SystemException)
        {
            throw UnsafePath();
        }
    }

    private static void EnsureWindows()
    {
        if (!OperatingSystem.IsWindows())
        {
            throw UnsafePath();
        }
    }

    private static UnsafePrivateStoragePathException UnsafePath() => new();

    [StructLayout(LayoutKind.Sequential)]
    private struct FileAttributeTagInformation
    {
        public uint FileAttributes;
        public uint ReparseTag;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct FileTime
    {
        public uint LowDateTime;
        public uint HighDateTime;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ByHandleFileInformation
    {
        public uint FileAttributes;
        public FileTime CreationTime;
        public FileTime LastAccessTime;
        public FileTime LastWriteTime;
        public uint VolumeSerialNumber;
        public uint FileSizeHigh;
        public uint FileSizeLow;
        public uint NumberOfLinks;
        public uint FileIndexHigh;
        public uint FileIndexLow;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct IoStatusBlock
    {
        public nint Status;
        public nuint Information;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct SecurityAttributes
    {
        public uint Length;
        public nint SecurityDescriptor;
        public int InheritHandle;
    }

    [LibraryImport("kernel32.dll", EntryPoint = "CreateFileW", SetLastError = true,
        StringMarshalling = StringMarshalling.Utf16)]
    private static partial SafeFileHandle CreateFile(
        string fileName,
        uint desiredAccess,
        uint shareMode,
        nint securityAttributes,
        uint creationDisposition,
        uint flagsAndAttributes,
        nint templateFile);

    [LibraryImport("kernel32.dll", EntryPoint = "CreateDirectoryW", SetLastError = true,
        StringMarshalling = StringMarshalling.Utf16)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool CreateDirectory(
        string path,
        ref SecurityAttributes securityAttributes);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetFileInformationByHandleEx(
        SafeFileHandle file,
        int fileInformationClass,
        out FileAttributeTagInformation fileInformation,
        uint bufferSize);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetFileInformationByHandle(
        SafeFileHandle file,
        out ByHandleFileInformation information);

    [LibraryImport("kernel32.dll")]
    private static partial uint GetFileType(SafeFileHandle file);

    [LibraryImport("kernel32.dll", EntryPoint = "GetFinalPathNameByHandleW", SetLastError = true,
        StringMarshalling = StringMarshalling.Utf16)]
    private static partial uint GetFinalPathNameByHandle(
        SafeFileHandle file,
        [Out] char[] path,
        uint pathLength,
        uint flags);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static unsafe partial bool SetFileInformationByHandle(
        SafeFileHandle file,
        int fileInformationClass,
        void* fileInformation,
        uint bufferSize);

    [LibraryImport("ntdll.dll")]
    private static unsafe partial int NtSetInformationFile(
        SafeFileHandle file,
        out IoStatusBlock ioStatusBlock,
        void* fileInformation,
        uint length,
        int fileInformationClass);

    [LibraryImport("advapi32.dll", EntryPoint = "ConvertStringSecurityDescriptorToSecurityDescriptorW",
        SetLastError = true, StringMarshalling = StringMarshalling.Utf16)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool ConvertStringSecurityDescriptorToSecurityDescriptor(
        string stringSecurityDescriptor,
        uint stringSdRevision,
        out nint securityDescriptor,
        out uint securityDescriptorSize);

    [LibraryImport("advapi32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetKernelObjectSecurity(
        SafeFileHandle handle,
        uint securityInformation,
        nint securityDescriptor);

    [LibraryImport("advapi32.dll")]
    private static partial uint GetSecurityInfo(
        SafeFileHandle handle,
        int objectType,
        uint securityInformation,
        out nint owner,
        out nint group,
        out nint dacl,
        out nint sacl,
        out nint securityDescriptor);

    [LibraryImport("advapi32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetSecurityDescriptorControl(
        nint securityDescriptor,
        out ushort control,
        out uint revision);

    [LibraryImport("advapi32.dll", EntryPoint = "ConvertSidToStringSidW", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool ConvertSidToStringSid(nint sid, out nint stringSid);

    [LibraryImport("kernel32.dll")]
    private static partial nint LocalFree(nint memory);
}

public sealed class WindowsPrivateDirectoryLease : IDisposable
{
    private readonly IReadOnlyList<SafeFileHandle> _handles;
    private bool _disposed;

    internal WindowsPrivateDirectoryLease(string path, IReadOnlyList<SafeFileHandle> handles)
    {
        Path = path;
        _handles = handles;
    }

    public string Path { get; }

    internal SafeFileHandle LeafHandle => !_disposed
        ? _handles[^1]
        : throw new ObjectDisposedException(nameof(WindowsPrivateDirectoryLease));

    internal void Validate() => WindowsPrivateStorage.ValidateDirectoryHandle(LeafHandle, Path);

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        for (int index = _handles.Count - 1; index >= 0; index--)
        {
            _handles[index].Dispose();
        }
    }
}

public sealed class WindowsPrivateFileLease : IDisposable
{
    private readonly WindowsPrivateDirectoryLease _directory;
    private readonly FileStream _stream;
    private bool _disposed;

    internal WindowsPrivateFileLease(
        string path,
        WindowsPrivateDirectoryLease directory,
        FileStream stream,
        bool canRename)
    {
        Path = path;
        _directory = directory;
        _stream = stream;
        CanRename = canRename;
    }

    public string Path { get; private set; }

    public FileStream Stream => !_disposed
        ? _stream
        : throw new ObjectDisposedException(nameof(WindowsPrivateFileLease));

    internal bool CanRename { get; }

    internal SafeFileHandle Handle => Stream.SafeFileHandle;

    internal SafeFileHandle DirectoryHandle => _directory.LeafHandle;

    internal string DirectoryPath => _directory.Path;

    internal void FlushToDisk() => Stream.Flush(flushToDisk: true);

    internal void UpdatePath(string path) => Path = path;

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        _stream.Dispose();
        _directory.Dispose();
    }
}

public sealed class UnsafePrivateStoragePathException : IOException
{
    internal UnsafePrivateStoragePathException()
        : base("Private storage path validation failed.")
    {
    }
}
