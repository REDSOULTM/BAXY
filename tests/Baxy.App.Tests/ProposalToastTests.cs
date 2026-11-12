using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// OVL1: the Sí of a proposal's toast authorizes too, and the toast comes up over whatever the person is clicking on.
/// Windows draws it, so the rule is by the time Windows tells of the press: a Sí before the toast's wait does not
/// answer, and the person is told plainly that the proposal still waits; the No always answers. Windows itself is
/// stood in.
/// </summary>
[TestFixture]
public sealed class ProposalToastTests
{
    private sealed class Shell
    {
        internal long Now;
        internal readonly List<(string Title, string? Context, Action<bool> Press)> Up = [];
        internal readonly List<int> Gone = [];
        internal readonly List<string> Told = [];
        internal bool Refuses;

        internal ProposalToast Toast() => new()
        {
            ArmMilliseconds = 1500,
            Ticks = () => Now,
            Plain = Told.Add,
            Post = (title, context, press) =>
            {
                if (Refuses)
                {
                    return null;
                }

                int n = Up.Count;
                Up.Add((title, context, press));
                return () => Gone.Add(n);
            },
        };
    }

    [Test]
    public void ASiBeforeTheToastsWaitDoesNotAnswerAndThePersonIsToldTheProposalStillWaits()
    {
        var shell = new Shell { Now = 5000 };
        var answers = new List<bool>();
        ProposalToast toast = shell.Toast();
        Assert.That(toast.Show("¿Guardo la nota del mediodía?", "La dejaste a medias.", answers.Add), Is.True);
        Assert.That(shell.Up, Has.Count.EqualTo(1));

        shell.Now = 6480;
        shell.Up[0].Press(true);
        Assert.That(answers, Is.Empty, "1480 ms after Windows took it: some of that it was not yet on the screen");
        Assert.That(shell.Told, Has.Count.EqualTo(1), "Windows took the toast away with the press");
        Assert.That(shell.Told[0], Does.EndWith("¿Guardo la nota del mediodía?"));
        Assert.That(shell.Up, Has.Count.EqualTo(1), "no second toast, which would come up nobody knows when");

        shell.Now = 9000;
        shell.Up[0].Press(true);
        Assert.That(answers, Is.Empty, "that toast went with its first press");
        Assert.That(shell.Told, Has.Count.EqualTo(1));
        toast.Hide();
        Assert.That(shell.Gone, Is.Empty, "nothing of it is left to take away");
    }

    [Test]
    public void ASiPastTheToastsWaitAnswers()
    {
        var shell = new Shell { Now = 5000 };
        var answers = new List<bool>();
        shell.Toast().Show("¿Guardo la nota del mediodía?", null, answers.Add);
        shell.Now = 6500;
        shell.Up[0].Press(true);
        Assert.That(answers, Is.EqualTo(new[] { true }));
        Assert.That(shell.Told, Is.Empty);
    }

    [Test]
    public void TheNoAnswersAtAnyTime()
    {
        var shell = new Shell { Now = 100 };
        var answers = new List<bool>();
        shell.Toast().Show("¿Bajo el brillo?", null, answers.Add);
        shell.Now = 101;
        shell.Up[0].Press(false);
        Assert.That(answers, Is.EqualTo(new[] { false }));
        Assert.That(shell.Told, Is.Empty);
    }

    [Test]
    public void AnEarlySiOfAToastThatWentSaysNothingAndDoesNotTouchTheOneShowing()
    {
        var shell = new Shell { Now = 100 };
        var answers = new List<string>();
        ProposalToast toast = shell.Toast();
        toast.Show("¿Bajo el brillo?", null, approve => answers.Add("brillo " + approve));
        toast.Hide();
        Assert.That(shell.Gone, Is.EqualTo(new[] { 0 }));

        toast.Show("¿Cierro la hoja?", null, approve => answers.Add("hoja " + approve));
        shell.Now = 400;
        shell.Up[0].Press(true);
        Assert.That(shell.Told, Is.Empty, "answered elsewhere: there is nothing to tell of it");
        shell.Now = 1700;
        shell.Up[1].Press(true);
        Assert.That(answers, Is.EqualTo(new[] { "hoja True" }), "the toast showing still answers past its own wait");
        toast.Hide();
        Assert.That(shell.Gone, Is.EqualTo(new[] { 0, 1 }));
    }

    [Test]
    public void WhenWindowsDoesNotTakeTheToastTheCallerIsTold()
    {
        var shell = new Shell { Refuses = true };
        Assert.That(shell.Toast().Show("¿Bajo el brillo?", null, _ => { }), Is.False);
    }
}
