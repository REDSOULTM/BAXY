using System.IO;
using System.Security.Cryptography;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.Providers.Windows.Infrastructure;

namespace Baxy.App;

/// <summary>
/// The person's verbs pick what a call does (c3-final6b e2e: the 4B model does not follow a receipt that tells it the
/// other call; refused, it asks the person with ask_user). In a turn the person opened, before anything runs:
/// <list type="bullet">
/// <item>Holdout v6 V6E041 («agrégale al file jugadores.txt … la línea: Matías, arquero», 8 of 8 runs file.write without
/// append): a file.write without append over a file of theirs that is there, when their words say to add to it and
/// nothing of replacing it, goes as an append, which keeps all the file had; a text that already holds what the file has
/// (the model rewrote it whole) goes as written. Aid «overwrite_guard».</item>
/// <item>e2e final6c V6E048 («sobrescribe repertorio.txt de mi carpeta Coro Parroquial en Documentos con la palabra
/// pendiente»: file_edit of one line, the file kept the rest): a file.edit of a file of theirs that is there, when their
/// words say to overwrite it, goes as the file.write of its newText over all of it under the file's own hash, which asks
/// the person's «sí» first (LocalFilesystemProvider.ReplacementAsksFirst). «Reemplaza X por Y» is an edit, and stays one.
/// Aid «overwrite_guard».</item>
/// <item>Holdout v5 V5E021 («a lo que tiene la calculadora súmale 53»): a calculator.expression.evaluate of a bare number,
/// when their words name one operation on what it shows, goes as that operator and the number (continuing from the
/// number shown). Words of several operations change nothing. Aid «calculator_next».</item>
/// </list>
/// The verbs are data (Assets/said-verbs.v1.json, embedded); the words are read as SaidFolders reads them (Spoken), and the
/// result of the call says what it did instead of what was written.
/// </summary>
internal sealed class SaidVerbs
{
    /// <summary>The fact in the result of a call the person's verb changed: the key it goes under.</summary>
    internal const string NoteKey = "saidVerb";

    // Text past this is no file an append is weighed for: it goes as written.
    private const long MaximumComparedBytes = 1_048_576;

    private static readonly Regex BareNumber = new(@"^\d+(?:[.,]\d+)?$", RegexOptions.CultureInvariant);

    private static readonly Lazy<(string[] Append, string[] KeepWhole, string[] Overwrite,
        (string Operator, string[] Words)[] Operators)> Verbs =
        new(() =>
        {
            using Stream stream = typeof(SaidVerbs).Assembly.GetManifestResourceStream("Baxy.App.SaidVerbs.json")
                ?? throw new InvalidOperationException("The said verbs are not embedded.");
            JsonObject data = JsonNode.Parse(stream) as JsonObject
                ?? throw new InvalidDataException("The said verbs are not an object.");
            static string[] Words(JsonNode? node) =>
                [.. (node as JsonArray ?? throw new InvalidDataException("A list of said verbs is missing."))
                    .Select(word => SaidFolders.Spoken((string)word!))];
            return (Words(data["append"]), Words(data["keepWhole"]), Words(data["overwrite"]),
                [.. (data["operators"] as JsonObject ?? throw new InvalidDataException("The said operators are missing."))
                    .Select(entry => (entry.Key, Words(entry.Value)))]);
        });

    private string _spoken = string.Empty;

    /// <summary>The person's words open a turn.</summary>
    internal void Heard(string words) => _spoken = SaidFolders.Spoken(words ?? string.Empty);

    /// <summary>The person's words answer the call that waits for their «sí»: the turn's words still hold, with these.</summary>
    internal void Answered(string words)
    {
        string spoken = SaidFolders.Spoken(words ?? string.Empty);
        _spoken = _spoken.Length == 0 ? spoken : _spoken + "\n" + spoken;
    }

    /// <summary>A heartbeat or a new session: no words of the person's hold.</summary>
    internal void Clear() => _spoken = string.Empty;

    /// <summary>
    /// The call as the person's verb picks it, and what its result says; null: it runs as it is.
    /// <paramref name="fileThere"/> gives the one file of the person's a file call (its operation and arguments) names
    /// when it is there (SaidFolders).
    /// </summary>
    internal (JsonObject Arguments, string Note)? Rule(string operation, JsonObject arguments,
        Func<string, JsonObject, string?> fileThere)
    {
        if (_spoken.Trim().Length == 0)
            return null;
        return operation switch
        {
            "file.write" => Append(arguments, () => fileThere(operation, arguments)),
            "file.edit" => Overwrite(arguments, fileThere),
            "calculator.expression.evaluate" => Operate(arguments),
            _ => null,
        };
    }

    private (JsonObject, string)? Append(JsonObject arguments, Func<string?> fileThere)
    {
        if (!ModelAids.On(ModelAids.OverwriteGuard)
            || (arguments["append"] is JsonValue append && append.TryGetValue(out bool on) && on)
            || Text(arguments["text"]) is not { } text
            || !Says(Verbs.Value.Append) || Says(Verbs.Value.KeepWhole)
            || fileThere() is not { } file || Holds(text, file))
            return null;
        var appended = (JsonObject)arguments.DeepClone();
        appended["append"] = true;
        string name = Path.GetFileName(file);
        return (appended, $"the person said to add to {name}: this call appended the text as a new line at its end and "
            + $"kept all {name} had, instead of replacing it, as it was written");
    }

    private (JsonObject, string)? Overwrite(JsonObject arguments, Func<string, JsonObject, string?> fileThere)
    {
        if (!ModelAids.On(ModelAids.OverwriteGuard) || !Says(Verbs.Value.Overwrite)
            || Text(arguments["newText"]) is not { } text || Text(arguments["folder"]) is not { } folder
            || folder == "all_known" || Text(arguments["fileName"]) is not { } fileName || Path.IsPathFullyQualified(fileName))
            return null;
        string? subdirectory = Text(arguments["subdirectory"]);
        if (subdirectory is not null && Path.IsPathFullyQualified(subdirectory))
            return null;
        var written = new JsonObject
        {
            ["relativePath"] = subdirectory is null ? fileName : subdirectory.TrimEnd('/', '\\') + "/" + fileName,
            ["folder"] = folder,
            ["text"] = text,
            ["append"] = false,
        };
        if (fileThere("file.write", written) is not { } file || Sha256(file) is not { } hash)
            return null;
        written["expectedSha256"] = hash;
        string name = Path.GetFileName(file);
        return (written, $"the person said to overwrite {name}: this call is file_write of newText over all {name} had, "
            + "under its current hash, its previous version to the Recycle Bin, instead of file_edit of oldText alone, as it "
            + "was written");
    }

    private static string? Sha256(string file)
    {
        try
        {
            using FileStream stream = File.OpenRead(file);
            return Convert.ToHexStringLower(SHA256.HashData(stream));
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return null;
        }
    }

    private (JsonObject, string)? Operate(JsonObject arguments)
    {
        if (!ModelAids.On(ModelAids.CalculatorNext) || Text(arguments["expression"]) is not { } number
            || !BareNumber.IsMatch(number))
            return null;
        string[] said = [.. Verbs.Value.Operators.Where(entry => Says(entry.Words)).Select(entry => entry.Operator)];
        if (said is not [string sign])
            return null;
        var operated = (JsonObject)arguments.DeepClone();
        operated["expression"] = sign + number;
        return (operated, $"the person said to operate on what the Calculator showed: this call pressed {sign}{number}, "
            + $"from the number it showed, instead of {number} alone, as it was written");
    }

    private bool Says(string[] words) => words.Any(word => _spoken.Contains(word, StringComparison.Ordinal));

    // Whether the text already holds all the file has (the model rewrote it whole with the new line): appending it would
    // write the file's text twice. A file that cannot be read whole as text is weighed as holding nothing.
    private static bool Holds(string text, string file)
    {
        try
        {
            if (new FileInfo(file).Length > MaximumComparedBytes)
                return true;
            string before = Lines(File.ReadAllText(file));
            return before.Length == 0 || Lines(text).Contains(before, StringComparison.Ordinal);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return true;
        }
    }

    private static string Lines(string text) => text.Replace("\r\n", "\n", StringComparison.Ordinal).Trim();

    private static string? Text(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out string? text) && !string.IsNullOrWhiteSpace(text) ? text.Trim() : null;
}
