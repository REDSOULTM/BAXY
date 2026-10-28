using NUnit.Framework;
using NUnit.Framework.Interfaces;
using NUnit.Framework.Internal;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Pruebas de escritorio (2026-10-28): a test that reads real windows, the foreground or a hotkey needs the person's
/// window station. Run over ssh (session 0) the window station is not interactive: its desktop window is not visible,
/// so IsWindowVisible answers false for every window, there is no foreground window and RegisterHotKey fails with
/// ERROR_REQUIRES_INTERACTIVE_WINDOWSTATION (1459). Such a test failed there with nothing wrong in the product, and one
/// hung on a wait no hotkey could answer. Like NUnit's Platform attribute, it is skipped with this reason where the
/// window station is not interactive (Environment.UserInteractive reads its WSF_VISIBLE flag) and runs everywhere else.
/// </summary>
[AttributeUsage(AttributeTargets.Class | AttributeTargets.Method, AllowMultiple = false, Inherited = false)]
public sealed class InteractiveDesktopAttribute : NUnitAttribute, IApplyToTest
{
    public void ApplyToTest(Test test)
    {
        if (test.RunState == RunState.NotRunnable || Environment.UserInteractive)
            return;
        test.RunState = RunState.Skipped;
        test.Properties.Set(PropertyNames.SkipReason,
            "needs an interactive window station (session 0, as over ssh, has no visible desktop, foreground or hotkeys)");
    }
}
