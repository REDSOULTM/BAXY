using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// M109 (DEV-D v4d, tests/data/c03_m109_evidence.json): D-w17-t4 «anything big in the news today» ended filtered as
/// reversed_result — the mind's report quoted a headline that said «No acepto que se ponga en duda mi palabra», and the
/// App's failure lens, which masked only web.search results, read a senator's words as a failure of the read. The
/// headlines a verified news read observed are now data here too (twin of the mind's
/// _without_observed_search_vocabulary). And D-p24-t4 «Yes, do it for me.» → «I have not done it yet because …», the
/// mind's answer to a go-ahead, was refused as ambiguous_without_question; the act said not done with its reason
/// answers «do it» (twin of semantic.dialogue.says_not_done_and_why, rows read on both sides). Phrasings are our own.
/// </summary>
[TestFixture]
public sealed class M109VaciosCharlaTests
{
    private const string Headlines =
        """{"kind":"operation","operation":"web.news.headlines","polarity":"success","verified":true,"succeeded":true,"observed":{"edition":"es-419/CL","count":2,"headlines":[{"title":"El ministro responde a la oposición: “No acepto esas críticas”","source":"Diario Uno"},{"title":"Rechazado en el Senado el plan de transporte nocturno","source":"Radio Dos"}]}}""";

    private static JsonObject Evidence() => (JsonObject)JsonNode.Parse(File.ReadAllText(Path.Combine(
        FindRepositoryRoot(), "tests", "data", "c03_m109_evidence.json")))!;

    private static IEnumerable<TestCaseData> NotDoneCases()
    {
        int index = 0;
        foreach (JsonNode? row in (JsonArray)Evidence()["not_done_and_why_twins"]!)
        {
            yield return new TestCaseData((string)row!["reply"]!, (bool)row["told"]!).SetName($"NotDone({index++})");
        }
    }

    [Test]
    public void AReportOfTheHeadlinesReadIsNotAReversedResult()
    {
        var draft = new UserMessageDraft(Headlines, "status", null);
        string report = "Titulares: «El ministro responde a la oposición: “No acepto esas críticas”»; "
            + "«Rechazado en el Senado el plan de transporte nocturno».";
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(report, draft, "qué hay de nuevo en las noticias"),
            Is.Not.EqualTo("reversed_result"));
    }

    [Test]
    public void AnOwnFailureToldOverTheHeadlinesStillIs()
    {
        var draft = new UserMessageDraft(Headlines, "status", null);
        string report = "Titulares: «Rechazado en el Senado el plan de transporte nocturno». No pude leer el resto.";
        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(report, draft, "qué hay de nuevo en las noticias"),
            Is.EqualTo("reversed_result"));
    }

    [TestCaseSource(nameof(NotDoneCases))]
    public void TheAppReadsTheActNotDoneAndWhyAsTheMindDoes(string reply, bool told) =>
        Assert.That(UserMessagePolicy.SaysNotDoneAndWhy(FoldForTest(reply)), Is.EqualTo(told), reply);

    [Test]
    public void DoItAnsweredWithTheActNotDoneAndWhyIsNoUnaskedQuestion()
    {
        Assert.Multiple(() =>
        {
            Assert.That(
                UserMessagePolicy.ConversationReplyRejectionReason(
                    "Yes, do it for me.",
                    "I have not done it yet because the store asks me to sign in on this PC first.",
                    "en"),
                Is.Not.EqualTo("ambiguous_without_question"));
            Assert.That(
                UserMessagePolicy.ConversationReplyRejectionReason("Yes, do it for me.", "Sure, right away.", "en"),
                Is.EqualTo("ambiguous_without_question"));
        });
    }

    // The policy folds before its readers (lowercase, no diacritics); the rows are folded the same way here.
    private static string FoldForTest(string value)
    {
        var builder = new System.Text.StringBuilder(value.Length);
        foreach (char character in value.Normalize(System.Text.NormalizationForm.FormD))
        {
            if (System.Globalization.CharUnicodeInfo.GetUnicodeCategory(character)
                != System.Globalization.UnicodeCategory.NonSpacingMark)
            {
                builder.Append(char.ToLowerInvariant(character));
            }
        }

        return builder.ToString().Normalize(System.Text.NormalizationForm.FormC);
    }

    private static string FindRepositoryRoot()
    {
        // Read while the cases are built, before any test context exists.
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Baxy.slnx")))
        {
            directory = directory.Parent;
        }

        return directory?.FullName ?? throw new DirectoryNotFoundException("Baxy.slnx not found");
    }
}
