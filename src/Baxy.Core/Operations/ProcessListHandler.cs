using System.Text;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.SystemStatus;

namespace Baxy.Core.Operations;

internal sealed class ProcessListHandler(IProcessStatusProvider provider) : IOperationHandler
{
    private readonly IProcessStatusProvider _provider =
        provider ?? throw new ArgumentNullException(nameof(provider));

    public OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("system.process.list");

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        if (!HasValidArgumentShape(invocation.Arguments))
        {
            return OperationOutcome.Failure("invalid_arguments");
        }

        ProcessListArguments arguments;
        try
        {
            arguments = JsonSerializer.Deserialize(
                invocation.Arguments,
                CoreJsonContext.Default.ProcessListArguments)
                ?? throw new JsonException();
        }
        catch (JsonException)
        {
            return OperationOutcome.Failure("invalid_arguments");
        }

        int limit = arguments.Limit ?? 10;
        if (limit is < 1 or > 50 || !TryParseSort(arguments.Sort, out ProcessStatusSort sort))
        {
            return OperationOutcome.Failure("invalid_arguments");
        }

        ProcessStatusSnapshot snapshot;
        try
        {
            snapshot = await _provider.GetProcessesAsync(sort, limit, cancellationToken)
                .ConfigureAwait(false);
        }
        catch (Exception error) when (error is
            InvalidOperationException or NotSupportedException or
            System.ComponentModel.Win32Exception)
        {
            return OperationOutcome.Failure("process_inventory_unavailable");
        }

        if (!TryCreateResult(snapshot, sort, limit, out ProcessListResult? result))
        {
            return OperationOutcome.Failure("process_inventory_unavailable");
        }
        return OperationOutcome.Success(JsonSerializer.SerializeToElement(
            result,
            CoreJsonContext.Default.ProcessListResult));
    }

    private static bool HasValidArgumentShape(JsonElement value)
    {
        if (value.ValueKind != JsonValueKind.Object)
        {
            return false;
        }
        var names = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonProperty property in value.EnumerateObject())
        {
            if (!names.Add(property.Name)
                || property.Name is not ("sort" or "limit"))
            {
                return false;
            }
        }
        return true;
    }

    private static bool TryParseSort(string? value, out ProcessStatusSort sort)
    {
        sort = value switch
        {
            null or "memory" => ProcessStatusSort.Memory,
            "cpu" => ProcessStatusSort.Cpu,
            "name" => ProcessStatusSort.Name,
            _ => (ProcessStatusSort)(-1),
        };
        return Enum.IsDefined(sort);
    }

    private static bool TryCreateResult(
        ProcessStatusSnapshot snapshot,
        ProcessStatusSort sort,
        int limit,
        out ProcessListResult? result)
    {
        result = null;
        if (snapshot.ObservedProcessCount < 1
            || snapshot.Processes.Count is < 1 or > 50
            || snapshot.Processes.Count > limit)
        {
            return false;
        }
        var identities = new HashSet<(int ProcessId, long Created)>();
        var items = new ProcessListItemResult[snapshot.Processes.Count];
        for (int index = 0; index < snapshot.Processes.Count; index++)
        {
            ProcessStatusEntry item = snapshot.Processes[index];
            if (item.ProcessId <= 0
                || item.CreationTimeUtcTicks <= 0
                || string.IsNullOrWhiteSpace(item.Name)
                || Encoding.UTF8.GetByteCount(item.Name) > 512
                || item.WorkingSetBytes < 0
                || !double.IsFinite(item.TotalProcessorSeconds)
                || item.TotalProcessorSeconds < 0
                || !identities.Add((item.ProcessId, item.CreationTimeUtcTicks)))
            {
                return false;
            }
            items[index] = new ProcessListItemResult(
                item.ProcessId,
                item.Name,
                item.WorkingSetBytes,
                item.TotalProcessorSeconds);
        }
        string publicSort = sort switch
        {
            ProcessStatusSort.Cpu => "cpu",
            ProcessStatusSort.Memory => "memory",
            ProcessStatusSort.Name => "name",
            _ => throw new InvalidOperationException(),
        };
        result = new ProcessListResult(1, publicSort, snapshot.ObservedProcessCount, items);
        return true;
    }
}
