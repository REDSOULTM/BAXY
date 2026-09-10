"""K2 native transport with the original schema made explicit to the model."""
import copy
import json
import threading

from baxy_mind import llm
import c03_k2_native_adapter732 as native


def schema_messages(wire):
    envelope = wire.get("response_format", {}).get("json_schema")
    if not isinstance(envelope, dict) or envelope.get("strict") is not True:
        return wire
    schema = envelope.get("schema")
    if not isinstance(schema, dict):
        return wire
    message = {
        "role": "system",
        "content": (
            "Return your final answer as one JSON object matching this schema. "
            "Put the answer in the final response, not only in reasoning. "
            "Do not add text outside the final JSON object. JSON Schema: "
            + json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        ),
    }
    messages = wire.get("messages", [])
    position = 0
    while position < len(messages) and messages[position].get("role") == "system":
        position += 1
    return {**wire, "messages": [*messages[:position], message, *messages[position:]]}


def install(private, model, endpoint):
    original_adapt = native.adapt_payload
    original_schema_post = llm.LlmRuntime._post_schema_object
    state = threading.local()

    def adapt(payload):
        wire = original_adapt(payload)
        original = getattr(state, "schema_payload", None)
        if original is not None and "grammar" in wire:
            compact = llm._compact_structured_grammar(original)
            if compact is not None and wire["grammar"] == compact:
                wire.pop("grammar")
                wire["response_format"] = copy.deepcopy(original["response_format"])
        return schema_messages(wire)

    def schema_post(self, payload, label):
        previous = getattr(state, "schema_payload", None)
        state.schema_payload = payload
        try:
            return original_schema_post(self, payload, label)
        finally:
            state.schema_payload = previous

    native.adapt_payload = adapt
    llm.LlmRuntime._post_schema_object = schema_post
    uninstall_native = native.install(private, model, endpoint)

    def uninstall():
        uninstall_native()
        assert llm.LlmRuntime._post_schema_object is schema_post
        assert native.adapt_payload is adapt
        llm.LlmRuntime._post_schema_object = original_schema_post
        native.adapt_payload = original_adapt

    return uninstall
