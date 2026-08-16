using System.Security.Cryptography;
using Microsoft.Win32;

namespace Baxy.Setup;

internal sealed record WindowsUninstallRegistrySpecification(
    string InstallId,
    string Version,
    int DataSchema,
    string InstallationRoot,
    string StableSetupHost,
    string StableSetupSha256,
    int EstimatedSizeKilobytes);

internal sealed record WindowsUninstallRegistryExpectedExisting(
    string Version,
    string StableSetupSha256,
    int EstimatedSizeKilobytes);

internal enum WindowsUninstallRegistryProbe
{
    Missing,
    ExactTarget,
    ExactExpectedExisting,
}

internal sealed record WindowsUninstallRegistryValue(object Value, RegistryValueKind Kind);

internal sealed record WindowsUninstallRegistryDeletionValue(
    string Name,
    object Value,
    RegistryValueKind Kind);

internal sealed class WindowsUninstallRegistryDeletionIntent
{
    private readonly IReadOnlyList<string> subkeyNames = Array.Empty<string>();
    private readonly IReadOnlyList<WindowsUninstallRegistryDeletionValue> values;

    private WindowsUninstallRegistryDeletionIntent(
        IEnumerable<KeyValuePair<string, WindowsUninstallRegistryValue>> expectedValues)
    {
        values = Array.AsReadOnly(expectedValues
            .Select(pair => new WindowsUninstallRegistryDeletionValue(
                pair.Key,
                pair.Value.Value,
                pair.Value.Kind))
            .ToArray());
    }

    internal IReadOnlyList<WindowsUninstallRegistryDeletionValue> Values => values;

    internal IReadOnlyList<string> SubkeyNames => subkeyNames;

    internal string InstallId => GetString("BaxyInstallId");

    internal string InstallationRoot => GetString("InstallLocation");

    internal string StableSetupHostSha256 => GetString("BaxyStableSetupSha256");

    internal string UninstallCommand => GetString("UninstallString");

    internal string QuietUninstallCommand => GetString("QuietUninstallString");

    internal static WindowsUninstallRegistryDeletionIntent Capture(
        WindowsUninstallRegistrySnapshot exactExpected) =>
        new(exactExpected.Values);

    internal WindowsUninstallRegistrySnapshot CopyExpectedSnapshot() =>
        new(values.Select(value => new KeyValuePair<string, WindowsUninstallRegistryValue>(
            value.Name,
            new WindowsUninstallRegistryValue(value.Value, value.Kind))));

    private string GetString(string name)
    {
        WindowsUninstallRegistryDeletionValue value = values.Single(value =>
            string.Equals(value.Name, name, StringComparison.Ordinal));
        return value.Kind == RegistryValueKind.String && value.Value is string text
            ? text
            : throw new InstallationSafetyException(
                "A captured uninstall-registry deletion intent is not canonical.");
    }
}

internal sealed class WindowsUninstallRegistrySnapshot
{
    internal WindowsUninstallRegistrySnapshot(
        IEnumerable<KeyValuePair<string, WindowsUninstallRegistryValue>> values,
        IEnumerable<string>? subkeyNames = null)
    {
        Values = new Dictionary<string, WindowsUninstallRegistryValue>(
            values,
            StringComparer.Ordinal);
        SubkeyNames = (subkeyNames ?? [])
            .Order(StringComparer.Ordinal)
            .ToArray();
    }

    internal IReadOnlyDictionary<string, WindowsUninstallRegistryValue> Values { get; }

    internal IReadOnlyList<string> SubkeyNames { get; }
}

internal interface IWindowsUninstallRegistryBackend
{
    WindowsUninstallRegistrySnapshot? Read();

    void CreateWithOwnershipMarkers(string installId, string installationRoot);

    void SetValue(string name, object value, RegistryValueKind kind);

    void DeleteKey();
}

internal sealed class WindowsUninstallRegistry
{
    internal const string CanonicalSubkey =
        @"Software\Microsoft\Windows\CurrentVersion\Uninstall\BAXY";

    private const string DisplayName = "DisplayName";
    private const string DisplayVersion = "DisplayVersion";
    private const string Publisher = "Publisher";
    private const string InstallLocation = "InstallLocation";
    private const string UninstallString = "UninstallString";
    private const string QuietUninstallString = "QuietUninstallString";
    private const string DisplayIcon = "DisplayIcon";
    private const string NoModify = "NoModify";
    private const string NoRepair = "NoRepair";
    private const string EstimatedSize = "EstimatedSize";
    private const string BaxyInstallId = "BaxyInstallId";
    private const string BaxyDataSchema = "BaxyDataSchema";
    private const string BaxyStableSetupSha256 = "BaxyStableSetupSha256";

    private readonly IWindowsUninstallRegistryBackend _backend;

    internal WindowsUninstallRegistry()
        : this(new Registry64CurrentUserBackend(CanonicalSubkey))
    {
    }

    internal WindowsUninstallRegistry(IWindowsUninstallRegistryBackend backend)
    {
        _backend = backend ?? throw new ArgumentNullException(nameof(backend));
    }

    internal static WindowsUninstallRegistry CreateForTestSubkey(string subkey)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(subkey);
        const string testPrefix = @"Software\BAXY.Tests-";
        string suffix = subkey.StartsWith(testPrefix, StringComparison.Ordinal)
            ? subkey[testPrefix.Length..]
            : string.Empty;
        if (!subkey.StartsWith(testPrefix, StringComparison.Ordinal) ||
            !Guid.TryParseExact(suffix, "N", out Guid identifier) ||
            !string.Equals(suffix, identifier.ToString("N"), StringComparison.Ordinal))
        {
            throw new ArgumentException(
                $"A registry test subkey must have exact form {testPrefix}<lowercase-guid-N>.",
                nameof(subkey));
        }

        return new WindowsUninstallRegistry(new Registry64CurrentUserBackend(subkey));
    }

    internal void WriteNewOrUpdateOwnedVerified(
        WindowsUninstallRegistrySpecification specification,
        WindowsUninstallRegistryExpectedExisting? expectedExisting = null)
    {
        ValidatedSpecification validated = ValidateSpecification(specification);
        WindowsUninstallRegistrySnapshot? expectedBefore = expectedExisting is null
            ? null
            : BuildExpectedExistingSnapshot(expectedExisting, validated);
        WindowsUninstallRegistrySnapshot? before = ReadSafely();
        if (before is null && expectedBefore is not null)
        {
            throw new InstallationSafetyException(
                "The expected existing BAXY uninstall registry snapshot is missing.");
        }

        if (before is not null && SnapshotsEqual(before, validated.Expected))
        {
            return;
        }

        if (before is not null)
        {
            if (expectedBefore is null)
            {
                throw new InstallationSafetyException(
                    "Updating the BAXY uninstall registry requires its exact expected existing state.");
            }

            EnsureExactSnapshot(before, expectedBefore, "expected existing");
        }

        bool mutationAttempted = false;
        try
        {
            if (before is null)
            {
                mutationAttempted = true;
                _backend.CreateWithOwnershipMarkers(validated.InstallId, validated.InstallationRoot);
            }

            foreach ((string name, WindowsUninstallRegistryValue value) in validated.Expected.Values)
            {
                mutationAttempted = true;
                _backend.SetValue(name, value.Value, value.Kind);
            }

            EnsureExactSnapshot(ReadSafely(), validated.Expected, "written");
        }
        catch (Exception exception) when (mutationAttempted)
        {
            ThrowAfterWriteRollback(before, validated, exception);
        }
    }

    internal WindowsUninstallRegistryProbe ProbeOwnedVerified(
        WindowsUninstallRegistrySpecification target,
        WindowsUninstallRegistryExpectedExisting? expectedExisting = null)
    {
        ValidatedSpecification validated = ValidateSpecification(target);
        WindowsUninstallRegistrySnapshot? expectedBefore = expectedExisting is null
            ? null
            : BuildExpectedExistingSnapshot(expectedExisting, validated);
        WindowsUninstallRegistrySnapshot? current = ReadSafely();
        if (current is null)
        {
            return WindowsUninstallRegistryProbe.Missing;
        }

        if (SnapshotsEqual(current, validated.Expected))
        {
            return WindowsUninstallRegistryProbe.ExactTarget;
        }

        if (expectedBefore is not null && SnapshotsEqual(current, expectedBefore))
        {
            return WindowsUninstallRegistryProbe.ExactExpectedExisting;
        }

        throw new InstallationSafetyException(
            "The BAXY uninstall registry key is neither the exact target nor its explicit expected prior state.");
    }

    internal void EnsureAbsentVerified()
    {
        if (ReadSafely() is not null)
        {
            throw new InstallationSafetyException(
                "A BAXY uninstall registry key already occupies the first-install path.");
        }
    }

    internal void ReconcileOwnedFromJournal(
        WindowsUninstallRegistrySpecification target,
        WindowsUninstallRegistryExpectedExisting? expectedExisting = null)
    {
        ValidatedSpecification validated = ValidateSpecification(target);
        WindowsUninstallRegistrySnapshot? expectedBefore = expectedExisting is null
            ? null
            : BuildExpectedExistingSnapshot(expectedExisting, validated);
        WindowsUninstallRegistrySnapshot? current = ReadSafely();
        if (current is not null && SnapshotsEqual(current, validated.Expected))
        {
            return;
        }

        if (current is null)
        {
            if (expectedBefore is not null)
            {
                throw new InstallationSafetyException(
                    "Journal recovery expected an existing BAXY uninstall registry key, but it is missing.");
            }

            InvokeMutationSafely(
                () => _backend.CreateWithOwnershipMarkers(
                    validated.InstallId,
                    validated.InstallationRoot),
                "The BAXY uninstall registry key could not be created during journal recovery.");
        }
        else
        {
            EnsureSafeJournalTransition(current, expectedBefore, validated.Expected);
        }

        foreach ((string name, WindowsUninstallRegistryValue value) in validated.Expected.Values)
        {
            InvokeMutationSafely(
                () => _backend.SetValue(name, value.Value, value.Kind),
                "The BAXY uninstall registry key could not be converged during journal recovery.");
        }

        EnsureExactSnapshot(ReadSafely(), validated.Expected, "journal-recovered");
    }

    internal bool DeleteOwnedVerified(WindowsUninstallRegistrySpecification specification)
    {
        ValidatedSpecification validated = ValidateSpecification(specification);
        WindowsUninstallRegistrySnapshot? before = ReadSafely();
        if (before is null)
        {
            return false;
        }

        EnsureExactSnapshot(before, validated.Expected, "owned before deletion");
        try
        {
            _backend.DeleteKey();
            if (ReadSafely() is not null)
            {
                throw new InstallationSafetyException(
                    "The BAXY uninstall registry key still exists after deletion.");
            }

            return true;
        }
        catch (Exception exception)
        {
            try
            {
                RestoreDeletedSnapshot(before, validated);
            }
            catch (Exception rollbackException)
            {
                throw new InstallationSafetyException(
                    "Deleting the BAXY uninstall registry key failed and its exact snapshot could not be restored.",
                    new AggregateException(exception, rollbackException));
            }

            throw new InstallationSafetyException(
                "Deleting the BAXY uninstall registry key failed; its exact snapshot was restored.",
                exception);
        }
    }

    internal WindowsUninstallRegistryDeletionIntent CaptureOwnedForDeletion(
        WindowsUninstallRegistrySpecification specification)
    {
        ValidatedSpecification validated = ValidateSpecification(specification);
        WindowsUninstallRegistrySnapshot? current = ReadSafely();
        EnsureExactSnapshot(current, validated.Expected, "captured for deletion");
        return WindowsUninstallRegistryDeletionIntent.Capture(validated.Expected);
    }

    internal bool DeleteCapturedOwned(WindowsUninstallRegistryDeletionIntent intent)
    {
        ArgumentNullException.ThrowIfNull(intent);
        WindowsUninstallRegistrySnapshot expected = intent.CopyExpectedSnapshot();
        EnsureCanonicalDeletionSnapshot(expected);

        WindowsUninstallRegistrySnapshot? current = ReadSafely();
        if (current is null)
        {
            return false;
        }

        EnsureExactSnapshot(current, expected, "captured-owned before deletion");
        try
        {
            _backend.DeleteKey();
        }
        catch (Exception exception)
        {
            return ResolveCapturedDeletionOutcome(expected, exception);
        }

        WindowsUninstallRegistrySnapshot? after = ReadSafely();
        if (after is null)
        {
            return true;
        }

        EnsureExactSnapshot(after, expected, "captured-owned after deletion");
        throw new InstallationSafetyException(
            "The exact BAXY uninstall registry key remains after deletion and can be retried.");
    }

    private static ValidatedSpecification ValidateSpecification(
        WindowsUninstallRegistrySpecification specification)
    {
        ArgumentNullException.ThrowIfNull(specification);
        if (!Guid.TryParseExact(specification.InstallId, "N", out Guid installId) ||
            !string.Equals(specification.InstallId, installId.ToString("N"), StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "The BAXY install_id must be a lowercase Guid in exact N format.");
        }

        if (!SemanticVersionComparer.IsValid(specification.Version))
        {
            throw new InstallationSafetyException("The BAXY registry version must be valid SemVer.");
        }

        if (specification.DataSchema != PackageContract.DataSchema)
        {
            throw new InstallationSafetyException(
                $"Only BAXY data schema {PackageContract.DataSchema} is supported.");
        }

        string installationRoot;
        try
        {
            installationRoot = PathSafety.ValidateInstallationRoot(specification.InstallationRoot);
        }
        catch (Exception exception) when (exception is not InstallationSafetyException)
        {
            throw new InstallationSafetyException("The BAXY installation root is invalid.", exception);
        }

        string expectedHost = Path.Combine(installationRoot, "Baxy.Setup.exe");
        string suppliedHost;
        try
        {
            suppliedHost = Path.GetFullPath(specification.StableSetupHost);
        }
        catch (Exception exception)
        {
            throw new InstallationSafetyException("The stable Setup host path is invalid.", exception);
        }

        if (!Path.IsPathFullyQualified(specification.StableSetupHost) ||
            !string.Equals(suppliedHost, expectedHost, StringComparison.OrdinalIgnoreCase))
        {
            throw new InstallationSafetyException(
                "The stable Setup host must be exactly Baxy.Setup.exe under the installation root.");
        }

        if (!IsLowercaseSha256(specification.StableSetupSha256))
        {
            throw new InstallationSafetyException(
                "The stable Setup SHA-256 must contain exactly 64 lowercase hexadecimal characters.");
        }

        string actualHash;
        try
        {
            PathSafety.AssertRegularFile(expectedHost);
            using FileStream stream = new(
                expectedHost,
                FileMode.Open,
                FileAccess.Read,
                FileShare.Read);
            actualHash = Convert.ToHexStringLower(SHA256.HashData(stream));
            PathSafety.AssertRegularFile(expectedHost);
        }
        catch (Exception exception) when (exception is not InstallationSafetyException)
        {
            throw new InstallationSafetyException(
                "The stable Setup host is not a readable regular file.",
                exception);
        }

        if (!string.Equals(actualHash, specification.StableSetupSha256, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "The stable Setup host does not match its declared SHA-256.");
        }

        if (specification.EstimatedSizeKilobytes < 1)
        {
            throw new InstallationSafetyException(
                "EstimatedSize must be between 1 and Int32.MaxValue kilobytes.");
        }

        WindowsUninstallRegistrySnapshot expected = BuildExpectedSnapshot(
            specification.InstallId,
            specification.Version,
            installationRoot,
            expectedHost,
            specification.StableSetupSha256,
            specification.EstimatedSizeKilobytes);
        return new ValidatedSpecification(
            specification.InstallId,
            installationRoot,
            expectedHost,
            specification.StableSetupSha256,
            expected);
    }

    private static WindowsUninstallRegistrySnapshot BuildExpectedSnapshot(
        string installId,
        string version,
        string installationRoot,
        string stableSetupHost,
        string stableSetupSha256,
        int estimatedSizeKilobytes)
    {
        string quotedHost = $"\"{stableSetupHost}\"";
        KeyValuePair<string, WindowsUninstallRegistryValue>[] values =
        [
            StringValue(DisplayName, "BAXY"),
            StringValue(DisplayVersion, version),
            StringValue(Publisher, "BAXY"),
            StringValue(InstallLocation, installationRoot),
            StringValue(UninstallString, $"{quotedHost} --uninstall"),
            StringValue(QuietUninstallString, $"{quotedHost} --uninstall --keep-data --quiet"),
            StringValue(DisplayIcon, $"{quotedHost},0"),
            DwordValue(NoModify, 1),
            DwordValue(NoRepair, 1),
            DwordValue(EstimatedSize, estimatedSizeKilobytes),
            StringValue(BaxyInstallId, installId),
            DwordValue(BaxyDataSchema, PackageContract.DataSchema),
            StringValue(BaxyStableSetupSha256, stableSetupSha256),
        ];
        return new WindowsUninstallRegistrySnapshot(values);
    }

    private static void EnsureCanonicalDeletionSnapshot(
        WindowsUninstallRegistrySnapshot expected)
    {
        if (expected.SubkeyNames.Count != 0 || expected.Values.Count != 13 ||
            !TryGetString(expected, BaxyInstallId, out string? installId) ||
            !Guid.TryParseExact(installId, "N", out Guid parsedInstallId) ||
            !string.Equals(installId, parsedInstallId.ToString("N"), StringComparison.Ordinal) ||
            !TryGetString(expected, DisplayVersion, out string? version) ||
            !SemanticVersionComparer.IsValid(version) ||
            !TryGetDword(expected, BaxyDataSchema, out int dataSchema) ||
            dataSchema != PackageContract.DataSchema ||
            !TryGetString(expected, InstallLocation, out string? installationRoot) ||
            !TryGetString(expected, BaxyStableSetupSha256, out string? stableSetupSha256) ||
            !IsLowercaseSha256(stableSetupSha256) ||
            !TryGetDword(expected, EstimatedSize, out int estimatedSizeKilobytes) ||
            estimatedSizeKilobytes < 1)
        {
            throw new InstallationSafetyException(
                "The uninstall-registry deletion intent is not canonical.");
        }

        string canonicalRoot;
        try
        {
            canonicalRoot = PathSafety.ValidateInstallationRoot(installationRoot!);
        }
        catch (Exception exception) when (exception is not InstallationSafetyException)
        {
            throw new InstallationSafetyException(
                "The uninstall-registry deletion intent contains an invalid installation root.",
                exception);
        }

        string stableSetupHost = Path.Combine(canonicalRoot, "Baxy.Setup.exe");
        WindowsUninstallRegistrySnapshot canonical = BuildExpectedSnapshot(
            installId,
            version!,
            canonicalRoot,
            stableSetupHost,
            stableSetupSha256!,
            estimatedSizeKilobytes);
        EnsureExactSnapshot(expected, canonical, "deletion-intent canonical");
    }

    private static WindowsUninstallRegistrySnapshot BuildExpectedExistingSnapshot(
        WindowsUninstallRegistryExpectedExisting expectedExisting,
        ValidatedSpecification validated)
    {
        ArgumentNullException.ThrowIfNull(expectedExisting);
        if (!SemanticVersionComparer.IsValid(expectedExisting.Version))
        {
            throw new InstallationSafetyException(
                "The expected existing registry version must be valid SemVer.");
        }

        if (!IsLowercaseSha256(expectedExisting.StableSetupSha256))
        {
            throw new InstallationSafetyException(
                "The expected existing stable Setup SHA-256 must be canonical lowercase hexadecimal.");
        }

        if (expectedExisting.EstimatedSizeKilobytes < 1)
        {
            throw new InstallationSafetyException(
                "The expected existing EstimatedSize must be between 1 and Int32.MaxValue kilobytes.");
        }

        return BuildExpectedSnapshot(
            validated.InstallId,
            expectedExisting.Version,
            validated.InstallationRoot,
            validated.StableSetupHost,
            expectedExisting.StableSetupSha256,
            expectedExisting.EstimatedSizeKilobytes);
    }

    private static KeyValuePair<string, WindowsUninstallRegistryValue> StringValue(
        string name,
        string value) =>
        new(name, new WindowsUninstallRegistryValue(value, RegistryValueKind.String));

    private static KeyValuePair<string, WindowsUninstallRegistryValue> DwordValue(
        string name,
        int value) =>
        new(name, new WindowsUninstallRegistryValue(value, RegistryValueKind.DWord));

    private static bool IsLowercaseSha256(string? value)
    {
        if (value is null || value.Length != 64)
        {
            return false;
        }

        foreach (char character in value)
        {
            if (character is not (>= '0' and <= '9') and not (>= 'a' and <= 'f'))
            {
                return false;
            }
        }

        return true;
    }

    private static bool TryGetString(
        WindowsUninstallRegistrySnapshot snapshot,
        string name,
        out string? result)
    {
        if (snapshot.Values.TryGetValue(name, out WindowsUninstallRegistryValue? value) &&
            value.Kind == RegistryValueKind.String &&
            value.Value is string text)
        {
            result = text;
            return true;
        }

        result = null;
        return false;
    }

    private static bool TryGetDword(
        WindowsUninstallRegistrySnapshot snapshot,
        string name,
        out int result)
    {
        if (snapshot.Values.TryGetValue(name, out WindowsUninstallRegistryValue? value) &&
            value.Kind == RegistryValueKind.DWord &&
            value.Value is int number)
        {
            result = number;
            return true;
        }

        result = 0;
        return false;
    }

    private static void EnsureExactSnapshot(
        WindowsUninstallRegistrySnapshot? actual,
        WindowsUninstallRegistrySnapshot expected,
        string state)
    {
        if (actual is null || actual.SubkeyNames.Count != 0 ||
            actual.Values.Count != expected.Values.Count)
        {
            throw new InstallationSafetyException(
                $"The BAXY uninstall registry {state} snapshot is not exact.");
        }

        foreach ((string name, WindowsUninstallRegistryValue expectedValue) in expected.Values)
        {
            if (!actual.Values.TryGetValue(name, out WindowsUninstallRegistryValue? actualValue) ||
                actualValue.Kind != expectedValue.Kind ||
                !Equals(actualValue.Value, expectedValue.Value))
            {
                throw new InstallationSafetyException(
                    $"The BAXY uninstall registry {state} snapshot is not exact.");
            }
        }
    }

    private WindowsUninstallRegistrySnapshot? ReadSafely()
    {
        try
        {
            return _backend.Read();
        }
        catch (InstallationSafetyException)
        {
            throw;
        }
        catch (Exception exception)
        {
            throw new InstallationSafetyException(
                "The BAXY uninstall registry key could not be read safely.",
                exception);
        }
    }

    private static void InvokeMutationSafely(Action mutation, string message)
    {
        try
        {
            mutation();
        }
        catch (InstallationSafetyException)
        {
            throw;
        }
        catch (Exception exception)
        {
            throw new InstallationSafetyException(message, exception);
        }
    }

    private void ThrowAfterWriteRollback(
        WindowsUninstallRegistrySnapshot? before,
        ValidatedSpecification validated,
        Exception exception)
    {
        try
        {
            if (before is null)
            {
                RollBackNewKey(validated);
            }
            else
            {
                RestoreExistingSnapshot(before, validated);
            }
        }
        catch (Exception rollbackException)
        {
            throw new InstallationSafetyException(
                "Writing the BAXY uninstall registry key failed and rollback could not be verified.",
                new AggregateException(exception, rollbackException));
        }

        throw new InstallationSafetyException(
            "Writing the BAXY uninstall registry key failed; its prior state was restored.",
            exception);
    }

    private bool ResolveCapturedDeletionOutcome(
        WindowsUninstallRegistrySnapshot expected,
        Exception deleteException)
    {
        WindowsUninstallRegistrySnapshot? after;
        try
        {
            after = ReadSafely();
        }
        catch (Exception readException)
        {
            throw new InstallationSafetyException(
                "Deleting the BAXY uninstall registry key failed and its outcome could not be attested.",
                new AggregateException(deleteException, readException));
        }

        if (after is null)
        {
            return true;
        }

        try
        {
            EnsureExactSnapshot(after, expected, "captured-owned after failed deletion");
        }
        catch (InstallationSafetyException foreignException)
        {
            throw new InstallationSafetyException(
                "Deleting the BAXY uninstall registry key failed and foreign state now occupies its path.",
                new AggregateException(deleteException, foreignException));
        }

        throw new InstallationSafetyException(
            "Deleting the exact BAXY uninstall registry key failed before removal; the operation can be retried.",
            deleteException);
    }

    private void RollBackNewKey(ValidatedSpecification validated)
    {
        WindowsUninstallRegistrySnapshot? current = ReadSafely();
        if (current is null)
        {
            return;
        }

        EnsureSafeOwnedPartial(current, validated.Expected, validated);
        _backend.DeleteKey();
        if (ReadSafely() is not null)
        {
            throw new InstallationSafetyException(
                "The newly created BAXY uninstall registry key survived rollback.");
        }
    }

    private void RestoreExistingSnapshot(
        WindowsUninstallRegistrySnapshot before,
        ValidatedSpecification validated)
    {
        WindowsUninstallRegistrySnapshot? current = ReadSafely();
        if (current is null)
        {
            throw new InstallationSafetyException(
                "An existing BAXY uninstall registry key disappeared during update.");
        }

        EnsureSafeOwnedTransition(current, before, validated.Expected, validated);
        foreach ((string name, WindowsUninstallRegistryValue value) in before.Values)
        {
            _backend.SetValue(name, value.Value, value.Kind);
        }

        EnsureExactSnapshot(ReadSafely(), before, "restored");
    }

    private static void EnsureSafeOwnedTransition(
        WindowsUninstallRegistrySnapshot current,
        WindowsUninstallRegistrySnapshot before,
        WindowsUninstallRegistrySnapshot target,
        ValidatedSpecification validated)
    {
        if (current.SubkeyNames.Count != 0 ||
            current.Values.Count != before.Values.Count ||
            current.Values.Count != target.Values.Count ||
            !TryGetString(current, BaxyInstallId, out string? installId) ||
            !string.Equals(installId, validated.InstallId, StringComparison.Ordinal) ||
            !TryGetString(current, InstallLocation, out string? root) ||
            !string.Equals(root, validated.InstallationRoot, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "Rollback refused a registry snapshot outside the owned update transition.");
        }

        foreach ((string name, WindowsUninstallRegistryValue currentValue) in current.Values)
        {
            if (!before.Values.TryGetValue(name, out WindowsUninstallRegistryValue? beforeValue) ||
                !target.Values.TryGetValue(name, out WindowsUninstallRegistryValue? targetValue) ||
                (!RegistryValuesEqual(currentValue, beforeValue) &&
                    !RegistryValuesEqual(currentValue, targetValue)))
            {
                throw new InstallationSafetyException(
                    "Rollback refused foreign registry state outside the exact old/new transition.");
            }
        }
    }

    private static void EnsureSafeJournalTransition(
        WindowsUninstallRegistrySnapshot current,
        WindowsUninstallRegistrySnapshot? before,
        WindowsUninstallRegistrySnapshot target)
    {
        if (current.SubkeyNames.Count != 0)
        {
            throw new InstallationSafetyException(
                "Journal recovery refused a registry key containing subkeys.");
        }

        foreach ((string name, WindowsUninstallRegistryValue currentValue) in current.Values)
        {
            if (!target.Values.TryGetValue(name, out WindowsUninstallRegistryValue? targetValue))
            {
                throw new InstallationSafetyException(
                    "Journal recovery refused an unknown uninstall registry value.");
            }

            bool matchesTarget = RegistryValuesEqual(currentValue, targetValue);
            bool matchesBefore = before is not null &&
                before.Values.TryGetValue(name, out WindowsUninstallRegistryValue? beforeValue) &&
                RegistryValuesEqual(currentValue, beforeValue);
            if (!matchesTarget && !matchesBefore)
            {
                throw new InstallationSafetyException(
                    "Journal recovery refused registry state outside the exact prior/target transition.");
            }
        }
    }

    private static bool RegistryValuesEqual(
        WindowsUninstallRegistryValue left,
        WindowsUninstallRegistryValue right) =>
        left.Kind == right.Kind && Equals(left.Value, right.Value);

    private void RestoreDeletedSnapshot(
        WindowsUninstallRegistrySnapshot before,
        ValidatedSpecification validated)
    {
        WindowsUninstallRegistrySnapshot? current = ReadSafely();
        if (current is not null && SnapshotsEqual(current, before))
        {
            return;
        }

        if (current is null)
        {
            _backend.CreateWithOwnershipMarkers(validated.InstallId, validated.InstallationRoot);
        }
        else
        {
            EnsureSafeOwnedPartial(current, before, validated);
        }

        foreach ((string name, WindowsUninstallRegistryValue value) in before.Values)
        {
            _backend.SetValue(name, value.Value, value.Kind);
        }

        EnsureExactSnapshot(ReadSafely(), before, "restored after deletion");
    }

    private static void EnsureSafeOwnedPartial(
        WindowsUninstallRegistrySnapshot current,
        WindowsUninstallRegistrySnapshot target,
        ValidatedSpecification validated)
    {
        if (current.SubkeyNames.Count != 0 ||
            !TryGetString(current, BaxyInstallId, out string? installId) ||
            !string.Equals(installId, validated.InstallId, StringComparison.Ordinal) ||
            !TryGetString(current, InstallLocation, out string? root) ||
            !string.Equals(root, validated.InstallationRoot, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException(
                "Rollback refused to mutate a registry key without BAXY's exact ownership markers.");
        }

        foreach ((string name, WindowsUninstallRegistryValue value) in current.Values)
        {
            if (!target.Values.TryGetValue(name, out WindowsUninstallRegistryValue? targetValue) ||
                value.Kind != targetValue.Kind ||
                !Equals(value.Value, targetValue.Value))
            {
                throw new InstallationSafetyException(
                    "Rollback refused to mutate a registry key containing foreign state.");
            }
        }
    }

    private static bool SnapshotsEqual(
        WindowsUninstallRegistrySnapshot left,
        WindowsUninstallRegistrySnapshot right)
    {
        try
        {
            EnsureExactSnapshot(left, right, "comparison");
            return true;
        }
        catch (InstallationSafetyException)
        {
            return false;
        }
    }

    private sealed record ValidatedSpecification(
        string InstallId,
        string InstallationRoot,
        string StableSetupHost,
        string StableSetupSha256,
        WindowsUninstallRegistrySnapshot Expected);

    private sealed class Registry64CurrentUserBackend : IWindowsUninstallRegistryBackend
    {
        private readonly string _subkey;

        internal Registry64CurrentUserBackend(string subkey)
        {
            _subkey = subkey;
        }

        public WindowsUninstallRegistrySnapshot? Read()
        {
            using RegistryKey currentUser = RegistryKey.OpenBaseKey(
                RegistryHive.CurrentUser,
                RegistryView.Registry64);
            using RegistryKey? key = currentUser.OpenSubKey(_subkey, writable: false);
            if (key is null)
            {
                return null;
            }

            Dictionary<string, WindowsUninstallRegistryValue> values = new(StringComparer.Ordinal);
            foreach (string name in key.GetValueNames())
            {
                object? value = key.GetValue(
                    name,
                    defaultValue: null,
                    RegistryValueOptions.DoNotExpandEnvironmentNames);
                if (value is null)
                {
                    throw new InstallationSafetyException(
                        $"Registry value '{name}' could not be read exactly.");
                }

                values.Add(name, new WindowsUninstallRegistryValue(value, key.GetValueKind(name)));
            }

            return new WindowsUninstallRegistrySnapshot(values, key.GetSubKeyNames());
        }

        public void CreateWithOwnershipMarkers(string installId, string installationRoot)
        {
            using RegistryKey currentUser = RegistryKey.OpenBaseKey(
                RegistryHive.CurrentUser,
                RegistryView.Registry64);
            using RegistryKey? existing = currentUser.OpenSubKey(_subkey, writable: false);
            if (existing is not null)
            {
                throw new InstallationSafetyException(
                    "Refusing to create an uninstall registry key that already exists.");
            }

            using RegistryKey key = currentUser.CreateSubKey(_subkey, writable: true);
            key.SetValue(BaxyInstallId, installId, RegistryValueKind.String);
            key.SetValue(InstallLocation, installationRoot, RegistryValueKind.String);
            key.Flush();
        }

        public void SetValue(string name, object value, RegistryValueKind kind)
        {
            using RegistryKey currentUser = RegistryKey.OpenBaseKey(
                RegistryHive.CurrentUser,
                RegistryView.Registry64);
            using RegistryKey? key = currentUser.OpenSubKey(_subkey, writable: true);
            if (key is null)
            {
                throw new InstallationSafetyException(
                    "The BAXY uninstall registry key disappeared during mutation.");
            }

            key.SetValue(name, value, kind);
            key.Flush();
        }

        public void DeleteKey()
        {
            using RegistryKey currentUser = RegistryKey.OpenBaseKey(
                RegistryHive.CurrentUser,
                RegistryView.Registry64);
            currentUser.DeleteSubKey(_subkey, throwOnMissingSubKey: true);
            currentUser.Flush();
        }
    }
}
