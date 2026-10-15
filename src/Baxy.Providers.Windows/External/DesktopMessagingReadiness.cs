using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// The element of a client's window that holds the keyboard focus, as UI Automation reads it: its control type, its
/// name, whether text typed now would go into it, and its runtime id (two reads of the same field share it).
/// </summary>
internal sealed record ClientFocus(string Kind, string Name, bool Editable, string Id);

/// <summary>
/// One read-only look at a client's window (ronda 24, «cliente en frío listo por interacción»): Answered is false
/// when nothing could be read (the worker is not up yet or did not answer in time); ContentShown when the window
/// exposes something a person interacts with (an editable field or a list), which a loading screen does not.
/// </summary>
internal sealed record ClientInteraction(bool Answered, bool ContentShown, ClientFocus? Focused)
{
    internal static readonly ClientInteraction Unanswered = new(false, false, null);
}

/// <summary>Reads a window's interaction state without input: nothing is pressed, clicked or focused.</summary>
internal interface IClientInteractionProbe
{
    /// <summary>Starts whatever the reads need, ahead of the first one; never waited on by a turn.</summary>
    void Prewarm();

    ValueTask<ClientInteraction> ReadAsync(nint handle, bool content, CancellationToken cancellationToken);
}

/// <summary>
/// The probe over the UI Automation worker («interaction» command). Until the worker has answered its first command
/// every read is Unanswered, so a turn never waits for the worker to start: the flow keeps its timed path then.
/// </summary>
internal sealed class UiaClientInteractionProbe : IClientInteractionProbe
{
    private static readonly TimeSpan ReadBudget = TimeSpan.FromMilliseconds(1500);
    private readonly IUiaWorker _worker;
    private Task? _warm;

    internal UiaClientInteractionProbe(IUiaWorker worker)
    {
        _worker = worker ?? throw new ArgumentNullException(nameof(worker));
    }

    // TZ-DC2: the worker is the Core's, already started by its prewarm (WindowsExternalCapabilityProvider), so this
    // completes at once and the first read of a Core's first search answers; a worker still starting is not waited for.
    public void Prewarm() => _warm ??= WarmAsync();

    private async Task WarmAsync()
    {
        try
        {
            await _worker.PrewarmAsync(CancellationToken.None).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException
            or System.ComponentModel.Win32Exception or ObjectDisposedException)
        {
            // A worker that cannot start leaves every read Unanswered.
        }
    }

    public async ValueTask<ClientInteraction> ReadAsync(nint handle, bool content, CancellationToken cancellationToken)
    {
        Prewarm();
        if (_warm is not { IsCompleted: true })
        {
            return ClientInteraction.Unanswered;
        }

        string command = new JsonObject
        {
            ["cmd"] = "interaction",
            ["hwnd"] = (long)handle,
            ["content"] = content,
        }.ToJsonString();
        using JsonDocument? answer = await _worker.SendAsync(command, ReadBudget, cancellationToken)
            .ConfigureAwait(false);
        return Parse(answer?.RootElement);
    }

    internal static ClientInteraction Parse(JsonElement? answer)
    {
        if (answer is not { ValueKind: JsonValueKind.Object } root
            || !root.TryGetProperty("ok", out JsonElement ok)
            || ok.ValueKind != JsonValueKind.True)
        {
            return ClientInteraction.Unanswered;
        }

        bool shown = root.TryGetProperty("content", out JsonElement contentShown)
            && contentShown.ValueKind == JsonValueKind.True;
        ClientFocus? focused = null;
        if (root.TryGetProperty("focused", out JsonElement focus) && focus.ValueKind == JsonValueKind.Object)
        {
            focused = new ClientFocus(
                Text(focus, "kind"),
                Text(focus, "name"),
                focus.TryGetProperty("editable", out JsonElement editable) && editable.ValueKind == JsonValueKind.True,
                Text(focus, "id"));
        }

        return new ClientInteraction(true, shown, focused);
    }

    private static string Text(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : string.Empty;
}

internal sealed partial class WindowsDesktopMessagingAutomation
{
    /// <summary>
    /// Ronda 24 (t1-c09, t2-c07, t3-c07 «mandale a Ron92 por …» with the client closed): the chat with the
    /// recipient was not opened, and nothing was typed into a conversation's composer, so nothing was written or sent.
    /// Not «recipient_identity_not_verified», which stays for a flow that may have typed near a composer.
    /// </summary>
    internal const string RecipientNotOpened = "recipient_not_opened";

    /// <summary>C3: the chat search showed no result naming the recipient; nothing was opened or written.</summary>
    internal const string RecipientNotFound = "recipient_not_found";

    // After a cold open, the window has to expose content a person interacts with within this clock.
    internal static readonly TimeSpan ClientContentBudget = TimeSpan.FromSeconds(15);

    // The shortcut that opens the client's chat search gets this long to put a new input in focus (the old fixed
    // wait), and once more, after Escape, when the first press showed nothing.
    internal static readonly TimeSpan SearchInputBudget = TimeSpan.FromMilliseconds(1400);
    internal static readonly TimeSpan SearchInputRetryBudget = TimeSpan.FromMilliseconds(2500);
    internal static readonly TimeSpan InteractionPoll = TimeSpan.FromMilliseconds(150);

    // After the row is chosen, the window's title is read for this long (it changed a minute later in r23 c07, one
    // read at 900 ms missed it).
    internal static readonly TimeSpan ChatTitleBudget = TimeSpan.FromSeconds(3);
    internal static readonly TimeSpan ChatTitlePoll = TimeSpan.FromMilliseconds(250);

    /// <summary>A window is ready for use when it shows interactive content, not when it has a title.</summary>
    internal static bool ClientInteractionReady(ClientInteraction read) => read.Answered && read.ContentShown;

    /// <summary>
    /// A shortcut opened an input when, after it, an editable field of the window has the focus and it is not the
    /// field that had it before (a conversation's composer keeps its id; the search input is a new one). With no
    /// editable field before (a cold client's focus on a panel), a composer the window focuses by itself also passes:
    /// this says where typing goes, not that it is a search, so the caller still checks the composer's picture
    /// before saying nothing was written (revisión 1 de r24).
    /// </summary>
    internal static bool ShortcutOpenedInput(ClientFocus? before, ClientFocus? after) =>
        after is not null
        && (after.Editable
            ? before is null || !before.Editable || !SameElement(before, after)
            : SearchRowKinds.Contains(after.Kind, StringComparer.Ordinal) && (before is null || !SameElement(before, after)));

    // Revisión 2 de r24: a search whose input points at its active result (aria-activedescendant in a web client)
    // is reported by UI Automation with the focus on that result row, not on the input (a4cfabc66: the quick
    // switcher's field «the tree does not report focused»). A row of a list that newly holds the focus after the
    // shortcut is the search open as well; typing still goes into its input. A button or a panel never is.
    private static readonly string[] SearchRowKinds = ["ListItem", "DataItem", "TreeItem"];

    private static bool SameElement(ClientFocus one, ClientFocus other) =>
        one.Id.Length > 0 || other.Id.Length > 0
            ? string.Equals(one.Id, other.Id, StringComparison.Ordinal)
            : string.Equals(one.Kind, other.Kind, StringComparison.Ordinal)
              && string.Equals(one.Name, other.Name, StringComparison.Ordinal);

    // Revisión 2 de r24: a client whose process started this long ago or less is the cold one of t1-c09, t2-c07 and
    // t3-c07 (opened by this turn or just before it). Only there may a search that was not seen open stop the name
    // from being typed: on a client running for longer the read cannot outvote the path that sent before the branch
    // (t4-c03 reached the confirmation in 8.6 s), so an unseen search keeps the old fixed wait and the name is typed.
    internal static readonly TimeSpan ColdClientSpan = TimeSpan.FromSeconds(90);

    internal static bool ClientStartedRecently(DateTime? startedAt, DateTime now) =>
        startedAt is { } started && now >= started && now - started < ColdClientSpan;

    internal static DateTime? ProcessStartTime(int processId)
    {
        try
        {
            using Process process = Process.GetProcessById(processId);
            return process.StartTime;
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException
            or System.ComponentModel.Win32Exception or NotSupportedException)
        {
            return null;
        }
    }

    /// <summary>What the search does after waiting for the shortcut's input.</summary>
    internal enum SearchStep
    {
        Type,
        Retry,
        Refuse,
    }

    /// <summary>
    /// After a wait for the shortcut's input: seen (or nothing readable), the name is typed. Not seen on a client
    /// started just now (<see cref="ClientStartedRecently"/>): Escape and the shortcut once more, then the name is
    /// never typed. Not seen on a client running for longer: typed as before the branch, after the same fixed wait,
    /// and the turn never says the composer was untouched (<see cref="ComposerUntouched"/> needs a seen input).
    /// </summary>
    internal static SearchStep AfterSearchWait(InputWait input, bool clientStartedRecently, bool retried) =>
        input != InputWait.NotOpened || !clientStartedRecently
            ? SearchStep.Type
            : retried ? SearchStep.Refuse : SearchStep.Retry;

    /// <summary>The outcome of waiting for a cold window's content: Ready, or the reads never answered.</summary>
    internal enum ContentWait
    {
        Ready,
        NotShown,
        Unanswered,
    }

    /// <summary>
    /// Polls the window until it shows interactive content, within <paramref name="budget"/>. When no read ever
    /// answered, the caller cannot tell and keeps its timed path.
    /// </summary>
    internal static async ValueTask<ContentWait> AwaitClientContentAsync(
        Func<CancellationToken, ValueTask<ClientInteraction>> read,
        TimeSpan budget,
        TimeSpan poll,
        CancellationToken cancellationToken)
    {
        bool answered = false;
        var clock = Stopwatch.StartNew();
        do
        {
            ClientInteraction now = await read(cancellationToken).ConfigureAwait(false);
            answered |= now.Answered;
            if (ClientInteractionReady(now))
            {
                return ContentWait.Ready;
            }

            await Task.Delay(poll, cancellationToken).ConfigureAwait(false);
        }
        while (clock.Elapsed < budget);

        return answered ? ContentWait.NotShown : ContentWait.Unanswered;
    }

    /// <summary>The outcome of waiting for a shortcut's input.</summary>
    internal enum InputWait
    {
        Opened,
        NotOpened,
        Unanswered,
    }

    /// <summary>
    /// Polls the window's focus after a shortcut until a new editable field has it, within <paramref name="budget"/>.
    /// Returns as soon as it is seen, so a client that answers fast is not kept waiting. When the read before the
    /// shortcut had no answer there is nothing to compare with (a worker that came up meanwhile would take the
    /// conversation's own composer for a new field): the whole budget is waited, as the old fixed wait did, and the
    /// outcome is Unanswered.
    /// </summary>
    internal static async ValueTask<InputWait> AwaitOpenedInputAsync(
        Func<CancellationToken, ValueTask<ClientInteraction>> read,
        ClientInteraction before,
        TimeSpan budget,
        TimeSpan poll,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(before);
        if (!before.Answered)
        {
            await Task.Delay(budget, cancellationToken).ConfigureAwait(false);
            return InputWait.Unanswered;
        }

        bool answered = false;
        var clock = Stopwatch.StartNew();
        do
        {
            await Task.Delay(poll, cancellationToken).ConfigureAwait(false);
            ClientInteraction now = await read(cancellationToken).ConfigureAwait(false);
            answered |= now.Answered;
            if (now.Answered && ShortcutOpenedInput(before.Focused, now.Focused))
            {
                return InputWait.Opened;
            }
        }
        while (clock.Elapsed < budget);

        return answered ? InputWait.NotOpened : InputWait.Unanswered;
    }

    // X1 (n1 t1-c09 on the notebook): the name typed, the search's first row is opened once its active result names
    // the recipient, read for this long; with no result row to read, after the old fixed wait.
    internal static readonly TimeSpan SearchResultBudget = TimeSpan.FromSeconds(3);
    internal static readonly TimeSpan UnreadResultWait = TimeSpan.FromMilliseconds(1200);

    /// <summary>
    /// X1 (n1 t1-c09 «mandale a Ron92 por discord…» on the notebook, client open on another view): a client that draws
    /// its filtered results late (G1 measured typed text 0.6–2.6 s late there) had its first row clicked after a fixed
    /// 1.2 s, while that row was still the one from before the filter: another chat opened and the send never ran.
    /// The search's active result (UI Automation puts the focus on it, <see cref="SearchRowKinds"/>) is read until it
    /// names the recipient, and the wait ends then. A row that never names it is waited for the whole budget; with no
    /// row to read (nothing answered, or the focus on the input) the old fixed wait is kept. Whether it was named, and
    /// the row: the one that named the recipient, or the last one read (null when none was).
    /// </summary>
    internal static async ValueTask<(bool Named, string? Row)> AwaitNamedResultAsync(
        Func<CancellationToken, ValueTask<ClientInteraction>> read,
        Func<string, bool> namesRecipient,
        TimeSpan poll,
        CancellationToken cancellationToken)
    {
        string? row = null;
        var clock = Stopwatch.StartNew();
        while (true)
        {
            ClientInteraction now = await read(cancellationToken).ConfigureAwait(false);
            if (now.Answered && now.Focused is { } focus && SearchRowKinds.Contains(focus.Kind, StringComparer.Ordinal))
            {
                if (namesRecipient(focus.Name))
                {
                    return (true, focus.Name);
                }

                row = focus.Name;
            }

            if (clock.Elapsed >= (row is not null ? SearchResultBudget : UnreadResultWait))
            {
                return (false, row);
            }

            await Task.Delay(poll, cancellationToken).ConfigureAwait(false);
        }
    }

    /// <summary>
    /// After a search that did not end on the recipient, no conversation's composer was touched only when the name
    /// went into an input the shortcut opened and the composer's picture, taken before the shortcut and again once
    /// the search was closed, did not change (unreadable counts as changed). Anything else may have left the name
    /// in a conversation.
    /// </summary>
    internal static bool ComposerUntouched(InputWait input, bool composerChanged) =>
        input == InputWait.Opened && !composerChanged;

    /// <summary>Reads <paramref name="matches"/> until it holds or <paramref name="budget"/> ends; the last read decides.</summary>
    internal static async ValueTask<bool> PollUntilAsync(
        Func<CancellationToken, ValueTask<bool>> matches,
        TimeSpan budget,
        TimeSpan poll,
        CancellationToken cancellationToken)
    {
        var clock = Stopwatch.StartNew();
        while (true)
        {
            if (await matches(cancellationToken).ConfigureAwait(false))
            {
                return true;
            }

            if (clock.Elapsed >= budget)
            {
                return false;
            }

            await Task.Delay(poll, cancellationToken).ConfigureAwait(false);
        }
    }

    /// <summary>
    /// The observation of a chat search that did not end on the recipient: when the text went only into an input the
    /// search itself opened (or nothing was typed), no conversation's composer was touched and nothing was written;
    /// otherwise the text may sit near a composer and the effect stays possible.
    /// </summary>
    internal static DesktopRecipientObservation UnverifiedChat(
        nint handle,
        int processId,
        bool composerUntouched) =>
        composerUntouched
            ? new(false, false, handle, processId, RecipientNotOpened)
            : new(false, true, handle, processId, "recipient_identity_not_verified");

    /// <summary>
    /// C3: no result of the chat search named the recipient, so nothing was clicked or opened: «recipient_not_found»
    /// with the row the search showed (null when none was read). Text that may have reached a composer keeps its
    /// possible effect and code.
    /// </summary>
    internal static DesktopRecipientObservation NotNamedInSearch(DesktopRecipientObservation unverified, string? row) =>
        unverified with
        {
            ErrorCode = unverified.EffectObserved ? unverified.ErrorCode : RecipientNotFound,
            Shown = row,
        };
}
