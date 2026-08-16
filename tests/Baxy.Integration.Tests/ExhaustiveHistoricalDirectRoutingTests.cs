using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class ExhaustiveHistoricalDirectRoutingTests
{
    private static readonly JsonSerializerOptions IndentedJson = new()
    {
        WriteIndented = true,
    };

    [Test]
    public void EveryExactRuntimeMessageIsAuditedByTheRealGuiInputPipeline()
    {
        string repository = FindRepository();
        string ledger = Path.Combine(
            repository,
            "artifacts",
            "historical_exhaustive",
            "all_executable_cases.jsonl");
        string oraclePath = Path.Combine(
            repository,
            "artifacts",
            "historical_exhaustive",
            "runtime_oracle.jsonl");
        if (!File.Exists(ledger) || !File.Exists(oraclePath))
        {
            Assert.Ignore("The local exhaustive historical ledger is not available.");
        }

        Dictionary<string, OracleRow> oracle = ReadOracle(oraclePath);
        string output = Path.Combine(
            repository,
            "artifacts",
            "historical_exhaustive",
            "runtime_app_route_gate.jsonl");
        string temporary = output + ".tmp";
        var counts = new Dictionary<string, int>(StringComparer.Ordinal);
        var failures = new List<GateRow>();
        int runtimeCases = 0;
        int accounted = 0;

        Directory.CreateDirectory(Path.GetDirectoryName(output)!);
        using (var writer = new StreamWriter(
            temporary,
            append: false,
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false)))
        {
            foreach (string line in File.ReadLines(ledger, Encoding.UTF8))
            {
                using JsonDocument document = JsonDocument.Parse(line);
                JsonElement root = document.RootElement;
                if (!IsRuntime(root))
                {
                    continue;
                }

                runtimeCases++;
                string caseId = root.GetProperty("case_id").GetString()!;
                string textHash = root.GetProperty("text_sha256").GetString()!;
                string text = root.GetProperty("text_literal").GetString()!;
                int occurrences = root.GetProperty("occurrence_count").GetInt32();
                if (!oracle.TryGetValue(caseId, out OracleRow? expected))
                {
                    throw new InvalidDataException($"Missing oracle row for {caseId}.");
                }

                string? operation = null;
                string decision = "mind_required";
                try
                {
                    MissionInputRoute route = MissionInputPipeline.Route(
                        new MissionInput(text, MissionInputSource.Text));
                    operation = route.OperationContract?.Name;
                    decision = operation is not null
                        ? route.HasPrivatePublicComposition
                            ? "direct_private_composition"
                            : "direct_operation"
                        : route.Memory.Outcome switch
                        {
                            MemoryParseOutcome.Clarify or
                            MemoryParseOutcome.AskToSave or
                            MemoryParseOutcome.ConfirmSensitiveSave =>
                                "direct_clarification",
                            MemoryParseOutcome.SessionContextOnly or
                            MemoryParseOutcome.RejectAuthorizationPersistence =>
                                "direct_conversation",
                            MemoryParseOutcome.NoRoute
                                when route.Memory.MustNotClaimStandaloneRoute =>
                                    "direct_conversation",
                            _ => "mind_required",
                        };
                }
                catch (MissionInputRejectedException)
                {
                    decision = "input_rejected";
                }

                string status = Assess(expected, operation, decision);
                counts[status] = counts.GetValueOrDefault(status) + 1;
                var row = new GateRow(
                    caseId,
                    textHash,
                    expected.ExpectedEffect,
                    expected.ExpectedFamilies,
                    decision,
                    operation,
                    status,
                    occurrences);
                writer.WriteLine(JsonSerializer.Serialize(row));
                accounted++;
                if (status is "direct_false_effect" or "direct_wrong_operation")
                {
                    failures.Add(row);
                }
            }
        }
        File.Move(temporary, output, overwrite: true);

        string summaryPath = Path.Combine(
            repository,
            "artifacts",
            "historical_exhaustive",
            "runtime_app_route_gate_summary.json");
        var summary = new
        {
            schemaVersion = 1,
            scope = "every_exact_runtime_message_real_gui_input_pipeline_no_effect",
            uniqueRuntimeCases = runtimeCases,
            allCasesAccounted = accounted == runtimeCases && runtimeCases == oracle.Count,
            sourceCaseSha256 = FileSha256(ledger),
            sourceOracleSha256 = FileSha256(oraclePath),
            statusCounts = counts.OrderBy(static item => item.Key).ToDictionary(),
            directFailures = failures.Count,
            toolsExecuted = 0,
            failureCases = failures.Take(200).ToArray(),
        };
        File.WriteAllText(
            summaryPath,
            JsonSerializer.Serialize(summary, IndentedJson).Replace("\r\n", "\n") + "\n",
            new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));

        Assert.Multiple(() =>
        {
            Assert.That(runtimeCases, Is.EqualTo(14_845));
            Assert.That(accounted, Is.EqualTo(runtimeCases));
            Assert.That(oracle, Has.Count.EqualTo(runtimeCases));
            Assert.That(failures, Is.Empty, JsonSerializer.Serialize(failures.Take(20)));
        });
    }

    private static string Assess(OracleRow oracle, string? operation, string decision)
    {
        if (oracle.ExpectedEffect is "none" or "unsupported")
        {
            return operation is null ? "pass_no_direct_effect" : "direct_false_effect";
        }
        if (oracle.ExpectedEffect == "operation")
        {
            if (operation is null)
            {
                return decision == "input_rejected" ? "review_input_rejected" : "mind_required";
            }

            string actualFamily = OperationFamily(operation);
            HashSet<string> compatible = [.. oracle.ExpectedFamilies];
            foreach (string family in oracle.ExpectedFamilies)
            {
                foreach (string alias in Compatibility(family))
                {
                    compatible.Add(alias);
                }
            }
            return compatible.Contains(actualFamily)
                ? "pass_direct_operation_family"
                : "direct_wrong_operation";
        }

        return operation is null ? "review_oracle" : "review_oracle_direct_effect";
    }

    private static string OperationFamily(string operation) =>
        operation.Split('.', 2)[0] switch
        {
            "note" or "task" => "note_task",
            "capture" or "ocr" => "vision",
            "settings" => "system_settings",
            "streaming" => "media",
            var family => family,
        };

    private static string[] Compatibility(string family) => family switch
    {
        "browser" => ["browser", "web"],
        "media" => ["media", "streaming"],
        "note_task" => ["note", "note_task", "task"],
        "system_settings" => ["system", "system_settings"],
        "vision" => ["capture", "ocr", "vision"],
        "web" => ["browser", "web"],
        _ => [],
    };

    private static bool IsRuntime(JsonElement row) =>
        row.GetProperty("provenance_classes")
            .EnumerateArray()
            .Any(static value => value.GetString()?.StartsWith(
                "runtime_",
                StringComparison.Ordinal) == true);

    private static Dictionary<string, OracleRow> ReadOracle(string path)
    {
        var rows = new Dictionary<string, OracleRow>(StringComparer.Ordinal);
        foreach (string line in File.ReadLines(path, Encoding.UTF8))
        {
            using JsonDocument document = JsonDocument.Parse(line);
            JsonElement root = document.RootElement;
            string id = root.GetProperty("case_id").GetString()!;
            rows.Add(
                id,
                new OracleRow(
                    root.GetProperty("expected_effect").GetString()!,
                    root.GetProperty("expected_families")
                        .EnumerateArray()
                        .Select(static value => value.GetString()!)
                        .ToArray()));
        }
        return rows;
    }

    private static string FileSha256(string path) =>
        Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))).ToLowerInvariant();

    private static string FindRepository()
    {
        DirectoryInfo? current = new(TestContext.CurrentContext.TestDirectory);
        while (current is not null)
        {
            if (File.Exists(Path.Combine(current.FullName, "Baxy.slnx")))
            {
                return current.FullName;
            }
            current = current.Parent;
        }
        throw new DirectoryNotFoundException("BAXY repository root was not found.");
    }

    private sealed record OracleRow(string ExpectedEffect, string[] ExpectedFamilies);

    private sealed record GateRow(
        string CaseId,
        string TextSha256,
        string ExpectedEffect,
        string[] ExpectedFamilies,
        string Decision,
        string? Operation,
        string Status,
        int RuntimeOccurrenceCount);
}
