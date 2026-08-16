using System.Runtime.InteropServices;
using System.Security;
using System.Text;

namespace Baxy.Security.Windows;

internal static partial class ProtectedPayloadPathPolicy
{
    private const int MaximumPathUtf8Length = 32 * 1024;
    private const uint DriveFixed = 3;
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);

    public static string ValidateAndNormalize(string path)
    {
        if (!OperatingSystem.IsWindows()
            || string.IsNullOrWhiteSpace(path)
            || path.StartsWith(@"\\", StringComparison.Ordinal)
            || !Path.IsPathFullyQualified(path))
        {
            throw InvalidPath();
        }

        try
        {
            string? inputRoot = Path.GetPathRoot(path);
            if (string.IsNullOrEmpty(inputRoot))
            {
                throw InvalidPath();
            }

            EnsureSegmentsAreSafe(path, inputRoot);
            string fullPath = Path.GetFullPath(path);
            string? root = Path.GetPathRoot(fullPath);
            if (root is null
                || root.Length != 3
                || !char.IsAsciiLetter(root[0])
                || root[1] != Path.VolumeSeparatorChar
                || root[2] != Path.DirectorySeparatorChar
                || fullPath.Length <= root.Length
                || fullPath.EndsWith(Path.DirectorySeparatorChar)
                || fullPath.EndsWith(Path.AltDirectorySeparatorChar)
                || fullPath.AsSpan(2).Contains(Path.VolumeSeparatorChar)
                || StrictUtf8.GetByteCount(fullPath) > MaximumPathUtf8Length)
            {
                throw InvalidPath();
            }

            EnsureRootIsFixedDrive(root);
            EnsureSegmentsAreSafe(fullPath, root);
            EnsureExistingPathHasNoReparsePoints(fullPath);
            return fullPath;
        }
        catch (ProtectedPayloadException)
        {
            throw;
        }
        catch (Exception exception) when (exception is ArgumentException
            or NotSupportedException
            or PathTooLongException
            or SecurityException
            or IOException
            or UnauthorizedAccessException
            or EncoderFallbackException)
        {
            throw InvalidPath();
        }
    }

    private static void EnsureRootIsFixedDrive(string root)
    {
        uint driveType;
        try
        {
            driveType = GetDriveType(root);
        }
        catch (Exception exception) when (exception is DllNotFoundException
            or EntryPointNotFoundException)
        {
            throw InvalidPath();
        }

        if (driveType != DriveFixed)
        {
            throw InvalidPath();
        }
    }

    public static void EnsureExistingPathHasNoReparsePoints(string fullPath)
    {
        string root = Path.GetPathRoot(fullPath)!;
        string current = root;
        ReadOnlySpan<char> relative = fullPath.AsSpan(root.Length);
        foreach (Range range in relative.SplitAny(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar))
        {
            ReadOnlySpan<char> segment = relative[range];
            if (segment.IsEmpty)
            {
                continue;
            }

            current = Path.Combine(current, segment.ToString());
            try
            {
                FileAttributes attributes = File.GetAttributes(current);
                if ((attributes & FileAttributes.ReparsePoint) != 0)
                {
                    throw InvalidPath();
                }
            }
            catch (FileNotFoundException)
            {
                break;
            }
            catch (DirectoryNotFoundException)
            {
                break;
            }
        }
    }

    private static void EnsureSegmentsAreSafe(string fullPath, string root)
    {
        ReadOnlySpan<char> relative = fullPath.AsSpan(root.Length);
        foreach (Range range in relative.SplitAny(
            Path.DirectorySeparatorChar,
            Path.AltDirectorySeparatorChar))
        {
            ReadOnlySpan<char> segment = relative[range];
            if (segment.IsEmpty
                || segment[^1] is ' ' or '.'
                || ContainsInvalidWindowsFileNameCharacter(segment)
                || IsReservedDosDeviceName(segment))
            {
                throw InvalidPath();
            }
        }
    }

    private static bool ContainsInvalidWindowsFileNameCharacter(ReadOnlySpan<char> segment)
    {
        foreach (char character in segment)
        {
            if (character < ' '
                || character is '<' or '>' or ':' or '"' or '/' or '\\' or '|' or '?' or '*')
            {
                return true;
            }
        }

        return false;
    }

    private static bool IsReservedDosDeviceName(ReadOnlySpan<char> segment)
    {
        int extensionIndex = segment.IndexOf('.');
        ReadOnlySpan<char> baseName = extensionIndex >= 0 ? segment[..extensionIndex] : segment;
        if (baseName.Equals("CON", StringComparison.OrdinalIgnoreCase)
            || baseName.Equals("PRN", StringComparison.OrdinalIgnoreCase)
            || baseName.Equals("AUX", StringComparison.OrdinalIgnoreCase)
            || baseName.Equals("NUL", StringComparison.OrdinalIgnoreCase))
        {
            return true;
        }

        return baseName.Length == 4
            && (baseName[..3].Equals("COM", StringComparison.OrdinalIgnoreCase)
                || baseName[..3].Equals("LPT", StringComparison.OrdinalIgnoreCase))
            && baseName[3] is >= '1' and <= '9';
    }

    private static ProtectedPayloadException InvalidPath() =>
        new(ProtectedPayloadErrorCode.InvalidKeyStorePath);

    [LibraryImport("kernel32.dll", EntryPoint = "GetDriveTypeW", StringMarshalling = StringMarshalling.Utf16)]
    private static partial uint GetDriveType(string rootPathName);
}
