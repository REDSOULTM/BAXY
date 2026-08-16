namespace Baxy.Integration.Tests;

internal static class PrivateDataRootTestSupport
{
    internal static string NewPath(string prefix)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(prefix);
        if (!string.Equals(Path.GetFileName(prefix), prefix, StringComparison.Ordinal))
        {
            throw new ArgumentException("The test data-root prefix must be one path component.", nameof(prefix));
        }

        return Path.Combine(
            Environment.GetFolderPath(
                Environment.SpecialFolder.LocalApplicationData,
                Environment.SpecialFolderOption.DoNotVerify),
            "BAXY",
            $"{prefix}-{Guid.NewGuid():N}");
    }
}
