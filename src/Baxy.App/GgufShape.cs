using System.Buffers.Binary;
using System.IO;
using System.Text;

namespace Baxy.App;

/// <summary>
/// What a GGUF's header says about the memory its model takes beside its weights (ModelMemory): its layers, which of
/// them keep a KV cache and how wide it is, the window of those that slide, its recurrent state, and the size of its
/// token embedding. Read from the header alone (the GGUF specification, docs/gguf.md in ggml's repository: magic, version,
/// counts, then key-value pairs, then each tensor's name, shape, type and offset), from a file or from the first bytes
/// of one on Hugging Face (an HTTP range): the architecture's own keys come before the tokenizer's, so a search reads a
/// few KB of each model and stops.
/// </summary>
internal sealed record GgufShape(
    string Architecture,
    int Layers,
    int ContextLength,
    int Embedding,
    int FeedForward,
    int FullLayers,
    long FullCellValues,
    int SlidingLayers,
    long SlidingCellValues,
    int SlidingWindow,
    long LayerCellValues,
    long RecurrentValues,
    long? TokenEmbeddingBytes)
{
    // A header past this is not read: the largest seen (Qwen3.5-4B's, 248k tokens and their merges) ends at 10.5 MiB.
    private const long MostHeaderBytes = 64L << 20;

    /// <summary>The shape a GGUF file's header gives, with its token embedding's size; null when it is not one.</summary>
    internal static GgufShape? Read(string path)
    {
        try
        {
            using var file = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete, 1 << 16);
            return Read(file, tensors: true);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return null;
        }
    }

    /// <summary>
    /// The shape <paramref name="stream"/>'s header gives; null when it is not a GGUF this reads or it ends before the
    /// architecture is told. With <paramref name="tensors"/> it reads on through the tokenizer to the tensors for the
    /// token embedding's size; without, it stops at the first tokenizer key once the architecture's are read.
    /// </summary>
    internal static GgufShape? Read(Stream stream, bool tensors)
    {
        try
        {
            var reader = new Reader(stream);
            if (reader.Bytes(4) is not [(byte)'G', (byte)'G', (byte)'U', (byte)'F'] || reader.U32() is < 2 or > 3)
            {
                return null;
            }

            ulong tensorCount = reader.U64();
            ulong keyCount = reader.U64();
            var keys = new Dictionary<string, object>(StringComparer.Ordinal);
            string? architecture = null;
            for (ulong index = 0; index < keyCount; index++)
            {
                string key = reader.Text();
                if (!tensors && architecture is not null && key.StartsWith("tokenizer.", StringComparison.Ordinal)
                    && keys.ContainsKey(architecture + ".block_count"))
                {
                    return From(keys, architecture, null);
                }

                object? value = reader.Value(reader.U32());
                if (value is not null)
                {
                    keys[key] = value;
                }

                if (key == "general.architecture")
                {
                    architecture = value as string;
                }
            }

            if (architecture is null)
            {
                return null;
            }

            long? embedding = null;
            for (ulong index = 0; tensors && index < tensorCount; index++)
            {
                string name = reader.Text();
                uint dimensions = reader.U32();
                long elements = 1;
                for (uint dimension = 0; dimension < dimensions; dimension++)
                {
                    elements *= (long)reader.U64();
                }

                uint type = reader.U32();
                _ = reader.U64();
                if (name == "token_embd.weight")
                {
                    embedding = TensorBytes(type, elements);
                    break;
                }
            }

            return From(keys, architecture, embedding);
        }
        catch (Exception exception) when (exception is EndOfStreamException or IOException or InvalidDataException or OverflowException)
        {
            return null;
        }
    }

    private static GgufShape? From(Dictionary<string, object> keys, string architecture, long? tokenEmbedding)
    {
        long[]? Numbers(string name) => keys.TryGetValue(architecture + "." + name, out object? value) ? value switch
        {
            long one => [one],
            long[] many => many,
            _ => null,
        } : null;
        long Number(string name, long otherwise) => Numbers(name) is [var one, ..] ? one : otherwise;

        int layers = (int)Number("block_count", 0);
        long[]? heads = Numbers("attention.head_count");
        if (layers <= 0 || heads is null)
        {
            return null;
        }

        long embedding = Number("embedding_length", 0);
        long Each(long[] values, int layer) => values.Length == layers ? values[layer] : values[0];
        long[] kvHeads = Numbers("attention.head_count_kv") ?? heads;
        long headWidth = heads[0] > 0 ? embedding / heads[0] : 0;
        long keyWidth = Number("attention.key_length", headWidth);
        long valueWidth = Number("attention.value_length", headWidth);
        // Qwen3-Next and Qwen3.5 keep a cache in every interval-th layer and a recurrent state in the others
        // (llama-model.cpp, hparams.recurrent_layer_arr); elsewhere a layer with no KV heads is a recurrent one.
        long interval = Number("full_attention_interval", 0);
        long window = Number("attention.sliding_window", 0);
        long[]? sliding = Numbers("attention.sliding_window_pattern");
        bool hasState = keys.ContainsKey(architecture + ".ssm.state_size");
        int full = 0, slides = 0, recurrent = 0;
        long fullValues = 0, slidingValues = 0, widest = 0;
        for (int layer = 0; layer < layers; layer++)
        {
            long values = Each(kvHeads, layer) * (keyWidth + valueWidth);
            bool attends = interval > 0 ? (layer + 1) % interval == 0 : values > 0;
            if (!attends)
            {
                recurrent++;
                continue;
            }

            widest = Math.Max(widest, values);
            if (window > 0 && Slides(architecture, sliding, layer))
            {
                slides++;
                slidingValues += values;
            }
            else
            {
                full++;
                fullValues += values;
            }
        }

        // A model whose every layer attends and also keeps a state (a parallel hybrid) keeps it in all of them.
        if (hasState && recurrent == 0)
        {
            recurrent = layers;
        }

        // The recurrent state per layer and sequence, as llama.cpp sizes it (llama-hparams.cpp, n_embd_r and n_embd_s): the
        // convolution's (kernel - 1) × (inner + 2 × groups × state) values and the state's state × inner, in f32.
        long kernel = Number("ssm.conv_kernel", 0), state = Number("ssm.state_size", 0), inner = Number("ssm.inner_size", 0);
        long groups = Number("ssm.group_count", 0);
        long stateValues = hasState ? (Math.Max(kernel - 1, 0) * (inner + (2 * groups * state))) + (state * inner) : 0;
        long feedForward = Math.Max(Numbers("feed_forward_length")?.Max() ?? 0,
            Number("expert_feed_forward_length", 0) * Math.Max(Number("expert_used_count", 1), 1));
        return new GgufShape(architecture, layers, (int)Math.Min(Number("context_length", 0), int.MaxValue), (int)embedding,
            (int)feedForward, full, fullValues, slides, slidingValues, (int)window, widest, recurrent * stateValues, tokenEmbedding);
    }

    // Which layers slide: the GGUF's own pattern when it has one (true for a sliding layer), or llama.cpp's for the
    // architectures that set theirs in code (llama-model.cpp, hparams.set_swa_pattern: Gemma 2 and gpt-oss every other
    // layer from the first, Gemma 3 five of every six). Any other with a window and no pattern is counted whole: never less.
    private static bool Slides(string architecture, long[]? pattern, int layer) => pattern is { Length: > 0 }
        ? pattern[layer % pattern.Length] != 0
        : architecture switch
        {
            "gemma2" or "gpt-oss" => layer % 2 == 0,
            "gemma3" => (layer + 1) % 6 != 0,
            _ => false,
        };

    // ggml's block sizes (ggml.c, type_traits: bytes per block and values per block), for the token embedding; an
    // unknown type is null, and nothing is taken off for it.
    private static long? TensorBytes(uint type, long elements)
    {
        (long Bytes, long Values)? block = type switch
        {
            0 => (4, 1), 1 => (2, 1), 30 => (2, 1),
            2 => (18, 32), 3 => (20, 32), 6 => (22, 32), 7 => (24, 32), 8 => (34, 32), 20 => (18, 32),
            10 => (84, 256), 11 => (110, 256), 12 => (144, 256), 13 => (176, 256), 14 => (210, 256), 23 => (136, 256),
            _ => null,
        };
        return block is { } size ? elements / size.Values * size.Bytes : null;
    }

    /// <summary>The header's little-endian values, read in order with nothing kept but what a key holds.</summary>
    private sealed class Reader(Stream stream)
    {
        private readonly byte[] _eight = new byte[8];
        private long _read;

        internal byte[] Bytes(int count)
        {
            if (count < 0 || _read + count > MostHeaderBytes)
            {
                throw new InvalidDataException("the GGUF header is larger than expected");
            }

            byte[] bytes = count <= 8 ? _eight[..count] : new byte[count];
            stream.ReadExactly(bytes);
            _read += count;
            return bytes;
        }

        internal uint U32() => BinaryPrimitives.ReadUInt32LittleEndian(Bytes(4));

        internal ulong U64() => BinaryPrimitives.ReadUInt64LittleEndian(Bytes(8));

        internal string Text() => Encoding.UTF8.GetString(Bytes(checked((int)U64())));

        // A number as a long, an array of numbers as a long[], a string as itself; what this does not use (floats, booleans
        // and arrays of strings, the tokenizer's) is read past and given as null.
        internal object? Value(uint type)
        {
            switch (type)
            {
                case 8:
                    return Text();
                case 9:
                {
                    uint inner = U32();
                    long count = checked((long)U64());
                    if (inner == 8)
                    {
                        for (long index = 0; index < count; index++)
                        {
                            _ = Bytes(checked((int)U64()));
                        }

                        return null;
                    }

                    var values = new long[count <= 4096 ? count : 0];
                    for (long index = 0; index < count; index++)
                    {
                        long? value = Number(inner);
                        if (index < values.Length)
                        {
                            values[index] = value ?? 0;
                        }
                    }

                    return values.Length == count ? values : null;
                }

                default:
                    return Number(type);
            }
        }

        private long? Number(uint type) => type switch
        {
            0 => Bytes(1)[0],
            1 => (sbyte)Bytes(1)[0],
            2 => BinaryPrimitives.ReadUInt16LittleEndian(Bytes(2)),
            3 => BinaryPrimitives.ReadInt16LittleEndian(Bytes(2)),
            4 => U32(),
            5 => BinaryPrimitives.ReadInt32LittleEndian(Bytes(4)),
            6 => Skip(4),
            7 => Bytes(1)[0],
            10 => checked((long)U64()),
            11 => BinaryPrimitives.ReadInt64LittleEndian(Bytes(8)),
            12 => Skip(8),
            _ => throw new InvalidDataException($"unknown GGUF value type {type}"),
        };

        private long? Skip(int count)
        {
            _ = Bytes(count);
            return null;
        }
    }
}
