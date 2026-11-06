using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// The element of a client's window that holds the keyboard focus, as UI Automation reads it: its control type, its
/// name, whether text typed now would go into it, its runtime id (two reads of the same field share it), and whether
/// it sits inside a dialog of the window's page (ronda final 28: a web client's quick switcher is one).
/// </summary>
internal sealed record ClientFocus(
    string Kind, string Name, bool Editable, string Id, bool InDialog = false, ScreenBox? Box = null);

/// <summary>An element's rectangle in screen pixels, as UI Automation reads it.</summary>
internal readonly record struct ScreenBox(int Left, int Top, int Width, int Height)
{
    internal int CentreX => Left + Width / 2;

    internal int CentreY => Top + Height / 2;
}

/// <summary>An editable field a client's window shows: its identity (<see cref="ClientFocus.Id"/>) and where it is, never its text.</summary>
internal sealed record ClientField(string Id, ScreenBox Box, bool HasFocus = false);

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

    /// <summary>The editable fields the window shows; none when it could not be read.</summary>
    ValueTask<IReadOnlyList<ClientField>> EditableFieldsAsync(nint handle, CancellationToken cancellationToken) =>
        ValueTask.FromResult<IReadOnlyList<ClientField>>([]);

    /// <summary>Where the window shows exactly this name, dialogs of its page left out; nowhere when it could not be read.</summary>
    ValueTask<IReadOnlyList<ScreenBox>> ShownNameBoxesAsync(nint handle, string name, CancellationToken cancellationToken) =>
        ValueTask.FromResult<IReadOnlyList<ScreenBox>>([]);

    /// <summary>Encargo 98: the one act of this probe, no key and no click: the whole text of the focused field selected
    /// by UI Automation and read back; false when it could not be.</summary>
    ValueTask<bool> SelectFocusedTextAsync(nint handle, CancellationToken cancellationToken) =>
        ValueTask.FromResult(false);

    /// <summary>Uso-128: how many dialogs of the page are open, wherever the focus is; null when it could not be read.</summary>
    ValueTask<int?> OpenDialogsAsync(nint handle, CancellationToken cancellationToken) =>
        ValueTask.FromResult<int?>(null);

    /// <summary>Uso-128: the client's voice panel, read without touching it: whether it shows a button of these names and
    /// the «channel / server» it says; not connected when it could not be read.</summary>
    ValueTask<VoicePanel> VoicePanelAsync(nint handle, IReadOnlyList<string> disconnectNames, CancellationToken cancellationToken) =>
        ValueTask.FromResult(new VoicePanel(false, null));

    /// <summary>Uso-128: the rows with a name and a kind the window shows («Ana (mensaje directo)»); none when not read.</summary>
    ValueTask<IReadOnlyList<string>> ShownRowsAsync(nint handle, CancellationToken cancellationToken) =>
        ValueTask.FromResult<IReadOnlyList<string>>([]);
}

/// <summary>What a client's voice panel says: connected (its disconnect button is there) and where («channel / server»).</summary>
internal sealed record VoicePanel(bool Connected, string? Place);

/// <summary>
/// Uso real 2026-11-05 (G6, the PC's WhatsApp: «abre el chat con…» told «whatsapp_client_still_starting» after its whole
/// clock, with the chat list on the screen): this client's window is a WinUI frame whose own UI Automation tree is its
/// caption buttons and an empty web view pane (9 elements, no field), and its content is a top-level window of a process
/// it started (a WebView2 runtime's Chrome_WidgetWin_1, 518 elements: the search field, the chat grid), no child of the
/// frame. So no read of the frame could see the content. The reads go to the window a person sees
/// (<see cref="VisibleControlSurface.FamilyContentWindows"/>, which the view already uses for the same clients); a client
/// that draws in its own window has none and is read as itself.
/// </summary>
internal sealed class ContentWindowProbe : IClientInteractionProbe
{
    private readonly IClientInteractionProbe _reads;
    private readonly Func<nint, IReadOnlyList<nint>> _contentWindows;

    internal ContentWindowProbe(IClientInteractionProbe reads, Func<nint, IReadOnlyList<nint>>? contentWindows = null)
    {
        _reads = reads ?? throw new ArgumentNullException(nameof(reads));
        _contentWindows = contentWindows ?? VisibleControlSurface.FamilyContentWindows;
    }

    private nint Surface(nint handle) => _contentWindows(handle) is { Count: > 0 } windows ? windows[0] : handle;

    public void Prewarm() => _reads.Prewarm();

    public ValueTask<ClientInteraction> ReadAsync(nint handle, bool content, CancellationToken cancellationToken) =>
        _reads.ReadAsync(Surface(handle), content, cancellationToken);

    public ValueTask<IReadOnlyList<ClientField>> EditableFieldsAsync(nint handle, CancellationToken cancellationToken) =>
        _reads.EditableFieldsAsync(Surface(handle), cancellationToken);

    public ValueTask<IReadOnlyList<ScreenBox>> ShownNameBoxesAsync(nint handle, string name, CancellationToken cancellationToken) =>
        _reads.ShownNameBoxesAsync(Surface(handle), name, cancellationToken);

    public ValueTask<bool> SelectFocusedTextAsync(nint handle, CancellationToken cancellationToken) =>
        _reads.SelectFocusedTextAsync(Surface(handle), cancellationToken);

    public ValueTask<int?> OpenDialogsAsync(nint handle, CancellationToken cancellationToken) =>
        _reads.OpenDialogsAsync(Surface(handle), cancellationToken);

    public ValueTask<VoicePanel> VoicePanelAsync(nint handle, IReadOnlyList<string> disconnectNames, CancellationToken cancellationToken) =>
        _reads.VoicePanelAsync(Surface(handle), disconnectNames, cancellationToken);

    public ValueTask<IReadOnlyList<string>> ShownRowsAsync(nint handle, CancellationToken cancellationToken) =>
        _reads.ShownRowsAsync(Surface(handle), cancellationToken);
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

    public async ValueTask<IReadOnlyList<ClientField>> EditableFieldsAsync(nint handle, CancellationToken cancellationToken)
    {
        Prewarm();
        if (_warm is not { IsCompleted: true })
        {
            return [];
        }

        string command = new JsonObject
        {
            ["cmd"] = "interaction",
            ["hwnd"] = (long)handle,
            ["fields"] = true,
        }.ToJsonString();
        using JsonDocument? answer = await _worker.SendAsync(command, ReadBudget, cancellationToken)
            .ConfigureAwait(false);
        return ParseFields(answer?.RootElement);
    }

    public async ValueTask<IReadOnlyList<ScreenBox>> ShownNameBoxesAsync(nint handle, string name, CancellationToken cancellationToken)
    {
        Prewarm();
        if (_warm is not { IsCompleted: true })
        {
            return [];
        }

        string command = new JsonObject
        {
            ["cmd"] = "interaction",
            ["hwnd"] = (long)handle,
            ["shows"] = name,
        }.ToJsonString();
        using JsonDocument? answer = await _worker.SendAsync(command, ReadBudget, cancellationToken)
            .ConfigureAwait(false);
        return ParseShownBoxes(answer?.RootElement);
    }

    public async ValueTask<bool> SelectFocusedTextAsync(nint handle, CancellationToken cancellationToken)
    {
        Prewarm();
        if (_warm is not { IsCompleted: true })
        {
            return false;
        }

        using JsonDocument? answer = await _worker.SendAsync(
            FocusedFieldSelection.Command(handle), ReadBudget, cancellationToken).ConfigureAwait(false);
        return FocusedFieldSelection.Selected(answer);
    }

    public async ValueTask<int?> OpenDialogsAsync(nint handle, CancellationToken cancellationToken)
    {
        Prewarm();
        if (_warm is not { IsCompleted: true })
            return null;
        string command = new JsonObject { ["cmd"] = "interaction", ["hwnd"] = (long)handle, ["dialogs"] = true }.ToJsonString();
        using JsonDocument? answer = await _worker.SendAsync(command, ReadBudget, cancellationToken).ConfigureAwait(false);
        return answer?.RootElement is { ValueKind: JsonValueKind.Object } root
            && root.TryGetProperty("dialogs", out JsonElement count) && count.TryGetInt32(out int open) && open >= 0
                ? open
                : null;
    }

    public async ValueTask<VoicePanel> VoicePanelAsync(nint handle, IReadOnlyList<string> disconnectNames, CancellationToken cancellationToken)
    {
        Prewarm();
        if (_warm is not { IsCompleted: true })
            return new(false, null);
        JsonArray names = [];
        foreach (string name in disconnectNames)
            names.Add((JsonNode?)JsonValue.Create(name));
        string command = new JsonObject { ["cmd"] = "interaction", ["hwnd"] = (long)handle, ["voicePanel"] = names }.ToJsonString();
        using JsonDocument? answer = await _worker.SendAsync(command, ReadBudget, cancellationToken).ConfigureAwait(false);
        return ParseVoicePanel(answer?.RootElement);
    }

    internal static VoicePanel ParseVoicePanel(JsonElement? answer) =>
        answer is { ValueKind: JsonValueKind.Object } root
        && root.TryGetProperty("voiceConnected", out JsonElement connected) && connected.ValueKind == JsonValueKind.True
            ? new(true, Text(root, "voicePlace") is { Length: > 0 } place ? place : null)
            : new(false, null);

    public async ValueTask<IReadOnlyList<string>> ShownRowsAsync(nint handle, CancellationToken cancellationToken)
    {
        Prewarm();
        if (_warm is not { IsCompleted: true })
            return [];
        string command = new JsonObject { ["cmd"] = "interaction", ["hwnd"] = (long)handle, ["rows"] = true }.ToJsonString();
        using JsonDocument? answer = await _worker.SendAsync(command, ReadBudget, cancellationToken).ConfigureAwait(false);
        return answer?.RootElement is { ValueKind: JsonValueKind.Object } root
            && root.TryGetProperty("rows", out JsonElement rows) && rows.ValueKind == JsonValueKind.Array
                ? [.. rows.EnumerateArray().Where(static row => row.ValueKind == JsonValueKind.String).Select(static row => row.GetString()!)]
                : [];
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
                Text(focus, "id"),
                focus.TryGetProperty("dialog", out JsonElement dialog) && dialog.ValueKind == JsonValueKind.True,
                Box(focus));
        }

        return new ClientInteraction(true, shown, focused);
    }

    internal static IReadOnlyList<ClientField> ParseFields(JsonElement? answer)
    {
        if (answer is not { ValueKind: JsonValueKind.Object } root
            || !root.TryGetProperty("ok", out JsonElement ok)
            || ok.ValueKind != JsonValueKind.True
            || !root.TryGetProperty("fields", out JsonElement fields)
            || fields.ValueKind != JsonValueKind.Array)
        {
            return [];
        }

        return [.. fields.EnumerateArray()
            .Where(field => Box(field) is not null)
            .Select(field => new ClientField(
                Text(field, "id"),
                Box(field)!.Value,
                field.TryGetProperty("focused", out JsonElement focused) && focused.ValueKind == JsonValueKind.True))];
    }

    internal static IReadOnlyList<ScreenBox> ParseShownBoxes(JsonElement? answer) =>
        answer is { ValueKind: JsonValueKind.Object } root
        && root.TryGetProperty("shownAt", out JsonElement places) && places.ValueKind == JsonValueKind.Array
            ? [.. places.EnumerateArray().Select(place => BoxOf(place)).OfType<ScreenBox>()]
            : [];

    private static ScreenBox? Box(JsonElement element) =>
        element.TryGetProperty("box", out JsonElement box) ? BoxOf(box) : null;

    private static ScreenBox? BoxOf(JsonElement box) =>
        box.ValueKind == JsonValueKind.Object
        && box.TryGetProperty("x", out JsonElement x) && x.TryGetInt32(out int left)
        && box.TryGetProperty("y", out JsonElement y) && y.TryGetInt32(out int top)
        && box.TryGetProperty("w", out JsonElement w) && w.TryGetInt32(out int width)
        && box.TryGetProperty("h", out JsonElement h) && h.TryGetInt32(out int height)
            ? new ScreenBox(left, top, width, height)
            : null;

    private static string Text(JsonElement element, string name) =>
        element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : string.Empty;
}

internal sealed partial class WindowsDesktopMessagingAutomation
{
    /// <summary>
    /// Ronda 24 (t1-c09, t2-c07, t3-c07 «mandale a Nube77 por …» with the client closed): the chat with the
    /// recipient was not opened, and nothing was typed into a conversation's composer, so nothing was written or sent.
    /// Not «recipient_identity_not_verified», which stays for a flow that may have typed near a composer.
    /// </summary>
    internal const string RecipientNotOpened = "recipient_not_opened";

    /// <summary>The chat search could not be found or did not take the focus, or the name typed reached something else.</summary>
    internal const string SearchFocusNotVerified = "search_focus_not_verified";

    /// <summary>
    /// The chat search among the fields a client's window shows (its conversation's composer is one too, lying beside the
    /// chat list and under it): the topmost field in the left half of the window; none when no field lies there.
    /// </summary>
    internal static ClientField? ChatSearchField(IReadOnlyList<ClientField> fields, ScreenBox window) =>
        fields.Where(field => field.Box.CentreX >= window.Left && field.Box.CentreX < window.CentreX
                && field.Box.CentreY >= window.Top && field.Box.CentreY < window.Top + window.Height)
            .OrderBy(field => field.Box.Top)
            .FirstOrDefault();

    /// <summary>
    /// Whether that field, among the fields read now, holds the focus: what is typed now goes there and nowhere else. Read
    /// on the field and not as UI Automation's focused element: over a web view's window that element is the frame's pane
    /// (measured, with the field holding the caret).
    /// </summary>
    internal static bool HoldsTheFocus(ClientField field, IReadOnlyList<ClientField> now) =>
        now.Any(read => read.HasFocus && string.Equals(read.Id, field.Id, StringComparison.Ordinal));

    // A click on the search field gets this long to put the focus in it.
    internal static readonly TimeSpan SearchFocusBudget = TimeSpan.FromMilliseconds(1400);

    /// <summary>C3: the chat search showed no result naming the recipient; nothing was opened or written.</summary>
    internal const string RecipientNotFound = "recipient_not_found";

    /// <summary>Uso-128: a voice channel's row was pressed and its voice panel was not read saying so.</summary>
    internal const string VoiceJoinNotVerified = "voice_join_not_verified";

    /// <summary>Uso-128: a voice channel's row found by a call whose yes was not asked for it: not pressed.</summary>
    internal const string VoiceChannelNotPressed = "voice_channel_not_pressed";

    // Uso-128 (2026-11-05): Discord's panel, read on the real client in Spanish; its disconnect button in the languages this
    // adapter already reads that client's voice buttons in (ClientVoiceScript: «Silenciar» / «Mute»). Another language is said
    // as a join not verified.
    internal static readonly string[] DisconnectButtonNames = ["Desconectar", "Disconnect"];

    // A press takes a moment to connect (the panel appears once the client has joined).
    internal static readonly TimeSpan VoiceJoinBudget = TimeSpan.FromSeconds(8);

    // Uso-128: the voice panel's «channel / server» names what was asked: the channel exactly and, when named, the server.
    internal static bool PlaceNames(string? place, string name, string? server)
    {
        if (string.IsNullOrWhiteSpace(place))
            return false;
        string[] parts = place.Split(" / ", 2, StringSplitOptions.TrimEntries);
        return NamesRecipient(parts[0], name) && (server is null || (parts.Length == 2 && NamesRecipient(parts[1], server)));
    }

    internal static string? PlaceServer(string? place) =>
        place?.Split(" / ", 2, StringSplitOptions.TrimEntries) is { Length: 2 } parts ? parts[1] : null;

    // A row's own name, its kind and what follows set aside: «Ana (mensaje directo)», «Sala (canal de voz), Gremio»,
    // «Sala de Pedro, Canal de voz, Gremio», «Sala — canal de voz, Gremio». Review R1: only a mark that is a kind, whole and
    // closing the part, is set aside: «Sala (vieja)» and «Sala — dos» are other channels than «Sala».
    internal static string RowOwnName(string row) => ReadRow(row).Name;

    // The server a voice row names after its name and kind; null when it names none.
    internal static string? VoiceRowServer(string row) => ReadRow(row).Server;

    // The kinds a row writes, in the languages this adapter reads the client in.
    private static readonly string[] VoiceKinds = ["canal de voz", "voice channel"];
    private static readonly string[] TextKinds = ["canal de texto", "text channel"];
    private static readonly string[] DirectKinds = ["mensaje directo", "direct message"];
    private static readonly string[] KindMarks = [" (", " — ", " – "];

    // A row's name, kind and server. Review R1: the name holds everything before its kind, so a comma of a voice channel's name is
    // the name's too (Discord allows them). A kind in words the client was not read writing still counts as a voice channel, with
    // its whole text as the name: its row is pressed only after the yes, and only when that whole text was asked for.
    private static (string Name, bool Voice, string? Server) ReadRow(string row)
    {
        string[] parts = row.Split(", ", StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length == 0)
            return (string.Empty, false, null);
        // «Sala (canal de voz), Canal de texto, Club»: the kind in its own place says what the name holds is only the name. With no
        // third part, that second part may be a server called so.
        if (parts.Length > 2 && TextKinds.Contains(Fold(parts[1])))
            return (parts[0], false, parts[2]);
        if (parts.Length > 1 && IsVoiceKind(parts[1]))
            return (NameAndKind(parts[0]).Name, true, parts.ElementAtOrDefault(2));
        for (int part = 0; part < parts.Length; part++)
        {
            string text = parts[part];
            string before = string.Join(", ", parts[..part]);
            string? after = parts.ElementAtOrDefault(part + 1);
            (string own, string kind) = NameAndKind(text);
            if (kind.Length > 0)
                return (before.Length > 0 ? before + ", " + own : own, VoiceKinds.Contains(kind), after);
            if (part > 0 && (IsVoiceKind(text) || (part == 1 && BareVoice(text))))
                return (before, true, after);
            if (WritesVoiceKind(text) || KindMarks.Any(mark => text.LastIndexOf(mark, StringComparison.Ordinal) is > 0 and var at && BareVoice(text[(at + mark.Length)..])))
                return (string.Join(", ", parts[..(part + 1)]), true, after);
        }

        return (parts[0], false, null);
    }

    // A part of a row split at a kind closing it, whole, in brackets or after a dash; Kind is empty when no kind closes it.
    private static (string Name, string Kind) NameAndKind(string part)
    {
        foreach (string mark in KindMarks)
        {
            string close = mark == " (" ? ")" : string.Empty;
            int at = part.LastIndexOf(mark, StringComparison.Ordinal);
            if (at <= 0 || !part.EndsWith(close, StringComparison.Ordinal))
                continue;
            string kind = Fold(part[(at + mark.Length)..^close.Length]);
            if (VoiceKinds.Concat(TextKinds).Concat(DirectKinds).Contains(kind))
                return (part[..at].Trim(), kind);
        }

        return (part.Trim(), string.Empty);
    }

    // Whole words, never letters inside a name («invoices», «Vozarrón») or an account («voice.channel», which has no space).
    private static bool WritesVoiceKind(string text) =>
        text.Contains(' ', StringComparison.Ordinal) && VoiceKinds.Any(kind => ContainsPhrase(text, kind));

    private static bool IsVoiceKind(string text) =>
        text.Contains(' ', StringComparison.Ordinal) && VoiceKinds.Contains(Fold(text));

    private static bool BareVoice(string text) => Fold(text) is "voz" or "voice";

    // Uso-128: «the name the person said against the names the window shows»: the owner's ruling (2026-09-19) that what was
    // misheard BAXY fixes. A form compared, no meaning: at most half the letters apart (Levenshtein over the folded letters,
    // the bound uso-119 measured), whole or against the name's first word; the closest three. The model asks; nothing opens.
    internal static IReadOnlyList<string> AlikeNames(string said, IEnumerable<string> rows)
    {
        string wanted = Fold(said).Replace(" ", string.Empty, StringComparison.Ordinal);
        if (wanted.Length < 3)
            return [];
        return [.. rows
            .Select(RowOwnName)
            .Where(static name => name.Length > 0)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Select(name => (Name: name, Apart: LettersApartShare(wanted, name)))
            .Where(static row => row.Apart <= 0.5)
            .OrderBy(static row => row.Apart)
            .ThenBy(static row => row.Name, StringComparer.Ordinal)
            .Take(3)
            .Select(static row => row.Name)];
    }

    private static double LettersApartShare(string wanted, string name)
    {
        string folded = Fold(name);
        double whole = ShareOf(wanted, folded.Replace(" ", string.Empty, StringComparison.Ordinal));
        string first = folded.Split(' ', StringSplitOptions.RemoveEmptyEntries).FirstOrDefault() ?? string.Empty;
        return Math.Min(whole, ShareOf(wanted, first));
    }

    private static double ShareOf(string left, string right)
    {
        if (right.Length < 3)
            return 1;
        int[] previous = [.. Enumerable.Range(0, right.Length + 1)];
        for (int i = 1; i <= left.Length; i++)
        {
            int[] current = new int[right.Length + 1];
            current[0] = i;
            for (int j = 1; j <= right.Length; j++)
                current[j] = Math.Min(Math.Min(previous[j] + 1, current[j - 1] + 1), previous[j - 1] + (left[i - 1] == right[j - 1] ? 0 : 1));
            previous = current;
        }

        return previous[right.Length] / (double)Math.Max(left.Length, right.Length);
    }

    // After a cold open, the window has to expose content a person interacts with within this clock.
    internal static readonly TimeSpan ClientContentBudget = TimeSpan.FromSeconds(15);

    // The shortcut that opens the client's chat search gets this long to put a new input in focus (the old fixed
    // wait), and once more (with no Escape before it, ronda final 26-27) when the first press showed nothing.
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
    /// field that had it before (a conversation's composer keeps its id; the search input is a new one). Ronda final
    /// 28 (regla 3): only a focus inside a dialog of the page is the switcher (with the switcher open before, Ctrl+K
    /// closes it and the composer, a new field outside any dialog, takes the focus; a cold client's own composer is
    /// no switcher either).
    /// </summary>
    internal static bool ShortcutOpenedInput(ClientFocus? before, ClientFocus? after) =>
        after is { InDialog: true }
        && (after.Editable
            ? before is null || !before.Editable || !SameElement(before, after)
            : SearchRowKinds.Contains(after.Kind, StringComparer.Ordinal) && (before is null || !SameElement(before, after)));

    /// <summary>
    /// Ronda final 28 (regla 3): the focus, before any shortcut, sits inside a dialog of the page: the switcher already
    /// open (its field or its active result) or another of the client's dialogs. Ctrl+K would close an open switcher
    /// and the name would go to the conversation's composer: no key is sent.
    /// </summary>
    internal static bool SearchStateUnknown(ClientFocus? focus) => focus is { InDialog: true };

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

    /// <summary>What the search does after waiting for the shortcut's input.</summary>
    internal enum SearchStep
    {
        Type,
        Retry,
        Refuse,
    }

    /// <summary>
    /// After a wait for the shortcut's input: the name is typed only into the switcher seen open and focused. Ronda final
    /// 27 (regla 3): not seen, on any client, or a window that could not be read: the shortcut once more, then the name
    /// is never typed (typed blind, it went into the person's message box when the switcher was already open and
    /// Ctrl+K closed it), on a client started just now or long ago alike.
    /// </summary>
    internal static SearchStep AfterSearchWait(InputWait input, bool retried) =>
        input == InputWait.Opened
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
    /// answered it says so (Unanswered); either way the window is not said ready (C14).
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
    /// X1 (n1 t1-c09 «mandale a Nube77 por discord…» on the notebook, client open on another view): a client that draws
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
            // Ronda final 28 (regla 3): only a row inside the switcher's dialog is a result (not a message or a channel).
            if (now.Answered && now.Focused is { InDialog: true } focus
                && SearchRowKinds.Contains(focus.Kind, StringComparer.Ordinal))
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
            // Ronda final 11 (regla 3): no row read at all is a search not read, never «not found».
            ErrorCode = unverified.EffectObserved ? unverified.ErrorCode
                : row is null ? "recipient_search_not_read" : RecipientNotFound,
            Shown = row,
            // Ronda final 12 (regla 3): the switcher was opened, the name typed and closed: an effect, whatever was found.
            EffectObserved = true,
        };
}
