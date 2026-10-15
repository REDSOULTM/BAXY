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

/// <summary>
/// Authenticated pointer from an anchor to the archived segment just before it:
/// its number and the exact position (sequence, last tag, length) it was sealed at.
/// </summary>
internal sealed record JournalArchiveLink(
    [property: JsonRequired] long Segment,
    [property: JsonRequired] JournalAnchorPosition Position);

/// <summary>
/// <see cref="Segment"/> and <see cref="Archive"/> are set only on an archived
/// segment's own anchor (its number and its link to the archived segment before
/// it). The live anchor never carries them, so it keeps the exact canonical bytes
/// and HMAC of the format before rotation and a Core rolled back to that format
/// still opens the live segment; the rotation state lives in the segment manifest.
/// </summary>
internal sealed record JournalAnchorPayload(
    [property: JsonRequired] int Version,
    [property: JsonRequired] string Authentication,
    [property: JsonRequired] string Phase,
    [property: JsonRequired] JournalAnchorPosition Current,
    [property: JsonRequired] JournalAnchorPosition? Next,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] long? Segment = null,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] JournalArchiveLink? Archive = null);

internal sealed record JournalAnchorEnvelope(
    [property: JsonRequired] JournalAnchorPayload Payload,
    [property: JsonRequired] string Tag);

internal sealed record JournalRetiredState(
    [property: JsonRequired] long Count,
    [property: JsonRequired] long Length,
    [property: JsonRequired] string Tag);

internal sealed record JournalRotationIntent(
    [property: JsonRequired] JournalArchiveLink Link,
    [property: JsonRequired] JournalAnchorPosition Next);

/// <summary>
/// The rotation state, in its own authenticated sidecar beside the live anchor:
/// the retained archived segments (newest first), the highest segment number left
/// by an earlier reset of the journal (<see cref="Floor"/>), pruned segments whose
/// files are still being deleted, the authenticated length of the retired-id file,
/// and, while a rotation is in flight, its intent.
/// </summary>
internal sealed record JournalSegmentManifest(
    [property: JsonRequired] int Version,
    [property: JsonRequired] string Authentication,
    [property: JsonRequired] string Phase,
    [property: JsonRequired] JournalArchiveLink[] Segments,
    [property: JsonRequired] long Floor,
    [property: JsonRequired] long[] Pruned,
    [property: JsonRequired] JournalRetiredState Retired,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] JournalRotationIntent? Pending = null);

internal sealed record JournalSegmentManifestEnvelope(
    [property: JsonRequired] JournalSegmentManifest Payload,
    [property: JsonRequired] string Tag);

/// <summary>
/// Authenticated memo of one full scan of a sealed segment: the invocations it
/// completed and the ones it left incomplete, bound to the segment's number, the
/// authenticated position it was sealed at (whose last tag closes its HMAC chain)
/// and its file's last write time. A later open trusts it instead of scanning the
/// whole segment again only while all of that still matches; anything else (a
/// different key, length, time or position) scans the segment, which stays the
/// authority. Reading a completion back from the segment always scans it again.
/// </summary>
internal sealed record JournalSegmentIndex(
    [property: JsonRequired] int Version,
    [property: JsonRequired] string Authentication,
    [property: JsonRequired] long Segment,
    [property: JsonRequired] JournalAnchorPosition Position,
    [property: JsonRequired] long LastWriteTimeUtcTicks,
    [property: JsonRequired] JournalSegmentIndexEntry[] Completed,
    [property: JsonRequired] JournalSegmentIndexEntry[] Incomplete);

internal sealed record JournalSegmentIndexEntry(
    [property: JsonRequired] string InvocationId,
    [property: JsonRequired] string RequestFingerprint);

internal sealed record JournalSegmentIndexEnvelope(
    [property: JsonRequired] JournalSegmentIndex Payload,
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
    public const string Archived = "archived";
}

internal static class JournalManifestPhases
{
    public const string Committed = "committed";
    public const string RotationPending = "rotation_pending";
}
