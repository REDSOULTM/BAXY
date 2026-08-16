using System.Globalization;
using System.IO;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Medición del tramo del shell en el camino de respuesta visible con el core
/// real: desde que el turno entra hasta la primera indicación honesta y hasta
/// que el texto queda publicado en la conversación.
///
/// ALCANCE EXACTO DE ESTAS CIFRAS — no son latencia productiva completa:
/// <list type="bullet">
/// <item>el ensamblado activa <c>BypassLlmCompositionForTests</c>
/// (<see cref="TestAssemblySetup"/>), así que el texto final proviene de la
/// plantilla determinista y NO de <c>message.compose</c>, que es la
/// composición real del LLM en producción;</item>
/// <item>la decisión la fija un resolver de prueba, no P/G/L/V/C;</item>
/// <item>el tramo WebView2→DOM→primer paint queda fuera.</item>
/// </list>
/// La cifra productiva end-to-end vive en la medición física opt-in, no aquí.
/// Lo que esta prueba sí certifica es la propiedad que importa del cambio de
/// R8: la indicación honesta precede al texto, no lo sustituye ni lo retrasa.
/// </summary>
[TestFixture]
public sealed class VisibleResponsePathMeasurementTests
{
    private const int Turns = 12;

    [Test]
    public async Task TheFirstHonestIndicationArrivesLongBeforeTheFinalText()
    {
        string path = Path.Combine(
            Path.GetTempPath(),
            "baxy-visible-path-" + Guid.NewGuid().ToString("N") + ".jsonl");
        var indications = new List<double>();
        var finals = new List<double>();
        try
        {
            using (ShellTrace? trace = ShellTrace.TryCreate(path))
            {
                Assert.That(trace, Is.Not.Null);
                using IDisposable scope = ShellTraceSink.Use(trace!);
                await using var viewModel = new MainWindowViewModel(
                    static route => new RoutedOperation(
                        "system.time",
                        new JsonObject()));
                await viewModel.InitializeAsync(CancellationToken.None);
                if (!viewModel.IsReady)
                {
                    Assert.Ignore("el core local no está disponible en este entorno");
                }

                var visible = new List<double>();
                viewModel.PropertyChanged += (_, args) =>
                {
                    if (args.PropertyName != nameof(MainWindowViewModel.IsBusy))
                    {
                        return;
                    }

                    // La indicación honesta se publica en cuanto el turno pasa a
                    // ocupado: es exactamente lo que ve la persona primero.
                    if (viewModel.IsBusy)
                    {
                        visible.Add(trace!.ElapsedMilliseconds);
                    }
                };

                for (int turn = 0; turn < Turns; turn++)
                {
                    visible.Clear();
                    double started = trace!.ElapsedMilliseconds;
                    await viewModel.SubmitAsync(
                        new MissionInput("¿Qué hora es?", MissionInputSource.Text),
                        CancellationToken.None);
                    double finished = trace.ElapsedMilliseconds;
                    Assert.That(visible, Is.Not.Empty, "no hubo indicación visible");
                    indications.Add(visible[0] - started);
                    finals.Add(finished - started);
                }
            }

            string[] lines = File.ReadAllLines(path);
            Assert.That(lines, Is.Not.Empty);
            Assert.That(
                lines.Count(line =>
                    ((JsonObject)JsonNode.Parse(line)!)["stage"]!.GetValue<string>()
                    == ShellTraceStages.ResponseFinal),
                Is.EqualTo(Turns));

            indications.Sort();
            finals.Sort();
            TestContext.Out.WriteLine(
                string.Create(
                    CultureInfo.InvariantCulture,
                    $"shell_visible_indication_ms p50={Percentile(indications, 0.50):F3} " +
                    $"p95={Percentile(indications, 0.95):F3} " +
                    $"max={indications[^1]:F3}"));
            TestContext.Out.WriteLine(
                string.Create(
                    CultureInfo.InvariantCulture,
                    $"shell_published_text_ms_without_llm_composition " +
                    $"p50={Percentile(finals, 0.50):F3} " +
                    $"p95={Percentile(finals, 0.95):F3} max={finals[^1]:F3}"));

            // La indicación honesta no puede llegar después del texto final:
            // si lo hiciera, la persona esperaría el turno completo sin señal.
            Assert.That(
                Percentile(indications, 0.95),
                Is.LessThan(Percentile(finals, 0.95)));
        }
        finally
        {
            File.Delete(path);
        }
    }

    private static double Percentile(List<double> ordered, double quantile) =>
        ordered[Math.Min(ordered.Count - 1, (int)(ordered.Count * quantile))];
}
