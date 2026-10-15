using System.Globalization;
using System.Text;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.SystemStatus;

namespace Baxy.Core.Operations;

internal sealed class SystemStatusHandler : IOperationHandler
{
    private const int MaximumGpuAdapters = 64;
    private const int MaximumGpuNameUtf8Bytes = 512;

    private static readonly SystemStatusScope[] OrderedScopes =
    [
        SystemStatusScope.Cpu,
        SystemStatusScope.Memory,
        SystemStatusScope.SystemDisk,
        SystemStatusScope.Battery,
        SystemStatusScope.OperatingSystem,
        SystemStatusScope.Uptime,
    ];

    private readonly ISystemStatusProvider _provider;
    private readonly IGpuStatusProvider _gpuProvider;

    public SystemStatusHandler(
        ISystemStatusProvider provider,
        IGpuStatusProvider gpuProvider)
    {
        _provider = provider ?? throw new ArgumentNullException(nameof(provider));
        _gpuProvider = gpuProvider ?? throw new ArgumentNullException(nameof(gpuProvider));
    }

    public OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("system.status");

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (!HasValidArgumentShape(invocation.Arguments))
        {
            return InvalidArguments();
        }

        SystemStatusArguments arguments;
        try
        {
            arguments = JsonSerializer.Deserialize(
                invocation.Arguments,
                CoreJsonContext.Default.SystemStatusArguments)
                ?? throw new JsonException("Arguments cannot be null.");
        }
        catch (JsonException)
        {
            return InvalidArguments();
        }

        string requestedScope = arguments.Scope ?? "summary";
        if (TryMapGpuScope(requestedScope, out GpuStatusScope gpuScope))
        {
            return await ExecuteGpuAsync(
                requestedScope,
                gpuScope,
                cancellationToken).ConfigureAwait(false);
        }

        if (!TryMapScope(requestedScope, out SystemStatusScope providerScope))
        {
            return InvalidArguments();
        }

        SystemStatusSnapshot snapshot = await _provider.GetStatusAsync(
            providerScope,
            cancellationToken).ConfigureAwait(false);
        if (!TryCreateResult(
                requestedScope,
                providerScope,
                snapshot,
                out SystemStatusResult? status,
                out int measurementCount))
        {
            return OperationOutcome.Failure(
                "verification_failed",
                causeCode: "system_measurements");
        }

        SystemStatusResult verifiedStatus = status!;
        JsonElement serialized = JsonSerializer.SerializeToElement(
            verifiedStatus,
            CoreJsonContext.Default.SystemStatusResult);
        if (measurementCount == 0)
        {
            return OperationOutcome.Failure("system_status_unavailable", serialized);
        }

        return OperationOutcome.Success(serialized);
    }

    private static OperationOutcome InvalidArguments() =>
        OperationOutcome.Failure("invalid_arguments");

    private async ValueTask<OperationOutcome> ExecuteGpuAsync(
        string requestedScope,
        GpuStatusScope providerScope,
        CancellationToken cancellationToken)
    {
        GpuStatusSnapshot snapshot = await _gpuProvider.GetStatusAsync(
            providerScope,
            cancellationToken).ConfigureAwait(false);
        if (!TryCreateGpuResult(
                requestedScope,
                providerScope,
                snapshot,
                out GpuSystemStatusResult? status,
                out int measurementCount))
        {
            return OperationOutcome.Failure(
                "verification_failed",
                causeCode: "gpu_measurements");
        }

        GpuSystemStatusResult verifiedStatus = status!;
        JsonElement serialized = JsonSerializer.SerializeToElement(
            verifiedStatus,
            GpuSystemStatusJsonContext.Default.GpuSystemStatusResult);
        if (measurementCount == 0)
        {
            return OperationOutcome.Failure("system_status_unavailable", serialized);
        }

        return OperationOutcome.Success(serialized);
    }

    private static bool HasValidArgumentShape(JsonElement arguments)
    {
        if (arguments.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        int propertyCount = 0;
        foreach (JsonProperty property in arguments.EnumerateObject())
        {
            propertyCount++;
            if (propertyCount > 1
                || !string.Equals(property.Name, "scope", StringComparison.Ordinal)
                || property.Value.ValueKind != JsonValueKind.String)
            {
                return false;
            }
        }

        return true;
    }

    private static bool TryMapGpuScope(string scope, out GpuStatusScope providerScope)
    {
        providerScope = scope switch
        {
            "gpu_identity" => GpuStatusScope.Identity,
            "gpu_usage" => GpuStatusScope.Usage,
            _ => (GpuStatusScope)(-1),
        };
        return providerScope is GpuStatusScope.Identity or GpuStatusScope.Usage;
    }

    private static bool TryMapScope(string scope, out SystemStatusScope providerScope)
    {
        providerScope = scope switch
        {
            "summary" => SystemStatusScope.All,
            "cpu_memory" => SystemStatusScope.Cpu | SystemStatusScope.Memory,
            "os_memory" => SystemStatusScope.OperatingSystem | SystemStatusScope.Memory,
            "cpu" => SystemStatusScope.Cpu,
            "memory" => SystemStatusScope.Memory,
            "disk" => SystemStatusScope.SystemDisk,
            "battery" => SystemStatusScope.Battery,
            "os" => SystemStatusScope.OperatingSystem,
            _ => SystemStatusScope.None,
        };
        return providerScope != SystemStatusScope.None;
    }

    private static bool TryCreateGpuResult(
        string requestedScope,
        GpuStatusScope providerScope,
        GpuStatusSnapshot? snapshot,
        out GpuSystemStatusResult? result,
        out int measurementCount)
    {
        result = null;
        measurementCount = 0;
        if (snapshot?.Adapters is null
            || snapshot.Failures is null
            || snapshot.Adapters.Count > MaximumGpuAdapters
            || snapshot.Failures.Count > MaximumGpuAdapters)
        {
            return false;
        }

        var failures = new List<GpuStatusFailure>(snapshot.Failures.Count);
        foreach (GpuStatusFailure? failure in snapshot.Failures)
        {
            if (failure is null
                || failure.Scope is not (GpuStatusScope.Identity or GpuStatusScope.Usage)
                || !IsKnownErrorCode(failure.ErrorCode))
            {
                return false;
            }

            failures.Add(failure);
        }

        var adapters = new GpuSystemStatusAdapterResult[snapshot.Adapters.Count];
        var measured = new bool[snapshot.Adapters.Count];
        for (int index = 0; index < snapshot.Adapters.Count; index++)
        {
            GpuAdapterStatus? adapter = snapshot.Adapters[index];
            if (adapter is null || !IsValidGpuIdentity(adapter))
            {
                return false;
            }

            bool hasUsagePercent = adapter.UsagePercent.HasValue;
            bool hasDedicatedUsage = adapter.DedicatedMemoryUsageBytes.HasValue;
            bool hasSharedUsage = adapter.SharedMemoryUsageBytes.HasValue;
            if (hasUsagePercent != hasDedicatedUsage
                || hasUsagePercent != hasSharedUsage
                || providerScope == GpuStatusScope.Identity && hasUsagePercent
                || hasUsagePercent && !IsValidGpuUsage(adapter))
            {
                return false;
            }

            measured[index] = hasUsagePercent;
            adapters[index] = new GpuSystemStatusAdapterResult(
                index,
                adapter.Name,
                adapter.VendorId,
                adapter.DeviceId,
                adapter.DedicatedVideoMemoryBytes,
                adapter.DedicatedSystemMemoryBytes,
                adapter.SharedSystemMemoryLimitBytes,
                adapter.UsagePercent,
                adapter.DedicatedMemoryUsageBytes,
                adapter.SharedMemoryUsageBytes);
        }

        if (providerScope == GpuStatusScope.Identity)
        {
            if (!HasConsistentGpuIdentityPresence(adapters.Length, failures))
            {
                return false;
            }

            measurementCount = adapters.Length;
        }
        else if (!HasConsistentGpuUsagePresence(measured, failures, out measurementCount))
        {
            return false;
        }

        GpuSystemStatusFailureResult[] failureResults = failures
            .Select(static failure => new GpuSystemStatusFailureResult(
                SystemStatusNarration.ToPublicGpuScope(failure.Scope),
                failure.AdapterIndex,
                failure.ErrorCode))
            .ToArray();
        result = new GpuSystemStatusResult(requestedScope, adapters, failureResults);
        return true;
    }

    private static bool HasConsistentGpuIdentityPresence(
        int adapterCount,
        List<GpuStatusFailure> failures)
    {
        if (adapterCount > 0)
        {
            return failures.Count == 0;
        }

        return failures.Count == 1
            && failures[0].Scope == GpuStatusScope.Identity
            && failures[0].AdapterIndex is null;
    }

    private static bool HasConsistentGpuUsagePresence(
        bool[] measured,
        List<GpuStatusFailure> failures,
        out int measurementCount)
    {
        measurementCount = measured.Count(static value => value);
        if (measured.Length == 0)
        {
            return failures.Count == 1
                && failures[0].Scope == GpuStatusScope.Identity
                && failures[0].AdapterIndex is null;
        }

        if (failures.Any(static failure => failure.Scope != GpuStatusScope.Usage))
        {
            return false;
        }

        GpuStatusFailure[] globalFailures = failures
            .Where(static failure => failure.AdapterIndex is null)
            .ToArray();
        if (measurementCount == 0)
        {
            return failures.Count == 1 && globalFailures.Length == 1;
        }

        if (globalFailures.Length != 0)
        {
            return false;
        }

        var failureByIndex = new Dictionary<int, GpuStatusFailure>();
        foreach (GpuStatusFailure failure in failures)
        {
            int adapterIndex = failure.AdapterIndex.GetValueOrDefault(-1);
            if (!failure.AdapterIndex.HasValue
                || adapterIndex < 0
                || adapterIndex >= measured.Length
                || failure.ErrorCode != SystemStatusErrorCodes.Unsupported
                || !failureByIndex.TryAdd(adapterIndex, failure))
            {
                return false;
            }
        }

        for (int index = 0; index < measured.Length; index++)
        {
            if (measured[index] == failureByIndex.ContainsKey(index))
            {
                return false;
            }
        }

        return true;
    }

    private static bool IsValidGpuIdentity(GpuAdapterStatus adapter) =>
        IsValidRequiredText(adapter.Name, 512)
        && adapter.Name.EnumerateRunes().All(static rune =>
            Rune.GetUnicodeCategory(rune) is not (
                UnicodeCategory.Control
                or UnicodeCategory.Format
                or UnicodeCategory.LineSeparator
                or UnicodeCategory.ParagraphSeparator))
        && Encoding.UTF8.GetByteCount(adapter.Name) <= MaximumGpuNameUtf8Bytes
        && TryGetDedicatedGraphicsCapacity(adapter, out _);

    private static bool IsValidGpuUsage(GpuAdapterStatus adapter)
    {
        double usagePercent = adapter.UsagePercent!.Value;
        ulong dedicatedUsage = adapter.DedicatedMemoryUsageBytes!.Value;
        ulong sharedUsage = adapter.SharedMemoryUsageBytes!.Value;
        return TryGetDedicatedGraphicsCapacity(adapter, out ulong dedicatedCapacity)
            && double.IsFinite(usagePercent)
            && usagePercent is >= 0d and <= 100d
            && dedicatedUsage <= dedicatedCapacity
            && sharedUsage <= adapter.SharedSystemMemoryLimitBytes;
    }

    private static bool TryGetDedicatedGraphicsCapacity(
        GpuAdapterStatus adapter,
        out ulong capacity)
    {
        try
        {
            capacity = checked(
                adapter.DedicatedVideoMemoryBytes + adapter.DedicatedSystemMemoryBytes);
            return true;
        }
        catch (OverflowException)
        {
            capacity = 0;
            return false;
        }
    }

    private static bool TryCreateResult(
        string requestedScope,
        SystemStatusScope providerScope,
        SystemStatusSnapshot? snapshot,
        out SystemStatusResult? result,
        out int measurementCount)
    {
        result = null;
        measurementCount = 0;
        if (snapshot?.Failures is null)
        {
            return false;
        }

        var failures = new Dictionary<SystemStatusScope, string>();
        foreach (SystemStatusFailure failure in snapshot.Failures)
        {
            if (!IsAtomicScope(failure.Scope)
                || !providerScope.HasFlag(failure.Scope)
                || !IsKnownErrorCode(failure.ErrorCode)
                || !failures.TryAdd(failure.Scope, failure.ErrorCode))
            {
                return false;
            }
        }

        if (!HasConsistentPresence(
                providerScope,
                SystemStatusScope.Cpu,
                snapshot.Cpu,
                failures)
            || !HasConsistentPresence(
                providerScope,
                SystemStatusScope.Memory,
                snapshot.Memory,
                failures)
            || !HasConsistentPresence(
                providerScope,
                SystemStatusScope.SystemDisk,
                snapshot.SystemDisk,
                failures)
            || !HasConsistentPresence(
                providerScope,
                SystemStatusScope.Battery,
                snapshot.Battery,
                failures)
            || !HasConsistentPresence(
                providerScope,
                SystemStatusScope.OperatingSystem,
                snapshot.OperatingSystem,
                failures)
            || !HasConsistentNullablePresence(
                providerScope,
                SystemStatusScope.Uptime,
                snapshot.UptimeSeconds,
                failures))
        {
            return false;
        }

        if (snapshot.Cpu is not null && !IsValid(snapshot.Cpu)
            || snapshot.Memory is not null && !IsValid(snapshot.Memory)
            || snapshot.SystemDisk is not null && !IsValid(snapshot.SystemDisk)
            || snapshot.Battery is not null && !IsValid(snapshot.Battery)
            || snapshot.OperatingSystem is not null && !IsValid(snapshot.OperatingSystem)
            || snapshot.UptimeSeconds is < 0)
        {
            return false;
        }

        SystemStatusFailureResult[] failureResults = OrderedScopes
            .Where(failures.ContainsKey)
            .Select(scope => new SystemStatusFailureResult(
                SystemStatusNarration.ToPublicScope(scope),
                failures[scope]))
            .ToArray();
        measurementCount = OrderedScopes.Count(scope =>
            providerScope.HasFlag(scope) && !failures.ContainsKey(scope));
        result = new SystemStatusResult(
            requestedScope,
            snapshot.Cpu is null
                ? null
                : new SystemStatusCpuResult(
                    snapshot.Cpu.UsagePercent,
                    snapshot.Cpu.LogicalProcessorCount,
                    snapshot.Cpu.Model,
                    snapshot.Cpu.PhysicalCoreCount),
            snapshot.Memory is null
                ? null
                : new SystemStatusMemoryResult(
                    snapshot.Memory.TotalBytes,
                    snapshot.Memory.AvailableBytes,
                    snapshot.Memory.InstalledBytes),
            snapshot.SystemDisk is null
                ? null
                : new SystemStatusDiskResult(
                    snapshot.SystemDisk.TotalBytes,
                    snapshot.SystemDisk.AvailableBytes),
            snapshot.Battery is null
                ? null
                : new SystemStatusBatteryResult(
                    snapshot.Battery.IsPresent,
                    snapshot.Battery.ChargePercent,
                    snapshot.Battery.IsCharging,
                    snapshot.Battery.IsAcOnline),
            snapshot.OperatingSystem is null
                ? null
                : new SystemStatusOperatingSystemResult(
                    snapshot.OperatingSystem.MajorVersion,
                    snapshot.OperatingSystem.MinorVersion,
                    snapshot.OperatingSystem.BuildNumber,
                    snapshot.OperatingSystem.Architecture,
                    snapshot.OperatingSystem.IsWorkstation,
                    snapshot.OperatingSystem.Caption),
            snapshot.UptimeSeconds,
            failureResults);
        return true;
    }

    private static bool HasConsistentPresence<T>(
        SystemStatusScope requested,
        SystemStatusScope scope,
        T? value,
        Dictionary<SystemStatusScope, string> failures)
        where T : class
    {
        bool isRequested = requested.HasFlag(scope);
        bool hasValue = value is not null;
        bool hasFailure = failures.ContainsKey(scope);
        return isRequested
            ? hasValue != hasFailure
            : !hasValue && !hasFailure;
    }

    private static bool HasConsistentNullablePresence(
        SystemStatusScope requested,
        SystemStatusScope scope,
        long? value,
        Dictionary<SystemStatusScope, string> failures)
    {
        bool isRequested = requested.HasFlag(scope);
        bool hasFailure = failures.ContainsKey(scope);
        return isRequested
            ? value.HasValue != hasFailure
            : !value.HasValue && !hasFailure;
    }

    private static bool IsAtomicScope(SystemStatusScope scope) => scope is
        SystemStatusScope.Cpu
        or SystemStatusScope.Memory
        or SystemStatusScope.SystemDisk
        or SystemStatusScope.Battery
        or SystemStatusScope.OperatingSystem
        or SystemStatusScope.Uptime;

    private static bool IsKnownErrorCode(string? errorCode) => errorCode is
        SystemStatusErrorCodes.MeasurementFailed
        or SystemStatusErrorCodes.InvalidMeasurement
        or SystemStatusErrorCodes.Unsupported;

    private static bool IsValid(CpuStatus status) =>
        double.IsFinite(status.UsagePercent)
        && status.UsagePercent is >= 0 and <= 100
        && status.LogicalProcessorCount is > 0 and <= 4096
        && (status.PhysicalCoreCount is null
            || status.PhysicalCoreCount > 0 && status.PhysicalCoreCount <= status.LogicalProcessorCount)
        && IsValidOptionalText(status.Model, 512);

    private static bool IsValid(MemoryStatus status) =>
        status.TotalBytes > 0 && status.AvailableBytes <= status.TotalBytes
        && (status.InstalledBytes is null || status.InstalledBytes >= status.TotalBytes);

    private static bool IsValid(SystemDiskStatus status) =>
        status.TotalBytes > 0
        && status.AvailableBytes >= 0
        && status.AvailableBytes <= status.TotalBytes;

    private static bool IsValid(BatteryStatus status)
    {
        if (status.ChargePercent is < 0 or > 100
            || (status.ChargePercent.HasValue || status.IsCharging.HasValue)
                && status.IsPresent is not true)
        {
            return false;
        }

        return status.IsPresent.HasValue
            || status.IsAcOnline.HasValue;
    }

    private static bool IsValid(OperatingSystemStatus status) =>
        status.MajorVersion > 0
        && status.MinorVersion >= 0
        && status.BuildNumber > 0
        && IsValidRequiredText(status.Caption, 64)
        && IsValidRequiredText(status.Architecture, 64);

    private static bool IsValidOptionalText(string? value, int maximumLength) =>
        value is null || IsValidRequiredText(value, maximumLength);

    private static bool IsValidRequiredText(string value, int maximumLength)
    {
        if (string.IsNullOrWhiteSpace(value)
            || value.Length > maximumLength
            || value.Any(char.IsControl))
        {
            return false;
        }

        try
        {
            return value.IsNormalized(NormalizationForm.FormC);
        }
        catch (ArgumentException)
        {
            return false;
        }
    }

}
