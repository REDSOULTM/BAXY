using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Web.WebView2.Core;

namespace Baxy.App;

/// <summary>
/// Escribe en el compositor real de la ventana y lee lo que la ventana muestra.
///
/// El conductor recorre la misma tubería pública pero sin ventana, así que no
/// acredita que la persona vea y entienda la respuesta. Sin esta pieza, la
/// única prueba de interfaz posible era el título de la ventana. La sonda no
/// abre ninguna vía nueva al producto: teclea en el mismo `input` que usa una
/// persona, envía el mismo formulario y lee el mismo DOM.
///
/// Sólo se activa con <c>--ui-probe</c> en un arranque de desarrollo.
/// </summary>
internal static class FieldUiProbe
{
    internal const string TurnsArgument = "--ui-probe";
    internal const string CaptureArgument = "--ui-capture";

    /// <summary>Escribe el texto en el input de React y envía el formulario.</summary>
    private const string SendScript = """
        (function (text) {
          const input = document.querySelector('input[aria-label="message input"]');
          if (!input) { return 'no_input'; }
          if (input.disabled) { return 'input_disabled'; }
          const setter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value').set;
          setter.call(input, text);
          input.dispatchEvent(new Event('input', { bubbles: true }));
          const form = input.closest('form');
          if (!form) { return 'no_form'; }
          form.requestSubmit
            ? form.requestSubmit()
            : form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
          return 'sent';
        })
        """;

    /// <summary>Lee las líneas que la ventana está mostrando ahora mismo.</summary>
    private const string ReadScript = """
        (function () {
          const rows = Array.from(document.querySelectorAll('.activity-scroll .act'));
          return JSON.stringify(rows.map(function (row) {
            const src = row.querySelector('.src');
            const msg = row.querySelector('.msg');
            const ts = row.querySelector('.ts');
            return {
              src: src ? src.textContent : '',
              msg: msg ? msg.textContent : '',
              ts: ts ? ts.textContent : ''
            };
          }));
        })()
        """;

    internal static bool IsRequested(IReadOnlyList<string> arguments)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        foreach (string argument in arguments)
        {
            if (argument.StartsWith(TurnsArgument, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return false;
    }

    internal static string? ValueOf(IReadOnlyList<string> arguments, string name)
    {
        ArgumentNullException.ThrowIfNull(arguments);
        for (int index = 0; index < arguments.Count; index++)
        {
            string argument = arguments[index];
            if (argument.StartsWith(name + "=", StringComparison.OrdinalIgnoreCase))
            {
                return argument[(name.Length + 1)..];
            }

            if (string.Equals(argument, name, StringComparison.OrdinalIgnoreCase)
                && index + 1 < arguments.Count)
            {
                return arguments[index + 1];
            }
        }

        return null;
    }

    internal static async Task RunAsync(
        CoreWebView2 core,
        IReadOnlyList<string> arguments,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(core);
        ArgumentNullException.ThrowIfNull(arguments);
        string? turnsPath = ValueOf(arguments, TurnsArgument);
        if (string.IsNullOrWhiteSpace(turnsPath) || !File.Exists(turnsPath))
        {
            return;
        }

        string capturePath = ValueOf(arguments, CaptureArgument)
            ?? Path.Combine(Path.GetDirectoryName(turnsPath)!, "ui-probe.jsonl");
        Directory.CreateDirectory(Path.GetDirectoryName(capturePath)!);
        await using var writer = new StreamWriter(capturePath, append: false);

        await WriteAsync(
            writer,
            new JsonObject
            {
                ["type"] = "meta",
                ["process"] = "Baxy.exe",
                ["pid"] = Environment.ProcessId,
                ["entry"] = "py main.py --ui-probe",
            });

        // La ventana habilita el input al terminar el arranque. Sin esa espera
        // se estaría midiendo el arranque, no la conversación.
        if (!await WaitForInputAsync(core, TimeSpan.FromMinutes(3), cancellationToken))
        {
            await WriteAsync(
                writer,
                new JsonObject
                {
                    ["type"] = "terminal",
                    ["kind"] = "blocked_environment",
                    ["diagnostic"] = "input_never_enabled",
                });
            return;
        }

        foreach (string line in await File.ReadAllLinesAsync(turnsPath, cancellationToken))
        {
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            JsonNode? command = JsonNode.Parse(line);
            string text = (string?)command?["text"] ?? string.Empty;
            if (text.Length == 0)
            {
                continue;
            }

            int before = await CountRowsAsync(core, cancellationToken);
            string sent = await core.ExecuteScriptAsync(
                $"({SendScript})({JsonSerializer.Serialize(text)})");
            bool published = await WaitForNewRowAsync(
                core,
                before + 2,
                TimeSpan.FromMinutes(3),
                cancellationToken);
            JsonNode? rows = JsonNode.Parse(
                JsonSerializer.Deserialize<string>(
                    await core.ExecuteScriptAsync(ReadScript)) ?? "[]");
            await WriteAsync(
                writer,
                new JsonObject
                {
                    ["type"] = "ui.turn",
                    ["text"] = text,
                    ["send"] = sent.Trim('"'),
                    ["published"] = published,
                    ["rendered"] = rows?.DeepClone(),
                });
        }

        await WriteAsync(writer, new JsonObject { ["type"] = "terminal", ["kind"] = "done" });
    }

    private static async Task<bool> WaitForInputAsync(
        CoreWebView2 core,
        TimeSpan budget,
        CancellationToken cancellationToken)
    {
        DateTime deadline = DateTime.UtcNow + budget;
        while (DateTime.UtcNow < deadline)
        {
            cancellationToken.ThrowIfCancellationRequested();
            string ready = await core.ExecuteScriptAsync(
                "(function(){const i=document.querySelector('input[aria-label=\"message input\"]');"
                + "return i && !i.disabled ? 'yes' : 'no';})()");
            if (ready.Contains("yes", StringComparison.Ordinal))
            {
                return true;
            }

            await Task.Delay(TimeSpan.FromMilliseconds(500), cancellationToken);
        }

        return false;
    }

    private static async Task<int> CountRowsAsync(
        CoreWebView2 core,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        string count = await core.ExecuteScriptAsync(
            "document.querySelectorAll('.activity-scroll .act').length");
        return int.TryParse(
            count.Trim('"'),
            NumberStyles.Integer,
            CultureInfo.InvariantCulture,
            out int parsed)
            ? parsed
            : 0;
    }

    private static async Task<bool> WaitForNewRowAsync(
        CoreWebView2 core,
        int expected,
        TimeSpan budget,
        CancellationToken cancellationToken)
    {
        DateTime deadline = DateTime.UtcNow + budget;
        while (DateTime.UtcNow < deadline)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (await CountRowsAsync(core, cancellationToken) >= expected)
            {
                return true;
            }

            await Task.Delay(TimeSpan.FromMilliseconds(400), cancellationToken);
        }

        return false;
    }

    private static async Task WriteAsync(StreamWriter writer, JsonObject payload)
    {
        await writer.WriteLineAsync(payload.ToJsonString());
        await writer.FlushAsync();
    }
}
