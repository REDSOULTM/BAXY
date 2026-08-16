using Baxy.Contracts;
using System.Text.Json.Serialization;

namespace Baxy.Kernel.Journal;

internal sealed record JournalPayload(
    [property: JsonRequired] long Sequence,
    [property: JsonRequired] DateTimeOffset TimestampUtc,
    [property: JsonRequired] string Phase,
    [property: JsonRequired] string RequestId,
    [property: JsonRequired] string MissionId,
    [property: JsonRequired] string InvocationId,
    [property: JsonRequired] string Operation,
    [property: JsonRequired] string RequestFingerprint,
    [property: JsonRequired] OperationResponse? Response);

internal sealed record JournalUnsignedEnvelope(
    [property: JsonRequired] int Version,
    [property: JsonRequired] string Authentication,
    [property: JsonRequired] JournalPayload Payload,
    [property: JsonRequired] string PreviousTag);

internal sealed record JournalEnvelope(
    [property: JsonRequired] int Version,
    [property: JsonRequired] string Authentication,
    [property: JsonRequired] JournalPayload Payload,
    [property: JsonRequired] string PreviousTag,
    [property: JsonRequired] string Tag);

internal sealed record JournalAnchorPosition(
    [property: JsonRequired] long Sequence,
    [property: JsonRequired] string LastTag,
    [property: JsonRequired] long JournalLength);

internal sealed record JournalAnchorPayload(
    [property: JsonRequired] int Version,
    [property: JsonRequired] string Authentication,
    [property: JsonRequired] string Phase,
    [property: JsonRequired] JournalAnchorPosition Current,
    [property: JsonRequired] JournalAnchorPosition? Next);

internal sealed record JournalAnchorEnvelope(
    [property: JsonRequired] JournalAnchorPayload Payload,
    [property: JsonRequired] string Tag);

internal static class JournalPhases
{
    public const string Started = "started";
    public const string Completed = "completed";
    public const string RetainedCompleted = "retained_completed";
}

internal static class JournalAnchorPhases
{
    public const string Committed = "committed";
    public const string CompactionPending = "compaction_pending";
}
