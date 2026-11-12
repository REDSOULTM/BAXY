using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.Providers.Windows.Routines;

/// <summary>
/// RUT1 (documentacion/RUTINAS.md §1-§2): the person's routines, one JSON file under the data root
/// (<c>routines-store\routines.v1.json</c>), each routine an object of the contract's shape (id, name, trigger, steps,
/// active, createdUtc, changedUtc). Written to a temporary file and moved over the old one, which is kept as
/// <c>.bak</c>; a file that cannot be read is never overwritten (it fails closed, as LocalTaskStore does).
/// </summary>
public sealed class LocalRoutineStore(string folder)
{
    /// <summary>The store's folder name under the data root.</summary>
    public const string FolderName = "routines-store";

    /// <summary>The most routines a person keeps.</summary>
    public const int MaximumRoutines = 64;

    private const string FileName = "routines.v1.json";

    private const int MaximumBytes = 64 * 1024;

    public string Folder { get; } = folder;

    private string FilePath => Path.Combine(Folder, FileName);

    /// <summary>The routines kept, in the order they were made; empty when there is no file yet. Throws
    /// <see cref="InvalidDataException"/> when the file is there and is not a routines list.</summary>
    public IReadOnlyList<JsonObject> Read()
    {
        if (!File.Exists(FilePath))
        {
            return [];
        }

        var info = new FileInfo(FilePath);
        if (info.Length > MaximumBytes)
        {
            throw new InvalidDataException("The routines file is larger than its limit.");
        }

        try
        {
            if (JsonNode.Parse(File.ReadAllText(FilePath, Encoding.UTF8)) is JsonObject root
                && root["routines"] is JsonArray routines
                && routines.All(static routine => routine is JsonObject))
            {
                return routines.Select(static routine => (JsonObject)routine!.DeepClone()).ToList();
            }
        }
        catch (JsonException exception)
        {
            throw new InvalidDataException("The routines file is not JSON.", exception);
        }

        throw new InvalidDataException("The routines file is not a routines list.");
    }

    /// <summary>Replaces the whole list, then reads it back; false when what was read is not what was written.</summary>
    public bool Write(IReadOnlyList<JsonObject> routines)
    {
        ArgumentNullException.ThrowIfNull(routines);
        var root = new JsonObject
        {
            ["version"] = 1,
            ["routines"] = new JsonArray(routines.Select(static routine => (JsonNode)routine.DeepClone()).ToArray()),
        };
        string text = root.ToJsonString(new JsonSerializerOptions { WriteIndented = true });
        if (Encoding.UTF8.GetByteCount(text) > MaximumBytes)
        {
            throw new InvalidDataException("The routines do not fit in the routines file.");
        }

        Directory.CreateDirectory(Folder);
        string temporary = FilePath + ".tmp";
        File.WriteAllText(temporary, text, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
        if (File.Exists(FilePath))
        {
            File.Replace(temporary, FilePath, FilePath + ".bak");
        }
        else
        {
            File.Move(temporary, FilePath);
        }

        return File.ReadAllText(FilePath, Encoding.UTF8) == text;
    }

    /// <summary>«Olvidar todo» and the uninstaller: the file and its backup go.</summary>
    public void DeleteAll()
    {
        foreach (string path in new[] { FilePath, FilePath + ".bak", FilePath + ".tmp" })
        {
            if (File.Exists(path))
            {
                File.Delete(path);
            }
        }
    }

    /// <summary>
    /// How a phrase or a name is compared (RUTINAS.md §1): lower case, without accents (NFD without its marks), without
    /// punctuation, single spaces. Only for comparing; the person's own spelling is what is kept and said.
    /// </summary>
    public static string Folded(string? text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return string.Empty;
        }

        var kept = new StringBuilder(text.Length);
        bool space = false;
        foreach (char character in text.Normalize(NormalizationForm.FormD))
        {
            UnicodeCategory category = CharUnicodeInfo.GetUnicodeCategory(character);
            if (category == UnicodeCategory.NonSpacingMark)
            {
                continue;
            }

            if (char.IsLetterOrDigit(character))
            {
                if (space && kept.Length > 0)
                {
                    kept.Append(' ');
                }

                kept.Append(char.ToLowerInvariant(character));
                space = false;
            }
            else
            {
                space = true;
            }
        }

        return kept.ToString().Normalize(NormalizationForm.FormC);
    }
}
