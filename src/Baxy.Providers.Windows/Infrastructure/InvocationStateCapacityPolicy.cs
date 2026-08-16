namespace Baxy.Providers.Windows.Infrastructure;

internal enum InvocationStateCapacityViolation
{
    None,
    ReparsePoint,
    Capacity,
}

internal static class InvocationStateCapacityPolicy
{
    public static InvocationStateCapacityViolation Evaluate(
        string stateDirectory,
        string targetPath,
        long replacementBytes,
        int maximumInvocationCount,
        long maximumTotalStateBytes)
    {
        ArgumentOutOfRangeException.ThrowIfNegative(replacementBytes);
        ArgumentOutOfRangeException.ThrowIfNegative(maximumInvocationCount);
        ArgumentOutOfRangeException.ThrowIfNegative(maximumTotalStateBytes);

        int count = 0;
        long totalBytes = 0;
        long replacedBytes = 0;
        bool targetFound = false;

        // Every top-level JSON participates in the quota, including files created
        // outside BAXY. Enumerating is the integrity check: an in-place child resize
        // does not update a reliable aggregate token on its parent directory.
        foreach (string path in Directory.EnumerateFileSystemEntries(
            stateDirectory,
            "*.json",
            SearchOption.TopDirectoryOnly))
        {
            FileAttributes attributes = File.GetAttributes(path);
            if ((attributes & FileAttributes.ReparsePoint) != 0)
            {
                return InvocationStateCapacityViolation.ReparsePoint;
            }

            if ((attributes & FileAttributes.Directory) != 0)
            {
                continue;
            }

            FileInfo file = new(path);
            count++;
            totalBytes = checked(totalBytes + file.Length);
            if (string.Equals(path, targetPath, StringComparison.OrdinalIgnoreCase))
            {
                targetFound = true;
                replacedBytes = file.Length;
            }

            if (count > maximumInvocationCount || totalBytes > maximumTotalStateBytes)
            {
                return InvocationStateCapacityViolation.Capacity;
            }
        }

        int resultingCount = targetFound ? count : count + 1;
        long resultingBytes = checked(totalBytes - replacedBytes + replacementBytes);
        return resultingCount > maximumInvocationCount
            || resultingBytes > maximumTotalStateBytes
                ? InvocationStateCapacityViolation.Capacity
                : InvocationStateCapacityViolation.None;
    }
}
