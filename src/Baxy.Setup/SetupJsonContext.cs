using System.Text.Json.Serialization;

namespace Baxy.Setup;

[JsonSourceGenerationOptions(
    PropertyNameCaseInsensitive = false,
    WriteIndented = false,
    UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
    GenerationMode = JsonSourceGenerationMode.Default)]
[JsonSerializable(typeof(BuildManifest))]
[JsonSerializable(typeof(InstalledVersionAttestation))]
[JsonSerializable(typeof(InstallationPointer))]
[JsonSerializable(typeof(EmbeddedPackageAttestation))]
[JsonSerializable(typeof(InstallTransaction))]
[JsonSerializable(typeof(EmbeddedVerificationEvidence))]
[JsonSerializable(typeof(WindowsInstallationIdentity))]
[JsonSerializable(typeof(WindowsIntegrationActiveIdentity))]
[JsonSerializable(typeof(WindowsIntegrationStableSetupState))]
[JsonSerializable(typeof(WindowsIntegrationShortcutState))]
[JsonSerializable(typeof(WindowsIntegrationState))]
[JsonSerializable(typeof(WindowsIntegrationTransaction))]
internal sealed partial class SetupJsonContext : JsonSerializerContext;
