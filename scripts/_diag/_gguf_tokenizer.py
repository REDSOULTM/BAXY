"""Reconstruye un tokenizer Unigram (SentencePiece) desde el GGUF de Gemma 4 E2B.

El GGUF (llama_cpp 0.3.17 no conoce 'gemma4') guarda el vocab completo:
tokens, scores (unigram logprobs), token_type. Con eso armamos un
tokenizers.Tokenizer(Unigram) equivalente al SP de Gemma para CONTAR tokens
con fidelidad (no estimación 4c/token).

token_type GGUF: 1=NORMAL 2=UNKNOWN 3=CONTROL 4=USER_DEFINED 6=BYTE.
"""
import functools

GGUF_PATH = (r"C:\Users\usuario\Desktop\ETC\Programacion\Probando Gemma 4"
             r"\models\E2B\gemma-4-E2B-it-Q4_K_M.gguf")


@functools.lru_cache(maxsize=1)
def _build():
    import gguf
    from tokenizers import Tokenizer, decoders
    from tokenizers.models import Unigram
    from tokenizers.pre_tokenizers import Metaspace as PreMetaspace

    r = gguf.GGUFReader(GGUF_PATH)
    f_tok = r.get_field("tokenizer.ggml.tokens")
    f_sc = r.get_field("tokenizer.ggml.scores")
    f_tt = r.get_field("tokenizer.ggml.token_type")

    tokens = [bytes(f_tok.parts[i]).decode("utf-8", "replace") for i in f_tok.data]
    scores = [float(f_sc.parts[i][0]) for i in f_sc.data]
    ttypes = [int(f_tt.parts[i][0]) for i in f_tt.data]

    # Construir el vocab Unigram. Para BYTE tokens (type 6) el string GGUF es
    # "<0xNN>"; el SP los trata como tokens normales con su score. Unigram de
    # HF los maneja como entradas comunes. byte_fallback=True permite que
    # cualquier byte no cubierto caiga a <0xNN>.
    vocab = list(zip(tokens, scores))

    unk_id = None
    for i, tt in enumerate(ttypes):
        if tt == 2:  # UNKNOWN
            unk_id = i
            break

    model = Unigram(vocab, unk_id=unk_id, byte_fallback=True)
    tok = Tokenizer(model)
    # Gemma/SP: prefijo de espacio con metaspace "▁", add_prefix_space.
    tok.pre_tokenizer = PreMetaspace(replacement="▁", prepend_scheme="always")
    tok.decoder = decoders.Metaspace(replacement="▁", prepend_scheme="always")
    return tok


def count(text: str) -> int:
    return len(_build().encode(text, add_special_tokens=False).ids)


if __name__ == "__main__":
    # sanity check vs SentencePiece oficial si está
    samples = [
        "Hola, ¿cómo estás?",
        "subí el volumen al 50 por ciento",
        "abre spotify y pon rock nacional de los 90",
    ]
    for s in samples:
        print(f"{count(s):>4}  {s!r}")
