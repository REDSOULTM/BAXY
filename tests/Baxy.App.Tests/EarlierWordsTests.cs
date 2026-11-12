using System.IO;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// PRV2 (decisión A2, 2026-11-10): a PC that updates kept, in clear text, what an earlier version wrote in the turn logs
/// with the person's words (INFORME_PRV1 R11). The first start of this version removes those files and nothing else,
/// once; where words are kept on purpose nothing goes; a file held open stays and the next start takes it.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class EarlierWordsTests
{
    private string _folder = string.Empty;

    [SetUp]
    public void SetUp()
    {
        _folder = Path.Combine(Path.GetTempPath(), "baxy-app-tests", "earlier-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_folder);
    }

    [TearDown]
    public void TearDown()
    {
        try
        {
            Directory.Delete(_folder, recursive: true);
        }
        catch (IOException)
        {
            // A reader of this test still holds a file a moment: the temporary folder is left.
        }
    }

    [Test]
    public void TheFirstStartRemovesWhatAnEarlierVersionWroteWithWordsAndNothingElse()
    {
        (EarlierWords earlier, string[] words, string[] kept) = AnUpdatedPc();
        long bytes = words.Sum(file => new FileInfo(file).Length);

        EarlierWords.Outcome outcome = earlier.RemoveOnce();

        Assert.Multiple(() =>
        {
            foreach (string file in words)
            {
                Assert.That(File.Exists(file), Is.False, Path.GetFileName(file) + " stayed");
            }

            foreach (string file in kept)
            {
                Assert.That(File.Exists(file), Is.True, Path.GetFileName(file) + " is the person's and went");
            }

            Assert.That(outcome, Is.EqualTo(new EarlierWords.Outcome(5, bytes, Done: true)));
            Assert.That(File.Exists(Path.Combine(earlier.DataRoot, EarlierWords.MarkName)), Is.True, "no mark");
        });
    }

    [Test]
    public void ItHappensOnceWhatIsWrittenAfterwardsStays()
    {
        (EarlierWords earlier, string[] words, _) = AnUpdatedPc();
        Assert.That(earlier.RemoveOnce().Done, Is.True);
        // This version writes the logs again, without words (or with them, where the owner asked later).
        string trace = words[0];
        File.WriteAllText(trace, "{\"stage\":\"turn.decide\",\"ms\":812}\n");

        Assert.That(earlier.RemoveOnce(), Is.EqualTo(new EarlierWords.Outcome(0, 0, Done: true)));
        Assert.That(File.Exists(trace), Is.True, "a later start removed this version's trace");
    }

    [Test]
    public void AFileHeldOpenStaysTheStartGoesOnAndTheNextStartTakesIt()
    {
        (EarlierWords earlier, string[] words, _) = AnUpdatedPc();
        string held = words[2];  // conversation.v1.jsonl
        EarlierWords.Outcome first;
        using (new FileStream(held, FileMode.Open, FileAccess.Read, FileShare.Read))
        {
            first = earlier.RemoveOnce();
        }

        Assert.Multiple(() =>
        {
            Assert.That(first.Done, Is.False);
            Assert.That(first.Removed, Is.EqualTo(4));
            Assert.That(File.Exists(held), Is.True);
            Assert.That(File.Exists(Path.Combine(earlier.DataRoot, EarlierWords.MarkName)), Is.False, "marked with a file left");
        });

        EarlierWords.Outcome next = earlier.RemoveOnce();
        Assert.That(next.Removed, Is.EqualTo(1));
        Assert.That(next.Done, Is.True);
        Assert.That(File.Exists(held), Is.False);
    }

    [TestCase("BAXY_TRACE_WORDS", "1", true)]
    [TestCase("BAXY_TRACE_WORDS", " 1 ", true)]
    [TestCase("BAXY_TRACE_WORDS", "true", true)]
    [TestCase("BAXY_TRACE_WORDS", "TRUE", true)]
    [TestCase("BAXY_TRACE_WORDS", "yes", true)]
    [TestCase("BAXY_TRACE_WORDS", "on", true)]
    [TestCase("BAXY_RENEW_TRACE_DIR", @"C:\banco\corrida", true)]
    [TestCase("BAXY_TRACE_WORDS", "0", false)]
    [TestCase("BAXY_TRACE_WORDS", "false", false)]
    [TestCase("BAXY_TRACE_WORDS", "no", false)]
    [TestCase("BAXY_TRACE_WORDS", "", false)]
    public void WhereWordsAreKeptOnPurposeTheyAreRecognized(string variable, string value, bool kept)
    {
        Func<string, string?> environment = name => name == variable ? value : null;

        Assert.That(EarlierWords.KeptHere(environment), Is.EqualTo(kept));
    }

    [Test]
    public void WhereTheOwnerKeepsWordsNothingGoesNowNorWhenHeTurnsItOffLater()
    {
        (EarlierWords earlier, string[] words, string[] kept) = AnUpdatedPc();

        Assert.That((earlier with { WordsKept = true }).RemoveOnce(),Is.EqualTo(new EarlierWords.Outcome(0, 0, Done: true)));
        // Revisión a ciegas de PRV2: without the mark, turning the variable off later removed what he asked to keep.
        Assert.That(earlier.RemoveOnce(), Is.EqualTo(new EarlierWords.Outcome(0, 0, Done: true)));
        Assert.That(words.Concat(kept).Where(file => !File.Exists(file)), Is.Empty);
    }

    // UNI1 (REV8 P2): a file Windows does not let go stayed for ever, and every start removed the others again, which by
    // then were this version's new logs without words. A read-only one goes; what is left is retried alone.
    [Test]
    public void AReadOnlyFileGoesToo()
    {
        (EarlierWords earlier, string[] words, _) = AnUpdatedPc();
        File.SetAttributes(words[0], FileAttributes.ReadOnly);

        Assert.That(earlier.RemoveOnce().Done, Is.True);
        Assert.That(File.Exists(words[0]), Is.False);
    }

    [Test]
    public void WhatWasLeftIsRetriedAloneAndTheNewLogsStay()
    {
        (EarlierWords earlier, string[] words, _) = AnUpdatedPc();
        string held = words[2];  // conversation.v1.jsonl
        EarlierWords.Outcome first;
        using (new FileStream(held, FileMode.Open, FileAccess.Read, FileShare.Read))
        {
            first = earlier.RemoveOnce();
        }

        // This version writes its trace again, without words, before the next start.
        File.WriteAllText(words[0], "{\"stage\":\"turn.decide\",\"ms\":812}\n");
        EarlierWords.Outcome next = earlier.RemoveOnce();

        Assert.Multiple(() =>
        {
            Assert.That(first, Is.EqualTo(new EarlierWords.Outcome(4, first.Bytes, Done: false, Left: 1)), "the trace says one is left");
            Assert.That(next, Is.EqualTo(new EarlierWords.Outcome(1, next.Bytes, Done: true)));
            Assert.That(File.Exists(held), Is.False);
            Assert.That(File.Exists(words[0]), Is.True, "the next start removed this version's new trace");
        });
    }

    // What is left is written in the data folder, where any program of the person's writes: only the five files are taken.
    [Test]
    public void TheListOfWhatWasLeftNamesNothingButTheFiveFiles()
    {
        (EarlierWords earlier, _, string[] kept) = AnUpdatedPc();
        File.WriteAllText(Path.Combine(earlier.DataRoot, EarlierWords.PendingName), "[\"" + kept[1].Replace("\\", "\\\\") + "\"]");

        earlier.RemoveOnce();

        Assert.That(kept.Where(file => !File.Exists(file)), Is.Empty);
    }

    // Independent review of UNI1: a list that names none of the five (an empty one) is not a start that left nothing.
    [Test]
    public void AListThatNamesNoneOfTheFiveLooksAtTheFive()
    {
        (EarlierWords earlier, string[] words, _) = AnUpdatedPc();
        File.WriteAllText(Path.Combine(earlier.DataRoot, EarlierWords.PendingName), "[]");

        Assert.That(earlier.RemoveOnce().Removed, Is.EqualTo(5));
        Assert.That(words.Where(File.Exists), Is.Empty);
    }

    [Test]
    public void ABenchsOwnTraceFolderIsNotThisPcs()
    {
        Func<string, string?> environment = name => name == "BAXY_RENEW_TRACE_DIR" ? _folder : null;

        Assert.That(EarlierWords.ForThisPc(environment), Is.Null);
    }

    [Test]
    public void AProfileThatIsNotThisPcsOwnRemovesNothingOfTheOwners()
    {
        // A test's or the conductor's profile (BAXY_DATA_DIR): the mind's trace folder is still the owner's.
        Func<string, string?> environment = name => name == "BAXY_DATA_DIR" ? _folder : null;

        Assert.That(EarlierWords.ForThisPc(environment), Is.Null);
    }

    [Test]
    public async Task TheMindsStartRemovesThemBeforeItWritesItsTrace()
    {
        using var fake = new FakeMind();
        (EarlierWords earlier, string[] words, string[] kept) = AnUpdatedPc();
        var viewModel = new MainWindowViewModel { Sound = static _ => { }, WordsOfEarlierVersions = earlier };
        await using (viewModel)
        {
            await ViewModelHarness.StartMindAsync(viewModel);

            Assert.That(viewModel.IsMindReady, Is.True);
            Assert.That(words.Where(File.Exists), Is.Empty);
            Assert.That(kept.Where(file => !File.Exists(file)), Is.Empty);
        }
    }

    // A data folder as a PC that updates has it: the five files written with words, and what is the person's beside them
    // (a kept conversation, memory, an alarm, the settings) and the logs that never held words.
    private (EarlierWords Earlier, string[] Words, string[] Kept) AnUpdatedPc()
    {
        string root = Path.Combine(_folder, "BAXY", "1");
        string renew = Path.Combine(_folder, "BAXY", "renew");
        var earlier = new EarlierWords(root, renew);
        string[] words =
        [
            Path.Combine(renew, "turns.jsonl"),
            Path.Combine(renew, "turns.jsonl.1"),
            Path.Combine(root, "conversation", "conversation.v1.jsonl"),
            Path.Combine(root, "conversation", "conversation.v1.jsonl.1"),
            Path.Combine(root, "captures", "streaming-playback-rejections.jsonl"),
        ];
        string[] kept =
        [
            Path.Combine(root, "sessions", "sesion-1.json"),
            Path.Combine(root, "memory", "memory.db"),
            Path.Combine(root, "alarms", "alarma-1.json"),
            Path.Combine(root, "settings.json"),
            Path.Combine(root, "conversation", "notas.jsonl"),
            Path.Combine(root, "diagnostics", "unhandled.v1.jsonl"),
            Path.Combine(renew, "llama-server.log"),
            Path.Combine(renew, "catalog.configure.json"),
            Path.Combine(renew, "turns.jsonl.2"),
        ];
        Assert.That(earlier.Files, Is.EquivalentTo(words));
        foreach (string file in words.Concat(kept))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(file)!);
            File.WriteAllText(file, "{\"text\":\"mi clave es tulipán\"}\n");
        }

        return (earlier, words, kept);
    }
}
