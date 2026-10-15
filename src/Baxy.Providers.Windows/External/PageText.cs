using System.Text.RegularExpressions;

namespace Baxy.Providers.Windows.External;

// web.fetch: a page's title and its readable text, without what a reader skips (the head, scripts, styles, menus,
// headers, footers and forms). Nothing of the page is chosen or left out by what it says.
internal static class PageText
{
    private static readonly TimeSpan RegexBudget = TimeSpan.FromSeconds(2);

    private static readonly Regex Unread = new(
        @"<!--.*?-->|<(head|script|style|noscript|svg|nav|header|footer|aside|form|template|iframe|button|select)\b.*?</\1\s*>",
        RegexOptions.Singleline | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, RegexBudget);

    private static readonly Regex Block = new(
        @"</?(?:p|li|h[1-6]|br|div|tr|td|th|dd|dt|blockquote|section|article|main|ul|ol|table|figcaption)\b[^>]*>",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant, RegexBudget);

    private static readonly Regex Tag = new("<[^>]*>", RegexOptions.CultureInvariant, RegexBudget);

    private static readonly Regex Title = new(
        @"<title\b[^>]*>(.*?)</title\s*>", RegexOptions.Singleline | RegexOptions.IgnoreCase | RegexOptions.CultureInvariant,
        RegexBudget);

    // The page's title and readable text, one block per line, cut at maximumCharacters.
    internal static (string Title, string Text, bool Truncated) Prose(string html, int maximumCharacters)
    {
        Match title = Title.Match(html);
        string prose = System.Net.WebUtility.HtmlDecode(Tag.Replace(Block.Replace(Unread.Replace(html, " "), "\n"), " "));
        string text = string.Join('\n', prose.Split('\n')
            .Select(static line => string.Join(' ', line.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries)))
            .Where(static line => line.Length > 0));
        return (title.Success ? Text(title.Groups[1].Value) : string.Empty,
            text.Length <= maximumCharacters ? text : text[..maximumCharacters],
            text.Length > maximumCharacters);
    }

    private static string Text(string html) =>
        string.Join(' ', System.Net.WebUtility.HtmlDecode(Tag.Replace(html, " "))
            .Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
}
