using System.IO;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Core.Operations;

namespace Baxy.App;

/// <summary>
/// Settings › General «Buscar actualizaciones» and the discreet notice of a newer BAXY (actualizar-ordenes-app, dueño
/// 2026-11-09). Both are the chat's own baxy.update sent to the same engine, so the kernel authorizes each call and the
/// handler is the only one that reads GitHub or a store (Baxy.Core BaxyUpdateHandler). The panel's «Actualizar» button is
/// the person's yes to that one install, as the memory panel's buttons are to theirs; any other challenge stays
/// unanswered. Nothing updates without it: the notice only says there is a newer version.
/// <para>APP1 (UPD-f, review of the App 2026-11-09): the install is a long operation with a state of its own, as a model's
/// download is (TunedModel, OpenModels). The view gives a request 30 s (field-native-bridge.js) and about 80 MB take longer
/// below some 22 Mbit/s: it said «no pude» and offered the button again while the engine went on, started the installer and
/// BAXY closed. The button's request now starts the install and answers with what it is doing; the view reads that state
/// (GET /update/install) until it ends, with the engine's own failure when it fails; a second press joins the one
/// running.</para>
/// </summary>
internal sealed class UpdatePanel
{
    internal const string Operation = "baxy.update";

    private static readonly TimeSpan CheckTimeout = TimeSpan.FromSeconds(30);

    // The download of the installer (about 80 MB) runs inside the install call. REV_APP UPD-b: the engine ends it within
    // its own limit, and this waits a minute more (its question to GitHub before, 20 s at most twice), so the answer is
    // here before this stops waiting and «no sé si el instalador llegó a abrirse» is left for an engine that hung.
    internal static readonly TimeSpan InstallTimeout = UpdateInstallerFile.Budget + TimeSpan.FromMinutes(1);

    // What the button's request waits for an install that ends at once (a store's page opened, nothing newer, no engine),
    // so the view hears that end in the same answer; far below the 30 s the view gives a request.
    private static readonly TimeSpan PromptEnd = TimeSpan.FromSeconds(2);

    private readonly Func<string, TimeSpan, bool, CancellationToken, Task<OperationResponse?>> _send;
    private readonly Func<string>? _dataRoot;
    private readonly TimeSpan _promptEnd;
    private readonly Action<string, Exception> _record;
    private readonly object _gate = new();
    private JsonObject? _known;
    private Task? _installing;
    private JsonObject? _installed;

    /// <param name="send">Sends baxy.update with this action and answers its challenge when the bool says the person
    /// pressed the button; null when no engine is there.</param>
    /// <param name="dataRoot">The profile's data, where the engine downloads the installer (UpdateInstallerFile), asked
    /// only while an install runs; null when how much of it is here cannot be read.</param>
    /// <param name="promptEnd">How long the button's request waits for an install that ends at once.</param>
    /// <param name="record">Keeps a failure nothing expected (UnhandledFailures).</param>
    internal UpdatePanel(
        Func<string, TimeSpan, bool, CancellationToken, Task<OperationResponse?>> send,
        Func<string>? dataRoot = null,
        TimeSpan? promptEnd = null,
        Action<string, Exception>? record = null)
    {
        _send = send;
        _dataRoot = dataRoot;
        _promptEnd = promptEnd ?? PromptEnd;
        _record = record ?? (static (source, failure) => UnhandledFailures.Record(source, failure));
    }

    /// <summary>An install ended (it started the installer, opened the store, or failed), as the view is told it.</summary>
    internal event Action<JsonObject>? InstallEnded;

    internal static UpdatePanel ForEngine(Func<CoreProcessClient?> client) => new(async (action, timeout, pressed, cancellation) =>
    {
        if (client() is not { IsReady: true } core)
        {
            return null;
        }

        PreparedOperation prepared = PreparedOperation.Create(Operation, new JsonObject { ["action"] = action });
        OperationResponse response = await core.SendOperationAsync(prepared, timeout, cancellation).ConfigureAwait(false);
        if (pressed && PendingOperationConfirmation.TryCreate(response, prepared, TimeProvider.System, out PendingOperationConfirmation? asked)
            && asked is not null)
        {
            response = await core.SendOperationAsync(prepared, timeout, cancellation, asked.Token).ConfigureAwait(false);
        }

        return response;
    }, MemoryOperationProtector.ResolveDataRoot);

    /// <summary>VIS3 (VIVO6 fila 4: Settings › Versión said no number until «Buscar actualizaciones» asked GitHub): the
    /// version this App is, from its own stamp (scripts/build_product.ps1 -p:InformationalVersion), with no request.</summary>
    internal static string? Installed { get; } =
        Version(typeof(UpdatePanel).Assembly.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion);

    /// <summary>The stamp's version without the build's commit after «+» (SemVer 2.0.0 §10: build metadata); null when
    /// there is none.</summary>
    internal static string? Version(string? stamp) =>
        stamp?.Split('+', 2)[0].Trim() is { Length: > 0 } version ? version : null;

    /// <summary>What the last check found, as the view shows it; null before one ran.</summary>
    internal JsonObject? Known
    {
        get
        {
            lock (_gate)
            {
                return (JsonObject?)_known?.DeepClone();
            }
        }
    }

    /// <summary>GET /update: a check now.</summary>
    internal async Task<JsonObject> CheckAsync(CancellationToken cancellationToken)
    {
        JsonObject view = await RunAsync("check", CheckTimeout, cancellationToken).ConfigureAwait(false);
        if (view["ok"] is JsonValue ok && ok.TryGetValue(out bool checkedOk) && checkedOk)
        {
            lock (_gate)
            {
                _known = (JsonObject)view.DeepClone();
            }
        }

        return view;
    }

    /// <summary>The install running now, or the last one; null before any.</summary>
    internal Task? Installing
    {
        get
        {
            lock (_gate)
            {
                return _installing;
            }
        }
    }

    /// <summary>
    /// POST /update/install: the button pressed. Starts the install unless one is running, and answers with its state
    /// (<see cref="InstallState"/>) without waiting for the download: what ended at once comes as its end.
    /// </summary>
    internal async Task<JsonObject> InstallAsync(CancellationToken cancellationToken)
    {
        Task running;
        lock (_gate)
        {
            if (_installing is null or { IsCompleted: true })
            {
                _installed = null;
                _installing = RunInstallAsync(cancellationToken);
            }

            running = _installing;
        }

        using var waited = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        await Task.WhenAny(running, Task.Delay(_promptEnd, waited.Token)).ConfigureAwait(false);
        await waited.CancelAsync().ConfigureAwait(false);
        return InstallState();
    }

    /// <summary>
    /// GET /update/install: what the install is doing, or how the last one ended. While it runs, «installing» with its phase
    /// («downloading», or «checking» once every published byte is here) and the bytes of the installer on disk, read from
    /// the file the engine writes (null when not read: never a 0 nobody saw); nothing is said done or failed. Once it
    /// ended, that end as the engine told it. Before any install, only «installing: false».
    /// </summary>
    internal JsonObject InstallState()
    {
        lock (_gate)
        {
            if (_installing is not { IsCompleted: false })
            {
                JsonObject ended = (JsonObject?)_installed?.DeepClone() ?? [];
                ended["installing"] = false;
                return ended;
            }

            string? latest = (string?)_known?["latest"];
            long? total = _known?["downloadBytes"] is JsonValue size && size.TryGetValue(out long bytes) && bytes > 0 ? bytes : null;
            long? here = null;
            bool whole = false;
            if (latest is not null && DataRoot() is { } dataRoot)
            {
                string target = UpdateInstallerFile.Target(dataRoot, latest);
                here = Length(UpdateInstallerFile.Partial(target));
                // No «.part» and the installer under its name: every byte came, and the engine checks it or starts it.
                whole = here is null ? Length(target) is not null : total is { } all && here >= all;
            }

            return new JsonObject
            {
                ["installing"] = true,
                ["phase"] = whole ? "checking" : "downloading",
                ["latest"] = latest,
                ["downloadBytes"] = total,
                ["downloadedBytes"] = whole ? total : here,
            };
        }
    }

    /// <summary>
    /// What «Salidas a internet» says of a check or an install that reached GitHub, or null when nothing went out (a store
    /// opens its own page, a development copy and a channel with no repository ask no one). A failure GitHub answered (its
    /// rate limit, a 5xx) went out too: the channel says it, not the answer (INT19 blind review). A call the App stopped
    /// waiting for comes with no receipt: the channel is the last check's, which the «Actualizar» button follows.
    /// </summary>
    internal string? WentOnline(string action, JsonObject view)
    {
        string? channel = (string?)view["channel"]
            ?? ((string?)view["error"] == "update_outcome_unknown" ? (string?)Known?["channel"] : null);
        if (channel is null || AskedNoOne(channel, (string?)view["error"]))
        {
            return null;
        }

        // «If needed»: an installer already downloaded with the published SHA-256 is not downloaded again.
        return action == "install"
            ? UiLanguage.Say("búsqueda de la versión nueva de BAXY en GitHub (api.github.com) y, si hace falta, descarga de su instalador (github.com)",
                "check for the newer BAXY on GitHub (api.github.com) and, if needed, download of its installer (github.com)")
            : UiLanguage.Say("búsqueda de una versión nueva de BAXY en GitHub (api.github.com)",
                "check for a newer BAXY on GitHub (api.github.com)");
    }

    /// <summary>
    /// Whether a baxy.update said in the chat stayed in this PC, by its own receipt (VER1, G-14: the chat noted every one
    /// in «Salidas a internet», as the catalog's effect says the operation may). The receipt's typed «channel» is where it
    /// went, as <see cref="WentOnline"/> reads it for the Settings button. One that does not say (no receipt, another
    /// failure) is not one that stayed in.
    /// </summary>
    internal static bool StayedIn(NativeTurnStep step)
    {
        JsonObject? observed;
        try
        {
            observed = (JsonNode.Parse(step.Observation) as JsonObject)?["observed"] as JsonObject;
        }
        catch (JsonException)
        {
            return false;
        }

        return observed?["channel"] is JsonValue said && said.TryGetValue(out string? channel)
            && AskedNoOne(channel, step.ErrorCode);
    }

    // GitHub is the one channel BAXY itself asks, and only when the copy says which repository is its own.
    private static bool AskedNoOne(string channel, string? error) =>
        channel != "github" || error == "baxy_update_source_unknown";

    /// <summary>The update event the view shows as a discreet notice, or null when there is nothing newer.</summary>
    internal static JsonObject? NoticeOf(JsonObject? known) =>
        known?["newer"] is JsonValue newer && newer.TryGetValue(out bool isNewer) && isNewer
            ? new JsonObject { ["type"] = "update", ["latest"] = known["latest"]?.DeepClone(), ["installed"] = known["installed"]?.DeepClone() }
            : null;

    private async Task RunInstallAsync(CancellationToken cancellationToken)
    {
        // Off the caller's thread and out of its lock, as a model's download starts (TunedModel.DownloadAsync).
        await Task.Yield();
        JsonObject ended;
        try
        {
            ended = await RunAsync("install", InstallTimeout, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception failure) when (failure is not OperationCanceledException)
        {
            // Nothing expected it: it is kept, and the view is told the end is not known instead of nothing at all.
            _record("update", failure);
            ended = new JsonObject { ["ok"] = false, ["error"] = "update_outcome_unknown" };
        }

        lock (_gate)
        {
            _installed = ended;
        }

        InstallEnded?.Invoke((JsonObject)ended.DeepClone());
    }

    private string? DataRoot()
    {
        try
        {
            return _dataRoot?.Invoke();
        }
        catch (Exception unread) when (unread is IOException or UnauthorizedAccessException or InvalidOperationException
            or ArgumentException)
        {
            return null;
        }
    }

    // A file's bytes as Windows has them now, though another process writes it; null when it is not there or not read.
    private static long? Length(string path)
    {
        try
        {
            FileInfo file = new(path);
            return file.Exists ? file.Length : null;
        }
        catch (Exception unread) when (unread is IOException or UnauthorizedAccessException)
        {
            return null;
        }
    }

    private async Task<JsonObject> RunAsync(string action, TimeSpan timeout, CancellationToken cancellationToken)
    {
        OperationResponse? response;
        try
        {
            response = await _send(action, timeout, action == "install", cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is TimeoutException or IOException or InvalidOperationException
            || exception is OperationCanceledException && !cancellationToken.IsCancellationRequested)
        {
            return new JsonObject { ["ok"] = false, ["error"] = "update_outcome_unknown" };
        }

        if (response is null)
        {
            return new JsonObject { ["ok"] = false, ["error"] = "engine_not_ready" };
        }

        // The receipt's facts (channel, versions) come with a failure too: «ya tienes la última» is told with its numbers.
        JsonObject view = response.Result is { ValueKind: JsonValueKind.Object } result
            ? JsonNode.Parse(result.GetRawText()) as JsonObject ?? []
            : [];
        bool done = string.Equals(response.Status, OperationStatuses.Completed, StringComparison.Ordinal) && response.Verified;
        view["ok"] = done;
        if (!done)
        {
            view["error"] = response.ErrorCode ?? response.Status;
        }

        return view;
    }
}
