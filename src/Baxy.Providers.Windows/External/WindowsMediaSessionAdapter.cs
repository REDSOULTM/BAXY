using System.Globalization;
using System.Text;
using System.Text.Json;
using Windows.Media.Control;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsMediaSessionAdapter : IExternalOperationAdapter, IDisposable
{
    private const int SpotifyPlaybackPollIntervals = 20;
    private const int SmtcPostreadPollIntervals = 7;
    private const int SmtcControlPostreadPollIntervals = 40;
    private static readonly TimeSpan SpotifyPlaybackPollInterval =
        TimeSpan.FromMilliseconds(500);
    private static readonly TimeSpan SmtcPostreadPollInterval =
        TimeSpan.FromMilliseconds(50);
    private readonly HttpClient _spotifyHttp;
    private readonly Func<string?> _token;
    private readonly Func<TimeSpan, CancellationToken, ValueTask> _delay;
    private readonly bool _ownsHttp;

    internal WindowsMediaSessionAdapter()
        : this(new HttpClient { Timeout = TimeSpan.FromSeconds(20) },
            () => Environment.GetEnvironmentVariable("BAXY_SPOTIFY_ACCESS_TOKEN"),
            ownsHttp: true)
    {
    }

    internal WindowsMediaSessionAdapter(
        HttpClient spotifyHttp,
        Func<string?> token,
        bool ownsHttp = false,
        Func<TimeSpan, CancellationToken, ValueTask>? delay = null)
    {
        _spotifyHttp = spotifyHttp ?? throw new ArgumentNullException(nameof(spotifyHttp));
        _token = token ?? throw new ArgumentNullException(nameof(token));
        _delay = delay ?? DefaultDelayAsync;
        _ownsHttp = ownsHttp;
    }

    public bool CanHandle(string operation) =>
        operation is "media.control" or "media.seek.relative" or "media.play.exact"
            or "media.play.query" or "media.status";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (operation is "media.play.exact" or "media.play.query"
            && !string.IsNullOrWhiteSpace(_token()))
        {
            return await PlayWithSpotifyApiAsync(operation, arguments, cancellationToken)
                .ConfigureAwait(false);
        }
        if (operation == "media.play.query")
            return ExternalJson.Failure(operation, "spotify_api_authentication_required");
        GlobalSystemMediaTransportControlsSession? session;
        try
        {
            GlobalSystemMediaTransportControlsSessionManager manager =
                await GlobalSystemMediaTransportControlsSessionManager.RequestAsync();
            if (operation is "media.status" or "media.control" or "media.seek.relative")
            {
                session = manager.GetCurrentSession();
                IReadOnlyList<GlobalSystemMediaTransportControlsSession> sessions =
                    manager.GetSessions();
                if (session is null)
                {
                    foreach (GlobalSystemMediaTransportControlsSession candidate in sessions)
                    {
                        if (candidate.GetPlaybackInfo().PlaybackStatus
                            == GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing)
                        {
                            session = candidate;
                            break;
                        }
                    }
                }
                session ??= sessions.Count > 0 ? sessions[0] : null;
                if (arguments.TryGetProperty("sourceApp", out JsonElement sourceAppValue)
                    && sourceAppValue.ValueKind == JsonValueKind.String
                    && !string.IsNullOrWhiteSpace(sourceAppValue.GetString()))
                {
                    string requestedSource = sourceAppValue.GetString()!;
                    session = sessions.FirstOrDefault(candidate =>
                        candidate.SourceAppUserModelId.Contains(
                            requestedSource, StringComparison.OrdinalIgnoreCase));
                }
                // Owner's test 2026-09-21 (turn 148, «para la canción» right after a
                // YouTube playback): Edge kept a session whose status was Closed, so
                // «stop» was verified against nothing and the final said nothing was
                // playing. A closed session is not a player: it stands aside so the
                // tab that actually plays answers.
                if (session is not null
                    && session.GetPlaybackInfo().PlaybackStatus
                        == GlobalSystemMediaTransportControlsSessionPlaybackStatus.Closed)
                {
                    string closedSource = session.SourceAppUserModelId;
                    session = sessions.FirstOrDefault(candidate =>
                        candidate.GetPlaybackInfo().PlaybackStatus
                            != GlobalSystemMediaTransportControlsSessionPlaybackStatus.Closed
                        && candidate.SourceAppUserModelId.Contains(
                            closedSource, StringComparison.OrdinalIgnoreCase));
                }
            }
            else
            {
                session = manager.GetSessions().SingleOrDefault(item =>
                    item.SourceAppUserModelId.Contains("spotify", StringComparison.OrdinalIgnoreCase));
            }
        }
        catch
        {
            return ExternalJson.Failure(operation, "smtc_session_access_failed");
        }

        if (session is null)
        {
            return ExternalJson.Failure(
                operation,
                operation is "media.status" or "media.control" or "media.seek.relative"
                    ? "media_session_not_found"
                    : "spotify_smtc_session_not_found");
        }

        return operation switch
        {
            "media.play.exact" => await PlayExactCurrentAsync(
                operation, arguments, session, cancellationToken).ConfigureAwait(false),
            "media.status" => await StatusAsync(
                operation, session, cancellationToken).ConfigureAwait(false),
            "media.seek.relative" => await SeekRelativeAsync(
                operation, arguments, session, cancellationToken).ConfigureAwait(false),
            _ => await ControlAsync(
                operation, arguments, session, cancellationToken).ConfigureAwait(false),
        };
    }

    public void Dispose()
    {
        if (_ownsHttp)
        {
            _spotifyHttp.Dispose();
        }
    }

    private async ValueTask<ExternalCapabilityReceipt> PlayWithSpotifyApiAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        bool effectBoundaryCrossed = false;
        try
        {
            bool exactSelection = operation == "media.play.exact";
            string requested = ExternalJson.RequiredString(
                arguments, exactSelection ? "title" : "query");
            string? token = _token();
            if (string.IsNullOrWhiteSpace(token))
            {
                return ExternalJson.Failure(operation, "spotify_api_authentication_required");
            }
            using JsonDocument search = await SpotifyJsonAsync(
                HttpMethod.Get,
                "https://api.spotify.com/v1/search?q="
                    + Uri.EscapeDataString(exactSelection ? "track:" + requested : requested)
                    + "&type=track&limit=20",
                token,
                null,
                cancellationToken).ConfigureAwait(false);
            if (!search.RootElement.TryGetProperty("tracks", out JsonElement tracks)
                || !tracks.TryGetProperty("items", out JsonElement items)
                || items.ValueKind != JsonValueKind.Array)
            {
                return ExternalJson.Failure(operation, "spotify_search_response_invalid");
            }
            JsonElement[] matches = items.EnumerateArray()
                .Where(item => item.TryGetProperty("name", out JsonElement name)
                    && (!exactSelection || string.Equals(
                        Fold(name.GetString() ?? string.Empty), Fold(requested), StringComparison.Ordinal))
                    && item.TryGetProperty("id", out JsonElement id)
                    && id.ValueKind == JsonValueKind.String)
                .OrderByDescending(item => item.TryGetProperty("popularity", out JsonElement popularity)
                    && popularity.TryGetInt32(out int score) ? score : 0)
                .Take(20)
                .Select(item => item.Clone())
                .ToArray();
            if (matches.Length == 0)
            {
                return ExternalJson.Failure(operation,
                    exactSelection ? "spotify_exact_track_not_found" : "spotify_query_track_not_found");
            }
            JsonElement selected = matches[0];
            string trackId = selected.GetProperty("id").GetString()!;
            string uri = selected.GetProperty("uri").GetString()!;
            string selectedTitle = selected.GetProperty("name").GetString()!;
            string artist = selected.TryGetProperty("artists", out JsonElement artists)
                && artists.ValueKind == JsonValueKind.Array
                && artists.GetArrayLength() > 0
                && artists[0].TryGetProperty("name", out JsonElement artistName)
                    ? artistName.GetString() ?? string.Empty
                    : string.Empty;

            using JsonDocument devices = await SpotifyJsonAsync(
                HttpMethod.Get,
                "https://api.spotify.com/v1/me/player/devices",
                token,
                null,
                cancellationToken).ConfigureAwait(false);
            JsonElement[] available = devices.RootElement.TryGetProperty("devices", out JsonElement deviceArray)
                && deviceArray.ValueKind == JsonValueKind.Array
                    ? deviceArray.EnumerateArray()
                        .Where(item => item.TryGetProperty("is_restricted", out JsonElement restricted)
                            && restricted.ValueKind == JsonValueKind.False
                            && item.TryGetProperty("id", out JsonElement id)
                            && id.ValueKind == JsonValueKind.String)
                        .Select(item => item.Clone())
                        .ToArray()
                    : [];
            JsonElement? device = available.FirstOrDefault(item => item.TryGetProperty("is_active", out JsonElement active)
                && active.ValueKind == JsonValueKind.True);
            device ??= available.FirstOrDefault();
            if (device is null || device.Value.ValueKind == JsonValueKind.Undefined)
            {
                return ExternalJson.Failure(operation, "spotify_playback_device_not_available");
            }
            string deviceId = device.Value.GetProperty("id").GetString()!;
            JsonElement playBody = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteStartArray("uris");
                writer.WriteStringValue(uri); writer.WriteEndArray(); writer.WriteEndObject();
            });
            effectBoundaryCrossed = true;
            using JsonDocument _ = await SpotifyJsonAsync(
                HttpMethod.Put,
                "https://api.spotify.com/v1/me/player/play?device_id=" + Uri.EscapeDataString(deviceId),
                token,
                playBody.GetRawText(),
                cancellationToken,
                allowEmpty: true).ConfigureAwait(false);
            for (int attempt = 0; attempt <= SpotifyPlaybackPollIntervals; attempt++)
            {
                if (attempt > 0)
                {
                    await _delay(SpotifyPlaybackPollInterval, cancellationToken)
                        .ConfigureAwait(false);
                }

                try
                {
                    using JsonDocument nowPlaying = await SpotifyJsonAsync(
                        HttpMethod.Get,
                        "https://api.spotify.com/v1/me/player/currently-playing",
                        token,
                        null,
                        cancellationToken,
                        allowEmpty: true).ConfigureAwait(false);
                    if (nowPlaying.RootElement.ValueKind == JsonValueKind.Object
                        && nowPlaying.RootElement.TryGetProperty(
                            "is_playing",
                            out JsonElement playing)
                        && playing.ValueKind == JsonValueKind.True
                        && nowPlaying.RootElement.TryGetProperty("item", out JsonElement item)
                        && item.ValueKind == JsonValueKind.Object
                        && item.TryGetProperty("id", out JsonElement observedId)
                        && string.Equals(
                            observedId.GetString(),
                            trackId,
                            StringComparison.Ordinal))
                    {
                        JsonElement result = ExternalJson.Create(writer =>
                        {
                            writer.WriteStartObject(); writer.WriteNumber("version", 1);
                            writer.WriteString("provider", "spotify");
                            writer.WriteString("trackId", trackId);
                            writer.WriteString("title", selectedTitle);
                            if (!exactSelection) writer.WriteString("query", requested);
                            writer.WriteString("artist", artist);
                            writer.WriteString("playbackStatus", "playing");
                            writer.WriteString("deviceId", deviceId);
                            writer.WriteString("authority", "spotify_web_api_postread");
                            writer.WriteEndObject();
                        });
                        return ExternalJson.Success(operation, result, effectObserved: true);
                    }
                }
                catch (Exception exception) when (
                    attempt == 0
                    && !cancellationToken.IsCancellationRequested
                    && exception is HttpRequestException or JsonException)
                {
                    // The immediate read is additive. A transient failure here
                    // must not pre-empt the first observation in the original
                    // 500 ms schedule.
                }
            }
            return ExternalJson.Failure(operation, "spotify_now_playing_not_verified", true);
        }
        catch (HttpRequestException)
        {
            return ExternalJson.Failure(operation, "spotify_api_request_failed", effectBoundaryCrossed);
        }
        catch (JsonException)
        {
            return ExternalJson.Failure(operation, "spotify_api_response_invalid", effectBoundaryCrossed);
        }
    }

    private async ValueTask<JsonDocument> SpotifyJsonAsync(
        HttpMethod method,
        string url,
        string token,
        string? body,
        CancellationToken cancellationToken,
        bool allowEmpty = false)
    {
        using var request = new HttpRequestMessage(method, url);
        request.Headers.Authorization = new("Bearer", token);
        if (body is not null)
        {
            request.Content = new StringContent(body, Encoding.UTF8, "application/json");
        }
        using HttpResponseMessage response = await _spotifyHttp.SendAsync(request, cancellationToken)
            .ConfigureAwait(false);
        if (!response.IsSuccessStatusCode)
        {
            throw new HttpRequestException("Spotify API rejected the operation.", null, response.StatusCode);
        }
        byte[] payload = await response.Content.ReadAsByteArrayAsync(cancellationToken).ConfigureAwait(false);
        return payload.Length == 0 && allowEmpty
            ? JsonDocument.Parse("{}")
            : JsonDocument.Parse(payload);
    }

    private async ValueTask<ExternalCapabilityReceipt> PlayExactCurrentAsync(
        string operation,
        JsonElement arguments,
        GlobalSystemMediaTransportControlsSession session,
        CancellationToken cancellationToken)
    {
        bool effectBoundaryCrossed = false;
        try
        {
            string requested = ExternalJson.RequiredString(arguments, "title");
            GlobalSystemMediaTransportControlsSessionMediaProperties properties =
                await session.TryGetMediaPropertiesAsync();
            if (!string.Equals(Fold(properties.Title), Fold(requested), StringComparison.Ordinal))
            {
                return ExternalJson.Failure(operation, "spotify_exact_selection_requires_verified_uia");
            }

            bool dispatched = false;
            GlobalSystemMediaTransportControlsSessionPlaybackStatus beforeStatus =
                session.GetPlaybackInfo().PlaybackStatus;
            if (beforeStatus
                != GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing)
            {
                effectBoundaryCrossed = true;
                dispatched = await session.TryPlayAsync();
                if (!dispatched)
                {
                    return ExternalJson.Failure(operation, "spotify_play_dispatch_rejected");
                }
            }

            GlobalSystemMediaTransportControlsSessionMediaProperties after = properties;
            GlobalSystemMediaTransportControlsSessionPlaybackStatus status =
                beforeStatus;
            bool verified = false;
            Exception? observationError = null;
            for (int attempt = 0; attempt <= SmtcPostreadPollIntervals; attempt++)
            {
                try
                {
                    after = await session.TryGetMediaPropertiesAsync();
                    status = session.GetPlaybackInfo().PlaybackStatus;
                    verified = string.Equals(
                            Fold(after.Title),
                            Fold(requested),
                            StringComparison.Ordinal)
                        && status
                            == GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing;
                    observationError = null;
                }
                catch (Exception exception) when (!cancellationToken.IsCancellationRequested)
                {
                    observationError = exception;
                    verified = false;
                }

                if (verified || !dispatched || attempt == SmtcPostreadPollIntervals)
                {
                    if (!verified && observationError is not null)
                    {
                        throw observationError;
                    }

                    break;
                }

                await _delay(SmtcPostreadPollInterval, cancellationToken)
                    .ConfigureAwait(false);
            }

            return verified
                ? ExternalJson.Success(operation,
                    MediaResult(after, "playing", session.SourceAppUserModelId, provider: "spotify"), dispatched)
                : ExternalJson.Failure(operation, "spotify_now_playing_not_verified", dispatched);
        }
        catch when (!cancellationToken.IsCancellationRequested)
        {
            return ExternalJson.Failure(
                operation,
                "spotify_now_playing_observation_failed",
                effectBoundaryCrossed);
        }
    }

    private async ValueTask<ExternalCapabilityReceipt> ControlAsync(
        string operation,
        JsonElement arguments,
        GlobalSystemMediaTransportControlsSession session,
        CancellationToken cancellationToken)
    {
        bool effectBoundaryCrossed = false;
        try
        {
            string action = ExternalJson.RequiredString(arguments, "action");
            GlobalSystemMediaTransportControlsSessionMediaProperties before =
                await session.TryGetMediaPropertiesAsync();
            GlobalSystemMediaTransportControlsSessionPlaybackStatus beforeStatus =
                session.GetPlaybackInfo().PlaybackStatus;
            effectBoundaryCrossed = true;
            bool dispatched = action switch
            {
                "play" => await session.TryPlayAsync(),
                "pause" => await session.TryPauseAsync(),
                "stop" => await session.TryStopAsync(),
                "next" => await session.TrySkipNextAsync(),
                "previous" => await session.TrySkipPreviousAsync(),
                "toggle" => beforeStatus
                    == GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing
                        ? await session.TryPauseAsync()
                        : await session.TryPlayAsync(),
                _ => false,
            };
            if (!dispatched)
            {
                return ExternalJson.Failure(operation, "smtc_control_dispatch_rejected");
            }

            GlobalSystemMediaTransportControlsSessionMediaProperties after = before;
            GlobalSystemMediaTransportControlsSessionPlaybackStatus status =
                beforeStatus;
            bool alreadySatisfiedBeforeDispatch = action switch
            {
                "play" => beforeStatus
                    == GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing,
                "pause" => beforeStatus
                    == GlobalSystemMediaTransportControlsSessionPlaybackStatus.Paused,
                "stop" => beforeStatus
                    is GlobalSystemMediaTransportControlsSessionPlaybackStatus.Stopped
                    or GlobalSystemMediaTransportControlsSessionPlaybackStatus.Closed,
                _ => false,
            };
            bool IsVerified() => action switch
            {
                "play" => status
                    == GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing,
                "pause" => status
                    == GlobalSystemMediaTransportControlsSessionPlaybackStatus.Paused,
                "stop" => status
                    is GlobalSystemMediaTransportControlsSessionPlaybackStatus.Stopped
                    or GlobalSystemMediaTransportControlsSessionPlaybackStatus.Closed,
                "next" or "previous" => !string.Equals(
                    Fold(before.Title + "\n" + before.Artist),
                    Fold(after.Title + "\n" + after.Artist),
                    StringComparison.Ordinal),
                "toggle" => beforeStatus
                    == GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing
                        ? status
                            == GlobalSystemMediaTransportControlsSessionPlaybackStatus.Paused
                        : status
                            == GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing,
                _ => false,
            };
            bool verified = false;
            Exception? observationError = null;
            for (int attempt = 0; attempt <= SmtcControlPostreadPollIntervals; attempt++)
            {
                try
                {
                    after = await session.TryGetMediaPropertiesAsync();
                    status = session.GetPlaybackInfo().PlaybackStatus;
                    verified = IsVerified();
                    observationError = null;
                }
                catch (Exception exception) when (!cancellationToken.IsCancellationRequested)
                {
                    observationError = exception;
                    verified = false;
                }

                bool terminal = attempt == SmtcControlPostreadPollIntervals;
                if ((verified && (!alreadySatisfiedBeforeDispatch || terminal)) || terminal)
                {
                    if (!verified && observationError is not null)
                    {
                        throw observationError;
                    }

                    break;
                }

                verified = false;
                await _delay(SmtcPostreadPollInterval, cancellationToken)
                    .ConfigureAwait(false);
            }

            return verified
                ? ExternalJson.Success(
                    operation,
                    MediaResult(after, status.ToString().ToLowerInvariant(), session.SourceAppUserModelId))
                : ExternalJson.Failure(operation, "smtc_postcondition_not_verified", effectObserved: true);
        }
        catch when (!cancellationToken.IsCancellationRequested)
        {
            return ExternalJson.Failure(
                operation,
                "smtc_control_observation_failed",
                effectBoundaryCrossed);
        }
    }

    private static async ValueTask<ExternalCapabilityReceipt> StatusAsync(
        string operation,
        GlobalSystemMediaTransportControlsSession session,
        CancellationToken cancellationToken)
    {
        try
        {
            cancellationToken.ThrowIfCancellationRequested();
            GlobalSystemMediaTransportControlsSessionMediaProperties properties =
                await session.TryGetMediaPropertiesAsync();
            GlobalSystemMediaTransportControlsSessionPlaybackStatus status =
                session.GetPlaybackInfo().PlaybackStatus;
            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("sourceAppUserModelId", session.SourceAppUserModelId);
                writer.WriteString("title", properties.Title);
                writer.WriteString("artist", properties.Artist);
                writer.WriteString("playbackStatus", status.ToString().ToLowerInvariant());
                writer.WriteString("authority", "windows_smtc_current_session_read");
                writer.WriteEndObject();
            });
            return ExternalJson.Success(operation, result, effectObserved: false);
        }
        catch when (!cancellationToken.IsCancellationRequested)
        {
            return ExternalJson.Failure(operation, "media_status_observation_failed");
        }
    }

    private async ValueTask<ExternalCapabilityReceipt> SeekRelativeAsync(
        string operation,
        JsonElement arguments,
        GlobalSystemMediaTransportControlsSession session,
        CancellationToken cancellationToken)
    {
        bool effectBoundaryCrossed = false;
        try
        {
            if (!arguments.TryGetProperty("seconds", out JsonElement secondsElement)
                || !secondsElement.TryGetInt32(out int seconds)
                || seconds is 0 or < -3_600 or > 3_600)
            {
                return ExternalJson.Failure(operation, "media_seek_delta_invalid");
            }

            GlobalSystemMediaTransportControlsSessionTimelineProperties before =
                session.GetTimelineProperties();
            if (before.EndTime <= before.StartTime)
            {
                return ExternalJson.Failure(operation, "media_timeline_not_available");
            }
            TimeSpan requested = before.Position + TimeSpan.FromSeconds(seconds);
            TimeSpan desired = requested < before.StartTime
                ? before.StartTime
                : requested > before.EndTime
                    ? before.EndTime
                    : requested;
            effectBoundaryCrossed = true;
            if (!await session.TryChangePlaybackPositionAsync(desired.Ticks))
            {
                return ExternalJson.Failure(operation, "media_seek_dispatch_rejected");
            }

            GlobalSystemMediaTransportControlsSessionTimelineProperties after = before;
            bool alreadyWithinPostreadTolerance =
                (before.Position - desired).Duration() <= TimeSpan.FromSeconds(2.5);
            bool verified = false;
            Exception? observationError = null;
            for (int attempt = 0; attempt <= SmtcPostreadPollIntervals; attempt++)
            {
                try
                {
                    after = session.GetTimelineProperties();
                    bool playing = session.GetPlaybackInfo().PlaybackStatus
                        == GlobalSystemMediaTransportControlsSessionPlaybackStatus.Playing;
                    TimeSpan tolerance = TimeSpan.FromSeconds(playing ? 2.5 : 1.0);
                    verified = (after.Position - desired).Duration() <= tolerance;
                    observationError = null;
                }
                catch (Exception exception) when (!cancellationToken.IsCancellationRequested)
                {
                    observationError = exception;
                    verified = false;
                }

                bool terminal = attempt == SmtcPostreadPollIntervals;
                if ((verified && (!alreadyWithinPostreadTolerance || terminal)) || terminal)
                {
                    if (!verified && observationError is not null)
                    {
                        throw observationError;
                    }

                    break;
                }

                verified = false;
                await _delay(SmtcPostreadPollInterval, cancellationToken)
                    .ConfigureAwait(false);
            }

            if (!verified)
            {
                return ExternalJson.Failure(
                    operation,
                    "media_seek_postcondition_not_verified",
                    effectObserved: true);
            }

            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteNumber("requestedDeltaSeconds", seconds);
                writer.WriteNumber("previousPositionSeconds", before.Position.TotalSeconds);
                writer.WriteNumber("positionSeconds", after.Position.TotalSeconds);
                writer.WriteNumber("durationSeconds", after.EndTime.TotalSeconds);
                writer.WriteString("sourceAppUserModelId", session.SourceAppUserModelId);
                writer.WriteString("authority", "windows_smtc_timeline_postread");
                writer.WriteEndObject();
            });
            return ExternalJson.Success(operation, result, effectObserved: true);
        }
        catch when (!cancellationToken.IsCancellationRequested)
        {
            return ExternalJson.Failure(
                operation,
                "media_seek_observation_failed",
                effectBoundaryCrossed);
        }
    }

    private static JsonElement MediaResult(
        GlobalSystemMediaTransportControlsSessionMediaProperties properties,
        string status,
        string sourceAppUserModelId,
        string? provider = null) => ExternalJson.Create(writer =>
    {
        writer.WriteStartObject();
        writer.WriteNumber("version", 1);
        if (provider is not null)
            writer.WriteString("provider", provider);
        writer.WriteString("sourceAppUserModelId", sourceAppUserModelId);
        writer.WriteString("title", properties.Title);
        writer.WriteString("artist", properties.Artist);
        writer.WriteString("playbackStatus", status);
        writer.WriteString("authority", "windows_smtc");
        writer.WriteEndObject();
    });

    private static async ValueTask DefaultDelayAsync(
        TimeSpan delay,
        CancellationToken cancellationToken)
    {
        await Task.Delay(delay, cancellationToken).ConfigureAwait(false);
    }

    private static string Fold(string value)
    {
        string normalized = value.Normalize(NormalizationForm.FormD).ToLowerInvariant();
        var builder = new StringBuilder(normalized.Length);
        foreach (char character in normalized)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) != UnicodeCategory.NonSpacingMark)
            {
                builder.Append(char.IsLetterOrDigit(character) ? character : ' ');
            }
        }
        return string.Join(' ', builder.ToString().Split(' ', StringSplitOptions.RemoveEmptyEntries));
    }
}
