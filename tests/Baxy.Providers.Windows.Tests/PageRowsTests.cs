using System.Globalization;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo 82 (vivo del 81, «léeme el último correo» 0/2): a page's rows as they lie on screen, and which one has the
/// latest date or time, by the form of a cell that holds nothing else. Invented rows.
/// </summary>
[TestFixture]
public sealed class PageRowsTests
{
    private static readonly DateTime Now = new(2026, 11, 4, 11, 0, 0, DateTimeKind.Local);
    private static readonly CultureInfo Spanish = CultureInfo.GetCultureInfo("es-CL");

    private static UserBrowserPageRow Row(double top, params string[] cells) => new(top, top + 20, cells);

    private static PageRowFacts? Read(params UserBrowserPageRow[] rows) => PageRows.Read(rows, Now, Spanish);

    [Test]
    public void TheTopRowWithTheLatestTimeIsNamedThoughItIsFirst()
    {
        PageRowFacts? facts = Read(
            Row(100, "Vivero Pino", "Riego del lunes", "10:31"),
            Row(120, "Club Faro", "Cuota", "09:12"),
            Row(140, "Boletín Sur", "Novedades", "ayer"));

        Assert.Multiple(() =>
        {
            Assert.That(facts?.Count, Is.EqualTo(3));
            Assert.That(facts?.LatestRow, Is.EqualTo(1));
            Assert.That(facts?.LatestWhen, Is.EqualTo("10:31"));
            Assert.That(facts?.LatestText, Is.EqualTo("Vivero Pino · Riego del lunes · 10:31"));
            Assert.That(facts?.WithoutDate, Is.EqualTo(1));
        });
    }

    [Test]
    public void ALatestRowAtTheBottomIsNamedToo()
    {
        PageRowFacts? facts = Read(
            Row(100, "Uno", "01/10/2026"),
            Row(120, "Dos", "15/10/2026"),
            Row(140, "Tres", "03/11/2026"));

        Assert.That(facts?.LatestRow, Is.EqualTo(3));
    }

    [Test]
    public void RowsAreCountedByTheirPlaceOnScreenNotByTheirOrderInThePage()
    {
        PageRowFacts? facts = Read(
            Row(140, "Abajo", "09:00"),
            Row(100, "Arriba", "10:00"),
            Row(120, "Medio", "09:30"));

        Assert.That(facts?.LatestRow, Is.EqualTo(1));
    }

    [Test]
    public void ACellInsideARowIsThatRowsNotAnother()
    {
        PageRowFacts? facts = Read(
            new UserBrowserPageRow(100, 120, ["Uno", "10:00"]),
            new UserBrowserPageRow(102, 118, ["10:00"]),
            new UserBrowserPageRow(120, 140, ["Dos", "09:00"]));

        Assert.Multiple(() =>
        {
            Assert.That(facts?.Count, Is.EqualTo(2));
            Assert.That(facts?.LatestRow, Is.EqualTo(1));
        });
    }

    [Test]
    public void ADateWithoutAYearIsTheLastOneThatPassed()
    {
        Assert.Multiple(() =>
        {
            Assert.That(PageRows.When("28 dic", Now, Spanish)?.Year, Is.EqualTo(2025));
            Assert.That(PageRows.When("3 nov", Now, Spanish)?.Year, Is.EqualTo(2026));
            Assert.That(PageRows.When("Nov 3, 2026", Now, Spanish)?.Day, Is.EqualTo(3));
            Assert.That(PageRows.When("10:31", Now, Spanish)?.Date, Is.EqualTo(Now.Date));
            Assert.That(PageRows.When("3:05 PM", Now, Spanish)?.Hour, Is.EqualTo(15));
        });
    }

    [TestCase("Reunión a las 15:00")]
    [TestCase("3-1")]
    [TestCase("1.5")]
    [TestCase("10.31")]
    [TestCase("2026")]
    [TestCase("ayer")]
    [TestCase("Riego del lunes")]
    [TestCase("")]
    public void AnythingElseIsNoDate(string cell) =>
        Assert.That(PageRows.When(cell, Now, Spanish), Is.Null);

    [Test]
    public void ATimeInsideASubjectIsTheSubjects()
    {
        PageRowFacts? facts = Read(
            Row(100, "Uno", "Cita a las 23:50", "09:00"),
            Row(120, "Dos", "Otra cosa", "10:00"));

        Assert.That(facts?.LatestRow, Is.EqualTo(2));
    }

    // Measured live: a list's option gives only its whole name, with the date at its end.
    [Test]
    public void ARowOfOneNameEndsWithItsDate()
    {
        PageRowFacts? facts = Read(
            Row(100, "Vivero Pino Riego del lunes 10:31"),
            Row(120, "Club Faro Cuota de noviembre 3 nov"),
            Row(140, "Boletín Sur Novedades ayer"));

        Assert.Multiple(() =>
        {
            Assert.That(facts?.LatestRow, Is.EqualTo(1));
            Assert.That(facts?.LatestWhen, Is.EqualTo("10:31"));
            Assert.That(facts?.WithoutDate, Is.EqualTo(1));
        });
    }

    [Test]
    public void AMenuOrARowAloneSaysNothing()
    {
        Assert.Multiple(() =>
        {
            Assert.That(Read(Row(100, "Inicio"), Row(120, "Productos"), Row(140, "Contacto")), Is.Null);
            Assert.That(Read(Row(100, "Uno", "10:00"), Row(120, "Dos")), Is.Null, "one date orders nothing");
            Assert.That(PageRows.Read(null, Now, Spanish), Is.Null);
        });
    }

    [Test]
    public void ATieNamesNoRow()
    {
        PageRowFacts? facts = Read(Row(100, "Uno", "10:00"), Row(120, "Dos", "10:00"));

        Assert.Multiple(() =>
        {
            Assert.That(facts?.Count, Is.EqualTo(2));
            Assert.That(facts?.LatestRow, Is.Null);
        });
    }
}
