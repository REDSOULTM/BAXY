using System.Text;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// file.edit's replacement in a text. Holdout v6 V6E048: the model wrote oldText with «\n» and the Windows file has
/// «\r\n» (a file_read shows neither), and the text the person sees there was not found. oldText is found as written;
/// when it is not there so, it is found with every line break read as a line break and the spaces and tabs that end a
/// line left out. newText's line breaks are written as the one the file uses, never mixed with it.
/// </summary>
internal static class TextReplacement
{
    /// <summary>
    /// Where oldText is (Occurrences), the text once replaced (null when it is not there, or is there more than once and
    /// not every one was asked) and how many places that changed.
    /// </summary>
    internal sealed record Replaced(int Occurrences, string? Edited, int Replacements);

    internal static Replaced Replace(string text, string oldText, string newText, bool replaceAll)
    {
        List<(int Start, int End)> spans = Spans(text, oldText);
        if (spans.Count == 0 || (spans.Count > 1 && !replaceAll)) return new Replaced(spans.Count, null, 0);
        string written = WithLineBreak(newText, LineBreakOf(text));
        var edited = new StringBuilder(text.Length);
        int at = 0;
        foreach ((int start, int end) in replaceAll ? spans : spans[..1])
        {
            edited.Append(text, at, start - at).Append(written);
            at = end;
        }
        return new Replaced(spans.Count, edited.Append(text, at, text.Length - at).ToString(), replaceAll ? spans.Count : 1);
    }

    internal static int Occurrences(string text, string value) => Spans(text, value).Count;

    // The places of value in text: as written, or else as its lines read (Folded).
    private static List<(int Start, int End)> Spans(string text, string value)
    {
        var spans = new List<(int Start, int End)>();
        for (int index = text.IndexOf(value, StringComparison.Ordinal); index >= 0;
             index = text.IndexOf(value, index + value.Length, StringComparison.Ordinal))
            spans.Add((index, index + value.Length));
        if (spans.Count > 0) return spans;
        Folded inText = Fold(text);
        string wanted = Fold(value).Text.ToString();
        string folded = inText.Text.ToString();
        for (int index = folded.IndexOf(wanted, StringComparison.Ordinal); index >= 0;
             index = folded.IndexOf(wanted, index + wanted.Length, StringComparison.Ordinal))
            spans.Add((inText.Starts[index], inText.Ends[index + wanted.Length - 1]));
        return spans;
    }

    // A text as its lines read: each line break («\r\n», «\n» or «\r») one «\n», and the spaces and tabs before it
    // gone; each character kept with the span it stands for in the text (a line break's holds the blanks before it).
    private sealed record Folded(StringBuilder Text, List<int> Starts, List<int> Ends);

    private static Folded Fold(string text)
    {
        var folded = new Folded(new StringBuilder(text.Length), new List<int>(text.Length), new List<int>(text.Length));
        int index = 0;
        while (index < text.Length)
        {
            int blanks = index;
            while (blanks < text.Length && text[blanks] is ' ' or '\t') blanks++;
            if (blanks < text.Length && text[blanks] is '\r' or '\n')
            {
                int end = text[blanks] == '\r' && blanks + 1 < text.Length && text[blanks + 1] == '\n'
                    ? blanks + 2
                    : blanks + 1;
                Add(folded, '\n', index, end);
                index = end;
                continue;
            }
            for (int last = Math.Max(blanks, index + 1); index < last; index++)
                Add(folded, text[index], index, index + 1);
        }
        return folded;
    }

    private static void Add(Folded folded, char character, int start, int end)
    {
        folded.Text.Append(character);
        folded.Starts.Add(start);
        folded.Ends.Add(end);
    }

    // The line break a text uses most («\r\n», «\n» or «\r»); null when it has none.
    private static string? LineBreakOf(string text)
    {
        int crlf = 0, lf = 0, cr = 0;
        for (int index = 0; index < text.Length; index++)
        {
            if (text[index] == '\n') lf++;
            else if (text[index] != '\r') continue;
            else if (index + 1 < text.Length && text[index + 1] == '\n') { crlf++; index++; }
            else cr++;
        }
        return crlf + lf + cr == 0 ? null : crlf >= lf && crlf >= cr ? "\r\n" : lf >= cr ? "\n" : "\r";
    }

    private static string WithLineBreak(string text, string? lineBreak)
    {
        if (lineBreak is null) return text;
        var written = new StringBuilder(text.Length);
        for (int index = 0; index < text.Length; index++)
        {
            if (text[index] is not ('\r' or '\n'))
            {
                written.Append(text[index]);
                continue;
            }
            if (text[index] == '\r' && index + 1 < text.Length && text[index + 1] == '\n') index++;
            written.Append(lineBreak);
        }
        return written.ToString();
    }
}
