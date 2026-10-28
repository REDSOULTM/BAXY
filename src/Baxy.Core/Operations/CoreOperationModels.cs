using System.Text.Json.Serialization;
using Baxy.Providers.Windows.Infrastructure;

namespace Baxy.Core.Operations;

internal sealed class EmptyArguments;

internal sealed record CreateNoteArguments(
    [property: JsonRequired] string Title,
    [property: JsonRequired] string Content);

internal sealed record NoteSelectorArguments(
    string? NoteId,
    string? Title,
    string? ExpectedTitle,
    long? ExpectedRevision,
    bool? ExpectedIsTrashed);

internal sealed record ListNotesArguments(
    string? Scope,
    int? Limit,
    int? Offset);

// NewDocument (cu-v3-documento-nuevo): the person asked for a new document of the application, never one of theirs.
// Place, PlaceValue (estabilización, encargo C): a place of the application whose address its data declare
// (ApplicationPlaces), opened once the application is.
// BAXY Renew cu (C18 variante): a paste into a new document of Word or Excel already running, read back in that document.
internal sealed record PastedIntoOffice(int Version, string AppId, string Document, int Characters, bool NewDocument);

// PlaceValueAsSaid (Renew al máximo): the value is the person's words (a game store act's title or query), never a
// catalog number, even when it is only digits («1942»). Only GameStoreHandler sets it; app.open's schema does not
// declare it, so the model never sends it.
internal sealed record OpenApplicationArguments(
    [property: JsonRequired] string AppId,
    bool? Foreground = null,
    bool? ForControl = null,
    bool? NewDocument = null,
    string? Place = null,
    string? PlaceValue = null,
    bool? PlaceValueAsSaid = null);

// WindowsActivation: Windows activated the opened application by itself (a packaged app, or one that ignores the
// request to show without activating) and the front was handed back at once to the window that had it (v3 point 0).
// FrontRestored: that hand-back was read back as held; with WindowsActivation and without it, the opened application
// kept the front (cu-v3-foco-segunda: Windows may refuse it).
internal sealed record OpenApplicationResult(
    string AppId,
    string DisplayName,
    bool AlreadyRunning,
    int ProcessId,
    long WindowHandle,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] bool WindowsActivation = false,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] bool FrontRestored = false,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] bool NewDocument = false,
    // ShownWithoutFocus (r20b palanca 4): asked in front while the person worked in another window, it was raised above
    // that window without taking their keyboard.
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] bool ShownWithoutFocus = false,
    // PlaceRequested (estabilización, encargo C; auditoría K10): the place's address was handed to Windows. Nothing here
    // reads whether it arrived; a look at the window does.
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] bool PlaceRequested = false,
    // EffectReadBack (revisión 2026-10-22, C-5): false with a place, aids on or off: the opening is verified, whether
    // the place shows is not (the mind's outcome reads it as «enviado sin verificar»). Absent without a place.
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] bool? EffectReadBack = null,
    // Next (pc-ayudas, aid place_unverified): with a place, that it was only asked for and how to look; F019 said
    // «abrí Steam en la biblioteca» from placeRequested alone (continuation probe: 3/3 without it, 0/3 with it, the
    // model looked with input_visible_controls).
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] string? Next = null,
    // FrontChanged (review H2): the place's handler raised the application above the person's window; FrontRestored
    // then says whether the front went back to them.
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] bool FrontChanged = false,
    // PlaceGame (BAXY Renew cu, C04): the game whose page was asked for by its title, as its catalog found it.
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] PlacedGame? PlaceGame = null,
    // WindowId: the id the window operations take for the window this opening verified (e2e p3 E007: the model passed
    // windowHandle as windowId and read the refusal as «it is no longer open»).
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] string? WindowId = null,
    // Window (NB-R1 P1.12): the number the input operations take as «window» for the same window (input.text.type,
    // input.key.press, input.scroll, input.visible.click), named as their argument; WindowHandle, the same number, stays
    // with the receipt (OperationVisibleFacts). With only windowId the model typed into window 1 and 125, made up.
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingDefault)] long Window = 0,
    // ProcessName (BAXY Renew, notebook): the program a view names the window this opening verified by, as
    // ForegroundHeldBy and the keys' sentTo name a window (a packaged app's own: CalculatorApp, not its launcher calc).
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] string? ProcessName = null,
    // Foreground (BAXY Renew, notebook, F004): whether the window this opening verified holds the front when the opening
    // answers, asked in front or not; ForegroundHeldBy: the window in front instead (none when Windows reports none).
    bool Foreground = false,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] WindowName? ForegroundHeldBy = null,
    // PlaceWindowChanged (Renew al máximo, 6.2): with a place, whether the application's window was drawn differently
    // within the place's watch after its address, aids on or off; absent when no drawing was read. A change does not
    // prove the place arrived (a window starting cold nearly always changes).
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] bool? PlaceWindowChanged = null);

// A game of a catalog: its number there and its name.
internal sealed record PlacedGame(string Number, string Name);

// A window as the receipts name it: its title and the program a view names it by.
internal sealed record WindowName(string Title, string Process);

internal sealed record AudioVolumeArguments(
    [property: JsonRequired] int Level);

internal sealed record AudioMuteArguments(
    [property: JsonRequired] bool State);

internal sealed record AudioEndpointStateResult(
    int VolumePercent,
    bool Muted);

internal sealed record AudioControlResult(
    string Operation,
    string TargetId,
    string EndpointIdHash,
    AudioEndpointStateResult Baseline,
    AudioEndpointStateResult Final,
    bool Applied,
    bool Reconciled);

internal sealed record AudioStatusResult(
    string Operation,
    string TargetId,
    string EndpointIdHash,
    AudioEndpointStateResult State)
{
    public string? EndpointName { get; init; }
}

internal sealed record NoteResult(
    string NoteId,
    string Title,
    string Content,
    DateTimeOffset CreatedAtUtc,
    DateTimeOffset UpdatedAtUtc,
    DateTimeOffset? TrashedAtUtc,
    long Revision,
    bool IsTrashed);

internal sealed record NoteSummaryResult(
    string NoteId,
    string Title,
    DateTimeOffset CreatedAtUtc,
    DateTimeOffset UpdatedAtUtc,
    DateTimeOffset? TrashedAtUtc,
    long Revision,
    bool IsTrashed);

internal sealed record NoteAmbiguityCandidateResult(
    string NoteId,
    string ContentPreview,
    DateTimeOffset CreatedAtUtc,
    DateTimeOffset UpdatedAtUtc,
    long Revision,
    bool IsTrashed);

internal sealed record NoteAmbiguityResult(
    IReadOnlyList<NoteAmbiguityCandidateResult> Candidates);

internal sealed record NoteListResult(
    IReadOnlyList<NoteSummaryResult> Notes,
    int Count,
    int TotalCount,
    string Scope,
    int Limit,
    int Offset,
    int? NextOffset);

internal sealed record SystemStatusArguments(string? Scope);

internal sealed record ProcessListArguments(string? Sort, int? Limit);

internal sealed record ProcessListItemResult(
    int ProcessId,
    string Name,
    long WorkingSetBytes,
    double TotalProcessorSeconds,
    double? CpuUsagePercent,
    double? SampleDurationSeconds)
{
    // Holdout v4 (falsedad, «69 % de CPU» for 0.69 %): the reading with its unit (ReadingUnits). cpuUsage is the share of
    // all the logical processors together.
    public string? CpuUsage => ReadingUnits.Percent(CpuUsagePercent);

    public string WorkingSet => ReadingUnits.Size(WorkingSetBytes);
}

internal sealed record ProcessListResult(
    int Version,
    string Sort,
    int ObservedProcessCount,
    IReadOnlyList<ProcessListItemResult> Processes,
    int ReturnedProcessCount,
    string ObservationScope,
    int? LogicalProcessorCount,
    // Ronda final 8 (regla 3): false when the observation stopped before every process.
    bool ObservationComplete,
    // Renew al máximo (w8): processes Windows did not let BAXY read (another user's, protected ones), not in the list.
    int UnmeasuredProcessCount);

internal sealed record SystemStatusCpuResult(
    double UsagePercent,
    int LogicalProcessorCount,
    string? Model,
    int? PhysicalCoreCount)
{
    // Holdout v4 (falsedad, «69 % de CPU» for 0.69 %): the reading with its unit (ReadingUnits).
    public string Usage => ReadingUnits.Percent(UsagePercent);
}

internal sealed record SystemStatusMemoryResult(
    ulong TotalBytes,
    ulong AvailableBytes,
    ulong? InstalledBytes)
{
    // Holdout v4 (falsedad, units): the sizes written with their unit, and the part in use (total less available).
    public string Total => ReadingUnits.Size(TotalBytes);

    public string Available => ReadingUnits.Size(AvailableBytes);

    public string? Installed => ReadingUnits.Size(InstalledBytes);

    public string InUse => ReadingUnits.Size(TotalBytes - Math.Min(AvailableBytes, TotalBytes));

    public string? InUseShare => ReadingUnits.Share(TotalBytes - Math.Min(AvailableBytes, TotalBytes), TotalBytes);
}

internal sealed record SystemStatusDiskResult(
    long TotalBytes,
    long AvailableBytes)
{
    // Holdout v4 (falsedad, units): the sizes written with their unit, and the part in use (total less available).
    public string Total => ReadingUnits.Size(TotalBytes);

    public string Available => ReadingUnits.Size(AvailableBytes);

    public string InUse => ReadingUnits.Size(Math.Max(0, TotalBytes - AvailableBytes));

    public string? InUseShare => ReadingUnits.Share(Math.Max(0, TotalBytes - AvailableBytes), TotalBytes);
}

internal sealed record SystemStatusBatteryResult(
    bool? IsPresent,
    int? ChargePercent,
    bool? IsCharging,
    bool? IsAcOnline)
{
    // Holdout v4 (falsedad, units): the charge written with its unit.
    public string? Charge => ReadingUnits.Percent(ChargePercent);
}

internal sealed record SystemStatusOperatingSystemResult(
    int MajorVersion,
    int MinorVersion,
    int BuildNumber,
    string Architecture,
    bool IsWorkstation,
    string Caption);

internal sealed record SystemStatusFailureResult(
    string Scope,
    string ErrorCode);

internal sealed record SystemStatusResult(
    string Scope,
    SystemStatusCpuResult? Cpu,
    SystemStatusMemoryResult? Memory,
    SystemStatusDiskResult? Disk,
    SystemStatusBatteryResult? Battery,
    SystemStatusOperatingSystemResult? Os,
    long? UptimeSeconds,
    IReadOnlyList<SystemStatusFailureResult> Failures);
