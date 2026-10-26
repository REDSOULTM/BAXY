namespace Baxy.Providers.Windows.Filesystem;

/// <summary>
/// Holdout v6 V6E041 (aid overwrite_guard): what a file's text would lose to the text that takes its place, the one
/// measure of file.write's replacement and file.edit's edit (V6E048). Lines null: a file that is no text.
/// </summary>
internal sealed record TextLoss(int? Lines, int Characters, int LinesKept)
{
    // Null when nothing is lost (an empty file or only blanks, a text that holds all of it) or when the text keeps more
    // than half of its words (an edit: a line corrected, one of three taken out); otherwise the file's lines, characters
    // and the lines the text keeps.
    internal static TextLoss? Of(string before, string text)
    {
        string had = Unified(before).Trim();
        if (had.Length == 0 || Unified(text).Contains(had, StringComparison.Ordinal)) return null;
        var words = new Dictionary<string, int>(StringComparer.Ordinal);
        foreach (string word in Words(text)) words[word] = words.GetValueOrDefault(word) + 1;
        int total = 0, kept = 0;
        foreach (string word in Words(before))
        {
            total++;
            if (words.GetValueOrDefault(word) > 0)
            {
                words[word]--;
                kept++;
            }
        }
        if (total > 0 && kept * 2 > total) return null;
        string[] lines = LinesOf(before);
        var newLines = new Dictionary<string, int>(StringComparer.Ordinal);
        foreach (string line in LinesOf(text))
        {
            string trimmed = line.Trim();
            newLines[trimmed] = newLines.GetValueOrDefault(trimmed) + 1;
        }
        int linesKept = 0;
        foreach (string line in lines)
        {
            string trimmed = line.Trim();
            if (trimmed.Length > 0 && newLines.GetValueOrDefault(trimmed) > 0)
            {
                newLines[trimmed]--;
                linesKept++;
            }
        }
        return new TextLoss(lines.Length, before.Length, linesKept);
    }

    private static string Unified(string text) =>
        text.Replace("\r\n", "\n", StringComparison.Ordinal).Replace('\r', '\n');

    // A text's lines as a reader counts them: a last line break ends the last line, it starts none.
    private static string[] LinesOf(string text)
    {
        string unified = Unified(text);
        if (unified.EndsWith('\n')) unified = unified[..^1];
        return unified.Length == 0 ? [] : unified.Split('\n');
    }

    // Its words: runs of letters and digits, in lower case.
    private static IEnumerable<string> Words(string text)
    {
        int start = -1;
        for (int index = 0; index <= text.Length; index++)
        {
            bool inWord = index < text.Length && char.IsLetterOrDigit(text[index]);
            if (inWord && start < 0)
            {
                start = index;
            }
            else if (!inWord && start >= 0)
            {
                yield return text[start..index].ToLowerInvariant();
                start = -1;
            }
        }
    }
}
