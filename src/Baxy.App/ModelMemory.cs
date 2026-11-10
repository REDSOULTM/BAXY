namespace Baxy.App;

/// <summary>
/// Encargo del dueño 2026-11-08: «que se calcule bien la VRAM total que va a usar el modelo para nunca mentir». The one
/// estimate of what a model takes on the graphics card, for every place BAXY says it: Hugging Face's results before a
/// download, the context options of an Ollama model, and the context options of BAXY's own model. It is the sum of what
/// llama.cpp allocates on the GPU and what the CUDA runtime takes beside it:
/// <list type="bullet">
/// <item>The weights: the file, less the token embedding when the output matrix is kept in RAM (llm_server.OUTPUT_ON_CPU).
/// llama.cpp keeps the input's copy in RAM and, when the output is tied to it, a second copy on the GPU (both measured).</item>
/// <item>The KV cache: each layer that keeps one, KV heads × (key width + value width) values a cell at the cache's type,
/// for the context rounded up to 256 cells; a sliding layer keeps its window and one batch (llama-kv-cache-iswa.cpp).</item>
/// <item>The recurrent state of a hybrid model, in f32, per sequence (GgufShape.RecurrentValues).</item>
/// <item>The compute buffer, bounded above: the batch's activations, 4 bytes × 512 × (3 × FFN + 6 × embedding), and per
/// cell an f16 copy of the widest layer's K and V (flash attention reads a quantized cache that way) and the f16 mask.</item>
/// <item>The CUDA context and cuBLAS, which llama.cpp does not count: 116-134 MiB measured beside its own count on an RTX
/// 3060 Laptop, 144 on an RTX 4060 Ti; Ollama's own size leaves out 120-124. 256 are counted.</item>
/// <item>A vision projector on the GPU: its file and 320 MiB for reading an image (223 + 54 measured with Qwen3.5's, 121 +
/// 61 with Gemma 3's).</item>
/// </list>
/// Measured 2026-11-08 on the notebook (RTX 3060 Laptop 6 GB, llama.cpp b11609, the product's arguments, nvidia-smi after
/// loading, after a prompt of up to 47k tokens and after an image): Qwen3.5-4B at 8,192-77,824 cells with and without its
/// projector, with the output in RAM and on the GPU, Qwen3-1.7B, Llama-3.2-3B and Gemma-3-4B (sliding window), and Ollama
/// 0.40.15 with Llama-3.2-3B and Qwen3.5-4B (an f16 cache): every estimate was above or equal to what was measured, 3 to
/// 10 % over (documentacion/VRAM_ESTIMADA.md).
/// </summary>
internal static class ModelMemory
{
    internal const long MiB = 1L << 20;

    // llama.cpp's micro-batch (-ub, 512 by default): the activations the compute buffer holds at once.
    internal const int MicroBatch = 512;

    // What the CUDA runtime takes beside llama.cpp's own buffers (see above).
    internal const long RuntimeBytes = 256 * MiB;

    // What reading an image takes beside the projector's file (see above).
    internal const long ProjectorComputeBytes = 320 * MiB;

    /// <summary>
    /// The bytes on the card for a model of <paramref name="shape"/> in a file of <paramref name="fileBytes"/>, at
    /// <paramref name="context"/> cells with a cache of <paramref name="kv"/> (llama.cpp's -ctk/-ctv: f16, q8_0, q5_1,
    /// q5_0, q4_1, q4_0), <paramref name="sequences"/> slots, the output in RAM or not, and a projector of
    /// <paramref name="projectorBytes"/> (0 for none) on the card.
    /// </summary>
    internal static long GpuBytes(GgufShape shape, long fileBytes, int context, string kv, bool outputInRam = false,
        long projectorBytes = 0, int sequences = 1)
    {
        ArgumentNullException.ThrowIfNull(shape);
        long cells = (Math.Max(context, 1) + 255L) / 256 * 256;
        long weights = fileBytes - (outputInRam ? shape.TokenEmbeddingBytes ?? 0 : 0);
        // A sliding layer keeps its window and a batch, rounded up to 256 cells as well (gpt-oss: 128 + 512 → 768, measured).
        long sliding = Math.Min(cells, (shape.SlidingWindow + (long)MicroBatch + 255) / 256 * 256);
        double cache = ((shape.FullCellValues * cells) + (shape.SlidingCellValues * sliding)) * CacheBytesPerValue(kv);
        long state = shape.RecurrentValues * 4 * Math.Max(sequences, 1);
        long compute = (4L * MicroBatch * ((3L * shape.FeedForward) + (6L * shape.Embedding)))
            + (cells * ((2 * shape.LayerCellValues) + (2 * MicroBatch)));
        return weights + (long)Math.Ceiling(cache) + state + compute + RuntimeBytes + ProjectorGpuBytes(projectorBytes);
    }

    /// <summary>
    /// Encargo del dueño 2026-11-08 («en recomendado debería de ser por default el contexto que ya trae el modelo»): the context
    /// to run a model with on this card. Its own (<paramref name="native"/>, its GGUF's &lt;arch&gt;.context_length) when the VRAM
    /// <paramref name="free"/> holds it («nativo»); else the most that does, in steps of 1,024 («tarjeta»); never under
    /// <paramref name="needs"/>, what BAXY's prompt takes («minimo_baxy» when the model declares less, «no_cabe» when not even
    /// that fits). With the free VRAM not known, its own. <paramref name="bytesAt"/> is the VRAM at a context.
    /// </summary>
    internal static (int Context, string Why) Recommend(Func<int, long> bytesAt, int native, int needs, long? free)
    {
        ArgumentNullException.ThrowIfNull(bytesAt);
        int top = Math.Max(native, needs);
        string whole = native >= needs ? "nativo" : "minimo_baxy";
        if (free is not { } room || bytesAt(top) <= room)
        {
            return (top, whole);
        }

        if (bytesAt(needs) > room)
        {
            return (needs, "no_cabe");
        }

        // The VRAM grows with the context: the most that fits, by halves.
        int low = needs, high = top;
        while (high - low > 1024)
        {
            int middle = low + ((high - low) / 2);
            if (bytesAt(middle) <= room)
            {
                low = middle;
            }
            else
            {
                high = middle;
            }
        }

        return (Math.Max(needs, low / 1024 * 1024), "tarjeta");
    }

    /// <summary>
    /// The view's context: <c>{ native, recommended, why, options: [{ tokens, vramBytes, fitsCard }] }</c>, each option among
    /// <paramref name="choices"/> (and the recommended one) up to the model's own or BAXY's least, <c>fitsCard</c> null with
    /// the free VRAM not known.
    /// </summary>
    internal static System.Text.Json.Nodes.JsonObject ContextJson(Func<int, long> bytesAt, int native, int needs, long? free, IEnumerable<int> choices)
    {
        (int recommended, string why) = Recommend(bytesAt, native, needs, free);
        int top = Math.Max(native, needs);
        var options = new System.Text.Json.Nodes.JsonArray();
        foreach (int tokens in choices.Append(recommended).Append(top).Where(tokens => tokens >= needs && tokens <= top).Distinct().Order())
        {
            long vram = bytesAt(tokens);
            options.Add(new System.Text.Json.Nodes.JsonObject
            {
                ["tokens"] = tokens,
                ["vramBytes"] = vram,
                ["fitsCard"] = free is { } room ? vram <= room : null,
            });
        }

        return new System.Text.Json.Nodes.JsonObject
        {
            ["native"] = native > 0 ? native : null,
            ["recommended"] = recommended,
            ["why"] = why,
            ["options"] = options,
        };
    }

    // What Windows must be able to promise to load a model whole on the card, beside its VRAM, as the translator checks it
    // (external_model.COMMIT_HOST and MEMORY_RESERVE; ModelMemoryTests holds them equal). Measured on the PC on 2026-11-09 (six
    // loads whole on an RTX 4060 Ti): the commit charge grew 1:1 with the card (WDDM backs video memory with system memory) and
    // 0.9-2.4 GiB more of the process's own; 3 GiB are left for the person's programs.
    internal const long CommitHostBytes = (long)(2.75 * (1L << 30));
    internal const long CommitReserveBytes = 3L << 30;

    /// <summary>What Windows must be able to promise for a model that takes <paramref name="vramBytes"/> whole on the card.</summary>
    internal static long RamBytes(long vramBytes) => vramBytes + CommitHostBytes + CommitReserveBytes;

    /// <summary>
    /// How much a model may take on the card: the VRAM free, and no more than what Windows can promise allows
    /// (<see cref="RamBytes"/>). The one room the search and a connection recommend a context by; null with neither known.
    /// </summary>
    internal static long? Room(long? freeVram, long? commitFree)
    {
        long? byRam = commitFree is { } promise ? promise - CommitHostBytes - CommitReserveBytes : null;
        return (freeVram, byRam) switch
        {
            ({ } card, { } ram) => Math.Min(card, ram),
            ({ } card, null) => card,
            (null, { } ram) => ram,
            _ => null,
        };
    }

    /// <summary>What a vision projector of <paramref name="fileBytes"/> takes on the card beside its model (0 for none).</summary>
    internal static long ProjectorGpuBytes(long fileBytes) => fileBytes > 0 ? fileBytes + ProjectorComputeBytes : 0;

    /// <summary>The bytes a cache of this type keeps per value (ggml's q8_0 is 34 bytes per 32 values, and so on).</summary>
    internal static double CacheBytesPerValue(string kv) => kv switch
    {
        "f16" or "bf16" => 2,
        "q8_0" => 34 / 32.0,
        "q5_1" => 24 / 32.0,
        "q5_0" => 22 / 32.0,
        "q4_1" => 20 / 32.0,
        "q4_0" => 18 / 32.0,
        _ => 4,
    };
}
