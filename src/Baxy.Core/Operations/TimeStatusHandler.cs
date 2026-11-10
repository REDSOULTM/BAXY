using System.Buffers;
using System.Globalization;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Infrastructure;
using Baxy.Providers.Windows.SystemStatus;

namespace Baxy.Core.Operations;

internal sealed class TimeStatusHandler(ITimeStatusProvider provider, IPlaceTimeZoneResolver places) : IOperationHandler
{
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("system.time");

    public async ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
    {
        // With a named place or zone, the reading also carries that zone's offset at the same observed instant. With
        // the aid place_clock (V5E016: the model added the offset to the PC's local clock and missed the change of day)
        // it carries that place's own date, clock time and weekday too; without it, the mind does the clock arithmetic.
        PlaceTimeZone? place = null;
        if (ReadPlace(invocation.Arguments) is { } named)
        {
            PlaceTimeZoneReading reading = await places.ResolveAsync(named, cancellationToken).ConfigureAwait(false);
            // WEB2: the places found instead travel with the failure, as the weather's do, so the person can be asked.
            if (reading.Place is null)
                return OperationOutcome.Failure(reading.ErrorCode ?? "time_place_not_found", result: reading.Candidates);
            place = reading.Place;
        }

        // VER1 (PR-03): a date asked about is worked out here, never by the model (CalendarAsk).
        if (!CalendarAsk.TryRead(invocation.Arguments, out CalendarAsk? asked))
            return OperationOutcome.Failure("time_date_invalid", result: CalendarAsk.Expected);

        TimeStatusSnapshot? snapshot = await provider.ReadVerifiedAsync(cancellationToken).ConfigureAwait(false);
        if (snapshot is null) return OperationOutcome.Failure("verification_failed");
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("utc", snapshot.UtcNow.ToString("O", CultureInfo.InvariantCulture));
            writer.WriteNumber("localUtcOffsetMinutes", snapshot.LocalUtcOffsetMinutes);
            // PUE5: the PC's clock time worked out here. With only utc the model read the utc field's hour as the PC's
            // («son las 5:54 de la tarde» at 05:54); a local date beside it brought «de este viernes» on a Thursday
            // (PUE4), so only the clock time, without a date.
            writer.WriteString("localTime", snapshot.UtcNow.ToOffset(TimeSpan.FromMinutes(snapshot.LocalUtcOffsetMinutes))
                .ToString("HH:mm", CultureInfo.InvariantCulture));
            if (place is not null)
            {
                writer.WriteStartObject("place");
                writer.WriteString("name", place.Name);
                writer.WriteString("country", place.Country);
                writer.WriteString("timeZone", place.Zone.Id);
                writer.WriteNumber(
                    "utcOffsetMinutes",
                    checked((int)place.Zone.GetUtcOffset(snapshot.UtcNow).TotalMinutes));
                if (ModelAids.On(ModelAids.PlaceClock))
                {
                    DateTimeOffset there = TimeZoneInfo.ConvertTime(snapshot.UtcNow, place.Zone);
                    writer.WriteString("date", there.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture));
                    writer.WriteString("localTime", there.ToString("HH:mm", CultureInfo.InvariantCulture));
                    writer.WriteString("weekday", there.ToString("dddd", CultureInfo.InvariantCulture));
                }
                writer.WriteString("authority", place.Authority);
                writer.WriteEndObject();
            }
            asked?.Write(writer, DateOnly.FromDateTime(
                snapshot.UtcNow.ToOffset(TimeSpan.FromMinutes(snapshot.LocalUtcOffsetMinutes)).DateTime));
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return OperationOutcome.Success(document.RootElement.Clone());
    }

    /// <summary>
    /// VER1 (PR-03, «en siete días es el viernes 12»): asked for a date that is not today, the 4B counted days and
    /// weekdays from the clock line and was wrong in most answers (INFORME_VER1 §4, 2026-11-09). What is asked about is
    /// typed, and its date, weekday and distance in days are worked out here on the PC's own date: «daysFromToday»; a
    /// «month» and «day», which with no «year» give the coming one (today's included) and the last one before today,
    /// so the model never chooses a year (it gave this year's 1 January for the one coming); or a «weekday»: the last
    /// one before today, the coming one after it and the one in next week, weeks from Monday as ISO 8601 counts them
    /// (named as the dates are: «el martes de la semana que viene» read «next» as tomorrow's). Nothing is added to a
    /// reading that asks for none.
    /// </summary>
    private sealed record CalendarAsk(int? Days, (int Month, int Day, int? Year)? Date, DayOfWeek? Weekday)
    {
        private const string DateFormat = "yyyy-MM-dd";

        // No date of a calendar is further than this from a day and month with no year (29 February, eight years).
        private const int YearsLooked = 8;

        internal static JsonElement Expected { get; } = JsonDocument.Parse(
            """{"version":1,"daysFromToday":"a whole number","month":"1 to 12, with day","day":"a day of that month, with month","year":"optional, with month and day","weekday":"monday to sunday"}""")
            .RootElement.Clone();

        /// <summary>False when an argument given cannot be read as what it is; <paramref name="asked"/> null when none was given.</summary>
        internal static bool TryRead(JsonElement arguments, out CalendarAsk? asked)
        {
            asked = null;
            if (arguments.ValueKind != JsonValueKind.Object) return true;
            if (!Whole(arguments, "daysFromToday", out int? days) || !Whole(arguments, "month", out int? month)
                || !Whole(arguments, "day", out int? day) || !Whole(arguments, "year", out int? year))
                return false;
            (int, int, int?)? date = null;
            if (month is not null || day is not null || year is not null)
            {
                // A day and its month together; 29 February stands with no year, and in a leap one.
                if (month is not (>= 1 and <= 12) || day is not >= 1 || day > DateTime.DaysInMonth(year ?? 2000, month.Value)
                    || year is < 1 or > 9999)
                    return false;
                date = (month.Value, day.Value, year);
            }

            DayOfWeek? weekday = null;
            if (arguments.TryGetProperty("weekday", out JsonElement name) && name.ValueKind != JsonValueKind.Null)
            {
                // By its name only: Enum.TryParse would also take «3».
                if (name.ValueKind != JsonValueKind.String || name.GetString() is not { } said
                    || !said.All(char.IsLetter) || !Enum.TryParse(said, ignoreCase: true, out DayOfWeek named))
                    return false;
                weekday = named;
            }

            if (days is not null || date is not null || weekday is not null) asked = new(days, date, weekday);
            return true;
        }

        internal void Write(Utf8JsonWriter writer, DateOnly today)
        {
            writer.WriteStartObject("calendar");
            writer.WriteStartObject("today");
            WriteDay(writer, today, today, named: true);
            writer.WriteEndObject();
            if (Days is { } days)
            {
                writer.WriteStartObject("inDays");
                WriteDay(writer, today.AddDays(days), today, named: true);
                writer.WriteEndObject();
            }

            if (Date is { } date)
            {
                writer.WriteStartObject("onDate");
                if (date.Year is { } year)
                {
                    WriteDay(writer, new DateOnly(year, date.Month, date.Day), today, named: true);
                }
                else
                {
                    foreach ((string key, int step) in new[] { ("coming", 1), ("last", -1) })
                    {
                        // From this year on for the coming one (today's counts), back from it for the last one.
                        DateOnly? found = Enumerable.Range(0, YearsLooked + 1)
                            .Select(n => today.Year + (step * n))
                            .Where(y => y is >= 1 and <= 9999 && date.Day <= DateTime.DaysInMonth(y, date.Month))
                            .Select(y => (DateOnly?)new DateOnly(y, date.Month, date.Day))
                            .FirstOrDefault(d => step > 0 ? d >= today : d < today);
                        if (found is { } one)
                        {
                            writer.WriteStartObject(key);
                            WriteDay(writer, one, today, named: true);
                            writer.WriteEndObject();
                        }
                    }
                }

                writer.WriteEndObject();
            }

            if (Weekday is { } weekday)
            {
                // Days back to the last one before today and on to the next one after it: 1 to 7 each.
                int back = (((int)today.DayOfWeek - (int)weekday + 6) % 7) + 1;
                int on = (((int)weekday - (int)today.DayOfWeek + 6) % 7) + 1;
                DateOnly nextMonday = today.AddDays((((int)DayOfWeek.Monday - (int)today.DayOfWeek + 6) % 7) + 1);
                writer.WriteStartObject("weekday");
                writer.WriteString("name", weekday.ToString());
                writer.WriteBoolean("isToday", today.DayOfWeek == weekday);
                foreach ((string key, DateOnly day) in new[]
                         {
                             ("last", today.AddDays(-back)),
                             ("coming", today.AddDays(on)),
                             ("inNextWeek", nextMonday.AddDays(((int)weekday + 6) % 7)),
                         })
                {
                    writer.WriteStartObject(key);
                    WriteDay(writer, day, today, named: false);
                    writer.WriteEndObject();
                }

                writer.WriteEndObject();
            }

            writer.WriteEndObject();
        }

        private static bool Whole(JsonElement arguments, string name, out int? value)
        {
            value = null;
            if (!arguments.TryGetProperty(name, out JsonElement given) || given.ValueKind == JsonValueKind.Null) return true;
            if (given.ValueKind != JsonValueKind.Number || !given.TryGetInt32(out int whole)) return false;
            value = whole;
            return true;
        }

        private static void WriteDay(Utf8JsonWriter writer, DateOnly day, DateOnly today, bool named)
        {
            writer.WriteString("date", day.ToString(DateFormat, CultureInfo.InvariantCulture));
            if (named) writer.WriteString("weekday", day.DayOfWeek.ToString());
            if (day != today || !named) writer.WriteNumber("daysFromToday", day.DayNumber - today.DayNumber);
        }
    }

    private static string? ReadPlace(JsonElement arguments) =>
        arguments.ValueKind == JsonValueKind.Object
        && arguments.TryGetProperty("place", out JsonElement value)
        && value.ValueKind == JsonValueKind.String
        && value.GetString() is { } text
        && !string.IsNullOrWhiteSpace(text)
            ? text.Trim()
            : null;
}
