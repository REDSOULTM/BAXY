using System.Diagnostics;
using System.Reflection;
using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;

namespace Baxy.App.Tests;

/// <summary>
/// A call waiting for the person's Sí or No, put where the turn loop keeps it (a heartbeat's proposal is the one the
/// loop holds by itself, without the engine these tests do not start), and its question published as the loop does.
/// </summary>
internal static class WaitingCalls
{
    private const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;

    /// <summary>A heartbeat's proposal whose question was published (its card shows), as NativeTurnLoop leaves it.</summary>
    internal static void HoldAskedProposal(NativeTurnLoop loop, DateTimeOffset expiresUtc)
    {
        PreparedOperation proposal = new RetryableOperationRegistry().GetOrAdd(
            new RoutedOperation("web.search", new JsonObject { ["query"] = "clima de mañana" }));
        typeof(NativeTurnLoop).GetField("_proposal", Private)!.SetValue(loop, proposal);
        typeof(NativeTurnLoop).GetField("_proposalExpiresUtc", Private)!.SetValue(loop, expiresUtc);
        typeof(NativeTurnLoop).GetField("_askedAt", Private)!.SetValue(loop, Stopwatch.GetTimestamp());
        typeof(NativeTurnLoop).GetField("_asking", Private)!.SetValue(loop, true);
    }

    /// <summary>The view model's loop holds a proposal and tells it was asked (the view's card, the toast).</summary>
    internal static NativeTurnConfirmation Ask(MainWindowViewModel viewModel)
    {
        var loop = (NativeTurnLoop)typeof(MainWindowViewModel).GetField("_loop", Private)!.GetValue(viewModel)!;
        DateTimeOffset expires = DateTimeOffset.UtcNow + NativeTurnLoop.ProposalLifetime;
        HoldAskedProposal(loop, expires);
        Assert(ProductCatalog.TryGet("web.search", out ProductOperationDescriptor? descriptor) && descriptor is not null);
        var asked = new NativeTurnConfirmation("web.search", new JsonObject { ["query"] = "clima de mañana" },
            descriptor!.Risk, expires, Proposal: true);
        var host = (NativeTurnLoop.Host)typeof(NativeTurnLoop).GetField("_host", Private)!.GetValue(loop)!;
        host.ConfirmationAsked!(asked);
        return asked;
    }

    /// <summary>The loop says the asked call ended (answered elsewhere, dropped), as it does.</summary>
    internal static void Resolve(MainWindowViewModel viewModel, string outcome)
    {
        var loop = (NativeTurnLoop)typeof(MainWindowViewModel).GetField("_loop", Private)!.GetValue(viewModel)!;
        var host = (NativeTurnLoop.Host)typeof(NativeTurnLoop).GetField("_host", Private)!.GetValue(loop)!;
        host.ConfirmationResolved!(outcome);
    }

    /// <summary>A turn of the person's runs (the view model's own flag while one does).</summary>
    internal static void Busy(MainWindowViewModel viewModel, bool busy) =>
        typeof(MainWindowViewModel).GetProperty(nameof(MainWindowViewModel.IsBusy))!.SetValue(viewModel, busy);

    private static void Assert(bool condition)
    {
        if (!condition)
        {
            throw new InvalidOperationException("web.search is not in the catalog.");
        }
    }
}
