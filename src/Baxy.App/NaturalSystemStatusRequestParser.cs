using System.Globalization;
using System.Text;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Baxy.App;

internal static partial class NaturalSystemStatusRequestParser
{
    public static bool TryParse(string text, out RoutedOperation? operation)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(text);
        string folded = Fold(text);
        if (IsCurrentTimeRequest(text))
        {
            operation = new RoutedOperation("system.time", new JsonObject());
            return true;
        }

        if (ProcessListPattern().IsMatch(folded))
        {
            string sort = ProcessCpuPattern().IsMatch(folded)
                ? "cpu"
                : ProcessMemoryPattern().IsMatch(folded)
                    ? "memory"
                    : "name";
            operation = new RoutedOperation(
                "system.process.list",
                new JsonObject { ["sort"] = sort, ["limit"] = 10 });
            return true;
        }

        string? scope = folded switch
        {
            _ when GpuIdentityPattern().IsMatch(folded) => "gpu_identity",
            _ when GpuUsagePattern().IsMatch(folded) => "gpu_usage",
            _ when CombinedCpuMemoryPattern().IsMatch(folded) => "cpu_memory",
            _ when CombinedOsMemoryPattern().IsMatch(folded) => "os_memory",
            _ when SummaryPattern().IsMatch(folded) => "summary",
            _ when BatteryPattern().IsMatch(folded) => "battery",
            _ when DiskPattern().IsMatch(folded) => "disk",
            _ when CpuPattern().IsMatch(folded) => "cpu",
            _ when MemoryPattern().IsMatch(folded) => "memory",
            _ when OperatingSystemPattern().IsMatch(folded) => "os",
            _ => null,
        };

        if (scope is null)
        {
            operation = null;
            return false;
        }

        operation = new RoutedOperation(
            "system.status",
            new JsonObject { ["scope"] = scope });
        return true;
    }

    private static string Fold(string value)
    {
        string decomposed = value.Normalize(NormalizationForm.FormD);
        var builder = new StringBuilder(decomposed.Length);
        foreach (char character in decomposed)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) != UnicodeCategory.NonSpacingMark)
            {
                builder.Append(char.ToLowerInvariant(character));
            }
        }

        return HorizontalWhitespacePattern()
            .Replace(builder.ToString(), " ")
            .Replace("¿", string.Empty, StringComparison.Ordinal)
            .Replace("¡", string.Empty, StringComparison.Ordinal)
            .Trim()
            .Normalize(NormalizationForm.FormC);
    }

    internal static bool IsCurrentTimeRequest(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return false;
        }

        string folded = Fold(text);
        if (MatchesTimePattern(folded))
        {
            return true;
        }

        if (folded.Length > 96 || TimeZoneTopicPattern().IsMatch(folded))
        {
            return false;
        }

        if (InventedClockAskPattern().IsMatch(folded)
            && !NegatedInventionPattern().IsMatch(folded))
        {
            return false;
        }

        return CurrentTimeAskPattern().IsMatch(folded)
            || CurrentTimeParaphrasePattern().IsMatch(folded);
    }

    internal static bool IsClockAndAudioStatusRequest(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return false;
        }

        string folded = Fold(text);
        bool clock = folded.Contains("hora", StringComparison.Ordinal)
            || folded.Contains("clock", StringComparison.Ordinal)
            || folded.Contains("reloj", StringComparison.Ordinal)
            || folded.Contains("time", StringComparison.Ordinal);
        bool audio = folded.Contains("audio", StringComparison.Ordinal)
            || folded.Contains("volumen", StringComparison.Ordinal)
            || folded.Contains("volume", StringComparison.Ordinal)
            || folded.Contains("mute", StringComparison.Ordinal)
            || folded.Contains("silenci", StringComparison.Ordinal);
        return clock && audio;
    }

    private static bool MatchesTimePattern(string folded)
    {
        if (TimePattern().IsMatch(folded))
        {
            return true;
        }

        string remainder = LeadingCourtesyPattern().Replace(folded, string.Empty).Trim();
        return remainder.Length > 0
            && !string.Equals(remainder, folded, StringComparison.Ordinal)
            && TimePattern().IsMatch(remainder);
    }

    [GeneratedRegex(
        "^(?:(?:dame|dime|decime|me dices|puedes decirme) (?:la hora(?: exacta| actual| local)?(?: en este momento| ahora(?: mismo)?)?|la fecha(?: de hoy)?|que hora es(?: ahora)?)|que (?:hora|fecha) es(?: ahora)?|hora (?:actual|local)(?: por favor)?|what time is it(?: now| right now| ahora)?|what(?:'|’)?s the time(?: now| right now)?|what is today(?:'|’)?s date|tell me the (?:current|local) time|cual es la fecha de hoy|diga la fecha hoy|mi puoi dire che ore sono|quelle heure est il|wie spat ist es|che ore sono)[?!.]?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex TimePattern();

    [GeneratedRegex(
        "^(?:(?:hola|hi|hey|hello|buenas(?: tardes| dias)?|gracias|thanks|ok|oye|please|porfa|ey)[,!. \\-—]+)+",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex LeadingCourtesyPattern();

    [GeneratedRegex(
        "\\b(?:huso|time zone|time zones|timezone|zona horaria|utc)\\b",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex TimeZoneTopicPattern();

    [GeneratedRegex(
        "\\b(?:inventa|invent|fabrica|make up|adivina|guess)\\b",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex InventedClockAskPattern();

    [GeneratedRegex(
        "(?:^|[, ])(?:no|sin|don['’]?t) (?:inventar|inventes|adivines|guess(?:ing)?)",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex NegatedInventionPattern();

    [GeneratedRegex(
        "^(?:(?:hola|hi|hey|hello|buenas(?: tardes| dias)?|gracias|thanks|ok|oye|please|porfa)[,!. \\-—]+)*(?:(?:me |puedes |could you |can you )?(?:dices |dime |decime |decir |tell me |give me |lees |leer |read )?)?(?:la |the |el |este |this )?(?:computers |computer['’]?s |pc |equipo )?(?:hora(?: exacta| local| actual)?|time|local time|current time|clock|reloj)(?: local| actual| now| ahora| please| por favor| otra vez| again| check| de este pc| of this pc| ya)?(?:(?:[, ]+| y )(?:sin inventar|no adivines|no inventes|don['’]?t guess|no guessing|please|porfa|por favor))?[?!. ]*$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex CurrentTimeAskPattern();

    [GeneratedRegex(
        "^(?:what does the clock say|que marca el reloj|tell the time(?: in english)?|otra vez[, ]+la hora|la hora[, ]+otra vez|finish with the local clock|termina con la hora local|local clock time|now the (?:time|clock)(?:[, ]+please)?|a tiny clock fact|segun el reloj, que (?:dia|hora) (?:es|marca)|la hora ya|clock now|clock\\??|check the time|time now|time once more|hora local, please)[?!. ]*$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex CurrentTimeParaphrasePattern();



    [GeneratedRegex(
        "^(?:(?:revisa(?: el)?(?: uso de)?|muestra(?:me)?|show(?: me)?|check)(?: el| the)? (?:cpu (?:y|and) ram|ram (?:y|and) cpu)|how much (?:memory and cpu|cpu and memory) am i using)[?!.]?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex CombinedCpuMemoryPattern();

    [GeneratedRegex(
        "^(?:dime )?que version de windows tengo y cuanta ram (?:tiene este pc|tengo)(?: usa python)?[?!.]?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex CombinedOsMemoryPattern();

    [GeneratedRegex(
        "^(?:dime mi gpu|dime que gpu tengo(?: y cuanta vram tiene)?|que gpu tengo|que gpu tiene este pc|cuanta vram tengo)[?!.]?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex GpuIdentityPattern();

    [GeneratedRegex(
        "^(?:show vram|muestra mi vram|gpu usage|uso de gpu|muestra uso de gpu con nvidia-smi|que tan llena esta la gpu|revisa (?:vram|nvidia-smi)|verifica gpu con nvidia-smi sin estresar pc)[?!.]?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex GpuUsagePattern();

    [GeneratedRegex(
        "^(?:estado(?: de)? (?:la |mi )?(?:pc|computadora|computador|equipo|sistema)|(?:mi |my |the )?(?:pc|computer|system) status|what is (?:my |the )?(?:pc|computer|system) status|como esta (?:mi |la )?(?:pc|computadora|computador|equipo|sistema)|how is (?:my |the )?(?:pc|computer|system)(?: doing)?|how esta mi pc status|revisa (?:el )?(?:estado|status)(?: de)? (?:mi |la )?(?:pc|computer|sistema))[?!.]?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex SummaryPattern();

    [GeneratedRegex(
        "^(?:battery (?:level|status|percentage(?: please)?)|how(?:'|’)?s my battery doing|do i have enough battery left|is my battery charging right now|estado de (?:la )?bateria|(?:nivel|niveau|livello|pourcentage|percentuale) (?:de |della )?(?:la )?(?:bateria|batterie)|que bateria queda|como esta la bateria|me queda mucha bateria|(?:la bateria|la batterie) (?:si sta|est en train de|esta) (?:caricando|charger|cargando)|(?:la bateria esta|esta) cargando(?: la bateria)?|(?:mostrame|muestrame) la bateria|(?:dime |decime )?cuanta bateria(?: tengo| queda| me queda| le queda a la notebook)?|cuanto por ciento de bateria tengo)[?!.]?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex BatteryPattern();

    [GeneratedRegex(
        "^(?:espacio en (?:el )?disco|free disk space|how much (?:free )?disk space (?:is free|is left|do i have left|do i have)|(?:dime )?cuanto espacio (?:libre|usado)(?: tengo| hay)? en (?:el )?disco(?: c)?|cuanto espacio libre tengo en (?:el disco )?c|quanto (?:spazio|espaco) (?:libero|livre)(?: ho| c e| tem)? (?:sul|no) disco|quanto (?:spazio|espaco) (?:mi resta|livre tem) (?:sul|no) disco)[?!.]?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex DiskPattern();

    [GeneratedRegex(
        "^(?:current cpu usage|uso de cpu actual|how busy is the cpu|(?:muestra|muestrame) el uso de cpu|what is the cpu usage|cual es el uso del procesador|que tan cargado esta el procesador|cuanta cpu estoy usando|cuanto uso de cpu tengo|dime cuantos nucleos de cpu tiene este pc y que modelo de procesador es)[?!.]?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex CpuPattern();

    [GeneratedRegex(
        "^(?:cuanta ram tengo|how much ram (?:is used|do i have)|cuanta (?:ram|memoria) (?:me queda libre|tengo libre)|quanta (?:memoria|ram) (?:ho libera|livre tenho)|cuanta ram estoy usando|dime cuanta ram tengo libre|cuanta ram libre hay en el sistema|dime cuanta ram tiene este pc)[?!.]?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex MemoryPattern();

    [GeneratedRegex(
        "^(?:dime )?que version de windows tengo[?!.]?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex OperatingSystemPattern();

    [GeneratedRegex(
        "^(?:(?:list all running processes)|(?:regarde|liste|affiche|montre|lista|listar|muestra|muestrame|mostrame|list|show me|show|what processes are|cuantos procesos hay)(?: (?:les|los|all|the|todos|me|my))? (?:processus|procesos|processes)(?: (?:actifs|activos|active|running|corriendo|que mas consumen|por cpu|por ram))?)(?: please| por favor)?[?!.]?$",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ProcessListPattern();

    [GeneratedRegex(
        "\\b(?:cpu|procesador|processor)\\b",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ProcessCpuPattern();

    [GeneratedRegex(
        "\\b(?:ram|memoria|memory|memoire)\\b",
        RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex ProcessMemoryPattern();

    [GeneratedRegex("[ \\t]+", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking)]
    private static partial Regex HorizontalWhitespacePattern();
}
