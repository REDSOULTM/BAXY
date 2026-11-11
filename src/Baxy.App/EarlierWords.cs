using System.Globalization;
using System.IO;
using System.Text.Json;
using Baxy.Providers.Windows.Capture;

namespace Baxy.App;

/// <summary>
/// PRV2 (decisión A2 del líder, 2026-11-10; INFORME_PRV1 R11 y D1): since PRV1 the product's two turn logs keep no words
/// (the mind's trace, <c>Mind.TRACE_FACTS</c>; <see cref="ConversationLog"/> without <c>text</c>) and the note of a
/// playback that was not verified is not written, unless the PC's owner asked for words to be kept
/// (<c>BAXY_TRACE_WORDS=1</c>). A PC that updates kept what an earlier version wrote in them with the person's words, up
/// to ~108 MB: the mind's <c>turns.jsonl</c> and its archive (2 × 50 MB), the App's <c>conversation.v1.jsonl</c> and its
/// archive (2 × 4 MB) and that note. The first start of this version removes those five files, once (a mark in the data
/// root says so), and nothing else: history, memory, alarms and settings are the person's and stay. Where the PC's owner
/// keeps words (the fleet's PCs set the variable on purpose) nothing is removed and the mark is written too, so turning
/// the variable off later removes nothing he kept («sigue ahí hasta que uses Olvidar todo», the policy says); a bench's
/// own trace folder or another profile is not this PC's and is left alone. A file another process holds stays, the start
/// goes on, and the next start takes it.
/// </summary>
internal sealed record EarlierWords(string DataRoot, string TraceDirectory, bool WordsKept = false)
{
    /// <summary>The mark in the data root that the files were removed; from then on nothing is looked at again.</summary>
    internal const string MarkName = "earlier-words-removed.v1";

    /// <summary>The mind's trace (src/baxy_mind/__main__.py, bounded_trace) and its one archive.</summary>
    internal const string TraceName = "turns.jsonl";

    /// <summary>
    /// The product's places: this PC's data root and the mind's trace folder, and whether its owner keeps words. None for
    /// a bench's own trace folder (<c>BAXY_RENEW_TRACE_DIR</c>) or a data root that is not this PC's own (a test's or the
    /// conductor's profile, <c>BAXY_DATA_DIR</c>): the trace folder beside it is still the owner's, and nothing of his is
    /// removed or marked for another profile.
    /// </summary>
    internal static EarlierWords? ForThisPc(Func<string, string?>? environment = null)
    {
        environment ??= Environment.GetEnvironmentVariable;
        return !string.IsNullOrWhiteSpace(environment(MindSidecarClient.TraceDirectoryEnvironmentVariable))
            || !string.IsNullOrWhiteSpace(environment("BAXY_DATA_DIR"))
            ? null
            : new EarlierWords(MemoryOperationProtector.ResolveDataRoot(), MindSidecarClient.TraceDirectory(), KeptHere(environment));
    }

    /// <summary>
    /// Whether this PC keeps the words in those logs: its owner set <c>BAXY_TRACE_WORDS=1</c> (the App's log,
    /// <see cref="ConversationLog.KeepsWords"/>), or a bench gave the mind its own trace folder (src/baxy_mind/__main__.py,
    /// trace_words, reads the same two).
    /// </summary>
    internal static bool KeptHere(Func<string, string?> environment) =>
        ConversationLog.KeepsWords(environment(ConversationLog.WordsEnvironmentVariable))
        || !string.IsNullOrWhiteSpace(environment(MindSidecarClient.TraceDirectoryEnvironmentVariable));

    /// <summary>The five files an earlier version wrote with the person's words, and only them (no pattern).</summary>
    internal IReadOnlyList<string> Files
    {
        get
        {
            string trace = Path.Combine(TraceDirectory, TraceName);
            string log = Path.Combine(DataRoot, "conversation", "conversation.v1.jsonl");
            return
            [
                trace,
                trace + BoundedJsonlFile.ArchiveSuffix,
                log,
                log + BoundedJsonlFile.ArchiveSuffix,
                Path.Combine(DataRoot, "captures", StoredCaptures.PlaybackNotes),
            ];
        }
    }

    /// <summary>What a start did: how many files and bytes went, and whether it is over (the mark is written).</summary>
    internal sealed record Outcome(int Removed, long Bytes, bool Done);

    /// <summary>
    /// Removes the <see cref="Files"/> unless the mark says it was done, or only writes the mark where words are kept; the
    /// mark is written only when none is left. Never throws for a file or a folder Windows refuses: it stays for the next
    /// start.
    /// </summary>
    internal Outcome RemoveOnce()
    {
        string mark = Path.Combine(DataRoot, MarkName);
        if (File.Exists(mark))
        {
            return new Outcome(0, 0, Done: true);
        }

        int removed = 0;
        long bytes = 0;
        bool left = false;
        foreach (string path in WordsKept ? [] : Files)
        {
            try
            {
                var file = new FileInfo(path);
                if (!file.Exists)
                {
                    continue;
                }

                long length = file.Length;
                file.Delete();
                removed++;
                bytes += length;
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                left = true;  // held open this moment (Windows refuses to delete it): the next start takes it
            }
        }

        if (!left)
        {
            try
            {
                Directory.CreateDirectory(DataRoot);
                File.WriteAllText(mark, JsonSerializer.Serialize(new Dictionary<string, object>
                {
                    ["utc"] = DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
                    ["removed"] = removed,
                    ["bytes"] = bytes,
                    ["kept"] = WordsKept,
                }) + Environment.NewLine);
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                left = true;  // the files are gone; the next start finds none and writes the mark
            }
        }

        return new Outcome(removed, bytes, Done: !left);
    }
}
