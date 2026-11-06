using System.Text;

namespace Baxy.Providers.Windows.External;

/// <summary>A piece of a page in document order: a link (with its address) or a text; its depth in the page's tree; the
/// index of the piece it lies under (-1: none); the shallowest depth walked since the piece before, which says a
/// container was left; whether a blank came before it; and where it lies on screen.</summary>
internal sealed record PageNode(bool IsLink, string Name, string Address, int Depth, int Under, int Rise, bool Gap, double Top, double Bottom);

/// <summary>One item of a page's list of linked items: its title, its link, and the text that goes with it.</summary>
internal sealed record PageBlock(string Title, string Address, string Text);

/// <summary>
/// Auditoría 04-11 (P3, 16 of 63 falsedades): a page of results read as one text gives titles, sites and snippets one
/// after the other with nothing that says where one result ends, and the model joined pieces of neighbours («según
/// Wikipedia… en 1938», a year only another result had). A text marked by what it belongs to is what lets a model keep a
/// fact with its source: ALCE (Gao et al., 2023, arXiv 2305.14627) measured it for citations, as web.search's typed
/// results do here. The items are told by the page's structure only, never by what its text says: a title that holds
/// its link or lies in it, or a link alone on its line, followed by its text inside the same container. A page that is
/// not mostly such a list (an article, whose links are inside its sentences) has no blocks and is read as before.
/// </summary>
internal static class PageBlocks
{
    /// <summary>Fewer than this is no list: one linked heading in an article is just that.</summary>
    private const int MinimumBlocks = 2;

    /// <summary>An item's text longer than this is an article's, not the text of an item of a list.</summary>
    private const int MaximumBlockText = 1_200;

    /// <summary>An item with more links to elsewhere than this is a stretch of the page (a menu, the rows of a table),
    /// not one item.</summary>
    private const int MaximumOtherLinks = 2;

    /// <summary>A link past this is no address the model could use or say (a redirect's wrapper): its text says the site.</summary>
    private const int MaximumAddress = 200;

    /// <summary>The list must be at least this share of the page's text: a few captions in an article are no list.</summary>
    private const double MinimumShareOfPage = 0.4;

    /// <summary>What each block adds to the receipt's JSON ({"title":"","url":"","text":""},): it is in the 8 KiB too.</summary>
    internal const int BlockOverhead = 32;

    /// <summary>How far ahead a block's piece may lie from the one before it in the page's text.</summary>
    private const int MaximumGap = 1_500;

    private sealed class Open(string title, string address, int depth, bool titled)
    {
        public string Title { get; } = title;
        public bool Titled { get; } = titled;
        public string Address { get; } = address;
        public int Depth { get; } = depth;
        public List<string> Pieces { get; } = [];
        public int OtherLinks { get; set; }

        /// <summary>A piece on the same line as the one before continues it (a word marked inside a sentence comes as a
        /// node of its own); on another line, it is a line of its own.</summary>
        public void Add(PageNode node, PageNode? before)
        {
            if (Pieces.Count > 0 && before is not null && node.Top < before.Bottom - 1 && node.Bottom > before.Top + 1)
                Pieces[^1] += (node.Gap ? " " : string.Empty) + node.Name;
            else
                Pieces.Add(node.Name);
        }
    }

    /// <summary>The blocks of the page, within <paramref name="maximumCharacters"/> of their text, or an empty list when
    /// the page is not mostly a list of linked items. <paramref name="cut"/> says some were left out for the budget.</summary>
    internal static IReadOnlyList<PageBlock> Read(
        IReadOnlyList<PageNode>? nodes, int textLength, int maximumCharacters, out bool cut)
    {
        cut = false;
        if (nodes is not { Count: > 0 })
            return [];
        List<Open> items = [.. Items(nodes).Where(static item => item.Pieces.Count > 0 && item.OtherLinks <= MaximumOtherLinks)];
        // A list's items have one form: where they have a title, a bare link with text after it (a logo over the intro) is none.
        if (items.Count(static item => item.Titled) >= MinimumBlocks)
            items.RemoveAll(static item => !item.Titled);
        if (items.Count < MinimumBlocks || items.Any(static item => item.Pieces.Sum(static piece => piece.Length) > MaximumBlockText))
            return [];
        // Against what the page holds, not the text already cut to the budget: an article's cards are no list.
        int pageLength = Math.Max(textLength, nodes.Where(static node => node.Under < 0).Sum(static node => node.Name.Length));
        if (items.Sum(static item => item.Title.Length + item.Pieces.Sum(static piece => piece.Length)) < MinimumShareOfPage * pageLength)
            return [];
        var blocks = new List<PageBlock>();
        int used = 0;
        foreach (Open item in items)
        {
            string text = string.Join("\n", item.Pieces.Select(static piece => piece.Trim()));
            string address = item.Address.Length <= MaximumAddress ? item.Address : string.Empty;
            int size = item.Title.Length + address.Length + text.Length + BlockOverhead;
            if (used + size > maximumCharacters)
            {
                cut = true;
                break;
            }
            used += size;
            blocks.Add(new PageBlock(item.Title, address, text));
        }
        if (blocks.Count >= MinimumBlocks)
            return blocks;
        cut = false;
        return [];
    }

    private static List<Open> Items(IReadOnlyList<PageNode> nodes)
    {
        var found = new List<Open>();
        Open? open = null;
        for (int index = 0; index < nodes.Count; index++)
        {
            PageNode node = nodes[index];
            if (open is not null && node.Rise < open.Depth)
                open = null;
            PageNode? inside = index + 1 < nodes.Count && nodes[index + 1].Under == index ? nodes[index + 1] : null;
            if (inside is not null && node.IsLink != inside.IsLink && AloneOnItsLine(nodes, index, index + 2))
            {
                // A text that holds a link (a heading) or a link that holds a text: the item's title and its address.
                PageNode link = node.IsLink ? node : inside;
                PageNode title = node.IsLink ? inside : node;
                open = Start(found, title.Name, link.Address, node.Depth, titled: true);
                string rest = Remainder(link.Name, title.Name);
                if (rest.Length > 0)
                    open.Pieces.Add(rest);
                index++;
                continue;
            }
            if (node.IsLink)
            {
                if (open is not null && open.Address.Length > 0 && string.Equals(open.Address, node.Address, StringComparison.Ordinal))
                {
                    open.Add(node, index > 0 ? nodes[index - 1] : null);
                    continue;
                }
                if (node.Address.Length > 0 && AloneOnItsLine(nodes, index, index + 1))
                {
                    open = Start(found, node.Name, node.Address, node.Depth, titled: false);
                    continue;
                }
                if (open is not null)
                    open.OtherLinks++;
            }
            open?.Add(node, index > 0 ? nodes[index - 1] : null);
        }
        return found;
    }

    /// <summary>The page's text without what the blocks hold, piece by piece, within the budget the blocks left: what lies
    /// around and between them stays. A piece not found in it (a text read another way) just stays.</summary>
    internal static string TextOutside(string text, IReadOnlyList<PageBlock> blocks, int budget, out bool cut)
    {
        var outside = new StringBuilder();
        int from = 0;
        foreach (PageBlock block in blocks)
        {
            // By their place in the page, the nearest first: a site comes over its title, and a short piece («Historia») may
            // be said again later. Only near: a piece found far ahead is another's.
            List<string> pieces = [.. block.Text.Split('\n').Prepend(block.Title).Where(static piece => piece.Length > 0)];
            while (pieces.Count > 0)
            {
                int start = from;
                (int At, string Piece)[] near = [.. pieces
                    .Select(piece => (At: text.IndexOf(piece, start, StringComparison.Ordinal), Piece: piece))
                    .Where(found => found.At >= 0 && found.At - start <= MaximumGap)
                    .OrderBy(static found => found.At)];
                if (near.Length == 0)
                    break;
                outside.Append(text, from, near[0].At - from);
                from = near[0].At + near[0].Piece.Length;
                pieces.Remove(near[0].Piece);
            }
        }
        outside.Append(text, from, text.Length - from);
        string kept = string.Join("\n", outside.ToString().Split('\n').Select(static line => line.Trim())
            .Where(static line => line.Length > 0));
        int room = Math.Max(budget, 0);
        cut = kept.Length > room;
        return cut ? kept[..room] : kept;
    }

    /// <summary>What a page's text holds for each embedded object (an image, a frame) is one mark on a line, with nothing
    /// to read: a page of icons spent its budget on them.</summary>
    internal static string WithoutObjectMarks(string text) =>
        !text.Contains('￼', StringComparison.Ordinal)
            ? text
            : string.Join("\n", text.Split('\n').Select(static line => line.Replace("￼", string.Empty, StringComparison.Ordinal))
                .Where(static line => line.Trim().Length > 0));

    private static Open Start(List<Open> found, string title, string address, int depth, bool titled)
    {
        var item = new Open(title.Trim(), address, depth, titled);
        // A link to the same address just before, with nothing of its own, is this item's too (the site over its title).
        if (found is [.., { Pieces.Count: 0 } before] && address.Length > 0 && string.Equals(before.Address, address, StringComparison.Ordinal))
        {
            found.RemoveAt(found.Count - 1);
            item.Pieces.Add(before.Title);
        }
        found.Add(item);
        return item;
    }

    /// <summary>A link's name holds its title and what else it shows (the site): that else.</summary>
    private static string Remainder(string name, string title)
    {
        int at = name.IndexOf(title, StringComparison.Ordinal);
        return (at < 0 ? string.Empty : name.Remove(at, title.Length)).Trim();
    }

    /// <summary>Whether nothing before or after the link shares its line: a link inside a sentence or in a row of a menu
    /// does not stand alone. A node inside a text's box is on that text's lines.</summary>
    private static bool AloneOnItsLine(IReadOnlyList<PageNode> nodes, int index, int after)
    {
        PageNode link = nodes[index];
        bool Shares(PageNode other) => other.Top < link.Bottom - 1 && other.Bottom > link.Top + 1;
        return (index == 0 || !Shares(nodes[index - 1])) && (after >= nodes.Count || !Shares(nodes[after]));
    }
}
