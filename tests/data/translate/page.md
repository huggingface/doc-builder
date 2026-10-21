# Hydration check

A paragraph of prose with a [link](https://huggingface.co) and `inline code`.

## Options

Text of the first option.

Text of the second option.

## API[[hydrationlib.tokenize]]

#### hydrationlib.tokenize[[hydrationlib.tokenize]]

```python
hydrationlib.tokenize(text, padding = False)
```

[Source](https://github.com/huggingface/hydrationlib/blob/main/src/hydrationlib/__init__.py#L6)

**Parameters:**

text (`str`) : The text to tokenize.  A second paragraph, so the parameter description has more than one paragraph.

padding (`bool`, *optional*, defaults to `False`) : Whether to pad the output.

**Returns:** `list[int]`

A list of integers in the range [0, 1].

1 for a special token, 0 for a sequence token.

**Raises:** ``ValueError``

- ``ValueError`` -- If the text is empty.

Turn a text into token ids.

