from hireburn._io import load_yaml, md_table, pct


def test_yaml_subset():
    doc = load_yaml("""
# comment
name: Example  # trailing comment
n: 5
ratio: 0.5
flag: true
empty:
inline: [a, "b c", 3]
flow: {}
nested:
  list:
    - one
    - id: q1
      text: "Hello: world"
      max: 1
    - id: q2
      text: plain text: with colon
text: |
  line one
  line two
folded: >-
  a
  b
""")
    assert doc["name"] == "Example" and doc["n"] == 5 and doc["ratio"] == 0.5 and doc["flag"] is True
    assert doc["empty"] is None and doc["inline"] == ["a", "b c", 3] and doc["flow"] == {}
    assert doc["nested"]["list"][0] == "one"
    assert doc["nested"]["list"][1] == {"id": "q1", "text": "Hello: world", "max": 1}
    assert doc["nested"]["list"][2]["text"] == "plain text: with colon"
    assert doc["text"] == "line one\nline two\n"
    assert doc["folded"] == "a b"


def test_yaml_list_at_key_indent():
    assert load_yaml("a:\n- 1\n- 2\nb: x\n") == {"a": [1, 2], "b": "x"}


def test_md_table_and_pct():
    t = md_table(["a", "b"], [["x", 1]])
    assert t.splitlines()[0].startswith("| a") and "---" in t
    assert pct(1, 4) == "25.0%" and pct(1, 0) == "—"


def test_flow_map():
    assert load_yaml("a: {x: 1, y: [p, q], z: 'k, l'}\n") == {"a": {"x": 1, "y": ["p", "q"], "z": "k, l"}}
