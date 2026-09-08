# Markdown regression cases

Plain prose must remain visible to translation, including punctuation and Unicode 😀.

## Fences

```python
print("A longer closing fence is valid")
````

```"
The quote is the fence's info string.
```

``````
[rank0]: This stays inside the code block.
``````

Read this paragraph after the fences.

## Links

Read [a parenthesized destination](https://example.org/Guide_(detail)) and [the report][paper].

[paper]: https://example.org/report "Report title"

The unfinished destination is [here](<INSERT LINK HERE>).

[![Open notebook](badge.svg)](notebook.ipynb) [![Read guide](guide.svg)](guide.md)

## Math

The perplexity is $\exp(-\frac{1}{t}\sum_i \log p(x_i))$, with text on both sides.

$$
p(x) = \prod_i p(x_i \mid x_{<i})
$$

## API

[[autodoc]] BertModel

    - forward
    - all

Read the [`BertModel`] reference and the prose below.

## Components

<div class="flex justify-center">
  <img
    src="https://example.org/diagram.png"
    alt="Protected component attribute"
  />
</div>

Read the diagram above.
