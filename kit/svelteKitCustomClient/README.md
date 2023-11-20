# Custom `sveltekit client.js` file

Sveltekit handles [internal routes](https://kit.svelte.dev/docs/routing) by:

1. partially loading changed components
2. updating the browser's [history](https://developer.mozilla.org/en-US/docs/Web/API/History)

which makes the user experience better by not loading/reloading pages completely from scratch.

### Hugging Face docs

In [hf docs](https://huggingface.co/docs), we have these redirection rules:

```
hf.co/docs/lib/page -> hf.co/docs/lib/default_version/default_lang/page
hf.co/docs/lib/version/page -> hf.co/docs/lib/version/default_lang/page
```

However, these rules were being handled as external routes by SvelteKit without taking advantage of partial reloadings. I've tried using [$app/navigation](https://kit.svelte.dev/docs/modules#$app-navigation) without success. Therefore, the simplest solution was: overwriting [sveltekit client.js](https://github.com/sveltejs/kit/blob/master/packages/kit/src/runtime/client/client.js) to handle hf doc routes accordingly.

Specifically, this [custom client.js](https://github.com/huggingface/doc-builder/blob/ab03d33801595579591ac8cdc49514c4f59fe068/kit/svelteKitCustomClient/client.js) is identical to [sveltekit client.js](https://github.com/sveltejs/kit/blob/master/packages/kit/src/runtime/client/client.js) with only one difference: addition and usage of [getHfDocFullPath function](https://github.com/huggingface/doc-builder/blob/ab03d33801595579591ac8cdc49514c4f59fe068/kit/svelteKitCustomClient/client.js#L43), which makes it possible for hf redirected paths (as described above) to be considered as `internal routes` and take full advantage of partial loading.
