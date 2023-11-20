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

However, these rules were being handled as external routes by SvelteKit without taking advantage of partial reloadings. I've tried using [$app/navigation](https://kit.svelte.dev/docs/modules#$app-navigation) without success. Therefore, the simplest solution was: overwrite 