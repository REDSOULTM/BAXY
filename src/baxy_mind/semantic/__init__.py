"""BAXY's semantic layer: everything that decides what the person meant, in one place.

``documentacion/SEMANTICA.md`` is the map. Modules:

- ``normalize``  the single fold every reader shares.
- ``lexicon``    each domain's nouns and verbs, said once and imported by every stage that reads them.
- ``dialogue``   the dialogue slot: when a message depends on the previous turn and how it is rearmed.
"""
