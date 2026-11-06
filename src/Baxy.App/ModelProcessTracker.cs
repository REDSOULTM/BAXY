using Baxy.Providers.Windows.SystemStatus;

namespace Baxy.App;

/// <summary>
/// Finds the model's processes (the mind, its python child and the llama-server below it) without listing the PC's
/// processes on every sample. The rail asks every 1.5 s; listing them (<c>Process.GetProcessesByName</c> reads the whole
/// process table and builds a <c>Process</c> for each entry, three times per sample) threw <see cref="OutOfMemoryException"/>
/// on a PC short of RAM and took the view down. Here the processes found are remembered and each sample only checks them
/// by id (one handle each); the process table is listed again only while no llama-server is known, and no more often
/// than <see cref="RescanInterval"/>.
/// </summary>
internal sealed class ModelProcessTracker
{
    internal static readonly TimeSpan RescanInterval = TimeSpan.FromSeconds(10);

    private readonly Func<IReadOnlyCollection<int>, string, IReadOnlyList<(int Id, int Parent)>> _scan;
    private readonly Func<int, int, bool> _isChildOf;
    private readonly Func<DateTimeOffset> _now;
    private int _mind;
    private List<(int Id, int Parent)> _pythons = [];
    private List<(int Id, int Parent)> _llamas = [];
    private DateTimeOffset _lastScan = DateTimeOffset.MinValue;

    internal ModelProcessTracker(
        Func<IReadOnlyCollection<int>, string, IReadOnlyList<(int Id, int Parent)>>? scan = null,
        Func<int, int, bool>? isChildOf = null,
        Func<DateTimeOffset>? now = null)
    {
        _scan = scan ?? WindowsModelResourceReader.ChildrenOf;
        _isChildOf = isChildOf ?? WindowsModelResourceReader.IsChildOf;
        _now = now ?? (static () => DateTimeOffset.UtcNow);
    }

    /// <summary>How many times the process table was listed (two lists per scan: python and llama-server).</summary>
    internal int Scans { get; private set; }

    /// <summary>The mind and the model processes under it. <see cref="OutOfMemoryException"/> propagates: the caller decides.</summary>
    internal List<int> ProcessesOf(int mind)
    {
        if (mind != _mind)
        {
            _mind = mind;
            _pythons = [];
            _llamas = [];
            _lastScan = DateTimeOffset.MinValue;
        }

        // Keep only the known processes that are still alive and still the children they were (ids are reused).
        _pythons = [.. _pythons.Where(entry => _isChildOf(entry.Id, entry.Parent))];
        _llamas = [.. _llamas.Where(entry => _isChildOf(entry.Id, entry.Parent))];
        if (_llamas.Count == 0 && _now() - _lastScan >= RescanInterval)
        {
            // Stamped first: a scan that ran out of memory must not be retried at once.
            _lastScan = _now();
            Scans++;
            IReadOnlyList<(int Id, int Parent)> pythons = _scan([_mind], "python");
            int[] parents = [_mind, .. pythons.Select(static entry => entry.Id)];
            IReadOnlyList<(int Id, int Parent)> llamas = _scan(parents, "llama-server");
            _pythons = [.. pythons];
            _llamas = [.. llamas];
        }

        return [mind, .. _pythons.Select(static entry => entry.Id), .. _llamas.Select(static entry => entry.Id)];
    }
}
