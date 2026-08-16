using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
[NonParallelizable]
public sealed class AssetManifestDiscoveryTests
{
    [Test]
    public void SharedDescriptorReportsTheExactMissingCandidates()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-assets-" + Guid.NewGuid());
        try
        {
            Directory.CreateDirectory(root);
            string descriptor = Path.Combine(root, "assets.manifest.json");
            File.WriteAllText(
                descriptor,
                """
                {
                  "schema": "baxy-assets-v1",
                  "version": 1,
                  "local_override": {
                    "environment": "BAXY_TEST_ASSET_OVERRIDE",
                    "default": "${LOCALAPPDATA}\\BAXYRuntime\\missing-assets.local.json",
                    "schema": "baxy-assets-local-v1"
                  },
                  "assets": {
                    "conversation_model": {
                      "kind": "file",
                      "required": true,
                      "environment": "BAXY_TEST_MODEL",
                      "candidates": [
                        "${REPOSITORY_ROOT}\\missing\\model.gguf"
                      ],
                      "repair": "Restaura el modelo atestado."
                    }
                  }
                }
                """);

            AssetManifestDiagnostic diagnostic =
                AssetManifestDiscovery.InspectRequiredAssets(descriptor);

            Assert.Multiple(() =>
            {
                Assert.That(diagnostic.Code, Is.EqualTo("asset_missing"));
                Assert.That(diagnostic.Message, Does.Contain("Restaura el modelo atestado."));
                Assert.That(
                    diagnostic.Candidates,
                    Is.EqualTo(new[] { Path.Combine(root, "missing", "model.gguf") }));
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [Test]
    public void SharedDescriptorAcceptsAMachineLocalOverride()
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-assets-override-" + Guid.NewGuid());
        string? previous = Environment.GetEnvironmentVariable("BAXY_TEST_ASSET_OVERRIDE");
        try
        {
            Directory.CreateDirectory(root);
            string model = Path.Combine(root, "private", "model.gguf");
            Directory.CreateDirectory(Path.GetDirectoryName(model)!);
            File.WriteAllBytes(model, [1]);
            string local = Path.Combine(root, "assets.local.json");
            File.WriteAllText(
                local,
                $$"""
                {
                  "schema": "baxy-assets-local-v1",
                  "assets": {
                    "conversation_model": [{{Json(model)}}]
                  }
                }
                """);
            Environment.SetEnvironmentVariable("BAXY_TEST_ASSET_OVERRIDE", local);
            string descriptor = Path.Combine(root, "assets.manifest.json");
            File.WriteAllText(
                descriptor,
                """
                {
                  "schema": "baxy-assets-v1",
                  "version": 1,
                  "local_override": {
                    "environment": "BAXY_TEST_ASSET_OVERRIDE",
                    "default": "${LOCALAPPDATA}\\BAXYRuntime\\assets.local.json",
                    "schema": "baxy-assets-local-v1"
                  },
                  "assets": {
                    "conversation_model": {
                      "kind": "file",
                      "required": true,
                      "environment": "BAXY_TEST_MODEL",
                      "candidates": [],
                      "repair": "Restaura el modelo."
                    }
                  }
                }
                """);

            AssetManifestDiagnostic diagnostic =
                AssetManifestDiscovery.InspectRequiredAssets(descriptor);

            Assert.That(diagnostic.Code, Is.EqualTo("assets_ready"));
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_TEST_ASSET_OVERRIDE", previous);
            Directory.Delete(root, recursive: true);
        }
    }

    private static string Json(string value) =>
        System.Text.Json.JsonSerializer.Serialize(value);
}
