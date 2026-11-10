using System.Globalization;
using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>A step as the overlay shows it: its title, its status (run, ok, same, sent, read, fail, skip, maybe) and what
/// was observed, or why it failed.</summary>
internal sealed record OverlayStep(string Label, string Status, string? Note);

/// <summary>What the overlay shows now. <c>Kind</c> is working, ask, talk, or how the turn ended (ok, same, read, sent,
/// maybe, part, fail, skip); <c>Card</c> is the card waiting for the person.</summary>
internal sealed record OverlaySnapshot(
    string Kind,
    string Title,
    string? Say,
    IReadOnlyList<OverlayStep> Steps,
    string? Request,
    string Elapsed,
    double Progress,
    string? Card);

/// <summary>
/// The overlay's own reading of the turn (owner, 2026-11-08: «while BAXY is behind, a list of what it is doing»). It is
/// fed the very events the view gets (FieldProductChannel: item, step) and says nothing they did not say. How a turn
/// ended is read from the steps' typed statuses as the view's card does (src/Baxy.FieldUi/src/outcome.ts): never more
/// than was checked. The App says when a turn is over (the state event's <c>busy</c> going down): APP1 (REV_APP OVL-2,
/// 2026-11-09) a turn cancelled, failed or that ended in a notice has no reply of BAXY's with text, and the clock ran with
/// «Trabajando» until the next request.
/// </summary>
internal sealed class OverlayModel
{
    private const int Shown = 4;
    private const int FailureSeconds = 20;

    private static readonly string[] StatusWords = ["leído", "read", "comprobado", "checked", "verificado", "verified"];

    private readonly List<(string Id, OverlayStep Step)> _steps = [];
    private string? _request;
    private string? _requestId;
    private string? _notTaken;
    private string? _reply;
    private string? _notice;
    private bool _busy;
    private DateTimeOffset? _startedAt;
    private DateTimeOffset? _endedAt;
    private (string Id, string Said, string? Risk, string? Context, bool EffectStarted, DateTimeOffset Expires)? _card;

    internal void Apply(JsonObject eventData, DateTimeOffset now)
    {
        ArgumentNullException.ThrowIfNull(eventData);
        switch ((string?)eventData["type"])
        {
            case "item" when eventData["item"] is JsonObject item:
                ApplyItem(item, now);
                break;
            case "step":
                ApplyStep(eventData);
                break;
            // APP1 (REV_APP OVL-3): the conversation on screen changed (FieldProductChannel.StartSession: another opened,
            // a new one, the current one deleted); a request that is not in it is no longer told.
            case "transcript" when eventData["items"] is JsonArray items && _requestId is not null
                && !items.OfType<JsonObject>().Any(item => (string?)item["id"] == _requestId):
                _steps.Clear();
                _request = _requestId = _reply = _notice = null;
                _startedAt = _endedAt = null;
                break;
            case "state" when eventData["busy"] is JsonValue value && value.TryGetValue(out bool busy):
                // MainWindowViewModel.IsBusy spans the whole turn, the wait for a yes too: its fall is the turn's end.
                if (_busy && !busy && _startedAt is not null)
                {
                    _endedAt ??= now;
                }

                _busy = busy;
                break;
        }
    }

    /// <summary>APP1 (REV_APP OVL-4): the App did not take the answer given to this card from the overlay (it was not the
    /// one pending any more, or the turn could not take it): its card says so until another card comes.</summary>
    internal void AnswerNotTaken(string card)
    {
        if (_card is { } pending && pending.Id == card)
        {
            _notTaken = card;
        }
    }

    /// <summary>Null when there is nothing to show: no request yet, or the end was shown long enough.</summary>
    /// <param name="hideSeconds">How long the end stays; 0 keeps it until the next request.</param>
    internal OverlaySnapshot? Snapshot(DateTimeOffset now, int hideSeconds, bool english)
    {
        if (_startedAt is not { } started)
        {
            return null;
        }

        string elapsed = Clock((_endedAt ?? now) - started);
        OverlayStep[] steps = [.. _steps.Select(static entry => entry.Step).TakeLast(Shown)];
        if (_card is { } card && card.Expires > now)
        {
            // INT16 (blind review): before the yes, what the view's card says first (FieldStepProjection.Card, Chat.tsx
            // Card): its risk or why it was held, that an earlier attempt may have run, and its context.
            string[] first = [.. new[] { card.Risk, card.EffectStarted ? UiLanguage.Say(english, "un intento anterior pudo haber corrido", "an earlier attempt may have run") : null, card.Context }
                .Where(static part => !string.IsNullOrWhiteSpace(part)).Select(static part => part!)];
            string said = first.Length > 0 ? string.Join(" · ", first) + "\n" + card.Said : card.Said;
            if (_notTaken == card.Id)
            {
                said += "\n" + UiLanguage.Say(english, "BAXY no tomó tu respuesta desde aquí: contesta en su ventana.",
                    "BAXY didn’t take your answer from here: answer in its window.");
            }

            return new OverlaySnapshot("ask", UiLanguage.Say(english, "Esperando tu sí", "Waiting for your OK"), said, steps, _request,
                Clock(card.Expires - now), Progress(), card.Id);
        }

        if (_endedAt is not { } ended)
        {
            string working = UiLanguage.Say(english, "Trabajando", "Working");
            return new OverlaySnapshot("working", _steps.Count > 0 ? working + UiLanguage.Say(english, " · paso ", " · step ") + _steps.Count : working,
                null, steps, _request, elapsed, Progress(), null);
        }

        // a step that started and never said how it ended, in a turn that is over: it may have happened
        steps = [.. steps.Select(static step => step.Status == "run" ? step with { Status = "maybe" } : step)];
        (string kind, string title) = _reply is null && _steps.Count == 0
            ? ("skip", UiLanguage.Say(english, "– Terminó sin respuesta", "– Ended with no reply"))
            : Outcome([.. _steps.Select(static entry => entry.Step.Status is "run" ? "maybe" : entry.Step.Status)], english);
        // «Si algo falla, se queda 20 s» (Personalización): a turn partly done with a step that failed stays as long too.
        int stays = _steps.Any(static entry => entry.Step.Status == "fail") ? Math.Max(hideSeconds, FailureSeconds) : hideSeconds;
        if (hideSeconds > 0 && now - ended > TimeSpan.FromSeconds(stays))
        {
            return null;
        }

        return new OverlaySnapshot(kind, title, _reply ?? _notice, steps, _request, elapsed, 1, null);
    }

    private void ApplyItem(JsonObject item, DateTimeOffset now)
    {
        switch ((string?)item["who"])
        {
            case "you":
                _steps.Clear();
                _request = (string?)item["text"];
                _requestId = (string?)item["id"];
                _reply = null;
                _notice = null;
                _card = null;
                _startedAt = now;
                _endedAt = null;
                break;
            case "baxy":
                if (item["steps"] is JsonArray list)
                {
                    _steps.Clear();
                    foreach (JsonObject step in list.OfType<JsonObject>())
                    {
                        _steps.Add(((string?)step["id"] ?? string.Empty, ToStep(step)));
                    }
                }

                _startedAt ??= now;
                if ((string?)item["text"] is { Length: > 0 } text)
                {
                    _reply = text;
                    if (_steps.All(static entry => entry.Step.Status != "run"))
                    {
                        _endedAt ??= now;
                    }
                }

                break;
            case "sys" when _startedAt is not null && _endedAt is null:
                // what the turn said instead of a reply (a failure, a notice): shown if it ends without one
                _notice = (string?)item["text"];
                break;
            case "card":
                string? id = (string?)item["id"];
                if ((string?)item["status"] == "pending" && id is not null && item["expires"] is JsonValue expires
                    && expires.TryGetValue(out long at))
                {
                    string said = (string?)item["title"] ?? string.Empty;
                    if ((string?)item["target"] is { Length: > 0 } target)
                    {
                        said += " · " + target;
                    }

                    _card = (id, said, (string?)item["risk"], (string?)item["context"],
                        item["effectStarted"] is JsonValue started && started.TryGetValue(out bool again) && again,
                        DateTimeOffset.FromUnixTimeMilliseconds(at));
                    _startedAt ??= now;
                }
                else if (_card is { } pending && pending.Id == id)
                {
                    _card = null;
                }

                break;
        }
    }

    private void ApplyStep(JsonObject step)
    {
        string id = (string?)step["id"] ?? string.Empty;
        OverlayStep shown = (string?)step["phase"] == "start"
            ? new OverlayStep((string?)step["label"] ?? string.Empty, "run", null)
            : ToStep(step);
        int at = _steps.FindIndex(entry => entry.Id == id);
        if (at >= 0)
        {
            _steps[at] = (id, shown);
        }
        else
        {
            _steps.Add((id, shown));
        }
    }

    private static OverlayStep ToStep(JsonObject step)
    {
        string status = (string?)step["status"] ?? "run";
        string? note = status is "fail" or "skip" or "maybe" ? (string?)step["reason"] : (string?)step["obs"];
        // an observation that only repeats the status («Leído») is left out, as the view's card does
        bool repeats = note is not null && StatusWords.Contains(note.Trim(), StringComparer.OrdinalIgnoreCase);
        return new OverlayStep((string?)step["label"] ?? string.Empty, status, string.IsNullOrWhiteSpace(note) || repeats ? null : note);
    }

    private double Progress() =>
        _steps.Count == 0 ? 0.08 : (double)_steps.Count(static entry => entry.Step.Status != "run") / (_steps.Count + 1);

    private static string Clock(TimeSpan span)
    {
        int seconds = Math.Max(0, (int)Math.Ceiling(span.TotalSeconds - 0.0001));
        return (seconds / 60).ToString(CultureInfo.InvariantCulture) + ":" + (seconds % 60).ToString("00", CultureInfo.InvariantCulture);
    }

    // The same table as the view's card (outcome.ts); a reply without steps is talk.
    private static (string Kind, string Title) Outcome(IReadOnlyList<string> statuses, bool english)
    {
        bool Has(params string[] any) => statuses.Any(any.Contains);
        bool All(params string[] any) => statuses.All(any.Contains);
        string kind = statuses.Count == 0 ? "talk"
            : Has("fail") ? (Has("ok", "same", "read", "sent", "maybe") ? "part" : "fail")
            : Has("maybe") ? "maybe"
            : Has("sent") ? "sent"
            : All("skip") ? "skip"
            : All("same") ? "same"
            : Has("ok", "same") ? (Has("skip") ? "part" : "ok")
            : Has("read") ? (Has("skip") ? "part" : "read")
            : "skip";
        string title = kind switch
        {
            "talk" => UiLanguage.Say(english, "Respondió", "Replied"),
            "ok" => UiLanguage.Say(english, "✓ Hecho y comprobado", "✓ Done and checked"),
            "same" => UiLanguage.Say(english, "= Ya estaba así", "= Already like that"),
            "read" => UiLanguage.Say(english, "✓ Leído", "✓ Read"),
            "sent" => UiLanguage.Say(english, "↗ Hecho, sin poder comprobarlo", "↗ Done, couldn’t check it"),
            "maybe" => UiLanguage.Say(english, "? Puede que se haya hecho", "? It may have happened"),
            "part" => UiLanguage.Say(english, "◐ Hecho en parte", "◐ Partly done"),
            "fail" => UiLanguage.Say(english, "✕ No pude", "✕ Couldn’t do it"),
            _ => UiLanguage.Say(english, "– No se hizo", "– Not done"),
        };
        return (kind, title);
    }
}
