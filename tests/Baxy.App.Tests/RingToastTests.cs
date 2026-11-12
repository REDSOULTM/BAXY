using System.Xml.Linq;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// ALR5 (A3, VIVO1 N6): with BAXY minimized, what rings shows a Windows notification with the card's buttons, whose press
/// answers it by its id; an alarm's stays on screen (scenario alarm), a reminder's is a reminder's, and both are silent
/// (the App plays the tone). Nothing is shown here: the notification's content is read.
/// </summary>
[TestFixture]
public sealed class RingToastTests
{
    private static readonly DateTimeOffset T0 = new(2026, 11, 10, 7, 0, 0, TimeSpan.Zero);

    [TestCase(false, "alarm", "Alarma · 07:00", "Posponer 10 min", "Parar")]
    [TestCase(true, "alarm", "Alarm · 07:00", "Snooze 10 min", "Stop")]
    [TestCase(false, "reminder", "Recordatorio · 07:00", "Recordar en 10 min", "Listo")]
    [TestCase(true, "reminder", "Reminder · 07:00", "Remind in 10 min", "Done")]
    public void ItSaysWhatRingsWithTheCardsButtonsAndIsSilent(bool english, string kind, string head, string snooze, string stop)
    {
        var ring = new RingNow("BAXY-x", "89abcdef", kind, "sal a <trabajar> & \"ya\"", "07:00", T0, "w", "ringing");

        XElement toast = XElement.Parse(RingToast.Xml(ring, english));

        Assert.Multiple(() =>
        {
            Assert.That((string?)toast.Attribute("scenario"), Is.EqualTo(kind == "alarm" ? "alarm" : "reminder"));
            Assert.That((string?)toast.Attribute("launch"), Is.EqualTo("open:89abcdef"));
            Assert.That(toast.Descendants("text").Select(static text => text.Value),
                Is.EqualTo(new[] { head, "sal a <trabajar> & \"ya\"" }));
            Assert.That((string?)toast.Element("audio")?.Attribute("silent"), Is.EqualTo("true"));
            Assert.That(toast.Descendants("action").Select(static action =>
                    ((string?)action.Attribute("content"), (string?)action.Attribute("arguments"))),
                Is.EqualTo(new[] { (snooze, "snooze:89abcdef"), (stop, "stop:89abcdef") }));
        });
    }

    [Test]
    public void OneWithNoTitleShowsItsWords()
    {
        var ring = new RingNow("BAXY-x", "89abcdef", "alarm", null, "07:00", T0, "Alarma de las 7:00.", "ringing");

        Assert.That(XElement.Parse(RingToast.Xml(ring, false)).Descendants("text").Last().Value,
            Is.EqualTo("Alarma de las 7:00."));
    }

    [TestCase("stop:89abcdef", "stop", "89abcdef")]
    [TestCase("snooze:89abcdef", "snooze", "89abcdef")]
    [TestCase("open:89abcdef", "open", "89abcdef")]
    public void APressSaysWhatItAsksAndOfWhich(string arguments, string action, string id) =>
        Assert.That(RingToast.Pressed(arguments), Is.EqualTo((action, id)));

    [TestCase(null)]
    [TestCase("")]
    [TestCase("yes")]
    [TestCase("stop:")]
    [TestCase("cancel:89abcdef")]
    public void AnythingElseAsksNothing(string? arguments) => Assert.That(RingToast.Pressed(arguments), Is.Null);
}
