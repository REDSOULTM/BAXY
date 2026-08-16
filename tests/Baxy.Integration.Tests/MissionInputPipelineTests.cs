using System.Globalization;
using System.Text;
using System.Xml.Linq;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class MissionInputPipelineTests
{
    [TestCase(
        "es",
        "Pon el volumen del PC al 20%",
        "audio.volume",
        OperationRisks.LowReversible,
        PolicyDecision.Allow)]
    [TestCase(
        "en",
        "open Notepad",
        "app.open",
        OperationRisks.LowReversible,
        PolicyDecision.Allow)]
    [TestCase(
        "pt-settings",
        "abre as configurações do Windows",
        "app.open",
        OperationRisks.LowReversible,
        PolicyDecision.Allow)]
    [TestCase(
        "en-verified-steam",
        "open steam but don't say it's done if you can't verify it",
        "app.open",
        OperationRisks.LowReversible,
        PolicyDecision.Allow)]
    [TestCase(
        "spanglish",
        "show me el volumen",
        "audio.status",
        OperationRisks.ReadOnly,
        PolicyDecision.Allow)]
    [TestCase(
        "es-confirmacion",
        "activa la memoria",
        "memory.enable",
        OperationRisks.PrivacySensitive,
        PolicyDecision.RequireConfirmation)]
    [TestCase(
        "en-confirmation",
        "forget my favorite color",
        "memory.forget",
        OperationRisks.WorkLoss,
        PolicyDecision.RequireConfirmation)]
    [TestCase(
        "spanglish-memory",
        "recuerda que I prefer dark mode",
        "memory.save",
        OperationRisks.LowReversible,
        PolicyDecision.Allow)]
    public async Task TextAndVoiceTranscriptDispatchTheSameIntentRiskAndConfirmation(
        string language,
        string text,
        string expectedOperation,
        string expectedRisk,
        PolicyDecision expectedConfirmation)
    {
        List<MissionInputRoute> dispatched = [];
        using var cancellation = new CancellationTokenSource();

        foreach (MissionInputSource source in Enum.GetValues<MissionInputSource>())
        {
            await MissionInputPipeline.DispatchAsync(
                new MissionInput(text, source),
                (route, token) =>
                {
                    Assert.That(token, Is.EqualTo(cancellation.Token), language);
                    dispatched.Add(route);
                    return Task.CompletedTask;
                },
                cancellation.Token);
        }

        Assert.Multiple(() =>
        {
            Assert.That(
                Enum.GetValues<MissionInputSource>(),
                Is.EqualTo(new[]
                {
                    MissionInputSource.Text,
                    MissionInputSource.VoiceTranscript,
                }));
            Assert.That(dispatched, Has.Count.EqualTo(2), language);
            Assert.That(dispatched[0].Source, Is.EqualTo(MissionInputSource.Text), language);
            Assert.That(
                dispatched[1].Source,
                Is.EqualTo(MissionInputSource.VoiceTranscript),
                language);
            Assert.That(CaptureDecision(dispatched[1]), Is.EqualTo(CaptureDecision(dispatched[0])));
            Assert.That(
                dispatched[0].OperationContract?.Name,
                Is.EqualTo(expectedOperation),
                language);
            Assert.That(
                dispatched[0].OperationContract?.Risk,
                Is.EqualTo(expectedRisk),
                language);
            Assert.That(
                dispatched[0].OperationContract?.ConfirmationPolicy,
                Is.EqualTo(expectedConfirmation),
                language);
        });
    }

    [TestCase("RECUERDA que my favorite color is verde!!!; abre Spotify")]
    [TestCase("WHAT'S MY FAVORITE COLOR?; abre Spotify")]
    [TestCase("lista mi memoria; abre Spotify")]
    [TestCase("tienes memoria; abre Spotify")]
    [TestCase("activa la memoria; abre Spotify")]
    [TestCase("desactiva la memoria; abre Spotify")]
    [TestCase("exporta mi memoria; abre Spotify")]
    [TestCase("forget my favorite color; open Spotify")]
    [TestCase("Remember that my name is Zoë.; open Spotify")]
    [TestCase("remember that I prefer short responses; play Billie Jean on Spotify")]
    [TestCase("abre Spotify, y lista mi memoria")]
    [TestCase("open Spotify, and list my memories")]
    [TestCase("Qu'est-ce que tu peux faire pour moi ? comment je m'appelle")]
    [TestCase("Que puedes hacer por mi? como me llamo")]
    public void PrivateAndPublicClausesComposeWithoutExposingMemoryToThePlanner(string text)
    {
        MissionInputRoute route = MissionInputPipeline.Route(
            new MissionInput(text, MissionInputSource.Text));

        Assert.Multiple(() =>
        {
            Assert.That(route.HasPrivatePublicComposition, Is.True, text);
            Assert.That(route.PublicObjective, Is.Not.Null.And.Not.Empty, text);
            Assert.That(route.Memory.Operation, Is.Not.Null, text);
            Assert.That(route.PublicObjective, Does.Not.Contain("memoria").IgnoreCase, text);
            Assert.That(route.PublicObjective, Does.Not.Contain("memory").IgnoreCase, text);
            Assert.That(route.PublicObjective, Does.Not.Contain("verde").IgnoreCase, text);
            Assert.That(route.PublicObjective, Does.Not.Contain("Zoë").IgnoreCase, text);
        });
    }

    [Test]
    public void BareConjunctionInsidePrivateValueIsNeverSplit()
    {
        MissionInputRoute route = MissionInputPipeline.Route(
            new MissionInput(
                "recuerda que mi color favorito es verde y azul",
                MissionInputSource.Text));

        Assert.Multiple(() =>
        {
            Assert.That(route.HasPrivatePublicComposition, Is.False);
            Assert.That(route.PublicObjective, Is.Null);
            Assert.That(route.Memory.Outcome, Is.EqualTo(MemoryParseOutcome.Route));
            Assert.That(
                route.Memory.Operation?.PrivateArguments["value"]?.GetValue<string>(),
                Is.EqualTo("verde y azul"));
        });
    }

    [TestCaseSource(nameof(RejectedTextCases))]
    public void EmptyNullMalformedAndOversizedInputsNeverReachExecution(
        string? text,
        string expectedReason)
    {
        int executions = 0;
        foreach (MissionInputSource source in Enum.GetValues<MissionInputSource>())
        {
            MissionInputRejectedException? exception = Assert.ThrowsAsync<
                MissionInputRejectedException>(async () =>
                    await MissionInputPipeline.DispatchAsync(
                        new MissionInput(text!, source),
                        (_, _) =>
                        {
                            executions++;
                            return Task.CompletedTask;
                        },
                        CancellationToken.None));

            Assert.That(exception?.Reason.ToString(), Is.EqualTo(expectedReason), source.ToString());
        }

        Assert.That(executions, Is.Zero);
    }

    [Test]
    public void UnsupportedSourceIsRejectedBeforeRoutingOrExecution()
    {
        int executions = 0;
        MissionInputRejectedException? exception = Assert.ThrowsAsync<
            MissionInputRejectedException>(async () =>
                await MissionInputPipeline.DispatchAsync(
                    new MissionInput("open Notepad", (MissionInputSource)99),
                    (_, _) =>
                    {
                        executions++;
                        return Task.CompletedTask;
                    },
                    CancellationToken.None));

        Assert.Multiple(() =>
        {
            Assert.That(
                exception?.Reason,
                Is.EqualTo(MissionInputRejectionReason.UnsupportedSource));
            Assert.That(executions, Is.Zero);
        });
    }

    [TestCase("Text")]
    [TestCase("VoiceTranscript")]
    public void InputStringProjectionNeverExposesMissionText(string sourceName)
    {
        MissionInputSource source = Enum.Parse<MissionInputSource>(sourceName);
        const string canary = "BAXY-PRIVATE-CANARY-7f2d8d";
        MissionInput input = new(canary, source);

        string projection = input.ToString();

        Assert.Multiple(() =>
        {
            Assert.That(projection, Does.Contain(sourceName));
            Assert.That(projection, Does.Contain("[REDACTED]"));
            Assert.That(projection, Does.Not.Contain(canary));
        });
    }

    [Test]
    public async Task ExactComposerBoundaryAllowsMultibyteTextForBothSources()
    {
        string text = new('\u00e1', MissionInputContract.MaximumCharacters);
        List<MissionInputRoute> dispatched = [];

        await MissionInputPipeline.DispatchAsync(
            new MissionInput(text, MissionInputSource.Text),
            (route, _) =>
            {
                dispatched.Add(route);
                return Task.CompletedTask;
            },
            CancellationToken.None);
        await MissionInputPipeline.DispatchAsync(
            new MissionInput(text, MissionInputSource.VoiceTranscript),
            (route, _) =>
            {
                dispatched.Add(route);
                return Task.CompletedTask;
            },
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(dispatched, Has.Count.EqualTo(2));
            Assert.That(dispatched, Has.All.Matches<MissionInputRoute>(route =>
                route.Text.Length == MissionInputContract.MaximumCharacters));
            Assert.That(
                Encoding.UTF8.GetByteCount(text),
                Is.GreaterThan(MissionInputContract.MaximumCharacters));
            Assert.That(CaptureDecision(dispatched[1]), Is.EqualTo(CaptureDecision(dispatched[0])));
        });
    }

    [Test]
    public void CharacterLimitMatchesTheRecoveredComposerBridgeAndFitsTheNoteContract()
    {
        string bridge = File.ReadAllText(
            RepositoryPath("src", "Baxy.App", "Assets", "field-native-bridge.js"));
        OperationArgumentProperty noteContent = ProductCatalog
            .GetRequired("note.create")
            .ArgumentsSchema
            .Properties
            .Single(property => property.Name == "content");
        int noteMaximumUtf8Bytes = noteContent.MaximumUtf8Bytes
            ?? throw new AssertionException("note.create content has no UTF-8 limit.");

        Assert.Multiple(() =>
        {
            Assert.That(
                bridge,
                Does.Contain($"composer.maxLength = {MissionInputContract.MaximumCharacters}"));
            Assert.That(noteMaximumUtf8Bytes, Is.EqualTo(65_536));
            Assert.That(
                MissionInputContract.MaximumCharacters * 4,
                Is.LessThanOrEqualTo(noteMaximumUtf8Bytes));
        });
    }

    [Test]
    public void LanguageRoutingRegexesStayInsideTheDeclaredInterimParserLayer()
    {
        string appRoot = RepositoryPath("src", "Baxy.App");
        string[] expectedParserFiles =
        [
            "MemoryOperationProtection.cs",
            "NaturalApplicationRequestParser.cs",
            "NaturalAudioRequestParser.cs",
            "NaturalMemoryRequestParser.cs",
            "NaturalNoteRequestParser.cs",
            "NaturalSystemStatusRequestParser.cs",
            "NoteDisambiguation.cs",
        ];
        string[] actualRegexFiles = Directory
            .EnumerateFiles(appRoot, "*.cs", SearchOption.TopDirectoryOnly)
            .Where(path => File.ReadAllText(path).Contains(
                "[GeneratedRegex(",
                StringComparison.Ordinal))
            .Select(static path => Path.GetFileName(path)
                ?? throw new InvalidOperationException("A parser source path has no file name."))
            .Order(StringComparer.Ordinal)
            .ToArray();

        Assert.That(actualRegexFiles, Is.EqualTo(expectedParserFiles));
    }

    [Test]
    public async Task RejectedGuiDraftIsPreservedAndGetsSafeDeterministicGuidance()
    {
        string root = PrivateDataRootTestSupport.NewPath("mission-input-rejection");
        string? previousDataRoot = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        Environment.SetEnvironmentVariable("BAXY_DATA_DIR", root);
        const string rejectedDraft = "open\0Notepad";

        try
        {
            await using var viewModel = new MainWindowViewModel();
            await viewModel.InitializeAsync(CancellationToken.None);
            int previousMessages = viewModel.Messages.Count;
            viewModel.Draft = rejectedDraft;

            Assert.That(viewModel.CanSend, Is.True);
            await viewModel.SubmitAsync(CancellationToken.None);

            ConversationMessage[] added = viewModel.Messages.Skip(previousMessages).ToArray();
            Assert.Multiple(() =>
            {
                Assert.That(viewModel.Draft, Is.EqualTo(rejectedDraft));
                Assert.That(added, Has.Length.EqualTo(1));
                Assert.That(added[0].IsUser, Is.False);
                Assert.That(added[0].Speaker, Is.EqualTo("BAXY"));
                Assert.That(added[0].Body, Is.EqualTo(MissionInputContract.SafeRejectionGuidance));
                Assert.That(added[0].Body, Does.Not.Contain(rejectedDraft));
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_DATA_DIR", previousDataRoot);
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    private static IEnumerable<TestCaseData> RejectedTextCases()
    {
        yield return new TestCaseData(null, nameof(MissionInputRejectionReason.Empty))
            .SetName("MissionInput_RejectsNullTextForEverySource");
        yield return new TestCaseData(string.Empty, nameof(MissionInputRejectionReason.Empty))
            .SetName("MissionInput_RejectsEmptyTextForEverySource");
        yield return new TestCaseData(" \t ", nameof(MissionInputRejectionReason.Empty))
            .SetName("MissionInput_RejectsWhitespaceForEverySource");
        yield return new TestCaseData(
                "open\0Notepad",
                nameof(MissionInputRejectionReason.ContainsNull))
            .SetName("MissionInput_RejectsNulForEverySource");
        yield return new TestCaseData(
                string.Concat("open Notepad", '\ud800'),
                nameof(MissionInputRejectionReason.MalformedUtf16))
            .SetName("MissionInput_RejectsMalformedUtf16ForEverySource");
        yield return new TestCaseData(
                new string('a', MissionInputContract.MaximumCharacters + 1),
                nameof(MissionInputRejectionReason.TooLarge))
            .SetName("MissionInput_RejectsOversizedCharactersForEverySource");
        yield return new TestCaseData(
                new string('\u00e1', MissionInputContract.MaximumCharacters + 1),
                nameof(MissionInputRejectionReason.TooLarge))
            .SetName("MissionInput_RejectsOversizedMultibyteTextForEverySource");
        yield return new TestCaseData(
                new string(' ', MissionInputContract.MaximumCharacters) + "open Notepad",
                nameof(MissionInputRejectionReason.TooLarge))
            .SetName("MissionInput_RejectsOversizedLeadingWhitespaceBeforeTrim");
        yield return new TestCaseData(
                "open Notepad" + new string(' ', MissionInputContract.MaximumCharacters),
                nameof(MissionInputRejectionReason.TooLarge))
            .SetName("MissionInput_RejectsOversizedTrailingWhitespaceBeforeTrim");
    }

    private static MissionDecisionSnapshot CaptureDecision(MissionInputRoute route)
    {
        RoutedOperation? standalone = route.ResolveStandaloneOperation();
        return new MissionDecisionSnapshot(
            route.Text,
            route.Memory.Outcome,
            route.Memory.MustNotPersist,
            route.Memory.MustNotDelete,
            route.Memory.MustNotChangeAuthority,
            route.Memory.MustNotInvent,
            route.Memory.MustNotClaimStandaloneRoute,
            route.Memory.MaskPublicProjection,
            route.Memory.Operation?.Name,
            route.Memory.Operation?.PrivateArguments.ToJsonString(),
            standalone?.Name,
            standalone?.Arguments.ToJsonString(),
            route.OperationContract);
    }

    private sealed record MissionDecisionSnapshot(
        string Text,
        MemoryParseOutcome MemoryOutcome,
        bool MustNotPersist,
        bool MustNotDelete,
        bool MustNotChangeAuthority,
        bool MustNotInvent,
        bool MustNotClaimStandaloneRoute,
        bool MaskPublicProjection,
        string? MemoryOperation,
        string? MemoryArguments,
        string? StandaloneOperation,
        string? StandaloneArguments,
        MissionOperationContract? OperationContract);

    private static string RepositoryPath(params string[] path)
    {
        DirectoryInfo? current = new(TestContext.CurrentContext.TestDirectory);
        while (current is not null && !File.Exists(Path.Combine(current.FullName, "Baxy.slnx")))
        {
            current = current.Parent;
        }

        if (current is null)
        {
            throw new AssertionException("Could not locate the BAXY repository root.");
        }

        return path.Aggregate(current.FullName, Path.Combine);
    }
}
