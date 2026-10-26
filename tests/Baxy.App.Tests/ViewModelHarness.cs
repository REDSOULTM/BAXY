using System.Reflection;
using Baxy.App;

namespace Baxy.App.Tests;

/// <summary>
/// The view model as the App runs it, with the fake mind started by its own start-up path (InitializeMindAsync) and,
/// where a test needs turns, an engine marked ready that never runs: the core is a process these tests do not start,
/// so its readiness and client are set by reflection (a turn that only talks with the mind never sends it anything).
/// </summary>
internal static class ViewModelHarness
{
    private const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;

    internal static async Task<MainWindowViewModel> WithMindAsync()
    {
        var viewModel = new MainWindowViewModel { FailedTurnSound = static () => { } }; // a failed turn sounds nothing here
        await StartMindAsync(viewModel);
        if (!viewModel.IsMindReady)
        {
            throw new InvalidOperationException("The view model did not take the fake mind.");
        }

        return viewModel;
    }

    /// <summary>One run of the view model's mind start-up (the App's own, as at start or a relaunch).</summary>
    internal static Task StartMindAsync(MainWindowViewModel viewModel) =>
        (Task)typeof(MainWindowViewModel).GetMethod("InitializeMindAsync", Private)!.Invoke(viewModel,
            [Task.FromResult(FakeMind.EmptyCatalog), CancellationToken.None, CancellationToken.None])!;

    /// <summary>Lets the person's turns in: the engine counts as up (it is never sent anything here).</summary>
    internal static void AcceptTurns(MainWindowViewModel viewModel)
    {
        typeof(MainWindowViewModel).GetField("_coreClient", Private)!.SetValue(viewModel, new CoreProcessClient());
        typeof(MainWindowViewModel).GetProperty(nameof(MainWindowViewModel.IsReady))!.SetValue(viewModel, true);
    }

    internal static async Task<bool> UntilAsync(Func<bool> condition, double seconds = 10)
    {
        var clock = System.Diagnostics.Stopwatch.StartNew();
        while (clock.Elapsed < TimeSpan.FromSeconds(seconds))
        {
            if (condition())
            {
                return true;
            }

            await Task.Delay(20);
        }

        return condition();
    }
}
