using System.Runtime.InteropServices;
using System.Text.Json;
using Baxy.Providers.Windows.Audio;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// RUT2 (pedido del dueño 10-11-2026: «cambia a los audífonos», «cambia a los altavoces»): audio.device.list reads the
/// active outputs and inputs by the names Windows shows and which one is the default; audio.device.set makes the one the
/// person named the default and reads the default again. The name said is compared with the names listed by form only
/// (<see cref="Matching"/>): one device matches and it is set; none or several and nothing changes, the failure lists
/// them so the model asks. Setting the default goes through the Sound panel's PolicyConfig client
/// (<see cref="WindowsCoreAudioPlatform.SetDefaultDevice"/>), which Windows does not document: a failed set or a default
/// that reads otherwise afterwards is a failed receipt.
/// </summary>
internal sealed class WindowsAudioDeviceAdapter : IExternalOperationAdapter
{
    internal const string NotMatched = "audio_device_not_matched";
    internal const string Ambiguous = "audio_device_ambiguous";
    internal const string NotVerified = "audio_default_not_verified";

    private readonly IAudioDevicePlatform _platform;

    internal WindowsAudioDeviceAdapter()
        : this(new WindowsAudioDevicePlatform())
    {
    }

    internal WindowsAudioDeviceAdapter(IAudioDevicePlatform platform) =>
        _platform = platform ?? throw new ArgumentNullException(nameof(platform));

    public bool CanHandle(string operation) => operation is "audio.device.list" or "audio.device.set";

    public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(operation == "audio.device.list"
                ? List(operation)
                : Set(operation, arguments, effectBoundary));
        }
        catch (Exception exception) when (exception is AudioPlatformException or COMException
            or InvalidCastException or InvalidDataException)
        {
            return ValueTask.FromResult(effectBoundary.Failure(operation, "audio_device_failed"));
        }
    }

    private ExternalCapabilityReceipt List(string operation)
    {
        IReadOnlyList<AudioDevice> outputs = _platform.Active(capture: false);
        IReadOnlyList<AudioDevice> inputs = _platform.Active(capture: true);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            WriteDevices(writer, "outputs", outputs);
            WriteDevices(writer, "inputs", inputs);
            writer.WriteString("authority", "windows_core_audio_endpoints_read");
            writer.WriteEndObject();
        }), effectObserved: false);
    }

    private ExternalCapabilityReceipt Set(string operation, JsonElement arguments, ExternalEffectBoundary effectBoundary)
    {
        string said = ExternalJson.RequiredString(arguments, "device");
        bool capture = arguments.TryGetProperty("kind", out JsonElement kindValue)
            && kindValue.ValueKind == JsonValueKind.String
            && kindValue.GetString() == "input";
        string kind = capture ? "input" : "output";
        IReadOnlyList<AudioDevice> devices = _platform.Active(capture);
        IReadOnlyList<int> matching = Matching(said, devices.Select(static device => device.Name).ToArray());
        if (matching.Count != 1)
        {
            // Nothing changed: the devices the name could be (or all of them when it matched none), for the model to ask.
            IReadOnlyList<AudioDevice> shown = matching.Count == 0 ? devices : matching.Select(index => devices[index]).ToArray();
            return ExternalJson.FailureBeforeEffect(operation, matching.Count == 0 ? NotMatched : Ambiguous) with
            {
                Result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteString("kind", kind);
                    writer.WriteBoolean("changed", false);
                    WriteDevices(writer, "devices", shown);
                    writer.WriteString("next", matching.Count == 0
                        ? $"nothing changed: no active {kind} device has every word said in its name; these are the ones there are: ask the person which one"
                        : $"nothing changed: these {kind} devices all match the words said; ask the person which one (device takes words that tell it apart)");
                    writer.WriteEndObject();
                }),
            };
        }

        AudioDevice target = devices[matching[0]];
        if (target.Default && target.ConsoleDefault)
        {
            return ExternalJson.Switched(operation, Result(kind, target.Name, previous: null, changed: false), effectObserved: false);
        }

        string? previous = devices.FirstOrDefault(static device => device.Default)?.Name;
        effectBoundary.Cross();
        _platform.SetDefault(target.Id);
        AudioDevice? now = _platform.Active(capture).FirstOrDefault(static device => device.Default);
        if (now is not null && now.ConsoleDefault && string.Equals(now.Id, target.Id, StringComparison.Ordinal))
        {
            return ExternalJson.Success(operation, Result(kind, target.Name, previous, changed: true));
        }

        return ExternalJson.WithStateAfter(
            ExternalJson.FailureAfterEffect(operation, NotVerified),
            ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteString("default", now?.Name);
                writer.WriteBoolean("requested", false);
                writer.WriteEndObject();
            }));
    }

    private static JsonElement Result(string kind, string device, string? previous, bool changed) =>
        ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteString("kind", kind);
            writer.WriteString("device", device);
            if (previous is not null)
            {
                writer.WriteString("previous", previous);
            }

            writer.WriteBoolean("changed", changed);
            writer.WriteString("authority", "windows_core_audio_default_endpoint_postread");
            writer.WriteEndObject();
        });

    private static void WriteDevices(Utf8JsonWriter writer, string name, IReadOnlyList<AudioDevice> devices)
    {
        writer.WriteStartArray(name);
        foreach (AudioDevice device in devices)
        {
            writer.WriteStartObject();
            writer.WriteString("name", device.Name);
            writer.WriteBoolean("default", device.Default);
            writer.WriteEndObject();
        }

        writer.WriteEndArray();
    }

    /// <summary>
    /// The devices whose name holds every word that was said, compared by form (folded case and accents): a word matches
    /// a word of the name that is it, starts with it, is its singular or plural (<see cref="Singulars"/>) or differs by one
    /// letter (two in long words), so a name said in part, in the other number or with a typo still matches. Words of
    /// three letters or fewer count only when nothing longer was said (an article is not a device). A name said whole is that device. No meaning is guessed: a word no name holds matches nothing.
    /// </summary>
    internal static IReadOnlyList<int> Matching(string said, IReadOnlyList<string> names)
    {
        string[] words = Words(said);
        string[] significant = words.Where(static word => word.Length >= 4 || word.Any(char.IsDigit)).ToArray();
        if (significant.Length == 0)
        {
            significant = words;
        }

        if (significant.Length == 0)
        {
            return [];
        }

        string whole = string.Concat(words);
        int[] exact = Enumerable.Range(0, names.Count)
            .Where(index => string.Concat(Words(names[index])) == whole)
            .ToArray();
        if (exact.Length > 0)
        {
            return exact;
        }

        return Enumerable.Range(0, names.Count)
            .Where(index =>
            {
                string[] named = Words(names[index]);
                return significant.All(word => named.Any(name => WordMatches(word, name)));
            })
            .ToArray();
    }

    // Words split at anything that is not a letter, a digit or an accent mark, each folded.
    private static string[] Words(string value)
    {
        var words = new List<string>();
        var current = new System.Text.StringBuilder();
        foreach (char character in value.Normalize(System.Text.NormalizationForm.FormD) + " ")
        {
            if (char.IsLetterOrDigit(character)
                || System.Globalization.CharUnicodeInfo.GetUnicodeCategory(character)
                    == System.Globalization.UnicodeCategory.NonSpacingMark)
            {
                current.Append(character);
                continue;
            }

            string word = WindowsCoreAudioPlatform.FoldToken(current.ToString());
            if (word.Length > 0)
            {
                words.Add(word);
            }

            current.Clear();
        }

        return [.. words];
    }

    private static bool WordMatches(string said, string named)
    {
        if (said == named)
        {
            return true;
        }

        if (said.Length >= 3 && named.StartsWith(said, StringComparison.Ordinal))
        {
            return true;
        }

        if (named.Length >= 4 && said.StartsWith(named, StringComparison.Ordinal))
        {
            return true;
        }

        if (Singulars(said).Intersect(Singulars(named), StringComparer.Ordinal).Any())
        {
            return true;
        }

        int allowed = Math.Min(said.Length, named.Length) switch
        {
            >= 8 => 2,
            >= 5 => 1,
            _ => 0,
        };
        return allowed > 0 && Distance(said, named) <= allowed;
    }

    // RUT5 (VIVOR2: «altavoz» did not match «Altavoces»): the word and what it would be if it were a regular plural, by
    // the rules of form of the two languages device names come in: Spanish adds -s or -es and a final z becomes -ces
    // (RAE, Diccionario panhispánico de dudas, «plural», section 1, https://www.rae.es/dpd/plural), English adds -s or -es
    // and a final consonant + y becomes -ies (Cambridge Dictionary, «Nouns: singular and plural»). Words of four letters
    // or fewer are left alone.
    private static IEnumerable<string> Singulars(string word)
    {
        yield return word;
        if (word.Length <= 4 || !word.EndsWith('s'))
        {
            yield break;
        }

        yield return word[..^1];
        if (word.EndsWith("es", StringComparison.Ordinal))
        {
            yield return word[..^2];
        }

        if (word.EndsWith("ces", StringComparison.Ordinal))
        {
            yield return word[..^3] + "z";
        }

        if (word.EndsWith("ies", StringComparison.Ordinal))
        {
            yield return word[..^3] + "y";
        }
    }

    // Optimal string alignment distance: insertions, deletions, substitutions and adjacent swaps.
    private static int Distance(string a, string b)
    {
        int[,] d = new int[a.Length + 1, b.Length + 1];
        for (int i = 0; i <= a.Length; i++)
        {
            d[i, 0] = i;
        }

        for (int j = 0; j <= b.Length; j++)
        {
            d[0, j] = j;
        }

        for (int i = 1; i <= a.Length; i++)
        {
            for (int j = 1; j <= b.Length; j++)
            {
                int cost = a[i - 1] == b[j - 1] ? 0 : 1;
                d[i, j] = Math.Min(Math.Min(d[i - 1, j] + 1, d[i, j - 1] + 1), d[i - 1, j - 1] + cost);
                if (i > 1 && j > 1 && a[i - 1] == b[j - 2] && a[i - 2] == b[j - 1])
                {
                    d[i, j] = Math.Min(d[i, j], d[i - 2, j - 2] + 1);
                }
            }
        }

        return d[a.Length, b.Length];
    }
}
