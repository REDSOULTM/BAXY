using System.Globalization;
using System.Numerics;
using System.Text.RegularExpressions;

namespace Baxy.Setup;

internal static partial class SemanticVersionComparer
{
    internal static bool IsValid(string? version) =>
        version is not null &&
        version.Length <= PackageContract.MaximumVersionLength &&
        SemVerRegex().IsMatch(version);

    internal static int ComparePrecedence(string left, string right)
    {
        ParsedVersion leftVersion = Parse(left);
        ParsedVersion rightVersion = Parse(right);
        int comparison = leftVersion.Major.CompareTo(rightVersion.Major);
        if (comparison != 0)
        {
            return comparison;
        }

        comparison = leftVersion.Minor.CompareTo(rightVersion.Minor);
        if (comparison != 0)
        {
            return comparison;
        }

        comparison = leftVersion.Patch.CompareTo(rightVersion.Patch);
        if (comparison != 0)
        {
            return comparison;
        }

        if (leftVersion.PreRelease.Length == 0 || rightVersion.PreRelease.Length == 0)
        {
            return leftVersion.PreRelease.Length == rightVersion.PreRelease.Length
                ? 0
                : leftVersion.PreRelease.Length == 0 ? 1 : -1;
        }

        int shared = Math.Min(leftVersion.PreRelease.Length, rightVersion.PreRelease.Length);
        for (int index = 0; index < shared; index++)
        {
            string leftIdentifier = leftVersion.PreRelease[index];
            string rightIdentifier = rightVersion.PreRelease[index];
            bool leftNumeric = IsNumeric(leftIdentifier);
            bool rightNumeric = IsNumeric(rightIdentifier);
            if (leftNumeric && rightNumeric)
            {
                comparison = BigInteger.Parse(leftIdentifier, CultureInfo.InvariantCulture).CompareTo(
                    BigInteger.Parse(rightIdentifier, CultureInfo.InvariantCulture));
            }
            else if (leftNumeric != rightNumeric)
            {
                comparison = leftNumeric ? -1 : 1;
            }
            else
            {
                comparison = StringComparer.Ordinal.Compare(leftIdentifier, rightIdentifier);
            }

            if (comparison != 0)
            {
                return comparison;
            }
        }

        return leftVersion.PreRelease.Length.CompareTo(rightVersion.PreRelease.Length);
    }

    private static ParsedVersion Parse(string version)
    {
        int buildIndex = version.IndexOf('+', StringComparison.Ordinal);
        string withoutBuild = buildIndex >= 0 ? version[..buildIndex] : version;
        int prereleaseIndex = withoutBuild.IndexOf('-', StringComparison.Ordinal);
        string core = prereleaseIndex >= 0 ? withoutBuild[..prereleaseIndex] : withoutBuild;
        string[] coreParts = core.Split('.');
        string[] prerelease = prereleaseIndex >= 0
            ? withoutBuild[(prereleaseIndex + 1)..].Split('.')
            : [];
        return new ParsedVersion(
            BigInteger.Parse(coreParts[0], CultureInfo.InvariantCulture),
            BigInteger.Parse(coreParts[1], CultureInfo.InvariantCulture),
            BigInteger.Parse(coreParts[2], CultureInfo.InvariantCulture),
            prerelease);
    }

    private static bool IsNumeric(string value) => value.All(static character => character is >= '0' and <= '9');

    private sealed record ParsedVersion(
        BigInteger Major,
        BigInteger Minor,
        BigInteger Patch,
        string[] PreRelease);

    [GeneratedRegex(
        @"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-(0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)(\.(0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*)?(\+[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?\z",
        RegexOptions.CultureInvariant)]
    private static partial Regex SemVerRegex();
}
