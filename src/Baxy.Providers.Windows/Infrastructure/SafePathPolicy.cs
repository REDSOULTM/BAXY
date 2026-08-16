using System.Security;

namespace Baxy.Providers.Windows.Infrastructure;

internal static class SafePathPolicy
{
    public static string NormalizeAndValidateExistingFile(string path)
    {
        string fullPath = NormalizeAbsolute(path);
        if (!File.Exists(fullPath) || !IsExistingPathWithoutReparse(fullPath))
        {
            throw new FileNotFoundException("The trusted executable path is unavailable.", fullPath);
        }

        return fullPath;
    }

    public static string NormalizeAndCreatePrivateDirectory(string path)
    {
        string fullPath = NormalizeAbsolute(path);
        ValidateExistingAncestors(fullPath);
        Directory.CreateDirectory(fullPath);
        if (!IsExistingPathWithoutReparse(fullPath))
        {
            throw new IOException("The state directory contains a reparse point.");
        }

        return Path.TrimEndingDirectorySeparator(fullPath);
    }

    public static bool IsExistingPathWithoutReparse(string path)
    {
        try
        {
            string fullPath = NormalizeAbsolute(path);
            string? root = Path.GetPathRoot(fullPath);
            if (string.IsNullOrEmpty(root))
            {
                return false;
            }

            string current = root;
            string relative = Path.GetRelativePath(root, fullPath);
            foreach (string component in relative.Split(
                Path.DirectorySeparatorChar,
                StringSplitOptions.RemoveEmptyEntries))
            {
                current = Path.Combine(current, component);
                FileAttributes attributes = File.GetAttributes(current);
                if ((attributes & FileAttributes.ReparsePoint) != 0)
                {
                    return false;
                }
            }

            return true;
        }
        catch (Exception exception) when (exception is ArgumentException
            or NotSupportedException
            or PathTooLongException
            or IOException
            or UnauthorizedAccessException
            or SecurityException)
        {
            return false;
        }
    }

    private static string NormalizeAbsolute(string path)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        string fullPath = Path.GetFullPath(path);
        if (!Path.IsPathFullyQualified(fullPath))
        {
            throw new ArgumentException("The path must be absolute.", nameof(path));
        }

        return fullPath;
    }

    private static void ValidateExistingAncestors(string fullPath)
    {
        string? candidate = fullPath;
        while (!string.IsNullOrEmpty(candidate) && !Directory.Exists(candidate))
        {
            candidate = Path.GetDirectoryName(candidate);
        }

        if (string.IsNullOrEmpty(candidate)
            || !IsExistingPathWithoutReparse(candidate))
        {
            throw new IOException("The state directory ancestry is not trusted.");
        }
    }
}
