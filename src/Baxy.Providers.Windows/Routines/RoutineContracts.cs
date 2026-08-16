namespace Baxy.Providers.Windows.Routines;

public sealed record RoutineRecord(
    Guid Id,
    string Name,
    string WorkflowId,
    string WorkflowVersion,
    IReadOnlyList<string> InputFields,
    string TriggerKind,
    string? AppKey,
    bool Enabled,
    bool Deleted,
    long Revision,
    DateTimeOffset CreatedAtUtc,
    DateTimeOffset UpdatedAtUtc);

public interface IRoutineStore
{
    RoutineRecord CreatePhrase(string name, string phrase, string action = "media.control");
    RoutineRecord Read(Guid id, bool includeDeleted);
    IReadOnlyList<RoutineRecord> List(bool includeDeleted, int limit);
    RoutineRecord ResolveExact(string name, bool includeDeleted);
    RoutineRecord SetEnabled(Guid id, long expectedRevision, bool enabled);
    RoutineRecord Delete(Guid id, long expectedRevision, string reviewLabel);
    RoutineRecord Restore(Guid id, long expectedRevision);
}
