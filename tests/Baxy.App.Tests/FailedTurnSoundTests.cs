using System.Diagnostics;
using System.Reflection;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// A failed turn is heard (final 6, accesibilidad): it sounds <see cref="Chime.TurnFailed"/> once, through
/// <see cref="MainWindowViewModel.LastTurnFailure"/>, whether the model did not answer (NativeTurnLoop's Fail) or the
/// turn threw; a turn that answers or that was cancelled sounds nothing.
/// </summary>
[TestFixture]
public sealed class FailedTurnSoundTests
{
    private const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;

    [Test]
    public async Task AFailedTurnSoundsOnceAndATurnThatAnswersOrIsCancelledSoundsNothing()
    {
        using var fake = new FakeMind();
        int sounded = 0;
        var viewModel = new MainWindowViewModel { Sound = chime => sounded += chime == Chime.TurnFailed ? 1 : 0 };
        await using (viewModel)
        {
            var loop = (NativeTurnLoop)typeof(MainWindowViewModel).GetField("_loop", Private)!.GetValue(viewModel)!;

            // No mind: the loop says mind_unavailable (NativeTurnLoop's Fail).
            await RunTurnAsync(viewModel, () => loop.RunAsync("abre la calculadora", Stopwatch.GetTimestamp(),
                CancellationToken.None));
            Assert.Multiple(() =>
            {
                Assert.That(viewModel.LastTurnFailure, Is.EqualTo("mind_unavailable"));
                Assert.That(sounded, Is.EqualTo(1));
            });

            await RunTurnAsync(viewModel, static () => Task.CompletedTask);
            Assert.Multiple(() =>
            {
                Assert.That(viewModel.LastTurnFailure, Is.Null);
                Assert.That(sounded, Is.EqualTo(1), "a turn that answered sounded");
            });

            // The person's cancellation arrives while the turn runs.
            using var cancelled = new CancellationTokenSource();
            await RunTurnAsync(viewModel, async () =>
            {
                await cancelled.CancelAsync();
                cancelled.Token.ThrowIfCancellationRequested();
            }, cancelled.Token);
            Assert.Multiple(() =>
            {
                Assert.That(viewModel.LastTurnFailure, Is.Null);
                Assert.That(sounded, Is.EqualTo(1), "a cancelled turn sounded");
            });

            // The loop fails and then the turn throws as well (turn_failed): one turn, one sound.
            await RunTurnAsync(viewModel, async () =>
            {
                await loop.RunAsync("abre la calculadora", Stopwatch.GetTimestamp(), CancellationToken.None);
                throw new KeyNotFoundException();
            });
            Assert.Multiple(() =>
            {
                Assert.That(viewModel.LastTurnFailure, Is.EqualTo("turn_failed"));
                Assert.That(sounded, Is.EqualTo(2), "the next failed turn sounds once");
            });
        }
    }

    [Test]
    public void TheFailedTurnToneIsShortAndNotTheWakeTone()
    {
        byte[] wave = Chime.TurnFailed.Wave;
        int dataBytes = BitConverter.ToInt32(wave, 40);
        int rate = BitConverter.ToInt32(wave, 24);
        double milliseconds = dataBytes / 2.0 / rate * 1000;
        Assert.Multiple(() =>
        {
            Assert.That(wave.Length, Is.EqualTo(44 + dataBytes));
            Assert.That(milliseconds, Is.InRange(100, 300));
            Assert.That(wave, Is.Not.EqualTo(Chime.Wake.Wave));
        });
    }

    // A turn as the App runs it: RunTurnAsync starts it empty and ends it (answered, cancelled or failed).
    private static Task RunTurnAsync(MainWindowViewModel viewModel, Func<Task> turn,
        CancellationToken cancellationToken = default) =>
        (Task)typeof(MainWindowViewModel).GetMethod("RunTurnAsync", Private)!.Invoke(viewModel,
            ["hola", turn, cancellationToken, null])!;
}
