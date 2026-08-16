using System.ComponentModel;
using Microsoft.Win32.SafeHandles;
using System.Runtime.InteropServices;
using System.Text;

namespace Baxy.Setup;

internal sealed record SafeFileTree(IReadOnlyList<string> Files, IReadOnlyList<string> Directories);

internal static partial class PathSafety
{
    private const int ErrorNoMoreFiles = 18;
    private const int ErrorHandleEof = 38;
    private static readonly nint InvalidHandleValue = new(-1);

    internal static string ValidateInstallationRoot(string root)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(root);
        if (!Path.IsPathFullyQualified(root))
        {
            throw new InstallationSafetyException("The installation root must be an absolute path supplied by the caller.");
        }

        string fullPath = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        string? volumeRoot = Path.GetPathRoot(fullPath)?.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        if (string.IsNullOrEmpty(volumeRoot) || string.Equals(fullPath, volumeRoot, StringComparison.OrdinalIgnoreCase))
        {
            throw new InstallationSafetyException("A filesystem root cannot be used as the BAXY installation root.");
        }

        if (fullPath.Length > 200)
        {
            throw new InstallationSafetyException("The installation root is too long for the reviewed payload layout.");
        }

        AssertExistingChainHasNoReparsePoint(fullPath);
        return fullPath;
    }

    internal static void ValidateRelativePath(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            throw new ProductPackageException("A package path is empty.");
        }

        if (path.Length > PackageContract.MaximumRelativePathLength)
        {
            throw new ProductPackageException($"A package path is too long: {path}");
        }

        if (!string.Equals(path, path.Normalize(NormalizationForm.FormC), StringComparison.Ordinal))
        {
            throw new ProductPackageException($"A package path is not Unicode NFC: {path}");
        }

        if (path.StartsWith('/') || path.EndsWith('/') || path.Contains("//", StringComparison.Ordinal) ||
            path.Contains('\\') || path.Contains(':'))
        {
            throw new ProductPackageException($"A package path uses an unsafe Windows path form: {path}");
        }

        foreach (char character in path)
        {
            if (character <= '\u001f' || character is '<' or '>' or '"' or '|' or '?' or '*')
            {
                throw new ProductPackageException($"A package path contains a forbidden character: {path}");
            }
        }

        foreach (string segment in path.Split('/'))
        {
            if (segment is "." or ".." || segment.Length is 0 or > 255 ||
                segment.EndsWith('.') || segment.EndsWith(' '))
            {
                throw new ProductPackageException($"A package path contains an unsafe segment: {path}");
            }

            string deviceStem = segment.Split('.', 2)[0];
            if (IsReservedDeviceName(deviceStem))
            {
                throw new ProductPackageException($"A package path uses a reserved Windows device name: {path}");
            }
        }
    }

    internal static string GetStrictDescendantPath(string root, string relativePath)
    {
        ValidateRelativePath(relativePath);
        string rootFull = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        string candidate = Path.GetFullPath(Path.Combine(rootFull, relativePath.Replace('/', Path.DirectorySeparatorChar)));
        if (!candidate.StartsWith(rootFull + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
        {
            throw new InstallationSafetyException("A derived installation path escaped its owned root.");
        }

        return candidate;
    }

    internal static void AssertExistingChainHasNoReparsePoint(string path)
    {
        string current = Path.GetFullPath(path);
        while (!string.IsNullOrEmpty(current))
        {
            try
            {
                FileAttributes attributes = File.GetAttributes(current);
                if ((attributes & FileAttributes.ReparsePoint) != 0)
                {
                    throw new InstallationSafetyException($"A filesystem reparse point is forbidden in the installation path: {current}");
                }
            }
            catch (FileNotFoundException)
            {
                // The remaining child path may legitimately not exist yet.
            }
            catch (DirectoryNotFoundException)
            {
                // The remaining child path may legitimately not exist yet.
            }

            DirectoryInfo? parent = Directory.GetParent(current);
            if (parent is null)
            {
                break;
            }

            current = parent.FullName;
        }
    }

    internal static void EnsureOwnedDirectory(string installationRoot, string directory)
    {
        string rootFull = Path.GetFullPath(installationRoot).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        string directoryFull = Path.GetFullPath(directory).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        if (!string.Equals(rootFull, directoryFull, StringComparison.OrdinalIgnoreCase) &&
            !directoryFull.StartsWith(rootFull + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
        {
            throw new InstallationSafetyException("Refusing to create a directory outside the installation root.");
        }

        AssertExistingChainHasNoReparsePoint(directoryFull);
        Directory.CreateDirectory(directoryFull);
        AssertExistingChainHasNoReparsePoint(directoryFull);
        FileAttributes attributes = File.GetAttributes(directoryFull);
        if ((attributes & FileAttributes.Directory) == 0 || (attributes & FileAttributes.ReparsePoint) != 0)
        {
            throw new InstallationSafetyException($"The expected installation directory is unsafe: {directoryFull}");
        }

        AssertNoAlternateDataStreams(directoryFull, isDirectory: true);
    }

    internal static SafeFileTree InspectTree(string root, int maximumEntries = 64)
    {
        string rootFull = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        AssertExistingChainHasNoReparsePoint(rootFull);
        if (!Directory.Exists(rootFull))
        {
            throw new InstallationSafetyException($"An expected installation directory is missing: {rootFull}");
        }

        AssertNoAlternateDataStreams(rootFull, isDirectory: true);
        List<string> files = [];
        List<string> directories = [];
        InspectDirectory(rootFull, rootFull, files, directories, maximumEntries);
        files.Sort(StringComparer.Ordinal);
        directories.Sort(StringComparer.Ordinal);
        return new SafeFileTree(files, directories);
    }

    internal static void DeleteTreeFailClosed(string installationRoot, string target)
    {
        string rootFull = Path.GetFullPath(installationRoot).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        string targetFull = Path.GetFullPath(target).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        if (string.Equals(rootFull, targetFull, StringComparison.OrdinalIgnoreCase) ||
            !targetFull.StartsWith(rootFull + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
        {
            throw new InstallationSafetyException("Refusing to recursively delete outside a strict installation-root descendant.");
        }

        if (!Directory.Exists(targetFull) && !File.Exists(targetFull))
        {
            return;
        }

        AssertExistingChainHasNoReparsePoint(targetFull);
        DeleteEntryFailClosed(targetFull);
    }

    internal static void AssertRegularFile(string path)
    {
        AssertExistingChainHasNoReparsePoint(path);
        FileAttributes attributes = File.GetAttributes(path);
        if ((attributes & (FileAttributes.Directory | FileAttributes.ReparsePoint)) != 0)
        {
            throw new InstallationSafetyException($"An expected regular file is unsafe: {path}");
        }

        AssertNoAlternateDataStreams(path, isDirectory: false);
        AssertSingleLink(path);
    }

    internal static void AssertRegularDirectory(string path)
    {
        AssertExistingChainHasNoReparsePoint(path);
        FileAttributes attributes = File.GetAttributes(path);
        if ((attributes & FileAttributes.Directory) == 0 ||
            (attributes & FileAttributes.ReparsePoint) != 0)
        {
            throw new InstallationSafetyException($"An expected directory is unsafe: {path}");
        }

        AssertNoAlternateDataStreams(path, isDirectory: true);
    }

    private static bool IsReservedDeviceName(string value)
    {
        if (value.Equals("CON", StringComparison.OrdinalIgnoreCase) ||
            value.Equals("PRN", StringComparison.OrdinalIgnoreCase) ||
            value.Equals("AUX", StringComparison.OrdinalIgnoreCase) ||
            value.Equals("NUL", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        if (value.Length != 4)
        {
            return false;
        }

        bool reservedPrefix = value.StartsWith("COM", StringComparison.OrdinalIgnoreCase) ||
            value.StartsWith("LPT", StringComparison.OrdinalIgnoreCase);
        char suffix = value[3];
        return reservedPrefix && (suffix is >= '1' and <= '9' or '\u00b9' or '\u00b2' or '\u00b3');
    }

    private static void InspectDirectory(
        string root,
        string current,
        List<string> files,
        List<string> directories,
        int maximumEntries)
    {
        foreach (string entry in Directory.EnumerateFileSystemEntries(current))
        {
            FileAttributes attributes = File.GetAttributes(entry);
            if ((attributes & FileAttributes.ReparsePoint) != 0)
            {
                throw new InstallationSafetyException($"A reparse point is forbidden in an installation tree: {entry}");
            }

            bool isDirectory = (attributes & FileAttributes.Directory) != 0;
            AssertNoAlternateDataStreams(entry, isDirectory);
            if (!isDirectory)
            {
                AssertSingleLink(entry);
            }
            string relative = Path.GetRelativePath(root, entry).Replace('\\', '/');
            ValidateRelativePath(relative);
            if (isDirectory)
            {
                directories.Add(relative);
                if (files.Count + directories.Count > maximumEntries)
                {
                    throw new InstallationSafetyException("An installation tree exceeds its reviewed entry limit.");
                }

                InspectDirectory(root, entry, files, directories, maximumEntries);
            }
            else
            {
                files.Add(relative);
                if (files.Count + directories.Count > maximumEntries)
                {
                    throw new InstallationSafetyException("An installation tree exceeds its reviewed entry limit.");
                }
            }
        }
    }

    private static void DeleteEntryFailClosed(string path)
    {
        FileAttributes attributes = File.GetAttributes(path);
        if ((attributes & FileAttributes.ReparsePoint) != 0)
        {
            throw new InstallationSafetyException($"Refusing to delete through a reparse point: {path}");
        }

        bool isDirectory = (attributes & FileAttributes.Directory) != 0;
        AssertNoAlternateDataStreams(path, isDirectory);
        if (!isDirectory)
        {
            AssertSingleLink(path);
            File.Delete(path);
            return;
        }

        foreach (string child in Directory.EnumerateFileSystemEntries(path))
        {
            DeleteEntryFailClosed(child);
        }

        Directory.Delete(path, recursive: false);
    }

    private static void AssertNoAlternateDataStreams(string path, bool isDirectory)
    {
        Win32FindStreamData data;
        nint handle = FindFirstStream(path, 0, out data, 0);
        if (handle == InvalidHandleValue)
        {
            int error = Marshal.GetLastWin32Error();
            if (isDirectory && error is ErrorNoMoreFiles or ErrorHandleEof)
            {
                return;
            }

            throw new InstallationSafetyException(
                $"Unable to attest NTFS streams for {path}.",
                new Win32Exception(error));
        }

        int defaultStreamCount = 0;
        try
        {
            do
            {
                if (string.Equals(data.StreamName, "::$DATA", StringComparison.OrdinalIgnoreCase))
                {
                    defaultStreamCount++;
                }
                else
                {
                    throw new InstallationSafetyException($"An alternate data stream is forbidden: {path} [{data.StreamName}]");
                }
            }
            while (FindNextStream(handle, out data));

            int error = Marshal.GetLastWin32Error();
            if (error is not ErrorNoMoreFiles and not ErrorHandleEof)
            {
                throw new InstallationSafetyException(
                    $"Unable to finish attesting NTFS streams for {path}.",
                    new Win32Exception(error));
            }
        }
        finally
        {
            _ = FindClose(handle);
        }

        if (!isDirectory && defaultStreamCount != 1)
        {
            throw new InstallationSafetyException($"A regular file has an unexpected default-stream layout: {path}");
        }
    }

    private static void AssertSingleLink(string path)
    {
        const uint fileReadAttributes = 0x00000080;
        const uint shareAll = 0x00000001 | 0x00000002 | 0x00000004;
        const uint openExisting = 3;
        const uint openReparsePoint = 0x00200000;
        using SafeFileHandle handle = CreateFile(
            path,
            fileReadAttributes,
            shareAll,
            0,
            openExisting,
            openReparsePoint,
            0);
        if (handle.IsInvalid)
        {
            throw new InstallationSafetyException(
                $"Unable to attest the link count for {path}.",
                new Win32Exception(Marshal.GetLastWin32Error()));
        }

        if (!GetFileInformationByHandle(handle, out ByHandleFileInformation information))
        {
            throw new InstallationSafetyException(
                $"Unable to read the link count for {path}.",
                new Win32Exception(Marshal.GetLastWin32Error()));
        }

        if (information.NumberOfLinks != 1)
        {
            throw new InstallationSafetyException($"A hard-linked installation file is forbidden: {path}");
        }
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct Win32FindStreamData
    {
        internal long StreamSize;

        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 296)]
        internal string StreamName;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct ByHandleFileInformation
    {
        internal uint FileAttributes;
        internal System.Runtime.InteropServices.ComTypes.FILETIME CreationTime;
        internal System.Runtime.InteropServices.ComTypes.FILETIME LastAccessTime;
        internal System.Runtime.InteropServices.ComTypes.FILETIME LastWriteTime;
        internal uint VolumeSerialNumber;
        internal uint FileSizeHigh;
        internal uint FileSizeLow;
        internal uint NumberOfLinks;
        internal uint FileIndexHigh;
        internal uint FileIndexLow;
    }

    [DllImport("kernel32.dll", EntryPoint = "FindFirstStreamW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern nint FindFirstStream(
        string fileName,
        int informationLevel,
        out Win32FindStreamData findStreamData,
        int flags);

    [DllImport("kernel32.dll", EntryPoint = "FindNextStreamW", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool FindNextStream(nint findStream, out Win32FindStreamData findStreamData);

    [DllImport("kernel32.dll", EntryPoint = "FindClose", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool FindClose(nint findFile);

    [DllImport("kernel32.dll", EntryPoint = "CreateFileW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFile(
        string fileName,
        uint desiredAccess,
        uint shareMode,
        nint securityAttributes,
        uint creationDisposition,
        uint flagsAndAttributes,
        nint templateFile);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetFileInformationByHandle(
        SafeFileHandle file,
        out ByHandleFileInformation fileInformation);
}
