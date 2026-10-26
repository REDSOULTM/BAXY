using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// Ronda 29 (pasada r27 en vivo, v3-53: the model pressed OBS's «Iniciar Transmisión» for «vuelve a activarlo» and no
/// one was asked). What a click sends out to the world is confirmed before the click, judged by the real name of the
/// control: going live joins sending, publishing, sharing, joining and calling, and the words are one data file
/// (src/baxy_mind/data/world_acts.v1.json) read by <see cref="RiskPolicy"/>.
/// </summary>
[TestFixture]
public sealed class RiskPolicyWorldActsTests
{
    // The labels the data file itself gives as asking and as free, read from the copy the kernel embeds.
    private static (string[] Asks, string[] Free) DataExamples()
    {
        using Stream stream = typeof(RiskPolicy).Assembly.GetManifestResourceStream("Baxy.Kernel.WorldActs.json")!;
        using JsonDocument document = JsonDocument.Parse(stream);
        JsonElement examples = document.RootElement.GetProperty("examples");
        return (
            [.. examples.GetProperty("asks").EnumerateArray().Select(item => item.GetString()!)],
            [.. examples.GetProperty("free").EnumerateArray().Select(item => item.GetString()!)]);
    }

    private static PolicyDecision Click(string label, ConfirmationMode mode = ConfirmationMode.Normal)
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("input.visible.click");
        using JsonDocument document = JsonDocument.Parse(JsonSerializer.Serialize(new { label }));
        return RiskPolicy.Evaluate(
            ProductCatalog.ToPolicyRisk(descriptor.Risk), mode, "input.visible.click", document.RootElement);
    }

    // The real controls of v3-53 (OBS) and of the round's order, Spanish and English.
    [TestCase("Iniciar Transmisión", true)]
    [TestCase("Start Streaming", true)]
    [TestCase("Go Live", true)]
    [TestCase("Transmitir", true)]
    [TestCase("Transmitir en vivo", true)]
    [TestCase("Emitir en directo", true)]
    [TestCase("Compartir pantalla", true)]
    [TestCase("Share screen", true)]
    [TestCase("Publicar", true)]
    [TestCase("Publish", true)]
    [TestCase("Enviar comentarios", true)]
    [TestCase("Unirse a la reunión", true)]
    [TestCase("Llamar", true)]
    [TestCase("Iniciar Transmisión (Ctrl+T)", true)]
    // A ribbon's tab named for sending asks too, as it did before this round: so no rule tries it blind
    // (tests/test_cu_v3_despliegue_pertinente.py, v3-07).
    [TestCase("Enviar y recibir", true)]
    // Auditoría de identidad (nb-f4-identidad; 00_IDENTIDAD, aclaración del 2026-10-10: en modo normal confirma lo que
    // sale al mundo, también instalar o desinstalar): a click on an installer's or a store's «Instalar» went unasked
    // (desinstalar already asked). A state, a progress or putting it off installs nothing.
    [TestCase("Instalar", true)]
    [TestCase("Install", true)]
    [TestCase("Instalar ahora", true)]
    [TestCase("Install now", true)]
    [TestCase("Instalar actualizaciones", true)]
    [TestCase("Instalado", false)]
    [TestCase("Installed", false)]
    [TestCase("Instalando…", false)]
    [TestCase("Instalar más tarde", false)]
    [TestCase("Install later", false)]
    [TestCase("Instalar automáticamente las actualizaciones de la aplicación", false)]
    // What stays in the computer, or belongs to another guard: playing is not broadcasting, recording writes a file,
    // «Iniciar sesión» is the account's (the mind's own veto), and the other buttons the model pressed in v3-53 and
    // in v3-08 / v3-09 send nothing out.
    [TestCase("Reproducir", false)]
    [TestCase("Play", false)]
    [TestCase("Grabar macro", false)]
    [TestCase("Iniciar Grabación", false)]
    [TestCase("Start Recording", false)]
    [TestCase("Iniciar Cámara Virtual", false)]
    [TestCase("Iniciar sesión", false)]
    [TestCase("Agregar página", false)]
    [TestCase("Nueva pestaña", false)]
    [TestCase("Dibujar", false)]
    [TestCase("Añadir transición configurable", false)]
    [TestCase("Abrir filtros de la escena", false)]
    [TestCase("Mover abajo", false)]
    [TestCase("Abrir Ajustes", false)]
    [TestCase("Aceptar", false)]
    [TestCase("Detener transmisión", false)]
    [TestCase("Mostrar diálogo de confirmación cuando se inicia una transmisión", false)]
    [TestCase("Grabar automáticamente cuando se transmite", false)]
    [TestCase("Transmisiones recientes", false)]
    public void A_click_that_goes_out_to_the_world_asks_before_it_is_pressed(string label, bool asks)
    {
        Assert.Multiple(() =>
        {
            Assert.That(Click(label), Is.EqualTo(asks ? PolicyDecision.RequireConfirmation : PolicyDecision.Allow));
            Assert.That(Click(label, ConfirmationMode.Bypass), Is.EqualTo(PolicyDecision.Allow));
        });
    }

    // The data's own examples: the contract the policy is held to.
    [Test]
    public void The_examples_of_the_data_ask_and_stay_free_as_they_say()
    {
        (string[] asks, string[] free) = DataExamples();
        Assert.Multiple(() =>
        {
            Assert.That(asks, Has.Length.GreaterThanOrEqualTo(20));
            Assert.That(free, Has.Length.GreaterThanOrEqualTo(20));
            Assert.That(asks.Where(label => Click(label) != PolicyDecision.RequireConfirmation), Is.Empty);
            Assert.That(free.Where(label => Click(label) != PolicyDecision.Allow), Is.Empty);
        });
    }

    // A click by index in another manner (its arrow, its menu) is judged by the same name: opening the list of
    // «Compartir» asked in v3-08 and v3-09, and still does when a step names it; the fix is that no rule opens it blind.
    [TestCase("""{"label":"Iniciar Transmisión","index":46,"window":4660}""", true)]
    [TestCase("""{"label":"Compartir","index":16,"manner":"open","window":4660}""", true)]
    [TestCase("""{"label":"Buscar","search":"directo","choose":"Iniciar transmisión"}""", true)]
    [TestCase("""{"label":"Agregar página","index":40,"window":4660}""", false)]
    [TestCase("""{"label":"Dibujar","index":10,"window":4660}""", false)]
    // Encargo V (banco e2, c7: «en Discord andá al canal Cotele y después en Steam andá a la tienda», the chain's first
    // link): the step that names the voice channel the worker would not press by «cotele» asks; a text channel does not.
    [TestCase("""{"label":"Cotele!!!😎, Canal de voz, Choche","index":60,"window":68208}""", true)]
    [TestCase("""{"label":"Cotele!!!😎, Canal de voz, Choche","window":68208}""", true)]
    [TestCase("""{"label":"general (canal de texto)","index":12,"window":68208}""", false)]
    public void The_exact_invocation_decides(string arguments, bool asks)
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("input.visible.click");
        using JsonDocument document = JsonDocument.Parse(arguments);
        Assert.Multiple(() =>
        {
            Assert.That(OperationArgumentValidator.IsValid(document.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(
                RiskPolicy.Evaluate(
                    ProductCatalog.ToPolicyRisk(descriptor.Risk), ConfirmationMode.Normal, "input.visible.click", document.RootElement),
                Is.EqualTo(asks ? PolicyDecision.RequireConfirmation : PolicyDecision.Allow));
        });
    }

    // The policy reads the label of the invocation; the provider presses a control. When the control's real name asks
    // and the label it was judged by does not, the policy read another name: the provider presses nothing.
    [TestCase("Transmisión", "Iniciar Transmisión", true)]
    [TestCase("General", "General (canal de voz)", true)]
    [TestCase("pruebas", "Eliminar pruebas", true)]
    [TestCase("Cotele", "Cotele!!!😎, Canal de voz, Choche", true)]
    // The label was judged as asking already (the person answered, or the mode is bypass): nothing more to ask.
    [TestCase("Iniciar Transmisión", "Iniciar Transmisión", false)]
    [TestCase("Cotele (canal de voz)", "Cotele!!!😎, Canal de voz, Choche", false)]
    [TestCase("Enviar", "Enviar a Ron92", false)]
    // An ordinary control named by a part of its name is pressed as before.
    [TestCase("Dibujar", "Dibujar", false)]
    [TestCase("Sitio", "Un título largo - Sitio", false)]
    [TestCase("Agregar", "Agregar página", false)]
    [TestCase("", "", false)]
    public void A_pressed_name_that_asks_more_than_its_label_is_told(string label, string pressed, bool more) =>
        Assert.That(RiskPolicy.PressedNameAsksMoreThanItsLabel(label, pressed), Is.EqualTo(more));

    // Encargo V: the one pattern the UIA worker is handed judges every label as the policy does (its words, its verbs,
    // its exceptions, its short labels and its shortcut hints).
    [Test]
    public void The_pattern_handed_to_the_worker_reads_as_the_policy()
    {
        (string[] asks, string[] free) = DataExamples();
        string[] more =
        [
            "Cotele!!!😎, Canal de voz, Choche", "general (canal de texto)", "Eliminar", "Eliminar pruebas", "No guardar",
            "Don't save", "Mover a la papelera", "Vaciar papelera de reciclaje", "Eliminados", "Deleted items",
            "Papelera de reciclaje", "Comprar ahora", "Proceed to checkout", "Realizar pedido", "Quitar de la biblioteca",
            "Vaciar la papelera cuando el disco se llena de archivos viejos", "Limpiar historial", "Clear all",
            "Enviar búsqueda", "Submit search", "En\u200Bviar mensaje", "Desinstalar (Supr)", "Choche, Llamada de voz en curso",
            "Ajustes de voz y video", "Abrir Discord", "Steam", "Tienda", "Deshabilitar todos", "Disable all",
            "Desactivar todo", "Deshabilitado", "Habilitar todos", "Quitar silencio", "Clear filters",
            "Limpiar búsqueda", "Descartar notificación", "Clear search history", "Vaciar papelera", "Descartar cambios",
        ];
        string[] differ =
        [
            .. asks.Concat(free).Concat(more).Where(label =>
                RiskPolicy.LabelAsks(label) != (RiskPolicy.LabelReachesAPerson(label) || RiskPolicy.LabelCannotBeUndone(label))),
        ];
        Assert.Multiple(() =>
        {
            Assert.That(differ, Is.Empty);
            Assert.That(RiskPolicy.LabelAsks("Cotele!!!😎, Canal de voz, Choche"), Is.True);
            Assert.That(RiskPolicy.LabelAsks("general (canal de texto)"), Is.False);
            Assert.That(RiskPolicy.LabelAsks("Eliminar pruebas"), Is.True);
            Assert.That(RiskPolicy.LabelAsks("Vaciar la papelera cuando el disco se llena de archivos viejos"), Is.False);
            // Incidente del 2026-10-15 (msconfig): turning everything off at once asks; a state or the reverse does not.
            Assert.That(RiskPolicy.LabelAsks("Deshabilitar todos"), Is.True);
            Assert.That(RiskPolicy.LabelAsks("Disable all"), Is.True);
            Assert.That(RiskPolicy.LabelAsks("Desactivar todo"), Is.True);
            Assert.That(RiskPolicy.LabelAsks("Deshabilitado"), Is.False);
            Assert.That(RiskPolicy.LabelAsks("Habilitar todos"), Is.False);
            // Decisión del dueño 2026-10-25: over a harmless object the verb does not ask; over a history it still
            // does.
            Assert.That(RiskPolicy.LabelAsks("Quitar silencio"), Is.False);
            Assert.That(RiskPolicy.LabelAsks("Clear filters"), Is.False);
            Assert.That(RiskPolicy.LabelAsks("Clear search history"), Is.True);
        });
    }

    // Encargo V contracases: opening the application asks nothing, and the bypass mode asks nothing, not even to join.
    [Test]
    public void Opening_the_application_or_the_bypass_mode_asks_nothing()
    {
        ProductOperationDescriptor open = ProductCatalog.GetRequired("app.open");
        using JsonDocument discord = JsonDocument.Parse("""{"appId":"discord"}""");
        Assert.Multiple(() =>
        {
            Assert.That(
                RiskPolicy.Evaluate(ProductCatalog.ToPolicyRisk(open.Risk), ConfirmationMode.Normal, "app.open", discord.RootElement),
                Is.EqualTo(PolicyDecision.Allow));
            Assert.That(Click("Cotele!!!😎, Canal de voz, Choche", ConfirmationMode.Bypass), Is.EqualTo(PolicyDecision.Allow));
            Assert.That(Click("Cotele!!!😎, Canal de voz, Choche"), Is.EqualTo(PolicyDecision.RequireConfirmation));
        });
    }

    // Revisión de V (H1): Enter or space on what the step's view says it lands on («onto»: the voice channel the search
    // holds chosen) asks as a click on it would; a text channel or another key does not; bypass never asks. Revisión
    // 2026-10-22 (K-2): no name and no target declares nothing, and then it asks.
    [TestCase("""{"key":"enter","onto":"Cotele!!!😎, Canal de voz, Choche","window":68208}""", true)]
    [TestCase("""{"key":"space","onto":"Cotele (canal de voz)"}""", true)]
    [TestCase("""{"key":"enter","onto":"Eliminar pruebas"}""", true)]
    [TestCase("""{"key":"enter","onto":"general (canal de texto)"}""", false)]
    [TestCase("""{"key":"enter","onto":null}""", true)]
    // Revisión de calidad del núcleo (final2): an empty or blank name declares nothing either.
    [TestCase("""{"key":"enter","onto":""}""", true)]
    [TestCase("""{"key":"space","onto":"  "}""", true)]
    [TestCase("""{"key":"tab","onto":"Cotele!!!😎, Canal de voz, Choche"}""", false)]
    public void A_key_on_what_asks_asks_as_its_click_would(string arguments, bool asks)
    {
        ProductOperationDescriptor descriptor = ProductCatalog.GetRequired("input.key.press");
        using JsonDocument document = JsonDocument.Parse(arguments);
        PolicyDecision Evaluate(ConfirmationMode mode) => RiskPolicy.Evaluate(
            ProductCatalog.ToPolicyRisk(descriptor.Risk), mode, "input.key.press", document.RootElement);
        Assert.Multiple(() =>
        {
            Assert.That(OperationArgumentValidator.IsValid(document.RootElement, descriptor.ArgumentsSchema), Is.True);
            Assert.That(Evaluate(ConfirmationMode.Normal), Is.EqualTo(asks ? PolicyDecision.RequireConfirmation : PolicyDecision.Allow));
            Assert.That(Evaluate(ConfirmationMode.Bypass), Is.EqualTo(PolicyDecision.Allow));
        });
    }

    // Revisión de V (H7): a call named as a setting, a log, a function, a game's title or leaving it is no call; a voice
    // channel whatever its name still is (the exception belongs to the bare words «llamada», «llamar» and «call» only).
    [TestCase("Ajustes de llamada", false)]
    [TestCase("Registro de llamadas", false)]
    [TestCase("Llamar a la función", false)]
    [TestCase("Call Stack", false)]
    [TestCase("Call of Duty®: Black Ops 6", false)]
    [TestCase("Abandonar llamada", false)]
    [TestCase("Leave Call", false)]
    [TestCase("Call of Duty (canal de voz)", true)]
    [TestCase("Ajustes de llamada (canal de voz)", true)]
    [TestCase("Iniciar llamada", true)]
    [TestCase("Llamar", true)]
    [TestCase("Llamada de voz", true)]
    public void A_call_that_is_none_does_not_ask(string label, bool asks)
    {
        Assert.Multiple(() =>
        {
            Assert.That(Click(label), Is.EqualTo(asks ? PolicyDecision.RequireConfirmation : PolicyDecision.Allow));
            Assert.That(RiskPolicy.LabelAsks(label), Is.EqualTo(asks), "the worker's pattern reads it alike");
        });
    }

    // Auditoría del núcleo 2026-10-23: a verb written with look-alike letters (a Cyrillic «Е», a Greek «Ε», full-width
    // letters) asks as the verb does, in the policy and in the worker's pattern; ending a program unsaved asks too.
    [TestCase("Еnviar mensaje", true)]
    [TestCase("Εliminar", true)]
    [TestCase("Ｅｎｖｉａｒ", true)]
    [TestCase("Cоmprar ahora", true)]
    [TestCase("Dеlete", true)]
    [TestCase("Finalizar tarea", true)]
    [TestCase("End task", true)]
    [TestCase("Forzar cierre", true)]
    [TestCase("Force quit", true)]
    [TestCase("Tarea finalizada", false)]
    [TestCase("Открыть", false)]
    public void A_look_alike_or_an_unsaved_end_asks_as_the_verb_does(string label, bool asks)
    {
        Assert.Multiple(() =>
        {
            Assert.That(Click(label), Is.EqualTo(asks ? PolicyDecision.RequireConfirmation : PolicyDecision.Allow));
            Assert.That(RiskPolicy.LabelAsks(label), Is.EqualTo(asks), "the worker's pattern reads it alike");
        });
    }

    // Revisión de calidad del núcleo (final2): a control's name with a sign before its verb («¡Comprar!», «🛒 Comprar
    // ahora», «✉ Enviar») or glued after it («Pagar.», «¡Publicar!») is still that verb; the noun that only shares its
    // stem still is not.
    [TestCase("¡Comprar!", true)]
    [TestCase("🛒 Comprar ahora", true)]
    [TestCase("¡Cómpralo ya!", true)]
    [TestCase("Pagar.", true)]
    [TestCase("Buy!", true)]
    [TestCase("✉ Enviar", true)]
    [TestCase("¿Enviar ahora?", true)]
    [TestCase("¡Publicar!", true)]
    [TestCase("▶ Unirse", true)]
    [TestCase("¡Compras!", false)]
    [TestCase("(Enviados)", false)]
    [TestCase("★ Publicaciones", false)]
    public void A_sign_around_the_verb_does_not_hide_it(string label, bool asks)
    {
        Assert.Multiple(() =>
        {
            Assert.That(Click(label), Is.EqualTo(asks ? PolicyDecision.RequireConfirmation : PolicyDecision.Allow));
            Assert.That(RiskPolicy.LabelAsks(label), Is.EqualTo(asks), "the worker's pattern reads it alike");
        });
    }
}
