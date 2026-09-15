using System.Security;
using Baxy.Providers.Windows.Infrastructure;

namespace Baxy.Providers.Windows.Applications;

internal sealed record NotepadLaunchTarget(
    string BootstrapExecutablePath,
    string ProgramFilesDirectory,
    IApplicationPathTrust PathTrust);

internal interface IApplicationPathTrust
{
    bool IsExistingPathWithoutReparse(string path);
}

internal sealed class SystemApplicationPathTrust : IApplicationPathTrust
{
    public static SystemApplicationPathTrust Instance { get; } = new();

    private SystemApplicationPathTrust()
    {
    }

    public bool IsExistingPathWithoutReparse(string path) =>
        SafePathPolicy.IsExistingPathWithoutReparse(path);
}

internal sealed record ApplicationProcessObservation(
    int ProcessId,
    long CreationTimeUtcTicks,
    string ExecutablePath,
    string? PackageFamilyName,
    string? PackageFullName,
    nint WindowHandle,
    bool WindowVisible,
    bool Foreground);

internal sealed class ApplicationInventoryException : Exception
{
    public ApplicationInventoryException(string message)
        : base(message)
    {
    }

    public ApplicationInventoryException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

internal sealed class ApplicationProcessExitedException : Exception
{
    public ApplicationProcessExitedException()
        : base("The observed process exited.")
    {
    }
}

internal static class NotepadIdentityPolicy
{
    internal const string PackageFamilyName =
        "Microsoft.WindowsNotepad_8wekyb3d8bbwe";
    internal const string PackageNamePrefix = "Microsoft.WindowsNotepad_";
    internal const string MicrosoftPublisherId = "8wekyb3d8bbwe";
    internal const string PackagedExecutableRelativePath = @"Notepad\Notepad.exe";

    public static bool IsAllowed(
        ApplicationProcessObservation observation,
        NotepadLaunchTarget target)
    {
        if (string.IsNullOrEmpty(observation.PackageFamilyName)
            && string.IsNullOrEmpty(observation.PackageFullName))
        {
            return PathsEqual(
                observation.ExecutablePath,
                target.BootstrapExecutablePath);
        }

        if (!string.Equals(
                observation.PackageFamilyName,
                PackageFamilyName,
                StringComparison.Ordinal)
            || !IsExplicitMicrosoftPackageFullName(observation.PackageFullName))
        {
            return false;
        }

        try
        {
            string expectedPath = Path.GetFullPath(
                Path.Combine(
                    target.ProgramFilesDirectory,
                    "WindowsApps",
                    observation.PackageFullName!,
                    PackagedExecutableRelativePath));

            return PathsEqual(observation.ExecutablePath, expectedPath)
                && target.PathTrust.IsExistingPathWithoutReparse(expectedPath);
        }
        catch (Exception exception) when (exception is ArgumentException
            or NotSupportedException
            or PathTooLongException
            or SecurityException
            or IOException
            or UnauthorizedAccessException)
        {
            return false;
        }
    }

    public static bool MatchesReceipt(
        ApplicationProcessObservation observation,
        ApplicationLaunchReceipt receipt)
    {
        return receipt.ProcessId == observation.ProcessId
            && receipt.ProcessCreationTimeUtcTicks == observation.CreationTimeUtcTicks
            && PathsEqual(receipt.ExecutablePath, observation.ExecutablePath)
            && string.Equals(
                receipt.PackageFamilyName,
                observation.PackageFamilyName,
                StringComparison.Ordinal)
            && string.Equals(
                receipt.PackageFullName,
                observation.PackageFullName,
                StringComparison.Ordinal);
    }

    private static bool IsExplicitMicrosoftPackageFullName(string? packageFullName)
    {
        if (string.IsNullOrWhiteSpace(packageFullName)
            || packageFullName.IndexOfAny(['\\', '/']) >= 0
            || !packageFullName.StartsWith(PackageNamePrefix, StringComparison.Ordinal)
            || !packageFullName.EndsWith(
                $"_{MicrosoftPublisherId}",
                StringComparison.Ordinal))
        {
            return false;
        }

        string[] fields = packageFullName.Split('_');
        string[] versionFields = fields.Length > 1
            ? fields[1].Split('.')
            : [];
        return fields.Length == 5
            && string.Equals(fields[0], "Microsoft.WindowsNotepad", StringComparison.Ordinal)
            && versionFields.Length == 4
            && versionFields.All(static value =>
                value.Length > 0 && value.All(char.IsAsciiDigit))
            && fields[2] is "x64" or "x86" or "arm64"
            && fields[3].Length == 0
            && string.Equals(fields[4], MicrosoftPublisherId, StringComparison.Ordinal);
    }

    private static bool PathsEqual(string? left, string? right)
    {
        if (string.IsNullOrWhiteSpace(left) || string.IsNullOrWhiteSpace(right))
        {
            return false;
        }

        try
        {
            return string.Equals(
                Path.GetFullPath(left),
                Path.GetFullPath(right),
                StringComparison.OrdinalIgnoreCase);
        }
        catch (Exception exception) when (exception is ArgumentException
            or NotSupportedException
            or PathTooLongException)
        {
            return false;
        }
    }
}
