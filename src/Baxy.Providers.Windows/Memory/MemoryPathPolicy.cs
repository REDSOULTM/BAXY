using System.Security;
using System.Diagnostics.CodeAnalysis;
using Baxy.Security.Windows;

namespace Baxy.Providers.Windows.Memory;

internal static class MemoryPathPolicy
{
    public static string NormalizeRoot(string path)
    {
        try
        {
            ArgumentException.ThrowIfNullOrWhiteSpace(path);
            if (path.StartsWith("\\\\", StringComparison.Ordinal)
                || path.StartsWith("//", StringComparison.Ordinal)
                || !Path.IsPathFullyQualified(path))
            {
                throw new UnsafeMemoryStorePathException();
            }

            string fullPath = Path.GetFullPath(path);
            if (!Path.IsPathFullyQualified(fullPath))
            {
                throw new UnsafeMemoryStorePathException();
            }

            string? root = Path.GetPathRoot(fullPath);
            if (string.IsNullOrEmpty(root)
                || root.StartsWith("\\\\", StringComparison.Ordinal)
                || fullPath.AsSpan(root.Length).Contains(':'))
            {
                throw new UnsafeMemoryStorePathException();
            }

            return Path.TrimEndingDirectorySeparator(fullPath);
        }
        catch (Exception exception) when (exception is ArgumentException
            or NotSupportedException
            or PathTooLongException
            or SecurityException)
        {
            throw new UnsafeMemoryStorePathException();
        }
    }

    public static void CreateAndValidateRoot(string rootDirectory)
    {
        try
        {
            using WindowsPrivateDirectoryLease lease = WindowsPrivateStorage.AcquireDirectory(
                rootDirectory,
                createMissing: true,
                protectLeaf: true);
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or SecurityException)
        {
            throw new UnsafeMemoryStorePathException();
        }
    }

    public static void EnsureDirectory(string path)
    {
        try
        {
            using WindowsPrivateDirectoryLease lease = WindowsPrivateStorage.AcquireDirectory(
                path,
                createMissing: false,
                protectLeaf: true);
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or SecurityException)
        {
            throw new UnsafeMemoryStorePathException();
        }
    }

    public static void EnsureRegularFileIfPresent(string path)
    {
        _ = RegularFileExists(path);
    }

    public static bool RegularFileExists(string path)
    {
        try
        {
            if (!WindowsPrivateStorage.TryOpenFile(
                    path,
                    FileAccess.Read,
                    FileShare.Read,
                    deleteAccess: false,
                    out WindowsPrivateFileLease? file))
            {
                return false;
            }

            file.Dispose();
            return true;
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or SecurityException)
        {
            throw new UnsafeMemoryStorePathException();
        }
    }

    public static bool TryOpenRegularFile(
        string path,
        FileAccess access,
        FileShare share,
        bool deleteAccess,
        [NotNullWhen(true)] out WindowsPrivateFileLease? file)
    {
        try
        {
            return WindowsPrivateStorage.TryOpenFile(
                path,
                access,
                share,
                deleteAccess,
                out file);
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or SecurityException)
        {
            file = null;
            throw new UnsafeMemoryStorePathException();
        }
    }

    public static WindowsPrivateFileLease CreateRegularFile(string path)
    {
        try
        {
            return WindowsPrivateStorage.CreateFile(path);
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or SecurityException)
        {
            throw new UnsafeMemoryStorePathException();
        }
    }

    public static bool RenameRegularFile(
        WindowsPrivateFileLease file,
        string destinationFileName,
        bool replace)
    {
        try
        {
            return WindowsPrivateStorage.Rename(file, destinationFileName, replace);
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or SecurityException)
        {
            throw new UnsafeMemoryStorePathException();
        }
    }

    public static void DeleteRegularFile(WindowsPrivateFileLease file)
    {
        try
        {
            WindowsPrivateStorage.Delete(file);
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or SecurityException)
        {
            throw new UnsafeMemoryStorePathException();
        }
    }

    public static string GetManagedPath(string rootDirectory, string fileName)
    {
        if (string.IsNullOrWhiteSpace(fileName)
            || fileName.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0
            || !string.Equals(Path.GetFileName(fileName), fileName, StringComparison.Ordinal))
        {
            throw new UnsafeMemoryStorePathException();
        }

        string path = Path.GetFullPath(Path.Combine(rootDirectory, fileName));
        string relative = Path.GetRelativePath(rootDirectory, path);
        if (relative.StartsWith("..", StringComparison.Ordinal)
            || Path.IsPathRooted(relative))
        {
            throw new UnsafeMemoryStorePathException();
        }

        return path;
    }

}
