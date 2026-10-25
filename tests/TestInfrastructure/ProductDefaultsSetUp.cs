using NUnit.Framework;

namespace Baxy;

/// <summary>
/// Calidad del PC (2026-10-25): a test assembly starts from the product's defaults, not from the shell that runs it.
/// A shell of this PC that ran a bench keeps BAXY_AYUDAS (the ablations set it to «none» or to a list), and the App's
/// suite then failed there and passed elsewhere: with BAXY_AYUDAS=none, 33 of its 241 tests (SaidFolders,
/// SaidApplication, the turn loop) and 13 of the providers' (the calculator, the caret, the repeated click, the known
/// folders). Around the whole assembly (namespace Baxy holds every test of it) the switch is
/// cleared and given back at the end; a test that needs it sets it itself, as those of SaidFoldersTests already do.
/// </summary>
[SetUpFixture]
public sealed class ProductDefaultsSetUp
{
    // The behavior switches the measured suites read; a runtime location (BAXY_MIND_LLM_GGUF, BAXY_DATA_DIR…) stays.
    private static readonly string[] Switches = ["BAXY_AYUDAS"];

    private readonly Dictionary<string, string?> _before = [];

    [OneTimeSetUp]
    public void StartFromTheDefaults()
    {
        foreach (string name in Switches)
        {
            _before[name] = Environment.GetEnvironmentVariable(name);
            Environment.SetEnvironmentVariable(name, null);
        }
    }

    [OneTimeTearDown]
    public void GiveTheShellItsSwitchesBack()
    {
        foreach ((string name, string? value) in _before)
        {
            Environment.SetEnvironmentVariable(name, value);
        }
    }
}
